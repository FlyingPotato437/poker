"""Fallback bot: a from-scratch implementation of FALLBACK_SPEC.md (stdlib only, one file).

This is what Codex should end up with if pre-written code is not allowed. Every number here is
in the spec; the section numbers in comments (S1..S7) point at it.

Interface: SpecBot().act(obs) -> (kind, amount), kind 0 fold / 1 check-call / 2 raise-to.
`obs` is any object (or dict) with the fields of nolimit.runtime.Obs:
    hole, board, street (0 pre, 1 flop, 2 turn, 3 river), seat, button, stacks, bets, in_hand,
    pot, to_call, min_raise_to (0 = cannot raise), max_raise_to, sb, bb, hand_no,
    history ((seat, street, kind, amount_to, all_in), ...; kind 3 = blind post)
Cards may be ints (rank = c // 4, 0 = deuce; suit = c % 4) or strings ("As", "Td", "10h").
"""
import gc
import math
import random
import time

FOLD, CALL, RAISE, POST = 0, 1, 2, 3

# --- S1. Tables ---------------------------------------------------------------------------
# 169 starting hands, strongest first (our bundle's order: multiway equity).
HAND_ORDER = (
    "AA KK QQ JJ TT 99 88 AKs 77 AQs AJs AKo AQo ATs AJo KQs 66 A9s KJs ATo A8s KTs KQo A9o "
    "A7s QJs KJo 55 K9s A6s A5s KTo QTs A8o A4s A7o A3s K8s QJo K9o A5o K7s A6o JTs Q9s QTo "
    "A2s 44 K6s A4o Q8s A3o K8o K5s K7o J9s Q9o A2o JTo K4s Q7s K6o T9s J8s K3s Q6s K5o Q8o "
    "33 J9o K2s Q5s J7s K4o T8s Q4s Q7o K3o J8o T9o T7s Q6o 98s Q3s J6s K2o 22 J5s Q2s Q5o "
    "J7o Q4o T8o J4s T6s 97s Q3o J3s 98o T7o 87s J6o 96s J2s Q2o J5o T5s J4o T4s 86s 97o T6o "
    "95s T3s J3o 76s 87o T2s 85s J2o T5o 96o 94s 75s T4o 86o 93s 65s 84s T3o 95o 92s 76o 74s "
    "54s T2o 85o 64s 83s 94o 82s 75o 65o 93o 73s 53s 63s 84o 92o 43s 74o 72s 54o 64o 52s 62s "
    "83o 82o 42s 73o 53o 63o 32s 43o 72o 52o 62o 42o 32o")
# Heads-up equity (%) vs a random hand, same order as HAND_ORDER.
E1_STR = (
    "85 82 80 77 75 72 69 67 66 66 65 65 64 65 64 63 63 63 63 63 62 62 61 61 61 60 61 60 60 "
    "60 60 60 59 60 59 59 58 58 58 58 58 58 58 58 58 57 57 57 57 57 56 56 56 56 55 56 55 55 "
    "55 55 54 54 54 54 54 54 53 54 54 53 53 53 52 52 52 52 52 51 52 52 51 51 51 51 51 50 50 "
    "50 50 50 50 49 50 49 49 49 48 48 48 48 48 48 47 47 47 47 47 46 47 46 46 46 46 46 45 45 "
    "45 45 45 44 44 44 44 44 44 43 43 43 43 43 43 42 42 42 42 42 41 41 41 41 40 40 40 40 40 "
    "40 39 39 39 39 39 38 38 38 38 38 38 37 37 37 36 36 36 35 35 34 34 33 32")
# Equity vs a "top y of hands" range: logit(eq) = c0 + c1*logit(E1) + c2*pair + c3*min(r,0)
# + c4*max(r,0), r = ln(clamp(pct / y, 0.05, 20)); interpolate linearly in y between rows.
EQR = ((0.03, -0.950, 0.629, -0.497, -0.971, -0.110), (0.06, -0.821, 0.350, -0.078, -0.657, -0.057),
       (0.10, -0.682, 0.215, 0.025, -0.554, -0.077), (0.15, -0.572, 0.182, 0.036, -0.480, -0.118),
       (0.20, -0.548, 0.218, 0.030, -0.438, -0.114), (0.30, -0.549, 0.430, 0.019, -0.344, -0.010),
       (0.45, -0.488, 0.793, -0.048, -0.206, 0.227), (0.65, -0.308, 1.056, -0.091, -0.078, 0.551),
       (1.00, 0.000, 1.000, 0.000, 0.000, 0.000))
# ICM push/fold (default points 100,65,45,30,20,12,6,0). Columns: effective stack in bb.
PF_STACKS = (2, 3, 4, 5, 6, 8, 10, 12, 15, 18, 21)
# SHOVE[n]: one row per position 0..n-2 (0 = first to act, n-2 = SB; HU: the SB/button).
# Value = top % of hands to open-shove when folded to you.
SHOVE = {
    2: "90 78 74 74 70 65 59 54 48 41 37",
    3: "36 49 51 49 46 44 40 34 28 25 21 | 67 77 78 77 75 69 64 63 57 52 47",
    4: "34 45 42 43 41 36 29 25 21 19 16 | 38 51 52 52 54 50 45 39 32 24 22 | 68 80 85 84 86 82 82 73 68 62 62",
    5: "31 37 38 37 33 26 24 21 17 15 13 | 33 43 44 46 43 39 29 27 22 21 17 | 37 51 51 53 54 53 48 41 32 26 26 "
       "| 69 83 87 87 88 87 86 82 76 71 66",
    6: "28 32 33 27 26 23 18 17 15 14 14 | 30 37 39 38 33 27 24 20 17 16 15 | 34 43 44 46 44 38 31 28 25 22 18 "
       "| 37 50 53 55 56 54 54 42 34 28 26 | 70 83 87 88 94 95 90 91 83 80 67",
    7: "26 28 26 23 24 18 17 15 14 13 12 | 28 31 32 27 26 23 19 17 15 14 14 | 30 36 37 38 34 27 23 21 18 16 15 "
       "| 33 42 44 46 44 38 31 28 24 24 19 | 36 49 54 56 57 54 54 43 37 27 27 | 69 84 87 91 96 97 91 92 84 82 69",
    8: "22 24 22 23 19 17 15 14 14 12 8 | 25 28 26 25 25 18 18 15 15 14 13 | 28 32 33 27 27 23 20 19 15 15 15 "
       "| 30 36 39 39 33 29 25 22 19 16 16 | 33 43 46 46 47 37 32 28 26 22 20 | 37 49 54 58 60 56 55 50 37 30 31 "
       "| 71 85 91 95 97 100 95 97 89 83 75",
}
# Calling an all-in (top % of hands). Key: "hu" heads-up; n == 3: "3:KJ"; n >= 4: "KJ" with
# K = players left to act behind the shover when he shoved (cap 4), J = players still to act
# behind you (cap 2; 0 = you close the action).
CALL_T = {
    "hu": "99.9 92.7 72.7 61.7 54.7 44.6 38.4 32.8 27.5 23.4 20.7",
    "3:10": "91.8 60.1 48.8 40.5 35.4 28.3 23.2 19.3 15.7 13.2 11.5",
    "3:20": "80.5 41.9 32.8 27.5 23.2 17.2 13.6 10.6 8.4 7.1 6.1",
    "3:21": "8.6 15.2 13.7 12.2 11.1 9.8 8.5 8.0 7.1 5.8 5.4",
    "10": "70.7 49.6 39.0 32.4 27.3 21.0 17.1 14.4 11.7 9.8 8.5",
    "20": "53.0 32.2 25.6 20.2 17.3 12.4 9.3 7.7 6.2 5.4 5.1",
    "21": "14.6 15.3 12.5 11.5 9.7 8.5 7.5 6.5 5.4 4.6 3.3",
    "30": "49.7 28.5 21.0 16.3 12.8 8.5 6.9 5.7 5.2 3.6 3.0",
    "31": "13.1 12.9 10.7 9.0 8.1 7.0 5.5 5.3 3.3 3.0 2.9",
    "32": "6.7 7.2 7.1 6.8 6.4 5.4 5.0 3.4 3.0 3.0 2.5",
    "40": "39.6 20.9 13.4 9.9 7.7 5.8 4.4 3.7 2.9 2.5 2.1",
    "41": "11.7 9.8 8.2 7.0 6.1 4.7 3.9 2.9 2.5 2.1 1.8",
    "42": "6.2 6.1 5.6 4.8 4.2 3.3 2.7 2.4 2.0 1.7 1.5",
}
# ICM bubble factor: equal stacks, whole stack at risk, by players left.
BF_FULL = {2: 1.00, 3: 1.41, 4: 1.57, 5: 1.64, 6: 1.73, 7: 1.75, 8: 1.76}
# Multiplier on (BF - 1) by [hero short/even/big][villain short/even/big]; short < 0.7/n, big > 1.4/n.
BF_SHARE = ((0.41, 0.53, 0.81), (0.29, 1.00, 1.49), (0.15, 0.44, 2.36))
# Open-raise share by players left to act behind (0..7).
SH_OPEN = (0.50, 0.50, 0.42, 0.28, 0.23, 0.19, 0.16, 0.14)
# Postflop equity vs ONE random hand (S4): POST_EQ[street][bucket] (%) + ADJ[group] . features,
# features = (hi, lo, flush_board, connected_board, paired_board), see board_feats().
POST_EQ = {
    1: (28, 33, 49, 68, 80, 75, 72, 73, 86, 94, 96, 104, 97),
    2: (21, 26, 35, 66, 75, 77, 75, 75, 88, 96, 95, 100, 96),
    3: (16, 16, 16, 65, 65, 79, 77, 77, 89, 98, 98, 102, 99),
}
GROUP = (0, 0, 0, 1, 1, 2, 2, 2, 3, 3, 3, 3, 3)    # air / weak pair / top pair+overpair / strong
ADJ = ((0.193, 0.028, -0.037, -0.032, 0.057), (0.056, 0.112, -0.073, -0.044, 0.047),
       (0.088, 0.041, -0.079, -0.049, 0.001), (0.028, 0.012, -0.086, -0.041, -0.024))
# eq vs k random hands = eq1 ** (k ** MW_EXP)   (k = 2: ^1.84, k = 3: ^2.63)
MW_EXP = 0.88
# Opponent-model priors (Beta mean, weight 6 pseudo-observations).
PRIORS = {"vpip": 0.35, "pfr": 0.18, "shove": 0.06, "fold_to_bet": 0.45, "agg": 0.45}
PRIOR_W = 6.0

# --- S2. Parameters ---------------------------------------------------------------------------
P = dict(
    open_base=0.264, open_late=0.426, open_bb=2.965, sh_open_scale=1.15, steal_exploit=2.03,
    iso_pct=0.103, sb_complete=0.727, hu_sb_play=0.80, reraise_eq=0.588, reraise_mult=3.22,
    pre_realize=0.922, pre_tighten=0.438,
    pf_bb=21.0, pf_shove_scale=1.167, pf_call_scale=1.348, pf_exploit=1.61, pf_margin=0.019,
    icm_weight=0.96,
    vbet_eq=0.648, vbet_frac=0.76, bluff_freq=0.381, bluff_max_eq=0.402, bluff_frac=0.584,
    raise_eq=0.813, raise_frac=0.821, call_margin=0.094, realize=0.823, tighten=0.79,
    commit_spr=1.52, commit_eq=0.59, station_value=0.20,
)
DEADLINE_S = 0.0006

RANKS = "23456789TJQKA"
SUITS = "cdhs"


def _build_pct():
    pct, cum = {}, 0
    names = HAND_ORDER.split()
    e1 = E1_STR.split()
    assert len(names) == 169 and len(e1) == 169
    for n, e in zip(names, e1):
        cum += 6 if len(n) == 2 else (4 if n[2] == "s" else 12)
        pct[n] = (cum / 1326.0, int(e) / 100.0)
    return pct


HAND = _build_pct()                          # name -> (percentile 0..1, E1)
_SHOVE = {n: [[int(x) / 100.0 for x in r.split()] for r in s.split("|")] for n, s in SHOVE.items()}
_CALL = {k: [float(x) / 100.0 for x in s.split()] for k, s in CALL_T.items()}


def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def card(c):
    """(rank 2..14, suit 0..3) from an int (rank*4 + suit) or a string like 'As' / '10h'."""
    if isinstance(c, int):
        return c // 4 + 2, c % 4
    s = str(c).strip()
    r = s[:-1].upper().replace("10", "T")
    return RANKS.index(r) + 2, SUITS.index(s[-1].lower())


def hand_name(hole):
    (r1, s1), (r2, s2) = sorted((card(c) for c in hole), reverse=True)
    if r1 == r2:
        return RANKS[r1 - 2] * 2
    return RANKS[r1 - 2] + RANKS[r2 - 2] + ("s" if s1 == s2 else "o")


def interp(row, x):
    st = PF_STACKS
    if x <= st[0]:
        return row[0]
    for i in range(len(st) - 1):
        if x <= st[i + 1]:
            t = (x - st[i]) / (st[i + 1] - st[i])
            return row[i] * (1 - t) + row[i + 1] * t
    return row[-1]


def logit(p):
    p = clamp(p, 1e-4, 1 - 1e-4)
    return math.log(p / (1 - p))


def eq_vs_range(name, y):
    """Heads-up preflop equity of hand `name` vs the top-y share of hands."""
    pct, e1 = HAND[name]
    y = clamp(y, 0.03, 1.0)
    pair = 1.0 if len(name) == 2 else 0.0
    r = math.log(clamp(pct / y, 0.05, 20.0))

    def z(c):
        return c[1] + c[2] * logit(e1) + c[3] * pair + c[4] * min(r, 0.0) + c[5] * max(r, 0.0)
    for i in range(len(EQR) - 1):
        lo, hi = EQR[i], EQR[i + 1]
        if y <= hi[0]:
            t = (y - lo[0]) / (hi[0] - lo[0])
            v = z(lo) * (1 - t) + z(hi) * t
            return 1.0 / (1.0 + math.exp(-v))
    return e1


def bubble_factor(n, mine, theirs, total, risk_frac):
    if n < 2 or total <= 0:
        return 1.0
    b = BF_FULL[min(n, 8)] - 1.0
    if b <= 0:
        return 1.0

    def cls(share):
        return 0 if share < 0.7 / n else 2 if share > 1.4 / n else 1
    m = BF_SHARE[cls(mine / total)][cls(theirs / total)]
    return 1.0 + b * m * clamp(risk_frac, 0.0, 1.0) ** 1.2


# --- S4. Postflop hand buckets -------------------------------------------------------------
def _straight_high(rs):
    """Highest straight top card in rank set rs (ace also plays low), else 0."""
    s = set(rs)
    if 14 in s:
        s.add(1)
    for top in range(14, 4, -1):
        if all(top - k in s for k in range(5)):
            return top
    return 0


def _cat(cards):
    """Category 0 high, 1 pair, 2 two pair, 3 trips, 4 straight, 5 flush, 6 full house+."""
    rc, sc = {}, {}
    for r, s in cards:
        rc[r] = rc.get(r, 0) + 1
        sc[s] = sc.get(s, 0) + 1
    cnt = sorted(rc.values(), reverse=True)
    if cnt[0] >= 4 or (cnt[0] == 3 and len(cnt) > 1 and cnt[1] >= 2):
        return 6
    if max(sc.values()) >= 5:
        return 5
    if _straight_high(rc):
        return 4
    if cnt[0] == 3:
        return 3
    if cnt[0] == 2 and len(cnt) > 1 and cnt[1] == 2:
        return 2
    return 1 if cnt[0] == 2 else 0


def post_bucket(hole, board):
    """0 air, 1 air + weak draw, 2 strong draw, 3 weak pair, 4 weak pair + strong draw,
    5 top pair weak kicker, 6 top pair kicker >= T, 7 overpair, 8 two pair (both hole cards),
    9 trips/set, 10 straight, 11 flush, 12 full house or better."""
    h = [card(c) for c in hole]
    b = [card(c) for c in board]
    allc = h + b
    cat, bcat = _cat(allc), (_cat(b) if len(b) >= 3 else 0)
    if cat >= 6 and bcat < 6:
        return 12
    if cat == 5 and bcat < 5:
        return 11
    if cat == 4 and bcat < 4:
        return 10
    hr = [r for r, _ in h]
    br = [r for r, _ in b]
    if cat == 3 or cat == 6:
        if any(br.count(r) + hr.count(r) >= 3 and r in hr for r in set(hr)):
            return 9
    paired = [r for r in set(hr) if r in br]
    pocket = hr[0] == hr[1]
    top = max(br)
    if len(paired) == 2:
        return 8
    # draws (not on the river)
    strong = weak = False
    if len(b) < 5:
        sc = {}
        for r, s in allc:
            sc[s] = sc.get(s, 0) + 1
        hs = {s for _, s in h}
        strong = any(v == 4 and s in hs for s, v in sc.items())
        rs = set(r for r, _ in allc)
        outs = 0
        for x in range(2, 15):
            if x not in rs and _straight_high(rs | {x}) and not _straight_high(set(br) | {x}):
                outs += 1
        if outs >= 2:
            strong = True
        elif outs == 1 or min(hr) > top:
            weak = True
    if pocket and hr[0] > top:
        return 7
    if paired:
        r = paired[0]
        if r == top:
            kick = max(x for x in hr if x != r) if not pocket else r
            return 6 if kick >= 10 or len(set(hr)) == 1 else 5
        return 4 if strong else 3
    if pocket:
        return 4 if strong else 3
    if strong:
        return 2
    return 1 if weak else 0


def board_feats(hole, board):
    """(hi, lo, flush_board, connected_board, paired_board): hole ranks scaled to -1 (2) .. +1 (A);
    board has 3+ of a suit; 3 distinct board ranks within a span of 4; board has a pair."""
    hr = sorted((card(c)[0] for c in hole), reverse=True)
    b = [card(c) for c in board]
    br = sorted(set(r for r, _ in b))
    sc = {}
    for _, s in b:
        sc[s] = sc.get(s, 0) + 1
    conn = any(br[i + 2] - br[i] <= 4 for i in range(len(br) - 2))
    return ((hr[0] - 8) / 6.0, (hr[1] - 8) / 6.0, float(max(sc.values()) >= 3), float(conn),
            float(len(br) < len(b)))


def post_equity1(hole, board, street):
    """Equity vs one random hand."""
    k = post_bucket(hole, board)
    f = board_feats(hole, board)
    a = ADJ[GROUP[k]]
    e = POST_EQ[min(street, 3)][k] / 100.0 + sum(x * y for x, y in zip(a, f))
    return clamp(e, 0.02, 0.99)


# --- S5. Opponent model ----------------------------------------------------------------------
class Seat:
    __slots__ = ("hands", "vpip", "pfr", "shove", "faced", "folded", "aggr", "passive", "acts", "allin")

    def __init__(self):
        for k in self.__slots__:
            setattr(self, k, 0)

    def rate(self, k):
        num, den = {"vpip": (self.vpip, self.hands), "pfr": (self.pfr, self.hands),
                    "shove": (self.shove, self.hands), "fold_to_bet": (self.folded, self.faced),
                    "agg": (self.aggr, self.aggr + self.passive)}[k]
        return (num + PRIORS[k] * PRIOR_W) / (den + PRIOR_W)

    def jammer(self):
        return self.acts >= 5 and self.allin >= 0.9 * self.acts


def ingest(stats, history):
    seen, vp, pr, sh = set(), set(), set(), set()
    street, bets = -1, {}
    for seat, st, kind, amt, all_in in history:
        if seat >= len(stats):
            continue
        seen.add(seat)
        if st != street:
            street, bets = st, {}
        cur = max(bets.values()) if bets else 0
        prev = bets.get(seat, 0)
        if kind == POST:
            bets[seat] = amt
            continue
        s = stats[seat]
        s.acts += 1
        s.allin += bool(all_in)
        if st == 0:
            if kind == RAISE:
                vp.add(seat)
                pr.add(seat)
                if all_in:
                    sh.add(seat)
            elif kind == CALL and amt > prev:
                vp.add(seat)
        else:
            if cur > prev:
                s.faced += 1
                s.folded += kind == FOLD
            if kind == RAISE:
                s.aggr += 1
            elif kind == CALL and amt > prev:
                s.passive += 1
        if kind in (CALL, RAISE):
            bets[seat] = amt
    for seat in seen:
        s = stats[seat]
        s.hands += 1
        s.vpip += seat in vp
        s.pfr += seat in pr
        s.shove += seat in sh


def _get(obs, k):
    return obs[k] if isinstance(obs, dict) else getattr(obs, k)


class _O:
    """Normalized observation (cards parsed once)."""

    def __init__(self, obs):
        for k in ("street", "seat", "button", "pot", "to_call", "min_raise_to", "max_raise_to", "bb", "hand_no"):
            setattr(self, k, _get(obs, k))
        self.stacks, self.bets = list(_get(obs, "stacks")), list(_get(obs, "bets"))
        self.in_hand = list(_get(obs, "in_hand"))
        self.hole, self.board = list(_get(obs, "hole")), list(_get(obs, "board"))
        self.history = tuple(tuple(h) for h in _get(obs, "history"))


# --- S6/S7. The bot --------------------------------------------------------------------------
class SpecBot:
    def __init__(self, tables=None, seed=None, params=None):
        self.p = dict(P, **(params or {}))
        self.rng = random.Random(seed)
        self.T = tables
        self.new_table(0, 8)

    def new_table(self, seat, n_seats):
        gc.collect()                    # outside the timed path
        self.seat = seat
        self.stats = [Seat() for _ in range(n_seats)]
        self.done = set()               # hand numbers already ingested
        self.cur_hand, self.cur_hist = None, ()

    def observe(self, event):
        try:
            kind, info = event
            if kind == "hand_end" and info["hand_no"] not in self.done:
                self.done.add(info["hand_no"])
                ingest(self.stats, info["history"])
        except Exception:
            pass

    def act(self, obs):
        self.t0 = time.perf_counter()
        try:
            o = _O(obs)
            return self.legal(o, self._act(o))
        except Exception:
            return (CALL, 0) if _get(obs, "to_call") <= 0 else (FOLD, 0)

    @staticmethod
    def legal(o, a):
        kind, amt = a
        if kind == RAISE and o.min_raise_to > 0:
            return (RAISE, int(clamp(int(amt), o.min_raise_to, max(o.max_raise_to, o.min_raise_to))))
        if kind == FOLD and o.to_call > 0:
            return (FOLD, 0)
        return (CALL, 0)

    def late(self):
        return time.perf_counter() - self.t0 > DEADLINE_S

    def _act(self, o):
        if len(self.stats) != len(o.stacks):
            self.stats = [Seat() for _ in o.stacks]
        if o.hand_no != self.cur_hand:          # new hand: ingest the last one if never reported
            if self.cur_hand is not None and self.cur_hand not in self.done:
                self.done.add(self.cur_hand)
                ingest(self.stats, self.cur_hist)
            self.cur_hand = o.hand_no
        self.cur_hist = o.history
        self.seat = o.seat
        if o.street == 0:
            return self.preflop(o)
        return self.postflop(o)

    # -- equity hooks (scripts/ab_spec.py swaps in exact tables here to measure what each costs)
    def eqr(self, name, y):
        return eq_vs_range(name, y)

    def post_eq(self, o, n):
        return post_equity1(o.hole, o.board, o.street) ** (n ** MW_EXP)

    # -- helpers
    def raise_to(self, o, target):
        if o.min_raise_to <= 0:
            return (CALL, 0)
        amt = max(o.min_raise_to, int(target))
        if amt >= 0.85 * o.max_raise_to:
            amt = o.max_raise_to
        return (RAISE, min(amt, o.max_raise_to))

    def shove(self, o):
        return (RAISE, o.max_raise_to) if o.min_raise_to > 0 else (CALL, 0)

    def need(self, o, villain):
        """Equity needed to call with the ICM bubble factor: BF*c / (BF*c + pot)."""
        c, me = o.to_call, o.seat
        n_alive = sum(1 for s in range(len(o.stacks)) if o.stacks[s] + o.bets[s] > 0 or o.in_hand[s])
        total = sum(o.stacks) + max(o.pot, sum(o.bets))
        mine, theirs = o.stacks[me] + o.bets[me], o.stacks[villain] + o.bets[villain]
        eff = max(min(mine, theirs), 1)
        bf = bubble_factor(n_alive, mine, theirs, total, c / eff)
        bf = 1.0 + self.p["icm_weight"] * (bf - 1.0)
        return bf * c / max(bf * c + o.pot, 1)

    def order(self, o):
        """Preflop action order of the seats dealt in: first to act ... big blind."""
        n = len(o.stacks)
        posts = [h[0] for h in o.history if h[2] == POST]
        dealt = {h[0] for h in o.history} | {i for i in range(n) if o.in_hand[i]}
        bb_seat = posts[1] if len(posts) >= 2 else (posts[0] if posts else o.button)
        return [(bb_seat + k) % n for k in range(1, n + 1) if (bb_seat + k) % n in dealt]

    def avg_vpip(self, seats):
        return sum(self.stats[s].rate("vpip") for s in seats) / len(seats) if seats else PRIORS["vpip"]

    # -- S3. preflop
    def preflop(self, o):
        p, me = self.p, o.seat
        name = hand_name(o.hole)
        pct = HAND[name][0]
        opps = [s for s in range(len(o.stacks)) if o.in_hand[s] and s != me]
        if not opps:
            return (CALL, 0)
        mine = o.stacks[me] + o.bets[me]
        eff_bb = min(mine, max(o.stacks[s] + o.bets[s] for s in opps)) / max(o.bb, 1)
        raises = [h for h in o.history if h[1] == 0 and h[2] == RAISE]
        order = self.order(o)
        pos = order.index(me) if me in order else 0
        if eff_bb <= p["pf_bb"]:
            return self.pushfold(o, name, pct, order, pos, raises, eff_bb)
        behind = [s for s in order[pos + 1:] if o.in_hand[s] and o.stacks[s] > 0]
        if not raises:
            limpers = sum(1 for h in o.history if h[1] == 0 and h[2] == CALL and h[3] > 0)
            if o.to_call == 0:                          # limped pot, our option
                return self.raise_to(o, (3 + limpers) * o.bb) if pct <= p["iso_pct"] else (CALL, 0)
            n_others = max(len(order) - 1, 1)
            thr = p["open_base"] + (p["open_late"] - p["open_base"]) * (1 - len(behind) / n_others)
            thr = max(thr, SH_OPEN[min(len(behind), 7)] * p["sh_open_scale"])
            if limpers:
                thr = p["iso_pct"]
            if behind:                                  # E1: steal wider vs tight players behind
                thr = min(1.0, thr * (PRIORS["vpip"] / max(self.avg_vpip(behind), 0.05)) ** (0.5 * p["steal_exploit"]))
            if pct <= thr:
                return self.raise_to(o, p["open_bb"] * o.bb + limpers * o.bb)
            comp = p["hu_sb_play"] if len(order) == 2 else p["sb_complete"]
            if limpers == 0 and o.to_call <= o.bb // 2 + 1 and pct <= comp:
                return (CALL, 0)
            return (FOLD, 0)
        raiser = raises[-1][0]
        st = self.stats[raiser]
        y = st.rate("pfr") * p["pre_tighten"] ** (len(raises) - 1)
        if raises[-1][4]:
            y = min(y, st.rate("shove") * 2.5)
        if st.jammer():
            y = 1.0
        eq = self.eqr(name, clamp(y, 0.01, 1.0))
        if len(opps) > 1:
            eq = eq ** (1 + 0.6 * (len(opps) - 1))
        if eq >= p["reraise_eq"] and len(raises) < 4 and o.min_raise_to > 0:
            target = max(o.bets) * p["reraise_mult"]
            return self.shove(o) if target >= 0.35 * mine else self.raise_to(o, target)
        if eq * p["pre_realize"] >= self.need(o, raiser):
            return (CALL, 0)
        return (FOLD, 0)

    def pushfold(self, o, name, pct, order, pos, raises, eff_bb):
        p, me, n = self.p, o.seat, len(order)
        if not raises:
            behind = [s for s in order[pos + 1:] if o.in_hand[s]]
            rows = _SHOVE.get(min(max(n, 2), 8))
            if pos < len(rows):
                thr = interp(rows[pos], eff_bb)
            else:                                       # BB after limps / no chart row
                thr = clamp(0.9 / (1 + 0.35 * len(behind)) * (6.0 / max(eff_bb, 1.0)) ** 0.5, 0.03, 1.0)
            if behind:                                  # E2: shove wider vs tables that rarely call
                thr *= (PRIORS["vpip"] / max(self.avg_vpip(behind), 0.05)) ** (0.5 * p["pf_exploit"])
            thr = clamp(thr * p["pf_shove_scale"], 0.0, 1.0)
            if o.to_call == 0:                          # limped to us in the BB
                return self.shove(o) if pct <= thr * 0.6 else (CALL, 0)
            return self.shove(o) if pct <= thr else (FOLD, 0)
        shover = raises[-1][0]
        st = self.stats[shover]
        spos = order.index(shover) if shover in order else 0
        need = self.need(o, shover) + p["pf_margin"]
        if st.hands >= 12 or st.jammer():               # E3: call on equity vs the shover's range
            y = 1.0 if st.jammer() else clamp(max(st.rate("shove"), st.rate("pfr") * 0.8) * 1.5, 0.02, 1.0)
            call = self.eqr(name, y) >= need
        else:
            if n <= 2:
                key = "hu"
            else:
                ks, j = n - 1 - spos, n - 1 - pos
                key = "3:%d%d" % (ks, j) if n == 3 else "%d%d" % (min(ks, 4), min(j, 2))
            row = _CALL.get(key)
            call = row is not None and pct <= interp(row, eff_bb) * p["pf_call_scale"]
        if call and sum(1 for s in order if o.in_hand[s] and s != me) > 1:
            call = self.eqr(name, 0.08) >= 0.5      # multiway: premiums only
        if not call:
            return (FOLD, 0)
        return self.shove(o) if o.min_raise_to > 0 else (CALL, 0)

    # -- S4. postflop
    def postflop(self, o):
        p, me = self.p, o.seat
        opps = [s for s in range(len(o.stacks)) if o.in_hand[s] and s != me]
        if not opps:
            return (CALL, 0)
        n = len(opps)
        eq = self.post_eq(o, n)
        aggr = 0.0
        for seat, st, kind, _a, _ai in o.history:
            if st > 0 and kind == RAISE and seat != me:
                aggr += clamp(PRIORS["agg"] / max(self.stats[seat].rate("agg"), 0.05), 0.4, 2.0)
        eq = eq ** (1 + p["tighten"] * aggr)
        pot, stack = o.pot, o.stacks[me]
        mine = stack + o.bets[me]
        folds = sum(self.stats[s].rate("fold_to_bet") for s in opps) / n
        if o.to_call == 0:
            # E4: value-bet thinner vs players who rarely fold
            vb = p["vbet_eq"] - p["station_value"] * max(0.0, PRIORS["fold_to_bet"] - folds)
            if eq >= vb:
                if stack <= p["commit_spr"] * pot and eq >= p["commit_eq"]:
                    return self.shove(o)
                return self.raise_to(o, o.bets[me] + p["vbet_frac"] * pot)
            if n <= 2 and eq <= p["bluff_max_eq"]:
                if self.rng.random() < p["bluff_freq"] * folds / PRIORS["fold_to_bet"] / n:
                    return self.raise_to(o, o.bets[me] + p["bluff_frac"] * pot)
            return (CALL, 0)
        if eq >= p["raise_eq"] and o.min_raise_to > 0:
            target = max(o.bets) + p["raise_frac"] * (pot + o.to_call)
            if target >= 0.4 * mine or stack <= p["commit_spr"] * pot:
                return self.shove(o)
            return self.raise_to(o, target)
        villain = self.aggressor(o)
        need = self.need(o, villain) + p["call_margin"]
        return (CALL, 0) if eq * p["realize"] >= need else (FOLD, 0)

    def aggressor(self, o):
        for seat, st, kind, _a, _ai in reversed(o.history):
            if st == o.street and kind == RAISE and seat != o.seat:
                return seat
        return max((s for s in range(len(o.bets)) if s != o.seat), key=lambda s: o.bets[s])


def gc_setup():
    """Call once at import in the submission (not in simulations): keep GC out of decisions."""
    gc.collect()
    if hasattr(gc, "freeze"):
        gc.freeze()
    gc.disable()


def make_bot(tables=None, seed=None):
    return SpecBot(tables, seed=seed)

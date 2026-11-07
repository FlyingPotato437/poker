import gc
import math
from time import perf_counter

gc.collect()
gc.freeze()
gc.disable()

FOLD, CALL, RAISE, POST = 0, 1, 2, 3

HAND_ORDER = """AA KK QQ JJ TT 99 88 AKs 77 AQs AJs AKo AQo ATs AJo KQs 66 A9s KJs ATo A8s KTs KQo A9o
A7s QJs KJo 55 K9s A6s A5s KTo QTs A8o A4s A7o A3s K8s QJo K9o A5o K7s A6o JTs Q9s QTo
A2s 44 K6s A4o Q8s A3o K8o K5s K7o J9s Q9o A2o JTo K4s Q7s K6o T9s J8s K3s Q6s K5o Q8o
33 J9o K2s Q5s J7s K4o T8s Q4s Q7o K3o J8o T9o T7s Q6o 98s Q3s J6s K2o 22 J5s Q2s Q5o
J7o Q4o T8o J4s T6s 97s Q3o J3s 98o T7o 87s J6o 96s J2s Q2o J5o T5s J4o T4s 86s 97o T6o
95s T3s J3o 76s 87o T2s 85s J2o T5o 96o 94s 75s T4o 86o 93s 65s 84s T3o 95o 92s 76o 74s
54s T2o 85o 64s 83s 94o 82s 75o 65o 93o 73s 53s 63s 84o 92o 43s 74o 72s 54o 64o 52s 62s
83o 82o 42s 73o 53o 63o 32s 43o 72o 52o 62o 42o 32o""".split()
E1S = """85 82 80 77 75 72 69 67 66 66 65 65 64 65 64 63 63 63 63 63 62 62 61 61 61 60 61 60 60
60 60 60 59 60 59 59 58 58 58 58 58 58 58 58 58 57 57 57 57 57 56 56 56 56 55 56 55 55
55 55 54 54 54 54 54 54 53 54 54 53 53 53 52 52 52 52 52 51 52 52 51 51 51 51 51 50 50
50 50 50 50 49 50 49 49 49 48 48 48 48 48 48 47 47 47 47 47 46 47 46 46 46 46 46 45 45
45 45 45 44 44 44 44 44 44 43 43 43 43 43 43 42 42 42 42 42 41 41 41 41 40 40 40 40 40
40 39 39 39 39 39 38 38 38 38 38 38 37 37 37 36 36 36 35 35 34 34 33 32""".split()

PCT = {}
E1H = {}
_cum = 0
for _i, _h in enumerate(HAND_ORDER):
    _cum += 6 if len(_h) == 2 else (4 if _h[2] == 's' else 12)
    PCT[_h] = _cum / 1326.0
    E1H[_h] = int(E1S[_i]) / 100.0
assert len(HAND_ORDER) == 169 and len(E1S) == 169

EQR = [
    (0.03, -0.950, 0.629, -0.497, -0.971, -0.110), (0.06, -0.821, 0.350, -0.078, -0.657, -0.057),
    (0.10, -0.682, 0.215, 0.025, -0.554, -0.077), (0.15, -0.572, 0.182, 0.036, -0.480, -0.118),
    (0.20, -0.548, 0.218, 0.030, -0.438, -0.114), (0.30, -0.549, 0.430, 0.019, -0.344, -0.010),
    (0.45, -0.488, 0.793, -0.048, -0.206, 0.227), (0.65, -0.308, 1.056, -0.091, -0.078, 0.551),
    (1.00, 0.000, 1.000, 0.000, 0.000, 0.000)]

BF_FULL = {2: 1.00, 3: 1.41, 4: 1.57, 5: 1.64, 6: 1.73, 7: 1.75, 8: 1.76}
BF_SHARE = [[0.41, 0.53, 0.81],
            [0.29, 1.00, 1.49],
            [0.15, 0.44, 2.36]]

PF_STACKS = [2, 3, 4, 5, 6, 8, 10, 12, 15, 18, 21]


def _row(s):
    return [float(x) / 100.0 for x in s.split()]


_SHOVE_RAW = {
    2: "90 78 74 74 70 65 59 54 48 41 37",
    3: "36 49 51 49 46 44 40 34 28 25 21 | 67 77 78 77 75 69 64 63 57 52 47",
    4: "34 45 42 43 41 36 29 25 21 19 16 | 38 51 52 52 54 50 45 39 32 24 22 | 68 80 85 84 86 82 82 73 68 62 62",
    5: "31 37 38 37 33 26 24 21 17 15 13 | 33 43 44 46 43 39 29 27 22 21 17 | 37 51 51 53 54 53 48 41 32 26 26 | 69 83 87 87 88 87 86 82 76 71 66",
    6: "28 32 33 27 26 23 18 17 15 14 14 | 30 37 39 38 33 27 24 20 17 16 15 | 34 43 44 46 44 38 31 28 25 22 18 | 37 50 53 55 56 54 54 42 34 28 26 | 70 83 87 88 94 95 90 91 83 80 67",
    7: "26 28 26 23 24 18 17 15 14 13 12 | 28 31 32 27 26 23 19 17 15 14 14 | 30 36 37 38 34 27 23 21 18 16 15 | 33 42 44 46 44 38 31 28 24 24 19 | 36 49 54 56 57 54 54 43 37 27 27 | 69 84 87 91 96 97 91 92 84 82 69",
    8: "22 24 22 23 19 17 15 14 14 12 8 | 25 28 26 25 25 18 18 15 15 14 13 | 28 32 33 27 27 23 20 19 15 15 15 | 30 36 39 39 33 29 25 22 19 16 16 | 33 43 46 46 47 37 32 28 26 22 20 | 37 49 54 58 60 56 55 50 37 30 31 | 71 85 91 95 97 100 95 97 89 83 75",
}
SHOVE = {n: [_row(r) for r in v.split('|')] for n, v in _SHOVE_RAW.items()}

_CALL_RAW = {
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
CALLCH = {k: _row(v) for k, v in _CALL_RAW.items()}

POST_EQ = {
    1: (28, 33, 49, 68, 80, 75, 72, 73, 86, 94, 96, 104, 97),
    2: (21, 26, 35, 66, 75, 77, 75, 75, 88, 96, 95, 100, 96),
    3: (16, 16, 16, 65, 65, 79, 77, 77, 89, 98, 98, 102, 99)}
ADJ = [(0.193, 0.028, -0.037, -0.032, 0.057),
       (0.056, 0.112, -0.073, -0.044, 0.047),
       (0.088, 0.041, -0.079, -0.049, 0.001),
       (0.028, 0.012, -0.086, -0.041, -0.024)]

CURVE = {
    1: ((-0.080, 0.173, 0.307, 0.061, 0.133, -0.044, 0.010),
        [(1.417, 0.777, 0.176), (0.956, 0.340, 0.035), (0.727, 0.173, 0.020), (1.108, 0.310, 0.034),
         (0.775, 0.042, 0.001), (0.830, -0.012, -0.188), (0.568, -0.147, -0.259), (0.559, -0.355, -0.248),
         (0.226, -0.435, -0.235), (0.070, -0.711, -0.258), (0.135, -0.718, -0.157), (0.331, -0.471, -0.087),
         (-0.410, -1.131, -0.331)]),
    2: ((-0.098, 0.079, 0.302, 0.062, 0.193, -0.081, 0.019),
        [(2.152, 1.175, 0.278), (1.459, 0.571, 0.133), (1.190, 0.401, 0.077), (1.716, 0.440, 0.050),
         (1.309, 0.241, 0.056), (1.325, 0.006, -0.228), (1.084, -0.154, -0.264), (1.011, -0.494, -0.265),
         (0.814, -0.409, -0.229), (0.501, -0.633, -0.274), (0.545, -0.753, -0.175), (0.517, -0.659, -0.334),
         (-0.058, -1.033, -0.435)]),
    3: ((-0.087, -0.285, 0.311, 0.104, 0.633, -0.236, 0.041),
        [(4.316, 1.738, 0.688), (2.663, -0.216, -0.235), (2.663, -0.216, -0.235), (4.254, 0.856, 0.249),
         (2.663, -0.216, -0.235), (3.649, -0.068, -0.325), (3.199, -0.451, -0.507), (2.944, -0.897, -0.516),
         (2.942, -0.656, -0.448), (2.194, -0.805, -0.496), (2.057, -0.802, -0.285), (2.055, -0.569, -0.490),
         (1.684, -0.722, -0.454)]),
}

# name: (base, exploit)
SETTINGS = {
    'open_base': (0.2643, 0.2654), 'open_late': (0.4262, 0.4165), 'open_bb': (2.965, 2.842),
    'steal_exploit': (2.031, 1.752), 'iso_pct': (0.1030, 0.1541), 'sb_complete_pct': (0.7267, 0.7694),
    'reraise_eq': (0.5884, 0.6112), 'reraise_mult': (3.221, 2.903), 'pre_realize': (0.9222, 0.9486),
    'pre_tighten': (0.4378, 0.4141), 'pf_bb': (21.09, 16.54), 'pf_shove_scale': (1.167, 1.087),
    'pf_call_scale': (1.348, 1.384), 'pf_exploit': (1.609, 1.325), 'pf_margin': (0.01941, 0.02509),
    'icm_weight': (0.9605, 0.8630),
    'realize': (0.8195, 0.8219), 'realize_chk': (0.8665, 0.8811), 'ev_margin': (0.04654, 0.03703),
    'call_ev_margin': (0.08401, 0.07154), 'risk_av': (1.032, 1.228), 'risk_depth': (28.24, 26.98),
    'raise_cont': (0.9975, 1.072), 'call_width': (1.445, 1.415),
    'cont_b0': (1.035, 1.175), 'cont_b1': (1.633, 1.713), 'cont_b2': (-1.784, -1.766),
    'cont_b3': (-0.267, -0.3887), 'cont_b4': (-2.719, -2.337),
    'rng_y_scale': (2.126, 1.834), 'rng_bet_scale': (1.556, 1.590), 'rng_check_cap': (0.6540, 0.3317),
    'rng_call_cut': (0.9865, 0.9073), 'rng_persist': (0.3338, 0.3326),
}
LEVELS = []
for _L in range(5):
    LEVELS.append({k: b + (_L / 4.0) * (e - b) for k, (b, e) in SETTINGS.items()})

SH_OPEN = (0.50, 0.50, 0.42, 0.28, 0.23, 0.19, 0.16, 0.14)
POST_SIZES = (0.33, 0.66, 1.0, 1.5)
RAISE_SIZES = (0.8, 1.3)
PO_REF = 0.65 / 2.3

RANKCH = "23456789TJQKA"


def clamp(x, lo, hi):
    return lo if x < lo else (hi if x > hi else x)


def sigmoid(z):
    z = clamp(z, -60.0, 60.0)
    return 1.0 / (1.0 + math.exp(-z))


def logit(p):
    p = clamp(p, 1e-4, 1 - 1e-4)
    return math.log(p / (1 - p))


def hand_name(hole):
    a, b = hole[0], hole[1]
    ra, rb = a // 4, b // 4
    if ra < rb:
        ra, rb = rb, ra
        a, b = b, a
    if ra == rb:
        return RANKCH[ra] + RANKCH[rb]
    return RANKCH[ra] + RANKCH[rb] + ('s' if a % 4 == b % 4 else 'o')


def eqr_name(name, y):
    pct = PCT[name]
    e1 = E1H[name]
    y = clamp(y, 0.03, 1.0)
    r = math.log(clamp(pct / y, 0.05, 20.0))
    L = logit(e1)
    pair = 1.0 if name[0] == name[1] else 0.0

    def zrow(row):
        return row[1] + row[2] * L + row[3] * pair + row[4] * min(r, 0.0) + row[5] * max(r, 0.0)
    if y <= 0.03:
        return sigmoid(zrow(EQR[0]))
    for i in range(1, len(EQR)):
        if EQR[i - 1][0] < y <= EQR[i][0]:
            lo, hi = EQR[i - 1], EQR[i]
            t = (y - lo[0]) / (hi[0] - lo[0])
            return sigmoid(zrow(lo) * (1 - t) + zrow(hi) * t)
    return sigmoid(zrow(EQR[-1]))


def BF(n, hs, vs, risk):
    if n < 2:
        return 1.0

    def cls(s):
        if s < 0.7 / n:
            return 0
        if s > 1.4 / n:
            return 2
        return 1
    return 1 + (BF_FULL[min(n, 8)] - 1) * BF_SHARE[cls(hs)][cls(vs)] * clamp(risk, 0.0, 1.0) ** 1.2


def chart_lookup(row, eff_bb):
    if eff_bb <= PF_STACKS[0]:
        return row[0]
    if eff_bb >= PF_STACKS[-1]:
        return row[-1]
    for i in range(1, len(PF_STACKS)):
        if eff_bb <= PF_STACKS[i]:
            t = (eff_bb - PF_STACKS[i - 1]) / float(PF_STACKS[i] - PF_STACKS[i - 1])
            return row[i - 1] * (1 - t) + row[i] * t
    return row[-1]


# ---------------- postflop evaluation ----------------

def has_straight(rs):
    s = set(rs)
    if 14 in s:
        s.add(1)
    for lo in range(1, 11):
        if all((lo + k) in s for k in range(5)):
            return True
    return False


def category(cards):
    ranks = [c // 4 + 2 for c in cards]
    suits = [c % 4 for c in cards]
    cnt = {}
    for r in ranks:
        cnt[r] = cnt.get(r, 0) + 1
    vals = list(cnt.values())
    quads = 4 in vals
    ntrips = sum(1 for v in vals if v == 3)
    npairs = sum(1 for v in vals if v == 2)
    flush_suit = None
    for s in range(4):
        if suits.count(s) >= 5:
            flush_suit = s
    if quads or (ntrips >= 1 and (npairs >= 1 or ntrips >= 2)):
        return 6
    if flush_suit is not None:
        fr = [c // 4 + 2 for c in cards if c % 4 == flush_suit]
        if has_straight(fr):
            return 6
        return 5
    if has_straight(cnt.keys()):
        return 4
    if ntrips >= 1:
        return 3
    if npairs >= 2:
        return 2
    if npairs == 1:
        return 1
    return 0


def bucket_info(hole, board):
    """returns (bucket, group)"""
    allc = list(hole) + list(board)
    cat = category(allc)
    bcat = category(board) if len(board) >= 3 else 0
    hr = [c // 4 + 2 for c in hole]
    br = [c // 4 + 2 for c in board]
    top = max(br)
    pocket = hr[0] == hr[1]
    paired = []
    for r in hr:
        if r in br and r not in paired:
            paired.append(r)
    allr = hr + br
    if cat >= 6 and bcat < 6:
        return 12, 3
    if cat == 5 and bcat < 5:
        return 11, 3
    if cat == 4 and bcat < 4:
        return 10, 3
    if cat in (3, 6) and any(allr.count(r) >= 3 for r in hr):
        return 9, 3
    if len(paired) == 2:
        return 8, 3
    strong = weak = False
    if len(board) in (3, 4):
        suits = [c % 4 for c in allc]
        for s in range(4):
            if suits.count(s) == 4 and any(c % 4 == s for c in hole):
                strong = True
        hbr = set(allr)
        bset = set(br)
        outs = 0
        for x in range(2, 15):
            if x in hbr:
                continue
            if has_straight(hbr | {x}) and not has_straight(bset | {x}):
                outs += 1
        if outs >= 2:
            strong = True
        if not strong and (outs == 1 or (hr[0] > top and hr[1] > top)):
            weak = True
    if pocket and hr[0] > top:
        return 7, 2
    if paired:
        r = paired[0]
        if r == top:
            other = hr[1] if hr[0] == r else hr[0]
            if pocket:
                other = r
            return (6, 2) if other >= 10 else (5, 2)
        return (4, 1) if strong else (3, 1)
    if pocket:
        return (4, 1) if strong else (3, 1)
    if strong:
        return 2, 0
    if weak:
        return 1, 0
    return 0, 0


def e1_post(hole, board, street, bucket, group):
    hr = sorted([c // 4 + 2 for c in hole], reverse=True)
    hi = (hr[0] - 8) / 6.0
    lo = (hr[1] - 8) / 6.0
    suits = [c % 4 for c in board]
    fb = 1.0 if any(suits.count(s) >= 3 for s in range(4)) else 0.0
    brs = sorted(set(c // 4 + 2 for c in board))
    cb = 0.0
    for i in range(len(brs) - 2):
        if brs[i + 2] - brs[i] <= 4:
            cb = 1.0
    allbr = [c // 4 + 2 for c in board]
    pb = 1.0 if len(set(allbr)) < len(allbr) else 0.0
    a = ADJ[group]
    v = POST_EQ[street][bucket] / 100.0 + a[0] * hi + a[1] * lo + a[2] * fb + a[3] * cb + a[4] * pb
    return clamp(v, 0.02, 0.99)


def RE(street, bucket, L, y, x):
    c = CURVE[street]
    c0, d1, d2, d3, d4, d5, d6 = c[0]
    A, B, C = c[1][bucket]
    lx = math.log(clamp(x, 0.05, 1.0))
    ly = math.log(clamp(y, 0.08, 1.0))
    z = (L + c0 + A * lx + B * ly + C * lx * ly + d1 * L * lx + d2 * L * ly + d3 * L * lx * ly
         + d4 * lx * lx + d5 * L * lx * lx + d6 * ly * ly)
    return sigmoid(z)


def IE(street, bucket, L, y, a, b):
    if b - a < 0.04:
        b = min(1.0, a + 0.04)
        a = b - 0.04
    eb = RE(street, bucket, L, y, b)
    if a < 0.002:
        return eb
    ea = RE(street, bucket, L, y, a)
    return clamp((b * eb - a * ea) / (b - a), 0.0, 1.0)


# ---------------- stats ----------------

FIELDS = ("hands vpip pfr shove faced folded raised faced_ab folded_ab bet_opp bets "
          "aggr passive acts allin minr fs_n fs_f fs_r").split()

LAM_COEF = [("vpip", -42.0452, 77.96), ("pfr", -1.6526, -27.8091), ("agg", 5.9021, -3.169),
            ("fold_to_bet", -16.0593, 6.8088), ("shove", 11.7009, 26.4823),
            ("bet", -10.378, 1.5881), ("fold_nb", -8.5967, 9.9044)]


def new_counters():
    return {f: 0 for f in FIELDS}


def rate(num, den, prior):
    return (num + prior * 6.0) / (den + 6.0)


def rates_of(c):
    g = lambda k: c.get(k, 0)
    return {
        'vpip': rate(g('vpip'), g('hands'), 0.35),
        'pfr': rate(g('pfr'), g('hands'), 0.18),
        'shove': rate(g('shove'), g('hands'), 0.06),
        'fold_to_bet': rate(g('folded'), g('faced'), 0.45),
        'agg': rate(g('aggr'), g('aggr') + g('passive'), 0.45),
        'bet': rate(g('bets'), g('bet_opp'), 0.40),
        'raise': rate(g('raised'), g('faced'), 0.12),
        'fold_nb': rate(g('folded') - g('folded_ab'), g('faced') - g('faced_ab'), 0.35),
        'fold_ab': rate(g('folded_ab'), g('faced_ab'), 0.15),
    }


def lam_of(c):
    hands = c.get('hands', 0)
    if hands == 0:
        return 0.0
    r = rates_of(c)
    z = 16.0915
    for k, a, b in LAM_COEF:
        z += r[k] * (a + b * r[k])
    if z < -30:
        return 0.0
    return hands / (hands + 15.0) * sigmoid(z)


def kind_of(c):
    acts = c.get('acts', 0)
    if acts >= 5 and (c.get('allin', 0) >= 0.9 * acts or c.get('minr', 0) >= 0.75 * acts):
        return 2
    if c.get('hands', 0) >= 8 and c.get('vpip', 0) == 0 and c.get('aggr', 0) == 0 and c.get('passive', 0) == 0:
        return 1
    return 0


def ingest_hand(stats, history):
    street = -1
    bets = {}
    aggr_set = set()
    bb = inc = 1
    n_r = 0
    opener = -1
    acted0 = set()
    seen, vp, pr, sh = set(), set(), set(), set()
    for ent in history:
        seat, st, kind, amt, all_in = ent[0], ent[1], ent[2], ent[3], ent[4]
        c = stats.setdefault(seat, new_counters())
        seen.add(seat)
        if st != street:
            street = st
            bets = {}
            aggr_set = set()
            inc = bb
        cur = max(bets.values()) if bets else 0
        prev = bets.get(seat, 0)
        if kind == POST:
            bets[seat] = amt
            if amt > bb:
                bb = inc = amt
            continue
        c['acts'] += 1
        if all_in:
            c['allin'] += 1
        if kind == RAISE:
            if amt - cur > inc:
                inc = amt - cur
            elif not all_in:
                c['minr'] += 1
        if st == 0:
            if n_r == 0 and kind == RAISE and not all_in:
                opener = seat
            if n_r == 1 and opener >= 0 and seat != opener and seat not in acted0:
                c['fs_n'] += 1
                if kind == FOLD:
                    c['fs_f'] += 1
                elif kind == RAISE:
                    c['fs_r'] += 1
            acted0.add(seat)
            if kind == RAISE:
                n_r += 1
                vp.add(seat)
                pr.add(seat)
                if all_in:
                    sh.add(seat)
            elif kind == CALL and amt > prev:
                vp.add(seat)
        else:
            if cur > prev:
                c['faced'] += 1
                if seat in aggr_set:
                    c['faced_ab'] += 1
                if kind == FOLD:
                    c['folded'] += 1
                    if seat in aggr_set:
                        c['folded_ab'] += 1
                elif kind == RAISE:
                    c['raised'] += 1
            else:
                c['bet_opp'] += 1
                if kind == RAISE:
                    c['bets'] += 1
            if kind == RAISE:
                c['aggr'] += 1
                aggr_set.add(seat)
            elif kind == CALL and amt > prev:
                c['passive'] += 1
        if kind == CALL or kind == RAISE:
            bets[seat] = amt
    for s in seen:
        c = stats.setdefault(s, new_counters())
        c['hands'] += 1
        c['vpip'] += 1 if s in vp else 0
        c['pfr'] += 1 if s in pr else 0
        c['shove'] += 1 if s in sh else 0


# ---------------- the bot ----------------

class SpecBot:
    def __init__(self):
        gc.collect()
        self.stats = {}
        self.n_seats = None
        self.me = None
        self.last_key = None
        self.last_hist = None
        self.last_ingested = True
        self.ingested_hands = set()
        self.lam_cache = {}

    def new_table(self, seat, n_seats):
        gc.collect()
        self.stats = {}
        self.n_seats = n_seats
        self.me = seat
        self.last_key = None
        self.last_hist = None
        self.last_ingested = True
        self.ingested_hands = set()
        self.lam_cache = {}

    def observe(self, event):
        try:
            kind, d = event[0], event[1]
            if kind == "hand_end":
                hn = d.get("hand_no")
                if hn in self.ingested_hands:
                    return
                self.ingested_hands.add(hn)
                ingest_hand(self.stats, d["history"])
                self.last_ingested = True
                self.lam_cache = {}
        except Exception:
            pass

    # --- stat accessors
    def cnt(self, s):
        return self.stats.get(s) or new_counters()

    def rts(self, s):
        c = self.stats.get(s)
        if c is None:
            c = new_counters()
        return rates_of(c)

    def lam_seat(self, s):
        c = self.stats.get(s)
        if c is None:
            return 0.0
        return lam_of(c)

    def kind_seat(self, s):
        c = self.stats.get(s)
        if c is None:
            return 0
        return kind_of(c)

    # --- act
    def act(self, obs):
        t0 = perf_counter()
        try:
            return self.legal(obs, self.decide(obs, t0))
        except Exception:
            return (CALL, 0) if obs.to_call <= 0 else (FOLD, 0)

    def legal(self, obs, a):
        kind, amt = a
        if kind == FOLD:
            if obs.to_call <= 0:
                return (CALL, 0)
            return (FOLD, 0)
        if kind == RAISE:
            if obs.min_raise_to <= 0:
                return (CALL, 0)
            amt = int(clamp(amt, obs.min_raise_to, max(obs.max_raise_to, obs.min_raise_to)))
            return (RAISE, amt)
        return (CALL, 0)

    def decide(self, obs, t0):
        n = len(obs.stacks)
        if self.n_seats is not None and self.n_seats != n:
            self.stats = {}
            self.ingested_hands = set()
        self.n_seats = n
        self.me = obs.seat
        key = (obs.hand_no, tuple(obs.hole))
        if key != self.last_key:
            if self.last_key is not None and not self.last_ingested and self.last_hist is not None:
                if self.last_key[0] not in self.ingested_hands:
                    self.ingested_hands.add(self.last_key[0])
                    ingest_hand(self.stats, self.last_hist)
            self.last_key = key
            self.last_ingested = False
        self.last_hist = [tuple(e) for e in obs.history]
        me = obs.seat
        opps = [s for s in range(n) if s != me and obs.in_hand[s]]
        self.opps = opps
        lam = 1.0
        hist = obs.history
        if obs.street == 0:
            acted = set(e[0] for e in hist if e[2] != POST)
            raisers = set(e[0] for e in hist if e[2] == RAISE)
            for s in opps:
                if s in acted:
                    if s not in raisers:
                        continue
                    x = 1.0 if self.kind_seat(s) == 2 else self.lam_seat(s)
                else:
                    if obs.stacks[s] <= 0:
                        continue
                    if self.kind_seat(s) != 0:
                        x = 1.0
                    else:
                        x = 1 - (1 - self.lam_seat(s)) * min(1.0, self.rts(s)['vpip'])
                lam = min(lam, x)
        else:
            for s in opps:
                x = 1.0 if self.kind_seat(s) == 2 else self.lam_seat(s)
                lam = min(lam, x)
        level = int(lam * 4 + 0.5)
        self.level = level
        p = LEVELS[level]
        self.p = p
        if obs.street == 0:
            return self.preflop(obs, p, opps)
        return self.postflop(obs, p, opps, t0)

    # --- helpers
    def raise_to(self, obs, target):
        if obs.min_raise_to <= 0:
            return (CALL, 0)
        amt = max(obs.min_raise_to, int(target))
        if amt >= 0.85 * obs.max_raise_to:
            amt = obs.max_raise_to
        return (RAISE, min(amt, obs.max_raise_to))

    def jam(self, obs):
        if obs.min_raise_to <= 0:
            return (CALL, 0)
        return (RAISE, obs.max_raise_to)

    def n_alive(self, obs):
        return sum(1 for s in range(len(obs.stacks)) if obs.stacks[s] + obs.bets[s] > 0 or obs.in_hand[s])

    def need(self, obs, p, v):
        c = obs.to_call
        me = obs.seat
        n_alive = self.n_alive(obs)
        total = sum(obs.stacks) + max(obs.pot, sum(obs.bets))
        mine = obs.stacks[me] + obs.bets[me]
        theirs = obs.stacks[v] + obs.bets[v]
        eff = min(mine, theirs)
        if total > 0 and eff > 0:
            bf = 1 + p['icm_weight'] * (BF(n_alive, mine / total, theirs / total, c / eff) - 1)
        else:
            bf = 1.0
        return bf * c / max(bf * c + obs.pot, 1)

    # --- preflop
    def preflop(self, obs, p, opps):
        me = obs.seat
        n_seats = len(obs.stacks)
        hist = obs.history
        bb = obs.bb
        posts = [e[0] for e in hist if e[2] == POST]
        if len(posts) >= 2:
            bb_seat = posts[1]
        elif len(posts) == 1:
            bb_seat = posts[0]
        else:
            bb_seat = obs.button
        dealt = set(e[0] for e in hist) | set(s for s in range(n_seats) if obs.in_hand[s])
        order = [(bb_seat + k) % n_seats for k in range(1, n_seats + 1) if (bb_seat + k) % n_seats in dealt]
        pos = order.index(me) if me in order else 0
        my_total = obs.stacks[me] + obs.bets[me]
        if not opps:
            return (CALL, 0)
        eff_bb = min(my_total, max(obs.stacks[s] + obs.bets[s] for s in opps)) / float(bb)
        raises = [e for e in hist if e[1] == 0 and e[2] == RAISE]
        name = hand_name(obs.hole)
        pct = PCT[name]
        if eff_bb <= p['pf_bb']:
            return self.pushfold(obs, p, opps, order, pos, eff_bb, raises, name, pct)
        if not raises:
            return self.deep_open(obs, p, order, pos, name, pct)
        return self.deep_facing(obs, p, opps, raises, name, pct, my_total)

    def deep_open(self, obs, p, order, pos, name, pct):
        me = obs.seat
        bb = obs.bb
        hist = obs.history
        behind = []
        if me in order:
            behind = [s for s in order[pos + 1:] if obs.in_hand[s] and obs.stacks[s] > 0]
        limpers = sum(1 for e in hist if e[1] == 0 and e[2] == CALL and e[3] > 0)
        if obs.to_call == 0:
            if pct <= p['iso_pct']:
                return self.raise_to(obs, 3 * bb + limpers * bb)
            return (CALL, 0)
        thr = p['open_base'] + (p['open_late'] - p['open_base']) * (1 - len(behind) / float(max(len(order) - 1, 1)))
        thr = max(thr, SH_OPEN[min(len(behind), 7)] * 1.15)
        if limpers:
            thr = p['iso_pct']
        if behind:
            vp = sum(self.rts(s)['vpip'] for s in behind) / len(behind)
            thr = min(1.0, thr * (0.35 / max(vp, 0.05)) ** (0.5 * p['steal_exploit']))
            if not limpers:
                prod = 1.0
                for s in behind:
                    c = self.cnt(s)
                    if c['vpip'] > 0 or c['hands'] < 10:
                        prod *= (c['fs_f'] + 4.8) / (c['fs_n'] + 6.0)
                if prod >= 0.8 - 1e-9:
                    thr = 1.0
        if pct <= thr:
            return self.raise_to(obs, p['open_bb'] * bb + limpers * bb)
        comp = 0.8 if len(order) == 2 else p['sb_complete_pct']
        if not limpers and obs.to_call <= bb // 2 + 1 and pct <= comp:
            return (CALL, 0)
        return (FOLD, 0)

    def deep_facing(self, obs, p, opps, raises, name, pct, my_total):
        last = raises[-1]
        raiser = last[0]
        r = self.rts(raiser)
        y = r['pfr'] * p['pre_tighten'] ** (len(raises) - 1)
        if last[4]:
            y = min(y, 2.5 * r['shove'])
        y = clamp(y, 0.01, 1.0)
        eq = eqr_name(name, y)
        hist = obs.history
        n_in = sum(1 for s in opps if any(e[0] == s and e[1] == 0 and e[2] in (CALL, RAISE) for e in hist))
        n_live = n_in + 0.25 * (len(opps) - n_in)
        if n_live > 1:
            eq = eq ** (1 + 0.6 * (n_live - 1))
        if eq >= p['reraise_eq'] and len(raises) < 4 and obs.min_raise_to > 0:
            target = max(obs.bets) * p['reraise_mult']
            if target >= 0.35 * my_total:
                return self.jam(obs)
            return self.raise_to(obs, target)
        if eq * p['pre_realize'] >= self.need(obs, p, raiser):
            return (CALL, 0)
        return (FOLD, 0)

    def pushfold(self, obs, p, opps, order, pos, eff_bb, raises, name, pct):
        me = obs.seat
        n = len(order)
        if not raises:
            behind = order[pos + 1:] if me in order else []
            behind = [s for s in behind if obs.in_hand[s]]
            thr = None
            if n in SHOVE and pos <= n - 2:
                rows = SHOVE[n]
                if pos < len(rows):
                    thr = chart_lookup(rows[pos], eff_bb)
            if thr is None:
                thr = clamp(0.9 / (1 + 0.35 * len(behind)) * math.sqrt(6.0 / max(eff_bb, 1)), 0.03, 1.0)
            if behind:
                vp = sum(self.rts(s)['vpip'] for s in behind) / len(behind)
                thr *= (0.35 / max(vp, 0.05)) ** (0.5 * p['pf_exploit'])
            thr = clamp(thr * p['pf_shove_scale'], 0.0, 1.0)
            if obs.to_call == 0:
                if pct <= 0.6 * thr:
                    return self.jam(obs)
                return (CALL, 0)
            if pct <= thr:
                return self.jam(obs)
            return (FOLD, 0)
        shover = raises[-1][0]
        spos = order.index(shover) if shover in order else -1
        need_pf = self.need(obs, p, shover) + p['pf_margin']
        t = None
        if 2 <= n <= 8 and spos >= 0 and spos < pos < n:
            if n == 2:
                key = "hu"
            else:
                K = min(n - 1 - spos, 4)
                J = min(n - 1 - pos, 2)
                key = ("3:%d%d" % (K, J)) if n == 3 else ("%d%d" % (K, J))
            if key in CALLCH:
                t = CALLCH[key]
        r = self.rts(shover)
        if t is None or self.cnt(shover)['hands'] >= 12:
            y = clamp(1.5 * max(r['shove'], 0.8 * r['pfr']), 0.02, 1.0)
            call = eqr_name(name, y) >= need_pf
        else:
            call = pct <= chart_lookup(t, eff_bb) * p['pf_call_scale']
        if sum(1 for s in opps if s in order and obs.in_hand[s]) > 1:
            call = call and eqr_name(name, 0.08) >= 0.5
        if call:
            return self.jam(obs)
        return (FOLD, 0)

    # --- postflop
    def pre_y(self, obs, p, s):
        bets = {}
        nr = 0
        y = 1.0
        r = self.rts(s)
        for seat, st, kind, amt, all_in in obs.history:
            if st != 0:
                break
            if kind == POST:
                bets[seat] = amt
                continue
            prev = bets.get(seat, 0)
            if kind == RAISE:
                nr += 1
                if seat == s:
                    yr = r['pfr'] * p['pre_tighten'] ** (nr - 1)
                    if all_in:
                        yr = min(yr, 2.5 * r['shove'])
                    y = min(y, yr)
            elif kind == CALL and seat == s and amt > prev:
                y = min(y, r['vpip'] * p['pre_tighten'] ** max(nr - 1, 0))
            if kind == CALL or kind == RAISE:
                bets[seat] = amt
        return clamp(y * p['rng_y_scale'], 0.02, 1.0)

    def post_slice(self, obs, p, s):
        r = self.rts(s)
        g_bet = clamp(r['bet'] * p['rng_bet_scale'], 0.03, 1.0)
        g_raise = clamp(r['raise'] * p['rng_bet_scale'], 0.02, 1.0)
        cont = clamp(1 - r['fold_nb'], 0.05, 1.0)
        a, b = 0.0, 1.0
        street = 0
        bets = {}
        cur = 0
        ag = False
        k = p['rng_persist']
        for seat, st, kind, amt, _ in obs.history:
            if st == 0:
                continue
            if st != street:
                if street > 0:
                    a, b = a * k, 1 - (1 - b) * k
                street = st
                bets = {}
                cur = 0
            prev = bets.get(seat, 0)
            if seat == s:
                w = b - a
                if kind == RAISE:
                    b = a + w * (g_raise if cur > prev else g_bet)
                    ag = (st == obs.street)
                elif kind == CALL:
                    if cur > prev:
                        a, b = a + w * g_raise * p['rng_call_cut'], a + w * max(cont, g_raise)
                    else:
                        a = a + w * g_bet * p['rng_check_cap']
            if kind == RAISE:
                cur = amt
            if kind == CALL or kind == RAISE:
                bets[seat] = amt
        if street > 0 and street != obs.street:
            a, b = a * k, 1 - (1 - b) * k
        return a, b, ag

    def postflop(self, obs, p, opps, t0):
        me = obs.seat
        if not opps:
            return (CALL, 0)
        street = obs.street
        hole, board = obs.hole, obs.board
        bucket, group = bucket_info(hole, board)
        e1 = e1_post(hole, board, street, bucket, group)
        L = logit(e1)
        P = obs.pot
        bb = obs.bb
        ys, sl, rts = {}, {}, {}
        for s in opps:
            ys[s] = self.pre_y(obs, p, s)
            sl[s] = self.post_slice(obs, p, s)
        n = len(opps)
        corr = 1.0
        if n > 1:
            K = n ** 0.88 if n <= 3 else 3 ** 0.88 * n / 3.0
            corr = e1 ** ((K - n) / float(n))
        real = 1.0 if street == 3 else p['realize']

        def eq_vs(s, f=1.0):
            a, b, _ = sl[s]
            return min(1.0, IE(street, bucket, L, ys[s], a, a + (b - a) * f) * corr)

        W_now = 1.0
        for s in opps:
            W_now *= eq_vs(s) * real

        n_alive = self.n_alive(obs)
        total = sum(obs.stacks) + max(P, sum(obs.bets))
        mine = obs.stacks[me] + obs.bets[me]
        theirs = max(obs.stacks[s] + obs.bets[s] for s in opps)
        eff = max(min(mine, theirs), 1)
        ra = p['risk_av'] * min(1.0, mine / float(bb) / p['risk_depth'])

        def bfw(risk):
            if risk <= 0 or total <= 0:
                return 1.0
            return ((1 + ra * min(risk / float(max(mine, 1)), 1.0)) ** 2 *
                    (1 + p['icm_weight'] * (BF(n_alive, mine / float(total), theirs / float(total), risk / float(eff)) - 1)))

        def cont_prob(s, po):
            a, b, ag = sl[s]
            r = self.rts(s)
            c0 = clamp(1 - (r['fold_ab'] if ag else r['fold_nb']), 0.01, 0.99)
            z = (p['cont_b0'] + p['cont_b1'] * logit(c0) + p['cont_b2'] * math.log(max(po, 0.01) / PO_REF)
                 + p['cont_b3'] * (1.0 if ag else 0.0) + p['cont_b4'] * (a + b) / 2.0)
            return sigmoid(z)

        facing = obs.to_call > 0
        cmul = p['raise_cont'] if facing else 1.0

        def ev_raise(R):
            R = min(R, max(obs.stacks[s] + obs.bets[s] for s in opps))
            A = max(R - obs.bets[me], 0)
            pot_after = P + A
            W = 1.0
            parts = []
            for s in opps:
                d = max(min(R, obs.stacks[s] + obs.bets[s]) - obs.bets[s], 0)
                if d <= 0 or obs.stacks[s] == 0:
                    c = 1.0
                else:
                    c = clamp(cont_prob(s, d / float(max(pot_after + d, 1))) * cmul, 0.02, 1.0)
                q = eq_vs(s, min(1.0, c * p['call_width'])) * real
                w = (1 - c) + c * q
                W *= w
                parts.append((c * q * d, w))
            gain = P * W
            for cqd, w in parts:
                gain += cqd * W / max(w, 1e-9)
            return gain - A * (1 - W) * bfw(A)

        if not facing:
            best = (CALL, 0)
            best_ev = P * W_now * p['realize_chk'] + p['ev_margin'] * P
            targets = [obs.bets[me] + f * P for f in POST_SIZES]
        else:
            A = min(obs.to_call, obs.stacks[me])
            best = (FOLD, 0)
            best_ev = 0.0
            ev_call = P * W_now - A * (1 - W_now) * bfw(A) - p['call_ev_margin'] * A
            if ev_call > 0:
                best = (CALL, 0)
                best_ev = ev_call
            targets = [max(obs.bets) + f * (P + obs.to_call) for f in RAISE_SIZES]
        if obs.min_raise_to > 0:
            tried = set()
            for R in targets + [obs.max_raise_to]:
                R = int(clamp(R, obs.min_raise_to, obs.max_raise_to))
                if R >= 0.85 * obs.max_raise_to:
                    R = obs.max_raise_to
                if R in tried:
                    continue
                tried.add(R)
                if perf_counter() - t0 > 0.0006:
                    break
                ev = ev_raise(R)
                if ev > best_ev:
                    best_ev = ev
                    best = (RAISE, R)
        return best

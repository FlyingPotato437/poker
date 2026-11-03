"""Rival teams: our best guess at what smart teams ship after 60 minutes with Codex.

The rules (Nov 3 read) give every team a starter kit with an ICM calculator, payouts and the
blind schedule, plus Codex and public docs (published push/fold charts). So the field is not
"buggy hackathon bots": most teams are quant-minded and will ship sound, simple engines.
Each class below is one design a strong team would plausibly build; every instance draws
its own thresholds from the class's ranges (seeded), so a field of one class is many teams
with the same idea, not one bot copied.

Realism limits a real team has and these bots copy:
- Equity is a Monte Carlo estimate inside 1 ms of Python, so it is noisy: we add the noise
  of `rollouts` samples to our exact numbers.
- Only the better designs weight the villain's range (VPIP/PFR, betting this street); the
  rest use equity vs random hands.
- Push/fold uses published Nash charts (our solved charts stand in for them) and the kit's
  ICM calculator (our bubble factors).

DEV classes are for development (choosing, tuning). HOLDOUT classes play only in the
one-shot final test, after everything is frozen.
"""
import math

from .runtime import CALL, FOLD, POST, RAISE, SeatStats, ingest_history
from .zoo import _Base


def _clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


class _Rival(_Base):
    SPEC = {}          # name -> (lo, hi): this design's thresholds, drawn per instance
    rollouts = 150     # Monte Carlo samples behind each equity estimate
    ranged = False     # weights the villain's range (VPIP/PFR, betting this street)

    def __init__(self, tables=None, seed=None):
        super().__init__(tables, seed)
        self.k = {name: self.rng.uniform(lo, hi) for name, (lo, hi) in sorted(self.SPEC.items())}
        self.stats = []

    def new_table(self, seat, n_seats):
        self.stats = [SeatStats() for _ in range(n_seats)]

    def observe(self, event):
        kind, info = event
        if kind == "hand_end" and self.stats:
            ingest_history(self.stats, info["history"])

    def act(self, obs):
        if len(self.stats) != len(obs.stacks):
            self.new_table(obs.seat, len(obs.stacks))
        return self.decide(obs)

    # -- table facts ------------------------------------------------------
    def _villains(self, obs):
        return [s for s, h in enumerate(obs.in_hand) if h and s != obs.seat]

    def _alive(self, obs):
        return sum(1 for s in range(len(obs.stacks)) if obs.stacks[s] + obs.bets[s] > 0 or obs.in_hand[s])

    def _eff_bb(self, obs):
        vs = self._villains(obs)
        mine = obs.stacks[obs.seat] + obs.bets[obs.seat]
        theirs = max((obs.stacks[s] + obs.bets[s] for s in vs), default=mine)
        return min(mine, theirs) / max(obs.bb, 1)

    def _order(self, obs):
        n = len(obs.stacks)
        posts = [h[0] for h in obs.history if h[2] == POST]
        bb_seat = posts[1] if len(posts) >= 2 else posts[0] if posts else obs.button
        dealt = {h[0] for h in obs.history} | {i for i in range(n) if obs.in_hand[i]}
        return [(bb_seat + k) % n for k in range(1, n + 1) if (bb_seat + k) % n in dealt]

    def _late(self, obs):
        """0 = first to act preflop ... 1 = button/blinds: how few players are left behind."""
        order = self._order(obs)
        if obs.seat not in order or len(order) < 2:
            return 1.0
        return order.index(obs.seat) / (len(order) - 1)

    def _raises(self, obs, street=None):
        st = obs.street if street is None else street
        return [h for h in obs.history if h[1] == st and h[2] == RAISE]

    def _pfr_seat(self, obs):
        r = self._raises(obs, 0)
        return r[-1][0] if r else None

    def _po(self, obs):
        return obs.to_call / max(obs.pot + obs.to_call, 1)

    def _rate(self, s, name):
        return self.stats[s].rate(name) if self.stats else 0.3

    # -- equity -----------------------------------------------------------
    def _noise(self, e):
        sd = math.sqrt(max(e * (1 - e), 0.01) / self.rollouts)
        return _clamp(e + self.rng.gauss(0.0, sd), 0.0, 1.0)

    def _pre_eq(self, obs, y=None):
        cls = self.T.hole_class(obs.hole)
        if y is None or not self.ranged:
            return self._noise(self.T.eq(cls, len(self._villains(obs)) or 1))
        e = self.T.eq_vs_range(cls, _clamp(y, 0.02, 1.0))
        n = len(self._villains(obs))
        return self._noise(e ** (1 + 0.7 * (n - 1)) if n > 1 else e)

    def _post_eq(self, obs):
        vs = self._villains(obs) or [obs.seat]
        if self.ranged and getattr(self.T, "rng_net", None) is not None:
            curve = self.T.post_curve(obs.hole, obs.board)
            pfr = self._pfr_seat(obs)
            prod = 1.0
            for s in vs:
                y = self._rate(s, "pfr") if s == pfr else self._rate(s, "vpip")
                bet_now = any(h[0] == s for h in self._raises(obs))
                bet_before = any(h[0] == s and h[2] == RAISE and 0 < h[1] < obs.street for h in obs.history)
                x = 0.35 if bet_now else 0.7 if bet_before else 1.0
                prod *= self.T.range_equity(curve, _clamp(y, 0.03, 1.0), x)
            e = prod ** (0.85 if len(vs) > 1 else 1.0)
        else:
            eqs = self.T.post_equity(obs.hole, obs.board)
            n = len(vs)
            e = eqs[n - 1] if n <= 3 else eqs[2] ** (n / 3.0)
        return self._noise(e)

    def _need(self, obs, icm=True):
        """Equity needed to call, with the kit's ICM calculator (bubble factor) if `icm`."""
        po = self._po(obs)
        if not icm or not obs.to_call:
            return po
        vs = self._villains(obs)
        if not vs:
            return po
        v = max(vs, key=lambda s: obs.bets[s])
        total = sum(obs.stacks) + max(obs.pot, sum(obs.bets))
        mine = obs.stacks[obs.seat] + obs.bets[obs.seat]
        theirs = obs.stacks[v] + obs.bets[v]
        eff = min(mine, theirs)
        bf = self.T.bubble_factor(self._alive(obs), mine / total, theirs / total, obs.to_call / max(eff, 1)) \
            if total > 0 and eff > 0 else None
        if bf is None:
            return po
        return bf * po / max(bf * po + 1 - po, 1e-9)

    # -- push/fold from published charts -----------------------------------
    def _pushfold(self, obs, widen=1.0):
        order = self._order(obs)
        n = len(order)
        pos = order.index(obs.seat) if obs.seat in order else 0
        pct = self.T.pct(self.T.hole_class(obs.hole))
        eff = self._eff_bb(obs)
        raises = self._raises(obs, 0)
        if not raises:
            thr = self.T.shove_threshold(n, pos, eff)
            if thr is None:
                thr = _clamp(0.9 / (1 + 0.35 * (n - pos - 1)) * (6.0 / max(eff, 1.0)) ** 0.5, 0.03, 1.0)
            thr = _clamp(thr * widen, 0.0, 1.0)
            if obs.to_call == 0:
                return self._shove(obs) if pct <= 0.6 * thr else (CALL, 0)
            return self._shove(obs) if pct <= thr else (FOLD, 0)
        spos = order.index(raises[-1][0]) if raises[-1][0] in order else 0
        thr = self.T.call_threshold(n, spos, pos, eff)
        if thr is None:
            thr = 0.12
        if len(self._villains(obs)) > 1:
            thr *= 0.5
        return (self._shove(obs) if obs.min_raise_to > 0 else (CALL, 0)) if pct <= thr * widen else (FOLD, 0)


# ---------------------------------------------------------------------------
# DEV designs
# ---------------------------------------------------------------------------

class RivalTag(_Rival):
    """The careful quant team: positional opens, 3-bet or fold, range-weighted equity, value
    bets two-thirds pot, c-bets as the raiser, ICM-aware calls, Nash push/fold when short."""
    ranged = True
    rollouts = 300
    SPEC = {"open_early": (0.10, 0.15), "open_late": (0.30, 0.42), "three": (0.03, 0.06),
            "flat": (0.08, 0.14), "pf_bb": (12, 16), "vbet": (0.58, 0.68), "cbet": (0.45, 0.75),
            "size": (0.55, 0.75), "margin": (0.0, 0.04), "big_margin": (0.06, 0.14)}

    def decide(self, obs):
        k = self.k
        pct = self.T.pct(self.T.hole_class(obs.hole))
        if obs.street == 0:
            if self._eff_bb(obs) <= k["pf_bb"]:
                return self._pushfold(obs)
            raises = self._raises(obs, 0)
            if not raises:
                width = k["open_early"] + (k["open_late"] - k["open_early"]) * self._late(obs)
                if pct <= width:
                    return self._raise(obs, 2.5 * obs.bb + obs.bb * sum(1 for h in obs.history
                                                                         if h[1] == 0 and h[2] == CALL))
                return self._cf(obs)
            if pct <= k["three"] * (1.5 if len(raises) == 1 else 0.6):
                return self._raise(obs, max(obs.bets) * 3)
            y = self._rate(raises[-1][0], "pfr")
            if pct <= k["flat"] and self._pre_eq(obs, y) >= self._need(obs) + 0.05:
                return (CALL, 0)
            return self._cf(obs)
        eq = self._post_eq(obs)
        aggressor = self._pfr_seat(obs) == obs.seat
        n_v = len(self._villains(obs))
        if obs.to_call == 0:
            if eq >= k["vbet"]:
                return self._raise(obs, k["size"] * obs.pot)
            if obs.street == 1 and aggressor and n_v <= 2 and self.rng.random() < k["cbet"]:
                return self._raise(obs, 0.33 * obs.pot)
            return (CALL, 0)
        if eq >= 0.82 and self.rng.random() < 0.7:
            return self._raise(obs, max(obs.bets) * 2.8)
        big = obs.to_call >= 0.66 * (obs.pot - obs.to_call)
        return (CALL, 0) if eq >= self._need(obs) + (k["big_margin"] if big else k["margin"]) else (FOLD, 0)


class RivalLag(_Rival):
    """The aggressive team: wide steals, light 3-bets in position, double barrels, re-shoves."""
    ranged = True
    rollouts = 200
    SPEC = {"open_early": (0.16, 0.24), "open_late": (0.45, 0.60), "three": (0.07, 0.12),
            "flat": (0.12, 0.20), "pf_bb": (15, 22), "vbet": (0.55, 0.64), "barrel": (0.45, 0.70),
            "barrel_eq": (0.22, 0.35), "size": (0.65, 0.95), "margin": (-0.02, 0.03), "widen": (1.0, 1.3)}

    def decide(self, obs):
        k = self.k
        pct = self.T.pct(self.T.hole_class(obs.hole))
        late = self._late(obs)
        if obs.street == 0:
            if self._eff_bb(obs) <= k["pf_bb"]:
                return self._pushfold(obs, widen=k["widen"])
            raises = self._raises(obs, 0)
            if not raises:
                width = k["open_early"] + (k["open_late"] - k["open_early"]) * late
                return self._raise(obs, 2.2 * obs.bb) if pct <= width else self._cf(obs)
            if pct <= k["three"] * (0.5 + late) and len(raises) <= 2:
                return self._raise(obs, max(obs.bets) * 3)
            return (CALL, 0) if pct <= k["flat"] and self._po(obs) <= 0.4 else self._cf(obs)
        eq = self._post_eq(obs)
        heads_up = len(self._villains(obs)) == 1
        if obs.to_call == 0:
            if eq >= k["vbet"]:
                return self._raise(obs, k["size"] * obs.pot)
            if heads_up and obs.street < 3 and eq >= k["barrel_eq"] and self.rng.random() < k["barrel"]:
                return self._raise(obs, 0.6 * obs.pot)
            return (CALL, 0)
        if eq >= 0.78:
            return self._shove(obs) if self._eff_bb(obs) <= 25 else self._raise(obs, max(obs.bets) * 3)
        return (CALL, 0) if eq >= self._need(obs) + k["margin"] else (FOLD, 0)


class RivalGto(_Rival):
    """The 'solver-inspired' team: polarized bets with the textbook bluff ratio, defends by
    minimum defense frequency, check-raises its best hands and some draws, mixes at random."""
    ranged = True
    rollouts = 250
    SPEC = {"open_early": (0.12, 0.17), "open_late": (0.35, 0.48), "three": (0.05, 0.09),
            "flat": (0.10, 0.16), "pf_bb": (12, 18), "value": (0.25, 0.35), "size": (0.6, 1.0),
            "xr": (0.08, 0.16)}

    def decide(self, obs):
        k = self.k
        pct = self.T.pct(self.T.hole_class(obs.hole))
        if obs.street == 0:
            if self._eff_bb(obs) <= k["pf_bb"]:
                return self._pushfold(obs)
            raises = self._raises(obs, 0)
            if not raises:
                width = k["open_early"] + (k["open_late"] - k["open_early"]) * self._late(obs)
                if pct <= width or (pct <= 1.3 * width and self.rng.random() < 0.3):
                    return self._raise(obs, 2.5 * obs.bb)
                return self._cf(obs)
            if pct <= k["three"] or (pct <= 2.5 * k["three"] and self.rng.random() < 0.2):
                return self._raise(obs, max(obs.bets) * 3)
            return (CALL, 0) if pct <= k["flat"] else self._cf(obs)
        # Rank this hand inside "my range": equity vs random is a stand-in for the hand's place.
        eq = self._post_eq(obs)
        b = k["size"]
        bluff_share = b / (1 + 2 * b)               # bluffs : value that makes calls break even
        if obs.to_call == 0:
            if eq >= 1 - k["value"]:
                return self._raise(obs, b * obs.pot)
            if eq <= 0.25 and self.rng.random() < bluff_share * k["value"] / 0.25:
                return self._raise(obs, b * obs.pot)
            return (CALL, 0)
        bet_frac = obs.to_call / max(obs.pot - obs.to_call, 1)
        mdf = 1.0 / (1.0 + bet_frac)                # defend this share of hands vs the bet
        if eq >= 0.8 or (eq <= 0.2 and self.rng.random() < k["xr"] * 0.5):
            if self.rng.random() < k["xr"] * 4:
                return self._raise(obs, max(obs.bets) * 3)
        return (CALL, 0) if eq >= 1.0 - mdf * 0.95 else (FOLD, 0)


class RivalExploit(_Rival):
    """The opponent-modelling team: reads per-seat stats (fold to bet, aggression, VPIP) and
    bluffs over-folders, value-bets thin into stations, calls down maniacs, steals vs nits."""
    ranged = True
    rollouts = 250
    SPEC = {"open": (0.16, 0.24), "pf_bb": (12, 18), "vbet": (0.55, 0.65), "bluff_k": (0.6, 1.2),
            "thin": (0.06, 0.12), "light": (0.05, 0.12)}

    def decide(self, obs):
        k = self.k
        pct = self.T.pct(self.T.hole_class(obs.hole))
        vs = self._villains(obs)
        avg = lambda name: sum(self._rate(s, name) for s in vs) / max(len(vs), 1)
        if obs.street == 0:
            if self._eff_bb(obs) <= k["pf_bb"]:
                behind = avg("vpip")
                return self._pushfold(obs, widen=_clamp((0.35 / max(behind, 0.08)) ** 0.4, 0.8, 1.6))
            raises = self._raises(obs, 0)
            if not raises:
                width = k["open"] * (0.6 + 0.8 * self._late(obs)) * (0.35 / max(avg("vpip"), 0.1)) ** 0.5
                return self._raise(obs, 2.5 * obs.bb) if pct <= _clamp(width, 0.05, 0.6) else self._cf(obs)
            rp = self._rate(raises[-1][0], "pfr")
            if pct <= 0.25 * rp:
                return self._raise(obs, max(obs.bets) * 3)
            return (CALL, 0) if pct <= 0.6 * rp and self._po(obs) <= 0.35 else self._cf(obs)
        eq = self._post_eq(obs)
        folds, agg = avg("fold_to_bet"), avg("agg")
        station = folds < 0.3
        if obs.to_call == 0:
            if eq >= k["vbet"] - (k["thin"] if station else 0.0):
                return self._raise(obs, (0.8 if station else 0.6) * obs.pot)
            if len(vs) <= 2 and not station and self.rng.random() < k["bluff_k"] * (folds - 0.35):
                return self._raise(obs, 0.5 * obs.pot)
            return (CALL, 0)
        if eq >= 0.8:
            return self._raise(obs, max(obs.bets) * 3)
        light = k["light"] * (agg - 0.45) / 0.45
        return (CALL, 0) if eq >= self._need(obs) + 0.03 - light else (FOLD, 0)


class RivalIcm(_Rival):
    """The tournament team: tight early, ICM push/fold from 20 bb with widened Nash ranges,
    calls only with the bubble-factor price, value-heavy postflop."""
    ranged = True
    rollouts = 200
    SPEC = {"open_early": (0.08, 0.12), "open_late": (0.25, 0.35), "pf_bb": (18, 24),
            "widen": (1.05, 1.35), "vbet": (0.62, 0.72)}

    def decide(self, obs):
        k = self.k
        pct = self.T.pct(self.T.hole_class(obs.hole))
        if obs.street == 0:
            if self._eff_bb(obs) <= k["pf_bb"]:
                return self._pushfold(obs, widen=k["widen"])
            raises = self._raises(obs, 0)
            if not raises:
                width = k["open_early"] + (k["open_late"] - k["open_early"]) * self._late(obs)
                return self._raise(obs, 2.3 * obs.bb) if pct <= width else self._cf(obs)
            if pct <= 0.03:
                return self._raise(obs, max(obs.bets) * 3)
            return (CALL, 0) if pct <= 0.07 else self._cf(obs)
        eq = self._post_eq(obs)
        if obs.to_call == 0:
            return self._raise(obs, 0.6 * obs.pot) if eq >= k["vbet"] else (CALL, 0)
        if eq >= 0.85:
            return self._shove(obs)
        return (CALL, 0) if eq >= self._need(obs) + 0.05 else (FOLD, 0)


class RivalMc(_Rival):
    """The fast-build team: Monte Carlo equity vs random hands against pot odds, raises big
    hands, push/fold chart when short. No position, no reads."""
    rollouts = 80
    SPEC = {"raise_k": (1.5, 2.0), "margin": (0.0, 0.08), "pf_bb": (8, 12), "size": (0.5, 1.0)}

    def decide(self, obs):
        k = self.k
        n = max(len(self._villains(obs)), 1)
        if obs.street == 0 and self._eff_bb(obs) <= k["pf_bb"]:
            return self._pushfold(obs)
        eq = self._pre_eq(obs) if obs.street == 0 else self._post_eq(obs)
        if eq >= k["raise_k"] / (n + 1) and eq >= 0.45:
            return self._raise(obs, max(obs.bets) + k["size"] * obs.pot)
        if obs.to_call == 0:
            return (CALL, 0)
        return (CALL, 0) if eq >= self._po(obs) + k["margin"] else (FOLD, 0)


class RivalAggro(_Rival):
    """The 'aggression wins bot fights' team: raise-or-fold preflop, c-bets every flop,
    barrels with any draw, jams short stacks wide."""
    rollouts = 100
    SPEC = {"open": (0.30, 0.42), "jam_bb": (18, 28), "jam_pct": (0.2, 0.32), "barrel_eq": (0.3, 0.42)}

    def decide(self, obs):
        k = self.k
        pct = self.T.pct(self.T.hole_class(obs.hole))
        if obs.street == 0:
            if self._eff_bb(obs) <= k["jam_bb"]:
                return self._shove(obs) if pct <= k["jam_pct"] * (0.6 if self._raises(obs, 0) else 1.0) \
                    else self._cf(obs)
            if pct <= (k["open"] if not self._raises(obs, 0) else 0.08):
                return self._raise(obs, max(obs.bets) * 3 if self._raises(obs, 0) else 3 * obs.bb)
            return self._cf(obs)
        eq = self._post_eq(obs)
        if obs.to_call == 0:
            if obs.street == 1 or eq >= k["barrel_eq"]:
                return self._raise(obs, 0.75 * obs.pot)
            return (CALL, 0)
        if eq >= 0.7:
            return self._shove(obs)
        return (CALL, 0) if eq >= self._po(obs) + 0.02 else (FOLD, 0)


class RivalMath(_Rival):
    """The cautious 'math' team: equity vs random hands against pot odds, bets only strong
    hands, never bluffs. Over-calls bets, because equity vs random overstates hands vs bets."""
    rollouts = 120
    SPEC = {"vbet": (0.65, 0.75), "open": (0.15, 0.25), "margin": (-0.02, 0.04)}

    def decide(self, obs):
        k = self.k
        pct = self.T.pct(self.T.hole_class(obs.hole))
        if obs.street == 0:
            if self._eff_bb(obs) <= 10:
                return self._pushfold(obs, widen=0.8)
            if pct <= k["open"] * 0.3:
                return self._raise(obs, max(obs.bets) * 3)
            if pct <= k["open"]:
                return (CALL, 0) if self._po(obs) <= 0.3 else self._cf(obs)
            return self._cf(obs)
        eq = self._post_eq(obs)
        if obs.to_call == 0:
            return self._raise(obs, 0.5 * obs.pot) if eq >= k["vbet"] else (CALL, 0)
        return (CALL, 0) if eq >= self._po(obs) + k["margin"] else (FOLD, 0)


class RivalBuggy(_Rival):
    """A decent MC design shipped with integration bugs: ~3% of decisions error or time out
    (auto check/fold), and raises are sent as raise-by, which the host reads as near-min raises."""
    rollouts = 80
    SPEC = {"crash": (0.01, 0.05), "margin": (0.0, 0.06), "open": (0.18, 0.3)}

    def decide(self, obs):
        k = self.k
        if self.rng.random() < k["crash"]:
            return self._cf(obs)
        pct = self.T.pct(self.T.hole_class(obs.hole))
        if obs.street == 0:
            if pct <= k["open"]:
                return self._raise(obs, max(obs.bets) + obs.bb * 2)    # raise-by read as raise-to
            return (CALL, 0) if obs.to_call <= obs.bb and pct <= 0.5 else self._cf(obs)
        eq = self._post_eq(obs)
        if eq >= 0.65:
            return self._raise(obs, max(obs.bets) + 0.5 * obs.pot * 0.3)
        if obs.to_call == 0:
            return (CALL, 0)
        return (CALL, 0) if eq >= self._po(obs) + k["margin"] else (FOLD, 0)


class RivalFrozen(_Rival):
    """A variant-integration bug: the postflop evaluator never got wired to the variant, so
    the bot plays every street on its preflop hand strength."""
    SPEC = {"open": (0.15, 0.3), "bet_pct": (0.08, 0.15)}

    def decide(self, obs):
        k = self.k
        pct = self.T.pct(self.T.hole_class(obs.hole))
        if obs.street == 0:
            if pct <= k["open"] * 0.4:
                return self._raise(obs, max(obs.bets) * 3)
            return (CALL, 0) if pct <= k["open"] and self._po(obs) <= 0.33 else self._cf(obs)
        if pct <= k["bet_pct"]:
            return self._raise(obs, 0.66 * obs.pot)
        if obs.to_call == 0:
            return (CALL, 0)
        return (CALL, 0) if pct <= 2 * k["bet_pct"] and self._po(obs) <= 0.35 else (FOLD, 0)


# ---------------------------------------------------------------------------
# HOLDOUT designs: never used to choose or tune. One-shot final test only.
# ---------------------------------------------------------------------------

class HoldoutSizer(_Rival):
    """Strong TAG with size tells removed: blocks small with medium hands, overbets the river
    with the nuts and with its worst bluffs, ICM calls, Nash push/fold."""
    ranged = True
    rollouts = 300
    SPEC = {"open_early": (0.11, 0.15), "open_late": (0.32, 0.45), "pf_bb": (12, 16)}

    def decide(self, obs):
        k = self.k
        pct = self.T.pct(self.T.hole_class(obs.hole))
        if obs.street == 0:
            if self._eff_bb(obs) <= k["pf_bb"]:
                return self._pushfold(obs)
            raises = self._raises(obs, 0)
            if not raises:
                width = k["open_early"] + (k["open_late"] - k["open_early"]) * self._late(obs)
                return self._raise(obs, 2.3 * obs.bb) if pct <= width else self._cf(obs)
            if pct <= 0.045:
                return self._raise(obs, max(obs.bets) * 3.2)
            return (CALL, 0) if pct <= 0.13 and self._po(obs) <= 0.33 else self._cf(obs)
        eq = self._post_eq(obs)
        if obs.to_call == 0:
            if obs.street == 3 and (eq >= 0.85 or (eq <= 0.12 and self.rng.random() < 0.25)):
                return self._raise(obs, 1.5 * obs.pot)
            if eq >= 0.62:
                return self._raise(obs, 0.66 * obs.pot)
            if 0.45 <= eq < 0.62 and self.rng.random() < 0.4:
                return self._raise(obs, 0.25 * obs.pot)
            return (CALL, 0)
        if eq >= 0.84:
            return self._raise(obs, max(obs.bets) * 2.6)
        big = obs.to_call >= 0.9 * (obs.pot - obs.to_call)
        return (CALL, 0) if eq >= self._need(obs) + (0.1 if big else 0.02) else (FOLD, 0)


class HoldoutBayes(_Rival):
    """Range-reading team: puts each villain on a range from VPIP/PFR and bet history, takes
    the EV-best of fold/call/raise with a fold-equity guess from that villain's fold rate."""
    ranged = True
    rollouts = 300
    SPEC = {"pf_bb": (12, 18), "open": (0.18, 0.26), "size": (0.5, 0.8)}

    def decide(self, obs):
        k = self.k
        pct = self.T.pct(self.T.hole_class(obs.hole))
        vs = self._villains(obs)
        if obs.street == 0:
            if self._eff_bb(obs) <= k["pf_bb"]:
                return self._pushfold(obs)
            raises = self._raises(obs, 0)
            if not raises:
                width = k["open"] * (0.5 + self._late(obs))
                return self._raise(obs, 2.5 * obs.bb) if pct <= width else self._cf(obs)
            y = self._rate(raises[-1][0], "pfr")
            eq = self._pre_eq(obs, y)
            if eq >= 0.6:
                return self._raise(obs, max(obs.bets) * 3)
            return (CALL, 0) if eq >= self._need(obs) + 0.04 else self._cf(obs)
        eq = self._post_eq(obs)
        fold = sum(self._rate(s, "fold_to_bet") for s in vs) / max(len(vs), 1)
        fold = fold ** max(len(vs), 1)                       # everyone has to fold
        bet = k["size"] * obs.pot
        call_amt = obs.to_call
        pot = obs.pot
        ev_call = eq * (pot + call_amt) - call_amt if call_amt else eq * pot
        # Raise EV: they fold `fold` of the time, else we realise ~eq of the bigger pot.
        ev_raise = fold * pot + (1 - fold) * (eq * (pot + 2 * bet + call_amt) - (bet + call_amt))
        if ev_raise > max(ev_call, 0.0) and obs.min_raise_to > 0:
            return self._raise(obs, max(obs.bets) + bet)
        if call_amt == 0:
            return (CALL, 0)
        return (CALL, 0) if ev_call > 0 and eq >= self._need(obs) else (FOLD, 0)


class HoldoutJam(_Rival):
    """Short-stack bully: open-jams up to 15 bb with wide ranges vs tight tables, re-jams
    over opens, plays small-ball postflop."""
    ranged = True
    rollouts = 150
    SPEC = {"jam_bb": (13, 18), "widen": (1.2, 1.6), "open": (0.22, 0.32)}

    def decide(self, obs):
        k = self.k
        pct = self.T.pct(self.T.hole_class(obs.hole))
        if obs.street == 0:
            if self._eff_bb(obs) <= k["jam_bb"]:
                return self._pushfold(obs, widen=k["widen"])
            raises = self._raises(obs, 0)
            if not raises:
                return self._raise(obs, 2.1 * obs.bb) if pct <= k["open"] * (0.5 + self._late(obs)) \
                    else self._cf(obs)
            if self._eff_bb(obs) <= 30 and pct <= 0.08:
                return self._shove(obs)
            return (CALL, 0) if pct <= 0.12 and self._po(obs) <= 0.3 else self._cf(obs)
        eq = self._post_eq(obs)
        if obs.to_call == 0:
            return self._raise(obs, 0.4 * obs.pot) if eq >= 0.55 or self.rng.random() < 0.15 else (CALL, 0)
        return (CALL, 0) if eq >= self._need(obs) + 0.02 else (FOLD, 0)


RIVALS = {
    "rv_tag": RivalTag, "rv_lag": RivalLag, "rv_gto": RivalGto, "rv_exploit": RivalExploit,
    "rv_icm": RivalIcm, "rv_mc": RivalMc, "rv_aggro": RivalAggro, "rv_math": RivalMath,
    "rv_buggy": RivalBuggy, "rv_frozen": RivalFrozen,
    "rvh_sizer": HoldoutSizer, "rvh_bayes": HoldoutBayes, "rvh_jam": HoldoutJam,
}
RIVAL_STRONG = ("rv_tag", "rv_lag", "rv_gto", "rv_exploit", "rv_icm")
RIVAL_MID = ("rv_mc", "rv_aggro", "rv_math")
RIVAL_WEAK = ("rv_buggy", "rv_frozen")
RIVAL_HOLDOUT = ("rvh_sizer", "rvh_bayes", "rvh_jam")


def rival_fields(prepped="prep:params/rival_prep.json"):
    """Dev fields of rival teams. "rival-real" is our best guess at a regional: mostly sound
    designs, a few rushed ones, and one prepped team like us. Holdout: rival-oos only."""
    strong = {k: 1 for k in RIVAL_STRONG}
    return {
        "rival-strong": strong,
        "rival-strong+prep": {**strong, prepped: 1.5},
        "rival-mid": {k: 1 for k in RIVAL_MID},
        "rival-real": {**strong, **{k: 0.6 for k in RIVAL_MID}, **{k: 0.4 for k in RIVAL_WEAK},
                       prepped: 0.5, "timeout": 0.2},
        "rival-oos": {k: 1 for k in RIVAL_HOLDOUT},
    }

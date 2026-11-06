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

from .runtime import (CALL, FLUSH, FOLD, FULL_HOUSE, PAIR, POST, PRIORS, QUADS, RAISE, STRAIGHT,
                      TRIPS, TWO_PAIR, SeatStats, ingest_history)
from .zoo import ManiacBot, NitBot, _Base


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


# ---------------------------------------------------------------------------
# LLM-bug designs (Nov 6): typical bugs and styles of a 60-minute LLM-written bot. Evaluation
# only (fields llm-bugs, llm-bugs+prep), never in a tuning default. Every instance draws its
# thresholds from SPEC like the rivals above; equity is MC-noisy vs random hands.
# ---------------------------------------------------------------------------

class _LlmTag(_Rival):
    """Shared 'ask the LLM for a solid TAG' core: open/3-bet/flat by percentile, value-bet,
    pot odds plus a margin. No position, no reads, no push/fold."""
    rollouts = 100
    TAG = {"open": (0.18, 0.26), "three": (0.04, 0.07), "flat": (0.10, 0.16), "vbet": (0.58, 0.66),
           "vsize": (0.55, 0.75), "margin": (0.0, 0.06), "nut": (0.78, 0.86)}

    def __init__(self, tables=None, seed=None):
        self.SPEC = {**self.TAG, **type(self).SPEC}
        super().__init__(tables, seed)

    def _pct(self, obs):
        return self.T.pct(self.T.hole_class(obs.hole))

    def _send(self, obs, target):
        """Raise to `target`; designs with a sizing bug override this."""
        return self._raise(obs, target)

    def tag_pre(self, obs):
        k = self.k
        pct = self._pct(obs)
        if not self._raises(obs, 0):
            if pct <= k["open"]:
                return self._send(obs, 3 * obs.bb)
            return (CALL, 0) if obs.to_call <= obs.bb // 2 + 1 and pct <= 0.35 else self._cf(obs)
        if pct <= k["three"]:
            return self._send(obs, max(obs.bets) * 3)
        return (CALL, 0) if pct <= k["flat"] and self._po(obs) <= 0.4 else self._cf(obs)

    def tag_post(self, obs):
        k = self.k
        eq = self._post_eq(obs)
        if obs.to_call == 0:
            return self._send(obs, k["vsize"] * obs.pot) if eq >= k["vbet"] else (CALL, 0)
        if eq >= k["nut"]:
            return self._send(obs, max(obs.bets) + obs.pot)
        return (CALL, 0) if eq >= self._po(obs) + k["margin"] else (FOLD, 0)

    def decide(self, obs):
        return self.tag_pre(obs) if obs.street == 0 else self.tag_post(obs)


class LlmPhase(_Rival):
    """'Tight early, aggressive late' written as a hard switch: the nit until hand ~60 (or,
    in half the instances, until its stack drops under ~15 bb), then the maniac."""
    SPEC = {"switch_hand": (50, 70), "switch_bb": (12, 18)}

    def __init__(self, tables=None, seed=None):
        super().__init__(tables, seed)
        self.by_stack = self.rng.random() < 0.5
        self.nit = NitBot(tables, seed)
        self.maniac = ManiacBot(tables, None if seed is None else seed + 1)
        self.wild = False

    def new_table(self, seat, n_seats):
        super().new_table(seat, n_seats)
        self.wild = False

    def decide(self, obs):
        if not self.wild:
            if self.by_stack:
                self.wild = obs.stacks[obs.seat] + obs.bets[obs.seat] < self.k["switch_bb"] * obs.bb
            else:
                self.wild = obs.hand_no >= self.k["switch_hand"]
        return self.maniac.act(obs) if self.wild else self.nit.act(obs)


class LlmRaiseBy(_LlmTag):
    """TAG with the raise-by/raise-to mix-up: every raise is sent as max(bets) + 0.75 pot +
    to_call (~1.5-2x the size meant). ~10% of the time the amount comes out under the
    min-raise, which the host legalizes to a min-raise (done here, so the action is legal)."""
    SPEC = {"frac": (0.65, 0.85), "short": (0.07, 0.13)}

    def _send(self, obs, target):
        if obs.min_raise_to <= 0:
            return (CALL, 0)
        if self.rng.random() < self.k["short"]:
            return (RAISE, obs.min_raise_to)
        return self._raise(obs, max(obs.bets) + self.k["frac"] * obs.pot + obs.to_call)


class LlmHuEquity(_Rival):
    """Monte Carlo vs exactly ONE random hand whatever the number of opponents, against pot
    odds: overrates every hand multiway and calls far too wide."""
    rollouts = 100
    SPEC = {"raise": (0.62, 0.72), "bet": (0.55, 0.62), "size": (0.5, 0.9), "open": (0.55, 0.62)}

    def decide(self, obs):
        k = self.k
        if obs.street == 0:
            eq = self._noise(self.T.eq(self.T.hole_class(obs.hole), 1))
            raised = bool(self._raises(obs, 0))
            if eq >= k["raise"]:
                return self._raise(obs, max(obs.bets) * 3 if raised else 3 * obs.bb)
            if obs.to_call == 0:
                return (CALL, 0)
            if not raised:
                return (CALL, 0) if eq >= k["open"] else (FOLD, 0)
            return (CALL, 0) if eq >= self._po(obs) else (FOLD, 0)
        eq = self._noise(self.T.post_equity(obs.hole, obs.board)[0])
        if eq >= k["raise"] + 0.1:
            return self._raise(obs, max(obs.bets) + k["size"] * obs.pot)
        if obs.to_call == 0:
            return self._raise(obs, k["size"] * obs.pot) if eq >= k["bet"] else (CALL, 0)
        return (CALL, 0) if eq >= self._po(obs) else (FOLD, 0)


class LlmRevSizer(_LlmTag):
    """Sizing written backwards: bets 1.2x pot with weak hands (equity < ~0.35), a third of
    pot with strong ones (> ~0.7), checks the middle. Calls by pot odds."""
    SPEC = {"lo": (0.30, 0.40), "hi": (0.66, 0.74)}

    def decide(self, obs):
        if obs.street == 0:
            return self.tag_pre(obs)
        k = self.k
        eq = self._post_eq(obs)
        if obs.to_call == 0:
            if eq < k["lo"]:
                return self._raise(obs, 1.2 * obs.pot)
            if eq > k["hi"]:
                return self._raise(obs, 0.33 * obs.pot)
            return (CALL, 0)
        return (CALL, 0) if eq >= self._po(obs) + k["margin"] else (FOLD, 0)


class LlmLimpJam(_LlmTag):
    """Open-limps the top ~40%; when raised, jams the top ~15% at <= ~30 bb, else calls the
    top ~25%. TAG postflop."""
    SPEC = {"limp": (0.35, 0.45), "jam": (0.12, 0.18), "call": (0.22, 0.28), "jam_bb": (27, 33)}

    def decide(self, obs):
        if obs.street != 0:
            return self.tag_post(obs)
        k = self.k
        pct = self._pct(obs)
        if not self._raises(obs, 0):
            return (CALL, 0) if pct <= k["limp"] else self._cf(obs)
        if self._eff_bb(obs) <= k["jam_bb"]:
            return self._shove(obs) if pct <= k["jam"] else self._cf(obs)
        return (CALL, 0) if pct <= k["call"] else self._cf(obs)


class LlmResteal(_LlmTag):
    """Tracks every opener's PFR; vs an open from a seat raising > ~30%, jams the top ~25%
    from the blinds or button at <= ~25 bb, else folds to the open (3-bets only the top
    ~4%). TAG otherwise."""
    SPEC = {"pfr_thr": (0.27, 0.33), "range": (0.22, 0.28), "max_bb": (22, 28), "premium": (0.03, 0.05)}

    def decide(self, obs):
        if obs.street != 0:
            return self.tag_post(obs)
        k = self.k
        raises = self._raises(obs, 0)
        if len(raises) != 1:
            return self.tag_pre(obs)
        pct = self._pct(obs)
        if pct <= k["premium"]:
            return self._raise(obs, max(obs.bets) * 3)
        posts = [h[0] for h in obs.history if h[2] == POST]
        steal_seat = obs.seat == obs.button or obs.seat in posts
        if steal_seat and pct <= k["range"] and self._eff_bb(obs) <= k["max_bb"] \
                and self._rate(raises[0][0], "pfr") > k["pfr_thr"]:
            return self._shove(obs)
        return self._cf(obs)


class LlmCapClock(_LlmTag):
    """Plays for the 200-hand cap: TAG until hand ~170, then folds all but the top ~3% when
    above the table's average stack, and shoves the top ~35% when below it."""
    SPEC = {"clock": (160, 180), "tight": (0.02, 0.04), "loose": (0.30, 0.40)}

    def decide(self, obs):
        k = self.k
        if obs.hand_no < k["clock"]:
            return self.tag_pre(obs) if obs.street == 0 else self.tag_post(obs)
        alive = [obs.stacks[s] + obs.bets[s] for s in range(len(obs.stacks))
                 if obs.stacks[s] + obs.bets[s] > 0 or obs.in_hand[s]]
        above = obs.stacks[obs.seat] + obs.bets[obs.seat] > sum(alive) / max(len(alive), 1)
        if obs.street == 0:
            return self._shove(obs) if self._pct(obs) <= (k["tight"] if above else k["loose"]) else self._cf(obs)
        if above:
            return self._shove(obs) if self._post_eq(obs) >= 0.8 else self._cf(obs)
        return self.tag_post(obs)


def _pair_or_draw(v, hole, board):
    """Any pair (pocket or with the board), or a 4-flush / 4-straight that uses a hole card."""
    S = v.suits
    hr = {c // S for c in hole}
    br = {c // S for c in board}
    if len(hr) < len(hole) or hr & br:
        return True
    cards = list(hole) + list(board)
    for su in {c % S for c in hole}:
        if sum(1 for c in cards if c % S == su) >= 4:
            return True
    ace = v.R - 1
    ranks = hr | br | ({-1} if ace in hr | br else set())
    mine = hr | ({-1} if ace in hr else set())
    for lo in range(-1, v.R - 4):
        win = set(range(lo, lo + 5))
        if len(win & ranks) >= 4 and win & mine:
            return True
    return False


class LlmFtsBluff(_LlmTag):
    """Fit-or-fold flop, give-up later: c-bets 100% of flops as the preflop raiser, calls any
    flop bet with any pair or draw, then gives up on the turn and river unless equity > ~0.6."""
    SPEC = {"cb": (0.5, 0.75), "give": (0.57, 0.63)}

    def decide(self, obs):
        if obs.street == 0:
            return self.tag_pre(obs)
        k = self.k
        eq = self._post_eq(obs)
        if obs.street == 1:
            if obs.to_call == 0:
                if self._pfr_seat(obs) == obs.seat or eq >= k["vbet"]:
                    return self._raise(obs, k["cb"] * obs.pot)
                return (CALL, 0)
            if eq >= k["nut"]:
                return self._raise(obs, max(obs.bets) * 3)
            return (CALL, 0) if _pair_or_draw(self.T.v, obs.hole, obs.board) else (FOLD, 0)
        if eq <= k["give"]:
            return self._cf(obs)
        if obs.to_call == 0:
            return self._raise(obs, 0.66 * obs.pot)
        return self._raise(obs, max(obs.bets) * 2.5) if eq >= k["nut"] else (CALL, 0)


# ---------------------------------------------------------------------------
# Strong-bot proxy ("whale"): what a near-equilibrium, well-tuned bot looks like.
# ---------------------------------------------------------------------------

class StrongEq(_Rival):
    """Near-equilibrium proxy for a heavily-computed rival: ICM push/fold straight from the
    solved charts, positional raise-or-fold opens with mixed borders, a linear-plus-bluff
    3-bet range, and balanced postflop play: bet sizes drawn at random per spot, bluffs at
    s / (1 + 2s) of the value bets for size s, defence by minimum defence frequency (with the
    ICM price as a floor). It never adapts to opponents' stats (equilibrium bots don't), and
    its equities are near-exact (no Monte Carlo noise to speak of)."""
    ranged = True
    rollouts = 4000
    SPEC = {"pf_bb": (14, 16), "o7": (0.12, 0.14), "mix": (0.25, 0.4), "three": (0.03, 0.04),
            "vflop": (0.62, 0.66), "vturn": (0.66, 0.70), "vriver": (0.70, 0.74), "def": (0.92, 1.0)}
    OPEN = (0.50, 0.48, 0.40, 0.30, 0.24, 0.19, 0.16, 0.13)   # by players left behind (1 = SB)

    def _behind(self, obs):
        order = self._order(obs)
        pos = order.index(obs.seat) if obs.seat in order else 0
        return len(order) - pos - 1

    def decide(self, obs):
        k, r = self.k, self.rng
        pct = self.T.pct(self.T.hole_class(obs.hole))
        bb = obs.bb
        if obs.street == 0:
            if self._eff_bb(obs) <= k["pf_bb"]:
                return self._pushfold(obs)
            raises = self._raises(obs, 0)
            nb = self._behind(obs)
            if not raises:
                limpers = sum(1 for h in obs.history if h[1] == 0 and h[2] == CALL and h[3] > 0)
                if limpers:
                    w = 0.10 if obs.to_call else 0.16
                    if pct <= w or (pct <= 1.3 * w and r.random() < k["mix"]):
                        return self._raise(obs, (3 + limpers) * bb)
                    if obs.to_call == 0:
                        return (CALL, 0)
                    return (CALL, 0) if pct <= 0.22 and obs.to_call <= bb else (FOLD, 0)
                if obs.to_call == 0:
                    return (CALL, 0)
                w = self.OPEN[min(nb, 7)] * (k["o7"] / 0.13 if nb >= 5 else 1.0)
                if pct <= w or (pct <= 1.25 * w and r.random() < k["mix"]):
                    return self._raise(obs, (2.2 + 0.3 * r.random()) * bb)
                return (FOLD, 0)
            opener = raises[0][0]
            o_order = self._order(obs)
            o_nb = len(o_order) - (o_order.index(opener) if opener in o_order else 0) - 1
            y_open = self.OPEN[min(o_nb, 7)]            # assumes an equilibrium opener: no reads
            n_r = len(raises)
            if n_r == 1:
                v3 = k["three"] * (1.0 + y_open)
                if pct <= v3:
                    return self._raise(obs, max(obs.bets) * (3.0 if nb else 3.6))
                # bluff 3-bets: hands just outside the flatting range, mixed
                if 2.2 * v3 < pct <= 3.2 * v3 and r.random() < 0.35:
                    return self._raise(obs, max(obs.bets) * (3.0 if nb else 3.6))
                eq = self._pre_eq(obs, y_open)
                return (CALL, 0) if eq * 0.92 >= self._need(obs) + 0.02 else (FOLD, 0)
            if n_r == 2:
                if pct <= 0.022:
                    return self._shove(obs) if self._eff_bb(obs) <= 40 else self._raise(obs, max(obs.bets) * 2.3)
                if pct <= 0.03 and r.random() < 0.3:
                    return self._shove(obs) if self._eff_bb(obs) <= 40 else self._raise(obs, max(obs.bets) * 2.3)
                eq = self._pre_eq(obs, 0.06)
                return (CALL, 0) if pct <= 0.07 and eq >= self._need(obs) else (FOLD, 0)
            return (self._shove(obs) if pct <= 0.015 else (CALL, 0) if pct <= 0.025 else self._cf(obs))
        eq = self._post_eq(obs)
        st = obs.street
        vthr = (k["vflop"], k["vturn"], k["vriver"])[min(st, 3) - 1]
        n_v = len(self._villains(obs))
        my_stack = obs.stacks[obs.seat]
        if obs.to_call == 0:
            s = r.choice((0.33, 0.66, 0.66, 1.0) if st == 1 else (0.5, 0.75, 1.0, 1.25))
            if n_v > 1:
                vthr += 0.06 * (n_v - 1)
            if eq >= vthr:
                if my_stack <= 1.2 * obs.pot:
                    return self._shove(obs)
                return self._raise(obs, s * obs.pot)
            if n_v <= 2:
                # bluffs : value = s / (1 + 2s); value share ~ (1 - vthr) / 0.4 of the range
                share = (1.0 - vthr) / 0.4 * s / (1 + 2 * s)
                lo, hi = (0.25, 0.45) if st < 3 else (0.0, 0.22)
                if lo <= eq <= hi and r.random() < share / max(hi - lo, 0.05) * 0.4 / n_v:
                    return self._raise(obs, s * obs.pot)
            return (CALL, 0)
        b = obs.to_call / max(obs.pot - obs.to_call, 1)
        mdf = 1.0 / (1.0 + b)
        need = self._need(obs)
        if eq >= 0.86 or (eq <= 0.3 and st < 3 and r.random() < 0.05):
            if r.random() < 0.6:
                if my_stack <= 2.0 * obs.pot:
                    return self._shove(obs)
                return self._raise(obs, max(obs.bets) * (2.7 + 0.5 * r.random()))
        thr = max(need - 0.04, (1.0 - mdf) * k["def"])
        return (CALL, 0) if eq >= min(thr, need + 0.08) else (FOLD, 0)


LLM_BUGS = {
    "phase": LlmPhase, "raiseby": LlmRaiseBy, "huequity": LlmHuEquity, "revsizer": LlmRevSizer,
    "limpjam": LlmLimpJam, "resteal": LlmResteal, "capclock": LlmCapClock, "ftsbluff": LlmFtsBluff,
}


def llm_fields(prepped="prep:params/rival_prep.json"):
    """Evaluation fields of LLM-bug designs: 7 opponents per table drawn by weight, as in
    rival_fields. Never in a tuning default. +prep adds a prepped copy (~0.9 seats a table)."""
    base = {k: 1 for k in LLM_BUGS}
    return {"llm-bugs": base, "llm-bugs+prep": {**base, prepped: 1.2}}


# ---------------------------------------------------------------------------
# GitHub-bot designs: modeled on the shapes of public poker bots (LLM-written and hobby
# repos), each with the bugs those bots ship. Written from short behavioral specs, not
# from their code. Evaluation fields only (github, github+prep), never in a tuning default.
# Every instance scales its thresholds by its own noise (+-10-20%); some carry the common
# "'T' parsed as rank 0" bug (Ten treated as the lowest card).
# ---------------------------------------------------------------------------

_RVAL = {ch: i + 2 for i, ch in enumerate("23456789TJQKA")}


class _Gh(_Rival):
    NOM = {}           # name -> nominal value; each instance scales it by its own noise
    TENBUG = 0.0       # share of instances that read 'T' as rank 0
    rollouts = 60

    def __init__(self, tables=None, seed=None):
        super().__init__(tables, seed)
        j = self.rng.uniform(0.10, 0.20)
        self.k = {name: v * self.rng.uniform(1 - j, 1 + j) for name, v in sorted(self.NOM.items())}
        self.tenbug = self.rng.random() < self.TENBUG
        v = self.T.v
        vals = [_RVAL.get(ch, i + 2) for i, ch in enumerate(v.ranks)]
        if self.tenbug and "T" in v.ranks:
            vals[v.ranks.index("T")] = 0
        S = v.suits
        self._val = [vals[c // S] for c in range(v.D)]
        self._suit = [c % S for c in range(v.D)]

    # -- card facts (with this instance's rank parsing) ---------------------
    def _hole2(self, obs):
        """(hi, lo, suited, pair) of the two highest hole cards."""
        cs = sorted(obs.hole, key=self._val.__getitem__, reverse=True)[:2]
        a, b = self._val[cs[0]], self._val[cs[1]]
        return a, b, self._suit[cs[0]] == self._suit[cs[1]], a == b

    def _cat(self, obs):
        ev = self.T.ev
        return ev.category(ev.best(obs.hole, obs.board))

    def _raised_pre(self, obs):
        return bool(self._raises(obs, 0))

    def _street_acts(self, obs):
        return [h for h in obs.history if h[1] == obs.street and h[2] != POST]

    def _facing_allin(self, obs):
        if not obs.to_call:
            return False
        top = max(obs.bets)
        return any(h[4] and h[3] == top and h[0] != obs.seat for h in self._street_acts(obs))

    def _stack(self, obs):
        return obs.stacks[obs.seat]

    def _start(self, obs):
        return (sum(obs.stacks) + obs.pot) / max(len(obs.stacks), 1)

    def _posts(self, obs):
        return [h[0] for h in obs.history if h[2] == POST]

    def _rto(self, obs, target):
        """Raise to `target` (clamped to legal); call when raising is closed."""
        return self._raise(obs, target)

    def _eq_n(self, obs, n=None):
        """Noisy MC-style equity vs n random hands (n = live opponents by default)."""
        n = n or self._n_opp(obs)
        if obs.street == 0:
            return self._noise(self.T.eq(self.T.hole_class(obs.hole), n))
        e = self.T.post_equity(obs.hole, obs.board)
        return self._noise(e[n - 1] if n <= 3 else e[2] ** (n / 3.0))


def _cat_score(bot, obs):
    """Score of the made category on all cards (board pairs and flushes count as ours), no draws."""
    c = bot._cat(obs)
    if c >= QUADS:
        return 0.95
    if c == FULL_HOUSE:
        return 0.90
    if c == FLUSH:
        return 0.85
    if c == STRAIGHT:
        return 0.80
    if c == TRIPS:
        return 0.75
    if c == TWO_PAIR:
        return 0.65
    vals = [bot._val[x] for x in tuple(obs.hole) + tuple(obs.board)]
    if c == PAIR:
        pr = max(v for v in vals if vals.count(v) > 1)
        return 0.60 if pr >= 11 else 0.45
    return 0.40 if max(vals) >= 13 else 0.25


def _pre_score(bot, obs):
    hi, lo, s, pair = bot._hole2(obs)
    if pair:
        return 0.95 if hi >= 13 else 0.85 if hi >= 11 else 0.75 if hi >= 9 else 0.65 if hi >= 7 else 0.55
    if hi == 14:
        if lo >= 12:
            return 0.80 if s else 0.75
        if lo >= 10:
            return 0.70 if s else 0.60
        if lo >= 8:
            return 0.60 if s else 0.45
        return 0.50 if s else 0.35
    if hi == 13:
        if lo >= 11:
            return 0.70 if s else 0.60
        if lo >= 9:
            return 0.55 if s else 0.45
        return 0.40 if s else 0.30
    if lo >= 10 and hi - lo == 1:
        return 0.60 if s else 0.50
    if s and hi - lo == 1 and lo >= 6:
        return 0.40
    return 0.25


class GhCatScore(_Gh):
    """Score table preflop, made-category score postflop (on all 7 cards, no draws), then a
    win-probability EV formula. Never bluffs; raises only with a score >= ~0.8."""
    TENBUG = 0.3
    NOM = {"bet": 0.70, "raise": 0.80, "allin": 0.60, "allin_po": 0.25, "margin": 0.10,
           "s_hi": 0.80, "s_mid": 0.60, "s_lo": 0.40, "rsize": 0.80}

    def _agg(self, obs):
        st = self._start(obs)
        me = self._stack(obs) + obs.bets[obs.seat]
        return 1.4 if me > 1.5 * st else 0.9 if me < 0.7 * st else 1.2

    def decide(self, obs):
        k = self.k
        hs = _pre_score(self, obs) if obs.street == 0 else _cat_score(self, obs)
        agg = self._agg(obs)
        if obs.to_call == 0:
            if hs >= k["bet"]:
                f = k["s_hi"] if hs >= 0.85 else k["s_mid"] if hs >= 0.65 else k["s_lo"]
                return self._rto(obs, max(obs.bets) + f * agg * obs.pot)
            return (CALL, 0)
        if self._facing_allin(obs):
            return (CALL, 0) if hs >= k["allin"] or self._po(obs) > k["allin_po"] else (FOLD, 0)
        if hs >= k["raise"] and len(self._raises(obs)) < 4:
            return self._rto(obs, max(obs.bets) + k["rsize"] * (obs.pot + obs.to_call) * agg)
        call = obs.to_call
        wp = hs * 0.9 ** self._n_opp(obs) * (1 - min(0.3, 0.5 * call / max(obs.pot, 1)))
        ev = wp * (obs.pot + call) - (1 - wp) * call
        opp = [h for h in self._street_acts(obs) if h[0] != obs.seat]
        a = sum(1 for h in opp if h[2] == RAISE) / len(opp) if opp else 0.5
        posf = 0.9 + 0.2 * self._late(obs)
        return (CALL, 0) if ev * posf * (2 - a) > k["margin"] * call else (FOLD, 0)


class GhOpus(_Gh):
    """Score table x1.3 (uncapped) in the last two seat numbers (seat index taken as position).
    Premiums open 3 bb / 3-bet 3x, good hands raise 2x+bb 60%, BB defends any 1 bb.
    Postflop on the made category only; won't call an all-in it can't fully cover."""
    TENBUG = 0.3
    NOM = {"prem": 0.85, "good": 0.65, "ok": 0.45, "mix": 0.60, "v": 0.80, "m": 0.60, "w": 0.40,
           "cb": 0.70, "stab": 0.15, "po_m": 0.30, "po_w": 0.25}

    def decide(self, obs):
        k = self.k
        fake = 1.3 if obs.seat >= len(obs.stacks) - 2 else 1.0
        if obs.to_call > self._stack(obs):
            return (FOLD, 0)                      # would be all-in for less: folds instead
        bb = obs.bb
        if obs.street == 0:
            sc = _pre_score(self, obs) * fake
            raised = self._raised_pre(obs)
            if sc > k["prem"]:
                return self._rto(obs, 3 * max(obs.bets) if raised else 3 * bb)
            if sc > k["good"]:
                if self.rng.random() < k["mix"]:
                    return self._rto(obs, 2 * max(obs.bets) + bb)
                return (CALL, 0)
            if sc > k["ok"] and obs.to_call <= 2 * bb:
                return (CALL, 0)
            posts = self._posts(obs)
            if len(posts) >= 2 and obs.seat == posts[1] and obs.to_call <= bb:
                return (CALL, 0)
            return self._cf(obs)
        sc = _cat_score(self, obs) * fake
        po = self._po(obs)
        if sc > k["v"]:
            return self._rto(obs, max(obs.bets) + 0.67 * (obs.pot + obs.to_call))
        if sc > k["m"]:
            if obs.to_call == 0:
                return self._rto(obs, 0.5 * obs.pot) if self.rng.random() < k["cb"] else (CALL, 0)
            return (CALL, 0) if po < k["po_m"] else (FOLD, 0)
        if sc > k["w"]:
            if obs.to_call == 0:
                return self._rto(obs, 0.33 * obs.pot) if self.rng.random() < k["stab"] else (CALL, 0)
            return (CALL, 0) if po < k["po_w"] else (FOLD, 0)
        return self._cf(obs)


class GhTiers(_Gh):
    """Three preflop tiers (T1 never folds and raises to 2 pots, T2 opens/calls one raise,
    T3 limps); postflop by made hand: boats+ raise, two pair..flush bet/call, pair calls cheap."""
    TENBUG = 0.3
    NOM = {"t2_stack": 0.15, "pair_po": 0.30, "big": 1.2, "mid": 0.7}
    _T2S = ((13, 12), (13, 11), (13, 10), (12, 11), (12, 10), (11, 10))
    _T2O = ((14, 13), (14, 12), (13, 12))
    _T3O = ((14, 11), (13, 11), (12, 11))

    def _tier(self, obs):
        hi, lo, s, pair = self._hole2(obs)
        if pair:
            return 1 if hi >= 11 else 2 if 7 <= hi <= 10 else 3
        if hi == 14 and s and lo >= 10:
            return 1
        if (hi, lo) in (self._T2S if s else self._T2O):
            return 2
        if s and (hi == 14 or hi - lo <= 2):
            return 3
        if not s and (hi, lo) in self._T3O:
            return 3
        return 4

    def decide(self, obs):
        k = self.k
        bb = obs.bb
        if obs.street == 0:
            t = self._tier(obs)
            nr = len(self._raises(obs, 0))
            if t == 1:
                return self._rto(obs, 2 * obs.pot + max(obs.bets) if nr else 4 * bb)
            if t == 2:
                if nr == 0:
                    return self._rto(obs, 3 * bb)
                if nr == 1 and obs.to_call < k["t2_stack"] * self._stack(obs):
                    return (CALL, 0)
                return self._cf(obs)
            if t == 3:
                return (CALL, 0) if obs.to_call <= 2 * bb else (FOLD, 0)
            return self._cf(obs)
        c = self._cat(obs)
        if c >= FULL_HOUSE:
            return self._rto(obs, max(obs.bets) + k["big"] * obs.pot)
        if c >= TWO_PAIR:
            return self._rto(obs, k["mid"] * obs.pot) if obs.to_call == 0 else (CALL, 0)
        if c == PAIR:
            return (CALL, 0) if self._po(obs) < k["pair_po"] else (FOLD, 0)
        return self._cf(obs)


class GhFlash(_Gh):
    """One preflop value (+-0.05 jitter) reused on every street, board ignored; a key bug
    sends most hands to the 0.2 default. Raises/jams 'strong' hands against stack fractions."""
    NOM = {"open_hi": 0.80, "open_mid": 0.50, "p_hi": 0.70, "p_mid": 0.40, "stk_r": 0.20,
           "stk_big": 0.30, "stk_mid": 0.15, "stk_lo": 0.05, "r_mix": 0.70, "jam_mix": 0.50}

    def _value(self, obs):
        hi, lo, s, pair = self._hole2(obs)
        if pair:
            return 0.9 if hi >= 10 else 0.5
        if s and ((hi == 14 and lo >= 10) or (hi, lo) in ((13, 12), (13, 11), (12, 10))):
            return 0.7
        if not s and ((hi == 14 and lo >= 11) or (hi, lo) == (13, 12)):
            return 0.6
        return 0.2

    def decide(self, obs):
        k = self.k
        v = self._value(obs) + self.rng.uniform(-0.05, 0.05)
        bb, stk = obs.bb, self._stack(obs)
        if obs.street == 0:
            raised = self._raised_pre(obs)
            if v >= k["open_hi"]:
                if not raised:
                    return self._rto(obs, 3 * bb)
                return self._rto(obs, 2 * max(obs.bets) + bb) if obs.to_call < k["stk_r"] * stk else (CALL, 0)
            if v >= k["open_mid"]:
                if not raised:
                    return self._rto(obs, 2 * bb)
                return (CALL, 0) if obs.to_call <= 2 * bb else (FOLD, 0)
            return (CALL, 0) if obs.to_call <= bb else (FOLD, 0)
        if v >= k["p_hi"]:
            if obs.to_call == 0:
                return self._rto(obs, self.rng.uniform(0.5, 0.7) * obs.pot)
            if obs.to_call < k["stk_big"] * stk:
                return self._rto(obs, 2 * max(obs.bets)) if self.rng.random() < k["r_mix"] else (CALL, 0)
            return self._shove(obs) if self.rng.random() < k["jam_mix"] else (FOLD, 0)
        if v >= k["p_mid"]:
            if obs.to_call == 0:
                return self._rto(obs, self.rng.uniform(0.3, 0.5) * obs.pot)
            return (CALL, 0) if obs.to_call < k["stk_mid"] * stk else (FOLD, 0)
        if obs.to_call == 0:
            return (CALL, 0)
        return (CALL, 0) if obs.to_call < k["stk_lo"] * stk else (FOLD, 0)


class GhMinnit(_Gh):
    """Min-raises its two top groups preflop, limps a third, folds the rest (a lookup-order
    bug folds ~15% of AK-type hands). Postflop it ignores its cards: 'rank' grows with the
    number of actions this street and is compared with pot odds."""
    NOM = {"misread": 0.15, "edge": 0.20, "step": 0.10, "size": 1.5}

    def __init__(self, tables=None, seed=None):
        super().__init__(tables, seed)
        self._hand = (-1, False)

    def _group(self, obs):
        hi, lo, s, pair = self._hole2(obs)
        if pair:
            return 1 if hi >= 11 else 2 if hi >= 8 else 3
        if hi == 14 and lo == 13:
            if self._hand[0] != obs.hand_no:
                self._hand = (obs.hand_no, self.rng.random() < self.k["misread"])
            return 4 if self._hand[1] else 1
        if s and (hi, lo) in ((14, 12), (14, 11), (13, 12)):
            return 2
        if not s and (hi, lo) == (14, 12):
            return 2
        if s and lo >= 10:
            return 3
        return 4

    def decide(self, obs):
        k = self.k
        if obs.street == 0:
            g = self._group(obs)
            nr = len(self._raises(obs, 0))
            if g == 1:
                return (RAISE, obs.min_raise_to) if obs.min_raise_to > 0 and nr < 4 else (CALL, 0)
            if g == 2:
                if nr == 0 and obs.min_raise_to > 0:
                    return (RAISE, obs.min_raise_to)
                return (CALL, 0) if obs.to_call <= 3 * obs.bb else self._cf(obs)
            if g == 3:
                return (CALL, 0) if obs.to_call <= obs.bb else (FOLD, 0)
            return self._cf(obs)          # also "folds" when the check is free (host checks)
        acts = self._street_acts(obs)
        rank = min(0.9, 0.5 + k["step"] * len(acts))
        if obs.to_call == 0:
            if acts and obs.min_raise_to > 0:
                return self._rto(obs, k["size"] * obs.min_raise_to)
            return (CALL, 0)
        po = self._po(obs)
        if rank > po + k["edge"] and obs.min_raise_to > 0 and len(self._raises(obs)) < 4:
            return (RAISE, obs.min_raise_to)
        return (CALL, 0) if rank > po else (FOLD, 0)


class GhInvStation(_Gh):
    """Inverted pot odds: never raises, checks when free, calls only bets bigger than ~40% of
    the resulting pot (folds the small ones)."""
    NOM = {"thr": 0.40}

    def decide(self, obs):
        if obs.to_call == 0:
            return (CALL, 0)
        return (CALL, 0) if self._po(obs) > self.k["thr"] else (FOLD, 0)


class GhPotOdds(_Gh):
    """Reference bot: raises to 3 pots with AA/KK preflop, otherwise checks, calls up to a
    third of the pot, folds the rest. Card-blind postflop."""
    NOM = {"frac": 1 / 3, "size": 3.0}

    def decide(self, obs):
        if obs.street == 0:
            hi, lo, s, pair = self._hole2(obs)
            if pair and hi >= 13:
                return self._rto(obs, self.k["size"] * obs.pot)
        if obs.to_call == 0:
            return (CALL, 0)
        return (CALL, 0) if obs.to_call <= self.k["frac"] * obs.pot else (FOLD, 0)


class GhMc1Jam(_Gh):
    """Equity vs ONE random hand (few MC samples) mapped to limp/raise/jam; ignores pot odds."""
    rollouts = 40
    NOM = {"sb_r": 0.60, "sb_j": 0.80, "bb_j": 0.60, "jam": 0.63, "p_bet": 0.50, "p_call": 0.59}

    def decide(self, obs):
        k = self.k
        eq = self._eq_n(obs, 1)
        if obs.street == 0:
            posts = self._posts(obs)
            if posts and obs.seat == posts[0] and not self._raised_pre(obs):
                if eq >= k["sb_j"]:
                    return self._shove(obs)
                if eq >= k["sb_r"]:
                    return self._rto(obs, 1.5 * obs.min_raise_to)
                return (CALL, 0)
            if len(posts) >= 2 and obs.seat == posts[1] and obs.to_call == 0:
                return self._shove(obs) if eq > k["bb_j"] else (CALL, 0)
            return self._shove(obs) if eq > k["jam"] else self._cf(obs)
        if obs.to_call == 0:
            return self._shove(obs) if eq > k["p_bet"] else (CALL, 0)
        return (CALL, 0) if eq > k["p_call"] else (FOLD, 0)


class GhLadder(_Gh):
    """Equity ladder vs the live opponents: the size tells the hand (all-in > 2 pots > pot >
    half pot > call). Thresholds b (bet) ~0.6-0.7 and c (call) ~0.4-0.5 per instance."""
    rollouts = 80

    def __init__(self, tables=None, seed=None):
        super().__init__(tables, seed)
        self.k = {"b": self.rng.uniform(0.60, 0.70), "c": self.rng.uniform(0.40, 0.50)}

    def decide(self, obs):
        b, c = self.k["b"], self.k["c"]
        e = self._eq_n(obs)
        top = max(obs.bets)
        if e > b + 0.2:
            return self._shove(obs)
        if e > b + 0.1:
            return self._rto(obs, top + 2 * obs.pot)
        if e > b:
            return self._rto(obs, top + obs.pot)
        if e > b - 0.1:
            return self._rto(obs, top + 0.5 * obs.pot)
        if e > c:
            return (CALL, 0)
        return self._cf(obs)


class GhShark(_Gh):
    """Card-blind stabber: TT+ raises to 3 min-raises every time (AK/AQ/AJ/KQ lost to a sort
    bug), medium hands call cheap in late seats; postflop bets 0.6 pot 40% in late seats when
    checked to and calls small bets by position. Never raises postflop."""
    NOM = {"late": 0.6, "med_po": 0.20, "stab": 0.40, "size": 0.60, "c_late": 0.25, "c_early": 0.15}

    def decide(self, obs):
        k = self.k
        late = self._late(obs) >= k["late"]
        if obs.street == 0:
            hi, lo, s, pair = self._hole2(obs)
            if pair and hi >= 10 and len(self._raises(obs, 0)) < 5:
                return self._rto(obs, 3 * obs.min_raise_to)
            if (hi >= 10 or s) and late and obs.to_call < k["med_po"] * obs.pot:
                return (CALL, 0)
            return self._cf(obs)
        if obs.to_call == 0:
            if late and self.rng.random() < k["stab"]:
                return self._rto(obs, k["size"] * obs.pot)
            return (CALL, 0)
        lim = k["c_late"] if late else k["c_early"]
        return (CALL, 0) if obs.to_call / max(obs.pot - obs.to_call, 1) <= lim else (FOLD, 0)


_MANIAC, _STATION, _NIT, _PASSIVE, _TAG = range(5)


_WINDOWS = tuple(0b11111 << lo for lo in range(1, 11))     # rank bitmasks, ace also as 1


def _rmask(vals):
    m = 0
    for r in vals:
        m |= 1 << r
    return m | 2 if m >> 14 & 1 else m


def _draw_eq(val, suit, hole, board):
    """Overlay equity of a flush draw (0.35), open-ender (0.32) or gutshot (0.16) that uses a
    hole card; 0 with none (or a made straight)."""
    cards = tuple(hole) + tuple(board)
    for su in {suit[c] for c in hole}:
        if sum(1 for c in cards if suit[c] == su) == 4:
            return 0.35
    have = _rmask([val[c] for c in cards])
    mine = _rmask([val[c] for c in hole])
    outs = 0
    for w in _WINDOWS:
        if not w & mine:
            continue
        miss = w & ~have
        if not miss:
            return 0.0                      # already a straight
        if not miss & (miss - 1):           # exactly one rank missing: it is an out
            outs |= miss
    n = bin(outs & ~2 if outs & 2 and outs >> 14 & 1 else outs).count("1")
    return 0.32 if n >= 2 else 0.16 if n == 1 else 0.0


class GhClassifier(_Gh):
    """Opponent-classifier mixer: noisy MC equity vs the live opponents with draw overlays,
    classes each villain after 10 actions (maniac/station/nit/passive/tag), price buckets,
    SPR rules, stack-state jam weights, and a river one-pair fold."""
    rollouts = 50
    NOM = {"open": 1.9, "three": 2.6, "pre_jam": 3.0, "value": 0.60, "strong": 0.72, "raise": 0.78,
           "m_lo": 0.02, "m_mid": 0.05, "m_hi": 0.08, "nit_adj": 0.08, "man_adj": 0.06,
           "semi": 0.30, "river_fold": 0.40}

    def new_table(self, seat, n_seats):
        super().new_table(seat, n_seats)
        self.classes = [_TAG] * n_seats

    def observe(self, event):
        super().observe(event)                    # classes change only when a hand ends
        if event[0] == "hand_end" and self.stats:
            self.classes = [self._classify(s) for s in range(len(self.stats))]

    def _cls(self, s):
        c = getattr(self, "classes", None)
        return c[s] if c and s < len(c) else _TAG

    def _classify(self, s):
        st = self.stats[s] if self.stats else None
        if st is None or st.acts < 10:
            return _TAG
        acts = st.acts
        allin = st.allin / acts
        rr = (st.pfr + st.aggr) / acts
        cr = max(0, st.vpip - st.pfr + st.passive) / acts
        vpip = st.vpip / max(st.hands, 1)
        if allin > 0.07 or rr > 0.35:
            return _MANIAC
        if cr > 0.32 and rr < 0.16:
            return _STATION
        if vpip < 0.18 and rr < 0.12:
            return _NIT
        if rr < 0.10 and cr > 0.18:
            return _PASSIVE
        return _TAG

    def decide(self, obs):
        k = self.k
        vs = self._villains(obs)
        st = self._start(obs)
        me = self._stack(obs) + obs.bets[obs.seat]
        state = 1 if me >= 2.2 * st else -1 if me <= 0.3 * st else 0
        jw = 0.4 if state == 1 else 1.0
        n = max(len(vs), 1)
        eq = self._eq_n(obs, n)
        if 0 < obs.street < 3:
            eq = max(eq, _draw_eq(self._val, self._suit, obs.hole, obs.board))
        spr = self._stack(obs) / max(obs.pot, 1)
        top = max(obs.bets)
        need = 0.0
        if obs.to_call:
            po = self._po(obs)
            agg = max(vs, key=lambda s: obs.bets[s]) if vs else None
            ac = self._cls(agg) if agg is not None else _TAG
            need = po + (k["m_lo"] if po <= 0.16 else k["m_mid"] if po <= 0.28 else k["m_hi"])
            need += k["nit_adj"] if ac == _NIT else -k["man_adj"] if ac == _MANIAC else 0.0
            if state == -1:
                need = min(need, 0.30)
        if obs.street == 0:
            r = eq * (n + 1)                      # equity over a fair share
            short = self._eff_bb(obs) <= 10 or spr <= 1.5
            if r >= k["pre_jam"] * (0.85 if state == -1 else 1.0) and (short or self.rng.random() < 0.15 * jw):
                return self._shove(obs)
            if not self._raised_pre(obs):
                if r >= k["open"]:
                    limpers = sum(1 for h in obs.history if h[1] == 0 and h[2] == CALL)
                    return self._rto(obs, (2.5 + limpers) * obs.bb)
                if obs.to_call == 0:
                    return (CALL, 0)
                return (CALL, 0) if eq >= need and obs.to_call <= obs.bb else (FOLD, 0)
            if r >= k["three"]:
                return self._rto(obs, 3 * top)
            return (CALL, 0) if eq >= need + 0.05 else self._cf(obs)
        vals = [self._val[c] for c in tuple(obs.hole) + tuple(obs.board)]
        one_pair = len(set(vals)) == len(vals) - 1 and self._cat(obs) == PAIR
        soft = any(self._cls(s) in (_STATION, _PASSIVE, _MANIAC) for s in vs)
        mult = 1.3 if soft else 1.0
        strong = eq >= k["strong"] * (0.9 if state == -1 else 1.0)
        if strong and spr <= 1.5 and not (one_pair and spr > 6) and (state == -1 or self.rng.random() < jw):
            return self._shove(obs)
        if obs.to_call == 0:
            if eq >= k["value"]:
                f = _clamp((0.4 + 1.5 * (eq - k["value"])) * mult, 0.25, 1.5)
                return self._rto(obs, f * obs.pot)
            if obs.street < 3 and eq >= 0.30 and self.rng.random() < k["semi"]:
                return self._rto(obs, 0.5 * obs.pot)
            return (CALL, 0)
        if obs.street == 3 and one_pair and obs.to_call > k["river_fold"] * (obs.pot - obs.to_call):
            return (FOLD, 0)
        if eq >= k["raise"] and len(self._raises(obs)) < 3:
            f = _clamp(0.8 * mult, 0.25, 1.5)
            if one_pair and spr > 6:
                f = min(f, 0.8)                   # SPR > 6: one pair never jams
            return self._rto(obs, top + f * (obs.pot + obs.to_call))
        return (CALL, 0) if eq >= need else (FOLD, 0)


class GhHobbyRaise(_Gh):
    """Hobby bot: raises any pair or two cards 8+ preflop, raises postflop when a hole card
    pairs the board, otherwise calls. Never folds."""
    NOM = {"pre": 2.0, "post": 0.75}

    def decide(self, obs):
        if len(self._raises(obs)) >= 3:
            return (CALL, 0)
        if obs.street == 0:
            hi, lo, s, pair = self._hole2(obs)
            if pair or lo >= 8:
                return self._rto(obs, self.k["pre"] * max(obs.bets) + obs.bb)
            return (CALL, 0)
        bv = {self._val[c] for c in obs.board}
        if any(self._val[c] in bv for c in obs.hole):
            return self._rto(obs, max(obs.bets) + self.k["post"] * obs.pot)
        return (CALL, 0)


GITHUB_BOTS = {
    "gh_catscore": GhCatScore, "gh_opus": GhOpus, "gh_tiers": GhTiers, "gh_flash": GhFlash,
    "gh_minnit": GhMinnit, "gh_invstation": GhInvStation, "gh_potodds": GhPotOdds,
    "gh_mc1jam": GhMc1Jam, "gh_ladder": GhLadder, "gh_shark": GhShark,
    "gh_classifier": GhClassifier, "gh_hobbyraise": GhHobbyRaise,
}
GITHUB_COMMON = ("gh_catscore", "gh_opus", "gh_tiers", "gh_flash", "gh_minnit", "gh_mc1jam")


def github_fields(prepped="prep:params/rival_prep.json"):
    """Evaluation fields of GitHub-bot designs, 7 opponents a table drawn by weight (the most
    common LLM shapes, 1-5 and 8, at 1.5). Never in a tuning default; +prep adds a prepped
    copy, as in llm_fields."""
    base = {k: (1.5 if k in GITHUB_COMMON else 1) for k in GITHUB_BOTS}
    return {"github": base, "github+prep": {**base, prepped: 1.2}}


# ---------------------------------------------------------------------------
# Event-field designs (Nov 6): the shapes of the public bots written for THIS event (one-shot
# LLM builds and a few team bots), from the behavioral specs in
# bench/standard/github_wide.md, not from their code. They fold 73-88% to 3-bets and ~82% to
# shoves and over-apply ICM to calls. Evaluation fields only (event, event+prep), never in a
# tuning default. Every instance scales its thresholds by its own noise (+-10-20%).
# ---------------------------------------------------------------------------

def _ingest_pre(pst, history):
    """Preflop counters per seat: opens, faced/folded a 3-bet over its open, and faced/folded
    a raise before putting voluntary chips in (fold to steal / to an open)."""
    raises = 0
    opener = None
    faced, faced3 = set(), set()
    vol = set()
    for seat, st, kind, amt, all_in in history:
        if st != 0:
            break
        if kind == POST:
            continue
        p = pst[seat]
        if raises >= 1 and seat not in faced and seat not in vol and seat != opener:
            faced.add(seat)
            p["fr_n"] += 1
            p["fr_f"] += kind == FOLD
        if raises >= 2 and seat == opener and seat not in faced3:
            faced3.add(seat)
            p["f3_n"] += 1
            p["f3_f"] += kind == FOLD
        if kind == RAISE:
            raises += 1
            if raises == 1:
                opener = seat
                p["open"] += 1
            vol.add(seat)
        elif kind == CALL:
            vol.add(seat)


def _new_pst():
    return {"open": 0, "fr_n": 0, "fr_f": 0, "f3_n": 0, "f3_f": 0}


class _Ev(_Gh):
    """Shared helpers: preflop counters, players behind, the '10 as rank 2' card bug, the
    'any raise over x% of the stack becomes all-in' sizing tell, and a hash coin."""
    TENBUG = 0.0
    ALLIN_FRAC = None          # (lo, hi): raises above this share of the stack go all-in
    F3_PRIOR, F3_W = 0.75, 4.0
    FR_PRIOR, FR_W = 0.80, 6.0

    def __init__(self, tables=None, seed=None):
        super().__init__(tables, seed)
        self.allin_frac = self.rng.uniform(*self.ALLIN_FRAC) if self.ALLIN_FRAC else None
        self.salt = self.rng.randrange(1 << 30)
        v = self.T.v
        S = v.suits
        self._tmap = None
        if self.tenbug and "T" in v.ranks and "2" in v.ranks:
            t, two = v.ranks.index("T"), v.ranks.index("2")
            self._tmap = {t * S + su: two * S + su for su in range(S)}
        if self.tenbug and "T" in v.ranks:
            t = v.ranks.index("T")
            for c in range(t * S, t * S + S):
                self._val[c] = 2
        self.pst = []

    def new_table(self, seat, n_seats):
        super().new_table(seat, n_seats)
        self.pst = [_new_pst() for _ in range(n_seats)]

    def observe(self, event):
        super().observe(event)
        if event[0] == "hand_end" and self.pst:
            _ingest_pre(self.pst, event[1]["history"])

    def act(self, obs):
        if len(self.pst) != len(obs.stacks):
            self.new_table(obs.seat, len(obs.stacks))
        return self.decide(obs)

    # -- facts ------------------------------------------------------------
    def _hole(self, obs):
        """Hole cards as this instance reads them ('10' parsed as a 2 in bugged instances)."""
        if not self._tmap:
            return tuple(obs.hole)
        used = set(obs.hole) | set(obs.board)
        out = []
        for c in obs.hole:
            d = self._tmap.get(c)
            if d is not None and d not in used and d not in out:
                out.append(d)
            else:
                out.append(c)
        return tuple(out)

    def _pct(self, obs):
        return self.T.pct(self.T.hole_class(self._hole(obs)))

    def _cls(self, obs):
        return self.T.hole_class(self._hole(obs))

    def _behind(self, obs):
        order = self._order(obs)
        if obs.seat not in order:
            return 0
        return sum(1 for s in order[order.index(obs.seat) + 1:] if obs.in_hand[s])

    def _behind_seats(self, obs):
        order = self._order(obs)
        if obs.seat not in order:
            return []
        return [s for s in order[order.index(obs.seat) + 1:] if obs.in_hand[s]]

    def _is_bb(self, obs):
        posts = self._posts(obs)
        return len(posts) >= 2 and obs.seat == posts[1]

    def _in_blinds(self, obs):
        return obs.seat in self._posts(obs)[:2]

    def _limpers(self, obs):
        return sum(1 for h in obs.history if h[1] == 0 and h[2] == CALL) if not self._raises(obs, 0) else 0

    def _f3(self, s):
        p = self.pst[s] if self.pst else _new_pst()
        return (p["f3_f"] + self.F3_PRIOR * self.F3_W) / (p["f3_n"] + self.F3_W)

    def _fr(self, s):
        p = self.pst[s] if self.pst else _new_pst()
        return (p["fr_f"] + self.FR_PRIOR * self.FR_W) / (p["fr_n"] + self.FR_W)

    def _open_rate(self, s):
        """Share of hands this seat opened (prior 0.2 over 8 hands)."""
        p = self.pst[s] if self.pst else _new_pst()
        h = self.stats[s].hands if self.stats else 0
        return (p["open"] + 0.2 * 8) / (h + 8)

    def _coin(self, obs, tag=0):
        x = hash((self.salt, tag, obs.hand_no, obs.street, len(obs.history), tuple(obs.board), tuple(obs.hole)))
        return (x & 0xFFFF) / 65536.0

    def _send(self, obs, target):
        """Raise to `target`; with the sizing tell, any raise over allin_frac of the stack jams."""
        tot = obs.stacks[obs.seat] + obs.bets[obs.seat]
        if self.allin_frac is not None and target - obs.bets[obs.seat] >= self.allin_frac * tot:
            return self._shove(obs)
        return self._raise(obs, target)

    def _ip(self, obs, vs_seat):
        """In position vs `vs_seat` postflop (acts later): not in the blinds, or the BB vs the SB."""
        posts = self._posts(obs)
        blinds = posts[:2]
        if obs.seat in blinds:
            return vs_seat in blinds and blinds.index(obs.seat) > blinds.index(vs_seat)
        if vs_seat in blinds:
            return True
        order = self._order(obs)
        return obs.seat in order and vs_seat in order and order.index(obs.seat) > order.index(vs_seat)

    def _eq_hu_post(self, obs, rollouts=None):
        e = self.T.post_equity(self._hole(obs), obs.board)[0]
        if rollouts:
            sd = math.sqrt(max(e * (1 - e), 0.01) / rollouts)
            return _clamp(e + self.rng.gauss(0.0, sd), 0.0, 1.0)
        return self._noise(e)


class EvCodexTag(_Ev):
    """A1, the modal one-shot LLM build: open table by players behind, 2.2/2.5 bb; push/fold at
    <= ~12.5 bb with jam % = base[behind]*(10/bb)^0.75; 3-bets the top max(.025, .25 r) at
    3.0x IP / 3.6x OOP; vs a 3-bet continues with the top ~3%; any raise over 40-75% of the
    stack goes all-in; no river bluffs; 'ICM' is a flat +0.03. Bugs: the fallback folds
    facing a bet (~3% of those spots), '10' read as a 2 in ~30% of instances."""
    TENBUG = 0.3
    ALLIN_FRAC = (0.40, 0.75)
    rollouts = 100
    OPEN = (0.30, 0.45, 0.36, 0.27, 0.21, 0.17, 0.14, 0.12)       # by players behind 0..7
    PUSH = (0.58, 0.58, 0.39, 0.28, 0.21, 0.17, 0.145, 0.125)
    NOM = {"open_m": 1.0, "push_m": 1.0, "pf_bb": 12.5, "pf_exp": 0.75, "three": 0.25,
           "cont3": 0.03, "call_r": 0.65, "call_bb": 0.90, "cost": 0.08, "cost_bb": 0.12,
           "vbet": 0.67, "vsize": 0.66, "csize": 0.47, "raise": 0.83, "disc0": 0.04, "disc1": 0.075,
           "icm": 0.03, "fallback": 0.03, "shove_call": 0.40}

    def _jam_pct(self, obs, eff):
        b = min(self._behind(obs), 7)
        return _clamp(self.PUSH[b] * self.k["push_m"] * (10.0 / max(eff, 1.0)) ** self.k["pf_exp"], 0.0, 1.0)

    def _hm(self, obs, e1=None):
        n = len(self._villains(obs)) or 1           # all-in opponents count too (bug)
        e1 = self._eq_hu_post(obs) if e1 is None else e1
        return e1 ** (1 + 0.65 * (n - 1))

    def decide(self, obs):
        k = self.k
        pct = self._pct(obs)
        stack = obs.stacks[obs.seat]
        eff = self._eff_bb(obs)
        if obs.street == 0:
            raises = self._raises(obs, 0)
            if not raises:
                if eff <= k["pf_bb"]:
                    if pct <= self._jam_pct(obs, eff):
                        return self._shove(obs)
                    return self._cf(obs)
                b = min(self._behind(obs), 7)
                lim = self._limpers(obs)
                if pct <= self.OPEN[b] * k["open_m"] * 0.58 ** lim:
                    size = 3.0 if b == 1 else 2.2 if eff < 25 else 2.5
                    return self._send(obs, (size + lim) * obs.bb)
                return self._cf(obs)
            if obs.to_call >= 0.35 * stack or eff <= k["pf_bb"] or raises[-1][4]:
                # committed / short: jam or fold; vs a shove, call the top slice of its own jam range
                thr = max(0.03, k["shove_call"] * self._jam_pct(obs, eff))
                if len(raises) >= 2:
                    thr = min(thr, k["cont3"])
                if obs.to_call >= 0.5 * stack:
                    thr *= 1.0 - k["icm"] * 3          # flat 'ICM' margin
                return (self._shove(obs) if pct <= thr else self._cf(obs))
            if len(raises) >= 2:
                if pct <= k["cont3"] * 0.5:
                    return self._send(obs, max(obs.bets) * 2.3)
                return (CALL, 0) if pct <= k["cont3"] else self._cf(obs)
            rs = raises[-1][0]
            st = self.stats[rs] if self.stats else None
            r = ((st.pfr if st else 0) + 0.15 * 8) / ((st.hands if st else 0) + 8)
            ip = self._ip(obs, rs)
            if pct <= max(0.025, k["three"] * r):
                return self._send(obs, max(obs.bets) * (3.0 if ip else 3.6))
            bb = self._is_bb(obs)
            if pct <= (k["call_bb"] if bb else k["call_r"]) * r and \
                    obs.to_call <= (k["cost_bb"] if bb else k["cost"]) * stack:
                return (CALL, 0)
            return self._cf(obs)
        hm = self._hm(obs)
        vs = self._villains(obs)
        if obs.to_call == 0:
            if hm >= k["vbet"]:
                return self._send(obs, k["vsize"] * obs.pot)
            if obs.street == 1 and len(vs) == 1 and self._pfr_seat(obs) == obs.seat:
                p = _clamp(1.6 * self._rate(vs[0], "fold_to_bet") - 0.1, 0.1, 0.85)
                if self.rng.random() < p:
                    return self._send(obs, k["csize"] * obs.pot)
            return (CALL, 0)                     # no river bluffs
        if self.rng.random() < k["fallback"]:
            return (FOLD, 0)                     # exception path: the fallback folds
        if hm >= k["raise"] and len(self._raises(obs)) < 3:
            return self._send(obs, max(obs.bets) + obs.pot)
        agg_s = max(vs, key=lambda s: obs.bets[s]) if vs else obs.seat
        size = obs.to_call / max(obs.pot - obs.to_call, 1)
        disc = (k["disc0"] + k["disc1"] * size) * (1.35 - self._rate(agg_s, "agg"))
        need = self._po(obs) + disc + (k["icm"] if obs.to_call >= 0.5 * stack else 0.0)
        return (CALL, 0) if hm >= need else (FOLD, 0)


class EvGhcpFastrange(_Ev):
    """A2, the best of 11 one-shot bots in a mirror test: open width by players behind,
    value 3-bets min(.065, max(.028, .19 w)), light A2s-A5s 3-bets 13% vs wide openers that
    fold; push <= 11 bb; postflop noisy MC (96 samples) value bets at eq >= .59+.045(n-1),
    hash-coin bluffs on flop/turn (mostly dry boards); 0.03% of decisions time out (fold)."""
    ALLIN_FRAC = (0.40, 0.55)
    OPEN = (0.65, 0.49, 0.45, 0.34, 0.27, 0.23, 0.20, 0.17)
    NOM = {"open_m": 1.0, "v3_hi": 0.065, "v3_lo": 0.028, "v3_k": 0.19, "light": 0.13,
           "call_ip": 0.78, "call_oop": 0.60, "call_bb": 0.13, "push_bb": 11.0, "push_k": 0.84,
           "vbet": 0.59, "vstep": 0.045, "bluff": 1.0, "raise": 0.80, "timeout": 0.0003}

    def _w(self, s):
        return _clamp(self._open_rate(s) * 1.1, 0.05, 0.9)

    def decide(self, obs):
        k = self.k
        if self.rng.random() < k["timeout"]:
            return self._cf(obs)
        pct = self._pct(obs)
        stack = obs.stacks[obs.seat]
        eff = self._eff_bb(obs)
        if obs.street == 0:
            raises = self._raises(obs, 0)
            b = min(self._behind(obs), 7)
            alive = self._alive(obs)
            width = (0.80 if alive == 2 else self.OPEN[b]) * k["open_m"]
            if not raises:
                if eff <= k["push_bb"]:
                    thr = k["push_k"] * width + 0.015 + (0.12 if eff <= 3 else 0.10 if eff <= 5 else 0.0)
                    return self._shove(obs) if pct <= thr else self._cf(obs)
                width -= 1.1 * (2.3 * obs.bb / max(stack, 1))
                if pct <= width:
                    size = (2.15 if eff < 30 else 2.35) + (0.35 if b == 1 else 0.0)
                    return self._send(obs, (size + self._limpers(obs)) * obs.bb)
                return self._cf(obs)
            rs = raises[-1][0]
            w = self._w(rs)
            lvl = len(raises)
            ip = self._ip(obs, rs)
            if raises[-1][4] or obs.to_call >= 0.4 * stack:     # facing a shove / committed
                thr = _clamp(0.45 * w, 0.03, 0.25) if lvl == 1 else 0.03
                return (CALL, 0) if pct <= thr else self._cf(obs)
            v3 = min(k["v3_hi"], max(k["v3_lo"], k["v3_k"] * w)) if lvl == 1 else 0.018 if lvl == 2 else 0.009
            if pct <= v3:
                return self._send(obs, max(obs.bets) * (3.0 if ip else 3.6))
            hi, lo, su, pair = self._hole2(obs)
            if lvl == 1 and su and hi == 14 and 2 <= lo <= 5 and w > 0.30 and self._fr(rs) > 0.5 \
                    and self._coin(obs, 1) < k["light"]:
                return self._send(obs, max(obs.bets) * (3.0 if ip else 3.6))
            if lvl == 1:
                thr = w * (k["call_ip"] if ip else k["call_oop"]) + (k["call_bb"] if self._is_bb(obs) else 0.0)
            else:
                thr = 0.045 if lvl == 2 else 0.012
            return (CALL, 0) if pct <= thr else self._cf(obs)
        vs = self._villains(obs)
        n = max(len(vs), 1)
        roll = 256 if (n == 1 and obs.street == 3) else 96
        e = self.T.post_equity(self._hole(obs), obs.board)
        e = e[n - 1] if n <= 3 else e[2] ** (n / 3.0)
        e = _clamp(e + self.rng.gauss(0.0, math.sqrt(max(e * (1 - e), 0.01) / roll)), 0.0, 1.0)
        need_v = k["vbet"] + k["vstep"] * (n - 1) + (0.025 if obs.street == 3 else 0.0)
        if obs.to_call == 0:
            if e >= need_v:
                return self._send(obs, 0.66 * obs.pot)
            if obs.street < 3:
                aggr = self._pfr_seat(obs) == obs.seat
                ip = all(self._ip(obs, s) for s in vs)
                draw = _draw_eq(self._val, self._suit, obs.hole, obs.board) > 0
                fold = sum(self._rate(s, "fold_to_bet") for s in vs) / n
                p = 0.10 + 0.13 * aggr + 0.09 * ip + 0.16 * draw + 0.5 * (fold - 0.43)
                vals = [self._val[c] for c in obs.board]
                suits = [self._suit[c] for c in obs.board]
                dry = len(set(vals)) == len(vals) and len(set(suits)) >= len(suits) - 1 and \
                    max(vals) - min(vals) >= 5
                p *= k["bluff"] * (1.0 if dry else 0.5) / n
                if self._coin(obs, 2) < p:
                    return self._send(obs, 0.5 * obs.pot)
            return (CALL, 0)
        if e >= k["raise"] and len(self._raises(obs)) < 3:
            return self._send(obs, max(obs.bets) + 0.9 * obs.pot)
        need = self._need(obs, icm=self._alive(obs) == 2 and obs.to_call >= 0.3 * stack) + 0.02
        return (CALL, 0) if e >= need else (FOLD, 0)


class EvPushfold4(_Ev):
    """A3: push/fold <= 15 bb with jam % clamp(5.8/bb/n^0.75) where n counts ALL live
    opponents (bug: not players behind); re-jams the top ~half of its jam range over a shove
    (it can't flat in the shove branch); deep opens min(.55, .9/(behind+1.2)) to 2.3 bb,
    3-bets the top 3%, flats the top 8% cheap; postflop made-hand tiers (two pair on a
    paired board read as two pair: bug)."""
    NOM = {"pf_bb": 15.0, "jam_k": 5.8, "recall": 0.5, "open_k": 0.9, "three": 0.03, "flat": 0.08,
           "flat_cost": 0.12, "bb_def": 0.35, "jam4": 0.02, "tptk": 0.42, "tptk_r": 0.34, "weak": 0.25,
           "draw": 0.30, "vsize": 0.66}

    def _jam(self, obs, eff):
        n = max(self._alive(obs) - 1, 1)
        return _clamp(self.k["jam_k"] / max(eff, 1.0) / n ** 0.75, 0.025, 1.0)

    def decide(self, obs):
        k = self.k
        pct = self._pct(obs)
        stack = obs.stacks[obs.seat]
        eff = self._eff_bb(obs)
        if obs.street == 0:
            raises = self._raises(obs, 0)
            if eff <= k["pf_bb"] or obs.to_call >= 0.35 * stack:
                jam = self._jam(obs, eff)
                if not raises:
                    return self._shove(obs) if pct <= jam else self._cf(obs)
                return self._shove(obs) if pct <= k["recall"] * jam else self._cf(obs)
            if not raises:
                if pct <= min(0.55, k["open_k"] / (self._behind(obs) + 1.2)):
                    return self._raise(obs, (2.3 + self._limpers(obs)) * obs.bb)
                return self._cf(obs)
            if len(raises) >= 2:
                return self._shove(obs) if pct <= k["jam4"] else self._cf(obs)
            if pct <= k["three"]:
                return self._raise(obs, max(obs.bets) * 3)
            if pct <= k["flat"] and obs.to_call <= k["flat_cost"] * stack:
                return (CALL, 0)
            if self._is_bb(obs) and pct <= k["bb_def"] and obs.to_call <= 1.5 * obs.bb:
                return (CALL, 0)
            return self._cf(obs)
        c = self._cat(obs)
        bvals = [self._val[x] for x in obs.board]
        hvals = [self._val[x] for x in obs.hole]
        po = self._po(obs)
        if c >= TWO_PAIR:
            if obs.to_call == 0:
                return self._raise(obs, k["vsize"] * obs.pot)
            return self._raise(obs, 3 * max(obs.bets)) if len(self._raises(obs)) < 3 else (CALL, 0)
        top = max(bvals)
        tp = c == PAIR and top in hvals
        pocket = len(set(hvals)) < len(hvals) and min(hvals) > top
        if tp or pocket:
            if obs.to_call == 0:
                return self._raise(obs, 0.5 * obs.pot)
            return (CALL, 0) if po <= (k["tptk_r"] if obs.street == 3 else k["tptk"]) else (FOLD, 0)
        if c == PAIR and any(v in bvals for v in hvals) or (len(set(hvals)) < len(hvals)):
            return (CALL, 0) if po <= k["weak"] else self._cf(obs)
        if obs.street < 3 and _draw_eq(self._val, self._suit, obs.hole, obs.board) > 0:
            return (CALL, 0) if po <= k["draw"] else self._cf(obs)    # gutshots count as strong
        return self._cf(obs)


class EvMcMwbug(_Ev):
    """A4: MC equity vs the live opponents with bet/raise thresholds scaled h^(n^0.75) (the
    0.62 bet line falls to ~0.13 at 7 opponents, so it bets and raises average hands
    multiway) while calls stay at pot odds; at <= 15 bb every call is a re-shove, at <= 25 bb
    every raise is all-in; risk premium 0.05*share when calling >= 25% of the stack."""
    rollouts = 60
    NOM = {"bet": 0.62, "raise": 0.75, "open": 0.56, "size": 0.66, "prem": 0.05, "jam_bb": 15.0,
           "allin_bb": 25.0}

    def decide(self, obs):
        k = self.k
        n = max(len(self._villains(obs)), 1)
        if obs.street == 0:
            e = self._noise(self.T.eq(self._cls(obs), n))
        else:
            e = self._eq_n(obs, n)
        sc = n ** 0.75
        t_bet, t_raise = k["bet"] ** sc, k["raise"] ** sc
        stack = obs.stacks[obs.seat]
        eff = self._eff_bb(obs)

        def up(target):
            return self._shove(obs) if eff <= k["allin_bb"] else self._raise(obs, target)

        if obs.street == 0:
            raised = bool(self._raises(obs, 0))
            if not raised:
                if e >= k["open"] ** sc:
                    return up(3 * obs.bb)
                return self._cf(obs)
            if e >= t_raise:
                return up(max(obs.bets) * 3)
        else:
            if obs.to_call == 0:
                return up(k["size"] * obs.pot) if e >= t_bet else (CALL, 0)
            if e >= t_raise:
                return up(max(obs.bets) + obs.pot)
        if obs.to_call == 0:
            return (CALL, 0)
        need = self._po(obs) + (k["prem"] * obs.to_call / max(stack, 1) if obs.to_call >= 0.25 * stack else 0.0)
        if e >= need:
            return self._shove(obs) if eff <= k["jam_bb"] else (CALL, 0)
        return (FOLD, 0)


class EvStrong1(_Ev):
    """A5: opens 0.52/n^0.78 scaled by the fold-to-raise of the players behind; 3-bets on
    range equity >= .555, calls when realized equity beats the price plus a survival premium
    (.05-.06 x risk fraction); push/fold charts when short; postflop range-weighted equity,
    shoves instead of calling when < 30% of the pot would be left behind."""
    ranged = True
    rollouts = 150
    PRI = {**PRIORS, "vpip": 0.28, "pfr": 0.14, "fold_to_bet": 0.40}
    NOM = {"open_k": 0.52, "three": 0.555, "real_ip": 0.90, "real_bb": 0.84, "real": 0.78,
           "surv": 0.055, "pf_bb": 12.0, "vbet": 0.62, "vsize": 0.66, "raise": 0.82, "bluff": 0.20}
    FR_PRIOR, FR_W = 0.60, 6.0

    def new_table(self, seat, n_seats):
        super().new_table(seat, n_seats)
        for st in self.stats:
            st.prior = self.PRI

    def _need_s(self, obs):
        stack = obs.stacks[obs.seat]
        risk = min(obs.to_call / max(stack + obs.bets[obs.seat], 1), 1.0)
        prem = self.k["surv"] * risk
        alive = [obs.stacks[s] + obs.bets[s] for s in range(len(obs.stacks)) if obs.stacks[s] + obs.bets[s] > 0]
        if obs.hand_no > 180 and alive and stack + obs.bets[obs.seat] >= max(alive):
            prem += 0.04
        return self._po(obs) + prem

    def decide(self, obs):
        k = self.k
        pct = self._pct(obs)
        stack = obs.stacks[obs.seat]
        if obs.street == 0:
            if self._eff_bb(obs) <= k["pf_bb"]:
                return self._pushfold(obs)
            raises = self._raises(obs, 0)
            if not raises:
                bs = self._behind_seats(obs)
                n = max(len(bs), 1)
                f = sum(self._fr(s) for s in bs) / n if bs else 0.6
                width = k["open_k"] / n ** 0.78 * _clamp((f / 0.6) ** 1.2, 0.65, 1.5)
                if pct <= width:
                    return self._raise(obs, (2.5 + self._limpers(obs)) * obs.bb)
                return self._cf(obs)
            rs = raises[-1][0]
            y = self._rate(rs, "pfr") * (0.35 if len(raises) >= 2 else 1.0)
            eq = self._pre_eq(obs, y)
            if eq >= k["three"] + 0.08 * (len(raises) - 1) and len(raises) < 4:
                return self._raise(obs, max(obs.bets) * (3.0 if self._ip(obs, rs) else 3.6))
            real = k["real_ip"] if self._ip(obs, rs) else k["real_bb"] if self._is_bb(obs) else k["real"]
            return (CALL, 0) if eq * real >= self._need_s(obs) else self._cf(obs)
        eq = self._post_eq(obs)
        vs = self._villains(obs)
        if obs.to_call == 0:
            if eq >= k["vbet"]:
                return self._raise(obs, k["vsize"] * obs.pot)
            if len(vs) == 1 and obs.street < 3:
                bf = _clamp(self._rate(vs[0], "fold_to_bet") / 0.4, 0.2, 1.5)
                if self.rng.random() < k["bluff"] * bf * 0.5:
                    return self._raise(obs, 0.5 * obs.pot)
            return (CALL, 0)
        if eq >= k["raise"] and len(self._raises(obs)) < 3:
            return self._raise(obs, max(obs.bets) + obs.pot)
        if eq >= self._need_s(obs):
            left = stack - obs.to_call
            if left < 0.3 * (obs.pot + obs.to_call):
                return self._shove(obs)
            return (CALL, 0)
        return (FOLD, 0)


class EvReshover(_Ev):
    """A6, the winner archetype: TAG, plus at 8-30 bb it re-shoves over a single open from
    any position when chip EV > 0.1 pot, assuming the opener calls with the top 45% of its
    open range and folds at its fold-to-3-bet rate (prior .75, weight 4)."""
    rollouts = 150
    OPEN = (0.30, 0.42, 0.34, 0.26, 0.20, 0.17, 0.15, 0.14)
    NOM = {"open_m": 1.0, "three": 0.035, "cont3": 0.035, "flat": 0.10, "lo_bb": 8.0, "hi_bb": 30.0,
           "ev_k": 0.10, "call_frac": 0.45, "gate": 0.30, "vbet": 0.63, "vsize": 0.66, "raise": 0.82,
           "margin": 0.02, "pf_bb": 8.0}

    def _table_vpip(self, obs):
        seats = [s for s in range(len(obs.stacks)) if s != obs.seat and obs.stacks[s] + obs.bets[s] > 0]
        if not seats or not self.stats:
            return 0.25
        return sum(self._rate(s, "vpip") for s in seats) / len(seats)

    def _jam_ev(self, obs, rs):
        cls = self._cls(obs)
        w = _clamp(self._open_rate(rs), 0.04, 0.8)
        eq = self._noise(self.T.eq_vs_range(cls, _clamp(self.k["call_frac"] * w, 0.02, 1.0)))
        f = self._f3(rs)
        me = obs.stacks[obs.seat] + obs.bets[obs.seat]
        them = obs.stacks[rs] + obs.bets[rs]
        E = min(me, them)
        dead = obs.pot - obs.bets[obs.seat] - obs.bets[rs]
        win_called = eq * (dead + 2 * E) - (E - obs.bets[obs.seat])
        return f * obs.pot + (1 - f) * win_called - self.k["ev_k"] * obs.pot

    def decide(self, obs):
        k = self.k
        pct = self._pct(obs)
        eff = self._eff_bb(obs)
        if obs.street == 0:
            raises = self._raises(obs, 0)
            if not raises:
                if eff <= k["pf_bb"]:
                    return self._pushfold(obs)
                b = min(self._behind(obs), 7)
                if pct <= self.OPEN[b] * k["open_m"]:
                    return self._raise(obs, (2.3 + self._limpers(obs)) * obs.bb)
                return self._cf(obs)
            if len(raises) == 1 and not raises[0][4] and k["lo_bb"] <= eff <= k["hi_bb"] \
                    and self._table_vpip(obs) <= k["gate"] and self._jam_ev(obs, raises[0][0]) > 0:
                return self._shove(obs)
            if eff <= k["pf_bb"] or raises[-1][4]:
                return self._pushfold(obs)
            if len(raises) >= 2:
                if pct <= k["cont3"] * 0.5:
                    return self._shove(obs)
                return (CALL, 0) if pct <= k["cont3"] else self._cf(obs)
            if pct <= k["three"]:
                return self._raise(obs, max(obs.bets) * 3)
            if pct <= k["flat"] and self._po(obs) <= 0.35:
                return (CALL, 0)
            return self._cf(obs)
        eq = self._post_eq(obs)
        if obs.to_call == 0:
            return self._raise(obs, k["vsize"] * obs.pot) if eq >= k["vbet"] else (CALL, 0)
        if eq >= k["raise"] and len(self._raises(obs)) < 3:
            return self._raise(obs, max(obs.bets) + obs.pot)
        return (CALL, 0) if eq >= self._need(obs) + k["margin"] else (FOLD, 0)


class EvPolicybot(_Ev):
    """A7, a real team's bot: steals any two when the product over players behind of their
    P(fold to a steal) is >= 0.9; seats with no voluntary chips yet (after 8 hands) drop out
    of 'behind'; otherwise the open range scales by observed/assumed fold; ICM bubble factor
    tightens calls and first-in shoves vs the deepest stack behind. C-bets air only heads-up
    vs folders, 3/4 pot value vs stations."""
    ranged = True
    rollouts = 200
    OPEN = (0.30, 0.45, 0.36, 0.27, 0.21, 0.17, 0.14, 0.12)
    NOM = {"steal": 0.90, "assume": 0.80, "pf_bb": 13.0, "three": 0.04, "flat": 0.10, "vbet": 0.62,
           "vsize": 0.6, "raise": 0.82, "margin": 0.02, "cb_ftb": 0.35}
    FR_PRIOR, FR_W = 0.80, 6.0

    def _broken(self, s):
        st = self.stats[s] if self.stats else None
        return st is not None and st.hands >= 8 and st.vpip == 0

    def decide(self, obs):
        k = self.k
        pct = self._pct(obs)
        eff = self._eff_bb(obs)
        if obs.street == 0:
            raises = self._raises(obs, 0)
            behind = [s for s in self._behind_seats(obs) if not self._broken(s)]
            if not raises:
                if eff <= k["pf_bb"]:
                    widen = 1.0
                    if behind:
                        deep = max(behind, key=lambda s: obs.stacks[s] + obs.bets[s])
                        total = sum(obs.stacks) + obs.pot
                        mine = obs.stacks[obs.seat] + obs.bets[obs.seat]
                        bf = self.T.bubble_factor(self._alive(obs), mine / max(total, 1),
                                                  (obs.stacks[deep] + obs.bets[deep]) / max(total, 1), 1.0)
                        if bf:
                            widen = _clamp(1.0 / bf, 0.6, 1.0)
                    return self._pushfold(obs, widen=widen)
                pf = 1.0
                for s in behind:
                    pf *= self._fr(s)
                if pf >= k["steal"] and self._limpers(obs) == 0:
                    return self._raise(obs, 2.2 * obs.bb)
                b = min(len(behind), 7)
                avg = sum(self._fr(s) for s in behind) / len(behind) if behind else 1.0
                width = self.OPEN[b] * _clamp(avg / k["assume"], 0.5, 3.0) ** 2
                if pct <= width:
                    return self._raise(obs, (2.5 + self._limpers(obs)) * obs.bb)
                return self._cf(obs)
            if eff <= k["pf_bb"] or raises[-1][4]:
                return self._pushfold(obs)
            rs = raises[-1][0]
            if len(raises) == 1 and pct <= k["three"]:
                return self._raise(obs, max(obs.bets) * 3)
            if len(raises) >= 2:
                return (CALL, 0) if pct <= 0.03 else self._cf(obs)
            if pct <= k["flat"] * 1.5:
                y = self._rate(rs, "pfr")
                if self._pre_eq(obs, y) >= self._need(obs) + 0.03:
                    return (CALL, 0)
            return self._cf(obs)
        eq = self._post_eq(obs)
        vs = self._villains(obs)
        if obs.to_call == 0:
            if eq >= k["vbet"]:
                station = len(vs) == 1 and self._rate(vs[0], "fold_to_bet") < 0.25
                return self._raise(obs, (0.75 if station else k["vsize"]) * obs.pot)
            if obs.street == 1 and len(vs) == 1 and self._pfr_seat(obs) == obs.seat \
                    and self._rate(vs[0], "fold_to_bet") >= k["cb_ftb"]:
                return self._raise(obs, 0.4 * obs.pot)
            return (CALL, 0)
        if eq >= k["raise"] and len(self._raises(obs)) < 3:
            return self._raise(obs, max(obs.bets) + obs.pot)
        return (CALL, 0) if eq >= self._need(obs) + k["margin"] else (FOLD, 0)


class EvCfrPushfold(RivalTag):
    """A8: near-Nash push/fold from published charts (our bundle's) at <= 15 bb (HU SB jams
    ~58% at 10 bb), range-weighted MC postflop with many samples, tight-solid deep."""
    rollouts = 800
    SPEC = {"open_early": (0.10, 0.13), "open_late": (0.30, 0.40), "three": (0.03, 0.05),
            "flat": (0.07, 0.11), "pf_bb": (14.5, 15.5), "vbet": (0.60, 0.68), "cbet": (0.40, 0.60),
            "size": (0.55, 0.70), "margin": (0.01, 0.04), "big_margin": (0.06, 0.12)}


class EvGunslinger(_Ev):
    """A9, Fullhouse 4th place: 3-bets ~33% of hands vs opens, 4-bets its own opens when
    3-bet, never 5-bet bluffs; multiway equity eq^(1+.35(n-1))."""
    rollouts = 120
    OPEN = (0.35, 0.50, 0.42, 0.33, 0.27, 0.22, 0.19, 0.17)
    NOM = {"open_m": 1.0, "three": 0.33, "four_ok": 1.0, "five": 0.04, "pf_bb": 10.0, "vbet": 0.60,
           "vsize": 0.7, "cbet": 0.6, "raise": 0.80, "margin": 0.03}

    def decide(self, obs):
        k = self.k
        pct = self._pct(obs)
        eff = self._eff_bb(obs)
        if obs.street == 0:
            raises = self._raises(obs, 0)
            if eff <= k["pf_bb"]:
                return self._pushfold(obs, widen=1.2)
            b = min(self._behind(obs), 7)
            open_w = self.OPEN[b] * k["open_m"]
            if not raises:
                if pct <= open_w:
                    return self._raise(obs, (2.5 + self._limpers(obs)) * obs.bb)
                return self._cf(obs)
            if raises[-1][4] or obs.to_call >= 0.4 * obs.stacks[obs.seat]:
                return (CALL, 0) if pct <= k["five"] else self._cf(obs)       # never 5-bet bluffs
            if len(raises) == 1:
                if pct <= k["three"]:
                    return self._raise(obs, max(obs.bets) * (3.0 if self._ip(obs, raises[0][0]) else 3.6))
                return (CALL, 0) if pct <= 0.40 and self._po(obs) <= 0.3 else self._cf(obs)
            if len(raises) == 2 and raises[0][0] == obs.seat:
                return self._raise(obs, max(obs.bets) * 2.3)            # 4-bets its own open
            return (CALL, 0) if pct <= k["five"] else self._cf(obs)
        vs = self._villains(obs)
        n = max(len(vs), 1)
        e = self._eq_hu_post(obs) ** (1 + 0.35 * (n - 1))
        if obs.to_call == 0:
            if e >= k["vbet"]:
                return self._raise(obs, k["vsize"] * obs.pot)
            if obs.street == 1 and self._pfr_seat(obs) == obs.seat and self.rng.random() < k["cbet"]:
                return self._raise(obs, 0.5 * obs.pot)
            return (CALL, 0)
        if e >= k["raise"] and len(self._raises(obs)) < 3:
            return self._raise(obs, max(obs.bets) + obs.pot)
        return (CALL, 0) if e >= self._po(obs) + k["margin"] else (FOLD, 0)


EVENT_BOTS = {
    "ev_codex_tag": EvCodexTag, "ev_ghcp_fastrange": EvGhcpFastrange, "ev_pushfold4": EvPushfold4,
    "ev_mc_mwbug": EvMcMwbug, "ev_strong1": EvStrong1, "ev_reshover": EvReshover,
    "ev_policybot": EvPolicybot, "ev_cfr_pushfold": EvCfrPushfold, "ev_gunslinger": EvGunslinger,
}
EVENT_WEIGHTS = {
    "ev_codex_tag": 3, "ev_ghcp_fastrange": 2, "ev_pushfold4": 1.5, "ev_mc_mwbug": 1, "ev_strong1": 1.5,
    "ev_reshover": 1.5, "ev_policybot": 1, "ev_cfr_pushfold": 1, "ev_gunslinger": 0.5,
}


def event_fields(prepped="prep:params/rival_prep.json"):
    """The field of bots written for this event (EVENT_BOTS), 7 opponents a table drawn by
    EVENT_WEIGHTS. Never in a tuning default; +prep adds a prepped copy, as in llm_fields."""
    base = dict(EVENT_WEIGHTS)
    return {"event": base, "event+prep": {**base, prepped: 1.2}}


RIVALS = {
    "rv_tag": RivalTag, "rv_lag": RivalLag, "rv_gto": RivalGto, "rv_exploit": RivalExploit,
    "rv_icm": RivalIcm, "rv_mc": RivalMc, "rv_aggro": RivalAggro, "rv_math": RivalMath,
    "rv_buggy": RivalBuggy, "rv_frozen": RivalFrozen,
    "rvh_sizer": HoldoutSizer, "rvh_bayes": HoldoutBayes, "rvh_jam": HoldoutJam,
    **LLM_BUGS,
    **GITHUB_BOTS,
    **EVENT_BOTS,
    "strong_eq": StrongEq,
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


WHALE_STRONG = "strong_eq"
WHALE_MIRROR = "prep:params/whale_mirror.json"     # a copy of cand_nlhe ("same research, more of it")
WHALE_BR = "prep:params/whale_br.json"             # best response tuned vs 7x cand_nlhe


def whale_fields(prepped="prep:params/rival_prep.json"):
    """Tables with one (or two) very strong rivals seated at every table, plus seats drawn
    from a realistic mix (rival-real, LLM-bug and GitHub designs). Each value is
    (weighted mix for the drawn seats, list of entries seated at every table)."""
    rf = rival_fields(prepped)["rival-real"]
    mix = {**rf, **{k: 0.35 for k in LLM_BUGS},
           **{k: (0.5 if k in GITHUB_COMMON else 0.3) for k in GITHUB_BOTS}}
    return {
        "whale1": (mix, [WHALE_STRONG]),
        "whale-mirror": (mix, [WHALE_MIRROR]),
        "whale2": (mix, [WHALE_STRONG, WHALE_MIRROR]),
        "whale-br": (mix, [WHALE_BR]),
        # added after the main runs: the event-repo archetypes as the drawn seats
        "whale-event": (dict(EVENT_WEIGHTS), [WHALE_STRONG]),
        "whale-event-cfr": (dict(EVENT_WEIGHTS), ["ev_cfr_pushfold"]),
        "whale-event-br": (dict(EVENT_WEIGHTS), [WHALE_BR]),
    }

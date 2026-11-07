"""Hybrid tables for the fallback study: the full bot's engine (PrepBot) on table pieces that
a from-scratch spec can reproduce. Flags pick what is replaced:
  curve  range-equity curve from a compact formula (CURVE_TH) on the spec's hand buckets
  e1     post_equity (vs 1..3 random) from the spec's buckets + ADJ
  pre    preflop pct / equity-vs-range / multiway equity from the spec's formulas
  pf     push/fold charts from the spec's rounded charts
  bf     bubble factor from the spec's formula
"""
import math
from nolimit.runtime import RANGE_X, RANGE_Y
from fallback import spec_bot as S

CURVE_TH = {}   # street -> list, filled by set_curve()
CURVE_KIND = "bucket"


def curve_feats(k, L, lx, ly, kind=None):
    kind = kind or CURVE_KIND
    base = [1.0, lx, ly, lx * ly, L * lx, L * ly, L * lx * ly, lx * lx, L * lx * lx, ly * ly]
    if kind == "bucket":
        for kk in range(13):
            d = 1.0 if k == kk else 0.0
            base += [d * lx, d * ly, d * lx * ly]
    return base


def spec_curve(hole, board):
    street = {3: 1, 4: 2, 5: 3}[len(board)]
    k = S.post_bucket(hole, board)
    L = S.logit(S.post_equity1(hole, board, street))
    th = CURVE_TH[street]
    out = []
    for y in RANGE_Y:
        ly = math.log(y)
        for x in RANGE_X:
            f = curve_feats(k, L, math.log(x), ly)
            z = L + sum(a * b for a, b in zip(th, f))
            out.append(1.0 / (1.0 + math.exp(-z)))
    return out


class HybTables:
    def __init__(self, T, flags):
        self._T = T
        self._f = set(flags)
        self._post_cache = {}
        self._rng_cache = {}
        if "pre" in self._f:
            R = "23456789TJQKA"
            self._name = {}
            for name in S.HAND:
                hi, lo = R.index(name[0]), R.index(name[1])
                off = len(name) == 2 or name[2] == "o"
                self._name[T.hole_class((hi * 4, lo * 4 + (1 if off else 0)))] = name

    def __getattr__(self, k):
        return getattr(self._T, k)

    def pct(self, cls):
        if "pre" in self._f:
            return S.HAND[self._name[cls]][0]
        return self._T.pct(cls)

    def eq_vs_range(self, cls, y):
        if "pre" in self._f:
            return S.eq_vs_range(self._name[cls], y)
        return self._T.eq_vs_range(cls, y)

    def eq(self, cls, n):
        if "pre" in self._f:
            e1 = S.HAND[self._name[cls]][1]
            return e1 ** (max(n, 1) ** 0.88)
        return self._T.eq(cls, n)

    def post_equity(self, hole, board):
        if "e1" in self._f:
            e = S.post_equity1(hole, board, {3: 1, 4: 2, 5: 3}[len(board)])
            return [e, e ** (2 ** 0.88), e ** (3 ** 0.88)]
        return self._T.post_equity(hole, board)

    def post_curve(self, hole, board):
        if "curve" in self._f:
            key = (tuple(hole), tuple(board))
            got = self._rng_cache.get(key)
            if got is None:
                if len(self._rng_cache) > 4096:
                    self._rng_cache.clear()
                got = self._rng_cache[key] = spec_curve(hole, board)
            return got
        return self._T.post_curve(hole, board)

    def shove_threshold(self, n, pos, eff_bb):
        if "pf" in self._f:
            if not 2 <= n <= 8 or pos >= n - 1:
                return None
            return S.interp(S._SHOVE[n][pos], eff_bb)
        return self._T.shove_threshold(n, pos, eff_bb)

    def call_threshold(self, n, spos, cpos, eff_bb):
        if "pf" in self._f:
            if not 2 <= n <= 8 or not spos < cpos < n:
                return None
            if n == 2:
                key = "hu"
            else:
                K = min(n - 1 - spos, 4)
                J = min(n - 1 - cpos, 2)
                key = ("3:" if n == 3 else "") + f"{K}{J}"
            row = S._CALL.get(key)
            return None if row is None else S.interp(row, eff_bb)
        return self._T.call_threshold(n, spos, cpos, eff_bb)

    def bubble_factor(self, n, hs, vs, risk):
        if "bf" in self._f:
            if n < 2:
                return None
            return S.bubble_factor(n, hs, vs, 1.0, risk)
        return self._T.bubble_factor(n, hs, vs, risk)


def load_curve(path="bench/fallback2/curve_th.json"):
    import json, os
    global CURVE_KIND
    if os.path.exists(path):
        d = json.load(open(path))
        CURVE_KIND = d.get("kind", "bucket")
        CURVE_TH.update({int(k): v for k, v in d["th"].items()})


def curve_z(street, k, L, y, x):
    th = CURVE_TH[street]
    lx = math.log(min(max(x, 0.05), 1.0))
    ly = math.log(min(max(y, 0.08), 1.0))
    f = curve_feats(k, L, lx, ly)
    return L + sum(a * b for a, b in zip(th, f))


class HybTablesC(HybTables):
    """As HybTables, with the curve evaluated directly at (y, x) (no 5x9 grid)."""

    def post_curve(self, hole, board):
        street = {3: 1, 4: 2, 5: 3}[len(board)]
        return (street, S.post_bucket(hole, board), S.logit(S.post_equity1(hole, board, street)))

    def range_equity(self, curve, y, x):
        st, k, L = curve
        return 1.0 / (1.0 + math.exp(-curve_z(st, k, L, y, x)))

    def interval_equity(self, curve, y, a, b):
        if b - a < 0.04:
            b = min(1.0, a + 0.04)
            a = b - 0.04
        eb = self.range_equity(curve, y, b)
        if a < 0.002:
            return eb
        ea = self.range_equity(curve, y, a)
        return min(max((b * eb - a * ea) / (b - a), 0.0), 1.0)


class HybTablesT(HybTablesC):
    """Diagnostic: continuous curve, but L from the bundle's equity net (true e1)."""

    def post_curve(self, hole, board):
        street = {3: 1, 4: 2, 5: 3}[len(board)]
        return (street, S.post_bucket(hole, board), S.logit(self._T.post_equity(hole, board)[0]))


E1_TH = {}


def load_e1(path="bench/fallback2/e1_th.json"):
    import json, os
    if os.path.exists(path):
        E1_TH.update({int(k): v for k, v in json.load(open(path)).items()})


def post_equity1_v2(hole, board, street):
    from e1_feats import e1_feats
    k = S.post_bucket(hole, board)
    th = E1_TH[street]
    g = S.GROUP[k]
    f = e1_feats(hole, board)
    nf = len(f)
    e = th[k] + sum(a * b for a, b in zip(th[13 + g * nf: 13 + (g + 1) * nf], f))
    return min(max(e, 0.02), 0.99)


CURVE2_TH = {}


class HybTablesC2(HybTablesC):
    """Continuous curve and e1 both from the v2 hand-strength formula (CURVE2_TH fitted on it)."""

    def post_equity(self, hole, board):
        e = post_equity1_v2(hole, board, {3: 1, 4: 2, 5: 3}[len(board)])
        return [e, e ** (2 ** 0.88), e ** (3 ** 0.88)]

    def post_curve(self, hole, board):
        street = {3: 1, 4: 2, 5: 3}[len(board)]
        return (street, S.post_bucket(hole, board), S.logit(post_equity1_v2(hole, board, street)))

    def range_equity(self, curve, y, x):
        st, k, L = curve
        lx = math.log(min(max(x, 0.05), 1.0))
        ly = math.log(min(max(y, 0.08), 1.0))
        f = curve_feats(k, L, lx, ly, "bucket")
        z = L + sum(a * b for a, b in zip(CURVE2_TH[st], f))
        return 1.0 / (1.0 + math.exp(-z))

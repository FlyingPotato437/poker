"""Payout-aware table views; no table data is retained in shared model objects.

The risk grid retains the frozen bot's approximation (equal stacks for opponents
other than hero/villain). Rank-probability differences make its values linear in
arbitrary payouts, so no payout-specific fitting happens during a decision.
"""
import copy
import math

DEFAULT_PAYOUTS = (50, 30, 20, 0, 0, 0, 0, 0)
HANDS_PER_LEVEL = 20
HAND_CAP = 250


def validate_payouts(values, players):
    p = tuple(float(x) for x in values)
    if not 2 <= players <= 10 or not p or len(p) > 10:
        raise ValueError("Invalid player count or payout length")
    if any(not math.isfinite(x) or x < 0 for x in p):
        raise ValueError("Payouts must be finite and nonnegative")
    if any(a < b for a, b in zip(p, p[1:])):
        raise ValueError("Payouts must be in descending place order")
    return (p + (0.0,) * players)[:players]


def equivalent_payouts(left, right, players):
    """ICM preferences are invariant to positive scaling and a constant offset."""
    a, b = validate_payouts(left, players), validate_payouts(right, players)
    ar, br = a[0] - a[-1], b[0] - b[-1]
    if ar == 0 or br == 0:
        return ar == br
    return all(abs((x - a[-1]) / ar - (y - b[-1]) / br) < 1e-9
               for x, y in zip(a, b))


class PayoutBasis:
    def __init__(self, meta, arrays):
        self.shares = tuple(meta["shares"])
        self.fracs = tuple(meta["fracs"])
        self.nmax = meta["nmax"]
        self.width = self.nmax
        self.gain = arrays["gain"][0]
        self.loss = arrays["loss"][0]

    def factor(self, payouts, n, hero_share, villain_share, risk_frac):
        if not 2 <= n <= self.nmax:
            return None
        sh, fr = self.shares, self.fracs
        i = min(range(len(sh)), key=lambda k: abs(sh[k] - hero_share))
        j = min(range(len(sh)), key=lambda k: abs(sh[k] - villain_share))
        base = (((n - 2) * len(sh) + i) * len(sh) + j) * len(fr)
        # Subtract the guaranteed last-place prize to avoid cancellation.
        p = tuple(x - payouts[n - 1] for x in payouts[:n])

        def at(k):
            offset = (base + k) * self.width
            gain = sum(p[r] * self.gain[offset + r] for r in range(n))
            loss = sum(p[r] * self.loss[offset + r] for r in range(n))
            return min(max(loss / gain, 0.8), 8.0) if gain > 1e-12 else 1.0

        f = min(max(risk_frac, fr[0]), fr[-1])
        for k in range(len(fr) - 1):
            if f <= fr[k + 1]:
                t = (f - fr[k]) / (fr[k + 1] - fr[k])
                return at(k) * (1 - t) + at(k + 1) * t
        return at(len(fr) - 1)


class DecisionTables:
    """A per-call view: immutable weights shared, hand-dependent caches private."""
    def __init__(self, source, basis, payouts, players, ante_bb=0.0):
        self.base = copy.copy(source)
        for name in ("_post_cache", "_rng_cache", "_feat_cache"):
            setattr(self.base, name, {})
        self.basis = basis
        self.payouts = validate_payouts(payouts, players)
        self.ante_bb = ante_bb
        meta = getattr(source, "meta", {})
        self.chart_payouts = meta.get("payouts")
        self.chart_ante = meta.get("pf_ante_bb")
        self.has_pushfold = bool(source.has_pushfold and self.chart_payouts is not None
                                 and self.chart_ante is not None
                                 and abs(self.chart_ante - ante_bb) < 1e-9)
        self.has_bf = basis is not None

    def __getattr__(self, name):
        return getattr(self.base, name)

    def _chart_matches(self, n):
        return (self.has_pushfold and n <= len(self.payouts)
                and equivalent_payouts(self.payouts, self.chart_payouts, n))

    def shove_threshold(self, n, pos, eff_bb):
        return self.base.shove_threshold(n, pos, eff_bb) if self._chart_matches(n) else None

    def call_threshold(self, n, shover_pos, caller_pos, eff_bb):
        return self.base.call_threshold(n, shover_pos, caller_pos, eff_bb) if self._chart_matches(n) else None

    def bubble_factor(self, n, hero_share, villain_share, risk_frac):
        if self.basis is None or n > len(self.payouts):
            return None
        return self.basis.factor(self.payouts, n, hero_share, villain_share, risk_frac)

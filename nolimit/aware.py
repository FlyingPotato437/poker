"""Bounty-aware wrapper for the 7-2 rule (engine bounty_72): the wrapped bot plays as usual,
except that holding 7-2 offsuit it does not fold when the price is small next to the
bounty it would collect. A cheap stand-in for "our bot knows about the bounty", used to
measure what not knowing costs (stipulation_sweep.py, special=72-bounty-aware).

Harness spec: any entry with a "+aware72" suffix, e.g. prep:params/cand_nlhe.json+aware72.
"""
from .runtime import CALL, FOLD, RAISE

BOUNTY_BB = 10.0     # what the wrapper assumes the bounty is, per opponent


class Aware72:
    def __init__(self, inner, variant, bounty_bb=BOUNTY_BB):
        self.inner, self.v, self.bounty_bb = inner, variant, bounty_bb

    def new_table(self, seat, n):
        self.inner.new_table(seat, n)

    def observe(self, event):
        self.inner.observe(event)

    def _is72o(self, hole):
        v = self.v
        if len(hole) != 2:
            return False
        return sorted(v.ranks[c // v.suits] for c in hole) == ["2", "7"] and hole[0] % v.suits != hole[1] % v.suits

    def act(self, obs):
        a = self.inner.act(obs)
        if not self._is72o(obs.hole) or int(a[0]) != FOLD:
            return a
        n_opp = sum(1 for i, s in enumerate(obs.stacks) if s > 0 and i != obs.seat) or 1
        prize = self.bounty_bb * obs.bb * n_opp
        # preflop: see a flop for up to a quarter of the prize; postflop: stay in for up
        # to a sixth of it (7-2 wins a showdown about 1 time in 6 to 8 heads-up).
        limit = prize * (0.25 if obs.street == 0 else 1 / 6)
        if obs.to_call <= limit:
            if obs.street == 0 and obs.to_call == 0 and obs.min_raise_to:
                return (RAISE, obs.min_raise_to)
            return (CALL, 0)
        return a

import random

from nolimit.engine import DEFAULT_PAYOUTS, SNG
from nolimit.icm import icm
from nolimit.runtime import CALL, RAISE, HeuristicTables, PrepBot
from nolimit.zoo import ZOO


class FixedEval:
    """Evaluator stub: hand value is looked up by the hole tuple."""

    def __init__(self, values):
        self.values = values

    def best(self, hole, board):
        return self.values[hole]


def _sng_for_settle(contrib, values, in_hand=None, button=0):
    agents = [ZOO["timeout"]() for _ in contrib]
    holes = [(i,) for i in range(len(contrib))]
    sng = SNG("nlhe", agents, rng=random.Random(0), evaluator=FixedEval(dict(zip(holes, values))))
    sng.stacks = [0] * len(contrib)
    sng.contrib = list(contrib)
    sng.in_hand = in_hand or [True] * len(contrib)
    sng.hole = holes
    sng.board = [0, 1, 2, 3, 4]
    sng.button = button
    sng._settle([])
    return sng.stacks


def test_side_pots():
    # Short stack has the best hand, mid stack second, big stack worst.
    assert _sng_for_settle([100, 300, 300], [30, 20, 10]) == [300, 400, 0]
    # Big stack wins everything it covers.
    assert _sng_for_settle([100, 300, 300], [10, 20, 30]) == [0, 0, 700]
    # Folded player's chips go to the winner.
    assert _sng_for_settle([50, 200, 200], [99, 20, 10], in_hand=[False, True, True]) == [0, 450, 0]


def test_split_pot_odd_chip_goes_left_of_button():
    # 203-chip pot split two ways: the odd chip goes to seat 1, first left of the button.
    assert _sng_for_settle([101, 101, 1], [10, 10, 0], in_hand=[True, True, False], button=0) == [101, 102, 0]


class Script:
    """open: raises to 100 into an unraised pot. short: jams over a raise. Else check/call."""

    def __init__(self, role):
        self.role, self.seen = role, []

    def new_table(self, seat, n):
        pass

    def observe(self, event):
        pass

    def act(self, obs):
        self.seen.append(obs)
        if self.role == "open" and max(obs.bets) <= obs.bb:
            return (RAISE, 100)
        if self.role == "short" and max(obs.bets) >= 100:
            return (RAISE, obs.max_raise_to)
        return (CALL, 0)


def _short_jam(short_stack, **kw):
    agents = [Script("open"), Script("short"), Script("call")]
    sng = SNG("nlhe", agents, rng=random.Random(1), max_hands=1, **kw)
    sng.stacks = [2000, short_stack, 2000]
    sng.run()
    # The opener's decision after the jam: facing it, with something to call.
    faced = [o for o in agents[0].seen if o.street == 0 and max(o.bets) == short_stack]
    assert faced and faced[0].to_call == short_stack - 100
    return faced[0]


def test_short_all_in_does_not_reopen_raising():
    assert _short_jam(130).min_raise_to == 0                     # +30 is less than a full raise
    assert _short_jam(130, reopen_short=True).min_raise_to > 0   # old simplified rule
    assert _short_jam(400).min_raise_to > 0                      # +300 is a full raise


def test_sng_conserves_chips_and_points():
    T = HeuristicTables("nlhe")
    for g in range(15):
        names = ["tag", "lag", "shover", "nit", "station", "maniac", "random"]
        agents = [PrepBot(T, seed=g, debug=True)] + [ZOO[k](T, seed=g) for k in names]
        sng = SNG("nlhe", agents, rng=random.Random(g))
        pts = sng.run()
        assert sum(sng.stacks) == 8 * 2000
        assert abs(sum(pts) - sum(DEFAULT_PAYOUTS)) < 1e-6
        assert sum(sng.errors) == 0


def test_icm():
    eq = icm([1000, 1000, 1000], [50, 30, 20])
    assert all(abs(e - 100 / 3) < 1e-9 for e in eq)
    eq = icm([5000, 1000, 0], [50, 30, 20])
    assert abs(sum(eq) - 100) < 1e-9 and eq[2] == 20 and eq[0] > eq[1]

"""Optional house rules in nolimit/engine.py: parity with them off, chips conserved and
legal actions with each one on, and the exact mechanics of each rule."""
import random

import pytest

from nolimit.engine import DEFAULT_PAYOUTS, SNG
from nolimit.runtime import CALL, POST, RAISE, HeuristicTables, PrepBot, parse_cards
from nolimit.zoo import ZOO
from tests.legacy_engine import SNG as LegacySNG

T = HeuristicTables("nlhe")
NAMES = ["tag", "lag", "shover", "nit", "station", "maniac", "random"]


class Rec:
    """Wraps an agent and records every observation and action (for parity and legality)."""

    def __init__(self, inner, log):
        self.inner, self.log = inner, log

    def new_table(self, seat, n):
        self.seat = seat
        self.inner.new_table(seat, n)

    def observe(self, ev):
        self.inner.observe(ev)

    def act(self, obs):
        a = self.inner.act(obs)
        self.log.append((obs.hand_no, obs.seat, obs.street, obs.stacks, obs.bets, obs.pot, obs.to_call,
                         obs.min_raise_to, obs.max_raise_to, obs.ante, obs.button, obs.history,
                         int(a[0]), int(a[1])))
        return a


def _agents(g, log, n=8):
    base = [PrepBot(T, seed=g)] + [ZOO[k](T, seed=g) for k in NAMES]
    return [Rec(a, log) for a in (base * 2)[:n]]


def _play(cls, g, n=8, **kw):
    log = []
    sng = cls("nlhe", _agents(g, log, n), rng=random.Random(g), evaluator=T_EV, **kw)
    pts = sng.run()
    return sng, pts, log


T_EV = None


def setup_module(_):
    global T_EV
    from nolimit.runtime import Evaluator
    T_EV = Evaluator(T.v)


@pytest.mark.parametrize("kw", [{}, {"log_hands": True}, {"hands_per_level": 10, "ante": 5},
                                {"reopen_short": True, "max_hands": 120}])
def test_parity_with_rules_off(kw):
    """Every observation and action identical to the pre-rules engine, same seeds."""
    for g in range(6):
        for n in (8, 3):
            new, p1, l1 = _play(SNG, g, n, **kw)
            old_kw = {k: v for k, v in kw.items() if k != "log_hands"}
            old, p2, l2 = _play(LegacySNG, g, n, **old_kw)
            assert l1 == l2
            assert p1 == p2 and new.stacks == old.stacks and new.hands_played == old.hands_played


RULES = [
    {"ante_bb": 0.25}, {"bb_ante": 1.0}, {"straddle": True}, {"bomb_every": 5, "bomb_bb": 2},
    {"run_twice": True}, {"bounty_72": 5}, {"bounty_72": 10, "bounty_72_noshow": True},
    {"max_bet_bb": 10}, {"max_raises": 2}, {"max_bet_bb": 30, "max_raises": 3},
    {"dead_button": True}, {"cap_scoring": "chips", "max_hands": 60}, {"stack_spread": 0.5},
    {"ko_points": 10},
    {"straddle": True, "bb_ante": 1.0, "run_twice": True, "bounty_72": 5, "dead_button": True,
     "bomb_every": 7, "bomb_bb": 1},
]


@pytest.mark.parametrize("kw", RULES)
def test_rule_conserves_chips_points_and_legality(kw):
    for g in range(5):
        for n in (8, 4, 2):
            log = []
            sng = SNG("nlhe", _agents(g, log, n), rng=random.Random(100 + g), log_hands=True, **kw)
            total0 = sum(sng.stacks)
            pts = sng.run()
            assert sum(sng.stacks) == total0
            assert min(sng.stacks) >= 0
            extra = kw.get("ko_points", 0) * sum(sng.kos)
            assert abs(sum(pts) - sum(DEFAULT_PAYOUTS[:n]) - extra) < 1e-6
            assert sum(sng.errors) == 0
            assert sum(sng.bounties) == 0
            for (_h, s, st, stacks, bets, pot, to_call, mn, mx, *_rest, kind, amt) in log:
                assert stacks[s] > 0 and to_call >= 0
                assert mx <= bets[s] + stacks[s]
                if mn:
                    assert max(bets) < mn <= mx
                if "max_bet_bb" in kw:
                    assert mx - max(bets) <= kw["max_bet_bb"] * 600
            # the per-hand log adds up to the chips each seat won
            for s in range(n):
                d = sum(r["delta"] for r in sng.hand_log if r["seat"] == s)
                assert d == sng.stacks[s] - total0 // n or "stack_spread" in kw


class Script:
    """Plays a fixed list of actions in order; then checks/calls."""

    def __init__(self, plan=()):
        self.plan, self.seen = list(plan), []

    def new_table(self, seat, n):
        pass

    def observe(self, ev):
        pass

    def act(self, obs):
        self.seen.append(obs)
        if self.plan:
            a = self.plan.pop(0)
            return (RAISE, obs.max_raise_to) if a == "jam" else a
        return (CALL, 0)


def _one_hand(agents, seed=0, **kw):
    sng = SNG("nlhe", agents, rng=random.Random(seed), max_hands=1, **kw)
    sng.button = len(agents) - 1      # seat 0 is the first button after the move
    sng.run()
    return sng


def test_straddle_posts_acts_last_and_sets_min_raise():
    ag = [Script() for _ in range(5)]
    sng = _one_hand(ag, straddle=True)
    # button 0, sb 1, bb 2, straddle 3: seat 4 acts first and faces 40, min raise to 80
    first = ag[4].seen[0]
    assert first.street == 0 and first.to_call == 40 and first.min_raise_to == 80
    posts = [h for h in first.history if h[2] == POST]
    assert posts == [(1, 0, POST, 10, False), (2, 0, POST, 20, False), (3, 0, POST, 40, False)]
    pre = [(o.seat) for a in ag for o in a.seen if o.street == 0]
    # everyone limps, the straddler gets the option last
    order = [h[0] for h in sng.history if h[1] == 0 and h[2] != POST]
    assert order[-1] == 3 and ag[3].seen[0].to_call == 0 and ag[3].seen[0].min_raise_to == 80
    assert len(pre) == 5


def test_bb_ante_is_dead_money_from_big_blind():
    ag = [Script() for _ in range(4)]
    _one_hand(ag, bb_ante=1.0)
    first = ag[3].seen[0]        # bb is seat 2, UTG seat 3
    assert first.pot == 10 + 20 + 20 and first.to_call == 20 and first.bets[2] == 20
    assert first.stacks[2] == 2000 - 40


def test_bb_ante_posted_before_blind_when_short():
    ag = [Script() for _ in range(3)]
    sng = SNG("nlhe", ag, rng=random.Random(0), max_hands=1, bb_ante=1.0)
    sng.button = 2
    sng.stacks = [2000, 2000, 30]           # bb seat 2 has 30: ante 20 first, then a 10 blind
    sng.run()
    posts = [h for h in sng.history if h[2] == POST]
    assert posts[-1] == (2, 0, POST, 10, True)


def test_ante_bb_scales_with_level():
    ag = [Script() for _ in range(3)]
    sng = _one_hand(ag, ante_bb=0.5)
    o = ag[0].seen[0]
    assert o.ante == 10 and o.pot == 3 * 10 + 30


def test_bomb_pot_skips_preflop():
    ag = [Script() for _ in range(4)]
    sng = _one_hand(ag, bomb_every=1, bomb_bb=3)
    assert all(o.street >= 1 for a in ag for o in a.seen)
    o = ag[1].seen[0]
    assert o.pot == 4 * 60 and o.board and len(o.board) == 3 and max(o.bets) == 0
    assert sum(sng.stacks) == 8000


def test_bomb_pot_every_nth_hand_only():
    ag = [Script() for _ in range(3)]
    sng = SNG("nlhe", ag, rng=random.Random(0), max_hands=6, bomb_every=3, bomb_bb=1)
    sng.run()
    pre_hands = {o.hand_no for a in ag for o in a.seen if o.street == 0}
    assert pre_hands == {0, 1, 3, 4}


class BoardEval:
    """Seat 0 wins when the river card is even, seat 1 when odd."""

    def best(self, hole, board):
        return (1 if board[-1] % 2 == 0 else 0) if hole == (0,) else (0 if board[-1] % 2 == 0 else 1)


def test_run_it_twice_splits_by_runout():
    ag = [Script() for _ in range(2)]
    sng = SNG("nlhe", ag, rng=random.Random(0), evaluator=BoardEval(), run_twice=True)
    sng.stacks = [0, 0]
    sng.contrib = [101, 101]
    sng.in_hand = [True, True]
    sng.hole = [(0,), (1,)]
    sng.board = [10, 11, 12]
    sng.button = 0
    sng._runout_from = 3
    sng._settle([20, 40, 21, 41])     # run 1 river 40 (seat 0), run 2 river 41 (seat 1)
    assert sng.stacks == [102, 100]      # 202-chip pot: the odd chips of each half go to run 1
    assert sng.boards == [[10, 11, 12, 20, 40], [10, 11, 12, 21, 41]]


def test_run_it_twice_in_play_conserves_and_deals_two_boards():
    seen = 0
    for g in range(30):
        ag = [Script(["jam"]), Script([(CALL, 0)]), Script([(CALL, 0)])]
        sng = SNG("nlhe", ag, rng=random.Random(g), max_hands=1, run_twice=True)
        sng.button = 2
        sng.run()
        assert sum(sng.stacks) == 6000
        if hasattr(sng, "boards"):
            seen += 1
            assert sng.boards[0] != sng.boards[1] and len(sng.boards[1]) == 5
    assert seen == 30


def _bounty_sng(hole0, **kw):
    v = T.v
    ag = [Script() for _ in range(4)]
    sng = SNG("nlhe", ag, rng=random.Random(0), **kw)
    sng.bb_amt = 20
    sng.stacks = [1000, 1000, 50, 0]
    sng.hole = [tuple(parse_cards(v, hole0)), tuple(parse_cards(v, "AsKs")), tuple(parse_cards(v, "QhQd")), None]
    return sng


def test_72_bounty_pays_from_every_live_player():
    sng = _bounty_sng("7c2d", bounty_72=5)
    sng._pay_bounties({0: (300, True)}, [0, 1, 2])
    assert sng.stacks == [1000 + 100 + 50, 900, 0, 0]
    assert sng.bounties == [150, -100, -50, 0]


def test_72_bounty_needs_offsuit_and_showdown_unless_noshow():
    sng = _bounty_sng("7d2d", bounty_72=5)
    sng._pay_bounties({0: (300, True)}, [0, 1, 2])
    assert sng.stacks == [1000, 1000, 50, 0]
    sng = _bounty_sng("7c2d", bounty_72=5)
    sng._pay_bounties({0: (300, False)}, [0, 1, 2])
    assert sng.stacks == [1000, 1000, 50, 0]
    sng = _bounty_sng("2h7c", bounty_72=5, bounty_72_noshow=True)
    sng._pay_bounties({0: (300, False)}, [0, 1, 2])
    assert sng.stacks == [1150, 900, 0, 0]


def test_max_raises_and_bet_cap():
    ag = [Script(["jam", "jam"]), Script(["jam", "jam"]), Script(["jam", "jam"])]
    sng = SNG("nlhe", ag, rng=random.Random(0), max_hands=1, max_bet_bb=5, max_raises=2)
    sng.button = 2
    sng.run()
    raises = [h for h in sng.history if h[2] == RAISE and h[1] == 0]
    assert len(raises) == 2
    assert raises[0][3] == 20 + 100 and raises[1][3] == 120 + 100
    assert all(o.min_raise_to == 0 for a in ag for o in a.seen if o.street == 0 and o.hand_no == 0
               and sum(1 for h in o.history if h[2] == RAISE and h[1] == 0) >= 2)


def test_dead_button_after_small_blind_busts():
    ag = [Script() for _ in range(4)]
    sng = SNG("nlhe", ag, rng=random.Random(0), max_hands=1, dead_button=True)
    sng.button = 3
    sng.run()          # hand 0: button 0, sb 1, bb 2
    assert (sng._prev_sb, sng._prev_bb) == (1, 2)
    sng.stacks[2] += sng.stacks[1]
    sng.stacks[1] = 0  # last hand's small blind busts
    sng.hand_no = 1
    sng._play_hand([0, 2, 3])
    posts = [h for h in sng.history if h[2] == POST]
    # bb moves to seat 3, sb on seat 2, button on seat 1 (empty): a dead button
    assert sng.button == 1 and [p[0] for p in posts] == [2, 3]
    assert sum(sng.stacks) == 8000


def test_dead_small_blind_is_skipped():
    ag = [Script() for _ in range(4)]
    sng = SNG("nlhe", ag, rng=random.Random(0), max_hands=1, dead_button=True)
    sng.button = 3
    sng.run()          # button 0, sb 1, bb 2
    sng.stacks[0] += sng.stacks[2]
    sng.stacks[2] = 0  # last hand's big blind busts: next hand has a dead small blind
    sng.hand_no = 1
    sng._play_hand([0, 1, 3])
    posts = [h for h in sng.history if h[2] == POST]
    assert [p[0] for p in posts] == [3] and sng.button == 1


def test_ko_points_go_to_buster():
    for g in range(20):
        sng = SNG("nlhe", [Script(["jam"] * 400), Script(["jam"] * 400)], rng=random.Random(g), ko_points=7)
        sng.button = 1
        pts = sng.run()
        winner = 0 if sng.stacks[0] else 1
        assert sng.kos[winner] == 1 and pts[winner] == 100 + 7 and pts[1 - winner] == 65


def test_chip_scoring_at_cap():
    ag = [Script() for _ in range(3)]
    sng = SNG("nlhe", ag, rng=random.Random(0), max_hands=0, cap_scoring="chips")
    sng.stacks = [3000, 2000, 1000]
    pts = sng.run()
    assert pts == [210 * 3 / 6, 210 * 2 / 6, 210 * 1 / 6]


def test_stack_spread_is_repeatable():
    a = SNG("nlhe", [Script() for _ in range(8)], rng=random.Random(5), stack_spread=0.5).stacks
    b = SNG("nlhe", [Script() for _ in range(8)], rng=random.Random(5), stack_spread=0.5).stacks
    assert a == b and len(set(a)) > 1 and all(1000 <= x <= 3000 for x in a)


def test_hand_log_positions_and_classes():
    log = []
    sng = SNG("nlhe", _agents(1, log), rng=random.Random(1), log_hands=True, max_hands=30)
    sng.run()
    h0 = [r for r in sng.hand_log if r["hand_no"] == 0]
    assert sorted(r["pos"] for r in h0) == sorted(SNG.position_names(8))
    assert all(len(r["hole"]) in (2, 3) for r in sng.hand_log)
    assert SNG.position_names(2) == ("BTN", "BB")

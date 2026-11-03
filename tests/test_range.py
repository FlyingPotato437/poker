"""Range-equity model: grid lookups, slice equity, range reading, and the EV engine's legality."""
import os
import random

import pytest

from nolimit import runtime
from nolimit.engine import SNG
from nolimit.runtime import CALL, POST, RAISE, RANGE_X, RANGE_Y, PrepBot, Tables, parse_cards
from nolimit.zoo import HELD_OUT, ZOO

BUNDLE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bundles", "nlhe_rng.nlb")
need_bundle = pytest.mark.skipif(not os.path.exists(BUNDLE), reason="bundles/nlhe_rng.nlb not built")


def test_grid_pos():
    logs = [runtime.math.log(g) for g in RANGE_X]
    assert runtime._grid_pos(logs, 1.0) == (0, 0.0)
    assert runtime._grid_pos(logs, 2.0) == (0, 0.0)
    i, t = runtime._grid_pos(logs, RANGE_X[3])
    assert (i, t) in ((3, 0.0), (2, 1.0))
    i, t = runtime._grid_pos(logs, 0.01)
    assert i == len(RANGE_X) - 1 and t == 0.0


class FakeTables(Tables):
    """Tables with a synthetic curve: equity = 0.3 + 0.2 x - 0.1 (1 - y)."""

    def __init__(self):
        self._ry = [runtime.math.log(g) for g in RANGE_Y]
        self._rx = [runtime.math.log(g) for g in RANGE_X]


def curve():
    return [0.3 + 0.2 * x - 0.1 * (1 - y) for y in RANGE_Y for x in RANGE_X]


def test_range_equity_hits_grid_and_interpolates():
    T, c = FakeTables(), curve()
    for y in RANGE_Y:
        for x in RANGE_X:
            assert abs(T.range_equity(c, y, x) - (0.3 + 0.2 * x - 0.1 * (1 - y))) < 1e-9
    mid = T.range_equity(c, 1.0, 0.6)
    assert T.range_equity(c, 1.0, 0.5) < mid < T.range_equity(c, 1.0, 0.7)


def test_interval_equity_decomposes():
    T, c = FakeTables(), curve()
    # The full range is the weighted sum of its top part and the rest.
    top, rest = T.interval_equity(c, 1.0, 0.0, 0.5), T.interval_equity(c, 1.0, 0.5, 1.0)
    assert abs(0.5 * top + 0.5 * rest - T.range_equity(c, 1.0, 1.0)) < 1e-9
    assert rest > top    # we do better against the bottom of their range


def _hist(*acts):
    return ((1, 0, POST, 10, False), (2, 0, POST, 20, False)) + tuple(acts)


def test_range_reading_narrows():
    T = FakeTables()
    T.has_rng = False
    bot = PrepBot.__new__(PrepBot)
    bot.p = dict(runtime.DEFAULT_PARAMS)
    bot.stats = [runtime.SeatStats() for _ in range(8)]
    raiser = bot._pre_y(3, _hist((3, 0, RAISE, 60, False)))
    limper = bot._pre_y(3, _hist((3, 0, CALL, 20, False)))
    bb_check = bot._pre_y(2, _hist((3, 0, CALL, 20, False), (2, 0, CALL, 20, False)))
    assert raiser < limper < bb_check == 1.0
    flop = _hist((3, 0, CALL, 20, False), (2, 0, CALL, 20, False))
    a, b_bet, ag = bot._post_slice(2, flop + ((2, 1, RAISE, 30, False),), 1)
    assert (a, ag) == (0.0, True) and b_bet < 0.6
    a, b, ag = bot._post_slice(2, flop + ((2, 1, CALL, 0, False),), 1)
    assert a > 0.0 and b == 1.0 and not ag
    a2, b2, _ = bot._post_slice(2, flop + ((2, 1, RAISE, 30, False), (3, 1, CALL, 30, False)), 2)
    assert a2 == 0.0 and b_bet < b2 < 1.0     # a new card loosens the read


@need_bundle
def test_range_model_outputs():
    with open(BUNDLE, "rb") as fh:
        T = Tables(fh.read())
    v = T.v
    rs = random.Random(3)
    for _ in range(20):
        cards = rs.sample(range(v.D), 2 + rs.choice((3, 4, 5)))
        c = T.post_curve(cards[:2], cards[2:])
        assert len(c) == len(RANGE_Y) * len(RANGE_X)
        assert all(0.0 <= x <= 1.0 for x in c)
    hole, board = parse_cards(v, "AhKd"), parse_cards(v, "As7c2d")
    c = T.post_curve(hole, board)
    assert T.range_equity(c, 1.0, 1.0) > T.range_equity(c, 1.0, 0.05) + 0.2
    assert T.range_equity(c, 1.0, 0.25) > T.range_equity(c, 0.08, 0.25)


@need_bundle
@pytest.mark.parametrize("mode", [{}, {"ev_post": 0.0, "rng_mix": 0.7}])
def test_engines_play_legal_poker(mode):
    with open(BUNDLE, "rb") as fh:
        T = Tables(fh.read())
    for g in range(3):
        agents = [PrepBot(T, mode, seed=g, debug=True), PrepBot(T, mode, seed=g + 9, debug=True)]
        agents += [ZOO[k](T, seed=g) for k in ("tag", "jammer", "station") + HELD_OUT[:3]]
        sng = SNG(T.v, agents, rng=random.Random(g))
        pts = sng.run()
        assert sum(sng.errors) == 0
        assert abs(sum(pts) - sum(sng.payouts)) < 1e-6


_PARITY = r"""
import json, random, sys
sys.path.insert(0, {root!r})
from nolimit.runtime import Tables, np
T = Tables(open({bundle!r}, "rb").read())
if np is not None:
    T.select_nets("small")
rs = random.Random(5)
out = []
for _ in range(30):
    c = rs.sample(range(T.v.D), 2 + rs.choice((3, 4, 5)))
    out.append(list(T.post_equity(c[:2], c[2:])) + list(T.post_curve(c[:2], c[2:])))
print(json.dumps(out))
"""


@need_bundle
def test_pure_python_models_match_numpy():
    """The no-numpy path (sparse rows, column sums, lazily computed range cells) must give
    the same numbers as numpy running the same small models."""
    import json
    import subprocess
    import sys
    pytest.importorskip("numpy")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    code = _PARITY.format(root=root, bundle=BUNDLE)
    runs = []
    for env in ({}, {"NOLIMIT_NO_NUMPY": "1"}):
        res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True,
                             env={**os.environ, **env})
        runs.append(json.loads(res.stdout))
    diff = max(abs(x - y) for a, b in zip(*runs) for x, y in zip(a, b))
    assert diff < 1e-5


@need_bundle
def test_deadline_falls_back_to_passive_actions():
    with open(BUNDLE, "rb") as fh:
        T = Tables(fh.read())
    class Recorder(PrepBot):
        def act(self, obs):
            a = PrepBot.act(self, obs)
            if obs.street > 0:
                self.post.append(a[0])
            return a

    old = PrepBot.deadline
    PrepBot.deadline = 0.0      # every decision is "late": no raise sizes get tried postflop
    try:
        hero = Recorder(T, seed=1, debug=True)
        hero.post = []
        agents = [hero] + [ZOO[k](T, seed=1) for k in ("tag", "lag", "station", "mc", "cbet", "balanced", "nit")]
        sng = SNG(T.v, agents, rng=random.Random(1))
        sng.run()
        assert sum(sng.errors) == 0 and hero.deadline_hits > 0
        assert hero.post and RAISE not in hero.post
    finally:
        PrepBot.deadline = old


@need_bundle
def test_model_size_override(monkeypatch):
    pytest.importorskip("numpy")
    with open(BUNDLE, "rb") as fh:
        T = Tables(fh.read())
    monkeypatch.setenv("NOLIMIT_NETS", "small")
    assert runtime.calibrate_nets(T) == "small" and T.rng_kind == "rngsmall"
    monkeypatch.setenv("NOLIMIT_NETS", "big")
    assert runtime.calibrate_nets(T) == "big" and T.rng_kind == "rng"

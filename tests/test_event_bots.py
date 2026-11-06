"""Event-field designs (nolimit/rivals.py EVENT_BOTS): every action they return is legal as
sent, SNGs with them run without errors and conserve chips, and each one decides fast."""
import os
import random
import sys
import time

import pytest

from nolimit.engine import SNG
from nolimit.rivals import EVENT_BOTS, EVENT_WEIGHTS, RIVALS, event_fields
from nolimit.runtime import HeuristicTables, PrepBot, Tables
from nolimit.zoo import ZOO

from test_llm_bugs import Checked

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUNDLE = os.path.join(ROOT, "bundles", "nlhe_rng.nlb")
_T = {}


def _tables(kind):
    if kind not in _T:
        if kind == "bundle":
            if not os.path.exists(BUNDLE):
                pytest.skip("bundles/nlhe_rng.nlb not built")
            _T[kind] = Tables(open(BUNDLE, "rb").read())
        else:
            _T[kind] = HeuristicTables("nlhe")
    return _T[kind]


@pytest.mark.parametrize("kind", ["bundle", "heuristic"])
@pytest.mark.parametrize("name", sorted(EVENT_BOTS))
def test_event_bot_legal(name, kind, monkeypatch):
    monkeypatch.setattr(PrepBot, "deadline", 1e9)
    T = _tables(kind)
    n_sngs = 3 if kind == "bundle" else 1
    for g in range(n_sngs):
        bad = []
        if g == 2:      # a full table of the design: 8 instances with distinct thresholds
            agents = [Checked(EVENT_BOTS[name](T, seed=100 * g + i), bad) for i in range(8)]
        else:
            others = [EVENT_BOTS[o] for o in sorted(EVENT_BOTS) if o != name]
            rng = random.Random(g)
            agents = [Checked(EVENT_BOTS[name](T, seed=100 * g + i), bad) for i in range(3)]
            agents += [Checked(rng.choice(others)(T, seed=50 + g), bad), PrepBot(T, seed=g),
                       ZOO["tag"](T, seed=g), ZOO["station"](T, seed=g), ZOO["maniac"](T, seed=g)]
        random.Random(g).shuffle(agents)
        sng = SNG(T.v, agents, rng=random.Random(1000 + g), hands_per_level=10 if g % 2 else 25)
        sng.run()
        assert sum(sng.errors) == 0, (name, sng.errors)
        assert bad == [], bad[:5]
        assert sum(sng.stacks) == 8 * 2000


@pytest.mark.parametrize("name", sorted(EVENT_BOTS))
def test_event_bot_fast(name):
    """Mean decision time under 0.05 ms (best of 3 SNGs; the limit scales with machine load,
    measured by the evaluator's speed against its unloaded ~0.003 ms per hand)."""
    T = _tables("bundle")
    rng = random.Random(3)
    hands = [rng.sample(range(T.v.D), 7) for _ in range(2000)]
    t0 = time.perf_counter()
    for h in hands:
        T.ev.best(h[:2], h[2:])
    load = max(1.0, (time.perf_counter() - t0) / len(hands) * 1000 / 0.003)
    means = []
    for g in range(3):
        agents = [EVENT_BOTS[name](T, seed=10 * g + i) for i in range(6)]
        agents += [ZOO["tag"](T, seed=1), ZOO["station"](T, seed=2)]
        sng = SNG(T.v, agents, rng=random.Random(7 + g), hands_per_level=25)
        sng.run()
        cnt = sum(sng.timing[s].count for s in range(6))
        tot = sum(sng.timing[s].total for s in range(6))
        assert cnt > 0
        means.append(tot / cnt)
    assert min(means) < 0.05 * load, (name, means, load)


def test_event_fields_registered():
    f = event_fields()
    assert set(f["event"]) == set(EVENT_BOTS) == set(EVENT_WEIGHTS)
    assert f["event"]["ev_codex_tag"] == 3 and f["event"]["ev_gunslinger"] == 0.5
    assert f["event+prep"]["prep:params/rival_prep.json"] == 1.2
    assert set(EVENT_BOTS) <= set(RIVALS)
    from nolimit.harness import parse_entry
    for name in EVENT_BOTS:
        assert parse_entry(name)["kind"] == "zoo:" + name
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from final_check import final_fields
    ff = final_fields("nlhe", {})
    assert ff["event"] == f["event"] and ff["event+prep"] == f["event+prep"]


class _O:
    def __init__(self, hole, board=()):
        self.hole, self.board = hole, board


def test_per_instance_noise_and_tenbug():
    T = HeuristicTables("nlhe")
    for name, cls in EVENT_BOTS.items():
        a, b = cls(T, seed=1), cls(T, seed=2)
        assert a.k and a.k != b.k, name
    bugged = [EVENT_BOTS["ev_codex_tag"](T, seed=s) for s in range(200)]
    n = sum(b.tenbug for b in bugged)
    assert 30 <= n <= 90, n
    b = next(x for x in bugged if x.tenbug)
    v = T.v
    ten = v.ranks.index("T") * v.suits
    ace = v.ranks.index("A") * v.suits + 1
    assert b._val[ten] == 2
    assert b._hole(_O((ten, ace)))[0] == v.ranks.index("2") * v.suits
    clean = next(x for x in bugged if not x.tenbug)
    assert clean._hole(_O((ten, ace))) == (ten, ace)

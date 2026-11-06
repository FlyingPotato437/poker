"""GitHub-bot designs (nolimit/rivals.py GITHUB_BOTS): every action they return is legal as
sent, SNGs with them run without errors and conserve chips, and each one decides fast."""
import os
import random
import time

import pytest

from nolimit.engine import SNG
from nolimit.rivals import GITHUB_BOTS, RIVALS, github_fields
from nolimit.runtime import HeuristicTables, PrepBot, Tables
from nolimit.zoo import ZOO

from test_llm_bugs import Checked

BUNDLE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bundles", "nlhe_rng.nlb")
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
@pytest.mark.parametrize("name", sorted(GITHUB_BOTS))
def test_github_bot_legal(name, kind, monkeypatch):
    monkeypatch.setattr(PrepBot, "deadline", 1e9)
    T = _tables(kind)
    n_sngs = 3 if kind == "bundle" else 1
    for g in range(n_sngs):
        bad = []
        if g == 2:      # a full table of the design: 8 instances with distinct thresholds
            agents = [Checked(GITHUB_BOTS[name](T, seed=100 * g + i), bad) for i in range(8)]
        else:
            others = [GITHUB_BOTS[o] for o in sorted(GITHUB_BOTS) if o != name]
            rng = random.Random(g)
            agents = [Checked(GITHUB_BOTS[name](T, seed=100 * g + i), bad) for i in range(3)]
            agents += [Checked(rng.choice(others)(T, seed=50 + g), bad), PrepBot(T, seed=g),
                       ZOO["tag"](T, seed=g), ZOO["station"](T, seed=g), ZOO["maniac"](T, seed=g)]
        random.Random(g).shuffle(agents)
        sng = SNG(T.v, agents, rng=random.Random(1000 + g), hands_per_level=10 if g % 2 else 25)
        sng.run()
        assert sum(sng.errors) == 0, (name, sng.errors)
        assert bad == [], bad[:5]
        assert sum(sng.stacks) == 8 * 2000


@pytest.mark.parametrize("name", sorted(GITHUB_BOTS))
def test_github_bot_fast(name):
    """Mean decision time under 0.05 ms (best of 3 SNGs; the limit scales up when the machine
    is loaded, measured by the evaluator's speed against its unloaded ~0.002 ms per hand)."""
    T = _tables("bundle")
    rng = random.Random(3)
    hands = [rng.sample(range(T.v.D), 7) for _ in range(2000)]
    t0 = time.perf_counter()
    for h in hands:
        T.ev.best(h[:2], h[2:])
    load = max(1.0, (time.perf_counter() - t0) / len(hands) * 1000 / 0.003)
    means = []
    for g in range(3):
        agents = [GITHUB_BOTS[name](T, seed=10 * g + i) for i in range(6)]
        agents += [ZOO["tag"](T, seed=1), ZOO["station"](T, seed=2)]
        sng = SNG(T.v, agents, rng=random.Random(7 + g), hands_per_level=25)
        sng.run()
        cnt = sum(sng.timing[s].count for s in range(6))
        tot = sum(sng.timing[s].total for s in range(6))
        assert cnt > 0
        means.append(tot / cnt)
    assert min(means) < 0.05 * load, (name, means, load)


def test_github_fields_registered():
    f = github_fields()
    assert set(f["github"]) == set(GITHUB_BOTS)
    assert "prep:params/rival_prep.json" in f["github+prep"]
    assert set(GITHUB_BOTS) <= set(RIVALS)
    from nolimit.harness import parse_entry
    for name in GITHUB_BOTS:
        assert parse_entry(name)["kind"] == "zoo:" + name


def test_per_instance_noise_and_tenbug():
    T = HeuristicTables("nlhe")
    for name, cls in GITHUB_BOTS.items():
        a, b = cls(T, seed=1), cls(T, seed=2)
        assert a.k and a.k != b.k, name
    for name in ("gh_catscore", "gh_tiers", "gh_opus"):
        bugged = sum(GITHUB_BOTS[name](T, seed=s).tenbug for s in range(200))
        assert 30 <= bugged <= 90, (name, bugged)
    assert not any(GITHUB_BOTS["gh_flash"](T, seed=s).tenbug for s in range(50))

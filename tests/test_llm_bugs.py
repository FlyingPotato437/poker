"""LLM-bug designs (nolimit/rivals.py LLM_BUGS): every action they return is legal as sent,
and SNGs with them run without errors, on the real bundle and on heuristic tables."""
import os
import random

import pytest

from nolimit.engine import SNG
from nolimit.rivals import LLM_BUGS, llm_fields
from nolimit.runtime import CALL, FOLD, RAISE, HeuristicTables, PrepBot, Tables
from nolimit.zoo import ZOO

BUNDLE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bundles", "nlhe_rng.nlb")


class Checked:
    """Wraps a bot and records any action that the host would have to correct."""

    def __init__(self, bot, bad):
        self.bot, self.bad = bot, bad

    def new_table(self, seat, n):
        self.bot.new_table(seat, n)

    def observe(self, event):
        self.bot.observe(event)

    def act(self, obs):
        a = self.bot.act(obs)
        kind, amt = a
        ok = isinstance(kind, int) and isinstance(amt, int) and kind in (FOLD, CALL, RAISE)
        if ok and kind == FOLD:
            ok = obs.to_call > 0
        if ok and kind == RAISE:
            ok = obs.min_raise_to > 0 and obs.min_raise_to <= amt <= obs.max_raise_to
        if not ok:
            self.bad.append((type(self.bot).__name__, a, obs.to_call, obs.min_raise_to, obs.max_raise_to))
        return a


def _tables(kind):
    if kind == "bundle":
        if not os.path.exists(BUNDLE):
            pytest.skip("bundles/nlhe_rng.nlb not built")
        return Tables(open(BUNDLE, "rb").read())
    return HeuristicTables("nlhe")


@pytest.mark.parametrize("kind", ["bundle", "heuristic"])
@pytest.mark.parametrize("name", sorted(LLM_BUGS))
def test_llm_bug_legal(name, kind, monkeypatch):
    monkeypatch.setattr(PrepBot, "deadline", 1e9)
    T = _tables(kind)
    n_sngs = 3 if kind == "bundle" else 1
    for g in range(n_sngs):
        bad = []
        # 4 copies of the design (distinct seeds, so distinct thresholds) + a mixed table.
        agents = [Checked(LLM_BUGS[name](T, seed=100 * g + i), bad) for i in range(4)]
        agents += [PrepBot(T, seed=g), ZOO["tag"](T, seed=g), ZOO["station"](T, seed=g),
                   ZOO["maniac"](T, seed=g)]
        random.Random(g).shuffle(agents)
        sng = SNG(T.v, agents, rng=random.Random(1000 + g), hands_per_level=10 if g % 2 else 25)
        sng.run()
        assert sum(sng.errors) == 0, (name, sng.errors)
        assert bad == [], bad[:5]
        assert sum(sng.stacks) == 8 * 2000


def test_llm_fields_registered():
    f = llm_fields()
    assert set(f["llm-bugs"]) == set(LLM_BUGS)
    assert "prep:params/rival_prep.json" in f["llm-bugs+prep"]
    from nolimit.harness import parse_entry
    for name in LLM_BUGS:
        assert parse_entry(name)["kind"] == "zoo:" + name


def test_per_instance_noise():
    T = HeuristicTables("nlhe")
    for name, cls in LLM_BUGS.items():
        a, b = cls(T, seed=1), cls(T, seed=2)
        assert a.k and a.k != b.k, name

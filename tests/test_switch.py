"""Per-table param arms: off without "alt", same play when the arm == base, switches on the rule."""
import os
import random

import pytest

from nolimit.engine import SNG
from nolimit.runtime import PrepBot, Tables
from nolimit.zoo import ZOO

BUNDLE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bundles", "nlhe_rng.nlb")
need_bundle = pytest.mark.skipif(not os.path.exists(BUNDLE), reason="bundles/nlhe_rng.nlb not built")
FEATS = ("vpip", "pfr", "agg", "fold_to_bet", "never")


def rule(const, params, from_hand=10):
    return {"from_hand": from_hand, "mu": dict.fromkeys(FEATS, 0.2), "sd": dict.fromkeys(FEATS, 0.1),
            "arms": [{"params": params, "beta": dict(dict.fromkeys(FEATS, 0.0), const=const)}]}


def _play(T, params, g, hero_out):
    hero = PrepBot(T, params, seed=g, debug=True)
    agents = [hero] + [ZOO[k](T, seed=g + i) for i, k in enumerate(("tag", "station", "nit", "lag", "shover", "timeout", "maniac"))]
    sng = SNG(T.v, agents, rng=random.Random(g))
    pts = sng.run()
    hero_out.append(hero)
    assert sum(sng.errors) == 0
    return pts


@need_bundle
def test_switch(monkeypatch):
    monkeypatch.setattr(PrepBot, "deadline", 1e9)       # timing-free, so runs are repeatable
    T = Tables(open(BUNDLE, "rb").read())
    base = {"bluff_freq": 0.2}
    alt = {"bluff_freq": 0.5, "open_base": 0.2}
    for g in range(3):
        bots = []
        plain = _play(T, base, g, bots)
        assert bots[-1]._rule is None and "alt" not in bots[-1].p and bots[-1].view is None
        same = _play(T, dict(base, alt=rule(1.0, {})), g, bots)
        assert same == plain                                # arm identical to base: identical game
        view = bots[-1].view
        assert view is not None and set(view) == set(FEATS) and bots[-1].arm == 0
        _play(T, dict(base, alt=rule(1.0, alt)), g, bots)
        assert bots[-1].p["bluff_freq"] == 0.5 and bots[-1].p["open_base"] == 0.2
        assert bots[-1].view == view                        # same history up to the switch point
        _play(T, dict(base, alt=rule(-1.0, alt)), g, bots)
        assert bots[-1].p["bluff_freq"] == 0.2 and bots[-1].arm == -1 and bots[-1].view == view

"""Strong-seat ("whale") mode: fold-to-3-bet counts, off by default, and the flag/boost logic."""
import json
import os
import random

import pytest

from nolimit.engine import SNG
from nolimit.rivals import RIVALS, whale_fields
from nolimit.runtime import CALL, EXPLOIT_LEVELS, FOLD, POST, RAISE, PrepBot, SeatStats, Tables, ingest_history

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUNDLE = os.path.join(ROOT, "bundles", "nlhe_rng.nlb")
need_bundle = pytest.mark.skipif(not os.path.exists(BUNDLE), reason="bundles/nlhe_rng.nlb not built")


def test_fold_to_3bet_counts():
    st = [SeatStats() for _ in range(4)]
    hist = ((1, 0, POST, 10, False), (2, 0, POST, 20, False),
            (3, 0, RAISE, 50, False),            # open
            (0, 0, RAISE, 150, False),           # 3-bet
            (1, 0, FOLD, 10, False), (2, 0, FOLD, 20, False),
            (3, 0, FOLD, 50, False))             # opener folds to the 3-bet
    ingest_history(st, hist)
    assert (st[3].f3o, st[3].f3f) == (1, 1)
    assert (st[0].f3o, st[2].f3o) == (0, 0)
    hist2 = ((1, 0, POST, 10, False), (2, 0, POST, 20, False), (3, 0, RAISE, 50, False),
             (0, 0, RAISE, 150, False), (1, 0, FOLD, 10, False), (2, 0, FOLD, 20, False),
             (3, 0, CALL, 150, False))
    ingest_history(st, hist2)
    assert (st[3].f3o, st[3].f3f) == (2, 1)


def test_whale_fields():
    f = whale_fields()
    assert {"whale1", "whale-mirror", "whale2", "whale-br", "whale-event"} <= set(f)
    mix, fixed = f["whale2"]
    from nolimit.harness import ZOO
    assert fixed and all(k in ZOO or k.startswith("prep:") for k in mix)
    assert "strong_eq" in RIVALS


def _play(T, params, g):
    hero = PrepBot(T, params, seed=g, debug=True)
    opp = ("strong_eq", "rv_tag", "gh_opus", "phase", "rv_mc", "rv_gto", "rv_icm")
    agents = [hero] + [RIVALS[k](T, seed=g + i) for i, k in enumerate(opp)]
    sng = SNG(T.v, agents, rng=random.Random(g))
    pts = sng.run()
    assert sum(sng.errors) == 0
    return pts, hero


@need_bundle
def test_strong_mode(monkeypatch):
    monkeypatch.setattr(PrepBot, "deadline", 1e9)
    T = Tables(open(BUNDLE, "rb").read())
    cand = json.load(open(os.path.join(ROOT, "params", "cand_nlhe.json")))
    off = json.loads(json.dumps(cand))
    off["exploit"]["strong"] = {"n": 10 ** 9, "boost": 0.0}    # never flags anyone: same game
    loud = json.loads(json.dumps(cand))
    loud["exploit"]["strong"] = {"n": 5, "boost": 0.5, "lam0": 1, "steal": 0.5, "pf_tax": 0.05,
                                 "call_tax": 0.1, "cont": 1.3, "f3_k": 0.5, "f3_thr": 0.3, "f3_n": 1}
    for g in range(2):
        base, _ = _play(T, cand, g)
        same, _ = _play(T, off, g)
        assert same == base
        _pts, bot = _play(T, loud, g)
        assert len(bot._ex_levels) == EXPLOIT_LEVELS + 1
        assert any(bot._strong(s) for s in range(1, 8))     # n 5, no other bounds: everyone seen flags

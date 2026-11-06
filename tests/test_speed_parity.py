"""Speed-ups that must not change any value: each fast path vs the code it replaced."""
import math
import operator
import random

import pytest

from nolimit import runtime as R
from nolimit.runtime import PRESETS, Evaluator, Variant, _midpoints, _nearest


def _variants():
    out = dict(PRESETS)
    # Must-use-2 variants beyond the presets: 3 hole cards (kit2-style) and a short-deck order.
    out["hu2_3hole"] = Variant("hu2_3hole", n_hole=3, hole_used=2)
    out["hu2_short"] = Variant("hu2_short", ranks="6789TJQKA", n_hole=4, hole_used=2,
                               category_order=PRESETS["shortdeck"].category_order)
    out["hu1_3hole"] = Variant("hu1_3hole", n_hole=3, hole_used=1)
    out["hu3_4hole"] = Variant("hu3_4hole", n_hole=4, hole_used=3)
    return out


@pytest.mark.parametrize("name", sorted(_variants()))
def test_evaluator_best_matches_per_combo_loop(name):
    v = _variants()[name]
    ev = Evaluator(v)
    ref = Evaluator(v)
    ref._split = None                       # the per-combo loop
    if v.hole_used == 2 and name in PRESETS:
        assert ev._split == 2               # PLO presets take the fast path
    rng = random.Random(hash(name) & 0xFFFF)
    flushy = 0
    for i in range(3000):
        n_board = (0, 3, 4, 5, 5)[i % 5] if v.n_board >= 5 else rng.randrange(v.n_board + 1)
        n_board = min(n_board, v.n_board)
        if i % 3 == 0 and v.n_hole + n_board >= 3:
            # Suit-heavy deals so flush branches are exercised often.
            su = rng.randrange(v.suits)
            pool = [c for c in range(v.D) if c % v.suits == su]
            k = min(len(pool), rng.randrange(3, v.n_hole + n_board + 1))
            cards = rng.sample(pool, k)
            rest = [c for c in range(v.D) if c not in cards]
            cards += rng.sample(rest, v.n_hole + n_board - k)
            rng.shuffle(cards)
        else:
            cards = rng.sample(range(v.D), v.n_hole + n_board)
        hole, board = cards[:v.n_hole], cards[v.n_hole:]
        got, want = ev.best(hole, board), ref.best(hole, board)
        assert got == want, (name, hole, board, got, want)
        if want >= 0 and ev.category(want) in (R.FLUSH, R.STRAIGHT_FLUSH):
            flushy += 1
    if v.hole_used is not None:
        assert flushy > 20


def test_nearest_share_matches_min_scan():
    rng = random.Random(5)
    grids = [[0.02, 0.04, 0.06, 0.08, 0.1, 0.125, 0.15, 0.175, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45,
              0.5, 0.6, 0.7, 0.8, 0.9]]
    grids += [sorted(set(round(rng.random(), rng.choice((2, 3, 17))) for _ in range(rng.randrange(2, 25))))
              for _ in range(40)]
    for g in grids:
        if len(g) < 2:
            continue
        mids = _midpoints(g)
        xs = [rng.uniform(-0.5, 1.5) for _ in range(3000)]
        for m in mids + g:
            xs += [m, math.nextafter(m, -1), math.nextafter(m, 2)]
        xs += [float("nan"), 1e300, -1e300, 0.0, 1.0]
        for x in xs:
            assert _nearest(g, mids, x) == min(range(len(g)), key=lambda k: abs(g[k] - x)), (g, x)


def test_sumprod_branch_matches(monkeypatch):
    """The math.sumprod branch (3.12+) computes the same dot products as the fallback."""
    v = PRESETS["nlhe"]
    rng = random.Random(2)
    n_in, h1, h2, n_out = R.feature_dim(v), 9, 7, 5

    def mat(r, c):
        return [[rng.uniform(-1, 1) for _ in range(c)] for _ in range(r)]
    w1 = mat(n_in, h1)
    w2c = [list(col) for col in zip(*mat(h1, h2))]
    w3c = [list(col) for col in zip(*mat(h2, n_out))]
    net = [w1, [0.1] * h1, w2c, [0.0] * h2, w3c, [0.05] * n_out]
    ev = Evaluator(v)
    feats = []
    for _ in range(50):
        c = rng.sample(range(v.D), 2 + 3 + rng.randrange(3))
        feats.append(R.postflop_features(v, ev, R.straight_windows(v), c[:2], c[2:]))

    def run():
        out = []
        for f in feats:
            hid = R.Tables._hidden(f, net)
            lazy = R._LazyCurve(hid, net[4], net[5])
            out.append((hid, list(lazy)))
        return out
    monkeypatch.setattr(R, "_sumprod", None)
    base = run()
    monkeypatch.setattr(R, "_sumprod", lambda a, b: sum(map(operator.mul, a, b)))
    assert run() == base

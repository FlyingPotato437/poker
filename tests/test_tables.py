"""Build a tiny NLHE bundle on CPU and check the runtime reads it back correctly."""
import numpy as np
import pytest

torch = pytest.importorskip("torch")

from gpu import pushfold  # noqa: E402
from gpu.build_tables import class_equities, enumerate_classes, pct_from_equity  # noqa: E402
from gpu.tensor_eval import TorchEval  # noqa: E402
from nolimit.bundle_io import read_bundle_np, write_bundle  # noqa: E402
from nolimit.runtime import PRESETS, Tables, parse_cards  # noqa: E402


@pytest.fixture(scope="module")
def mini(tmp_path_factory):
    v = PRESETS["nlhe"]
    torch.manual_seed(0)
    te = TorchEval(v, torch.device("cpu"))
    combo_class, reps, weight = enumerate_classes(v)
    eq1, _ = class_equities(te, reps, 1, 400, 100_000)
    pct = pct_from_equity(eq1[:, 0], weight)
    eq, eq_range = class_equities(te, reps, 3, 800, 100_000, combo_class, pct, 20)
    stacks = (2, 10, 20)
    shove, call = pushfold.solve_charts(pct, weight, eq_range, [50, 30, 20, 0, 0, 0, 0, 0],
                                        stacks=stacks, nmax=4, iters=200, workers=2)
    meta = {"variant": v.to_dict(), "k_max": 3, "range_buckets": 20, "pf_stacks": list(stacks), "pf_nmax": 4}
    arrays = {"combo_class": combo_class.astype(np.int16), "class_weight": weight,
              "class_pct": pct.astype(np.float32), "class_eq": eq.astype(np.float32),
              "eq_range": eq_range.astype(np.float32), "pf_shove": shove, "pf_call": call}
    path = tmp_path_factory.mktemp("b") / "mini.nlb"
    write_bundle(str(path), meta, arrays)
    return path, arrays


def test_classes():
    combo_class, reps, weight = enumerate_classes(PRESETS["nlhe"])
    assert len(reps) == 169 and weight.sum() == 1326 and sorted(set(weight)) == [4, 6, 12]
    assert len(enumerate_classes(PRESETS["plo4"])[1]) == 16432


def test_roundtrip_and_lookups(mini):
    path, arrays = mini
    meta, back = read_bundle_np(str(path))
    for k, a in arrays.items():
        assert np.array_equal(back[k], a)
    T = Tables(path.read_bytes())
    v = T.v
    aa = T.hole_class(parse_cards(v, "AsAh"))
    assert aa == T.hole_class(parse_cards(v, "AdAc"))
    trash = T.hole_class(parse_cards(v, "7c2d"))
    assert T.pct(aa) < 0.01 and T.pct(trash) > 0.9
    assert 0.80 < T.eq(aa, 1) < 0.90
    assert T.eq(aa, 1) > T.eq(aa, 3)
    assert T.eq_vs_range(aa, 0.05) < T.eq_vs_range(aa, 1.0)


def test_pushfold_sanity(mini):
    path, _ = mini
    T = Tables(path.read_bytes())
    # Shorter stacks shove wider; later positions shove wider; heads-up at 2bb shoves nearly all.
    assert T.shove_threshold(4, 0, 2) > T.shove_threshold(4, 0, 20)
    assert T.shove_threshold(4, 2, 10) > T.shove_threshold(4, 0, 10)
    assert T.shove_threshold(2, 0, 2) > 0.8


def test_bubble_factors():
    bf = pushfold.bubble_factors([50, 30, 20, 0], nmax=4, workers=2, log=lambda *_: None)
    sh = pushfold.BF_SHARES.index
    assert abs(bf[0, sh(0.5), sh(0.5), -1] - 1.0) < 1e-6           # heads-up ICM is linear
    eq = bf[2, sh(0.25), sh(0.25)]
    assert 1.0 <= eq[0] < eq[-1]                                     # bigger risk, bigger premium
    assert bf[2, sh(0.4), sh(0.15), -1] < bf[2, sh(0.15), sh(0.4), -1]   # covering stack calls wider

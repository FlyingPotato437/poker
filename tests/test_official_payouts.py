import math
from pathlib import Path

import pytest

from nolimit.icm import icm
from nolimit.official_payouts import DecisionTables, PayoutBasis, equivalent_payouts, validate_payouts
from nolimit.runtime import HeuristicTables, read_bundle


def test_validation_and_positive_affine_equivalence():
    assert validate_payouts([50, 30, 20], 8) == (50, 30, 20, 0, 0, 0, 0, 0)
    assert equivalent_payouts([50, 30, 20], [105, 65, 45], 3)
    assert not equivalent_payouts([50, 30, 20], [100, 65, 45], 3)
    for p in ([0, 1], [float("nan")], [-1], []):
        with pytest.raises(ValueError):
            validate_payouts(p, 8)


def test_changed_payouts_or_ante_disable_chart_only():
    t = HeuristicTables("nlhe")
    t.has_pushfold = True
    t.meta = {"payouts": [50, 30, 20, 0, 0, 0, 0, 0], "pf_ante_bb": 0}
    t.shove_threshold = lambda *a: 0.234
    t.call_threshold = lambda *a: 0.123
    view = DecisionTables(t, object(), [50, 30, 20], 8)
    assert view.shove_threshold(8, 0, 10) == 0.234
    assert DecisionTables(t, object(), [100, 0, 0], 8).shove_threshold(8, 0, 10) is None
    assert DecisionTables(t, object(), [50, 30, 20], 8, 0.1).call_threshold(8, 0, 1, 10) is None
    assert t.meta["payouts"][0] == 50
    assert view.has_bf


@pytest.fixture(scope="module")
def basis():
    path = Path(__file__).resolve().parents[1] / "build/official/icm_basis.nlb"
    if not path.exists():
        pytest.skip("Run scripts/official.py basis for the generated-basis checks")
    return PayoutBasis(*read_bundle(path.read_bytes()))


@pytest.mark.parametrize("payouts", [[50, 30, 20, 0, 0, 0, 0, 0, 0, 0],
                                      [100, 0, 0, 0, 0, 0, 0, 0, 0, 0],
                                      [10] * 10, list(range(10, 0, -1)),
                                      [91, 89, 17, 9, 4, 2, 0, 0, 0, 0]])
def test_basis_matches_independent_exact_icm_on_grid(basis, payouts):
    for n in (2, 3, 5, 8, 10):
        for h, other in ((0.125, 0.125), (0.04, 0.6), (0.45, 0.08)):
            x = min(other, 0.98 - h) if n > 2 else 1 - h
            tail = [(1 - h - x) / (n - 2)] * (n - 2) if n > 2 else []
            now = icm([h, x] + tail, payouts[:n])[0]
            for frac in (0.1, 0.3, 1.0):
                r = frac * min(h, x)
                gain = icm([h + r, x - r] + tail, payouts[:n])[0] - now
                loss = now - icm([h - r, x + r] + tail, payouts[:n])[0]
                expected = min(max(loss / gain, 0.8), 8) if gain > 1e-10 else 1
                assert basis.factor(payouts, n, h, other, frac) == pytest.approx(expected, abs=1e-5)


def test_winner_take_all_linear_chip_utility(basis):
    for n in range(2, 11):
        for frac in (0.1, 0.23, 0.7, 1):
            assert basis.factor([100] + [0] * 9, n, 0.125, 0.2, frac) == pytest.approx(1, abs=1e-6)

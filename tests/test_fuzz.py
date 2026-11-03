"""Short version of scripts/fuzz.py: real games under extreme setups + degraded observations."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import fuzz  # noqa: E402

from nolimit.runtime import PRESETS, HeuristicTables  # noqa: E402


@pytest.mark.parametrize("vname", sorted(PRESETS))
def test_fuzz_heuristic(vname):
    T = HeuristicTables(vname)
    worst = []
    fuzz.layer1(T, 8, 1, worst)
    fuzz.layer2(T, 1500, 2, worst)

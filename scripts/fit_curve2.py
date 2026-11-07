"""Fit CURVE_TH (see scripts/hyb_tables.py) on random deals; writes bench/fallback2/curve_th.json."""
import json, math, random, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from nolimit.runtime import load_tables, RANGE_X, RANGE_Y
from fallback import spec_bot as S
import hyb_tables as HT
kind = sys.argv[1] if len(sys.argv) > 1 else "bucket"
n = int(sys.argv[2]) if len(sys.argv) > 2 else 6000
T = load_tables("bundles/nlhe_rng.nlb")
rng = random.Random(7)
th = {}
for street, nb in ((1, 3), (2, 4), (3, 5)):
    X, Y = [], []
    for _ in range(n):
        cards = rng.sample(range(52), 2 + nb); hole, board = cards[:2], cards[2:]
        curve = T.post_curve(hole, board)
        k = S.post_bucket(hole, board); L = S.logit(S.post_equity1(hole, board, street))
        for iy, y in enumerate(RANGE_Y):
            for ix, x in enumerate(RANGE_X):
                c = min(max(curve[iy * 9 + ix], 1e-3), 1 - 1e-3)
                X.append(HT.curve_feats(k, L, math.log(x), math.log(y), kind)); Y.append(math.log(c / (1 - c)) - L)
    t, *_ = np.linalg.lstsq(np.array(X), np.array(Y), rcond=None)
    th[street] = [round(float(v), 3) for v in t]
    print(street, len(t))
json.dump({"kind": kind, "th": th}, open("bench/fallback2/curve_th.json", "w"), indent=1)

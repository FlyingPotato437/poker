"""Fit a compact formula for the range-equity curve (the range MLP's 5x9 grid) from the
spec bot's hand features, so a from-scratch bot can run the EV postflop engine.

z(y, x) = logit(e1) + sum_j theta[street][j] * phi_j,  phi from (L=logit e1, lx=ln x, ly=ln y).
"""
import math, random, sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from nolimit.runtime import load_tables, RANGE_X, RANGE_Y
from fallback import spec_bot as S

def phis(L, lx, ly):
    return [1.0, lx, ly, lx * ly, L * lx, L * ly, L * lx * ly, lx * lx, L * lx * lx, ly * ly]

def main(n=6000, seed=1, use_true=False):
    T = load_tables("bundles/nlhe_rng.nlb")
    rng = random.Random(seed)
    out = {}
    for street, nb in ((1, 3), (2, 4), (3, 5)):
        X, Y, base = [], [], []
        for _ in range(n):
            cards = rng.sample(range(52), 2 + nb)
            hole, board = cards[:2], cards[2:]
            curve = T.post_curve(hole, board)
            e1 = T.post_equity(hole, board)[0] if use_true else S.post_equity1(hole, board, street)
            L = S.logit(e1)
            for iy, y in enumerate(RANGE_Y):
                for ix, x in enumerate(RANGE_X):
                    c = min(max(curve[iy * len(RANGE_X) + ix], 1e-3), 1 - 1e-3)
                    X.append(phis(L, math.log(x), math.log(y)))
                    Y.append(math.log(c / (1 - c)) - L)
                    base.append((c, L))
        X, Y = np.array(X), np.array(Y)
        th, *_ = np.linalg.lstsq(X, Y, rcond=None)
        pred = 1 / (1 + np.exp(-(X @ th + np.array([b[1] for b in base]))))
        truth = np.array([b[0] for b in base])
        e0 = 1 / (1 + np.exp(-np.array([b[1] for b in base])))
        print(f"street {street}: mae {np.abs(pred-truth).mean():.4f}  (x=y=1 cells only: "
              f"{np.abs(pred-truth)[::45].mean():.4f}; no-fit e1 mae {np.abs(e0-truth).mean():.4f})")
        out[street] = [round(float(t), 3) for t in th]
    print(json.dumps(out))
    return out

if __name__ == "__main__":
    main(use_true="--true" in sys.argv)

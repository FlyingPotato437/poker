"""Range-conditioned postflop equity: adds a second MLP (rng_*) to an existing bundle.

    python -m gpu.range_eq --bundle bundles/nlhe.nlb             # GPU profile
    python -m gpu.range_eq --bundle bundles/day.nlb --laptop     # day-of, offline (CPU; --device mps opts in)

The model predicts hero's heads-up equity against an opponent holding the top x (by
postflop strength) of their top y (by preflop strength) hands, on the grid
RANGE_Y x RANGE_X, flattened y-major. PrepBot reads ranges off opponents' actions:
a preflop raise narrows y, a postflop bet narrows x, a check keeps the bottom part.

The opponent's postflop ranking uses the bundle's own vs-random MLP. That is exactly
how an equity-threshold bot decides to bet or call, and close enough for the rest.
Labels: for each (hole, board) and each y, K opponent hands drawn from the top-y combos,
each played out R times; the label for x averages the top ceil(x * K) by ranking.
"""
import argparse
import itertools
import os
import time

import numpy as np
import torch

from gpu.build_tables import log, train_mlp
from gpu.tensor_eval import TorchEval, pick_device, run_with_fallback, set_threads
from nolimit.bundle_io import read_bundle_np, write_bundle
from nolimit.runtime import RANGE_X, RANGE_Y, Variant

GPU = dict(samples=300_000, k=64, rollouts=4, val_samples=3000, val_k=256, val_rollouts=24,
           chunk=600_000, epochs=14, hidden="1024,512", small_hidden="64,32")
LAPTOP = dict(samples=50_000, k=32, rollouts=3, val_samples=500, val_k=128, val_rollouts=8,
              chunk=200_000, epochs=12, hidden="1024,512", small_hidden="64,32")
QUICK = dict(samples=4000, k=16, rollouts=2, val_samples=200, val_k=64, val_rollouts=4,
             chunk=100_000, epochs=6, hidden="64,32", small_hidden="64,32")


def sorted_combos(v, combo_class, class_pct, dev):
    """Every hole-card combo, strongest preflop first, as a (M, n_hole) tensor."""
    h, D = v.n_hole, v.D
    M = len(combo_class)
    combos = np.fromiter(itertools.chain.from_iterable(itertools.combinations(range(D), h)),
                         dtype=np.int64, count=M * h).reshape(M, h)
    B = np.zeros((D + 1, h + 1), dtype=np.int64)
    for n in range(D + 1):
        B[n, 0] = 1
        for r in range(1, min(n, h) + 1):
            B[n, r] = B[n - 1, r - 1] + (B[n - 1, r] if r <= n - 1 else 0)
    colex = sum(B[combos[:, i], i + 1] for i in range(h))
    pct = class_pct[combo_class[colex]]
    return torch.as_tensor(combos[np.argsort(pct, kind="stable")], device=dev)


def torch_mlp(arrs, dev):
    w = [torch.as_tensor(arrs["mlp_" + k], device=dev) for k in ("w1", "b1", "w2", "b2", "w3", "b3")]

    def f(x):
        h = torch.relu(x @ w[0] + w[1])
        h = torch.relu(h @ w[2] + w[3])
        return torch.sigmoid(h @ w[4] + w[5])
    return f


@torch.no_grad()
def range_dataset(te, mlp1, combos, n, board_len, k, rollouts, chunk):
    v, dev = te.v, te.dev
    h, nb = v.n_hole, v.n_board
    if board_len == nb:          # river: nothing to roll out, spend the budget on more hands
        k, rollouts = k * rollouts, 1
    M = combos.shape[0]
    NY, NX = len(RANGE_Y), len(RANGE_X)
    xs = torch.tensor(RANGE_X, device=dev)
    X, L = [], []
    per = max(1, chunk // (k * rollouts))
    for s0 in range(0, n, per):
        b = min(per, n - s0)
        cards = te.draw(torch.empty(b, 0, dtype=torch.long, device=dev), h + board_len)
        hole, board = cards[:, :h], cards[:, h:]
        X.append(te.features(hole, board).cpu())
        known = cards
        lab = torch.empty(b, NY, NX, device=dev)
        for yi, y in enumerate(RANGE_Y):
            top = max(1, int(round(y * M)))
            vill = combos[torch.randint(0, top, (b, k), device=dev)]              # (b, k, h)
            valid = ~(vill.unsqueeze(-1) == known[:, None, None, :]).any(-1).any(-1)
            vf = vill.reshape(b * k, h)
            vb = board.repeat_interleave(k, 0)
            score = mlp1(te.features(vf, vb))[:, 0].view(b, k)
            score = torch.where(valid, score, torch.full_like(score, -1.0))     # invalid sort last
            hr = hole.repeat_interleave(k * rollouts, 0)
            vr = vf.repeat_interleave(rollouts, 0)
            br = vb.repeat_interleave(rollouts, 0)
            if board_len < nb:
                full = torch.cat([br, te.draw(torch.cat([hr, vr, br], 1), nb - board_len)], 1)
            else:
                full = br
            w = te.shares(hr, full, [vr])[:, 0].view(b, k, rollouts).mean(2)
            order = score.argsort(1, descending=True)
            ws = (w * valid).gather(1, order).cumsum(1)
            nv = valid.sum(1).clamp(min=1)
            take = torch.ceil(xs[None, :] * nv[:, None]).long().clamp(min=1)         # (b, NX)
            lab[:, yi, :] = ws.gather(1, take - 1) / take
        L.append(lab.reshape(b, NY * NX).cpu())
    return torch.cat(X), torch.cat(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bundle", required=True, help="bundle with mlp_*; rng_* is added in place")
    ap.add_argument("--out", help="write here instead of overwriting --bundle")
    ap.add_argument("--device", default="auto", help="auto|cpu|mps|cuda (see gpu.build_tables --help)")
    ap.add_argument("--threads", type=int, help="torch CPU threads (default $NOLIMIT_THREADS or all)")
    ap.add_argument("--laptop", action="store_true")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--work", help="data cache dir (default: <bundle dir>/work_<variant>)")
    ap.add_argument("--reuse", action="store_true", help="reuse cached range_data.npz")
    ap.add_argument("--seed", type=int, default=0)
    for key, val in GPU.items():
        ap.add_argument("--" + key.replace("_", "-"), type=type(val), default=None)
    args = ap.parse_args()
    cfg = dict(QUICK if args.quick else LAPTOP if args.laptop else GPU)
    for key in GPU:
        if getattr(args, key) is not None:
            cfg[key] = getattr(args, key)

    meta, arrs = read_bundle_np(args.bundle)
    if "mlp_w1" not in arrs:
        raise SystemExit("bundle has no postflop MLP; build it first (gpu.build_tables)")
    v = Variant.from_dict(meta["variant"])
    log(f"torch threads {set_threads(args.threads)}")
    finished = set()
    run_with_fallback(lambda d: build(args, cfg, meta, arrs, v, d, finished),
                      pick_device(args.device, log=log), log=log)


def build(args, cfg, meta, arrs, v, dev, finished):
    """Everything after argument parsing. finished holds "data" once this process saved
    range_data.npz, so an out-of-memory fallback to CPU only redoes the training."""
    torch.manual_seed(args.seed)
    te = TorchEval(v, dev)
    work = args.work or os.path.join(os.path.dirname(os.path.abspath(args.bundle)), f"work_{v.name}")
    os.makedirs(work, exist_ok=True)
    data_path = os.path.join(work, "range_data.npz")
    log(f"range equity for {v.name}: grid {len(RANGE_Y)}x{len(RANGE_X)}, device {dev}, cfg {cfg}")

    if (args.reuse or "data" in finished) and os.path.exists(data_path):
        d = np.load(data_path)
        X, Yl, Xv, Yv = (torch.from_numpy(d[key]) for key in ("X", "Y", "Xv", "Yv"))
        log(f"reusing {len(X):,} cached samples")
    else:
        combos = sorted_combos(v, arrs["combo_class"].astype(np.int64), arrs["class_pct"], dev)
        mlp1 = torch_mlp(arrs, dev)
        parts = {"X": [], "Y": [], "Xv": [], "Yv": []}
        cum = 0
        for n_cards in v.streets:
            cum += n_cards
            if not te.combo_idx(v.n_hole, cum).numel():
                continue
            t0 = time.time()
            x, y = range_dataset(te, mlp1, combos, cfg["samples"], cum, cfg["k"], cfg["rollouts"], cfg["chunk"])
            xv, yv = range_dataset(te, mlp1, combos, cfg["val_samples"], cum, cfg["val_k"],
                                   cfg["val_rollouts"], cfg["chunk"])
            for key, val in zip(("X", "Y", "Xv", "Yv"), (x, y, xv, yv)):
                parts[key].append(val)
            log(f"board {cum}: {len(x):,} samples ({time.time() - t0:.1f}s), "
                f"mean label {y.mean():.3f}, top-5% of top-8% {y[:, -1].mean():.3f}")
        X, Yl, Xv, Yv = (torch.cat(parts[key]) for key in ("X", "Y", "Xv", "Yv"))
        np.savez(data_path, X=X.numpy(), Y=Yl.numpy(), Xv=Xv.numpy(), Yv=Yv.numpy())
        finished.add("data")

    out = {}
    hidden = [int(x) for x in cfg["hidden"].split(",")]
    w, mae = train_mlp(X, Yl, Xv, Yv, hidden, cfg["epochs"], dev)
    out.update({"rng_" + key[4:]: a for key, a in w.items()})
    meta["rng_mae"] = float(np.mean(mae))
    meta["rng_hidden"] = hidden
    log(f"range MLP {cfg['hidden']}: validation MAE {np.mean(mae):.4f} "
        f"(y=1,x=1 {mae[0]:.4f}; y=1,x=.05 {mae[len(RANGE_X) - 1]:.4f}; y=.08,x=.05 {mae[-1]:.4f})")
    if cfg["small_hidden"] != cfg["hidden"]:
        small = [int(x) for x in cfg["small_hidden"].split(",")]
        ws, mae_s = train_mlp(X, Yl, Xv, Yv, small, cfg["epochs"], dev)
        out.update({"rngsmall_" + key[4:]: a for key, a in ws.items()})
        meta["rng_mae_small"] = float(np.mean(mae_s))
        log(f"range MLP {cfg['small_hidden']}: validation MAE {np.mean(mae_s):.4f}")
    arrs = {key: a for key, a in arrs.items() if not key.startswith(("rng_", "rngsmall_"))}
    arrs.update(out)
    meta["rng_y"], meta["rng_x"] = list(RANGE_Y), list(RANGE_X)
    path = args.out or args.bundle
    size = write_bundle(path, meta, arrs)
    log(f"wrote {path} ({size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()

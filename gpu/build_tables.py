"""Build the lookup-table bundle for one variant. Heavy parts run on GPU.

    python -m gpu.build_tables --variant nlhe --out bundles/nlhe.nlb             # full run (CUDA)
    python -m gpu.build_tables --variant day.json --out bundles/day.nlb --laptop # day-of, offline (~5 min M3 Pro)
    python -m gpu.build_tables --variant plo4 --out bundles/plo4.nlb --quick     # ~1 min smoke test

Stages (each checkpointed in --work, rerun with --reuse to skip finished ones):
  classes   suit-isomorphic hole-card classes and the combo -> class map
  preflop   per-class equity vs 1..7 random opponents, HU equity vs top-y ranges
  postflop  Monte Carlo labels + MLP that predicts equity vs 1/2/3 opponents
  pushfold  ICM push/fold charts for the points table (--payouts)
"""
import argparse
import itertools
import json
import os
import time

import numpy as np
import torch

from gpu import pushfold
from gpu.tensor_eval import TorchEval, pick_device
from nolimit.bundle_io import write_bundle
from nolimit.engine import DEFAULT_PAYOUTS
from nolimit.runtime import PRESETS, Variant, feature_dim

FULL = dict(rows_budget=6e7, pct_frac=0.1, eq_cap=200_000, chunk=400_000, range_buckets=40,
            post_samples=400_000, post_rollouts=64, val_samples=4000, val_rollouts=1000,
            epochs=14, hidden="1024,512", small_hidden="64,32")
QUICK = dict(rows_budget=1.5e6, pct_frac=0.2, eq_cap=4000, chunk=120_000, range_buckets=40,
             post_samples=30_000, post_rollouts=16, val_samples=600, val_rollouts=200,
             epochs=8, hidden="64,32", small_hidden="64,32")
# Day-of on the laptop GPU with no network: NLHE measured at 4.5 min on an M3 Pro (MPS).
# Width keeps paying even at this data size (NLHE MAE 0.027 at 128x64 -> 0.015 at 1024x512)
# and costs ~10 s more training on MPS; numpy inference stays ~15 us.
LAPTOP = dict(rows_budget=1e7, pct_frac=0.1, eq_cap=40_000, chunk=200_000, range_buckets=40,
              post_samples=150_000, post_rollouts=32, val_samples=1500, val_rollouts=400,
              epochs=12, hidden="1024,512", small_hidden="64,32")


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def load_variant(arg):
    if arg in PRESETS:
        return PRESETS[arg]
    with open(arg) as fh:
        return Variant.from_dict(json.load(fh))


# ---------------------------------------------------------------------------
def enumerate_classes(v):
    D, h, S = v.D, v.n_hole, v.suits
    M = 1
    for i in range(h):
        M = M * (D - i) // (i + 1)
    combos = np.fromiter(itertools.chain.from_iterable(itertools.combinations(range(D), h)),
                         dtype=np.int64, count=M * h).reshape(M, h)
    B = np.zeros((D + 1, h + 1), dtype=np.int64)
    for n in range(D + 1):
        B[n, 0] = 1
        for r in range(1, min(n, h) + 1):
            B[n, r] = B[n - 1, r - 1] + (B[n - 1, r] if r <= n - 1 else 0)
    colex = sum(B[combos[:, i], i + 1] for i in range(h))
    ranks, suits = combos // S, combos % S
    powers = D ** np.arange(h - 1, -1, -1, dtype=np.int64)
    canon = None
    for perm in itertools.permutations(range(S)):
        mapped = ranks * S + np.asarray(perm)[suits]
        mapped.sort(axis=1)
        key = mapped @ powers
        canon = key if canon is None else np.minimum(canon, key)
    _, first, inverse, counts = np.unique(canon, return_index=True, return_inverse=True, return_counts=True)
    combo_class = np.empty(M, dtype=np.int32)
    combo_class[colex] = inverse
    return combo_class, combos[first], counts.astype(np.int32)


def class_equities(te, reps, n_opp, rollouts, chunk, combo_class=None, class_pct=None, Y=40):
    """Equity per class vs 1..n_opp random opponents; optionally HU sums by opponent pct bucket."""
    v, dev = te.v, te.dev
    C, h, nb = reps.shape[0], v.n_hole, v.n_board
    reps_t = torch.as_tensor(reps, device=dev)
    eq_sum = torch.zeros(C, n_opp, device=dev)
    want_range = class_pct is not None
    if want_range:
        cc_t = torch.as_tensor(combo_class.astype(np.int64), device=dev)
        pct_t = torch.as_tensor(class_pct, dtype=torch.float32, device=dev)
        r_sum = torch.zeros(C * Y, device=dev)
        r_cnt = torch.zeros(C * Y, device=dev)
    total = C * rollouts
    t0 = time.time()
    for start in range(0, total, chunk):
        ids = torch.arange(start, min(total, start + chunk), device=dev) // rollouts
        hero = reps_t[ids]
        drawn = te.draw(hero, n_opp * h + nb)
        opps = [drawn[:, k * h:(k + 1) * h] for k in range(n_opp)]
        board = drawn[:, n_opp * h:]
        sh = te.shares(hero, board, opps)
        eq_sum.index_add_(0, ids, sh)
        if want_range:
            p = pct_t[cc_t[te.combo_index(opps[0])]]
            flat = ids * Y + (p * Y).long().clamp(max=Y - 1)
            r_sum.index_add_(0, flat, sh[:, 0].contiguous())
            r_cnt.index_add_(0, flat, torch.ones_like(sh[:, 0]))
    eq = eq_sum.cpu().double().numpy() / rollouts
    log(f"  {total:,} rollouts x {n_opp} opp in {time.time() - t0:.1f}s")
    if not want_range:
        return eq, None
    rs = r_sum.cpu().double().numpy().reshape(C, Y).cumsum(1)
    rc = r_cnt.cpu().double().numpy().reshape(C, Y).cumsum(1)
    eq_range = np.where(rc > 0, rs / np.maximum(rc, 1), np.nan)
    # Buckets no sample reached (card removal, tiny top ranges): back-fill from wider ranges.
    for j in range(Y - 2, -1, -1):
        bad = np.isnan(eq_range[:, j])
        eq_range[bad, j] = eq_range[bad, j + 1]
    return eq, eq_range


def pct_from_equity(eq1, w):
    order = np.argsort(-eq1, kind="stable")
    cw = np.cumsum(w[order].astype(float))
    pct = np.empty(len(eq1))
    pct[order] = (cw - w[order] / 2.0) / cw[-1]
    return pct


# ---------------------------------------------------------------------------
def postflop_dataset(te, n, rollouts, k_opp, chunk, board_len):
    v, dev = te.v, te.dev
    h, nb = v.n_hole, v.n_board
    X, Y = [], []
    per = max(1, chunk // rollouts)
    for s0 in range(0, n, per):
        b = min(per, n - s0)
        cards = te.draw(torch.empty(b, 0, dtype=torch.long, device=dev), h + board_len)
        hole, board = cards[:, :h], cards[:, h:]
        X.append(te.features(hole, board).cpu())
        hero = hole.repeat_interleave(rollouts, 0)
        kb = board.repeat_interleave(rollouts, 0)
        drawn = te.draw(torch.cat([hero, kb], 1), k_opp * h + nb - board_len)
        opps = [drawn[:, k * h:(k + 1) * h] for k in range(k_opp)]
        full = torch.cat([kb, drawn[:, k_opp * h:]], 1)
        Y.append(te.shares(hero, full, opps).view(b, rollouts, k_opp).mean(1).cpu())
    X, Y = torch.cat(X), torch.cat(Y)
    if Y.shape[1] < 3:
        Y = torch.cat([Y] + [Y[:, -1:]] * (3 - Y.shape[1]), 1)
    return X, Y


def train_mlp(X, Y, Xv, Yv, hidden, epochs, device, lr=3e-3):
    torch.manual_seed(0)
    batch = int(max(256, min(8192, len(X) // 300)))   # keep >= ~300 steps per epoch
    dims = [X.shape[1]] + hidden
    layers = []
    for a, b in zip(dims[:-1], dims[1:]):
        layers += [torch.nn.Linear(a, b), torch.nn.ReLU()]
    layers.append(torch.nn.Linear(dims[-1], Y.shape[1]))
    model = torch.nn.Sequential(*layers).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    steps = epochs * ((len(X) + batch - 1) // batch)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=lr, total_steps=steps)
    X, Y = X.to(device), Y.to(device)
    for ep in range(epochs):
        perm = torch.randperm(len(X), device=device)
        tot = 0.0
        for i in range(0, len(X), batch):
            idx = perm[i:i + batch]
            loss = torch.nn.functional.mse_loss(torch.sigmoid(model(X[idx])), Y[idx])
            opt.zero_grad()
            loss.backward()
            opt.step()
            sched.step()
            tot += loss.item() * len(idx)
        if ep == epochs - 1 or ep % 4 == 0:
            log(f"  epoch {ep + 1}/{epochs} train mse {tot / len(X):.5f}")
    with torch.no_grad():
        pred = torch.sigmoid(model(Xv.to(device))).cpu()
    mae = (pred - Yv).abs().mean(0).tolist()
    lin = [m for m in model if isinstance(m, torch.nn.Linear)]
    weights = {}
    for i, m in enumerate(lin, 1):
        weights[f"mlp_w{i}"] = m.weight.detach().T.contiguous().cpu().numpy().astype(np.float32)
        weights[f"mlp_b{i}"] = m.bias.detach().cpu().numpy().astype(np.float32)
    return weights, mae


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--variant", required=True, help="preset name or variant JSON file")
    ap.add_argument("--out", required=True)
    ap.add_argument("--device", default="auto")
    ap.add_argument("--quick", action="store_true", help="small sample sizes for a ~1 min smoke test")
    ap.add_argument("--laptop", action="store_true", help="day-of offline profile sized for a laptop GPU")
    ap.add_argument("--work", help="checkpoint dir (default: <out dir>/work_<variant>)")
    ap.add_argument("--reuse", action="store_true", help="reuse finished stages from --work")
    ap.add_argument("--skip", default="", help="comma list of stages to skip: postflop,pushfold")
    ap.add_argument("--payouts", default=",".join(str(x) for x in DEFAULT_PAYOUTS))
    ap.add_argument("--seed", type=int, default=0)
    for k, val in FULL.items():
        ap.add_argument("--" + k.replace("_", "-"), type=type(val), default=None)
    args = ap.parse_args()
    cfg = dict(QUICK if args.quick else LAPTOP if args.laptop else FULL)
    for k in FULL:
        if getattr(args, k) is not None:
            cfg[k] = getattr(args, k)
    skip = set(filter(None, args.skip.split(",")))

    v = load_variant(args.variant)
    dev = pick_device(args.device)
    torch.manual_seed(args.seed)
    te = TorchEval(v, dev)
    work = args.work or os.path.join(os.path.dirname(os.path.abspath(args.out)), f"work_{v.name}")
    os.makedirs(work, exist_ok=True)
    k_max = v.max_opponents()
    Y = cfg["range_buckets"]
    log(f"variant {v.name}: deck {v.D}, hole {v.n_hole}, streets {v.streets}, device {dev}")

    def stage(name):
        path = os.path.join(work, name + ".npz")
        return path, (args.reuse and os.path.exists(path))

    path, done = stage("classes")
    if done:
        z = np.load(path)
        combo_class, reps, weight = z["combo_class"], z["reps"], z["weight"]
    else:
        t0 = time.time()
        combo_class, reps, weight = enumerate_classes(v)
        np.savez(path, combo_class=combo_class, reps=reps, weight=weight)
        log(f"classes: {len(reps):,} classes over {len(combo_class):,} combos ({time.time() - t0:.1f}s)")
    C = len(reps)

    path, done = stage("preflop")
    if done:
        z = np.load(path)
        class_pct, class_eq, eq_range = z["class_pct"], z["class_eq"], z["eq_range"]
    else:
        budget = cfg["rows_budget"]
        r_pct = int(max(100, min(cfg["eq_cap"], budget * cfg["pct_frac"] // C)))
        r_eq = int(max(200, min(cfg["eq_cap"], budget // C)))
        log(f"preflop pass 1 (strength order): {r_pct} rollouts/class")
        eq1, _ = class_equities(te, reps, 1, r_pct, cfg["chunk"])
        class_pct = pct_from_equity(eq1[:, 0], weight)
        log(f"preflop pass 2 (equities + ranges): {r_eq} rollouts/class, {k_max} opponents")
        class_eq, eq_range = class_equities(te, reps, k_max, r_eq, cfg["chunk"],
                                            combo_class, class_pct, Y)
        np.savez(path, class_pct=class_pct, class_eq=class_eq, eq_range=eq_range)
        best = np.argsort(class_pct)[:5]
        log("  strongest: " + ", ".join(
            "".join(v.ranks[c // v.suits] + "cdhs"[c % v.suits] for c in reps[i]) +
            f" ({class_eq[i, 0]:.3f})" for i in best))

    arrays = {
        "combo_class": combo_class.astype(np.int16 if C < 32767 else np.int32),
        "class_weight": weight.astype(np.int32),
        "class_pct": class_pct.astype(np.float32),
        "class_eq": class_eq.astype(np.float32),
        "eq_range": eq_range.astype(np.float32),
    }
    meta = {"variant": v.to_dict(), "k_max": k_max, "range_buckets": Y, "n_classes": C,
            "feature_dim": feature_dim(v), "built": time.strftime("%Y-%m-%d %H:%M:%S"),
            "config": cfg, "device": str(dev)}

    if "postflop" not in skip:
        path, done = stage("postflop")
        if done:
            z = np.load(path, allow_pickle=True)
            weights = {k: z[k] for k in z.files if k.startswith(("mlp_", "mlpsmall_"))}
            mae = z["mae"].tolist()
            mae_s = z["mae_small"].tolist() if "mae_small" in z.files else None
        else:
            # The Monte Carlo data is the slow part: cache it so retraining (other
            # --hidden sizes, more --epochs) only needs --reuse after deleting postflop.npz.
            data_path, have_data = stage("postflop_data")
            if have_data:
                d = np.load(data_path)
                X, Yl, xv, yv = (torch.from_numpy(d[k]) for k in ("X", "Y", "Xv", "Yv"))
                log(f"postflop data: reusing {len(X):,} cached samples")
            else:
                k_opp = min(3, k_max)
                Xs, Ys, Xv, Yv = [], [], [], []
                cum = 0
                for n_cards in v.streets:
                    cum += n_cards
                    if not te.combo_idx(v.n_hole, cum).numel():
                        continue
                    t0 = time.time()
                    X, Yl = postflop_dataset(te, cfg["post_samples"], cfg["post_rollouts"], k_opp, cfg["chunk"], cum)
                    xv, yv = postflop_dataset(te, cfg["val_samples"], cfg["val_rollouts"], k_opp, cfg["chunk"], cum)
                    Xs.append(X), Ys.append(Yl), Xv.append(xv), Yv.append(yv)
                    log(f"postflop data, board {cum}: {len(X):,} samples ({time.time() - t0:.1f}s)")
                X, Yl, xv, yv = torch.cat(Xs), torch.cat(Ys), torch.cat(Xv), torch.cat(Yv)
                np.savez(data_path, X=X.numpy(), Y=Yl.numpy(), Xv=xv.numpy(), Yv=yv.numpy())
            hidden = [int(x) for x in cfg["hidden"].split(",")]
            weights, mae = train_mlp(X, Yl, xv, yv, hidden, cfg["epochs"], dev)
            mae_s = None
            if cfg["small_hidden"] != cfg["hidden"]:
                # The runtime uses this one when numpy is missing (pure Python must stay fast).
                small = [int(x) for x in cfg["small_hidden"].split(",")]
                ws, mae_s = train_mlp(X, Yl, xv, yv, small, cfg["epochs"], dev)
                weights.update({"mlpsmall_" + k[4:]: a for k, a in ws.items()})
                log(f"small MLP {cfg['small_hidden']} validation MAE: {', '.join(f'{m:.4f}' for m in mae_s)}")
            extra = {} if mae_s is None else {"mae_small": np.array(mae_s)}
            np.savez(path, mae=np.array(mae), **extra, **weights)
        log(f"postflop MLP validation MAE vs 1/2/3 opp: {', '.join(f'{m:.4f}' for m in mae)}")
        arrays.update(weights)
        meta["mlp_mae"] = mae
        meta["mlp_hidden"] = [int(weights["mlp_w1"].shape[1]), int(weights["mlp_w2"].shape[1])]
        if mae_s is not None:
            meta["mlp_mae_small"] = mae_s

    if "pushfold" not in skip:
        payouts = [float(x) for x in args.payouts.split(",")]
        shove, call = pushfold.solve_charts(class_pct, weight, eq_range, payouts, log=log)
        arrays["pf_shove"], arrays["pf_call"] = shove, call
        arrays["icm_bf"] = pushfold.bubble_factors(payouts, log=log)
        meta.update(pf_stacks=list(pushfold.DEFAULT_STACKS), pf_nmax=8, payouts=payouts,
                    bf_shares=list(pushfold.BF_SHARES), bf_fracs=list(pushfold.BF_FRACS))

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    size = write_bundle(args.out, meta, arrays)
    log(f"wrote {args.out} ({size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()

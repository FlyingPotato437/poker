"""ICM push/fold charts via fictitious play over hand-strength thresholds.

Model per (players left n, stack S in bb): equal stacks, action folds to the shover,
at most one caller (no overcalls), ICM payoffs on the points table for the remaining
places. Hands are aggregated into strength bins so this runs fast for any variant.

Re-solve on the day once the points table is announced (seconds):

    python -m gpu.pushfold --bundle bundles/nlhe.nlb --payouts 100,65,45,30,20,12,6,0
"""
import argparse
import os
from multiprocessing import Pool

import numpy as np

from nolimit.icm import icm

DEFAULT_STACKS = tuple(range(1, 26)) + (30,)


def hand_bins(class_pct, class_w, eq_range, H=200):
    """Aggregate classes into H strength bins: (bin weights summing to 1, bin equity (H, Y))."""
    Y = eq_range.shape[1]
    b = np.minimum((class_pct * H).astype(int), H - 1)
    w = np.bincount(b, weights=class_w, minlength=H).astype(float)
    E = np.zeros((H, Y))
    np.add.at(E, b, eq_range * class_w[:, None])
    nz = w > 0
    E[nz] /= w[nz, None]
    filled = np.where(nz)[0]
    for i in np.where(~nz)[0]:
        E[i] = E[filled[np.abs(filled - i).argmin()]]
    return w / w.sum(), E


def interp_y(E, y):
    Y = E.shape[1]
    x = min(max(y, 1.0 / Y), 1.0) * Y - 1.0
    i = int(x)
    if i >= Y - 1:
        return E[:, Y - 1]
    t = x - i
    return E[:, i] * (1 - t) + E[:, i + 1] * t


def range_weights(w, s):
    H = len(w)
    return w * np.clip(s * H - np.arange(H), 0.0, 1.0)


def range_vs_range(w, E, s, c):
    rw = range_weights(w, s)
    tot = rw.sum()
    return float((rw * interp_y(E, c)).sum() / tot) if tot > 0 else 0.5


def solve(n, S, payouts, w, E, iters=600, ante=0.0):
    """Returns (shove fraction per position (n-1,), call fraction c[i, j] (n, n))."""
    pay = list(payouts[:n])
    sbp, bbp = (0, 1) if n == 2 else (n - 2, n - 1)
    posted = np.zeros(n)
    posted[sbp] = 0.5
    posted[bbp] = 1.0
    base = np.maximum(S - ante - posted, 0.0)
    dead = posted.sum() + n * ante

    def V(st):
        return np.array(icm(list(st), pay))

    st = base.copy()
    st[bbp] += dead
    v_fold = V(st)
    steal = []
    for i in range(n):
        st = base.copy()
        st[i] += dead
        steal.append(V(st))
    vw, vl = {}, {}
    for i in range(n - 1):
        for j in range(i + 1, n):
            pot = 2 * S + sum(ante + posted[k] for k in range(n) if k not in (i, j))
            st = base.copy()
            st[i], st[j] = pot, 0.0
            vw[i, j] = V(st)
            st = base.copy()
            st[i], st[j] = 0.0, pot
            vl[i, j] = V(st)

    s = np.full(n - 1, 0.3)
    c = np.full((n, n), 0.2)
    for t in range(iters):
        s_br = np.zeros_like(s)
        c_br = np.zeros_like(c)
        for i in range(n - 1):
            ev = np.zeros(len(w))
            reach = 1.0
            for j in range(i + 1, n):
                e = interp_y(E, c[i, j])
                ev += reach * c[i, j] * (e * vw[i, j][i] + (1 - e) * vl[i, j][i])
                reach *= 1 - c[i, j]
            ev += reach * steal[i][i]
            s_br[i] = w[ev > v_fold[i]].sum()
            e_vs_shover = interp_y(E, s[i])
            for j in range(i + 1, n):
                ev_call = e_vs_shover * vl[i, j][j] + (1 - e_vs_shover) * vw[i, j][j]
                ev_fold = 0.0
                reach = 1.0
                for k in range(j + 1, n):
                    r = range_vs_range(w, E, s[i], c[i, k])
                    ev_fold += reach * c[i, k] * (r * vw[i, k][j] + (1 - r) * vl[i, k][j])
                    reach *= 1 - c[i, k]
                ev_fold += reach * steal[i][j]
                c_br[i, j] = w[ev_call > ev_fold].sum()
        step = 1.0 / (t + 2)
        s += (s_br - s) * step
        c += (c_br - c) * step
    return s, c


def _solve_job(args):
    n, k, S, payouts, w, E, iters, ante = args
    s, c = solve(n, S, payouts, w, E, iters, ante)
    return n, k, s, c


def solve_charts(class_pct, class_w, eq_range, payouts, stacks=DEFAULT_STACKS, nmax=8,
                 iters=600, ante=0.0, workers=None, log=print):
    w, E = hand_bins(np.asarray(class_pct), np.asarray(class_w, dtype=float), np.asarray(eq_range))
    K = len(stacks)
    shove = np.zeros((nmax - 1, nmax, K), dtype=np.float32)
    call = np.zeros((nmax - 1, nmax, nmax, K), dtype=np.float32)
    jobs = [(n, k, float(S), list(payouts), w, E, iters, ante)
            for n in range(2, nmax + 1) for k, S in enumerate(stacks)]
    with Pool(workers or os.cpu_count()) as pool:
        for n, k, s, c in pool.imap_unordered(_solve_job, jobs):
            shove[n - 2, :n - 1, k] = s
            call[n - 2, :n, :n, k] = c
    log(f"push/fold: solved {len(jobs)} spots (n=2..{nmax}, stacks {stacks[0]}..{stacks[-1]} bb)")
    return shove, call


BF_SHARES = tuple(round(x, 3) for x in (0.02, 0.04, 0.06, 0.08, 0.10, 0.125, 0.15, 0.175, 0.20, 0.25,
                                        0.30, 0.35, 0.40, 0.45, 0.50, 0.60, 0.70, 0.80, 0.90))
BF_FRACS = (0.1, 0.3, 1.0)


def _bf_job(args):
    n, i, j, h, x, payouts = args
    if n == 2:
        x = 1.0 - h
    x = min(x, 0.98 - h) if n > 2 else x
    if x <= 0.005 or h <= 0.005:
        return n, i, j, [1.0] * len(BF_FRACS)
    others = [(1.0 - h - x) / (n - 2)] * (n - 2) if n > 2 else []
    base = [h, x] + others
    now = icm(base, payouts[:n])[0]
    eff = min(h, x)
    out = []
    for f in BF_FRACS:
        r = f * eff
        win = icm([h + r, x - r] + others, payouts[:n])[0]
        lose = icm([h - r, x + r] + others, payouts[:n])[0]
        gain = win - now
        out.append(float(min(max((now - lose) / gain, 0.8), 8.0)) if gain > 1e-12 else 1.0)
    return n, i, j, out


def bubble_factors(payouts, nmax=8, workers=None, log=print):
    """ICM bubble factor BF[n-2, hero_share, villain_share, risk_frac].

    BF = (ICM_now - ICM_lose) / (ICM_win - ICM_now) for the hero risking risk_frac of the
    effective stack against the villain, remaining chips split evenly among the others.
    A call needs equity BF*c / (BF*c + pot) instead of c / (c + pot).
    """
    S = len(BF_SHARES)
    bf = np.ones((nmax - 1, S, S, len(BF_FRACS)), dtype=np.float32)
    jobs = [(n, i, j, h, x, list(payouts)) for n in range(2, nmax + 1)
            for i, h in enumerate(BF_SHARES) for j, x in enumerate(BF_SHARES)]
    with Pool(workers or os.cpu_count()) as pool:
        for n, i, j, out in pool.imap_unordered(_bf_job, jobs, chunksize=16):
            bf[n - 2, i, j] = out
    log(f"bubble factors: {len(jobs)} spots; 8 left, equal stacks, all-in: BF "
        f"{bf[nmax - 2, BF_SHARES.index(0.125), BF_SHARES.index(0.125), -1]:.2f}")
    return bf


def print_chart(shove, call, stacks, nmax):
    for n in (nmax, 4, 2):
        if n > nmax:
            continue
        print(f"\n{n} players left: open-shove top % by position (rows) x stack bb (cols)")
        cols = [k for k, S in enumerate(stacks) if S in (2, 4, 6, 8, 10, 15, 20)]
        print("pos  " + "".join(f"{stacks[k]:>6}" for k in cols))
        for i in range(n - 1):
            print(f"{i:>3}  " + "".join(f"{100 * shove[n - 2, i, k]:>6.1f}" for k in cols))
        print("BB call vs first-position shove: " +
              " ".join(f"{stacks[k]}bb={100 * call[n - 2, 0, n - 1, k]:.1f}%" for k in cols))


def main():
    from nolimit.bundle_io import read_bundle_np, write_bundle
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--payouts", required=True, help="points for 1st..8th, comma separated")
    ap.add_argument("--out", help="defaults to overwriting --bundle")
    ap.add_argument("--ante-bb", type=float, default=0.0)
    ap.add_argument("--iters", type=int, default=600)
    ap.add_argument("--workers", type=int)
    args = ap.parse_args()
    payouts = [float(x) for x in args.payouts.split(",")]
    meta, arrs = read_bundle_np(args.bundle)
    stacks = meta.get("pf_stacks", list(DEFAULT_STACKS))
    nmax = meta.get("pf_nmax", 8)
    shove, call = solve_charts(arrs["class_pct"], arrs["class_weight"], arrs["eq_range"], payouts,
                               stacks, nmax, args.iters, args.ante_bb, args.workers)
    arrs["pf_shove"], arrs["pf_call"] = shove, call
    arrs["icm_bf"] = bubble_factors(payouts, nmax, args.workers)
    meta.update(pf_stacks=list(stacks), pf_nmax=nmax, payouts=payouts,
                bf_shares=list(BF_SHARES), bf_fracs=list(BF_FRACS))
    size = write_bundle(args.out or args.bundle, meta, arrs)
    print_chart(shove, call, stacks, nmax)
    print(f"\nwrote {args.out or args.bundle} ({size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()

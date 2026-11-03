"""Should the bot switch params per table after it has seen the table? An uplift study.

    python scripts/switch_study.py --bundle bundles/nlhe_rng.nlb --base params/ev_t4.json \
        --arm w=params/w_nlhe.json --arm r=params/r_nlhe.json --sngs 20000 --out bench/wk/switch.jsonl

Every SNG draws its own table: opponent-style weights from a Dirichlet over --pool (small
alpha, so tables run from one style to a mix), then 7 seats from those weights. The SNG is
played once per branch, in the same seat with the same deck and seeds:

  stay    the base params for the whole SNG
  <arm>   the base params, then that arm's params from hand --at-hand on

Branches use the runtime's own switch (params "alt"), forced to one arm, so up to the switch
point every branch plays the same game (simulations run without the time deadline) and sees
the same table. Each branch records what the bot saw at the switch point (PrepBot.table_view:
the other seats' mean VPIP, PFR, aggression and fold-to-bet, and the share that never play);
the views must agree, which is checked. Features therefore only use information the bot had
before switching, and the outcome d = points(arm) - points(stay) is the effect of switching
from that point. SNGs the bot left before the switch point keep d = 0 and stay in every
average, so gains are per SNG played, as the runtime would see them.

Then: d of each arm is regressed on the features, and the rule "play the arm with the highest
predicted d, if any is > 0" is scored by 5-fold cross-validation (fit and standardize on 4/5,
judge on the held-out fifth) against staying and against always switching to each arm.
Confidence intervals are 95%, from the paired per-SNG differences. A rule only goes into the
runtime if its held-out gain clearly beats all of those, and it still has to win the end-to-end
final_check as a packaged bot.
"""
import argparse
import json
import math
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from nolimit import harness  # noqa: E402
from nolimit.engine import SNG  # noqa: E402
from nolimit.harness import make_agent, make_pool, parse_entry  # noqa: E402
from nolimit.runtime import PrepBot  # noqa: E402
from run_tournament import sng_kwargs  # noqa: E402

# Gate opponents (zoo FINAL_*, OOS, hyb_t1_g8) stay out, so the end-to-end check is out of sample.
POOL = ("timeout,random,station,maniac,nit,tag,lag,shover,sizer,cbet,mc,balanced,overbet,"
        "limper,icmshort,potcontrol,adaptive,prep:params/ev_t4.json")
FEATURES = ("vpip", "pfr", "agg", "fold_to_bet", "never")
Z95 = 1.96


def forced(base, arm, at_hand, on):
    """Base params plus the runtime switch forced on (to `arm`) or off (stay; still records the view)."""
    beta = dict(dict.fromkeys(FEATURES, 0.0), const=1.0 if on else -1.0)
    return dict(base, alt={"from_hand": at_hand, "mu": dict.fromkeys(FEATURES, 0.0), "sd": dict.fromkeys(FEATURES, 1.0),
                           "arms": [{"params": arm, "beta": beta}]})


def _job(job):
    games, kw, at_hand, base, arms = job
    out = []
    for seats, seed, slot in games:
        branches = [("stay", forced(base, {}, at_hand, False))] + [(k, forced(base, a, at_hand, True)) for k, a in arms]
        pts, views = {}, []
        for name, params in branches:
            agents = [PrepBot(harness._W["tables"], params, seed=seed * 31 + i) if i == slot else make_agent(e, seed * 31 + i)
                      for i, e in enumerate(seats)]
            sng = SNG(harness._W["variant"], agents, rng=random.Random(seed), evaluator=harness._W["tables"].ev, **kw)
            pts[name] = sng.run()[slot]
            views.append(agents[slot].view)
        out.append({"seed": seed, "styles": [e["label"] for i, e in enumerate(seats) if i != slot],
                    "f": views[0], "same_view": all(v == views[0] for v in views), "pts": pts})
    return out


def build_games(args):
    pool = [parse_entry(s) for s in args.pool.split(",")]
    rng = random.Random(args.seed)
    games = []
    for g in range(args.sngs):
        w = [rng.gammavariate(args.alpha, 1.0) for _ in pool]
        seats = rng.choices(pool, weights=w, k=7)
        slot = rng.randrange(8)
        seats.insert(slot, {"label": "hero", "kind": "prep"})
        games.append((seats, args.seed * 1_000_003 + g, slot))
    return games


def ols(X, y):
    import numpy as np
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    cov = np.linalg.pinv(X.T @ X) * (resid @ resid) / max(len(y) - X.shape[1], 1)
    return beta, np.sqrt(np.diag(cov))


def design(F, mu, sd):
    import numpy as np
    return np.hstack([np.ones((len(F), 1)), (F - mu) / sd])


def analyse(rows, fair):
    import numpy as np
    arms = [k for k in rows[0]["pts"] if k != "stay"]
    D = np.array([[r["pts"][k] - r["pts"]["stay"] for k in arms] for r in rows], dtype=float)
    seen = np.array([r["f"] is not None for r in rows])
    F = np.array([[r["f"][k] for k in FEATURES] if r["f"] else [0.0] * len(FEATURES) for r in rows])
    bad = sum(not r["same_view"] for r in rows) + int((np.abs(D[~seen]) > 1e-9).sum())

    def ci(v):
        m, s = v.mean() / fair * 100, v.std(ddof=1) / math.sqrt(len(v)) / fair * 100
        return f"{m:+6.2f}% [{m - Z95 * s:+.2f}, {m + Z95 * s:+.2f}]"

    print(f"{len(rows)} tables; bot reached the switch point at {seen.mean():.0%}; "
          f"determinism violations {bad} (must be 0). Gains in % of fair ({fair:.2f} pts) per SNG, 95% CI.")
    for j, k in enumerate(arms):
        print(f"always switch to {k:<6} vs stay: {ci(D[:, j])}")

    idx = np.flatnonzero(seen)
    for j, k in enumerate(arms):
        mu, sd = F[idx].mean(0), F[idx].std(0) + 1e-9
        beta, se = ols(design(F[idx], mu, sd), D[idx, j])
        print(f"\nOLS of d({k}) on standardized features, switched tables (pts per 1 sd):")
        for name, bb, ss, mm, sdd in zip(("const",) + FEATURES, beta, se, (0,) + tuple(mu), (1,) + tuple(sd)):
            extra = f"   mean {mm:.3f} sd {sdd:.3f}" if name != "const" else ""
            print(f"  {name:<12}{bb:+7.2f} ±{ss:.2f}  t {bb / ss:+5.1f}{extra}")

    # 5-fold cross-fit: standardize and fit on the training folds only, pick on the held-out fold.
    k_fold = 5
    order = np.random.default_rng(0).permutation(idx)
    choice = np.full(len(rows), -1)
    for f in range(k_fold):
        test = order[f::k_fold]
        train = np.setdiff1d(idx, test)
        mu, sd = F[train].mean(0), F[train].std(0) + 1e-9
        pred = np.column_stack([design(F[test], mu, sd) @ ols(design(F[train], mu, sd), D[train, j])[0]
                                for j in range(len(arms))])
        best = pred.argmax(1)
        choice[test] = np.where(pred.max(1) > 0, best, -1)
    gain = np.where(choice >= 0, D[np.arange(len(rows)), np.maximum(choice, 0)], 0.0)
    print(f"\n5-fold held-out rule (arm with the highest predicted d, if > 0):")
    print("  plays " + ", ".join(f"{k} {np.mean(choice[seen] == j):.0%}" for j, k in enumerate(arms))
          + f", stays {np.mean(choice[seen] == -1):.0%} of switched tables")
    print(f"  rule vs stay:              {ci(gain)}")
    for j, k in enumerate(arms):
        print(f"  rule vs always {k:<10} {ci(gain - D[:, j])}")

    mu, sd = F[idx].mean(0), F[idx].std(0) + 1e-9
    rule = {"mu": dict(zip(FEATURES, mu.tolist())), "sd": dict(zip(FEATURES, sd.tolist())),
            "betas": {k: dict(zip(("const",) + FEATURES, ols(design(F[idx], mu, sd), D[idx, j])[0].tolist()))
                      for j, k in enumerate(arms)}}
    print("\nrule fit on all tables (for the runtime):", json.dumps(rule))

    print("\nd by style, tables where the style holds >= 3 of 7 seats (n >= 200):")
    for st in sorted({s for r in rows for s in r["styles"]}):
        sel = np.array([r["styles"].count(st) >= 3 for r in rows])
        if sel.sum() >= 200:
            print(f"  {st:<26}{sel.sum():>6}  " + "  ".join(f"{k} {ci(D[sel, j])}" for j, k in enumerate(arms)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--variant", default="nlhe")
    ap.add_argument("--base", required=True, help="params JSON played up to the switch point, and after it by 'stay'")
    ap.add_argument("--arm", action="append", default=[], help="name=params.json, one per arm")
    ap.add_argument("--sngs", type=int, default=20000)
    ap.add_argument("--pool", default=POOL)
    ap.add_argument("--alpha", type=float, default=0.3, help="Dirichlet concentration of a table's styles")
    ap.add_argument("--at-hand", type=int, default=30)
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    ap.add_argument("--seed", type=int, default=6161)
    ap.add_argument("--payouts", default="100,65,45,30,20,12,6,0")
    ap.add_argument("--schedule")
    ap.add_argument("--hands-per-level", type=int, default=25)
    ap.add_argument("--max-hands", type=int, default=200)
    ap.add_argument("--stack", type=int, default=2000)
    ap.add_argument("--time-limit-ms", type=float)
    ap.add_argument("--out", required=True)
    ap.add_argument("--analyse-only", action="store_true", help="re-read --out instead of playing")
    args = ap.parse_args()
    kw = sng_kwargs(args)
    fair = sum(kw["payouts"]) / 8

    if not args.analyse_only:
        base = json.load(open(args.base))
        arms = []
        for spec in args.arm:
            name, path = spec.split("=", 1)
            p = json.load(open(path))
            arms.append((name, {k: v for k, v in p.items() if base.get(k) != v}))
        games = build_games(args)
        jobs = [(games[i:i + 8], kw, args.at_hand, base, arms) for i in range(0, len(games), 8)]
        pool = make_pool(args.bundle, args.variant, args.workers)
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        try:
            with open(args.out, "w") as fh:
                for part in pool.imap_unordered(_job, jobs):
                    for r in part:
                        fh.write(json.dumps(r) + "\n")
        finally:
            pool.terminate()
    rows = [json.loads(line) for line in open(args.out)]
    analyse(rows, fair)


if __name__ == "__main__":
    main()

"""Payoff matrix for the live-adaptation study: x-fair of every PORTFOLIO strategy in every scenario.

    python scripts/adapt_matrix.py --sngs 1200 --workers 4 --seed 7701 [--schedule normal|fast]
    python scripts/adapt_matrix.py --report            # rebuild matrix JSON/markdown from saved records

Every SNG is played once per strategy, same seat/opponents/deck (paired). Per-SNG records,
including the opponents' hand-log counts from the cand run, go to
bench/adapt/rec_<schedule>_<scenario>.json, so runs resume per scenario. The report reweights
the pooled records (nolimit.adapt.Pool) for every scenario, which uses all SNGs for each cell.
"""
import argparse
import json
import math
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.chdir(ROOT)

from nolimit import adapt  # noqa: E402
from nolimit.engine import DEFAULT_PAYOUTS  # noqa: E402

OUT = os.path.join(ROOT, "bench", "adapt")
FAIR = sum(DEFAULT_PAYOUTS) / len(DEFAULT_PAYOUTS)
HPL = {"normal": 25, "fast": 10}


def bundle_path():
    from benchmark import rebundle
    return rebundle(os.path.join(ROOT, "bundles", "nlhe_rng.nlb"), DEFAULT_PAYOUTS)


def rec_path(sched, scn):
    return os.path.join(OUT, f"rec_{sched}_{scn}.json")


def load_records(sched):
    recs, props = [], {}
    for scn, mix in adapt.SCENARIOS.items():
        p = rec_path(sched, scn)
        if not os.path.exists(p):
            continue
        d = json.load(open(p))
        for r in d["recs"]:
            r["scenario"] = scn
        recs.extend(d["recs"])
        props[scn] = (mix, len(d["recs"]))
    return recs, props


def paired_se(recs, w, j, k):
    """se of strategy j - strategy k under weights w (x-fair units)."""
    d = [r["pts"][j] - r["pts"][k] for r in recs]
    m = sum(wi * x for wi, x in zip(w, d))
    return m / FAIR, math.sqrt(sum(wi * wi * (x - m) ** 2 for wi, x in zip(w, d))) / FAIR


def report(sched):
    recs, props = load_records(sched)
    if not recs:
        return None
    pool = adapt.Pool(recs, props)
    names = list(adapt.PORTFOLIO)
    mat = {}
    for scn, mix in adapt.SCENARIOS.items():
        w = pool.weights(mix)
        pay, se, ess = pool.payoff(mix, FAIR)
        diffs = [paired_se(recs, w, j, 0) for j in range(len(names))]
        mat[scn] = {"xfair": dict(zip(names, pay)), "se": dict(zip(names, se)), "ess": ess,
                    "d_vs_cand": {n: d[0] for n, d in zip(names, diffs)},
                    "d_se": {n: d[1] for n, d in zip(names, diffs)},
                    "stats": dict(zip(adapt.STAT_KEYS, pool.stats(mix))),
                    "n_own": props.get(scn, (None, 0))[1]}
    out = {"schedule": sched, "fair": FAIR, "strategies": names, "portfolio": adapt.PORTFOLIO,
           "scenarios": {k: v for k, v in adapt.SCENARIOS.items()}, "matrix": mat}
    json.dump(out, open(os.path.join(OUT, f"matrix_{sched}.json"), "w"), indent=1)
    lines = [f"# Payoff matrix, {sched} blinds (x-fair; MIS over {len(recs)} paired SNGs)", "",
             "Cells: x-fair of the strategy. `best` = argmax; `gain` = best − cand in % of fair "
             "± paired se. ESS = effective SNGs behind each row after reweighting.", "",
             "| scenario | " + " | ".join(names) + " | best | gain vs cand | ESS |",
             "|---|" + "---|" * (len(names) + 3)]
    for scn in adapt.SCENARIOS:
        m = mat[scn]
        best = max(names, key=lambda n: m["xfair"][n])
        lines.append(f"| {scn} | " + " | ".join(f"{m['xfair'][n]:.3f}" for n in names)
                     + f" | {best} | {100 * m['d_vs_cand'][best]:+.1f} ±{100 * m['d_se'][best]:.1f} | {m['ess']:.0f} |")
    lines += ["", "Paired difference vs cand, % of fair (± se):", "",
              "| scenario | " + " | ".join(names[1:]) + " |", "|---|" + "---|" * (len(names) - 1)]
    for scn in adapt.SCENARIOS:
        m = mat[scn]
        lines.append(f"| {scn} | " + " | ".join(f"{100 * m['d_vs_cand'][n]:+.1f} ±{100 * m['d_se'][n]:.1f}"
                                                for n in names[1:]) + " |")
    lines += ["", "Aggregate opponent stats (what a hand log gives):", "",
              "| scenario | " + " | ".join(adapt.STAT_KEYS) + " |", "|---|" + "---|" * len(adapt.STAT_KEYS)]
    for scn in adapt.SCENARIOS:
        lines.append(f"| {scn} | " + " | ".join(f"{mat[scn]['stats'][k]:.3f}" for k in adapt.STAT_KEYS) + " |")
    open(os.path.join(OUT, f"matrix_{sched}.md"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sngs", type=int, default=1200)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--seed", type=int, default=7701)
    ap.add_argument("--schedule", default="normal")
    ap.add_argument("--scenarios", default=",".join(adapt.SCENARIOS))
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    if not args.report:
        import multiprocessing as mp
        strats = list(adapt.PORTFOLIO.values())
        pool = mp.get_context("spawn").Pool(args.workers, initializer=adapt._worker_init, initargs=(bundle_path(),))
        try:
            for i, scn in enumerate(args.scenarios.split(",")):
                p = rec_path(args.schedule, scn)
                if os.path.exists(p):
                    print(f"{scn}: have {p}", flush=True)
                    continue
                t0 = time.time()
                games = adapt.make_games(adapt.SCENARIOS[scn], args.sngs, args.seed * 100 + i)
                rows = adapt.run_paired(pool, games, strats, {"hands_per_level": HPL[args.schedule]})
                recs = [{"seed": s, "opps": o, "pts": pts, "counts": c, "hands": h} for s, o, pts, c, h in rows]
                json.dump({"scenario": scn, "schedule": args.schedule, "strategies": list(adapt.PORTFOLIO),
                           "recs": recs}, open(p, "w"))
                m = [sum(r["pts"][j] for r in recs) / len(recs) / FAIR for j in range(len(strats))]
                print(f"{scn}: {len(recs)} SNGs in {time.time() - t0:.0f}s  "
                      + " ".join(f"{n}={x:.3f}" for n, x in zip(adapt.PORTFOLIO, m)), flush=True)
        finally:
            pool.terminate()
    report(args.schedule)


if __name__ == "__main__":
    main()

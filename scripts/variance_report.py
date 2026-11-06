"""Variance decomposition: where the candidate's chips (and their variance) come from.

    python scripts/variance_report.py --field rival-real --sngs 1000 --workers 4
    python scripts/variance_report.py --field zoo --hands-per-level 10 --straddle --out bench/sweep/var_fast.md

Plays the candidate in one seat against the field with the engine's per-hand log on, then
breaks chips won per hand (in chips and in big blinds) and their spread down by position
(seat offset from the button among players dealt in), hole-card class, stack depth in BB
at the start of the hand, and all-in vs not. "share of var" is the group's part of the total
sum of squared chip results (sum of delta^2 over hands), i.e. how much of the swing it
carries; "share of chips" is its part of the net chips won. Also writes the raw records as
JSON lines when --dump is given.
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

from nolimit.harness import build_seatings, make_pool, parse_entry, run_games  # noqa: E402
from rules_cli import add_rule_args, rule_kwargs  # noqa: E402
from stipulation_sweep import SWEEP_FIELDS, payouts_for, rebundle  # noqa: E402
from benchmark import PAYOUTS  # noqa: E402

STACK_BUCKETS = (0, 8, 12, 16, 25, 40, 60, 100, 150, 1e9)
POS_ORDER = ("UTG", "UTG+1", "UTG+2", "UTG+3", "LJ", "HJ", "CO", "BTN", "SB", "BB")


def bucket(x):
    for lo, hi in zip(STACK_BUCKETS, STACK_BUCKETS[1:]):
        if x < hi:
            return f"{lo:g}-{hi:g}" if hi < 1e9 else f"{lo:g}+"
    return "?"


def group(recs, keyf):
    acc = {}
    for r in recs:
        acc.setdefault(keyf(r), []).append(r)
    return acc


def stats(rs, tot_sq, tot_net, n_tables):
    d = [r["delta"] for r in rs]
    b = [r["delta"] / r["bb"] for r in rs]
    n = len(d)
    m = sum(d) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in d) / max(n - 1, 1))
    mb = sum(b) / n
    sdb = math.sqrt(sum((x - mb) ** 2 for x in b) / max(n - 1, 1))
    sq = sum(x * x for x in d)
    return {"hands": n, "per_table": n / n_tables, "mean": m, "se": sd / math.sqrt(n), "sd": sd,
            "mean_bb": mb, "sd_bb": sdb, "net_per_table": sum(d) / n_tables,
            "share_var": sq / tot_sq if tot_sq else 0, "share_net": sum(d) / tot_net if tot_net else 0,
            "allin": sum(r["allin"] for r in rs) / n}


def table(title, groups, order, tot_sq, tot_net, n_tables, limit=None):
    lines = [f"### {title}", "",
             "| group | hands/table | chips/hand | ±se | SD chips | BB/hand | SD BB | chips/table | share of chips | share of var | all-in % |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    keys = order if order else list(groups)
    keys = [k for k in keys if k in groups]
    if limit:
        keys = keys[:limit]
    for k in keys:
        s = stats(groups[k], tot_sq, tot_net, n_tables)
        lines.append(f"| {k} | {s['per_table']:.2f} | {s['mean']:+.1f} | {s['se']:.1f} | {s['sd']:.0f} | "
                     f"{s['mean_bb']:+.2f} | {s['sd_bb']:.1f} | {s['net_per_table']:+.0f} | "
                     f"{100 * s['share_net']:+.0f}% | {100 * s['share_var']:.1f}% | {100 * s['allin']:.0f}% |")
    return lines + [""]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bundle", default="bundles/nlhe_rng.nlb")
    ap.add_argument("--candidate", default="prep:params/cand_nlhe.json")
    ap.add_argument("--field", default="rival-real", help="one of " + ",".join(SWEEP_FIELDS))
    ap.add_argument("--sngs", type=int, default=1000)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--seed", type=int, default=7401)
    ap.add_argument("--players", type=int, default=8)
    ap.add_argument("--points", default="default", help="a benchmark.py PAYOUTS name")
    ap.add_argument("--stack", type=int, default=2000)
    ap.add_argument("--hands-per-level", type=int, default=25)
    ap.add_argument("--max-hands", type=int, default=200)
    ap.add_argument("--top", type=int, default=12, help="hole classes shown at each end")
    ap.add_argument("--out", default=os.path.join(ROOT, "bench", "sweep", "variance_rival-real.md"))
    ap.add_argument("--dump", help="write the hand records here (JSON lines)")
    add_rule_args(ap)
    args = ap.parse_args()
    pts = payouts_for(PAYOUTS[args.points], args.players)
    kw = {"payouts": pts, "start_stack": args.stack, "hands_per_level": args.hands_per_level,
          "max_hands": args.max_hands, **rule_kwargs(args)}
    ante_pf = kw.get("ante_bb", 0.0) + kw.get("bb_ante", 0.0) / args.players
    bundle = rebundle(args.bundle, pts, ante_pf, args.workers)
    me = parse_entry(args.candidate)
    me["label"] = "me"
    field = [parse_entry(k, w) for k, w in SWEEP_FIELDS[args.field].items()]
    games = build_seatings(field, args.sngs, args.seed, fixed=[me], n_seats=args.players)
    t0 = time.time()
    pool = make_pool(bundle, None, args.workers)
    try:
        summ, recs = run_games(games, sng_kw=kw, pool=pool, log_labels=["me"])
    finally:
        pool.terminate()
    if args.dump:
        with open(args.dump, "w") as fh:
            for r in recs:
                fh.write(json.dumps(r) + "\n")
    n_tables = args.sngs
    fair = sum(pts) / args.players
    tot_sq = sum(r["delta"] ** 2 for r in recs)
    tot_net = sum(r["delta"] for r in recs)
    # per-table results
    by_t = group(recs, lambda r: r["sng_seed"])
    pts_t = [rs[0]["points"] for rs in by_t.values()]
    mp = sum(pts_t) / len(pts_t)
    sdp = math.sqrt(sum((x - mp) ** 2 for x in pts_t) / max(len(pts_t) - 1, 1))
    hands_t = [len(rs) for rs in by_t.values()]
    lines = [f"# Variance decomposition: {args.candidate} vs {args.field}", "",
             f"{args.sngs} SNGs, {args.players} players, points {args.points}, stack {args.stack}, "
             f"{args.hands_per_level} hands/level, cap {args.max_hands}, rules {rule_kwargs(args) or 'default'}; "
             f"seed {args.seed}; {time.time() - t0:.0f}s.", "",
             f"Score {mp / fair:.3f}x fair ±{sdp / fair / math.sqrt(len(pts_t)):.3f} (points/table {mp:.1f}, SD "
             f"{sdp:.1f} = {sdp / fair:.2f}x fair). Hands dealt in per table {sum(hands_t) / len(hands_t):.1f}; "
             f"net chips per table {tot_net / n_tables:+.0f}; chip SD per hand "
             f"{stats(recs, tot_sq, tot_net, n_tables)['sd']:.0f}.", ""]
    lines += table("By position", group(recs, lambda r: r["pos"]), POS_ORDER, tot_sq, tot_net, n_tables)
    lines += table("By players dealt in", group(recs, lambda r: r["n_alive"]), sorted({r["n_alive"] for r in recs}, reverse=True),
                   tot_sq, tot_net, n_tables)
    lines += table("By stack at the start of the hand (BB)", group(recs, lambda r: bucket(r["stack_bb"])),
                   [bucket((lo + hi) / 2 if hi < 1e9 else lo + 1) for lo, hi in zip(STACK_BUCKETS, STACK_BUCKETS[1:])],
                   tot_sq, tot_net, n_tables)
    lines += table("All-in vs not", group(recs, lambda r: "all-in" if r["allin"] else "not all-in"),
                   ["all-in", "not all-in"], tot_sq, tot_net, n_tables)
    lines += table("Showdown vs not", group(recs, lambda r: "showdown" if r["showdown"] else "no showdown"),
                   ["showdown", "no showdown"], tot_sq, tot_net, n_tables)
    lines += table("Raised (bet or raised at some point) vs not",
                   group(recs, lambda r: "raised" if r["raised"] else "never raised"),
                   ["raised", "never raised"], tot_sq, tot_net, n_tables)
    if any(r["bounty"] for r in recs):
        lines += table("7-2 bounty paid or collected", group(recs, lambda r: "bounty" if r["bounty"] else "none"),
                       ["bounty", "none"], tot_sq, tot_net, n_tables)
    hc = group(recs, lambda r: r["hole"])
    net = sorted(hc, key=lambda k: -sum(r["delta"] for r in hc[k]))
    lines += table(f"Hole classes: top {args.top} chip winners", hc, net, tot_sq, tot_net, n_tables, args.top)
    lines += table(f"Hole classes: bottom {args.top} (biggest losers)", hc, net[::-1], tot_sq, tot_net, n_tables, args.top)
    var = sorted(hc, key=lambda k: -sum(r["delta"] ** 2 for r in hc[k]))
    lines += table(f"Hole classes: top {args.top} by share of variance", hc, var, tot_sq, tot_net, n_tables, args.top)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()

"""Paired A/B test: two bots take the same seat against the same opponents and cards.

    python scripts/ab_test.py --bundle bundles/nlhe_rng.nlb --a prep:params/new.json \\
        --b prep:params/nlhe_final_legacy.json --sngs 1000

Every SNG is played twice, once with A and once with B in the seat, with identical
opponents, seats and deck order. Each cell prints the paired difference (A - B) in
points per table with its standard error, so luck cancels and small edges show up.
The h2h cell seats 4 A and 4 B (seats swapped in the replay) and reports A's share.
Fields marked * contain only held-out styles that no tune run has seen.
"""
import argparse
import math
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from benchmark import FIELDS, PAYOUTS, SCHEDULES, rebundle  # noqa: E402
from final_check import final_fields  # noqa: E402
from nolimit.harness import build_seatings, make_pool, parse_entry, run_games  # noqa: E402
from nolimit.zoo import DEFAULT_FIELD_MIX, FRESH, HELD_OUT  # noqa: E402
from rules_cli import add_rule_args, rule_kwargs  # noqa: E402

AB_FIELDS = dict(FIELDS)
AB_FIELDS["held-out*"] = {k: 1 for k in HELD_OUT}
AB_FIELDS["zoo+held-out"] = {**DEFAULT_FIELD_MIX, **{k: 0.1 for k in HELD_OUT}}
AB_FIELDS["sharks"] = {"prep:params/nlhe_final_legacy.json": 3, "tag": 1, "lag": 1, "cbet": 1, "balanced": 1}
# Sealed fields (not in the default list): final confirmation only, never for choosing.
AB_FIELDS["fresh*"] = {k: 1 for k in FRESH}
AB_FIELDS["fresh+old-tunes*"] = {**{k: 1 for k in FRESH}, "prep:params/nlhe_quick.json": 1,
                                 "prep:params/nlhe_full.json": 1, "prep:params/nlhe_robust.json": 1}
AB_FIELDS["fresh+zoo*"] = {**DEFAULT_FIELD_MIX, **{k: 0.12 for k in FRESH}}
# final_check's fields, in-process and without the deadline (not in the default list).
AB_FIELDS.update({f"gate-{k}": v for k, v in final_fields("nlhe", {}).items()
                  if k != "oos" and not k.startswith(("rival", "llm"))})
# Rival-team fields (nolimit/rivals.py), not in the default list; rival-oos is sealed.
AB_FIELDS.update({k: v for k, v in final_fields("nlhe", {}).items() if k.startswith("rival") and k != "rival-oos"})
# LLM-bug designs (nolimit/rivals.py): evaluation fields, not in the default list.
AB_FIELDS.update({k: v for k, v in final_fields("nlhe", {}).items() if k.startswith("llm")})


def paired(rows, a, b):
    pa = {r[7]: r[1] for r in rows if r[0] == a}
    pb = {r[7]: r[1] for r in rows if r[0] == b}
    d = [pa[k] - pb[k] for k in pa if k in pb]
    m = sum(d) / len(d)
    var = sum((x - m) ** 2 for x in d) / max(len(d) - 1, 1)
    return m, math.sqrt(var / len(d)), len(d)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--sngs", type=int, default=800)
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    ap.add_argument("--fields", default=",".join(k for k in AB_FIELDS if not k.startswith(("fresh", "gate-", "rival", "llm"))))
    ap.add_argument("--payouts", default="default,top-heavy")
    ap.add_argument("--schedules", default="normal,fast")
    ap.add_argument("--seed", type=int, default=21)
    # The kit's rules on the day, instead of editing benchmark.py:
    ap.add_argument("--points", help="the kit's points 1st..last, e.g. 12,8,5,3,2,1,0,0 (replaces --payouts)")
    ap.add_argument("--keep-bundle", action="store_true", help="use --bundle's push/fold as is (already solved "
                    "for these points and antes, e.g. bundles/day/<tag>.nlb) instead of re-solving per points")
    ap.add_argument("--schedule", help="the kit's blind levels, e.g. 10/20,15/30,25/50")
    ap.add_argument("--hands-per-level", type=int, help="the kit's hands per level (replaces --schedules)")
    ap.add_argument("--stack", type=int, help="starting stack")
    ap.add_argument("--ante", type=int, default=0, help="ante in chips, every hand")
    ap.add_argument("--max-hands", type=int, help="hand cap")
    ap.add_argument("--reopen-short", action="store_true", help="a short all-in reopens the betting")
    add_rule_args(ap)
    args = ap.parse_args()
    if args.points:
        PAYOUTS["kit"] = tuple(float(x) for x in args.points.split(","))
        args.payouts = "kit"
    if args.hands_per_level:
        SCHEDULES["kit"] = args.hands_per_level
        args.schedules = "kit"
    rules = {}
    if args.schedule:
        rules["schedule"] = tuple(tuple(int(x) for x in lvl.split("/")) for lvl in args.schedule.split(","))
    for k, v in (("start_stack", args.stack), ("ante", args.ante), ("max_hands", args.max_hands),
                 ("reopen_short", args.reopen_short)):
        if v:
            rules[k] = v
    rules.update(rule_kwargs(args))

    t_start = time.time()
    total = {"d": 0.0, "v": 0.0, "n": 0}
    print(f"A = {args.a}\nB = {args.b}\n{'points':<10}{'blinds':<8}{'field':<16}{'A-B pts/table':>15}{'±se':>7}"
          f"{'  A-B % of fair':>15}   errors A/B")
    for pname in args.payouts.split(","):
        payouts = PAYOUTS[pname]
        fair = sum(payouts) / len(payouts)
        pool = make_pool(args.bundle if args.keep_bundle else rebundle(args.bundle, payouts), None, args.workers)
        try:
            for sname in args.schedules.split(","):
                kw = {"payouts": list(payouts), "hands_per_level": SCHEDULES[sname], **rules}
                ea, eb = parse_entry(args.a), parse_entry(args.b)
                ea["label"], eb["label"] = "A", "B"
                for fname in args.fields.split(","):
                    field = [parse_entry(k, w) for k, w in AB_FIELDS[fname].items()]
                    base = build_seatings(field, args.sngs, args.seed, fixed=[{"label": "slot"}])
                    games = []
                    for seats, seed in base:
                        for e in (ea, eb):
                            games.append(([e if s.get("label") == "slot" else s for s in seats], seed))
                    rows = run_games(games, sng_kw=kw, pool=pool, raw=True)
                    m, se, n = paired(rows, "A", "B")
                    errs = (sum(r[6] for r in rows if r[0] == "A"), sum(r[6] for r in rows if r[0] == "B"))
                    total["d"] += m / fair
                    total["v"] += (se / fair) ** 2
                    total["n"] += 1
                    print(f"{pname:<10}{sname:<8}{fname:<16}{m:>+15.2f}{se:>7.2f}{100 * m / fair:>+14.1f}%   "
                          f"{errs[0]}/{errs[1]}", flush=True)
                # head to head: 4 A + 4 B, replayed with every seat flipped
                games = []
                for g in range(args.sngs // 2):
                    seed = args.seed * 1_000_003 + 500_000 + g
                    seats = [ea, eb] * 4
                    games.append((seats, seed))
                    games.append((seats[1:] + seats[:1], seed))
                rows = run_games(games, sng_kw=kw, pool=pool, raw=True)
                sa = sum(r[1] for r in rows if r[0] == "A") / (len(games) * 4)
                print(f"{pname:<10}{sname:<8}{'h2h 4v4':<16}{'A ' + format(sa / fair, '.3f') + 'x fair':>15}", flush=True)
        finally:
            pool.terminate()
    k = total["n"]
    print(f"\nmean over {k} cells: A-B {100 * total['d'] / k:+.2f}% of fair (±{100 * math.sqrt(total['v']) / k:.2f})"
          f"  [{time.time() - t_start:.0f}s]")


if __name__ == "__main__":
    main()

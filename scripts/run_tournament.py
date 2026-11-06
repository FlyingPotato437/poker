"""Score bots in the organizers' format: random 8-seat SNGs, average points per table.

    python scripts/run_tournament.py --bundle bundles/nlhe.nlb --sngs 2000
    python scripts/run_tournament.py --bundle bundles/nlhe.nlb --field prep,prep:params/best.json,tag,shover,nit
    python scripts/run_tournament.py --variant plo4 --field heur,tag,shover    # no bundle yet

Field entries take an optional weight: tag=3,shover=2. Default field: two PrepBot
copies against the zoo mix in nolimit/zoo.py.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nolimit.engine import DEFAULT_PAYOUTS, DEFAULT_SCHEDULE  # noqa: E402
from nolimit.harness import build_seatings, format_summary, parse_entry, run_games  # noqa: E402
from nolimit.zoo import DEFAULT_FIELD_MIX  # noqa: E402
from rules_cli import add_rule_args, rule_kwargs  # noqa: E402


def parse_field(text):
    out = []
    for item in filter(None, text.split(",")):
        name, _, w = item.partition("=")
        out.append(parse_entry(name, float(w) if w else 1.0))
    return out


def sng_kwargs(args):
    kw = {"payouts": [float(x) for x in args.payouts.split(",")], "max_hands": args.max_hands,
          "hands_per_level": args.hands_per_level, "start_stack": args.stack}
    if args.schedule:
        kw["schedule"] = tuple(tuple(int(x) for x in lvl.split("/")) for lvl in args.schedule.split(","))
    if args.time_limit_ms:
        kw["time_limit_ms"] = args.time_limit_ms
    if getattr(args, "ante", 0):
        kw["ante"] = args.ante
    if getattr(args, "reopen_short", False):
        kw["reopen_short"] = True
    kw.update(rule_kwargs(args))
    return kw


def add_common(ap):
    ap.add_argument("--bundle", help="table bundle (.nlb); omit to use heuristic tables")
    ap.add_argument("--variant", default="nlhe", help="preset, used when no bundle")
    ap.add_argument("--sngs", type=int, default=1000)
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--payouts", default=",".join(str(x) for x in DEFAULT_PAYOUTS))
    ap.add_argument("--schedule", help="blind levels like 10/20,15/30,25/50 (default: engine)")
    ap.add_argument("--hands-per-level", type=int, default=25)
    ap.add_argument("--max-hands", type=int, default=200)
    ap.add_argument("--stack", type=int, default=2000)
    ap.add_argument("--time-limit-ms", type=float, help="enforce the per-decision limit like the host")
    ap.add_argument("--ante", type=int, default=0, help="ante in chips from every player, every hand")
    ap.add_argument("--reopen-short", action="store_true", help="a short all-in reopens the betting")
    add_rule_args(ap)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_common(ap)
    ap.add_argument("--field", help="comma list of entries (default: zoo mix)")
    ap.add_argument("--fixed", default="prep,prep", help="entries seated at every table")
    args = ap.parse_args()
    field = parse_field(args.field) if args.field else [parse_entry(k, w) for k, w in DEFAULT_FIELD_MIX.items()]
    fixed = parse_field(args.fixed) if args.fixed else []
    t0 = time.time()
    games = build_seatings(field, args.sngs, args.seed, fixed=fixed)
    summary = run_games(games, args.bundle, args.variant, args.workers, sng_kwargs(args))
    print(format_summary(summary))
    print(f"\n{args.sngs} SNGs in {time.time() - t0:.1f}s; total points per table "
          f"{sum(float(x) for x in args.payouts.split(','))}")


if __name__ == "__main__":
    main()

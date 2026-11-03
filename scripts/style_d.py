"""Per-style gain of one params set over another: A vs B against 7 copies of each style.

    python scripts/style_d.py --a prep:params/r2p0_nlhe.json --b prep:params/ev_t4.json \
        --styles tag,lag,...  --sngs 600 --seed 9601 > bench/rivals/style_d_r2p0.txt

Tells where exploit params pay (d > 0) and where they cost (d < 0): the labels for the
per-opponent exploitation rule. Paired as in ab_test.py; normal blinds, default points.
"""
import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ab_test import paired  # noqa: E402
from nolimit.engine import DEFAULT_PAYOUTS  # noqa: E402
from nolimit.harness import build_seatings, make_pool, parse_entry, run_games  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bundle", default="bundles/nlhe_rng.nlb")
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--styles", required=True)
    ap.add_argument("--sngs", type=int, default=600)
    ap.add_argument("--seed", type=int, default=9601)
    ap.add_argument("--hands-per-level", type=int, default=25)
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    ap.add_argument("--json", help="also write {style: [d %fair, se]} here")
    args = ap.parse_args()
    fair = sum(DEFAULT_PAYOUTS) / len(DEFAULT_PAYOUTS)
    ea, eb = parse_entry(args.a), parse_entry(args.b)
    ea["label"], eb["label"] = "A", "B"
    out = {}
    pool = make_pool(args.bundle, None, args.workers)
    try:
        print(f"A = {args.a}\nB = {args.b}\n{'style':<28}{'A-B % of fair':>14}{'±se':>7}")
        for st in args.styles.split(","):
            base = build_seatings([parse_entry(st)], args.sngs, args.seed, fixed=[{"label": "slot"}])
            games = [([e if s.get("label") == "slot" else s for s in seats], seed)
                     for seats, seed in base for e in (ea, eb)]
            rows = run_games(games, sng_kw={"hands_per_level": args.hands_per_level}, pool=pool, raw=True)
            m, se, n = paired(rows, "A", "B")
            out[st] = [100 * m / fair, 100 * se / fair]
            print(f"{st:<28}{100 * m / fair:>+13.1f}%{100 * se / fair:>7.1f}", flush=True)
    finally:
        pool.terminate()
    if args.json:
        json.dump(out, open(args.json, "w"), indent=1)


if __name__ == "__main__":
    main()

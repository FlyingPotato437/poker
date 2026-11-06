"""Per-style x-fair for A and B, one seat vs 7 copies of each style, paired; normal and fast blinds.

    python scripts/style_xfair.py prep:params/x_nlhe.json prep:params/ev_t4.json phase,raiseby 800 9812 [workers]
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from nolimit.engine import DEFAULT_PAYOUTS  # noqa: E402
from nolimit.harness import build_seatings, make_pool, parse_entry, run_games  # noqa: E402


def stats(xs):
    m = sum(xs) / len(xs)
    return m, math.sqrt(sum((x - m) ** 2 for x in xs) / max(len(xs) - 1, 1) / len(xs))


def main():
    a, b, styles, n, seed = sys.argv[1], sys.argv[2], sys.argv[3].split(","), int(sys.argv[4]), int(sys.argv[5])
    fair = sum(DEFAULT_PAYOUTS) / len(DEFAULT_PAYOUTS)
    ea, eb = parse_entry(a), parse_entry(b)
    ea["label"], eb["label"] = "A", "B"
    workers = int(sys.argv[6]) if len(sys.argv) > 6 else 4
    pool = make_pool(os.path.join(ROOT, "bundles", "nlhe_rng.nlb"), None, workers)
    print(f"A = {a}\nB = {b}\n{'blinds':<8}{'style':<12}{'A xfair':>9}{'±se':>6}{'B xfair':>9}{'±se':>6}{'A-B %fair':>11}{'±se':>6}")
    try:
        for hpl, sname in ((25, "normal"), (10, "fast")):
            for st in styles:
                base = build_seatings([parse_entry(st)], n, seed, fixed=[{"label": "slot"}])
                games = [([e if s.get("label") == "slot" else s for s in seats], sd)
                         for seats, sd in base for e in (ea, eb)]
                rows = run_games(games, sng_kw={"hands_per_level": hpl}, pool=pool, raw=True)
                pa = {r[7]: r[1] for r in rows if r[0] == "A"}
                pb = {r[7]: r[1] for r in rows if r[0] == "B"}
                ma, sa = stats(list(pa.values()))
                mb, sb = stats(list(pb.values()))
                md, sd_ = stats([pa[k] - pb[k] for k in pa])
                print(f"{sname:<8}{st:<12}{ma / fair:>9.3f}{sa / fair:>6.3f}{mb / fair:>9.3f}{sb / fair:>6.3f}"
                      f"{100 * md / fair:>+10.1f}%{100 * sd_ / fair:>6.1f}", flush=True)
    finally:
        pool.terminate()


if __name__ == "__main__":
    main()

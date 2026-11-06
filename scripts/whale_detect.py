"""Strong-seat detector study on whale_flow.py --stats snapshots.

    python scripts/whale_detect.py bench/whale/stats_9931.jsonl --params params/cand_whale.json

Prints, per label and hand checkpoint, the mean seat stats, P(exploitable) from the fitted
logistic and the share of seats the strong-seat rule ("exploit" -> "strong") flags.
"""
import argparse
import collections
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nolimit.runtime import EXPLOIT_FEATS  # noqa: E402


def coef(ex):
    k, beta = len(ex["mu"]), ex["beta"]
    c0, ab = beta[0], []
    for i, (m, s) in enumerate(zip(ex["mu"], ex["sd"])):
        bl, bq = beta[1 + i], beta[1 + k + i]
        c0 += -bl * m / s + bq * m * m / (s * s)
        ab.append((bl / s - 2 * bq * m / (s * s), bq / (s * s)))
    return c0, ab


def flag(d, c, g):
    r = d["rates"]
    if d["hands"] < g.get("n", 40):
        return False
    z = c[0] + sum(x * (a + b * x) for (a, b), x in zip(c[1], r))
    pe = 1 / (1 + math.exp(-max(min(z, 30), -30)))
    vlo, vhi = g.get("vpip", (0, 1))
    alo, ahi = g.get("agg", (0, 1))
    flo, fhi = g.get("ftb", (0, 1))
    return (pe <= g.get("p_max", 1) and vlo <= r[0] <= vhi and r[1] >= g.get("pfr_r", 0) * r[0]
            and alo <= r[2] <= ahi and flo <= r[3] <= fhi and d["allin"] <= g.get("ai_max", 1) * max(d["acts"], 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stats")
    ap.add_argument("--params", default="params/cand_nlhe.json")
    ap.add_argument("--strong", help="JSON rule overriding the params file's exploit.strong")
    ap.add_argument("--run", default="A")
    args = ap.parse_args()
    ex = json.load(open(args.params))["exploit"]
    g = json.loads(args.strong) if args.strong else ex.get("strong", {})
    c = coef(ex)
    acc = collections.defaultdict(list)
    for line in open(args.stats):
        d = json.loads(line)
        if d["run"] != args.run or d["cls"] == "us":
            continue
        z = c[0] + sum(x * (a + b * x) for (a, b), x in zip(c[1], d["rates"]))
        pe = 1 / (1 + math.exp(-max(min(z, 30), -30)))
        acc[(d["label"], d["h"])].append((d["rates"], pe, flag(d, c, g), d.get("f3o", 0), d.get("f3f", 0)))
    labels = sorted({k[0] for k in acc})
    print("rule:", json.dumps(g))
    print(f"{'label':<26}{'h':>4}{'n':>6}  " + " ".join(f"{f[:6]:>6}" for f in EXPLOIT_FEATS)
          + f"{'P(ex)':>7}{'f3':>6}{'flag%':>7}")
    for lb in labels:
        for h in (25, 50, 100, 150):
            v = acc.get((lb, h))
            if not v:
                continue
            n = len(v)
            m = [sum(x[0][i] for x in v) / n for i in range(len(EXPLOIT_FEATS))]
            f3o = sum(x[3] for x in v)
            print(f"{lb:<26}{h:>4}{n:>6}  " + " ".join(f"{x:>6.3f}" for x in m)
                  + f"{sum(x[1] for x in v) / n:>7.3f}{(sum(x[4] for x in v) / f3o if f3o else float('nan')):>6.2f}"
                  f"{100 * sum(x[2] for x in v) / n:>6.1f}%")


if __name__ == "__main__":
    main()

"""Tune PrepBot parameters with cross-entropy search over simulated SNGs.

    python scripts/tune.py --bundle bundles/nlhe.nlb --gens 15 --pop 24 --sngs 2000 --out params/nlhe.json

Every candidate plays the same seatings and card seeds in a generation (common random
numbers), so differences come from decisions, not luck. The field is the zoo mix plus
copies of the current mean params ("self"), so the bot cannot just overfit to the zoo.
Saves the mean params after every generation: safe to Ctrl-C and submit what is there.
"""
import argparse
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nolimit.harness import build_seatings, make_pool, parse_entry, run_games  # noqa: E402
from nolimit.runtime import DEFAULT_PARAMS, PARAM_SPACE, TUNE_EXCLUDE  # noqa: E402
from nolimit.zoo import DEFAULT_FIELD_MIX  # noqa: E402
from run_tournament import add_common, parse_field, sng_kwargs  # noqa: E402


def to_unit(params, keys):
    return [(params[k] - PARAM_SPACE[k][0]) / (PARAM_SPACE[k][1] - PARAM_SPACE[k][0]) for k in keys]


def from_unit(u, keys, base):
    p = dict(base)
    for k, x in zip(keys, u):
        lo, hi = PARAM_SPACE[k]
        p[k] = lo + min(max(x, 0.0), 1.0) * (hi - lo)
    return p


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    add_common(ap)
    ap.add_argument("--out", required=True)
    ap.add_argument("--init", help="start from this params JSON")
    ap.add_argument("--gens", type=int, default=15)
    ap.add_argument("--pop", type=int, default=24)
    ap.add_argument("--elite", type=int, default=6)
    ap.add_argument("--sigma", type=float, default=0.15)
    ap.add_argument("--keys", help="comma list of params to tune (default: all)")
    ap.add_argument("--field", help="opponent mix (default: zoo mix)")
    ap.add_argument("--self-weight", type=float, default=0.25, help="share of opponents that are the current mean")
    ap.add_argument("--mix-hands-per-level", help="comma list, e.g. 25,10: score every candidate at each "
                    "blind speed (same seatings) and average, so params can't overfit one schedule")
    args = ap.parse_args()

    base = dict(DEFAULT_PARAMS)
    if args.init:
        with open(args.init) as fh:
            base.update(json.load(fh))
    keys = args.keys.split(",") if args.keys else [k for k in PARAM_SPACE if k not in TUNE_EXCLUDE]
    field = parse_field(args.field) if args.field else [parse_entry(k, w) for k, w in DEFAULT_FIELD_MIX.items()]
    zoo_total = sum(e["weight"] for e in field)
    rng = random.Random(args.seed)
    mean = to_unit(base, keys)
    sigma = [args.sigma] * len(keys)
    kw = sng_kwargs(args)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    pool = make_pool(args.bundle, args.variant, args.workers)
    try:
        for gen in range(args.gens):
            t0 = time.time()
            mean_params = from_unit(mean, keys, base)
            selfe = {"label": "self", "kind": "prep", "params": mean_params,
                     "weight": zoo_total * args.self_weight / (1 - args.self_weight)}
            cands = [mean] + [[m + rng.gauss(0, s) for m, s in zip(mean, sigma)] for _ in range(args.pop - 1)]
            cands = [[min(max(x, 0.0), 1.0) for x in c] for c in cands]
            games = []
            seed = args.seed * 7919 + gen
            for i, c in enumerate(cands):
                entry = {"label": f"c{i}", "kind": "prep", "params": from_unit(c, keys, base)}
                games += build_seatings(field + [selfe], args.sngs, seed, fixed=[entry])
            speeds = [int(x) for x in args.mix_hands_per_level.split(",")] if args.mix_hands_per_level else [None]
            per = []
            for hpl in speeds:
                kw_s = dict(kw, hands_per_level=hpl) if hpl else kw
                per.append(run_games(games, sng_kw=kw_s, pool=pool))
            summary = {k: {"mean": sum(sm[k]["mean"] for sm in per) / len(per),
                           "se": sum(sm[k]["se"] for sm in per) / len(per) / len(per) ** 0.5} for k in per[0]}
            scores = [summary[f"c{i}"]["mean"] for i in range(len(cands))]
            order = sorted(range(len(cands)), key=lambda i: -scores[i])
            elite = [cands[i] for i in order[:args.elite]]
            new_mean = [sum(e[d] for e in elite) / len(elite) for d in range(len(keys))]
            new_sig = [max(0.02, (sum((e[d] - new_mean[d]) ** 2 for e in elite) / len(elite)) ** 0.5)
                       for d in range(len(keys))]
            mean = [0.3 * m + 0.7 * n for m, n in zip(mean, new_mean)]
            sigma = [0.3 * s + 0.7 * n for s, n in zip(sigma, new_sig)]
            out = from_unit(mean, keys, base)
            with open(args.out, "w") as fh:
                json.dump(out, fh, indent=1, sort_keys=True)
            se = summary["c0"]["se"]
            print(f"gen {gen + 1:>2}/{args.gens}: mean-params {scores[0]:6.2f} (±{se:.2f})  "
                  f"best {scores[order[0]]:6.2f}  elite avg {sum(scores[i] for i in order[:args.elite]) / args.elite:6.2f}  "
                  f"sigma {sum(sigma) / len(sigma):.3f}  ({time.time() - t0:.0f}s)", flush=True)
    finally:
        pool.terminate()
    print(f"saved {args.out}")


if __name__ == "__main__":
    main()

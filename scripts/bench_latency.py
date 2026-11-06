"""Per-decision latency, single process, the way the host measures the 1 ms limit.

    python scripts/bench_latency.py --bundle bundles/nlhe.nlb
    python scripts/bench_latency.py --bundle bundles/nlhe.nlb --no-numpy --gc freeze
    python scripts/bench_latency.py --bundle bundles/nlhe.nlb --gc settle   # as the packaged bot

Aim for p99.9 well under 1 ms on this machine: the host sandbox may be slower.
"""
import argparse
import gc
import json
import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bundle")
    ap.add_argument("--variant", default="nlhe")
    ap.add_argument("--params")
    ap.add_argument("--sngs", type=int, default=60)
    ap.add_argument("--no-numpy", action="store_true")
    ap.add_argument("--gc", choices=("default", "freeze", "off", "settle", "settle-threshold"), default="default")
    args = ap.parse_args()
    if args.no_numpy:
        os.environ["NOLIMIT_NO_NUMPY"] = "1"

    from nolimit.engine import SNG
    from nolimit.runtime import HeuristicTables, PrepBot, Tables, gc_settle, load_tables, np, warmup
    from nolimit.zoo import ZOO

    T = load_tables(path=args.bundle) if args.bundle else load_tables(variant=args.variant)
    warmup(T)              # as the packaged bot does at import (includes the model-size check)
    # Opponents get a private copy (load_tables shares one object), so they never fill our
    # caches: in a real game nobody does.
    T_opp = Tables(open(args.bundle, "rb").read()) if args.bundle else HeuristicTables(args.variant)
    params = json.load(open(args.params)) if args.params else None
    times, pre, post = [], [], []

    class Timed(PrepBot):
        def act(self, obs):
            t0 = time.perf_counter()
            a = PrepBot.act(self, obs)
            dt = (time.perf_counter() - t0) * 1000
            times.append(dt)
            (pre if obs.street == 0 else post).append(dt)
            return a

    if args.gc == "freeze":
        gc.collect()
        gc.freeze()
    elif args.gc == "off":
        gc.disable()
    elif args.gc == "settle":           # what the packaged bot does (adapter: gc_settle())
        gc_settle("off")
    elif args.gc == "settle-threshold":
        gc_settle("threshold")
    bots = []
    for g in range(args.sngs):
        agents = [Timed(T, params, seed=g * 8 + i) for i in range(4)]
        bots += agents
        agents += [ZOO[k](T_opp, seed=g) for k in ("tag", "lag", "shover", "station")]
        random.Random(g).shuffle(agents)
        SNG(T.v, agents, rng=random.Random(g)).run()

    def pct(xs, q):
        xs = sorted(xs)
        return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else 0.0

    hits = sum(a.deadline_hits for a in bots)
    print(f"tables {type(T).__name__}, numpy {'yes' if np is not None else 'no'}, gc {args.gc}, "
          f"{len(times):,} decisions, models {getattr(T, 'net_choice', None)}, "
          f"deadline {PrepBot.deadline * 1000:.2f} ms hit {hits} times")
    for name, xs in (("all", times), ("preflop", pre), ("postflop", post)):
        print(f"  {name:<9} p50 {pct(xs, .5):.4f}  p99 {pct(xs, .99):.4f}  p99.9 {pct(xs, .999):.4f}  "
              f"max {max(xs) if xs else 0:.3f} ms   >0.5ms {sum(x > .5 for x in xs)}  >1ms {sum(x > 1 for x in xs)}")


if __name__ == "__main__":
    main()

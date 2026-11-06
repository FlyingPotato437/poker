"""Paired A/B like scripts/ab_test.py, with the fallback spec bot seatable as 'spec', and the
absolute score (x fair) of A and B printed next to A - B.

    python scripts/ab_spec.py --bundle bundles/nlhe_rng.nlb --a spec --b prep:params/ev_t4.json \\
        --fields github,llm-bugs,rival-real,gate-mixed --sngs 800 --workers 2

'spec' is registered into nolimit.harness.ZOO at import. Pool workers are spawned and re-run
this file's top level as __mp_main__, so they get the registration too, and harness.py stays
unchanged. (The one-line alternative, in harness.py after `ZOO = {**ZOO, **RIVALS}`:
    from fallback.spec_bot import SpecBot; ZOO["spec"] = lambda T, seed=None: SpecBot(T, seed=seed)
)
"""
import argparse
import math
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import nolimit.harness as H  # noqa: E402
from fallback.spec_bot import SpecBot  # noqa: E402


def _spec(tables=None, seed=None):
    return SpecBot(tables, seed=seed)


_REP = {}


def _rep_class(T, name):
    """Bundle hole class of a hand name (via one representative combo)."""
    got = _REP.get(name)
    if got is None:
        R = "23456789TJQKA"
        hi, lo = R.index(name[0]), R.index(name[1])
        off = len(name) == 2 or name[2] == "o"
        got = _REP[name] = T.hole_class((hi * 4, lo * 4 + (1 if off else 0)))
    return got


class _SpecExactPost(SpecBot):
    """Diagnostic: the spec bot with the bundle's postflop equity net instead of the buckets."""

    def post_eq(self, o, n):
        e = self.T.post_equity(o.hole, o.board)
        return e[n - 1] if n <= 3 else e[2] ** (n / 3.0)


class _SpecExactPre(SpecBot):
    """Diagnostic: the spec bot with the bundle's preflop equity-vs-range table instead of the fit."""

    def eqr(self, name, y):
        return self.T.eq_vs_range(_rep_class(self.T, name), y)


class _SpecExactBoth(_SpecExactPost, _SpecExactPre):
    pass


H.ZOO["spec"] = _spec
H.ZOO["spec_xpost"] = lambda tables=None, seed=None: _SpecExactPost(tables, seed=seed)
H.ZOO["spec_xpre"] = lambda tables=None, seed=None: _SpecExactPre(tables, seed=seed)
H.ZOO["spec_xboth"] = lambda tables=None, seed=None: _SpecExactBoth(tables, seed=seed)


def main():
    from ab_test import AB_FIELDS, paired
    from benchmark import PAYOUTS, SCHEDULES, rebundle

    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--a", default="spec")
    ap.add_argument("--b", default="prep:params/ev_t4.json")
    ap.add_argument("--sngs", type=int, default=800)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--fields", default="github,llm-bugs,rival-real,gate-mixed")
    ap.add_argument("--payouts", default="default")
    ap.add_argument("--schedules", default="normal,fast")
    ap.add_argument("--seed", type=int, default=9701)
    ap.add_argument("--no-h2h", action="store_true")
    args = ap.parse_args()

    t0 = time.time()
    tot = {"d": 0.0, "v": 0.0, "n": 0, "a": 0.0, "b": 0.0}
    print(f"A = {args.a}\nB = {args.b}\n{'blinds':<8}{'field':<14}{'A xfair':>9}{'B xfair':>9}"
          f"{'A-B pts':>9}{'±se':>6}{'A-B %fair':>11}   errors A/B")
    for pname in args.payouts.split(","):
        payouts = PAYOUTS[pname]
        fair = sum(payouts) / len(payouts)
        pool = H.make_pool(rebundle(args.bundle, payouts), None, args.workers)
        try:
            for sname in args.schedules.split(","):
                kw = {"payouts": list(payouts), "hands_per_level": SCHEDULES[sname]}
                ea, eb = H.parse_entry(args.a), H.parse_entry(args.b)
                ea["label"], eb["label"] = "A", "B"
                for fname in args.fields.split(","):
                    field = [H.parse_entry(k, w) for k, w in AB_FIELDS[fname].items()]
                    base = H.build_seatings(field, args.sngs, args.seed, fixed=[{"label": "slot"}])
                    games = []
                    for seats, seed in base:
                        for e in (ea, eb):
                            games.append(([e if s.get("label") == "slot" else s for s in seats], seed))
                    rows = H.run_games(games, sng_kw=kw, pool=pool, raw=True)
                    m, se, _n = paired(rows, "A", "B")
                    ra = [r[1] for r in rows if r[0] == "A"]
                    rb = [r[1] for r in rows if r[0] == "B"]
                    xa, xb = sum(ra) / len(ra) / fair, sum(rb) / len(rb) / fair
                    errs = (sum(r[6] for r in rows if r[0] == "A"), sum(r[6] for r in rows if r[0] == "B"))
                    tot["d"] += m / fair
                    tot["v"] += (se / fair) ** 2
                    tot["n"] += 1
                    tot["a"] += xa
                    tot["b"] += xb
                    print(f"{sname:<8}{fname:<14}{xa:>9.3f}{xb:>9.3f}{m:>+9.2f}{se:>6.2f}{100 * m / fair:>+10.1f}%"
                          f"   {errs[0]}/{errs[1]}", flush=True)
                if not args.no_h2h:
                    games = []
                    for g in range(args.sngs // 2):
                        seed = args.seed * 1_000_003 + 500_000 + g
                        seats = [ea, eb] * 4
                        games.append((seats, seed))
                        games.append((seats[1:] + seats[:1], seed))
                    rows = H.run_games(games, sng_kw=kw, pool=pool, raw=True)
                    sa = sum(r[1] for r in rows if r[0] == "A") / (len(games) * 4)
                    print(f"{sname:<8}{'h2h 4v4':<14}{sa / fair:>9.3f}  (A's x fair with 4 A + 4 B)", flush=True)
        finally:
            pool.terminate()
    k = tot["n"]
    print(f"\nmean over {k} cells: A {tot['a'] / k:.3f}x fair, B {tot['b'] / k:.3f}x fair, "
          f"A-B {100 * tot['d'] / k:+.2f}% of fair (±{100 * math.sqrt(tot['v']) / k:.2f})  [{time.time() - t0:.0f}s]")


if __name__ == "__main__":
    main()

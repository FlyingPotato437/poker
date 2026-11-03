"""Robustness matrix: opponent fields x points tables x blind speeds.

    python scripts/benchmark.py --bundle bundles/nlhe.nlb --candidate prep:params/nlhe_full.json
    python scripts/benchmark.py ... --compare prep,heur --sngs 1000 --exploiter params/br.json

For every points table the bundle's push/fold charts and ICM bubble factors are re-solved
first (bundles/bench/*.nlb), the same way they would be on the day. Score is points per
table divided by the fair share (total points / 8): 1.00 = break-even.

The mirror cell seats 8 copies of the candidate in fixed seats and scores each seat on its
own. The average over the 8 seats is 1.00 by construction, so it proves nothing; the
per-seat spread is what tests the simulator for seat bias (expect every seat within ~2 se).
Writes bench/report.md.
"""
import argparse
import hashlib
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from nolimit.harness import build_seatings, make_pool, parse_entry, run_games  # noqa: E402
from nolimit.zoo import DEFAULT_FIELD_MIX  # noqa: E402

PAYOUTS = {
    "default": (100, 65, 45, 30, 20, 12, 6, 0),
    "top-heavy": (100, 40, 20, 10, 5, 0, 0, 0),
    "linear": (7, 6, 5, 4, 3, 2, 1, 0),
    "top-3": (50, 30, 20, 0, 0, 0, 0, 0),
    # Never tuned for: checks of the day-of rule "use the preset nearest the announced points".
    "wta": (1, 0, 0, 0, 0, 0, 0, 0),
    "slope": (10, 8, 6, 5, 4, 3, 2, 1),
}
SCHEDULES = {"normal": 25, "fast": 10}
FIELDS = {
    "zoo": DEFAULT_FIELD_MIX,
    "passive": {"nit": 3, "station": 2, "timeout": 2, "tag": 2},
    "aggressive": {"maniac": 2, "lag": 3, "shover": 3, "jammer": 1, "bully": 1},
    "competent": {"tag": 3, "lag": 2, "trapper": 2, "prep": 3},
}


def rebundle(bundle, payouts):
    tag = hashlib.md5((os.path.abspath(bundle) + str(payouts)).encode()).hexdigest()[:8]
    out = os.path.join(ROOT, "bundles", "bench", f"{os.path.splitext(os.path.basename(bundle))[0]}_{tag}.nlb")
    if not os.path.exists(out) or os.path.getmtime(out) < os.path.getmtime(bundle):
        os.makedirs(os.path.dirname(out), exist_ok=True)
        subprocess.run([sys.executable, "-m", "gpu.pushfold", "--bundle", bundle, "--out", out,
                        "--payouts", ",".join(str(x) for x in payouts)], cwd=ROOT, check=True,
                       capture_output=True)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--candidate", default="prep")
    ap.add_argument("--compare", default="", help="extra bots scored in the same seat, e.g. prep,heur")
    ap.add_argument("--exploiter", help="params JSON of a best-response attacker (adds a field)")
    ap.add_argument("--sngs", type=int, default=600)
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    ap.add_argument("--payouts", default=",".join(PAYOUTS))
    ap.add_argument("--schedules", default=",".join(SCHEDULES))
    ap.add_argument("--out", default=os.path.join(ROOT, "bench", "report.md"))
    args = ap.parse_args()

    bots = [args.candidate] + [b for b in args.compare.split(",") if b]
    fields = dict(FIELDS)
    if args.exploiter:
        fields["exploiter"] = {"prep:" + args.exploiter: 1}
    rows = []
    mirror_notes = []
    t_start = time.time()
    for pname in args.payouts.split(","):
        payouts = PAYOUTS[pname]
        fair = sum(payouts) / 8
        bundle = rebundle(args.bundle, payouts)
        pool = make_pool(bundle, None, args.workers)
        try:
            for sname in args.schedules.split(","):
                kw = {"payouts": list(payouts), "hands_per_level": SCHEDULES[sname]}
                scen = {f: [parse_entry(k, w) for k, w in mix.items()] for f, mix in fields.items()}
                for bot in bots:
                    me = parse_entry(bot)
                    me["label"] = "me"
                    cells = {}
                    for fname, field in scen.items():
                        cells[fname] = run_games(build_seatings(field, args.sngs, 11, fixed=[me]), sng_kw=kw, pool=pool)
                    cells["3 of us + zoo"] = run_games(build_seatings(scen["zoo"], args.sngs, 12, fixed=[me] * 3),
                                                       sng_kw=kw, pool=pool)
                    seats = [dict(me, label=f"seat{i}") for i in range(8)]
                    mir = run_games(build_seatings([me], args.sngs, 13, fixed=seats, shuffle=False),
                                    sng_kw=kw, pool=pool)
                    devs = [(mir[f"seat{i}"]["mean"] - fair) / max(mir[f"seat{i}"]["se"], 1e-9) for i in range(8)]
                    worst_seat = max(range(8), key=lambda i: abs(devs[i]))
                    mirror_notes.append(
                        f"{bot} {pname}/{sname}: seats " + " ".join(f"{mir[f'seat{i}']['mean'] / fair:.2f}" for i in range(8))
                        + f"; worst seat {worst_seat} at {devs[worst_seat]:+.1f} se")
                    print(f"{pname:<10}{sname:<7}{bot:<28}{'mirror seats':<18}{mirror_notes[-1]}", flush=True)
                    for cname, summ in cells.items():
                        s = summ["me"]
                        rows.append((pname, sname, bot, cname, s["mean"] / fair, s["se"] / fair, s["errors"], s["ms_max"]))
                        print(f"{pname:<10}{sname:<7}{bot:<28}{cname:<18}{s['mean'] / fair:6.2f}x ±{s['se'] / fair:.2f}"
                              f"  errors {s['errors']}", flush=True)
        finally:
            pool.terminate()

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    cnames = list(dict.fromkeys(r[3] for r in rows))
    lines = [f"# Benchmark: {args.candidate}", "",
             f"Bundle `{os.path.basename(args.bundle)}`, {args.sngs} SNGs per cell, "
             f"{time.strftime('%Y-%m-%d %H:%M')}. Score = points per table / fair share "
             "(1.00 = break-even).", ""]
    for bot in bots:
        lines += [f"## {bot}", "", "| points | blinds | " + " | ".join(cnames) + " |",
                  "|---|---|" + "---|" * len(cnames)]
        for pname in args.payouts.split(","):
            for sname in args.schedules.split(","):
                cell = {r[3]: r for r in rows if r[0] == pname and r[1] == sname and r[2] == bot}
                lines.append(f"| {pname} | {sname} | " +
                             " | ".join(f"{cell[c][4]:.2f} ±{cell[c][5]:.2f}" for c in cnames) + " |")
        worst = min((r for r in rows if r[2] == bot), key=lambda r: r[4])
        errs = sum(r[6] for r in rows if r[2] == bot)
        lines += ["", f"Worst cell: **{worst[4]:.2f}x** ({worst[0]}, {worst[1]}, {worst[3]}). "
                      f"Errors: {errs}.", ""]
    lines += ["## Seat fairness (8 copies of the candidate, fixed seats)", "",
              "Per-seat score; the mean over seats is 1.00 by construction. A seat beyond ~3 se "
              "would point at a simulator bias.", ""] + [f"- {n}" for n in mirror_notes] + [""]
    with open(args.out, "w") as fh:
        fh.write("\n".join(lines))
    print(f"\nwrote {args.out} ({time.time() - t_start:.0f}s)")


if __name__ == "__main__":
    main()

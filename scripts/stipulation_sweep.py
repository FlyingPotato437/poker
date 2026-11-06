"""Stipulation sweep: how much each rule the organizers might announce moves our score.

    python scripts/stipulation_sweep.py --sngs 300 --workers 4
    python scripts/stipulation_sweep.py --factors players,special --sngs 300 --baseline none
    python scripts/stipulation_sweep.py --candidate prep:params/x.json --baseline prep:params/ev_t4.json \\
        --factors field,points --straddle          # every cell also gets a straddle

One factor at a time around the default (8 players, 100 BB, 25 hands a level, no ante,
200-hand cap, short all-ins don't reopen, default points, rival-real field, NLHE, ICM at
the cap, no special rule). Every cell plays the same seeded seatings with the candidate in
one seat; with a baseline, every SNG is replayed with the baseline in that seat (paired, as
ab_test.py), so A - B has the luck taken out. Any house-rule flag (rules_cli.py) or the base
flags below change the default for every cell.

Score = x-fair: points per table / (table's total points / players). SD is the SD of one
table's x-fair. Push/fold charts are re-solved for each points table, player count and ante
(bundles/bench/), as on the day. The report ranks factors by how far their levels move
x-fair and SD, and flags cells below fair or below the baseline.
Writes bench/sweep/report.md (+ .json with every cell).
"""
import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from benchmark import FIELDS, PAYOUTS  # noqa: E402
from nolimit.engine import DEFAULT_PAYOUTS  # noqa: E402
from nolimit.harness import build_seatings, make_pool, parse_entry, run_games  # noqa: E402
from nolimit.rivals import llm_fields, rival_fields  # noqa: E402
from rules_cli import add_rule_args, rule_kwargs  # noqa: E402

SWEEP_FIELDS = {"zoo": FIELDS["zoo"], **{k: v for k, v in rival_fields().items() if k in
                ("rival-real", "rival-strong", "rival-mid", "rival-strong+prep")},
                "llm-bugs": llm_fields()["llm-bugs"]}        # sealed fields (oos, rvh_*, fresh*) never
VARIANT_SETUP = {          # bundle, candidate params, baseline params (None: same as candidate)
    "shortdeck": ("bundles/shortdeck_rng.nlb", "prep:params/ev_t3.json", None),
    "shortdeck_triton": ("bundles/shortdeck_triton_rng.nlb", "prep:params/ev_t3.json", None),
    "plo4": ("bundles/plo4_rng.nlb", "prep:params/rc1_plo4.json", None),
    "plo5": ("bundles/plo5_rng.nlb", "prep:params/ev_t3.json", None),
    "holdem3": ("bundles/holdem3_rng.nlb", "prep:params/ev_t3.json", None),
    # royal is left out: 20 cards cannot deal 8 hands plus a board.
}
SPECIAL = {
    "none": {},
    "72-bounty": {"bounty_72": 10},
    "72-bounty-noshow": {"bounty_72": 10, "bounty_72_noshow": True},
    "72-bounty-aware": {"bounty_72": 10, "_aware": True},     # candidate wrapped by nolimit/aware.py
    "straddle": {"straddle": True},
    "bomb/10": {"bomb_every": 10, "bomb_bb": 2},
    "run-twice": {"run_twice": True},
    "ko-10pts": {"ko_points": 10},
    "bet-cap-30bb": {"max_bet_bb": 30},
    "3-raise-cap": {"max_raises": 3},
    "dead-button": {"dead_button": True},
    "uneven-stacks": {"stack_spread": 0.5},
}
FACTORS = {      # name: (levels, default)
    "players": ([2, 3, 4, 6, 8, 9, 10], 8),
    "stack_bb": ([25, 50, 100, 200, 300], 100),
    "hands_per_level": ([5, 10, 25, 50], 25),
    "ante": (["0", "0.1bb", "0.25bb", "bb-ante"], "0"),
    "hand_cap": ([100, 200, 400, "none"], 200),
    "reopen_short": (["off", "on"], "off"),
    "points": (list(PAYOUTS), "default"),
    "cap_scoring": (["icm", "chips"], "icm"),
    "field": (["zoo", "rival-real", "rival-strong", "llm-bugs"], "rival-real"),
    "variant": (["nlhe"] + list(VARIANT_SETUP), "nlhe"),
    "special": (list(SPECIAL), "none"),
}


def payouts_for(base, n):
    """An n-place table with the shape of the 8-place one (first and last place kept)."""
    base = list(base)
    if n == len(base):
        return base
    out = []
    for i in range(n):
        x = i * (len(base) - 1) / (n - 1)
        lo = int(math.floor(x))
        hi = min(lo + 1, len(base) - 1)
        out.append(round(base[lo] + (base[hi] - base[lo]) * (x - lo), 2))
    return out


def rebundle(bundle, payouts, ante_bb=0.0, workers=4):
    """Push/fold charts and bubble factors re-solved for these points (and antes), cached."""
    pts8 = (list(payouts) + [0] * 8)[:max(8, len(payouts))]
    tag = hashlib.md5((os.path.abspath(bundle) + str(pts8) + (f"a{ante_bb}" if ante_bb else "")).encode()).hexdigest()[:8]
    out = os.path.join(ROOT, "bundles", "bench", f"{os.path.splitext(os.path.basename(bundle))[0]}_{tag}.nlb")
    if not os.path.exists(out) or os.path.getmtime(out) < os.path.getmtime(bundle):
        os.makedirs(os.path.dirname(out), exist_ok=True)
        cmd = [sys.executable, "-m", "gpu.pushfold", "--bundle", bundle, "--out", out, "--workers", str(workers),
               "--payouts", ",".join(str(x) for x in pts8)]
        if ante_bb:
            cmd += ["--ante-bb", str(ante_bb)]
        subprocess.run(cmd, cwd=ROOT, check=True, capture_output=True)
    return out


def cell_setup(c, args, base_rules):
    """Cell levels -> (bundle, n seats, payouts, sng kwargs, field mix, candidate, baseline)."""
    n = c["players"]
    pts = payouts_for(PAYOUTS[c["points"]], n)
    bb0 = 20
    kw = dict(base_rules)
    kw.update(payouts=pts, hands_per_level=c["hands_per_level"], start_stack=int(c["stack_bb"] * bb0),
              max_hands=10_000 if c["hand_cap"] == "none" else int(c["hand_cap"]))
    ante_pf = kw.get("ante_bb", 0.0)
    if c["ante"] == "0.1bb":
        kw["ante_bb"] = ante_pf = 0.1
    elif c["ante"] == "0.25bb":
        kw["ante_bb"] = ante_pf = 0.25
    elif c["ante"] == "bb-ante":
        kw["bb_ante"] = 1.0
        ante_pf = 1.0 / n                     # the same dead money per player, for push/fold
    if c["reopen_short"] == "on":
        kw["reopen_short"] = True
    if c["cap_scoring"] != "icm":
        kw["cap_scoring"] = c["cap_scoring"]
    sp = dict(SPECIAL[c["special"]])
    aware = sp.pop("_aware", False)
    kw.update(sp)
    if c["variant"] == "nlhe":
        bundle, cand, base = args.bundle, args.candidate, args.baseline
    else:
        bundle, cand, base = VARIANT_SETUP[c["variant"]]
        base = base or cand
    if aware:
        base, cand = cand, cand + "+aware72"     # baseline = the unaware bot, same game
    if base in (None, "none", cand):
        base = None
    return (rebundle(bundle, pts, ante_pf, args.workers), n, pts, kw, SWEEP_FIELDS[c["field"]], cand, base)


def msd(xs):
    m = sum(xs) / len(xs)
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / max(len(xs) - 1, 1))
    return m, sd


def run_cell(c, args, base_rules, pools):
    bundle, n, pts, kw, mix, cand, base = cell_setup(c, args, base_rules)
    if bundle not in pools:
        for p in pools.values():
            p.terminate()
        pools.clear()
        pools[bundle] = make_pool(bundle, None, args.workers)
    pool = pools[bundle]
    field = [parse_entry(k, w) for k, w in mix.items()]
    ea = parse_entry(cand)
    ea["label"] = "A"
    seats_list = build_seatings(field, args.sngs, args.seed, fixed=[{"label": "slot"}], n_seats=n)
    games = []
    entries = [ea]
    if base:
        eb = parse_entry(base)
        eb["label"] = "B"
        entries.append(eb)
    for seats, seed in seats_list:
        for e in entries:
            games.append(([e if s.get("label") == "slot" else s for s in seats], seed))
    t0 = time.time()
    rows = run_games(games, sng_kw=kw, pool=pool, raw=True, chunk=4)
    st = _split_tables(rows, n)
    a = [x for _s, x, _e in st["A"]]
    ma, sda = msd(a)
    res = {"cell": c, "n_seats": n, "payouts": pts, "candidate": cand, "baseline": base, "tables": len(a),
           "xfair": ma, "se": sda / math.sqrt(len(a)), "sd": sda, "errors": sum(e for *_x, e in st["A"]),
           "sec": time.time() - t0, "sd_points": sda * sum(pts) / n}
    if base:
        b = dict((s, x) for s, x, _e in st["B"])
        d = [x - b[s] for s, x, _e in st["A"] if s in b]
        md, sdd = msd(d)
        mb, sdb = msd(list(b.values()))
        res.update(base_xfair=mb, base_se=sdb / math.sqrt(len(b)), base_sd=sdb, diff=md,
                   diff_se=sdd / math.sqrt(len(d)), diff_sd=sdd)
    return res


def _split_tables(rows, n):
    """Group rows into tables. A replay's n rows share a seed and contain exactly one A or B."""
    by = {}
    for r in rows:
        by.setdefault(r[7], []).append(r)
    out = {"A": [], "B": []}
    for seed, rs in by.items():
        # rows of one game are contiguous within a job; a seed has 1 or 2 replays of n rows
        for i in range(0, len(rs), n):
            t = rs[i:i + n]
            fair = sum(r[1] for r in t) / n
            for r in t:
                if r[0] in out:
                    out[r[0]].append((seed, r[1] / fair if fair else 0.0, r[6]))
    return out


def flags(r):
    f = []
    lo, hi = r["xfair"] - 1.96 * r["se"], r["xfair"] + 1.96 * r["se"]
    if hi < 1:
        f.append("**BELOW FAIR**")
    elif r["xfair"] < 1:
        f.append("below fair (ns)")
    if "diff" in r:
        dhi = r["diff"] + 1.96 * r["diff_se"]
        if dhi < 0:
            f.append("**BELOW BASELINE**")
        elif r["diff"] < 0:
            f.append("< baseline (ns)")
    return ", ".join(f)



def write_report(results, args, out, base_rules, t_start):
    default = {k: v[1] for k, v in FACTORS.items()}
    dkey = json.dumps(default, sort_keys=True)
    by_key = {json.dumps(r["cell"], sort_keys=True): r for r in results}
    lines = [f"# Stipulation sweep: {args.candidate}", "",
             f"Baseline `{args.baseline}`; bundle `{os.path.basename(args.bundle)}`; {args.sngs} SNGs per cell "
             f"(paired with the baseline when there is one), seed {args.seed}, "
             f"{time.strftime('%Y-%m-%d %H:%M')}, {time.time() - t_start:.0f}s.",
             "", "Default cell: " + ", ".join(f"{k}={v}" for k, v in default.items())
             + (f"; extra rules on every cell: {base_rules}" if base_rules else "") + ".",
             "", "x-fair = points per table / fair share (1.00 = break-even). SD = SD of one table's x-fair. "
             "A-B = paired candidate minus baseline, % of fair. 95% CI = ±1.96 se. "
             "Flags: **bold** = significant at 95%, (ns) = point estimate only.", ""]
    # ranking
    rank = []
    for f, (levels, dflt) in FACTORS.items():
        cells = []
        for lv in levels:
            c = dict(default, **{f: lv})
            r = by_key.get(json.dumps(c, sort_keys=True))
            if r:
                cells.append((lv, r))
        if len(cells) < 2:
            continue
        xs = [r["xfair"] for _l, r in cells]
        sds = [r["sd"] for _l, r in cells]
        lo = min(cells, key=lambda t: t[1]["xfair"])
        hi = max(cells, key=lambda t: t[1]["xfair"])
        sep = (hi[1]["xfair"] - lo[1]["xfair"]) / math.sqrt(hi[1]["se"] ** 2 + lo[1]["se"] ** 2)
        diffs = [r["diff"] for _l, r in cells if "diff" in r]
        rank.append((f, max(xs) - min(xs), sep, lo, hi, max(sds) - min(sds), min(sds), max(sds),
                     (max(diffs) - min(diffs)) if len(diffs) > 1 else None))
    lines += ["## Factors ranked by how much they move x-fair", "",
              "| rank | factor | x-fair range | range / se | worst level | best level | SD range (min-max) | A-B range |",
              "|---|---|---|---|---|---|---|---|"]
    for i, (f, rng, sep, lo, hi, sdr, sdmin, sdmax, dr) in enumerate(sorted(rank, key=lambda t: -t[1]), 1):
        lines.append(f"| {i} | {f} | {rng:.3f} | {sep:.1f} | {lo[0]} ({lo[1]['xfair']:.3f}) | "
                     f"{hi[0]} ({hi[1]['xfair']:.3f}) | {sdr:.3f} ({sdmin:.2f}-{sdmax:.2f}) | "
                     f"{'' if dr is None else f'{100 * dr:.1f}%'} |")
    lines += ["", "## Factors ranked by score variance (SD per table)", "",
              "| rank | factor | SD min | SD max | max/min | level with max SD |", "|---|---|---|---|---|---|"]
    for i, t in enumerate(sorted(rank, key=lambda t: -(t[7] / max(t[6], 1e-9))), 1):
        f = t[0]
        levels = FACTORS[f][0]
        cells = [(lv, by_key.get(json.dumps(dict(default, **{f: lv}), sort_keys=True))) for lv in levels]
        top = max((c for c in cells if c[1]), key=lambda c: c[1]["sd"])
        lines.append(f"| {i} | {f} | {t[6]:.2f} | {t[7]:.2f} | {t[7] / max(t[6], 1e-9):.2f} | {top[0]} |")
    lines += ["", "## Every cell", "",
              "| factor | level | x-fair | ±se | SD | baseline x-fair | A-B % fair | ±se | flags | tables | errors |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for f, (levels, dflt) in FACTORS.items():
        for lv in levels:
            r = by_key.get(json.dumps(dict(default, **{f: lv}), sort_keys=True))
            if not r:
                continue
            mark = " (default)" if lv == dflt else ""
            b = (f"{r['base_xfair']:.3f} | {100 * r['diff']:+.1f} | {100 * r['diff_se']:.1f}" if "diff" in r
                 else "— | — | —")
            lines.append(f"| {f} | {lv}{mark} | {r['xfair']:.3f} | {r['se']:.3f} | {r['sd']:.2f} | {b} | "
                         f"{flags(r)} | {r['tables']} | {r['errors']} |")
    d = by_key.get(dkey)
    if d:
        fair = sum(d["payouts"]) / d["n_seats"]
        sd_pts = d["sd"] * fair
        lines += ["", "## Sample size (default cell)", "",
                  f"Points SD per SNG for the candidate: {sd_pts:.1f} points ({d['sd']:.2f} x-fair; fair = {fair:.1f})."]
        rows = [("unpaired (one bot's score)", d["sd"])]
        if "diff_sd" in d:
            lines.append(f"Paired A-B SD per SNG: {d['diff_sd']:.2f} x-fair "
                         f"({d['diff_sd'] / d['sd']:.2f} of the unpaired SD).")
            rows.append(("paired A-B (same seats and cards)", d["diff_sd"]))
        lines += ["", "SNGs needed to detect an edge of e (fraction of fair), 95% two-sided; "
                  "'CI' = 95% half-width equals e, '80% power' = (1.96 + 0.84)^2 (SD/e)^2.", "",
                  "| comparison | e=1% CI | e=1% 80% power | e=2% CI | e=2% 80% power | e=5% CI | e=5% 80% power |",
                  "|---|---|---|---|---|---|---|"]
        for name, sd in rows:
            cells = []
            for e in (0.01, 0.02, 0.05):
                cells += [f"{(1.96 * sd / e) ** 2:,.0f}", f"{((1.96 + 0.84) * sd / e) ** 2:,.0f}"]
            lines.append(f"| {name} | " + " | ".join(cells) + " |")
        lines += ["", f"One scored tournament (10,000 SNGs) pins our x-fair to ±{1.96 * d['sd'] / 100:.3f} (95%)."]
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    with open(os.path.splitext(out)[0] + ".json", "w") as fh:
        json.dump(results, fh, indent=1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bundle", default="bundles/nlhe_rng.nlb")
    ap.add_argument("--candidate", default="prep:params/cand_nlhe.json")
    ap.add_argument("--baseline", default="prep:params/ev_t4.json", help="'none' for candidate only")
    ap.add_argument("--sngs", type=int, default=300)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--seed", type=int, default=7301)
    ap.add_argument("--factors", default=",".join(FACTORS))
    ap.add_argument("--levels", action="append", default=[],
                    help="override one factor's levels, e.g. --levels players=6,8 (repeatable)")
    ap.add_argument("--out", default=os.path.join(ROOT, "bench", "sweep", "report.md"))
    ap.add_argument("--resume", action="store_true", help="reuse cells already in the .json next to --out")
    add_rule_args(ap)
    args = ap.parse_args()
    if args.baseline == "none":
        args.baseline = None
    for spec in args.levels:
        f, _, lv = spec.partition("=")
        cast = type(FACTORS[f][1])
        FACTORS[f] = ([x if x == "none" else cast(x) for x in lv.split(",")], FACTORS[f][1])
    base_rules = rule_kwargs(args)
    default = {k: v[1] for k, v in FACTORS.items()}
    cells, seen = [], set()
    for f in args.factors.split(","):
        for lv in FACTORS[f][0]:
            c = dict(default, **{f: lv})
            k = json.dumps(c, sort_keys=True)
            if k not in seen:
                seen.add(k)
                cells.append(c)
    cells.sort(key=lambda c: c != default)          # default first
    results = []
    done = {}
    jpath = os.path.splitext(args.out)[0] + ".json"
    if args.resume and os.path.exists(jpath):
        done = {json.dumps(r["cell"], sort_keys=True): r for r in json.load(open(jpath))}
    pools = {}
    t_start = time.time()
    print(f"{len(cells)} cells x {args.sngs} SNGs ({'paired' if args.baseline else 'candidate only'})", flush=True)
    try:
        for c in cells:
            k = json.dumps(c, sort_keys=True)
            if k in done:
                results.append(done[k])
                continue
            r = run_cell(c, args, base_rules, pools)
            results.append(r)
            diff = f"  A-B {100 * r['diff']:+.1f}% ±{100 * r['diff_se']:.1f}" if "diff" in r else ""
            changed = [f"{f}={c[f]}" for f in c if c[f] != default[f]] or ["default"]
            print(f"{','.join(changed):<28} x-fair {r['xfair']:.3f} ±{r['se']:.3f}  SD {r['sd']:.2f}{diff}"
                  f"  {flags(r)}  [{r['sec']:.0f}s]", flush=True)
            write_report(results, args, args.out, base_rules, t_start)
    finally:
        for p in pools.values():
            p.terminate()
    write_report(results, args, args.out, base_rules, t_start)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()

"""How fast the bot learns its opponents inside one table, and where its edge comes from.

    python scripts/learning_curve.py --a prep:params/cand_nlhe.json --b prep:params/ev_t4.json \\
        --fields github,llm-bugs,rival-real,rival-strong+prep --sngs 400 --seed 9990 --workers 4

Every SNG seats A in one slot and 7 draws from the field; it is replayed with B in the same
slot (same seats, cards and seeds), as in ab_test.py. Per hand-number bucket it reports:

  chips    A's chips won per hand it was dealt in, in big blinds of that hand (blinds rise
           every --hands-per-level hands, so raw chips would overweight late buckets);
  dA-B     paired (A - B) chips per table-hand in bb: the bucket's bb sum difference per SNG,
           divided by the bucket length (a busted seat counts 0), with its standard error;
  lam      A's mean lambda per live opponent seat (exploit rule, after each hand_end), by the
           seat's true class: weak (zoo / rival / LLM-bug / GitHub designs), strong (rival
           designs that play solid poker, gate positional / barrel), prep (our own prepped bots);
  P        the rule's P(exploitable) per class, and its accuracy against the training label
           (exploitable = not a prep bot), with P > 0.5 as the call;
  lvl>0    share of A's decisions played at an exploit level above 0, and the mean level (0-4).

A without an "exploit" block reports chips only. Points per table (A - B) close each field.
Sealed fields (fresh*, held-out*, oos, rvh_*) are refused.
"""
import argparse
import math
import multiprocessing as mp
import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from nolimit import harness  # noqa: E402
from nolimit.engine import DEFAULT_PAYOUTS, SNG  # noqa: E402
from nolimit.runtime import EXPLOIT_LEVELS, _ex_rates  # noqa: E402

BUCKETS = ((1, 25), (26, 50), (51, 100), (101, 200))
STRONG = {"rv_tag", "rv_lag", "rv_gto", "rv_exploit", "rv_icm", "positional", "barrel"}
CLASSES = ("weak", "strong", "prep")
FAIR = sum(DEFAULT_PAYOUTS) / 8


def klass(label):
    if label.startswith(("prep", "heur")):
        return "prep"
    return "strong" if label in STRONG else "weak"


def bucket(h):
    """h is 1-based (hand 1 = the table's first hand)."""
    for i, (lo, hi) in enumerate(BUCKETS):
        if lo <= h <= hi:
            return i
    return len(BUCKETS) - 1


def _p_exploitable(bot, st):
    c = bot._ex_coef
    z = c[0]
    for (a, b), r in zip(c[1], _ex_rates(st)):
        z += r * (a + b * r)
    return 0.0 if z < -30 else 1.0 / (1.0 + math.exp(-z))


def _play(seats, seed, me, sng_kw, track):
    agents = [harness.make_agent(e, seed * 31 + i) for i, e in enumerate(seats)]
    bot = agents[me]
    sng = SNG(harness._W["variant"], agents, rng=random.Random(seed), evaluator=harness._W["tables"].ev, **sng_kw)
    nb = len(BUCKETS)
    chips = [0.0] * nb           # bb won by A per bucket
    dealt = [0] * nb             # hands A was dealt in
    seat_acc = {}                # (bucket, class) -> [n, sumP, sumLam, correct]
    dec = [[0, 0, 0] for _ in range(nb)]   # decisions, at level > 0, sum of levels
    cur = {"b": 0}
    play_hand = sng._play_hand

    def ph(alive):
        b = bucket(sng.hand_no + 1)
        cur["b"] = b
        before = sng.stacks[me]
        play_hand(alive)
        if before > 0:
            chips[b] += (sng.stacks[me] - before) / sng.bb_amt
            dealt[b] += 1
        if track and bot._ex:
            for s, st in enumerate(bot.stats):
                if s == me or not st.hands or sng.stacks[s] <= 0:
                    continue
                p = _p_exploitable(bot, st)
                lam = bot._ex_lam(s)        # what the bot computes anyway (cached on hands)
                k = klass(seats[s]["label"])
                acc = seat_acc.setdefault((b, k), [0, 0.0, 0.0, 0])
                acc[0] += 1
                acc[1] += p
                acc[2] += lam
                acc[3] += (p > 0.5) == (k != "prep")

    sng._play_hand = ph
    if track and bot._ex:
        lvl = bot._ex_level

        def ex_level(obs):
            x = lvl(obs)
            d = dec[cur["b"]]
            d[0] += 1
            d[1] += x > 0
            d[2] += x
            return x

        bot._ex_level = ex_level
    pts = sng.run()
    return {"pts": pts[me], "chips": chips, "dealt": dealt, "seat": seat_acc, "dec": dec}


def _job(job):
    games, sng_kw, ea, eb = job
    out = []
    for seats, seed in games:
        me = next(i for i, s in enumerate(seats) if s.get("label") == "slot")
        ra = _play([ea if i == me else s for i, s in enumerate(seats)], seed, me, sng_kw, True)
        rb = _play([eb if i == me else s for i, s in enumerate(seats)], seed, me, sng_kw, False) if eb else None
        out.append((ra, rb))
    return out


def mean_se(xs):
    n = len(xs)
    m = sum(xs) / n
    v = sum((x - m) ** 2 for x in xs) / max(n - 1, 1)
    return m, math.sqrt(v / n)


def report(fname, res, has_b):
    nb = len(BUCKETS)
    lines = [f"\n== {fname}  ({len(res)} SNGs)"]
    hdr = f"{'hands':<9}{'A chips/hand':>13}{'dealt':>7}"
    if has_b:
        hdr += f"{'B chips/hand':>13}{'dA-B bb/tbl-hand':>18}{'±se':>7}"
    hdr += f"{'lvl>0':>7}{'lvl':>6}"
    for k in CLASSES:
        hdr += f"{'lam ' + k:>12}{'P ' + k:>9}"
    hdr += f"{'acc':>7}{'seat-hands':>11}"
    lines.append(hdr)
    for b, (lo, hi) in enumerate(BUCKETS):
        ca = sum(r[0]["chips"][b] for r in res)
        da = sum(r[0]["dealt"][b] for r in res)
        row = f"{f'{lo}-{hi}':<9}{ca / max(da, 1):>+13.3f}{da / len(res):>7.1f}"
        if has_b:
            cb = sum(r[1]["chips"][b] for r in res)
            db = sum(r[1]["dealt"][b] for r in res)
            m, se = mean_se([(r[0]["chips"][b] - r[1]["chips"][b]) / (hi - lo + 1) for r in res])
            row += f"{cb / max(db, 1):>+13.3f}{m:>+18.3f}{se:>7.3f}"
        nd = sum(r[0]["dec"][b][0] for r in res)
        row += f"{sum(r[0]['dec'][b][1] for r in res) / max(nd, 1):>7.2f}"
        row += f"{sum(r[0]['dec'][b][2] for r in res) / max(nd, 1):>6.2f}"
        tot_n = tot_c = 0
        for k in CLASSES:
            acc = [r[0]["seat"].get((b, k)) for r in res]
            acc = [a for a in acc if a]
            n = sum(a[0] for a in acc)
            tot_n += n
            tot_c += sum(a[3] for a in acc)
            if n:
                row += f"{sum(a[2] for a in acc) / n:>12.2f}{sum(a[1] for a in acc) / n:>9.2f}"
            else:
                row += f"{'-':>12}{'-':>9}"
        row += f"{tot_c / max(tot_n, 1):>7.2f}{tot_n:>11}"
        lines.append(row)
    # whole table
    if has_b:
        m, se = mean_se([r[0]["pts"] - r[1]["pts"] for r in res])
        ca = sum(sum(r[0]["chips"]) for r in res) / len(res)
        cb = sum(sum(r[1]["chips"]) for r in res) / len(res)
        lines.append(f"points A-B per table {m:+.3f} ±{se:.3f} ({100 * m / FAIR:+.1f}% of fair);"
                     f" bb won per table A {ca:+.1f}, B {cb:+.1f}")
    else:
        lines.append(f"points A per table {mean_se([r[0]['pts'] for r in res])[0]:.3f}")
    return lines


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bundle", default="bundles/nlhe_rng.nlb")
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", help="paired comparison bot (e.g. the base params without the exploit block)")
    ap.add_argument("--fields", default="github,llm-bugs,rival-real,rival-strong+prep")
    ap.add_argument("--sngs", type=int, default=400)
    ap.add_argument("--seed", type=int, default=9990)
    ap.add_argument("--hands-per-level", type=int, default=25)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    from ab_test import AB_FIELDS
    from benchmark import rebundle
    t0 = time.time()
    ea = harness.parse_entry(args.a)
    eb = harness.parse_entry(args.b) if args.b else None
    ea["label"] = "A"
    if eb:
        eb["label"] = "B"
    sng_kw = {"hands_per_level": args.hands_per_level}
    print(f"A = {args.a}\nB = {args.b}\nseed {args.seed}, {args.sngs} SNGs per field, "
          f"{args.hands_per_level} hands per level; lam/P/acc/lvl are A's", flush=True)
    allres = []
    with mp.get_context("spawn").Pool(args.workers, initializer=harness._init, initargs=(rebundle(args.bundle, DEFAULT_PAYOUTS), None)) as pool:
        for fname in args.fields.split(","):
            if fname.startswith(("fresh", "held-out")) or "oos" in fname or fname.startswith("rvh"):
                raise SystemExit(f"{fname} is sealed")
            field = [harness.parse_entry(k, w) for k, w in AB_FIELDS[fname].items()]
            assert not any(k.startswith("rvh_") for k in AB_FIELDS[fname]), "sealed styles"
            base = harness.build_seatings(field, args.sngs, args.seed, fixed=[{"label": "slot"}])
            jobs = [(base[i:i + 8], sng_kw, ea, eb) for i in range(0, len(base), 8)]
            res = [r for part in pool.imap_unordered(_job, jobs) for r in part]
            allres += res
            print("\n".join(report(fname, res, eb is not None)), flush=True)
    print("\n".join(report("all fields pooled", allres, eb is not None)))
    print(f"\n[{time.time() - t0:.0f}s]")


if __name__ == "__main__":
    main()

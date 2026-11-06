"""Where the points and chips go at whale tables (opt-in logging; the harness is untouched).

    python scripts/whale_flow.py --bundle bundles/nlhe_rng.nlb --a prep:params/cand_nlhe.json \\
        --b prep:params/ev_t4.json --fields whale1,whale-br --sngs 1500 --seed 9931 --workers 4

Every SNG is played with A and then B in the slot, same opponents, seats and cards (as in
ab_test.py). Per run it reports points per table of the slot, the whale seat(s) and the
drawn ("weak") seats, and a chip-flow matrix: in each hand the chips the losers lost are
split over the winners in proportion to what each won, summed per table. With --stats it
also dumps every seat's stats at hands 25/50/100/150 (JSON lines) for detector studies.
"""
import argparse
import json
import math
import multiprocessing as mp
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from ab_test import AB_FIELDS  # noqa: E402
from benchmark import PAYOUTS, SCHEDULES, rebundle  # noqa: E402
from nolimit import harness  # noqa: E402
from nolimit.engine import SNG  # noqa: E402
from nolimit.harness import build_seatings, parse_entry  # noqa: E402
from nolimit.runtime import EXPLOIT_FEATS, SeatStats, _ex_rates, ingest_history  # noqa: E402

CHECK = (25, 50, 100, 150)


class FlowSNG(SNG):
    def _play_hand(self, alive):
        start = list(self.stacks)
        super()._play_hand(alive)
        d = [e - s for e, s in zip(self.stacks, start)]
        won = sum(x for x in d if x > 0)
        if won > 0:
            for i, x in enumerate(d):
                if x < 0:
                    for j, y in enumerate(d):
                        if y > 0:
                            self.flow[i][j] += -x * y / won
        st = self.obs_stats
        ingest_history(st, self.history)
        h = self.hand_no + 1
        if self.dump is not None and h in CHECK:
            for s in range(self.n):
                if st[s].hands:
                    t = st[s]
                    self.dump.append({"h": h, "seat": s, "hands": t.hands,
                                      "rates": list(_ex_rates(t)), "acts": t.acts, "allin": t.allin,
                                      "minr": t.minr, "vpip_n": t.vpip, "pfr_n": t.pfr, "f3o": t.f3o, "f3f": t.f3f})


def _job(job):
    games, kw, want_stats = job
    out = []
    for seats, seed, tag in games:
        agents = [harness.make_agent(e, seed * 31 + i) for i, e in enumerate(seats)]
        sng = FlowSNG(harness._W["variant"], agents, rng=random.Random(seed), evaluator=harness._W["tables"].ev, **kw)
        sng.flow = [[0.0] * len(seats) for _ in seats]
        sng.obs_stats = [SeatStats() for _ in seats]
        sng.dump = [] if want_stats else None
        pts = sng.run()
        labels = [e["label"] for e in seats]
        dump = sng.dump or []
        for d in dump:
            d["label"] = labels[d["seat"]]
        out.append((tag, seed, labels, pts, sng.flow, dump))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--a", required=True)
    ap.add_argument("--b")
    ap.add_argument("--fields", default="whale1")
    ap.add_argument("--sngs", type=int, default=500)
    ap.add_argument("--seed", type=int, default=9931)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--schedules", default="normal")
    ap.add_argument("--stats", help="write per-seat stat snapshots (JSON lines) here")
    args = ap.parse_args()
    payouts = PAYOUTS["default"]
    fair = sum(payouts) / len(payouts)
    pool = mp.get_context("spawn").Pool(args.workers, initializer=harness._init,
                                        initargs=(rebundle(args.bundle, payouts), None))
    dump_fh = open(args.stats, "w") if args.stats else None
    try:
        for sname in args.schedules.split(","):
            kw = {"payouts": list(payouts), "hands_per_level": SCHEDULES[sname]}
            ents = [("A", parse_entry(args.a))] + ([("B", parse_entry(args.b))] if args.b else [])
            for tag, e in ents:
                e["label"] = tag
            for fname in args.fields.split(","):
                spec, fixed = AB_FIELDS[fname], []
                if isinstance(spec, tuple):
                    spec, fixed = spec[0], [parse_entry(x) for x in spec[1]]
                field = [parse_entry(k, w) for k, w in spec.items()]
                whales = {f["label"] for f in fixed}
                base = build_seatings(field, args.sngs, args.seed, fixed=[{"label": "slot"}] + fixed)
                games = [([e if s.get("label") == "slot" else s for s in seats], seed, tag)
                         for seats, seed in base for tag, e in ents]
                jobs = [(games[i:i + 8], kw, bool(dump_fh)) for i in range(0, len(games), 8)]
                res = [r for part in pool.imap_unordered(_job, jobs) for r in part]
                print(f"\n== {fname} ({sname}), {args.sngs} SNGs, whales {sorted(whales) or '-'}; "
                      f"points per table (x fair) and chips per table won from (+) / lost to (-)")
                for tag, _e in ents:
                    rr = [r for r in res if r[0] == tag]
                    acc = {"us": [], "whale": [], "weak": []}
                    fl = {k: 0.0 for k in ("us<-whale", "us<-weak", "whale<-weak")}
                    for _t, _s, labels, pts, flow, dump in rr:
                        cls = ["us" if lb == tag else "whale" if lb in whales else "weak" for lb in labels]
                        for c in acc:
                            v = [p for p, k in zip(pts, cls) if k == c]
                            if v:
                                acc[c].append(sum(v) / len(v))
                        n = len(labels)
                        for i in range(n):
                            for j in range(n):
                                f = flow[i][j]           # chips i lost to j
                                ci, cj = cls[i], cls[j]
                                if cj == "us" and ci == "whale":
                                    fl["us<-whale"] += f
                                elif ci == "us" and cj == "whale":
                                    fl["us<-whale"] -= f
                                elif cj == "us" and ci == "weak":
                                    fl["us<-weak"] += f
                                elif ci == "us" and cj == "weak":
                                    fl["us<-weak"] -= f
                                elif cj == "whale" and ci == "weak":
                                    fl["whale<-weak"] += f
                                elif ci == "whale" and cj == "weak":
                                    fl["whale<-weak"] -= f
                        if dump_fh:
                            for d in dump:
                                d.update(field=fname, run=tag, sched=sname,
                                         cls="us" if d["label"] == tag else "whale" if d["label"] in whales else "weak")
                                dump_fh.write(json.dumps(d) + "\n")
                    def ms(v):
                        m = sum(v) / max(len(v), 1)
                        se = math.sqrt(sum((x - m) ** 2 for x in v) / max(len(v) - 1, 1) / max(len(v), 1))
                        return f"{m / fair:.3f}x (±{se / fair:.3f})"
                    nt = max(len(rr), 1)
                    print(f"  {tag}={args.a if tag == 'A' else args.b}: us {ms(acc['us'])}  "
                          f"whale/seat {ms(acc['whale']) if acc['whale'] else '-'}  weak/seat {ms(acc['weak'])}"
                          f"   chips/table: us<-whale {fl['us<-whale'] / nt:+.0f}  us<-weak {fl['us<-weak'] / nt:+.0f}"
                          f"  whale<-weak {fl['whale<-weak'] / nt:+.0f}", flush=True)
                if len(ents) == 2:
                    pa = {r[1]: r for r in res if r[0] == "A"}
                    pb = {r[1]: r for r in res if r[0] == "B"}
                    dw = []
                    for k in pa:
                        la, lb_ = pa[k][2], pb[k][2]
                        wa = [p for p, lb in zip(pa[k][3], la) if lb in whales]
                        wb = [p for p, lb in zip(pb[k][3], lb_) if lb in whales]
                        if wa:
                            dw.append(sum(wa) - sum(wb))
                    if dw:
                        m = sum(dw) / len(dw)
                        se = math.sqrt(sum((x - m) ** 2 for x in dw) / max(len(dw) - 1, 1) / len(dw))
                        print(f"  whale points with A minus with B (paired): {m:+.2f} ±{se:.2f} pts/table")
    finally:
        pool.terminate()
        if dump_fh:
            dump_fh.close()


if __name__ == "__main__":
    main()

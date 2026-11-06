"""Validation of event_sim.py policies with real SNGs (called by `event_sim.py --validate`).

For each scenario, a few full events: the practice field and T1..T6 fields drift as in
event_sim.make_world; every tournament is `--sngs` real SNGs on fresh seeds with every
portfolio strategy paired in our seat, so each policy (and the oracle) is scored on real
results. The policy sees its own real tournament score (noisier than 10,000 SNGs: se ~
sqrt(10000/sngs) times larger, and the policy is told so) and the real hand-log stats.
"""
import json
import math
import multiprocessing as mp
import os
import random
import time

import numpy as np

import adapt_matrix as am
import event_sim as es
from nolimit import adapt

SCENARIOS = ("jammer_heavy", "prepped_heavy", "realistic")
HAND_GUESS = 150


def mix_of(v):
    return {a: float(x) for a, x in zip(es.ARCH, v) if x > 1e-9}


def real_round(pool, mix, n, seed, strats):
    games = adapt.make_games(mix, n, seed)
    rows = adapt.run_paired(pool, games, strats, {"hands_per_level": 25})
    pts = np.array([r[2] for r in rows], dtype=float)
    c = {k: sum(r[3][k] for r in rows) for k in adapt._CNT}
    return pts, np.array(adapt.stats_from_counts(c)), sum(r[4] for r in rows)


def main(args, truth, K, sig_t10k):
    strats = list(adapt.PORTFOLIO.values())
    pool = mp.get_context("spawn").Pool(args.workers, initializer=adapt._worker_init, initargs=(am.bundle_path(),))
    out = {"sngs": args.sngs, "events": []}
    t0 = time.time()
    pols = es.policies(args.handoff_thr)
    try:
        for si, scn in enumerate(args.val_scenarios.split(",")):
            for e in range(args.val_events):
                seed = 880000 + 100 * si + e
                rng = random.Random(seed)
                w = es.make_world(rng, None, base=scn, drift_mean=args.drift)
                w["bias"], w["sbias"] = 0.0, np.zeros(7)
                # practice: 1000 hands of cand-only logs (~7 SNGs)
                n_pr = max(1, args.practice_hands // HAND_GUESS) if args.practice_hands else 0
                ps = None
                if n_pr:
                    _, ps, _ = real_round(pool, mix_of(w["fields"][0]), n_pr, seed * 10, strats[:1])
                model_P = truth.payoff(w["fields"])
                cfg = {"sig_t": sig_t10k * math.sqrt(10000 / args.sngs), "sig_b_assumed": 0.05,
                       "practice_hands": args.practice_hands, "practice_score": False}
                # lockstep: each round, every policy picks; real SNGs are played (paired) for the
                # union of picks plus cand; each policy then sees its own real score and the stats.
                ag = {n: {"s": [], "y": [], "st": ([(ps, args.practice_hands)] if ps is not None else []),
                          "state": {"switched": None, "P": model_P}, "played": [], "xs": []} for n in pols}
                real_rounds = []
                for t in range(1, 7):
                    picks = {n: pol(t, K, ag[n]["s"], ag[n]["y"], ag[n]["st"], ag[n]["state"], cfg)
                             for n, pol in pols.items()}
                    need = sorted(set(picks.values()) | {0})
                    pts, st, _ = real_round(pool, mix_of(w["fields"][t]), args.sngs, seed * 10 + t,
                                            [strats[j] for j in need])
                    real = {j: float(pts[:, i].mean() / es.FAIR) for i, j in enumerate(need)}
                    real_rounds.append({es.NAMES[j]: x for j, x in real.items()})
                    for n, j in picks.items():
                        a = ag[n]
                        a["played"].append(j)
                        a["xs"].append(real[j])
                        a["s"].append(j)
                        a["y"].append(real[j])
                        a["st"].append((st, 10 ** 7))
                ev = {"scenario": scn, "drift": w["drift"], "real_rounds": real_rounds,
                      "model_P": model_P[1:].tolist(), "scores": {}, "picks": {}}
                for n, a in ag.items():
                    ev["scores"][n] = es.weighted_score(a["xs"])
                    ev["picks"][n] = [es.NAMES[j] for j in a["played"]]
                # the model's prediction of the same policies' scores
                ev["model_scores"] = {}
                Sm = truth.stats(w["fields"])
                for name, pol in pols.items():
                    xs, _ = es.run_policy(pol, K, model_P, Sm, ps, w, np.random.default_rng(0),
                                          dict(cfg, sig_t=sig_t10k), obs_noise=0.0)
                    ev["model_scores"][name] = es.weighted_score(xs)
                out["events"].append(ev)
                print(f"{scn} event {e} ({w['drift']}): " + "  ".join(
                    f"{n}={ev['scores'][n] - ev['scores']['a_fixed_cand']:+.3f}" for n in pols)
                    + f"  [{time.time() - t0:.0f}s]", flush=True)
                print("   picks: " + "; ".join(f"{n}:{','.join(p)}" for n, p in ev["picks"].items()), flush=True)
                json.dump(out, open(os.path.join(es.OUT, "validation.json"), "w"), indent=1)
    finally:
        pool.terminate()
    lines = [f"# Real-SNG validation ({args.sngs} paired SNGs per tournament, fresh seeds)", "",
             "Each round plays real SNGs for every strategy some policy picked, plus cand, paired. "
             "Gain of each policy vs fixed cand in weighted x-fair, % of fair: real SNGs / payoff model "
             "on the same drifting fields (f_oracle picks by the model here).", "",
             "| scenario | event | drift | " + " | ".join(pols) + " |", "|---|---|---|" + "---|" * len(pols)]
    for i, ev in enumerate(out["events"]):
        b, bm = ev["scores"]["a_fixed_cand"], ev["model_scores"]["a_fixed_cand"]
        lines.append(f"| {ev['scenario']} | {i} | {ev['drift']} | " + " | ".join(
            f"{100 * (ev['scores'][n] - b):+.1f} / {100 * (ev['model_scores'][n] - bm):+.1f}" for n in pols) + " |")
    lines += ["", "Picks per policy (T1..T6):", ""]
    for i, ev in enumerate(out["events"]):
        lines.append(f"- {ev['scenario']} #{i}: " + "; ".join(f"{n}: {','.join(p)}" for n, p in ev["picks"].items()))
    lines += ["", "Real x-fair of the strategies played, per round (model in brackets):", ""]
    for i, ev in enumerate(out["events"]):
        for t, rr in enumerate(ev["real_rounds"]):
            lines.append(f"- {ev['scenario']} #{i} T{t + 1}: " + ", ".join(
                f"{n} {x:.3f} ({ev['model_P'][t][es.NAMES.index(n)]:.3f})" for n, x in rr.items()))
    open(os.path.join(es.OUT, "validation.md"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))

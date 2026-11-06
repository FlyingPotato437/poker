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
    pols = es.policies(0.15)
    try:
        for si, scn in enumerate(SCENARIOS):
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
                P = np.zeros((7, es.J))
                S = np.zeros((7, 7))
                se = np.zeros(7)
                for t in range(1, 7):
                    pts, st, _ = real_round(pool, mix_of(w["fields"][t]), args.sngs, seed * 10 + t, strats)
                    P[t] = pts.mean(0) / es.FAIR
                    S[t] = st
                    se[t] = float(pts[:, 0].std() / math.sqrt(len(pts)) / es.FAIR)
                model_P = truth.payoff(w["fields"])
                cfg = {"sig_t": float(se[1:].mean()), "sig_b_assumed": 0.05, "practice_hands": args.practice_hands,
                       "practice_score": False}
                ev = {"scenario": scn, "drift": w["drift"], "real_P": P[1:].tolist(), "model_P": model_P[1:].tolist(),
                      "stats": S[1:].tolist(), "scores": {}, "picks": {}}
                for name, pol in pols.items():
                    xs, played = es.run_policy(pol, K, P, S, ps, w, np.random.default_rng(0), cfg, obs_noise=0.0)
                    ev["scores"][name] = es.weighted_score(xs)
                    ev["picks"][name] = [es.NAMES[j] for j in played]
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
    lines = [f"# Real-SNG validation ({args.sngs} paired SNGs per tournament, all strategies, fresh seeds)", "",
             "Gain of each policy vs fixed cand in weighted x-fair, % of fair: real SNGs / payoff model "
             "on the same drifting fields.", "",
             "| scenario | event | drift | " + " | ".join(pols) + " |", "|---|---|---|" + "---|" * len(pols)]
    for i, ev in enumerate(out["events"]):
        b, bm = ev["scores"]["a_fixed_cand"], ev["model_scores"]["a_fixed_cand"]
        lines.append(f"| {ev['scenario']} | {i} | {ev['drift']} | " + " | ".join(
            f"{100 * (ev['scores'][n] - b):+.1f} / {100 * (ev['model_scores'][n] - bm):+.1f}" for n in pols) + " |")
    lines += ["", "Real x-fair per strategy, averaged over T1..T6 of each event (model in brackets):", "",
              "| scenario | event | " + " | ".join(es.NAMES) + " |", "|---|---|" + "---|" * es.J]
    for i, ev in enumerate(out["events"]):
        rp, mp_ = np.array(ev["real_P"]).mean(0), np.array(ev["model_P"]).mean(0)
        lines.append(f"| {ev['scenario']} | {i} | " + " | ".join(f"{a:.3f} ({b:.3f})" for a, b in zip(rp, mp_)) + " |")
    open(os.path.join(es.OUT, "validation.md"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))

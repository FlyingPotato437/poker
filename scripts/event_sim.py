"""Simulate the whole event (practice, T1..T6 with weights 1..6) many times and compare
live-adaptation policies.

    python scripts/event_sim.py                       # payoff-model events -> bench/adapt/event_sim.{json,md}
    python scripts/event_sim.py --classifier          # level-2 classifier accuracy by sample size
    python scripts/event_sim.py --validate --workers 4 --sngs 300   # real-SNG events in 3 scenarios

World model (all from bench/adapt/rec_normal_*.json, the paired records of adapt_matrix.py):
* The records are split by seed parity. Half A fits the "truth" payoff model, half B the
  "knowledge" model that policies use (calibration, hypotheses, classifier training), so
  policies carry real estimation error.
* Payoff model: points of strategy j at a table are additive in the opponents' archetypes
  (ridge least squares); a field's x-fair is then linear in the mixture. Hand-log rates are
  modelled the same way (per-seat, per-hand counts), so any mixture, drifted or not, has an
  expected x-fair per strategy and expected opponent stats.
* An event: a base field (a named scenario or a random Dirichlet mixture), a practice field
  F0 and T1..T6 fields, each step drifting a random fraction of seats toward one target
  (bugs fixed, push/fold, prepped code, or another random field).
* Level-1 feedback: our tournament score = true x-fair + a per-event sim-to-real bias
  (common to all strategies) + 10,000-SNG noise. Level-2: the field's aggregate opponent
  stats (+ a per-event stats bias), from N practice hands before T1 and from each tournament.
"""
import argparse
import json
import math
import os
import random
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from nolimit import adapt  # noqa: E402

OUT = os.path.join(ROOT, "bench", "adapt")
FAIR = 34.75
WEIGHTS = np.arange(1, 7, dtype=float)
NAMES = list(adapt.PORTFOLIO)
J = len(NAMES)
ARCH = list(adapt.ARCHETYPES)
AIDX = {a: i for i, a in enumerate(ARCH)}
NUM = ("vpip", "pfr", "post_agg", "allin", "ftb", "sd", "sd")
DEN = ("dealt", "dealt", "post_act", "dealt", "faced", "flop", "dealt")
CNT = adapt._CNT


def vec(mix):
    v = np.zeros(len(ARCH))
    for k, x in mix.items():
        v[AIDX[k]] = x
    return v / v.sum()


def weighted_score(xs):
    """Event score: weighted mean of the six tournament x-fairs (weights 1..6)."""
    xs = np.asarray(xs, dtype=float)
    return float((xs * WEIGHTS).sum() / WEIGHTS.sum())


# ---------------------------------------------------------------- payoff / stats model
class Model:
    """Additive-in-opponents model of points (per strategy) and of hand-log counts per hand."""

    def __init__(self, recs, lam=3.0):
        X = np.zeros((len(recs), len(ARCH)))
        for i, r in enumerate(recs):
            for a in r["opps"]:
                X[i, AIDX[a]] += 1
        Y = np.array([r["pts"] for r in recs], dtype=float)
        H = np.array([max(r["hands"], 1) for r in recs], dtype=float)
        C = np.array([[r["counts"][k] for k in CNT] for r in recs], dtype=float) / H[:, None]
        # ridge toward a common per-seat value: center on the per-seat mean
        A = X.T @ X + lam * np.eye(len(ARCH))
        m = Y.mean(0) / 7.0
        self.beta = m[None, :] + np.linalg.solve(A, X.T @ (Y - 7.0 * m[None, :]))   # A x J
        mc = C.mean(0) / 7.0
        self.gam = mc[None, :] + np.linalg.solve(A, X.T @ (C - 7.0 * mc[None, :]))  # A x CNT
        self.gam = np.maximum(self.gam, 1e-6)
        self.sd_pts = float(Y.std(0).mean())
        self.n = len(recs)

    def payoff(self, w):
        """x-fair per strategy for mixture vector(s) w (A or n x A)."""
        return 7.0 * (np.asarray(w) @ self.beta) / FAIR

    def rates(self, w):
        return 7.0 * (np.asarray(w) @ self.gam)

    def stats(self, w):
        return stats_of(self.rates(w))


def stats_of(c):
    c = np.asarray(c, dtype=float)
    ix = {k: i for i, k in enumerate(CNT)}
    num = np.stack([c[..., ix[k]] for k in NUM], -1)
    den = np.stack([c[..., ix[k]] for k in DEN], -1)
    return num / np.maximum(den, 1e-9)


def noisy_stats(model, w, n_hands, rng):
    """Stats a hand log of n_hands gives: tables drawn from w (~150 hands each), Poisson/binomial counts."""
    if n_hands is None or n_hands <= 0:
        return None
    if n_hands >= 10 ** 6:
        return model.stats(w)
    n_tab = max(1, int(round(n_hands / 150.0)))
    hands = n_hands / n_tab
    tot = np.zeros(len(CNT))
    for _ in range(n_tab):
        comp = rng.multinomial(7, w)
        tot += hands * (comp @ model.gam)
    ix = {k: i for i, k in enumerate(CNT)}
    den = {k: rng.poisson(tot[ix[k]]) for k in set(DEN)}
    num = []
    for k, d in zip(NUM, DEN):
        p = min(tot[ix[k]] / max(tot[ix[d]], 1e-9), 1.0)
        num.append(rng.binomial(den[d], p) / max(den[d], 1))
    return np.array(num)


# ---------------------------------------------------------------- worlds
def make_world(rng, nprng, base=None, drift_mean=0.08):
    """Fields F0 (practice) .. F6 as mixture vectors, plus a description."""
    if base is None:
        if rng.random() < 0.5:
            name = rng.choice(adapt.NAMED)
            mix = vec(adapt.SCENARIOS[name])
        else:
            name = "random"
            mix = vec(adapt.random_mixture(rng))
    else:
        name, mix = base, vec(adapt.SCENARIOS[base])
    kind = rng.choice(["fix", "pushfold", "prep", "random", "none"])
    tgt = vec(adapt.random_mixture(rng)) if kind == "random" else (
        vec(adapt.DRIFT_TARGETS[kind]) if kind != "none" else mix)
    fields = [mix]
    for _ in range(6):
        f = rng.uniform(0, 2 * drift_mean) if kind != "none" else 0.0
        fields.append((1 - f) * fields[-1] + f * tgt)
    return {"base": name, "drift": kind, "fields": np.array(fields)}


# ---------------------------------------------------------------- policies
class Knowledge:
    """What we know before the event: the half-B model, hypotheses, classifier."""

    def __init__(self, model, rng, n_hyp=400, n_train=3000, sizes=(200, 1000, 5000, 10 ** 6)):
        self.m = model
        hyps = [vec(adapt.SCENARIOS[k]) for k in adapt.NAMED]
        self.hyp_names = list(adapt.NAMED) + ["rnd"] * n_hyp
        hyps += [vec(adapt.random_mixture(rng)) for _ in range(n_hyp)]
        self.H = np.array(hyps)
        self.HP = model.payoff(self.H)            # hyp x J
        self.HS = model.stats(self.H)             # hyp x 7
        self.cal = dict(zip(adapt.NAMED, self.HP[:len(adapt.NAMED)]))
        self.ssd = self.HS.std(0) + 1e-6
        self.smu = self.HS.mean(0)
        # classifier: ridge from standardized stats (+ squares) to gains vs cand, per sample size
        nprng = np.random.default_rng(rng.randrange(1 << 30))
        train = [vec(adapt.random_mixture(rng)) for _ in range(n_train)] + \
                [vec(adapt.SCENARIOS[k]) for k in adapt.NAMED] * 20
        W = np.array(train)
        G = model.payoff(W)
        G = G - G[:, :1]
        self.clf = {}
        for n in sizes:
            S = np.array([noisy_stats(model, w, n, nprng) for w in W])
            F = self.feats(S)
            A = F.T @ F + 1.0 * np.eye(F.shape[1])
            self.clf[n] = np.linalg.solve(A, F.T @ G)
        cent = model.stats(np.array([vec(adapt.SCENARIOS[k]) for k in adapt.NAMED]))
        self.cent = (cent - self.smu) / self.ssd
        self.cent_best = np.argmax(model.payoff(np.array([vec(adapt.SCENARIOS[k]) for k in adapt.NAMED])), 1)

    def feats(self, S):
        Z = (np.atleast_2d(S) - self.smu) / self.ssd
        return np.hstack([np.ones((Z.shape[0], 1)), Z, Z ** 2 / 3.0])

    def size_key(self, n):
        return min(self.clf, key=lambda k: abs(math.log(k) - math.log(max(n, 1))))

    def clf_pick(self, s, n, margin=0.0):
        g = (self.feats(s) @ self.clf[self.size_key(n)])[0]
        g[0] = 0.0
        j = int(np.argmax(g))
        return j if g[j] > margin else 0

    def centroid_pick(self, s):
        z = (s - self.smu) / self.ssd
        return int(self.cent_best[int(np.argmin(((self.cent - z) ** 2).sum(1)))])

    def posterior(self, obs_s, obs_y, stats=(), sig_t=0.01, sig_m=0.03, sig_b=0.05, sig_st=0.6):
        """Posterior over hypotheses given level-1 scores (strategy, score) with a common
        unknown bias, and optional level-2 stats [(stats, n_hands)]."""
        ll = np.zeros(len(self.H))
        if obs_s:
            mu = self.HP[:, obs_s]                       # hyp x k
            r = np.asarray(obs_y)[None, :] - mu
            k = len(obs_s)
            S = (sig_t ** 2 + sig_m ** 2) * np.eye(k) + sig_b ** 2 * np.ones((k, k))
            Si = np.linalg.inv(S)
            ll += -0.5 * np.einsum("hi,ij,hj->h", r, Si, r)
        for s, n in stats:
            z = (s - self.HS) / self.ssd
            samp = 1.0 + 1500.0 / max(n, 1)              # small logs are noisier
            ll += -0.5 * (z ** 2).sum(1) / (sig_st ** 2 * samp)
        ll -= ll.max()
        p = np.exp(ll)
        return p / p.sum()

    def bayes_pick(self, post, exclude=None):
        e = post @ self.HP
        if exclude is not None:
            e[exclude] = -np.inf
        return int(np.argmax(e))


def run_policy(policy, K, P, S, practice_stats, world, obs_rng, cfg, obs_noise=None):
    """Play one event. P: 7 x J true x-fair (row 0 = practice field), S: 7 x 7 field stats,
    practice_stats: what the practice log shows (or None). Returns the 6 x-fairs and picks."""
    bias = world["bias"]
    sbias = world["sbias"]
    sig_t = cfg["sig_t"] if obs_noise is None else obs_noise
    stats_obs = []                                      # [(stats, n_hands)]
    obs_s, obs_y = [], []
    if practice_stats is not None:
        stats_obs.append((practice_stats + sbias, cfg["practice_hands"]))
    if cfg["practice_score"]:
        obs_s.append(0)
        obs_y.append(P[0, 0] + bias + obs_rng.normal(0, sig_t))
    played, xs = [], []
    state = {"switched": None, "P": P}
    for t in range(1, 7):
        j = policy(t, K, obs_s, obs_y, stats_obs, state, cfg)
        played.append(j)
        x = P[t, j]
        xs.append(x)
        obs_s.append(j)
        obs_y.append(x + bias + obs_rng.normal(0, sig_t))
        stats_obs.append((S[t] + sbias, 10 ** 7))
    return xs, played


def pol_fixed(j):
    return lambda t, K, s, y, st, state, cfg: j


def pol_oracle(t, K, s, y, st, state, cfg):
    return int(np.argmax(state["P"][t]))


def pol_handoff(thr, alt=1):
    """HANDOFF rule: ship cand for T1; if T1 x-fair is more than thr below cand's calibration
    on the realistic field, switch to the alternative for the rest of the event (once)."""
    def f(t, K, s, y, st, state, cfg):
        if t == 1:
            return 0
        if state["switched"] is None:
            state["switched"] = y[len(s) - (t - 1)] < K.cal["realistic"][0] - thr   # T1's score
        return alt if state["switched"] else 0
    return f


def pol_bayes_l1(t, K, s, y, st, state, cfg):
    return K.bayes_pick(K.posterior(s, y, sig_t=cfg["sig_t"], sig_b=cfg["sig_b_assumed"]))


def pol_explore(t, K, s, y, st, state, cfg):
    """T1 cand; T2 the best alternative by posterior (forced exploration); then greedy Bayes."""
    post = K.posterior(s, y, sig_t=cfg["sig_t"], sig_b=cfg["sig_b_assumed"])
    if t == 1:
        return 0
    if t == 2:
        return K.bayes_pick(post, exclude=[0])
    return K.bayes_pick(post)


def pol_clf(margin):
    """Level-2 classifier: before T1 from practice stats, after each tournament from its stats."""
    def f(t, K, s, y, st, state, cfg):
        if not st:
            return 0
        stats, n = st[-1]
        return K.clf_pick(stats, n, margin)
    return f


def pol_centroid(t, K, s, y, st, state, cfg):
    return K.centroid_pick(st[-1][0]) if st else 0


def pol_bayes_l12(t, K, s, y, st, state, cfg):
    post = K.posterior(s, y, stats=st[-1:], sig_t=cfg["sig_t"], sig_b=cfg["sig_b_assumed"])
    return K.bayes_pick(post)


def policies(thr):
    return {
        "a_fixed_cand": pol_fixed(0),
        "b_fixed_ev_t4": pol_fixed(1),
        "c_handoff_rule": pol_handoff(thr),
        "c2_bayes_L1": pol_bayes_l1,
        "d_classifier_L2": pol_clf(0.01),
        "d2_centroid_L2": pol_centroid,
        "e_explore_L1": pol_explore,
        "g_bayes_L1+L2": pol_bayes_l12,
        "f_oracle": pol_oracle,
    }


# ---------------------------------------------------------------- data
def load_halves(sched="normal"):
    import adapt_matrix as am
    recs, _ = am.load_records(sched)
    a = [r for r in recs if r["seed"] % 2 == 0]
    b = [r for r in recs if r["seed"] % 2 == 1]
    return recs, a, b


def simulate(n_events, seed, truth, K, cfg, thr, base=None):
    rng = random.Random(seed)
    nprng = np.random.default_rng(seed)
    pols = policies(thr)
    res = {k: [] for k in pols}
    picks = {k: [] for k in pols}
    worlds = []
    for e in range(n_events):
        w = make_world(rng, nprng, base=base, drift_mean=cfg["drift_mean"])
        w["bias"] = nprng.normal(0, cfg["sig_b"])
        w["sbias"] = nprng.normal(0, cfg["sig_sbias"], size=7)
        worlds.append({"base": w["base"], "drift": w["drift"]})
        P = truth.payoff(w["fields"])
        S = truth.stats(w["fields"])
        ps = noisy_stats(truth, w["fields"][0], cfg["practice_hands"], np.random.default_rng(seed * 31 + e))
        for name, pol in pols.items():
            obs_rng = np.random.default_rng(seed * 7919 + e)      # same noise for every policy
            xs, played = run_policy(pol, K, P, S, ps, w, obs_rng, cfg)
            res[name].append(weighted_score(xs))
            picks[name].append(played)
    return res, picks, worlds


def summarize(res, worlds):
    names = list(res)
    base = np.array(res["a_fixed_cand"])
    orc = np.array(res["f_oracle"])
    out = {}
    for n in names:
        x = np.array(res[n])
        d = x - base
        out[n] = {"mean": float(x.mean()), "p5": float(np.percentile(x, 5)), "min": float(x.min()),
                  "gain_vs_cand": float(d.mean()), "gain_se": float(d.std() / math.sqrt(len(d))),
                  "worst_vs_cand": float(d.min()), "p5_vs_cand": float(np.percentile(d, 5)),
                  "regret": float((orc - x).mean()),
                  "by_base": {}}
        for b in sorted(set(w["base"] for w in worlds)):
            idx = [i for i, w in enumerate(worlds) if w["base"] == b]
            out[n]["by_base"][b] = float(d[idx].mean())
    return out


def table(summ, title):
    lines = [f"### {title}", "", "| policy | mean | p5 | gain vs cand (±se) | p5 vs cand | worst vs cand | regret vs oracle |",
             "|---|---|---|---|---|---|---|"]
    for n, s in summ.items():
        lines.append(f"| {n} | {s['mean']:.4f} | {s['p5']:.4f} | {100 * s['gain_vs_cand']:+.2f} ±{100 * s['gain_se']:.2f} "
                     f"| {100 * s['p5_vs_cand']:+.2f} | {100 * s['worst_vs_cand']:+.2f} | {100 * s['regret']:.2f} |")
    return lines


def tune_thr(truth, K, cfg, seed):
    best, bt = -1e9, None
    for thr in (0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40):
        rng = random.Random(seed)
        nprng = np.random.default_rng(seed)
        tot = 0.0
        pol = pol_handoff(thr)
        for e in range(300):
            w = make_world(rng, nprng, drift_mean=cfg["drift_mean"])
            w["bias"] = nprng.normal(0, cfg["sig_b"])
            w["sbias"] = nprng.normal(0, cfg["sig_sbias"], size=7)
            ps = noisy_stats(truth, w["fields"][0], cfg["practice_hands"], np.random.default_rng(e + 1))
            xs, _ = run_policy(pol, K, truth.payoff(w["fields"]), truth.stats(w["fields"]), ps, w,
                               np.random.default_rng(e), cfg)
            tot += weighted_score(xs)
        if tot > best:
            best, bt = tot, thr
    return bt


def model_check(recs_a, truth):
    """Additive model vs the direct per-scenario mean of each scenario's own SNGs (half A)."""
    rows = []
    for scn in adapt.SCENARIOS:
        own = [r for r in recs_a if r["scenario"] == scn]
        if not own:
            continue
        direct = np.array([r["pts"] for r in own]).mean(0) / FAIR
        pred = truth.payoff(vec(adapt.SCENARIOS[scn]))
        dd = (direct - direct[0]) - (pred - pred[0])
        rows.append((scn, float(np.abs(direct - pred).max()), float(np.abs(dd).max()),
                     int(np.argmax(direct)), int(np.argmax(pred))))
    return rows


def classifier_eval(truth, K, seed, n_test=600):
    rng = random.Random(seed)
    nprng = np.random.default_rng(seed)
    tests = [("random", vec(adapt.random_mixture(rng))) for _ in range(n_test)]
    tests += [(k, vec(adapt.SCENARIOS[k])) for k in adapt.NAMED for _ in range(10)]
    res = {}
    for n in (200, 1000, 5000, 10 ** 6):
        acc = {"random": [], "named": []}
        reg = {"random": [], "named": []}
        gain = {"random": [], "named": []}
        cacc = {"random": [], "named": []}
        for kind, w in tests:
            p = truth.payoff(w)
            s = noisy_stats(truth, w, n, nprng)
            j = K.clf_pick(s, n, 0.01)
            c = K.centroid_pick(s)
            g = "random" if kind == "random" else "named"
            acc[g].append(j == int(np.argmax(p)))
            cacc[g].append(c == int(np.argmax(p)))
            reg[g].append(p.max() - p[j])
            gain[g].append(p[j] - p[0])
        res[str(n)] = {g: {"acc": float(np.mean(acc[g])), "centroid_acc": float(np.mean(cacc[g])),
                           "regret": float(np.mean(reg[g])), "gain_vs_cand": float(np.mean(gain[g])),
                           "oracle_gain": None} for g in acc}
    for g in ("random", "named"):
        ps = [truth.payoff(w) for kind, w in tests if (kind == "random") == (g == "random")]
        og = float(np.mean([p.max() - p[0] for p in ps]))
        cand_best = float(np.mean([int(np.argmax(p)) == 0 for p in ps]))
        for n in res:
            res[n][g]["oracle_gain"] = og
            res[n][g]["cand_is_best"] = cand_best
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--events", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=4242)
    ap.add_argument("--practice-hands", type=int, default=1000, help="level-2 practice log size before T1 (0 = none)")
    ap.add_argument("--sig-b", type=float, default=0.05, help="sim-to-real bias of our x-fair (common to strategies)")
    ap.add_argument("--drift", type=float, default=0.08, help="mean fraction of seats that switch per step")
    ap.add_argument("--classifier", action="store_true")
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--sngs", type=int, default=300)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--val-events", type=int, default=2)
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    recs, ra, rb = load_halves()
    truth, know_model = Model(ra), Model(rb)
    sig_t = truth.sd_pts / math.sqrt(10000) / FAIR
    K = Knowledge(know_model, random.Random(args.seed + 1))
    print(f"records {len(recs)} (A {len(ra)}, B {len(rb)}); 10k-SNG noise sd {100 * sig_t:.2f}% of fair  "
          f"[{time.time() - t0:.0f}s]", flush=True)
    if args.validate:
        import event_validate
        event_validate.main(args, truth, K, sig_t)
        return
    if args.classifier:
        res = classifier_eval(truth, K, args.seed + 2)
        json.dump(res, open(os.path.join(OUT, "classifier.json"), "w"), indent=1)
        lines = ["| hands in log | field set | classifier picks best | centroid picks best | gain vs cand | "
                 "oracle gain | regret | cand is best |", "|---|---|---|---|---|---|---|---|"]
        for n, d in res.items():
            for g, r in d.items():
                lines.append(f"| {n} | {g} | {100 * r['acc']:.0f}% | {100 * r['centroid_acc']:.0f}% | "
                             f"{100 * r['gain_vs_cand']:+.2f}% | {100 * r['oracle_gain']:+.2f}% | {100 * r['regret']:.2f}% | "
                             f"{100 * r['cand_is_best']:.0f}% |")
        open(os.path.join(OUT, "classifier.md"), "w").write("\n".join(lines) + "\n")
        print("\n".join(lines))
        return
    out = {"model_check": model_check(ra, truth), "sig_t": sig_t, "runs": {}}
    md = ["# Event simulation", "",
          f"Truth model from {len(ra)} SNGs, knowledge model from {len(rb)} (disjoint halves). "
          f"10k-SNG score noise sd = {100 * sig_t:.2f}% of fair. Scores are weighted x-fair (weights 1..6)/21.", "",
          "Model check (additive model vs each scenario's direct mean, half A): max |level error|, "
          "max |error of gain vs cand|, argmax direct / model:", "",
          "| scenario | level err | gain err | best direct | best model |", "|---|---|---|---|---|"]
    for scn, le, de, bd, bm in out["model_check"]:
        md.append(f"| {scn} | {100 * le:.1f}% | {100 * de:.1f}% | {NAMES[bd]} | {NAMES[bm]} |")
    configs = [
        ("main: practice 1000 hands, bias sd 5%, drift 8%/step", dict(practice_hands=args.practice_hands, sig_b=args.sig_b)),
        ("no practice, bias sd 5%", dict(practice_hands=0, sig_b=args.sig_b)),
        ("practice 200 hands", dict(practice_hands=200, sig_b=args.sig_b)),
        ("practice full log (10k SNGs)", dict(practice_hands=10 ** 7, sig_b=args.sig_b)),
        ("no sim-to-real bias", dict(practice_hands=args.practice_hands, sig_b=0.0)),
        ("bias sd 10%", dict(practice_hands=args.practice_hands, sig_b=0.10)),
        ("heavy drift 20%/step", dict(practice_hands=args.practice_hands, sig_b=args.sig_b, drift_mean=0.2)),
    ]
    for title, over in configs:
        cfg = {"sig_t": sig_t, "sig_b": args.sig_b, "sig_b_assumed": 0.05, "drift_mean": args.drift,
               "practice_hands": args.practice_hands, "practice_score": False, "sig_sbias": 0.01}
        cfg.update(over)
        thr = tune_thr(truth, K, cfg, args.seed + 3)
        res, picks, worlds = simulate(args.events, args.seed, truth, K, cfg, thr)
        summ = summarize(res, worlds)
        sw = {n: float(np.mean([len(set(p)) > 1 or p[0] != 0 for p in picks[n]])) for n in picks}
        out["runs"][title] = {"cfg": cfg, "handoff_thr": thr, "summary": summ, "deviates_from_cand": sw}
        md += ["", *table(summ, f"{title} (handoff thr {thr:.2f}, {args.events} events)")]
        md += ["", "Gain vs fixed cand by base field (% of fair): " + ", ".join(
            f"{n}: " + " ".join(f"{b} {100 * v:+.1f}" for b, v in summ[n]["by_base"].items())
            for n in ("c2_bayes_L1", "d_classifier_L2", "g_bayes_L1+L2", "f_oracle"))]
        print(f"{title} [{time.time() - t0:.0f}s]", flush=True)
        print("\n".join(table(summ, title)), flush=True)
    # named scenarios, no randomness in the base: per-scenario policy gains
    cfg = {"sig_t": sig_t, "sig_b": args.sig_b, "sig_b_assumed": 0.05, "drift_mean": args.drift,
           "practice_hands": args.practice_hands, "practice_score": False, "sig_sbias": 0.01}
    thr = out["runs"][configs[0][0]]["handoff_thr"]
    md += ["", "### Per named scenario (main config, 300 events each): gain vs fixed cand, % of fair", "",
           "| scenario | " + " | ".join(policies(thr)) + " |", "|---|" + "---|" * len(policies(thr))]
    per = {}
    for scn in adapt.NAMED:
        res, _, worlds = simulate(300, args.seed + 11, truth, K, cfg, thr, base=scn)
        summ = summarize(res, worlds)
        per[scn] = {n: s["gain_vs_cand"] for n, s in summ.items()}
        md.append(f"| {scn} | " + " | ".join(f"{100 * per[scn][n]:+.1f}" for n in summ) + " |")
    out["per_scenario"] = per
    json.dump(out, open(os.path.join(OUT, "event_sim.json"), "w"), indent=1)
    open(os.path.join(OUT, "event_sim.md"), "w").write("\n".join(md) + "\n")
    print("\n".join(md[-(len(adapt.NAMED) + 4):]))


if __name__ == "__main__":
    main()

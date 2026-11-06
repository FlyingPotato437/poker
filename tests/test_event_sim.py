"""Live-adaptation study: hand-log stats, drift, payoff model, event scoring and policies."""
import os
import random
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

import event_sim as es  # noqa: E402
from nolimit import adapt  # noqa: E402
from nolimit.runtime import CALL, FOLD, POST, RAISE  # noqa: E402


def test_weighted_score():
    assert es.weighted_score([1.0] * 6) == 1.0
    assert abs(es.weighted_score([0, 0, 0, 0, 0, 1.0]) - 6 / 21) < 1e-12
    assert abs(es.weighted_score([1.0, 0, 0, 0, 0, 0]) - 1 / 21) < 1e-12


def test_scenarios_and_drift_are_distributions():
    for mix in adapt.SCENARIOS.values():
        assert abs(sum(mix.values()) - 1) < 1e-9
        assert set(mix) <= set(adapt.ARCHETYPES)
    rng = random.Random(3)
    for _ in range(20):
        w = es.make_world(rng, None, drift_mean=0.2)
        assert w["fields"].shape == (7, len(es.ARCH))
        assert np.allclose(w["fields"].sum(1), 1.0)
        assert (w["fields"] >= 0).all()
    d = adapt.drift({"tag": 1.0}, 0.25, {"jammer": 1.0})
    assert abs(d["tag"] - 0.75) < 1e-12 and abs(d["jammer"] - 0.25) < 1e-12


def test_no_sealed_styles():
    sealed = {"limper", "icmshort", "potcontrol", "adaptive", "chen", "potodds", "bluffy", "brittle"}
    for a in adapt.ARCHETYPES:
        assert a not in sealed and not a.startswith("rvh_")


def test_hand_stats_counts():
    # seat 0 = us. Seat 1 SB, seat 2 BB. Seat 3 raises, 0 calls, 1 folds, 2 calls.
    # Flop: 2 checks, 3 bets, 0 folds, 2 folds facing the bet.
    hist = ((1, 0, POST, 10, False), (2, 0, POST, 20, False),
            (3, 0, RAISE, 60, False), (0, 0, CALL, 60, False), (1, 0, FOLD, 10, False), (2, 0, CALL, 60, False),
            (2, 1, CALL, 0, False), (3, 1, RAISE, 100, False), (0, 1, FOLD, 0, False), (2, 1, FOLD, 0, False))
    acc = adapt.new_counts()
    adapt.hand_stats(hist, {}, 0, acc, board_len=3)
    assert acc["dealt"] == 3                    # seats 1, 2, 3
    assert acc["vpip"] == 2 and acc["pfr"] == 1  # 2 called, 3 raised
    assert acc["post_act"] == 3 and acc["post_agg"] == 1
    assert acc["faced"] == 1 and acc["ftb"] == 1
    assert acc["flop"] == 2 and acc["sd"] == 0
    s = adapt.stats_from_counts(acc)
    assert abs(s[0] - 2 / 3) < 1e-12 and abs(s[4] - 1.0) < 1e-12


def _synthetic_recs(n=4000, seed=0):
    """cand scores 2.0 vs everyone; ev_t4 beats cand only vs prepped bots."""
    rng = random.Random(seed)
    recs = []
    for g in range(n):
        opps = rng.choices(["tag", "prep_ev_t4", "station"], k=7)
        k = opps.count("prep_ev_t4")
        pts = [es.FAIR * (2.0 - 0.15 * k)] * es.J
        pts[1] = es.FAIR * (1.9 - 0.05 * k)
        pts = [p + rng.gauss(0, 1) for p in pts]
        cnt = adapt.new_counts()
        for key in cnt:
            cnt[key] = 100
        cnt["vpip"] = 20 + 8 * opps.count("station")
        recs.append({"opps": opps, "pts": pts, "counts": cnt, "hands": 100, "seed": g})
    return recs


def test_model_recovers_linear_payoffs():
    m = es.Model(_synthetic_recs())
    w_tag = es.vec({"tag": 1})
    w_prep = es.vec({"prep_ev_t4": 1})
    assert abs(m.payoff(w_tag)[0] - 2.0) < 0.02
    assert abs(m.payoff(w_prep)[0] - (2.0 - 1.05)) < 0.02
    assert m.payoff(w_prep)[1] > m.payoff(w_prep)[0]
    assert m.stats(es.vec({"station": 1}))[0] > m.stats(w_tag)[0]


def test_policies_on_synthetic_world():
    m = es.Model(_synthetic_recs())
    K = es.Knowledge(m, random.Random(1), n_hyp=50, n_train=200, sizes=(1000, 10 ** 6))
    fields = np.array([es.vec({"prep_ev_t4": 0.8, "tag": 0.2})] * 7)
    world = {"fields": fields, "bias": 0.0, "sbias": np.zeros(7), "base": "x", "drift": "none"}
    P, S = m.payoff(fields), m.stats(fields)
    cfg = {"sig_t": 0.01, "sig_b_assumed": 0.05, "practice_hands": 0, "practice_score": False}
    pols = es.policies(0.15)
    xs, played = es.run_policy(pols["a_fixed_cand"], K, P, S, None, world, np.random.default_rng(0), cfg)
    assert played == [0] * 6
    xs_o, played_o = es.run_policy(pols["f_oracle"], K, P, S, None, world, np.random.default_rng(0), cfg)
    assert played_o == [1] * 6 and es.weighted_score(xs_o) > es.weighted_score(xs)
    # L1 Bayes: after T1 the scores identify the prepped field; ev_t4 from T2 on
    _, played_b = es.run_policy(pols["c2_bayes_L1"], K, P, S, None, world, np.random.default_rng(0), cfg)
    assert all(j == 1 for j in played_b[1:])
    # HANDOFF rule: T1 x-fair below the realistic calibration by > thr -> switch once, stay
    K.cal["realistic"] = np.full(es.J, 2.0)
    _, played_h = es.run_policy(pols["c_handoff_rule"], K, P, S, None, world, np.random.default_rng(0), cfg)
    assert played_h == [0, 1, 1, 1, 1, 1]

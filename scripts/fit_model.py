"""Fit PrepBot's opponent model to data: range-reading and fold-response parameters.

    python scripts/fit_model.py --bundle bundles/nlhe_rng.nlb --params params/nlhe_final.json --out params/model.json

The EV engine leans on two predictions: our equity against each opponent's range, and
how often an opponent continues against a bet of a given size. Both can be checked
against ground truth in simulation (the simulator knows every hole card), so instead of
searching them by tournament score this script logs (situation, truth) pairs and fits:

  range params (rng_*):          least squares, predicted equity vs range against true
                                 equity vs the opponent's actual cards
  response params (cont_*):      log loss, predicted continue probability against
                                 whether the opponent actually continued

Fit on --field, report calibration on --holdout (styles the fit never saw). Writes
--params updated with the fitted values to --out.
"""
import argparse
import collections
import copy
import json
import math
import multiprocessing as mp
import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from nolimit.engine import SNG  # noqa: E402
from nolimit.harness import parse_entry  # noqa: E402
import numpy as np  # noqa: E402

from nolimit.runtime import FOLD, PARAM_SPACE, PO_REF, RAISE, PrepBot, load_tables  # noqa: E402
from nolimit.zoo import DEFAULT_FIELD_MIX, HELD_OUT, ZOO  # noqa: E402

RANGE_KEYS = ("rng_y_scale", "rng_bet_scale", "rng_check_cap", "rng_call_cut", "rng_persist")
_W = {}


def _init(bundle, params):
    _W["T"] = load_tables(path=bundle)
    _W["p"] = params
    _W["rs"] = random.Random(5)


def true_eq(T, hero, vill, board, rs):
    v = T.v
    need = v.n_board - len(board)
    dead = set(hero) | set(vill) | set(board)
    deck = [c for c in range(v.D) if c not in dead]
    if need == 0:
        outs = [()]
    elif need == 1:
        outs = [(c,) for c in deck]
    else:
        outs = [tuple(rs.sample(deck, need)) for _ in range(60)]
    tot = 0.0
    for o in outs:
        b = tuple(board) + o
        a, c = T.ev.best(hero, b), T.ev.best(vill, b)
        tot += 1.0 if a > c else 0.5 if a == c else 0.0
    return tot / len(outs)


class Logger(PrepBot):
    """PrepBot that records oracle rows and the decisions whose responses we score."""

    def act(self, obs):
        self.trace = None
        a = PrepBot.act(self, obs)
        if obs.street == 0 or not self.trace:
            return a
        T = self.T
        for s, (_y, _lo, _hi, ag) in self.trace["rngs"].items():
            st = copy.copy(self.stats[s])
            self.out_eq.append((tuple(obs.hole), tuple(obs.board), obs.history, s, st, obs.street,
                                true_eq(T, obs.hole, self.sng.hole[s], obs.board, _W["rs"])))
        if a[0] == RAISE:
            pend = []
            for s in self.trace["rngs"]:
                if obs.stacks[s] == 0:
                    continue
                d = max(min(a[1], obs.stacks[s] + obs.bets[s]) - obs.bets[s], 0)
                if d <= 0:
                    continue
                pot_after = obs.pot + a[1] - obs.bets[obs.seat]
                _y, lo, hi, ag = self.trace["rngs"][s]
                pend.append((s, copy.copy(self.stats[s]), d / max(pot_after + d, 1), ag, (lo + hi) / 2,
                             (tuple(obs.hole), tuple(obs.board), obs.history, obs.street, self.trace["rngs"][s]),
                             true_eq(self.T, obs.hole, self.sng.hole[s], obs.board, _W["rs"])))
            self.pending.append((obs.hand_no, len(obs.history), obs.street, pend))
        return a

    def observe(self, event):
        PrepBot.observe(self, event)
        _kind, info = event
        hist = info["history"]
        for hand_no, n_hist, street, pend in self.pending:
            if hand_no != info["hand_no"]:
                continue
            after = [h for h in hist[n_hist + 1:] if h[1] == street]
            for s, st, po, ag, mid, ctx, teq in pend:
                resp = [h for h in after if h[0] == s]
                if resp:
                    self.out_resp.append((st, po, ag, mid, 0.0 if resp[0][2] == FOLD else 1.0, ctx, teq))
        self.pending = [x for x in self.pending if x[0] != info["hand_no"]]


def _sim(job):
    names, seed = job
    T, p = _W["T"], _W["p"]
    hero = Logger(T, p, seed=seed, debug=True)
    hero.out_eq, hero.out_resp, hero.pending = [], [], []
    agents = [hero] + [ZOO[k](T, seed=seed * 7 + i) for i, k in enumerate(names)]
    rng = random.Random(seed)
    order = list(range(8))
    rng.shuffle(order)
    seated = [agents[i] for i in order]
    sng = SNG(T.v, seated, rng=random.Random(seed))
    hero.sng = sng
    sng.run()
    return hero.out_eq, hero.out_resp


def collect(pool, mix, n, seed):
    rng = random.Random(seed)
    keys, w = list(mix), list(mix.values())
    jobs = [([rng.choices(keys, w)[0] for _ in range(7)], seed * 100_000 + g) for g in range(n)]
    eq_rows, resp_rows = [], []
    for e, r in pool.imap_unordered(_sim, jobs, chunksize=4):
        eq_rows += e
        resp_rows += r
    return eq_rows, resp_rows


# ---------------------------------------------------------------------------
def eq_preds(T, base, rows, vals):
    p = dict(base)
    p.update(vals)
    bot = PrepBot(T, p)
    out = []
    for hole, board, hist, s, st, street, _t in rows:
        bot.stats = collections.defaultdict(lambda: st)
        bot.stats[s] = st
        y = bot._pre_y(s, hist)
        a, b, _ag = bot._post_slice(s, hist, street)
        out.append(T.interval_equity(T.post_curve(hole, board), y, a, b))
    return out


def eq_loss(T, base, rows, vals):
    pr = eq_preds(T, base, rows, vals)
    return sum((x - r[6]) ** 2 for x, r in zip(pr, rows)) / len(rows)


def fit_range(T, base, rows, rounds=3):
    """Coordinate search on an 11-point grid per parameter (the loss is cheap but not smooth)."""
    vals = {k: base[k] for k in RANGE_KEYS}
    best = eq_loss(T, base, rows, vals)
    for _ in range(rounds):
        for k in RANGE_KEYS:
            lo, hi = PARAM_SPACE[k]
            for x in [lo + (hi - lo) * i / 10 for i in range(11)]:
                trial = dict(vals, **{k: x})
                loss = eq_loss(T, base, rows, trial)
                if loss < best:
                    best, vals = loss, trial
    return vals, best


RESP_KEYS = ("cont_b0", "cont_b1", "cont_b2", "cont_b3", "cont_b4")


def resp_x(rows):
    X = []
    for st, po, ag, mid, *_rest in rows:
        c0 = min(max(1.0 - st.rate("fold_ab" if ag else "fold_nb"), 0.01), 0.99)
        X.append([1.0, math.log(c0 / (1 - c0)), math.log(max(po, 0.01) / PO_REF), float(ag), mid])
    return np.array(X), np.array([r[4] for r in rows])


def resp_pred(rows, beta):
    X, _y = resp_x(rows)
    return 1.0 / (1.0 + np.exp(-(X @ np.asarray(beta))))


def resp_loss(rows, beta):
    _X, y = resp_x(rows)
    c = np.clip(resp_pred(rows, beta), 1e-6, 1 - 1e-6)
    return float(-(y * np.log(c) + (1 - y) * np.log(1 - c)).mean())


def fit_resp(rows, l2=1e-3, iters=50):
    """Logistic regression by Newton's method; returns the five cont_b* coefficients."""
    X, y = resp_x(rows)
    beta = np.array([0.0, 1.0, -0.7, 0.0, 0.0])
    for _ in range(iters):
        c = 1.0 / (1.0 + np.exp(-(X @ beta)))
        g = X.T @ (c - y) / len(y) + l2 * beta
        H = (X.T * (c * (1 - c))) @ X / len(y) + l2 * np.eye(len(beta))
        step = np.linalg.solve(H, g)
        beta -= step
        if np.abs(step).max() < 1e-7:
            break
    lo = [PARAM_SPACE[k][0] for k in RESP_KEYS]
    hi = [PARAM_SPACE[k][1] for k in RESP_KEYS]
    return [float(min(max(b, l), h)) for b, l, h in zip(beta, lo, hi)]


def caller_preds(T, base, rows, beta, width):
    """Predicted equity vs the opponents who did continue, against their actual cards."""
    p = dict(base, call_width=width, **dict(zip(RESP_KEYS, beta)))
    bot = PrepBot(T, p)
    out = []
    for st, po, ag, _mid, yv, (hole, board, _hist, _street, rng), teq in rows:
        if not yv:
            continue
        bot.stats = collections.defaultdict(lambda: st)
        c = bot._cont(0, po, rng)
        y, a, b, _ag = rng
        out.append((T.interval_equity(T.post_curve(hole, board), y, a, a + (b - a) * min(1.0, c * width)), teq))
    return out


def fit_width(T, base, rows, beta):
    best = (1.0, 1e9)
    for w in [0.5 + 0.1 * i for i in range(21)]:
        pr = caller_preds(T, base, rows, beta, w)
        loss = sum((a - b) ** 2 for a, b in pr) / max(len(pr), 1)
        if loss < best[1]:
            best = (w, loss)
    return best[0]


def calib_report(label, preds, truth):
    lines = [f"  {label}: n={len(preds)} mean pred {sum(preds) / len(preds):.3f} true "
             f"{sum(truth) / len(truth):.3f}  MAE {sum(abs(a - b) for a, b in zip(preds, truth)) / len(preds):.3f}"]
    for lo, hi in ((0, .2), (.2, .4), (.4, .6), (.6, .8), (.8, 1.01)):
        sel = [(a, b) for a, b in zip(preds, truth) if lo <= a < hi]
        if sel:
            lines.append(f"      [{lo:.1f},{hi:.1f}) n={len(sel):5d} pred {sum(a for a, _ in sel) / len(sel):.3f} "
                         f"true {sum(b for _, b in sel) / len(sel):.3f}")
    return "\n".join(lines)


def resp_report(label, rows, beta):
    pr = resp_pred(rows, beta)
    by = collections.defaultdict(lambda: [0, 0.0, 0.0])
    for r, c in zip(rows, pr):
        po, ag, y = r[1], r[2], r[4]
        key = ("raise after bet" if ag else "bet") + (" small" if po < 0.25 else " medium" if po < 0.36 else " big")
        b = by[key]
        b[0] += 1
        b[1] += c
        b[2] += y
    out = [f"  {label} (beta {', '.join(f'{b:.2f}' for b in beta)}):"]
    for key in sorted(by):
        n, pc, yc = by[key]
        out.append(f"      {key:<24} n={n:5d} pred continue {pc / n:.3f} actual {yc / n:.3f}")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--params", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sngs", type=int, default=300)
    ap.add_argument("--field", default="zoo", help="'zoo' (default mix) or name=w,... of zoo styles to fit on")
    ap.add_argument("--holdout", default=",".join(HELD_OUT))
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    ap.add_argument("--max-eq-rows", type=int, default=12000)
    args = ap.parse_args()

    with open(args.params) as fh:
        base = json.load(fh)
    from nolimit.runtime import DEFAULT_PARAMS
    full = dict(DEFAULT_PARAMS, **base)
    mix = dict(DEFAULT_FIELD_MIX) if args.field == "zoo" else {
        k: float(w or 1) for k, _, w in (x.partition("=") for x in args.field.split(","))}
    hold = {k: 1.0 for k in args.holdout.split(",")}
    T = load_tables(path=args.bundle)
    t0 = time.time()
    pool = mp.get_context("spawn").Pool(args.workers, initializer=_init, initargs=(args.bundle, full))
    try:
        eq_fit, resp_fit = collect(pool, mix, args.sngs, 1)
        eq_ho, resp_ho = collect(pool, hold, args.sngs, 2)
    finally:
        pool.terminate()
    rs = random.Random(0)
    if len(eq_fit) > args.max_eq_rows:
        eq_fit = rs.sample(eq_fit, args.max_eq_rows)
    if len(eq_ho) > args.max_eq_rows:
        eq_ho = rs.sample(eq_ho, args.max_eq_rows)
    print(f"collected {len(eq_fit)}+{len(eq_ho)} equity rows, {len(resp_fit)}+{len(resp_ho)} responses "
          f"({time.time() - t0:.0f}s)", flush=True)

    before = {k: full[k] for k in RANGE_KEYS}
    vals, loss = fit_range(T, full, eq_fit)
    print("range params:", {k: round(v, 3) for k, v in vals.items()}, f"(was {before})")
    for name, rows in (("fit field", eq_fit), ("held-out", eq_ho)):
        truth = [r[6] for r in rows]
        print(calib_report(name + " before", eq_preds(T, full, rows, before), truth))
        print(calib_report(name + " after ", eq_preds(T, full, rows, vals), truth))

    b0 = [full[k] for k in RESP_KEYS]
    beta = fit_resp(resp_fit)
    print(f"response params: {dict(zip(RESP_KEYS, (round(b, 3) for b in beta)))}; log loss fit "
          f"{resp_loss(resp_fit, b0):.4f} -> {resp_loss(resp_fit, beta):.4f}, held-out "
          f"{resp_loss(resp_ho, b0):.4f} -> {resp_loss(resp_ho, beta):.4f}")
    print(resp_report("held-out before", resp_ho, b0))
    print(resp_report("held-out after ", resp_ho, beta))
    full_fit = dict(full, **vals)
    w0 = full["call_width"]
    width = fit_width(T, full_fit, resp_fit, beta)
    print(f"call_width {width:.2f} (was {w0:.2f})")
    for name, rows in (("fit field", resp_fit), ("held-out", resp_ho)):
        for tag, b, w in (("before", b0, w0), ("after ", beta, width)):
            pr = caller_preds(T, full_fit if tag != "before" else full, rows, b, w)
            print(calib_report(f"{name} eq vs callers {tag}", [a for a, _ in pr], [t for _, t in pr]))

    out = dict(base)
    out.update(vals)
    out.update(zip(RESP_KEYS, beta))
    out["call_width"] = width
    out["raise_cont"] = 1.0
    with open(args.out, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print(f"wrote {args.out} ({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()

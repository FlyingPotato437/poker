"""Run many SNGs in parallel and score bots the way the organizers do (avg points per table)."""
import json
import math
import multiprocessing as mp
import os
import random

# Sim workers each run tiny matmuls; a multi-threaded BLAS per worker oversubscribes the
# CPU (load 50+ on 8 cores measured). Spawned workers inherit this before importing numpy.
for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_var, "1")

from .engine import SNG
from .runtime import HeuristicTables, PrepBot, Tables, load_tables
from .rivals import RIVALS
from .zoo import ZOO

ZOO = {**ZOO, **RIVALS}      # rival-team designs are entries like any zoo style

_W = {}


def _nets(tables):
    """NOLIMIT_NETS=small|big picks the model size for the whole run (default: big with numpy)."""
    if os.environ.get("NOLIMIT_NETS") and hasattr(tables, "select_nets"):
        tables.select_nets(os.environ["NOLIMIT_NETS"])
    return tables


def _init(bundle, variant):
    # The per-decision deadline depends on machine load; off in simulations so the same seed
    # always plays the same game. NOLIMIT_SIM_DEADLINE_MS turns it on to measure its cost.
    PrepBot.deadline = float(os.environ.get("NOLIMIT_SIM_DEADLINE_MS", "1e9")) / 1000.0
    _W["tables"] = _nets(load_tables(path=bundle) if bundle else load_tables(variant=variant))
    _W["bundle"] = bundle
    _W["heur"] = None
    _W["variant"] = _W["tables"].v


def parse_entry(spec, weight=1.0):
    """'prep' | 'prep:params.json' | 'heur' | 'heur:params.json' | zoo name ('tag', 'nit', ...).

    A prep entry can carry its own tables with '@bundle.nlb' (prep@b.nlb,
    prep:p.json@b.nlb) to A/B bundles; everyone else uses the run's --bundle.
    A '#small' or '#big' suffix picks that entry's model size (prep:p.json#small).
    """
    spec, _, nets = spec.partition("#")
    spec, _, bundle = spec.partition("@")
    tag = "@" + os.path.splitext(os.path.basename(bundle))[0] if bundle else ""
    if nets:
        tag += "#" + nets
    if spec == "prep":
        return {"label": "prep" + tag, "kind": "prep", "params": None, "weight": weight,
                "bundle": bundle or None, "nets": nets or None}
    if spec.startswith("prep:"):
        path = spec[5:]
        with open(path) as fh:
            params = json.load(fh)
        label = "prep:" + os.path.splitext(os.path.basename(path))[0] + tag
        return {"label": label, "kind": "prep", "params": params, "weight": weight,
                "bundle": bundle or None, "nets": nets or None}
    if spec == "heur" or spec.startswith("heur:"):    # heuristic tables, e.g. a day-of v0
        params = json.load(open(spec[5:])) if spec.startswith("heur:") else None
        label = "heur:" + os.path.splitext(os.path.basename(spec[5:]))[0] if params is not None else "heur"
        return {"label": label, "kind": "heur", "params": params, "weight": weight}
    if spec in ZOO:
        return {"label": spec, "kind": "zoo:" + spec, "params": None, "weight": weight}
    raise ValueError(f"unknown agent spec {spec!r}")


def make_agent(entry, seed):
    kind = entry["kind"]
    if kind == "prep":
        tables = _nets(load_tables(path=entry["bundle"])) if entry.get("bundle") else _W["tables"]
        if entry.get("nets"):
            key = ("nets", entry.get("bundle") or _W["bundle"], entry["nets"])
            if key not in _W:
                # A private copy: load_tables() hands out one shared object per bundle.
                _W[key] = Tables(open(key[1], "rb").read()) if key[1] else HeuristicTables(_W["variant"])
                _W[key].select_nets(entry["nets"])
            tables = _W[key]
        return PrepBot(tables, entry.get("params"), seed=seed)
    if kind == "heur":
        if _W["heur"] is None:
            _W["heur"] = HeuristicTables(_W["variant"])
        return PrepBot(_W["heur"], entry.get("params"), seed=seed)
    return ZOO[kind[4:]](_W["tables"], seed=seed)


def _run_job(job):
    games, sng_kw = job[0], job[1]
    log_labels = job[2] if len(job) > 2 else None
    out = []
    logs = []
    for seats, seed in games:
        agents = [make_agent(e, seed * 31 + i) for i, e in enumerate(seats)]
        kw = dict(sng_kw, log_hands=True) if log_labels else sng_kw
        sng = SNG(_W["variant"], agents, rng=random.Random(seed), evaluator=_W["tables"].ev, **kw)
        pts = sng.run()
        for i, e in enumerate(seats):
            tm = sng.timing[i]
            out.append((e["label"], pts[i], tm.count, tm.total, tm.max, tm.over, sng.errors[i], seed))
        if log_labels:
            for r in sng.hand_log:
                lab = seats[r["seat"]]["label"]
                if lab in log_labels:
                    logs.append(dict(r, label=lab, sng_seed=seed, points=pts[r["seat"]]))
    return (out, logs) if log_labels else out


def build_seatings(field, n_sngs, seed, fixed=(), n_seats=8, shuffle=True):
    """Each SNG seats `fixed` entries plus weighted random draws from `field`.

    shuffle=False keeps `fixed` in seat order (for per-seat fairness checks)."""
    rng = random.Random(seed)
    weights = [e.get("weight", 1.0) for e in field]
    games = []
    for g in range(n_sngs):
        seats = list(fixed) + rng.choices(field, weights=weights, k=n_seats - len(fixed))
        if shuffle:
            rng.shuffle(seats)
        games.append((seats, seed * 1_000_003 + g))
    return games


def make_pool(bundle=None, variant=None, workers=None):
    return mp.get_context("spawn").Pool(workers or os.cpu_count(), initializer=_init,
                                        initargs=(bundle, variant))


def run_games(games, bundle=None, variant=None, workers=None, sng_kw=None, chunk=8, pool=None, raw=False,
              log_labels=None):
    """log_labels: per-hand records (engine log_hands) for the seats with these labels; then
    returns (result, records). Off by default, so plain runs pay nothing for it."""
    sng_kw = sng_kw or {}
    if log_labels:
        jobs = [(games[i:i + chunk], sng_kw, tuple(log_labels)) for i in range(0, len(games), chunk)]
    else:
        jobs = [(games[i:i + chunk], sng_kw) for i in range(0, len(games), chunk)]
    workers = workers or os.cpu_count()
    if pool is not None:
        parts = list(pool.imap_unordered(_run_job, jobs))
    elif workers <= 1:
        _init(bundle, variant)
        parts = [_run_job(j) for j in jobs]
    else:
        with make_pool(bundle, variant, workers) as p:
            parts = list(p.imap_unordered(_run_job, jobs))
    if log_labels:
        rows = [r for part, _ in parts for r in part]
        logs = [r for _, lg in parts for r in lg]
        return (rows if raw else summarize(rows)), logs
    rows = [r for part in parts for r in part]
    return rows if raw else summarize(rows)


def summarize(rows):
    acc = {}
    for label, pts, cnt, tot, mx, over, err, _seed in rows:
        a = acc.setdefault(label, {"n": 0, "sum": 0.0, "sq": 0.0, "decisions": 0, "ms_total": 0.0,
                                   "ms_max": 0.0, "over": 0, "errors": 0})
        a["n"] += 1
        a["sum"] += pts
        a["sq"] += pts * pts
        a["decisions"] += cnt
        a["ms_total"] += tot
        a["ms_max"] = max(a["ms_max"], mx)
        a["over"] += over
        a["errors"] += err
    out = {}
    for label, a in acc.items():
        mean = a["sum"] / a["n"]
        var = max(a["sq"] / a["n"] - mean * mean, 0.0)
        out[label] = {"tables": a["n"], "mean": mean, "se": math.sqrt(var / a["n"]),
                      "ms_avg": a["ms_total"] / max(a["decisions"], 1), "ms_max": a["ms_max"],
                      "over_1ms": a["over"], "errors": a["errors"]}
    return out


def format_summary(summary):
    lines = [f"{'bot':<22}{'tables':>8}{'pts/table':>11}{'±se':>8}{'ms avg':>9}{'ms max':>9}{'errors':>8}"]
    for label, s in sorted(summary.items(), key=lambda kv: -kv[1]["mean"]):
        lines.append(f"{label:<22}{s['tables']:>8}{s['mean']:>11.2f}{s['se']:>8.2f}"
                     f"{s['ms_avg']:>9.3f}{s['ms_max']:>9.2f}{s['errors']:>8}")
    return "\n".join(lines)

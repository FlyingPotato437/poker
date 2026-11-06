"""Final check of the frozen submission files, run the way a host would run them.

    python scripts/final_check.py --variant nlhe --sngs 800 > bench/final_rc1_nlhe.txt

A = frozen/<tag>/<variant>_bot.py (release candidate), B = frozen/<tag>/fallback/<variant>_bot.py
(the old bot). Each is rebuilt with the mock-kit adapter in place of the template adapter, after
checking that everything above the adapter is byte-identical to the frozen file, and imported in
every worker the way a host would: model-size calibration at import and the bot's own 0.6 ms
deadline guard both on. Every decision goes through the mock kit's state format and is timed
around get_action() only; a decision over --limit-ms is replaced with check/fold, as a host
auto-fold would. Opponents run in-process with no time limit, so the field stays repeatable.

Pairing as in ab_test.py: each SNG is played once with A and once with B in the same seat,
against the same opponents and deck order. Opponent styles were written after the freeze
(zoo FINAL_WEAK / FINAL_STRONG) or never played as opponents (hyb_t1_g8); "timeout" and
"random" stand in for crashed bots. NLHE adds attackers tuned against each bot, and an
exploitability cell: one attacker at a table of 7 copies of the bot it was tuned against.
The default seed was never used by an earlier run. The out-of-sample field (zoo OOS) only
plays when asked for with --fields oos: keep it for the last check, after choosing.
"""
import argparse
import importlib.util
import math
import multiprocessing as mp
import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
for _d in ("scripts", "examples"):
    sys.path.insert(0, os.path.join(ROOT, _d))

from freeze import sha, split_package, with_adapter  # noqa: E402
from mock_kit import kit_state  # noqa: E402
from nolimit import harness  # noqa: E402
from nolimit.engine import DEFAULT_PAYOUTS, SNG  # noqa: E402
from nolimit.harness import build_seatings, parse_entry  # noqa: E402
from nolimit.runtime import CALL, FOLD, RAISE, BotBase  # noqa: E402
from nolimit.zoo import FINAL_STRONG, FINAL_WEAK, OOS  # noqa: E402
from nolimit.rivals import llm_fields, rival_fields  # noqa: E402

SCHEDULES = {"normal": 25, "fast": 10}
ATTACKERS = {"nlhe": {"A": "prep:params/br_vs_ev_t4.json", "B": "prep:params/br_vs_legacy_same.json"}}
BIN_MS = 0.01
N_BINS = 300            # 0-3 ms in 0.01 ms bins, then one overflow bin


def final_fields(variant, attackers=None):
    weak = {k: 1 for k in FINAL_WEAK}
    f = {
        "weak": weak,
        "weak+crashed": {**weak, "timeout": 1, "random": 0.5},
        "strong": {**{k: 2 for k in FINAL_STRONG}, "prep:params/hyb_t1_g8.json": 2},
        "mixed": {**weak, **{k: 1 for k in FINAL_STRONG}, "prep:params/hyb_t1_g8.json": 0.5, "timeout": 0.5},
        "oos": {k: 1 for k in OOS},                  # out-of-sample: only with --fields oos, after choosing
    }
    f.update(rival_fields())                         # rival teams; rival-oos is sealed like oos
    f.update(llm_fields())                           # LLM-bug designs: evaluation only, opt-in
    for who, spec in (ATTACKERS.get(variant, {}) if attackers is None else attackers).items():
        f[f"attack-on-{who}"] = {spec: 1}
    return f


class Timing:
    def __init__(self):
        self.hist = [0] * (N_BINS + 1)
        self.max = 0.0
        self.over = self.errors = 0

    def add(self, ms):
        self.hist[min(int(ms / BIN_MS), N_BINS)] += 1
        self.max = max(self.max, ms)

    def merge(self, d):
        self.hist = [a + b for a, b in zip(self.hist, d["hist"])]
        self.max = max(self.max, d["max"])
        self.over += d["over"]
        self.errors += d["errors"]

    def dump(self):
        return {"hist": self.hist, "max": self.max, "over": self.over, "errors": self.errors}

    @property
    def n(self):
        return sum(self.hist)

    def pct(self, q):
        k, acc = q * self.n, 0
        for i, c in enumerate(self.hist):
            acc += c
            if acc >= k:
                return (i + 1) * BIN_MS if i < N_BINS else self.max
        return self.max


class TimedKit(BotBase):
    """The packaged bot behind the mock-kit interface, timed and penalized like a host would."""

    def __init__(self, mod, seed, v, limit_ms, timing):
        self.kit = mod.Bot()
        self.kit.core = mod.make_core(seed=seed)     # Bot() seeds itself randomly; this keeps runs repeatable
        self.v, self.limit, self.tm = v, limit_ms, timing

    def act(self, obs):
        state = kit_state(obs, self.v)               # the host's work, outside the timer
        t0 = time.perf_counter()
        try:
            a = self.kit.get_action(state)
        except Exception:
            a = None
        dt = (time.perf_counter() - t0) * 1000.0
        self.tm.add(dt)
        if a is None:
            self.tm.errors += 1
        elif dt > self.limit:
            self.tm.over += 1
        elif a["action"] == "fold":
            return (FOLD, 0)
        elif a["action"] in ("check", "call"):
            return (CALL, 0)
        else:
            return (RAISE, max(obs.bets) + int(a["amount"]))
        return (CALL, 0) if obs.to_call == 0 else (FOLD, 0)


_K = {}


def _init(bundle, kit_paths, limit_ms):
    harness._init(bundle, None)
    _K["limit"] = limit_ms
    _K["info"] = {}
    for who, path in kit_paths.items():
        spec = importlib.util.spec_from_file_location(f"kit_{who}", path)
        mod = importlib.util.module_from_spec(spec)
        t0 = time.perf_counter()
        spec.loader.exec_module(mod)
        T = mod._tables()
        _K[who] = mod
        nets = getattr(T, "net_choice", None)
        _K["info"][who] = (round(time.perf_counter() - t0, 2), nets[0] if nets else "-", mod.np is not None)


def _run_job(job):
    games, kw = job
    v = harness._W["variant"]
    timings, rows = {}, []
    for seats, seed, cell in games:
        agents = []
        for i, e in enumerate(seats):
            if e["kind"] == "kit":
                tm = timings.setdefault((cell, e["label"]), Timing())
                agents.append(TimedKit(_K[e["label"]], seed * 31 + i, v, _K["limit"], tm))
            else:
                agents.append(harness.make_agent(e, seed * 31 + i))
        sng = SNG(v, agents, rng=random.Random(seed), evaluator=harness._W["tables"].ev, **kw)
        pts = sng.run()
        rows += [(cell, e["label"], pts[i], seed) for i, e in enumerate(seats)]
    return rows, {k: t.dump() for k, t in timings.items()}, (os.getpid(), _K["info"])


def build_kit_files(args):
    out_dir = os.path.join(ROOT, "build", "final_check")
    os.makedirs(out_dir, exist_ok=True)
    paths = {}
    for who, src in (("A", args.a), ("B", args.b)):
        with open(src) as fh:
            frozen = fh.read()
        text = with_adapter(src, args.adapter)
        assert split_package(text)[:2] == split_package(frozen)[:2], "runtime/params/tables changed"
        paths[who] = os.path.join(out_dir, f"{args.variant}_{who}_{sha(frozen)[:8]}_kit.py")
        with open(paths[who], "w") as fh:
            fh.write(text)
        print(f"{who} = {os.path.relpath(src, ROOT)}  sha256 {sha(frozen)[:12]}  "
              f"(runtime+params+tables identical, mock-kit adapter)")
    return paths


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--variant", default="nlhe")
    ap.add_argument("--tag", default="rc1")
    ap.add_argument("--a", help="default frozen/<tag>/<variant>_bot.py")
    ap.add_argument("--b", help="default frozen/<tag>/fallback/<variant>_bot.py")
    ap.add_argument("--bundle", help="opponents' tables (default bundles/<variant>_rng.nlb)")
    ap.add_argument("--adapter", default=os.path.join(ROOT, "examples", "adapter_mock_solution.py"))
    ap.add_argument("--sngs", type=int, default=600, help="paired SNGs per cell")
    ap.add_argument("--exploit-sngs", type=int, default=300, help="SNGs per bot in the exploitability cell")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2),
                    help="default: half the cores, so timing is not distorted by hyperthread sharing")
    ap.add_argument("--limit-ms", type=float, default=1.0)
    ap.add_argument("--seed", type=int, default=8086)
    ap.add_argument("--fields", help="comma list (default: all for the variant)")
    ap.add_argument("--schedules", default="normal,fast")
    ap.add_argument("--payouts", help="points 1st..8th (default: the engine's, which the frozen tables were "
                    "built for); A and B should carry ICM tables solved for the same points")
    ap.add_argument("--attackers", help="override the attacker per bot, e.g. B=prep:params/br_vs_ev_t4.json "
                    "(a field per attacker; the exploitability cell needs one per bot)")
    args = ap.parse_args()
    attackers = None
    if args.attackers:
        attackers = dict(item.split("=", 1) for item in args.attackers.split(","))
    frozen = os.path.join(ROOT, "frozen", args.tag)
    args.a = args.a or os.path.join(frozen, f"{args.variant}_bot.py")
    args.b = args.b or os.path.join(frozen, "fallback", f"{args.variant}_bot.py")
    args.bundle = args.bundle or os.path.join(ROOT, "bundles", f"{args.variant}_rng.nlb")

    t_start = time.time()
    kit_paths = build_kit_files(args)
    fields = final_fields(args.variant, attackers)
    names = args.fields.split(",") if args.fields else [f for f in fields
                                                          if f != "oos" and not f.startswith(("rival", "llm"))]
    payouts = [float(x) for x in args.payouts.split(",")] if args.payouts else list(DEFAULT_PAYOUTS)
    fair = sum(payouts) / 8
    kit = {who: {"label": who, "kind": "kit"} for who in ("A", "B")}

    games = []
    for sname in args.schedules.split(","):
        for fname in names:
            field = [parse_entry(k, w) for k, w in fields[fname].items()]
            for seats, seed in build_seatings(field, args.sngs, args.seed, fixed=[{"label": "slot"}]):
                for who in ("A", "B"):
                    games.append(([kit[who] if s.get("label") == "slot" else s for s in seats],
                                  seed, (sname, fname), SCHEDULES[sname]))
    exploit = (ATTACKERS.get(args.variant) if attackers is None else attackers) if args.exploit_sngs else None
    if exploit:
        rng = random.Random(args.seed)
        for who, spec in exploit.items():
            att = dict(parse_entry(spec), label="attacker")
            for g in range(args.exploit_sngs):
                seats = [att] + [kit[who]] * 7
                rng.shuffle(seats)
                games.append((seats, args.seed * 1_000_003 + 700_000 + g, ("normal", f"exploit-{who}"),
                              SCHEDULES["normal"]))

    jobs = {}
    for seats, seed, cell, hpl in games:
        jobs.setdefault(hpl, []).append((seats, seed, cell))
    chunks = [((part[i:i + 8]), {"payouts": payouts, "hands_per_level": hpl})
              for hpl, part in jobs.items() for i in range(0, len(part), 8)]
    random.Random(0).shuffle(chunks)                 # mix cells so slow ones don't finish last
    rows, timings, workers = [], {}, {}
    pool = mp.get_context("spawn").Pool(args.workers, initializer=_init,
                                        initargs=(args.bundle, kit_paths, args.limit_ms))
    try:
        for r, tms, (pid, info) in pool.imap_unordered(_run_job, chunks):
            rows += r
            workers[pid] = info
            for k, d in tms.items():
                timings.setdefault(k, Timing()).merge(d)
    finally:
        pool.terminate()

    print(f"\nvariant {args.variant}, {len(rows) // 8} SNGs, payouts {payouts}, limit {args.limit_ms} ms, "
          f"{args.workers} workers, seed {args.seed}")
    for who in ("A", "B"):
        seen = sorted({info[who] for info in workers.values()}, key=str)
        print(f"{who} import (s, model size, numpy) per worker: {seen}")
    print(f"\n{'blinds':<8}{'field':<15}{'A x fair':>9}{'B x fair':>9}{'A-B pts':>9}{'±se':>6}{'A-B %fair':>11}"
          f"{'A pen/1k':>10}{'B pen/1k':>10}")
    tot = {"d": 0.0, "v": 0.0, "n": 0}
    for sname in args.schedules.split(","):
        for fname in names:
            cell = (sname, fname)
            pa = {r[3]: r[2] for r in rows if r[0] == cell and r[1] == "A"}
            pb = {r[3]: r[2] for r in rows if r[0] == cell and r[1] == "B"}
            d = [pa[k] - pb[k] for k in pa if k in pb]
            m = sum(d) / len(d)
            se = math.sqrt(sum((x - m) ** 2 for x in d) / max(len(d) - 1, 1) / len(d))
            pen = [1000 * (timings[cell, w].over + timings[cell, w].errors) / max(timings[cell, w].n, 1)
                   for w in ("A", "B")]
            tot["d"] += m / fair
            tot["v"] += (se / fair) ** 2
            tot["n"] += 1
            print(f"{sname:<8}{fname:<15}{sum(pa.values()) / len(pa) / fair:>9.3f}{sum(pb.values()) / len(pb) / fair:>9.3f}"
                  f"{m:>+9.2f}{se:>6.2f}{100 * m / fair:>+10.1f}%{pen[0]:>10.2f}{pen[1]:>10.2f}", flush=True)
    k = max(tot["n"], 1)
    print(f"\nmean over {k} cells: A-B {100 * tot['d'] / k:+.2f}% of fair (±{100 * math.sqrt(tot['v']) / k:.2f})")
    if exploit:
        print("\nexploitability: one attacker tuned against the bot, at a table of 7 copies of it")
        for who in exploit:
            att = [r[2] for r in rows if r[0] == ("normal", f"exploit-{who}") and r[1] == "attacker"]
            m = sum(att) / len(att)
            se = math.sqrt(sum((x - m) ** 2 for x in att) / max(len(att) - 1, 1) / len(att))
            print(f"  attacker vs 7x {who}: {m / fair:.3f}x fair (±{se / fair:.3f}), {len(att)} SNGs")

    print(f"\ndecision time through get_action(), all cells (ms)")
    print(f"{'bot':<5}{'decisions':>10}{'p50':>7}{'p99':>7}{'p99.9':>7}{'max':>7}{'over limit':>11}{'errors':>8}")
    for who in ("A", "B"):
        t = Timing()
        for (cell, w), tm in timings.items():
            if w == who:
                t.merge(tm.dump())
        print(f"{who:<5}{t.n:>10}{t.pct(0.5):>7.2f}{t.pct(0.99):>7.2f}{t.pct(0.999):>7.2f}{t.max:>7.2f}"
              f"{t.over:>11}{t.errors:>8}")
    print(f"[{time.time() - t_start:.0f}s]")


if __name__ == "__main__":
    main()

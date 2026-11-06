"""Day-of pipeline, one command per step, so either teammate can run all of it.

    python scripts/day.py build v0 --preset nlhe --points 100,65,45,30,20,12,6,0 --adapter my_adapter.py
    python scripts/day.py build v0 --heuristic variants/day.json --adapter my_adapter.py   # new variant, no tables yet
    python scripts/day.py build rc1k --from-frozen rc1 --adapter my_adapter.py   # rc1 bytes + today's adapter
    python scripts/day.py submit v0              # puts the frozen file at dist/SUBMIT/<name>: upload that
    python scripts/day.py rollback               # back to the previously submitted tag
    python scripts/day.py status

build <tag>: re-solves push/fold for the announced points (and antes) on a copy of the bundle,
packages it with the params and adapter (package_bot.py, incl. its smoke test), checks the
package in a clean interpreter (size, import time, peak memory and decision latency with and
without numpy, with the 0.6 ms deadline guard on and a 1 ms auto-fold like a host), runs the
kit's own simulator if given (--kit-cmd, "{bot}" is replaced by the file), and freezes it as
frozen/<tag>/ (tags are never overwritten). Nothing reaches dist/SUBMIT/ until `submit`.

Defaults per preset: bundle bundles/<preset>_rng.nlb; params ev_t4 for nlhe, ev_t3 otherwise
(the v2 EV engine). For a variant built on the day, pass --bundle bundles/day_rng.nlb.
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from freeze import sha  # noqa: E402

PY = sys.executable
SUBMIT = os.path.join(ROOT, "dist", "SUBMIT")
STATE = os.path.join(SUBMIT, "STATE.json")
LIMIT_MB = 100

CHECK = r"""
import importlib.util, json, os, random, resource, sys, time
sys.path.insert(0, {root!r})
def peak_mb():
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / 1e6 if sys.platform == "darwin" else r / 1e3
t0 = time.perf_counter()
spec = importlib.util.spec_from_file_location("submitted_bot", {path!r})
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
imp, mem_import = time.perf_counter() - t0, peak_mb()
from nolimit.engine import SNG
from nolimit.runtime import RAISE, BotBase
from nolimit.zoo import ZOO

class Timed(BotBase):
    def __init__(self, core):
        self.core, self.ms = core, []
    def new_table(self, seat, n):
        self.core.new_table(seat, n)
    def observe(self, ev):
        self.core.observe(ev)
    def act(self, obs):
        t = time.perf_counter()
        a = self.core.act(obs)
        self.ms.append((time.perf_counter() - t) * 1000)
        kind, amt = a
        if kind == RAISE and not (obs.min_raise_to and obs.min_raise_to <= amt <= obs.max_raise_to):
            raise ValueError(f"illegal raise {{amt}} outside [{{obs.min_raise_to}}, {{obs.max_raise_to}}]")
        return a

T = mod._tables()
seats, errors, over = [], 0, 0
for g in range({sngs}):
    bots = [Timed(mod.make_core(seed=g)), Timed(mod.make_core(seed=g + 99))]
    agents = bots + [ZOO[k](T, seed=g) for k in ("tag", "shover", "nit", "lag", "station", "timeout")]
    random.Random(g).shuffle(agents)
    sng = SNG(T.v, agents, rng=random.Random(g), evaluator=T.ev, time_limit_ms=1.0,
              hands_per_level=(25, 10)[g % 2])
    sng.run()
    for b in bots:
        s = agents.index(b)
        errors += sng.errors[s]
        over += sng.timing[s].over
        seats.append(b)
ms = sorted(x for b in seats for x in b.ms)
q = lambda p: ms[min(len(ms) - 1, int(p * len(ms)))]
print(json.dumps({{"numpy": mod.np is not None, "import_s": round(imp, 2), "peak_mb_import": round(mem_import, 1),
                  "peak_mb": round(peak_mb(), 1), "decisions": len(ms), "p50_ms": round(q(0.5), 3),
                  "p99_ms": round(q(0.99), 3), "p999_ms": round(q(0.999), 3), "max_ms": round(ms[-1], 2),
                  "over_1ms": over, "errors_or_illegal": errors, "variant": T.v.name}}))
"""


def run(cmd, **kw):
    print("$ " + " ".join(cmd), flush=True)
    res = subprocess.run(cmd, cwd=ROOT, **kw)
    if res.returncode:
        sys.exit(f"FAILED ({res.returncode}): {' '.join(cmd)}")
    return res


def check(path, sngs, numpy):
    env = dict(os.environ)
    if not numpy:
        env["NOLIMIT_NO_NUMPY"] = "1"
    res = subprocess.run([PY, "-I", "-c", CHECK.format(root=ROOT, path=os.path.abspath(path), sngs=sngs)],
                         env=env, capture_output=True, text=True)
    if res.returncode:
        print(res.stderr[-2000:])
        sys.exit("package check FAILED: the bot crashed or played an illegal action")
    return json.loads(res.stdout.strip().splitlines()[-1])


def build(args):
    if os.path.exists(os.path.join(ROOT, "frozen", args.tag)):
        sys.exit(f"frozen/{args.tag} exists: tags are never overwritten, pick a new one")
    t0 = time.time()
    if args.from_frozen:
        return build_from_frozen(args, t0)
    if args.heuristic:      # no tables yet: rules engine on heuristic tables for the exact rules
        bundle = None
        params = args.params or os.path.join(ROOT, "params", "nlhe_final_legacy.json")
    else:
        bundle = args.bundle or os.path.join(ROOT, "bundles", f"{args.preset}_rng.nlb")
        params = args.params or os.path.join(ROOT, "params", "ev_t4.json" if args.preset == "nlhe" else "ev_t3.json")
    for p in (bundle or args.adapter, params, args.adapter):
        if not os.path.exists(p):
            sys.exit(f"missing {p}")
    os.makedirs(os.path.join(ROOT, "bundles", "day"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "dist", "day"), exist_ok=True)
    day_bundle = os.path.join(ROOT, "bundles", "day", f"{args.tag}.nlb")
    out = os.path.join(ROOT, "dist", "day", f"{args.tag}.py")
    if args.heuristic:
        print("heuristic tables: no push/fold charts, so --points/--ante-bb do not apply")
    elif args.points:
        cmd = [PY, "-m", "gpu.pushfold", "--bundle", bundle, "--payouts", args.points, "--out", day_bundle,
               "--workers", str(args.workers)]
        if args.ante_bb:
            cmd += ["--ante-bb", str(args.ante_bb)]
        run(cmd)
    else:
        print("WARNING: no --points, keeping the bundle's push/fold tables (built for the placeholder points)")
        shutil.copyfile(bundle, day_bundle)
    cmd = [PY, "scripts/package_bot.py", "--params", params, "--adapter", args.adapter, "--out", out]
    cmd += ["--variant", args.heuristic] if args.heuristic else ["--bundle", day_bundle]
    if args.pure_python:
        cmd.append("--pure-python")
    run(cmd)
    rep = {"tag": args.tag, "bundle": os.path.relpath(bundle, ROOT) if bundle else f"heuristic {args.heuristic}",
           "params": os.path.relpath(params, ROOT),
           "points": args.points, "ante_bb": args.ante_bb, "adapter": os.path.relpath(args.adapter, ROOT),
           "bytes": os.path.getsize(out), "checks": {}}
    finish(args, out, rep, t0)


def build_from_frozen(args, t0):
    """The frozen file (runtime, params, tables: exact bytes) with only its adapter replaced."""
    from freeze import with_adapter
    rel = f"{args.preset}_bot.py"
    src = os.path.join(ROOT, "frozen", args.from_frozen, rel)
    for p in (src, args.adapter):
        if not os.path.exists(p):
            sys.exit(f"missing {p}")
    if args.points or args.ante_bb or args.pure_python or args.params or args.bundle or args.heuristic:
        print(f"--from-frozen keeps frozen/{args.from_frozen}/{rel} as it is: --points/--ante-bb/--params/"
              "--bundle/--pure-python/--heuristic are ignored (push/fold stays at the placeholder points)")
        args.points, args.ante_bb, args.pure_python = None, 0.0, False
    os.makedirs(os.path.join(ROOT, "dist", "day"), exist_ok=True)
    out = os.path.join(ROOT, "dist", "day", f"{args.tag}.py")
    with open(out, "w") as fh:
        fh.write(with_adapter(src, args.adapter))
    print(f"wrote {out}: frozen/{args.from_frozen}/{rel} with adapter {args.adapter}")
    rep = {"tag": args.tag, "bundle": f"frozen/{args.from_frozen}/{rel}", "params": f"frozen/{args.from_frozen}/{rel}",
           "points": None, "ante_bb": 0.0, "adapter": os.path.relpath(args.adapter, ROOT),
           "bytes": os.path.getsize(out), "checks": {}}
    finish(args, out, rep, t0)


def finish(args, out, rep, t0):
    for numpy in ((False,) if args.pure_python else (True, False)):
        c = check(out, args.sngs, numpy)
        rep["checks"]["numpy" if numpy else "no_numpy"] = c
        print(f"check {'numpy   ' if numpy else 'no numpy'}: import {c['import_s']}s, peak memory {c['peak_mb']} MB, "
              f"{c['decisions']} decisions p99 {c['p99_ms']} ms, p99.9 {c['p999_ms']} ms, max {c['max_ms']} ms, "
              f"over 1 ms {c['over_1ms']}, errors/illegal {c['errors_or_illegal']}")
    warn = []
    if rep["bytes"] / 1e6 > LIMIT_MB:
        warn.append(f"file {rep['bytes'] / 1e6:.1f} MB > {LIMIT_MB} MB")
    if any(c["peak_mb"] > LIMIT_MB for c in rep["checks"].values()):
        warn.append(f"peak memory > {LIMIT_MB} MB (matters only if the limit is RAM): try --pure-python, smaller tables")
    if any(c["over_1ms"] * 1000 > 2 * c["decisions"] for c in rep["checks"].values()):
        warn.append("more than 2 decisions per 1000 over 1 ms")
    if args.kit_cmd:
        res = subprocess.run(args.kit_cmd.replace("{bot}", out), shell=True, cwd=ROOT, capture_output=True, text=True)
        print((res.stdout + res.stderr)[-3000:])
        rep["kit_check"] = res.returncode
        if res.returncode:
            sys.exit("kit simulator FAILED: not frozen")
    else:
        warn.append("kit simulator not run (--kit-cmd): test the file in the kit before submitting")
    run([PY, "scripts/freeze.py", "--tag", args.tag, "--files", out])
    rep["sha256"] = sha(open(out, "rb").read())
    rep["warnings"] = warn
    rep["build_s"] = round(time.time() - t0)
    with open(os.path.join(ROOT, "dist", "day", f"{args.tag}.check.json"), "w") as fh:
        json.dump(rep, fh, indent=1)
    for w in warn:
        print("WARNING: " + w)
    print(f"\nbuilt and froze {args.tag} in {rep['build_s']}s, sha {rep['sha256'][:12]}. "
          f"To submit: python scripts/day.py submit {args.tag}")


def load_state():
    if os.path.exists(STATE):
        with open(STATE) as fh:
            return json.load(fh)
    return {"name": "bot.py", "history": []}


def frozen_file(tag):
    d = os.path.join(ROOT, "frozen", tag)
    with open(os.path.join(d, "MANIFEST.json")) as fh:
        man = json.load(fh)
    rels = [r for r in man["files"] if not r.startswith("fallback/")]
    if len(rels) != 1:
        sys.exit(f"frozen/{tag} holds {len(rels)} bot files; day.py submits single-file tags ({rels})")
    path = os.path.join(d, rels[0])
    if sha(open(path, "rb").read()) != man["files"][rels[0]]["sha256"]:
        sys.exit(f"frozen/{tag}/{rels[0]} no longer matches its manifest: do not submit it")
    return path, man["files"][rels[0]]["sha256"]


def submit(tag, name=None, note="submit"):
    st = load_state()
    st["name"] = name or st["name"]
    src, digest = frozen_file(tag)
    os.makedirs(SUBMIT, exist_ok=True)
    for old in glob.glob(os.path.join(SUBMIT, "*.py")):
        os.remove(old)
    dst = os.path.join(SUBMIT, st["name"])
    shutil.copyfile(src, dst)
    assert sha(open(dst, "rb").read()) == digest
    st["history"].append({"tag": tag, "sha256": digest, "time": time.strftime("%H:%M:%S"), "how": note})
    with open(STATE, "w") as fh:
        json.dump(st, fh, indent=1)
    print(f"dist/SUBMIT/{st['name']} = frozen/{tag} (sha {digest[:12]}). UPLOAD THIS FILE NOW, then check the "
          f"kit/site shows it.")


def status():
    st = load_state()
    cur = st["history"][-1] if st["history"] else None
    path = os.path.join(SUBMIT, st["name"])
    if cur:
        ok = os.path.exists(path) and sha(open(path, "rb").read()) == cur["sha256"]
        print(f"current: {cur['tag']} sha {cur['sha256'][:12]} at {cur['time']} -> dist/SUBMIT/{st['name']}"
              f" ({'matches' if ok else 'FILE CHANGED OR MISSING'})")
    else:
        print("nothing submitted yet")
    print("history: " + ", ".join(f"{h['tag']}@{h['time']}({h['how']})" for h in st["history"]))
    print("\nbuilt tags:")
    for f in sorted(glob.glob(os.path.join(ROOT, "dist", "day", "*.check.json")), key=os.path.getmtime):
        r = json.load(open(f))
        c = r["checks"].get("numpy") or r["checks"]["no_numpy"]
        print(f"  {r['tag']:<8} {r['sha256'][:12]}  {r['params']}  points {r['points']}  peak {c['peak_mb']} MB  "
              f"p99.9 {c['p999_ms']} ms  kit {'ok' if r.get('kit_check') == 0 else 'NOT RUN'}"
              + (f"  warnings: {len(r['warnings'])}" if r["warnings"] else ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("tag")
    b.add_argument("--preset", default="nlhe")
    b.add_argument("--bundle", help="default bundles/<preset>_rng.nlb")
    b.add_argument("--params", help="default params/ev_t4.json (nlhe) or params/ev_t3.json; with --heuristic "
                   "params/nlhe_final_legacy.json")
    b.add_argument("--heuristic", metavar="VARIANT", help="no tables: preset name or variants/day.json (the v0 "
                   "for a new variant while its tables build)")
    b.add_argument("--points", help="announced points 1st..8th, e.g. 100,65,45,30,20,12,6,0")
    b.add_argument("--ante-bb", type=float, default=0.0)
    b.add_argument("--from-frozen", metavar="TAG", help="fallback: frozen/TAG/<preset>_bot.py byte for byte "
                   "(its runtime, params and tables) with only the adapter swapped, e.g. --from-frozen rc1")
    b.add_argument("--adapter", required=True)
    b.add_argument("--pure-python", action="store_true")
    b.add_argument("--kit-cmd", help='shell command running the kit simulator on "{bot}"')
    b.add_argument("--sngs", type=int, default=30, help="SNGs per check (2 seats each)")
    b.add_argument("--workers", type=int, default=4, help="push/fold solver processes")
    s = sub.add_parser("submit")
    s.add_argument("tag")
    s.add_argument("--as", dest="name", help="file name the kit expects (remembered; default bot.py)")
    r = sub.add_parser("rollback")
    r.add_argument("tag", nargs="?", help="default: the tag submitted before the current one")
    sub.add_parser("status")
    args = ap.parse_args()
    if args.cmd == "build":
        build(args)
    elif args.cmd == "submit":
        submit(args.tag, args.name)
    elif args.cmd == "rollback":
        hist = load_state()["history"]
        if args.tag:
            tag = args.tag
        else:
            prev = [h["tag"] for h in hist if h["tag"] != (hist[-1]["tag"] if hist else None)]
            if not prev:
                sys.exit("no earlier submission to roll back to")
            tag = prev[-1]
        submit(tag, note="rollback")
    else:
        status()


if __name__ == "__main__":
    main()

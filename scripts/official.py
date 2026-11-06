"""Prepare official-contract candidates without modifying frozen research releases.

python scripts/official.py basis --out build/official/icm_basis.nlb
python scripts/official.py build --preset nlhe --out build/official/nlhe
python scripts/official.py check build/official/nlhe.zip
python scripts/official.py kit-check build/official/nlhe --kit /path/to/starter-kit

These are PRE-KIT candidates, not approved tournament submissions. The exact SDK,
variant ID/rules, event schema, and real host timing must be checked on release.
"""
import argparse
import ast
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nolimit.official_payouts import DEFAULT_PAYOUTS, HAND_CAP, HANDS_PER_LEVEL, validate_payouts
from freeze import MARK, split_package

UPLOAD_LIMIT = 50_000_000
UNPACKED_LIMIT = 200_000_000
AGENT_LIMIT = 1_000_000
ENTRY_LIMIT = 1000
PRESETS = ("nlhe", "plo4", "plo5", "shortdeck", "shortdeck_triton", "holdem3", "royal")

AGENT = '''"""Published-interface adapter. Verify against the released starter kit before upload."""
import os
for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
             "NUMBA_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[name] = "1"

import gc
import json
from pathlib import Path
from poker_agent_sdk import Agent as SDKAgent
try:
    from poker_agent_sdk import Action
except ImportError:
    from poker_agent_protocol import Action
from core_runtime import Tables, read_bundle, warmup
from official_payouts import PayoutBasis
from official_adapter import OfficialBridge

HERE = Path(__file__).resolve().parent
TABLES = Tables((HERE / "tables.nlb").read_bytes())
meta, arrays = read_bundle((HERE / "icm_basis.nlb").read_bytes())
BASIS = PayoutBasis(meta, arrays)
PARAMS = json.loads((HERE / "params.json").read_text())
CONFIG = json.loads((HERE / "model.json").read_text())
warmup(TABLES)
# Warmup's hand-dependent caches are discarded before serving any real table.
for name in ("_post_cache", "_rng_cache", "_feat_cache"):
    getattr(TABLES, name, {}).clear()
BRIDGE = OfficialBridge(TABLES, BASIS, PARAMS, CONFIG["variant_ids"])
gc.collect()
gc.freeze()

class Agent(SDKAgent):
    def act(self, state, memory):
        return BRIDGE.act(state, memory, Action)
'''


def digest(data):
    return hashlib.sha256(data).hexdigest()


def build_basis(out, nmax=10):
    import numpy as np
    from gpu.pushfold import BF_FRACS, BF_SHARES
    from nolimit.bundle_io import write_bundle
    from nolimit.icm_fast import hero_rank_probabilities
    if out.exists():
        raise ValueError(f"Refusing to overwrite {out}")
    shape = (nmax - 1, len(BF_SHARES), len(BF_SHARES), len(BF_FRACS), nmax)
    gain, loss = np.zeros(shape, np.float32), np.zeros(shape, np.float32)
    for n in range(2, nmax + 1):
        for i, h in enumerate(BF_SHARES):
            for j, other in enumerate(BF_SHARES):
                x = min(other, 0.98 - h) if n > 2 else 1 - h
                if x <= 0.005 or h <= 0.005:
                    continue
                tail = [(1 - h - x) / (n - 2)] * (n - 2) if n > 2 else []
                now = np.array(hero_rank_probabilities([h, x] + tail))
                for k, frac in enumerate(BF_FRACS):
                    risk = frac * min(h, x)
                    win = np.array(hero_rank_probabilities([h + risk, x - risk] + tail))
                    lose = np.array(hero_rank_probabilities([h - risk, x + risk] + tail))
                    gain[n - 2, i, j, k, :n] = win - now
                    loss[n - 2, i, j, k, :n] = now - lose
        print(f"ICM rank basis: {n} players", flush=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_bundle(str(out), {"shares": BF_SHARES, "fracs": BF_FRACS, "nmax": nmax,
                           "approximation": "equal other stacks, nearest share grid, linear risk interpolation"},
                 {"gain": gain, "loss": loss})


def check_files(files):
    if len(files) > ENTRY_LIMIT:
        raise ValueError("Too many archive entries")
    if "agent.py" not in files:
        raise ValueError("agent.py must be at archive root")
    if sum(len(b) for b in files.values()) > UNPACKED_LIMIT:
        raise ValueError("Unpacked package exceeds 200 MB")
    if len(files["agent.py"]) > AGENT_LIMIT:
        raise ValueError("agent.py exceeds 1 MB")
    for name, blob in files.items():
        p = Path(name)
        if p.is_absolute() or ".." in p.parts or "\\" in name or len(name) > 512 or len(p.parts) > 16:
            raise ValueError(f"Invalid archive path {name}")
        if p.suffix in (".so", ".dylib", ".dll", ".exe"):
            raise ValueError(f"Uploaded native binaries cannot run: {name}")
        if p.suffix == ".py":
            tree = ast.parse(blob, filename=name)
            for node in ast.walk(tree):
                names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                         else [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
                if any(n.split(".")[0] in ("poker_engine", "pokerkit") for n in names):
                    raise ValueError(f"Forbidden local-only import in {name}")


def zip_files(path, files):
    check_files(files)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for name, blob in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, blob)
    if path.stat().st_size > UPLOAD_LIMIT:
        raise ValueError("Upload exceeds 50 MB")


def check_zip(path):
    if path.stat().st_size > UPLOAD_LIMIT:
        raise ValueError("Upload exceeds 50 MB")
    with zipfile.ZipFile(path) as z:
        entries = z.infolist()
        if (len(entries) > ENTRY_LIMIT or sum(i.file_size for i in entries) > UNPACKED_LIMIT
                or len(set(i.filename for i in entries)) != len(entries)):
            raise ValueError("Unsafe archive size or duplicate entries")
        if any((i.external_attr >> 16) & 0o170000 == 0o120000 for i in entries):
            raise ValueError("Symlink archive entry")
        files = {i.filename: z.read(i) for i in entries}
    check_files(files)
    return {"upload_bytes": path.stat().st_size, "unpacked_bytes": sum(map(len, files.values())),
            "agent_bytes": len(files["agent.py"]), "entries": len(files), "sha256": digest(path.read_bytes())}


def build(args):
    from nolimit.bundle_io import read_bundle_np, write_bundle
    from gpu.pushfold import solve_charts
    source = Path(args.frozen or ROOT / "frozen" / "rc2" / f"{args.preset}_bot.py").resolve()
    manifest_path = source.parent / "MANIFEST.json"
    man = json.loads(manifest_path.read_text())
    expected = man["files"][source.name]["sha256"]
    raw = source.read_bytes()
    if digest(raw) != expected:
        raise ValueError("Frozen source does not match its manifest")
    runtime, generated, _ = split_package(raw.decode())
    lines = generated[len(MARK):].splitlines()
    params = json.loads(lines[0][len("_PARAMS = "):])
    if not lines[1].startswith("_BUNDLE_B64 = "):
        raise ValueError("Expected embedded frozen bundle")
    bundle = base64.b64decode(ast.literal_eval(lines[1].split(" = ", 1)[1]))
    payouts = validate_payouts(args.payouts, 8)
    out = Path(args.out).resolve()
    archive = out.with_suffix(".zip")
    report_path = out.with_suffix(".manifest.json")
    if out.exists() or archive.exists() or report_path.exists():
        raise ValueError(f"Output exists; use a new candidate directory: {out}")
    basis_path = Path(args.basis)
    if not basis_path.exists():
        build_basis(basis_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent, prefix="official-build-") as tmp:
        tmp = Path(tmp)
        tables = tmp / "tables.nlb"
        tables.write_bytes(bundle)
        meta, arrays = read_bundle_np(str(tables))
        if not args.skip_charts:
            print(f"Rebuilding {args.preset} charts for payouts {payouts}", flush=True)
            shove, call = solve_charts(arrays["class_pct"], arrays["class_weight"], arrays["eq_range"],
                                      payouts, meta["pf_stacks"], meta["pf_nmax"], args.iters,
                                      args.ante_bb, args.workers)
            arrays["pf_shove"], arrays["pf_call"] = shove, call
            meta.update(payouts=payouts, pf_ante_bb=args.ante_bb)
        else:
            # Old charts have no verified ante provenance; disable them explicitly.
            arrays.pop("pf_shove", None)
            arrays.pop("pf_call", None)
        # The adapter always uses the arbitrary-payout basis, never this stale grid.
        arrays.pop("icm_bf", None)
        write_bundle(str(tables), meta, arrays)
        config = {"variant_ids": args.variant_id or [args.preset], "variant": meta["variant"],
                  "default_payouts": payouts, "hands_per_level": HANDS_PER_LEVEL, "hand_cap": HAND_CAP,
                  "kit_verified": False, "variant_rules_verified": False}
        v = meta["variant"]
        config["max_players_from_deck"] = (len(v["ranks"]) * v["suits"] - sum(v["streets"])) // v["n_hole"]
        files = {"agent.py": AGENT.encode(), "core_runtime.py": runtime.encode(),
                 "tables.nlb": tables.read_bytes(), "icm_basis.nlb": basis_path.read_bytes(),
                 "params.json": json.dumps(params, sort_keys=True).encode(),
                 "model.json": json.dumps(config, indent=2, sort_keys=True).encode()}
        for name in ("official_adapter", "official_payouts"):
            code = (ROOT / "nolimit" / (name + ".py")).read_text()
            code = code.replace("from .runtime import ", "from core_runtime import ")
            code = code.replace("from .official_payouts import ", "from official_payouts import ")
            files[name + ".py"] = code.encode()
        zip_files(tmp / "candidate.zip", files)
        checks = check_zip(tmp / "candidate.zip")
        out.mkdir()
        for name, blob in files.items():
            (out / name).write_bytes(blob)
        (tmp / "candidate.zip").replace(archive)
    report = {"status": "PRE_KIT_CANDIDATE", "source": str(source), "source_sha256": expected,
              "frozen_runtime_sha256": digest(runtime.encode()), "checks": checks,
              "files": {n: digest(b) for n, b in files.items()}, "config": config,
              "chart_iters": 0 if args.skip_charts else args.iters,
              "missing_checks": ["actual SDK imports and schema", "announced variant rules and ID",
                                 "official pack/check", "official 8-seat simulation", "zero-bank host timing"]}
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"candidate": str(archive), **checks}), flush=True)


def kit_check(args):
    candidate, kit = Path(args.candidate).resolve(), Path(args.kit).resolve()
    cli = kit / ".venv/bin/poker-agent"
    if not cli.exists():
        raise ValueError("Official kit is not installed: .venv/bin/poker-agent is missing")
    for name in ("AGENTS.md", "RULES.md", "README.md"):
        if not (kit / name).exists():
            raise ValueError(f"Incomplete starter kit: {name}")
    # Keep verification evidence distinct; successful pack/check does NOT prove timing.
    archive = candidate.with_suffix(".kit.zip")
    if archive.exists():
        raise ValueError("Verification archive exists; use a new candidate version")
    subprocess.run([str(cli), "pack", str(candidate), str(archive)], cwd=kit, check=True)
    subprocess.run([str(cli), "check", str(archive)], cwd=kit, check=True)
    print("Official static checks passed. Next: confirm RULES/schema, run 8-seat play and zero-bank validation.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)
    b = sub.add_parser("basis")
    b.add_argument("--out", type=Path, default=ROOT / "build/official/icm_basis.nlb")
    b = sub.add_parser("build")
    b.add_argument("--preset", choices=PRESETS, default="nlhe")
    b.add_argument("--frozen")
    b.add_argument("--out", required=True)
    b.add_argument("--basis", default=str(ROOT / "build/official/icm_basis.nlb"))
    b.add_argument("--variant-id", action="append")
    b.add_argument("--payouts", type=lambda s: tuple(float(x) for x in s.split(",")), default=DEFAULT_PAYOUTS)
    b.add_argument("--ante-bb", type=float, default=0.0)
    b.add_argument("--workers", type=int, default=2)
    b.add_argument("--iters", type=int, default=600)
    b.add_argument("--skip-charts", action="store_true")
    c = sub.add_parser("check")
    c.add_argument("archive", type=Path)
    k = sub.add_parser("kit-check")
    k.add_argument("candidate")
    k.add_argument("--kit", required=True)
    args = ap.parse_args()
    if args.command == "basis":
        build_basis(args.out)
    elif args.command == "build":
        build(args)
    elif args.command == "check":
        print(json.dumps(check_zip(args.archive), indent=2))
    else:
        kit_check(args)


if __name__ == "__main__":
    main()

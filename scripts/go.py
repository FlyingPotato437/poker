"""Day-of in one command: announced rules in, tested + frozen bots out.

    python scripts/go.py variants/ANNOUNCE.json --adapter my_adapter.py
    python scripts/go.py variants/ANNOUNCE.json --adapter my_adapter.py --kit-cmd "python kit/sim.py {bot}"
    python scripts/go.py variants/ANNOUNCE.json --check           # validate + plan only, builds nothing

What it does, in order (every line also goes to bench/dayof/go_<tag>.log, with elapsed time):
  1. validates the announcement, prints a plain-English summary, warnings and the plan for
     every rule the bot can't model (VARIANTS.md section 3);
  2. resolves the variant: a preset when the hand evaluation is identical, else it writes
     variants/day.json (or --variant-out);
  3. no bundle fits: starts the table build in the background first (build_tables, range_eq,
     then day.py build <tag>_v1 by itself), with an ETA;
  4. builds and checks <tag>_v0 = heuristic tables for the exact rules (day.py build
     --heuristic), so something is submittable within minutes;
  5. a preset bundle fits: builds <tag>_v1 from it (points/ante re-solve, the mapped params);
  6. prints the exact day.py submit / rollback / status commands to copy.

Params per variant come from one table, variants/PARAMS_MAP.json (edit that, not this file).
Tags are <tag>_v0, <tag>_v1 (default tag "day"); frozen tags are never overwritten, so a
second run needs a new --tag.
"""
import argparse
import json
import math
import os
import shlex
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from nolimit.runtime import CATEGORY_NAMES, PRESETS, Variant  # noqa: E402

PY = sys.executable
PARAMS_MAP = os.path.join(ROOT, "variants", "PARAMS_MAP.json")
LOGDIR = os.environ.get("GO_LOGDIR") or os.path.join(ROOT, "bench", "dayof")
BETTING = ("no-limit", "pot-limit", "fixed-limit")
GAME_TYPES = ("high", "hi-lo", "lowball-27", "lowball-a5", "badugi", "wild-cards", "discard", "stud")
ANTE_TYPES = ("none", "every-player", "bb-ante")
SPECIAL = ("seven_deuce", "straddle", "bomb_pot", "bounty", "run_it_twice")
MECHANICS = ("ranks", "suits", "n_hole", "streets", "hole_used", "category_order", "ace_low_straight")
OFFICIAL = {"players": 8, "starting_stack": 2000, "hands_per_level": 25, "hand_cap": 200, "time_limit_ms": 1.0}

# Measured table-build minutes on this M5 Pro (MPS), see DAYOF.md: minutes = a + b * (5-card
# combos evaluated per showdown). Calibrated on 2-hole (21 combos) and kit2 3-hole/2-used (30).
ETA = {"laptop": (6.0, 0.55), "fast": (3.0, 0.2)}

PLANS = {
    "pot-limit": "Pot-limit: the bot stays legal if the adapter passes the kit's pot-limit maximum as "
                 "max_raise_to (clamp in to_obs). Strategy assumes no-limit, so big bets clip to the pot. "
                 "Our engine/tunes can't simulate the cap (VARIANTS.md section 3).",
    "fixed-limit": "Fixed-limit: in to_obs set min_raise_to = max_raise_to = current bet + the fixed bet size, "
                   "and min_raise_to = None once the raise cap is reached. Strategy assumes no-limit "
                   "(VARIANTS.md section 3).",
    "raise_cap": "Raise cap: when the cap is reached, the adapter must set min_raise_to = None (no raise "
                 "legal), else the bot can return an illegal raise.",
    "hi-lo": "Hi-lo split: the evaluator ranks high hands only. v0 plays it as high-only. Plan (20-40 min of "
             "code): new hand_value_5 + TorchEval.eval5; meanwhile prefer a check/call-down style "
             "(VARIANTS.md section 3).",
    "lowball-27": "Lowball: the evaluator ranks high hands only, so the built bot plays the WRONG game. "
                  "Write hand_value_5 + TorchEval.eval5 for the low ranking (tests/test_evaluator.py), "
                  "rebuild tables. Meanwhile submit v0 anyway (legal moves, kit-tested).",
    "lowball-a5": "Lowball A-5: as lowball-27 (new evaluator needed).",
    "badugi": "Badugi: new evaluator + draw step needed; v0 is only a legal-move placeholder.",
    "wild-cards": "Wild cards: evaluator. Interim: in Evaluator.best treat the wild card as the card that "
                  "best improves the hand; v0 ignores wildness.",
    "discard": "Discard/pineapple: write the variant AFTER the discard (e.g. n_hole 2). The adapter keeps "
               "the cards whose T.hole_class scores best (preflop) or the best made hand (postflop); ~15 min.",
    "stud": "Stud: engine/tables don't model up-cards. Adapter treats everyone's up-cards as board cards; "
            "low quality, heuristic only.",
    "seven_deuce": "7-2 game: the bonus is not modeled; the bot never bluffs 72 on purpose. Ignore it "
                   "(small EV), or add a preflop override in the adapter if the bonus is big.",
    "straddle": "Straddle: adapter adds the straddle as a POST in history and in bets; the bot reads "
                "to_call/min-raise from the state, so it stays legal. Not simulated in tunes.",
    "bomb_pot": "Bomb pot: adapter puts everyone's forced chips in pot (and POSTs in history); street comes "
                "from the state, so a skipped preflop is fine.",
    "bounty": "Bounties: knockout value is not in the points/ICM model. The bot plays for place points only. "
              "If bounties are large, widen calls vs short stacks by hand in the adapter (no automation).",
    "run_it_twice": "Run it twice: doesn't change decisions; ignore.",
}


class Log:
    def __init__(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.fh = open(path, "a")
        self.t0 = time.time()
        self.path = path

    def stamp(self):
        s = int(time.time() - self.t0)
        return f"[+{s // 60:02d}:{s % 60:02d}]"

    def __call__(self, msg=""):
        for line in str(msg).splitlines() or [""]:
            out = f"{self.stamp()} {line}"
            print(out, flush=True)
            self.fh.write(out + "\n")
        self.fh.flush()

    def run(self, cmd, env=None):
        self("$ " + " ".join(shlex.quote(c) for c in cmd))
        t = time.time()
        env = dict(env or os.environ, PYTHONUNBUFFERED="1")     # child lines arrive (and get stamped) live
        p = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in p.stdout:
            self("    " + line.rstrip())
        p.wait()
        self(f"    -> exit {p.returncode} after {time.time() - t:.0f}s")
        return p.returncode


# ---------------------------------------------------------------------------
# announcement -> normalized spec
def strip_comments(x):
    if isinstance(x, dict):
        return {k: strip_comments(v) for k, v in x.items() if not k.startswith("_")}
    if isinstance(x, list):
        return [strip_comments(v) for v in x]
    return x


def parse_levels(blinds):
    """"10/20,15/30/5" or ["10/20", [15, 30, 5]] -> [(sb, bb, ante or None)]."""
    if blinds is None:
        return []
    if isinstance(blinds, str):
        blinds = [b for b in blinds.replace(" ", "").split(",") if b]
    out = []
    for b in blinds:
        parts = [float(x) for x in (b.split("/") if isinstance(b, str) else b)]
        if len(parts) not in (2, 3):
            raise ValueError(f"blind level {b!r}: want sb/bb or sb/bb/ante")
        out.append((parts[0], parts[1], parts[2] if len(parts) == 3 else None))
    return out


def category_order(x):
    if x is None:
        return None
    return [CATEGORY_NAMES.index(c) if isinstance(c, str) else int(c) for c in x]


def variant_dict(var):
    """The announcement's variant block -> (Variant dict, preset it started from or None)."""
    base = var.get("preset")
    if base is not None and base not in PRESETS:
        raise ValueError(f"unknown preset {base!r}; presets: {', '.join(PRESETS)}")
    d = PRESETS[base].to_dict() if base else Variant("day").to_dict()
    for k in MECHANICS:
        if var.get(k) is not None:
            d[k] = var[k]
    if var.get("category_order") is not None:
        d["category_order"] = category_order(var["category_order"])
    d["name"] = var.get("name") or base or "day"
    return d, base


def same_rules(a, b):
    return all(list(a[k]) == list(b[k]) if k in ("streets", "category_order") else a[k] == b[k] for k in MECHANICS)


def match_preset(vd):
    """Presets with identical hand evaluation; ones with a bundle on disk first."""
    hits = [p for p, v in PRESETS.items() if same_rules(v.to_dict(), vd)]
    return sorted(hits, key=lambda p: not os.path.exists(bundle_path(p)))


def bundle_path(preset):
    return os.path.join(ROOT, "bundles", f"{preset}_rng.nlb")


def load_params_map():
    with open(PARAMS_MAP) as fh:
        return strip_comments(json.load(fh))


def pick_params(preset, vd, pmap):
    """(v1 params, why) from variants/PARAMS_MAP.json."""
    if preset and preset in pmap["preset"]:
        return pmap["preset"][preset], f"PARAMS_MAP preset.{preset}"
    kind = "holdem_like" if vd["n_hole"] == 2 and vd["hole_used"] is None else "other"
    return pmap["new_variant"][kind], f"PARAMS_MAP new_variant.{kind}"


def combos_per_showdown(vd):
    nb = sum(vd["streets"])
    if vd["hole_used"] is None:
        return math.comb(vd["n_hole"] + nb, 5)
    k = vd["hole_used"]
    return math.comb(vd["n_hole"], k) * math.comb(nb, 5 - k)


def eta_minutes(vd, profile):
    a, b = ETA[profile]
    return a + b * combos_per_showdown(vd)


def ante_bb(spec):
    """One ante/bb ratio for the push/fold solve: the level where an average stack is <= 25 bb
    (where shoving starts to matter). bb-ante: the BB's ante spread over the table."""
    if spec["ante_bb_override"] is not None:
        return float(spec["ante_bb_override"]), "ante_bb_override"
    if spec["ante_type"] == "none":
        return 0.0, "no ante"
    levels = spec["levels"]
    if spec["ante_type"] == "bb-ante":
        return round(1.0 / spec["players"], 4), f"BB ante = 1 bb dead money / {spec['players']} players"
    if not levels:
        return 0.0, "ante given but no blind schedule: pass ante_bb_override"
    pick = next((lv for lv in levels if spec["starting_stack"] / lv[1] <= 25), levels[-1])
    a = pick[2] if pick[2] is not None else spec["ante_chips"]
    if not a:
        return 0.0, "ante 0 at the shoving levels"
    return round(a / pick[1], 4), f"ante {a:g} at level {pick[0]:g}/{pick[1]:g} (first level with stack <= 25 bb)"


def validate(raw):
    """-> (spec, errors, warnings, plans). spec is the normalized announcement."""
    a = strip_comments(raw)
    errors, warnings, plans = [], [], []
    spec = {}
    var = a.get("variant") or {}
    if isinstance(var, str):
        var = {"preset": var}
    try:
        vd, base = variant_dict(var)
        Variant.from_dict(vd)       # raises on a bad combination
        spec["variant"], spec["base_preset"] = vd, base
    except (ValueError, TypeError, KeyError) as e:
        errors.append(f"variant: {e}")
        vd = None
    if vd:
        if len(set(vd["ranks"])) != len(vd["ranks"]):
            errors.append(f"variant.ranks {vd['ranks']!r} repeats a rank")
        if not 1 <= vd["suits"] <= 7:
            errors.append("variant.suits must be 1..7")
        if vd["hole_used"] is not None and not 0 <= 5 - vd["hole_used"] <= sum(vd["streets"]):
            errors.append("variant: hole_used + board cards can't make 5 cards")
        if vd["n_hole"] + sum(vd["streets"]) < 5:
            errors.append("variant: fewer than 5 cards per player")
        if vd["suits"] >= 5 and vd["category_order"].index(9) < vd["category_order"].index(8):
            warnings.append("five_kind ranks below straight_flush: check the announcement")
    game = a.get("game_type", "high")
    if game not in GAME_TYPES:
        errors.append(f"game_type {game!r}: one of {', '.join(GAME_TYPES)}")
    elif game != "high":
        warnings.append(f"game_type {game}: not modeled by the evaluator")
        plans.append(PLANS[game])
    spec["game_type"] = game

    bet = a.get("betting") or {}
    if isinstance(bet, str):
        bet = {"type": bet}
    btype = bet.get("type", "no-limit")
    if btype not in BETTING:
        errors.append(f"betting.type {btype!r}: one of {', '.join(BETTING)}")
    elif btype != "no-limit":
        warnings.append(f"{btype} betting: strategy assumes no-limit")
        plans.append(PLANS[btype])
    if bet.get("raise_cap"):
        warnings.append(f"raise cap {bet['raise_cap']} per street")
        plans.append(PLANS["raise_cap"])
    if bet.get("short_allin_reopens"):
        warnings.append("a short all-in reopens betting: the bot reads the legal range from the state (fine); "
                        "add --reopen-short to tune/ab_test runs")
    spec["betting"], spec["raise_cap"] = btype, bet.get("raise_cap")

    def num(key, lo, hi, kind=float):
        x = a.get(key, OFFICIAL.get(key))
        if x is None:
            return None
        try:
            x = kind(x)
        except (TypeError, ValueError):
            errors.append(f"{key} must be a number")
            return None
        if not lo <= x <= hi:
            errors.append(f"{key} = {x} outside {lo}..{hi}")
        return x

    spec["players"] = num("players", 2, 10, int)
    spec["starting_stack"] = num("starting_stack", 1, 10 ** 9)
    spec["hands_per_level"] = num("hands_per_level", 1, 10 ** 6, int)
    spec["hand_cap"] = a.get("hand_cap", OFFICIAL["hand_cap"])
    spec["time_limit_ms"] = num("time_limit_ms", 0.01, 10 ** 6)
    try:
        spec["levels"] = parse_levels(a.get("blinds"))
    except ValueError as e:
        errors.append(str(e))
        spec["levels"] = []
    if not spec["levels"]:
        warnings.append("no blind schedule: tunes/A-B use the engine default (10/20, 15/30, 25/50, ...)")

    ante = a.get("ante") or {}
    if isinstance(ante, (int, float)):
        ante = {"type": "every-player" if ante else "none", "chips": ante}
    spec["ante_type"] = ante.get("type", "none")
    spec["ante_chips"] = ante.get("chips") or 0
    spec["ante_bb_override"] = ante.get("ante_bb_override")
    if spec["ante_type"] not in ANTE_TYPES:
        errors.append(f"ante.type {spec['ante_type']!r}: one of {', '.join(ANTE_TYPES)}")
    elif spec["ante_type"] == "bb-ante":
        plans.append("BB ante: in to_obs set Obs.ante = 0, add the BB's ante to pot (not to bets), leave it out "
                     "of history. Push/fold is solved with the BB ante spread as a per-player ante.")
    elif spec["ante_type"] == "every-player" and not spec["ante_chips"] and not any(lv[2] for lv in spec["levels"]):
        errors.append("ante.type every-player but no ante.chips and no sb/bb/ante levels")
    if spec["ante_type"] in ANTE_TYPES and spec["starting_stack"] and spec["players"]:
        spec["ante_bb"], spec["ante_bb_why"] = ante_bb(spec)

    pts = a.get("points")
    if pts is None:
        errors.append("points: fill in the points for 1st..last (kit payouts / ICM table)")
    else:
        try:
            pts = [float(x) for x in (pts.split(",") if isinstance(pts, str) else pts)]
        except ValueError:
            errors.append("points must be numbers")
            pts = None
    if pts is not None and spec.get("players"):
        if len(pts) < spec["players"]:
            warnings.append(f"{len(pts)} points for {spec['players']} players: padding with 0")
            pts = pts + [0.0] * (spec["players"] - len(pts))
        elif len(pts) > spec["players"]:
            errors.append(f"{len(pts)} points for {spec['players']} players")
        if any(pts[i] < pts[i + 1] for i in range(len(pts) - 1)):
            warnings.append("points are not decreasing by place: check the table")
        if pts and max(pts) <= 0:
            errors.append("points are all zero")
    spec["points"] = pts
    if spec.get("players") and spec["players"] > 8:
        warnings.append(f"{spec['players']} seats: push/fold charts cover up to 8 players left; earlier spots use "
                        "the postflop/preflop engine (fine, checked at 9-10 seats)")
    tl = spec.get("time_limit_ms")
    if tl is not None and tl != 1.0:
        warnings.append(f"time limit {tl:g} ms: go.py appends PrepBot.deadline = {0.6 * tl / 1000:.6f} s to a copy "
                        "of the adapter")
        if tl < 0.5:
            plans.append("Time limit under 0.5 ms: also consider --params params/nlhe_final_legacy.json (cheaper "
                         "rules engine) and check p99.9 in the day.py checks.")

    sp = a.get("special_rules") or {}
    for k in SPECIAL:
        if sp.get(k):
            warnings.append(f"special rule {k}: not modeled")
            plans.append(PLANS[k])
    unknown = [k for k in sp if k not in SPECIAL + ("other",)]
    if unknown:
        errors.append(f"special_rules: unknown keys {unknown} (use 'other' for free text)")
    if sp.get("other"):
        warnings.append(f"other rule (read VARIANTS.md, decide by hand): {sp['other']}")
    spec["special"] = {k: sp.get(k) for k in SPECIAL + ("other",) if sp.get(k)}

    kit = a.get("kit") or {}
    spec["kit"] = kit
    if kit.get("raise_semantics", "raise-to") not in ("raise-to", "raise-by"):
        errors.append("kit.raise_semantics: raise-to or raise-by")
    if kit.get("raise_semantics") == "raise-by":
        plans.append("Kit uses raise-BY: to_obs must give min_raise_to/max_raise_to as raise-TO totals (add the "
                     "current bet) and to_kit_action must subtract it again.")
    if kit.get("numpy_available") is False:
        warnings.append("no numpy on the host: every build uses --pure-python")
    if kit.get("reuses_bot_across_tables"):
        plans.append("The kit reuses one bot object across tables: build a new core (self.core = make_core()) "
                     "at its new-game hook, or state leaks between tables.")
    return spec, errors, warnings, plans


def check_adapter(path, spec):
    """Problems that would only show up in the kit: unfilled template, missing class."""
    errs, warns = [], []
    if not path or not os.path.exists(path):
        return [f"adapter {path} not found"], warns
    text = open(path).read()
    if 'raise NotImplementedError("map the starter kit' in text or "raise NotImplementedError(\"map our action" in text:
        errs.append(f"{path} is still the unfilled template (to_obs / to_kit_action raise NotImplementedError)")
    cls = spec["kit"].get("bot_class")
    if cls and f"class {cls}" not in text:
        warns.append(f"adapter has no 'class {cls}' (kit.bot_class)")
    meth = spec["kit"].get("method")
    if meth and f"def {meth}(" not in text:
        warns.append(f"adapter has no 'def {meth}(' (kit.method)")
    if "gc_settle()" in text and 'if "gc_settle" in globals()' not in text:
        warns.append("bare gc_settle() in the adapter: keep the guarded block from adapter_template.py")
    return errs, warns


def summary(spec, preset, params, why):
    vd = spec["variant"]
    order = " < ".join(CATEGORY_NAMES[c] for c in vd["category_order"])
    board = "+".join(str(x) for x in vd["streets"])
    used = "any 5 of hole+board" if vd["hole_used"] is None else f"exactly {vd['hole_used']} hole + " \
        f"{5 - vd['hole_used']} board"
    lines = [
        f"Game: {vd['name']} ({spec['game_type']}, {spec['betting']}"
        + (f", raise cap {spec['raise_cap']}" if spec["raise_cap"] else "") + ")",
        f"  deck {len(vd['ranks'])} ranks {vd['ranks']} x {vd['suits']} suits = {len(vd['ranks']) * vd['suits']} "
        f"cards; {vd['n_hole']} hole cards; board {board}; {used}; ace low {'yes' if vd['ace_low_straight'] else 'no'}",
        f"  ranking (weakest first): {order}",
        f"  -> {'preset ' + preset + ' (identical hand evaluation)' if preset else 'NEW variant (no preset matches)'}",
        f"Table: {spec['players']} players, stack {spec['starting_stack']:g}, "
        f"{len(spec['levels']) or 'default'} blind levels every {spec['hands_per_level']} hands"
        + (f" ({', '.join(f'{lv[0]:g}/{lv[1]:g}' + (f'/{lv[2]:g}' if lv[2] else '') for lv in spec['levels'][:6])}"
           + (", ..." if len(spec["levels"]) > 6 else "") + ")" if spec["levels"] else "")
        + f", hand cap {spec['hand_cap']}",
        f"  ante: {spec['ante_type']}" + (f" {spec['ante_chips']:g} chips" if spec["ante_chips"] else "")
        + f" -> push/fold solved at ante {spec['ante_bb']:g} bb ({spec['ante_bb_why']})",
        f"  points 1st..last: {','.join(f'{p:g}' for p in spec['points'])}",
        f"  time limit {spec['time_limit_ms']:g} ms per decision",
        f"Kit: {spec['kit'].get('raise_semantics', 'raise-to')}, cards {spec['kit'].get('card_format', '?')}, "
        f"class {spec['kit'].get('bot_class', '?')}.{spec['kit'].get('method', '?')}, "
        f"submit as {spec['kit'].get('file_name', 'bot.py')}",
        f"Params for v1: {params} ({why})",
    ]
    if spec["special"]:
        lines.append(f"Special rules: {spec['special']}")
    return "\n".join(lines)


def pts_arg(spec):
    return ",".join(f"{p:g}" for p in spec["points"])


def schedule_arg(spec):
    return ",".join(f"{lv[0]:g}/{lv[1]:g}" for lv in spec["levels"])


def ab_cmd(spec, bundle, a, b):
    cmd = [".venv/bin/python", "scripts/ab_test.py", "--bundle", bundle, "--keep-bundle", "--a", a, "--b", b,
           "--sngs", "400", "--workers", "3", "--points", pts_arg(spec), "--fields", "zoo,passive,aggressive"]
    if spec["levels"]:
        cmd += ["--schedule", schedule_arg(spec)]
    if spec["hands_per_level"]:
        cmd += ["--hands-per-level", str(spec["hands_per_level"])]
    cmd += ["--stack", f"{spec['starting_stack']:g}"]
    if spec["ante_type"] == "every-player" and (spec["ante_chips"] or 0) > 0:
        cmd += ["--ante", f"{spec['ante_chips']:g}"]
    if spec["hand_cap"]:
        cmd += ["--max-hands", str(spec["hand_cap"])]
    return " ".join(shlex.quote(c) for c in cmd)


def deadline_adapter(adapter, spec, tag):
    """The adapter, plus a deadline line when the time limit isn't 1 ms."""
    tl = spec["time_limit_ms"]
    text = open(adapter).read()
    if tl == 1.0 or "PrepBot.deadline" in text:
        return adapter
    out = os.path.join(ROOT, "dist", "day", f"{tag}_adapter.py")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as fh:
        fh.write(text.rstrip("\n") + f"\n\nPrepBot.deadline = {0.6 * tl / 1000:.6f}   # go.py: time limit {tl:g} ms\n")
    return out


def day_build(tag, adapter, kit_cmd, spec, sngs, workers, extra):
    cmd = [PY, "scripts/day.py", "build", tag, "--adapter", adapter, "--sngs", str(sngs), "--workers", str(workers)]
    cmd += extra
    if kit_cmd:
        cmd += ["--kit-cmd", kit_cmd]
    if spec["kit"].get("numpy_available") is False:
        cmd.append("--pure-python")
    return cmd


def table_script(tag, vpath, spec, params, adapter, kit_cmd, profile, sngs, workers):
    """Background chain: build_tables -> range_eq -> day.py build <tag>_v1."""
    base = f"bundles/day/{tag}_base.nlb"
    rng = f"bundles/day/{tag}_base_rng.nlb"
    work = f"bundles/day/work_{tag}"
    prof_bt = ["--laptop"] if profile == "laptop" else ["--laptop"] + FAST_BT
    prof_re = ["--laptop"] if profile == "laptop" else ["--laptop"] + FAST_RE
    q = lambda c: " ".join(shlex.quote(x) for x in c)  # noqa: E731
    bt = [PY, "-m", "gpu.build_tables", "--variant", vpath, "--out", base, "--work", work, "--skip", "pushfold",
          "--payouts", pts_arg(spec)] + prof_bt
    re = [PY, "-m", "gpu.range_eq", "--bundle", base, "--out", rng, "--work", work] + prof_re
    v1 = day_build(f"{tag}_v1", adapter, kit_cmd, spec, sngs, workers,
                   ["--bundle", rng, "--params", params, "--points", pts_arg(spec), "--ante-bb", str(spec["ante_bb"])])
    lines = [
        "#!/bin/bash",
        f"# go.py background table build for {tag} ({profile} profile)",
        f"cd {shlex.quote(ROOT)}",
        f"export OMP_NUM_THREADS={workers} MKL_NUM_THREADS={workers} PYTORCH_ENABLE_MPS_FALLBACK=1 PYTHONUNBUFFERED=1",
        "set -e",
        "T0=$(date +%s); el() { echo \"[go +$(( ($(date +%s) - T0) / 60 ))m$(( ($(date +%s) - T0) % 60 ))s] $*\"; }",
        "el build_tables start",
        # a failure (seen: MPS out of memory when other jobs hold GPU memory) retries once with
        # smaller chunks, reusing the finished stages
        q(bt) + " || { el 'build_tables failed: retry with --chunk 50000 --reuse'; " + q(bt + RETRY) + "; }",
        "el build_tables done",
        q(re) + " || { el 'range_eq failed: retry with --chunk 50000'; " + q(re + RETRY) + "; }",
        "el range_eq done",
        q(v1),
        f"el {tag}_v1 built: python scripts/day.py submit {tag}_v1",
        "echo GO_TABLES_DONE",
    ]
    return "\n".join(lines) + "\n", v1, rng


# Quicker-than-laptop settings (measured in DAYOF.md): fewer Monte Carlo samples, same nets.
RETRY = ["--chunk", "50000", "--reuse"]
FAST_BT = ["--rows-budget", "2000000", "--eq-cap", "20000", "--post-samples", "60000", "--post-rollouts", "24",
           "--val-samples", "800", "--val-rollouts", "200", "--epochs", "10"]
FAST_RE = ["--samples", "20000", "--k", "24", "--val-samples", "300", "--val-k", "64", "--epochs", "10"]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("announce", help="variants/ANNOUNCE.json filled in from the announced rules")
    ap.add_argument("--adapter", help="your filled-in adapter (copy of adapter_template.py)")
    ap.add_argument("--kit-cmd", help='kit simulator command with "{bot}" (default: kit.sim_cmd in the JSON)')
    ap.add_argument("--tag", default="day", help="tag prefix: builds <tag>_v0, <tag>_v1 (default day)")
    ap.add_argument("--check", action="store_true", help="validate, summarize and plan; build nothing")
    ap.add_argument("--v0", choices=("always", "never"), default="always",
                    help="build the heuristic v0 even when a preset bundle fits (default always)")
    ap.add_argument("--tables", choices=("fast", "laptop"), default="fast",
                    help="profile for a new variant's background table build (default fast; see DAYOF.md)")
    ap.add_argument("--variant-out", default=os.path.join("variants", "day.json"))
    ap.add_argument("--sngs", type=int, default=20, help="SNGs per day.py check (2 seats each)")
    ap.add_argument("--workers", type=int, default=3, help="CPU workers/threads for builds")
    ap.add_argument("--foreground-tables", action="store_true", help="wait for the table build (tests/timing)")
    args = ap.parse_args(argv)

    os.makedirs(LOGDIR, exist_ok=True)
    log = Log(os.path.join(LOGDIR, f"go_{args.tag}.log"))
    log(f"go.py {' '.join(argv if argv is not None else sys.argv[1:])}   ({time.strftime('%Y-%m-%d %H:%M:%S')})")
    try:
        with open(args.announce) as fh:
            raw = json.load(fh)
    except (OSError, json.JSONDecodeError) as e:
        log(f"ERROR reading {args.announce}: {e}")
        return 2
    spec, errors, warnings, plans = validate(raw)
    if errors:
        for e in errors:
            log("ERROR: " + e)
        log("fix the announcement JSON (see variants/ANNOUNCE.md) and rerun")
        return 2
    vd = spec["variant"]
    hits = match_preset(vd)
    preset = hits[0] if hits else None
    has_bundle = preset is not None and os.path.exists(bundle_path(preset))
    pmap = load_params_map()
    params, why = pick_params(preset if has_bundle else None, vd, pmap)
    log(summary(spec, preset, params, why))

    if not args.check:
        aerr, awarn = check_adapter(args.adapter, spec)
        warnings += awarn
        if aerr:
            for e in aerr:
                log("ERROR: " + e)
            return 2
    for w in warnings:
        log("WARNING: " + w)
    for p in plans:
        log("PLAN: " + p)

    kit_cmd = args.kit_cmd or spec["kit"].get("sim_cmd")
    if kit_cmd:
        kit_cmd = kit_cmd.replace("{py}", shlex.quote(PY))     # {py} = this repo's python
    if kit_cmd and "{bot}" not in kit_cmd:
        log("ERROR: the kit command needs {bot} where the bot file goes")
        return 2
    if not kit_cmd:
        log("WARNING: no kit simulator (--kit-cmd or kit.sim_cmd): builds are checked on our engine only")

    tags = [f"{args.tag}_v0", f"{args.tag}_v1"]
    taken = [t for t in tags if os.path.exists(os.path.join(ROOT, "frozen", t))]
    if taken and not args.check:
        log(f"ERROR: frozen/{taken[0]} exists (tags are never overwritten): rerun with a new --tag")
        return 2

    if preset:
        vpath = preset
        log(f"variant: preset {preset}" + ("" if has_bundle else " (no bundle on disk: building tables)"))
    else:
        vpath = args.variant_out
        log(f"variant: writing {vpath}")
    if args.check:
        log("--check: nothing built")
        return 0
    if not preset:
        with open(os.path.join(ROOT, vpath), "w") as fh:
            json.dump(vd, fh, indent=1)
        log.run([PY, "scripts/variant_stats.py", "--variant", vpath, "--samples", "20000"])

    adapter = deadline_adapter(args.adapter, spec, args.tag)
    if adapter != args.adapter:
        log(f"adapter with deadline line: {os.path.relpath(adapter, ROOT)}")
    name = spec["kit"].get("file_name") or "bot.py"
    done = []

    bg_log = v1_cmd = None
    if not has_bundle:
        eta = eta_minutes(vd, args.tables)
        script, v1_cmd, rng = table_script(args.tag, vpath, spec, params, adapter, kit_cmd, args.tables,
                                           args.sngs, args.workers)
        spath = os.path.join(ROOT, "bench", "dayof", f"go_{args.tag}_tables.sh")
        bg_log = os.path.join("bench", "dayof", f"go_{args.tag}_tables.log")
        with open(spath, "w") as fh:
            fh.write(script)
        os.chmod(spath, 0o755)
        log(f"tables: no bundle for this variant -> background build ({args.tables} profile, "
            f"~{eta:.0f} min + ~2 min for the v1 checks on an idle laptop): {os.path.relpath(spath, ROOT)}")
        log(f"        progress: tail -f {bg_log}")
        if args.foreground_tables:
            bg = None
        else:
            bg = subprocess.Popen(["bash", spath], cwd=ROOT, stdout=open(os.path.join(ROOT, bg_log), "w"),
                                  stderr=subprocess.STDOUT, start_new_session=True)
            log(f"        started, pid {bg.pid}")

    if args.v0 == "always" or not has_bundle:
        log(f"--- {tags[0]}: heuristic tables, exact rules (submittable while tables build) ---")
        rc = log.run(day_build(tags[0], adapter, kit_cmd, spec, args.sngs, args.workers,
                               ["--heuristic", vpath, "--params", pmap["heuristic_v0"]]))
        if rc:
            log(f"{tags[0]} FAILED: fix the adapter (see the output above); the kit check is the usual cause")
            return 1
        done.append(tags[0])
        log(f"*** {tags[0]} READY: python scripts/day.py submit {tags[0]} --as {name}")

    if has_bundle:
        log(f"--- {tags[1]}: preset bundle {preset}, params {params}, points/ante re-solved ---")
        rc = log.run(day_build(tags[1], adapter, kit_cmd, spec, args.sngs, args.workers,
                               ["--preset", preset, "--params", params, "--points", pts_arg(spec),
                                "--ante-bb", str(spec["ante_bb"])]))
        if rc:
            log(f"{tags[1]} FAILED; keep {tags[0]}")
        else:
            done.append(tags[1])
            log(f"*** {tags[1]} READY: python scripts/day.py submit {tags[1]} --as {name}")
        gate = ab_cmd(spec, f"bundles/day/{tags[1]}.nlb", f"prep:{params}", f"heur:{pmap['heuristic_v0']}")
    else:
        if args.foreground_tables:
            log.run(["bash", os.path.join("bench", "dayof", f"go_{args.tag}_tables.sh")])
            if os.path.exists(os.path.join(ROOT, "frozen", tags[1])):
                done.append(tags[1])
        gate = ab_cmd(spec, f"bundles/day/{tags[1]}.nlb", f"prep:{params}", f"heur:{pmap['heuristic_v0']}")

    log("")
    log("=== COPY THESE ===")
    if done:
        log(f"python scripts/day.py submit {done[-1]} --as {name}     # then upload dist/SUBMIT/{name}")
    if not has_bundle and tags[1] not in done:
        log(f"# {tags[1]} builds itself when the tables finish (ETA ~{eta_minutes(vd, args.tables):.0f} min); "
            f"watch for GO_TABLES_DONE in: tail -f {bg_log}")
        log(f"python scripts/day.py submit {tags[1]} --as {name}     # once it says '{tags[1]} built'")
        log("# if the background chain stopped after range_eq, build v1 by hand:")
        log("  " + " ".join(shlex.quote(c) for c in v1_cmd).replace(PY, ".venv/bin/python"))
    log("python scripts/day.py rollback                          # back to the previous submission (sha-checked)")
    log("python scripts/day.py status                            # what is live")
    log(f"# A/B gate v1 vs v0 under the kit's rules (~400 paired SNGs):\n  {gate}")
    log(f"log: {os.path.relpath(log.path, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

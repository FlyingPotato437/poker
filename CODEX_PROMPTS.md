# Codex prompts for the 60-minute build, in time order

Codex reads `AGENTS.md` by itself, so each prompt is short and self-contained. Fastest path:
`scripts/codex_day.sh --kit <starter kit dir>` opens Codex with prompt 1 preloaded;
`scripts/codex_day.sh --kit <dir> auto` runs prompts 1-4 unattended (about 10 min,
measured in `bench/codex/rehearsal.md`). To paste by hand, replace `{KIT}` with the starter
kit folder (and `{CHANGE}`, `{SYMPTOM}`, `{RESULTS}` where they appear).

After each answer, read its **Check** line before going on. If a check fails, paste the
failing output back to Codex with "fix this, new tag".

## 0. Preflight (before T+0, 1 min)

```prompt
Preflight only, change nothing. Run `.venv/bin/python -c "import numpy, torch; print(numpy.__version__, torch.__version__, torch.backends.mps.is_available())"`, `.venv/bin/python scripts/day.py status`, and `ls scripts/go.py variants/ANNOUNCE.json DAYOF.md frozen/`. Report each result in one line, and say whether the day-of flow in AGENTS.md can run as written (go.py present or not).
```

**Check:** torch imports (else a new variant can't build tables: plan on heuristic v0 only);
`go.py` present; `frozen/rc1` present.

## 1. Rules (T+0 to T+3)

```prompt
The starter kit is in `{KIT}`. Read its README (and any rules/announcement text there); do not read the simulator's source. Then: `cp variants/ANNOUNCE.json variants/day_announce.json` and fill it in from the kit, following `variants/ANNOUNCE.md` and the examples in `variants/examples/`: variant (a preset name only if the hand evaluation is identical to one, else preset null plus the mechanics that differ: n_hole, hole_used, ranks, suits, streets, category_order, ace_low_straight), betting, players, starting_stack, blinds (all levels), hands_per_level, ante, hand_cap, points 1st..last, time_limit_ms, special_rules, and kit (raise_semantics, card_format, bot_class, method, file_name, and sim_cmd = the kit simulator command using `{py}` for our python and `{bot}` for the bot file). Run `.venv/bin/python scripts/go.py variants/day_announce.json --check` and fix the JSON until it reports no ERROR. Finish with: the go.py summary verbatim, every WARNING/PLAN line, a two-column table "kit says / JSON has" for every rule, and anything the kit leaves unclear.
```

**Check:** every row of the "kit says / JSON has" table agrees; points in place order; the
summary says `preset <x>` or `NEW variant` as you expect; ante bb value is sensible
(ante / bb at the shoving levels).

## 2. Adapter (T+3 to T+10)

```prompt
Write the adapter for the starter kit in `{KIT}` (read its README for the state, cards and moves; do not read the simulator source). `cp adapter_template.py my_adapter.py` and implement `to_obs`, `to_kit_action` and the kit's bot class/method (`kit.bot_class` / `kit.method` in `variants/day_announce.json`), following the Obs conventions in AGENTS.md exactly. Keep `make_core`, `_tables`, the guarded `gc_settle` block, and `self.core = make_core()` in `__init__`. Then test on heuristic tables: run `.venv/bin/python scripts/go.py variants/day_announce.json --check` (it writes nothing), package with `.venv/bin/python scripts/package_bot.py --variant <the preset name, or variants/day.json written from the JSON's variant mechanics if it's new> --adapter my_adapter.py --out dist/try.py`, and run the kit simulator on dist/try.py (the sim_cmd from the JSON), also with its parity option if it has one. Iterate until 0 exceptions, 0 illegal moves, and parity 100%. Report the final simulator summary lines verbatim and list each bug you fixed.
```

**Check:** final simulator line shows `0 exceptions, 0 illegal`; parity `N/N` identical (or
the kit has no parity mode). Points per game near or above the fair share.

## 3. Build v0 (and v1 for a preset) (T+10)

```prompt
Run `.venv/bin/python scripts/go.py variants/day_announce.json --adapter my_adapter.py` (the kit simulator command comes from kit.sim_cmd in the JSON). For a NEW variant this starts the GPU table build, so request escalated permission to run it outside the sandbox (AGENTS.md); if that is refused, stop and tell me to run `scripts/codex_day.sh build`. If scripts/go.py does not exist, run the equivalent `scripts/day.py build` from AGENTS.md step 4 instead. If a tag already exists, rerun with a new `--tag`. Do not submit. Report: every READY line, every WARNING and PLAN line, each build's `check numpy` / `check no numpy` lines and kit simulator summary, the table-build ETA and log path if one started, and the `=== COPY THESE ===` block verbatim.
```

**Check:** `day_v0` built and frozen; `errors/illegal 0` for numpy and no numpy; kit
simulator 0 exceptions / 0 illegal. Preset: `day_v1` too. New variant: a background table
build started (log path printed).

## 3b. Fix a failed build (used by `auto` when the host build fails)

```prompt
The build `scripts/go.py variants/day_announce.json --adapter my_adapter.py` failed; its log is {LOG}. Read the last 60 lines, find the cause (usually my_adapter.py or variants/day_announce.json; never edit frozen/, nolimit/, gpu/ or params/), fix it, and re-test with package_bot.py --variant ... --out dist/try.py plus the kit simulator (sim_cmd in the JSON, with parity if it has it) until 0 exceptions and 0 illegal. Do not run go.py or day.py build yourself; the driver reruns it on the host. Report the cause and the fix.
```

**Check:** the cause is named and the kit simulator is clean on `dist/try.py`.

## 4. Submit v0 (T+12, before the first practice round)

```prompt
Pick the tag to submit from `dist/day/*.check.json`: it must have kit_check 0 and errors_or_illegal 0 in every check; prefer a table-built tag (bundle not "heuristic ...") whose points and ante_bb match the current variants/day_announce.json (newest such tag), else the newest heuristic tag. Never pick a tag built with outdated points. Run `.venv/bin/python scripts/day.py submit <tag> --as <kit.file_name from variants/day_announce.json>`, then `.venv/bin/python scripts/day.py status`. Report the tag, sha (12 chars), and the absolute path of the file to upload.
```

**Check:** status line ends in `matches`. A human uploads `dist/SUBMIT/<file>` and confirms
the site shows it.

## 5. v1 for a new variant (T+15 to T+40, when the tables finish)

```prompt
Check the background table build: `tail -30 bench/dayof/go_day_tables.log` (or the go_<tag>_tables.log that go.py printed). If it ends with GO_TABLES_DONE, report the day_v1 check lines and its kit simulator summary, then run the A/B gate command go.py printed in bench/dayof/go_day.log (v1 vs v0 under the kit's rules) and report the mean and every cell. If the build is still running, report the last stage and elapsed time and stop. If it failed, report the error and the resume command from AGENTS.md. Do not submit.
```

**Check:** `day_v1` built with kit check ok; the A/B mean is positive and no cell is
significantly negative. Then run prompt 4 again (it submits `day_v1`).

## 6. Rule change mid-build (whenever announced)

```prompt
The organizers just changed a rule: {CHANGE}. Update variants/day_announce.json, run `.venv/bin/python scripts/go.py variants/day_announce.json --check` and show the changed summary line (and the new ante bb). Then, using a tag that is not in frozen/ yet: (a) preset: `.venv/bin/python scripts/go.py variants/day_announce.json --adapter my_adapter.py --tag <new> --v0 never`; (b) new variant whose tables are done (bundles/day/day_base_rng.nlb exists): `.venv/bin/python scripts/day.py build <new>_v1 --bundle bundles/day/day_base_rng.nlb --params <same params as day_v1, see dist/day/day_v1.check.json or PARAMS_MAP> --points <new points> --ante-bb <new ante bb> --adapter my_adapter.py --kit-cmd "<sim_cmd with {py} = .venv/bin/python>"`; (c) new variant whose tables are still building: build nothing now (the heuristic v0 has no push/fold tables, so points and antes don't change it), say that the day_v1 the background chain builds will use the OLD values and must not be submitted, and print the exact (b) command to run once GO_TABLES_DONE appears. Report which case applied, and the new tag's checks and kit simulator summary if one was built. Do not submit.
```

**Check:** the summary shows the new value; case (a)/(b): a new tag (never an old one) built
with `errors/illegal 0` and kit ok, then prompt 4 with that tag. Case (c): the command for
later is printed; don't submit `day_v1` once it lands, build and submit the new tag instead.

## 7. Something misbehaves (practice round)

```prompt
Our submitted bot misbehaves in the practice round: {SYMPTOM}. FIRST run `.venv/bin/python scripts/day.py rollback` and `.venv/bin/python scripts/day.py status` and report them. Only then look for the cause in my_adapter.py, dist/day/*.check.json and bench/dayof/go_*.log, without editing frozen/, nolimit/, gpu/ or params/. Propose a fix and the rebuild command with a new tag; do not submit.
```

**Check:** rollback ran first; status shows the previous tag and `matches`.

## 8. Final check (T+55)

```prompt
Run `.venv/bin/python scripts/day.py status`. Confirm the current tag is the one we intended (the latest tag that passed every check), that its file matches its frozen sha, and list every built tag with its kit result. Change nothing.
```

**Check:** `matches`; intended tag; uploaded file is `dist/SUBMIT/<file>`.

## 9. After each scored round (T1..T6)

```prompt
Scored results so far: {RESULTS}. Which tag and params are live: `.venv/bin/python scripts/day.py status`. Following AGENTS.md "Should we switch strategy after T1?" (bench/adapt/README.md first if it exists), should we keep the current bot or switch? Compare our x-fair (points per table / fair share) only with absolute x-fair calibration, never with paired A-B percentages. Quote the rule, the threshold, the calibration file and line, and our numbers. Change nothing.
```

**Check:** the answer cites a specific rule and number. Decide once, before T3-T4; don't
switch back and forth.

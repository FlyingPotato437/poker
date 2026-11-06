# AGENTS.md: instructions for a coding agent (Codex) on the day

You are helping two people build a poker bot in 60 minutes for an announced variant. The
pipeline already exists. Your job is to fill in two files and run commands, not to write a
new bot. Python: `.venv/bin/python`. Work offline.

## Read first
1. `DAYOF.md`: the steps in order. Follow it.
2. `variants/ANNOUNCE.md`: every key of the rules file.
3. `adapter_template.py`: the adapter checklist at the top.

## Do
1. Copy `variants/ANNOUNCE.json` to `variants/day_announce.json`. Fill it from the announced rules and the starter kit's README. Fill in only what the announcement says. Mark anything unclear in `special_rules.other`, then ask.
2. Run `.venv/bin/python scripts/go.py variants/day_announce.json --check`. Show the humans its summary and every WARNING or PLAN line.
3. Copy `adapter_template.py` to `my_adapter.py`. Implement `to_obs`, `to_kit_action` and the kit's bot class and method. Use raise-TO totals in `Obs`. Blinds are `POST` in history, and antes are left out of history. Keep the guarded `gc_settle` block. Look at `examples/adapter_mock_solution.py` and `examples/answers/kit2_adapter.py` for two complete examples.
4. Run `.venv/bin/python scripts/go.py variants/day_announce.json --adapter my_adapter.py --kit-cmd "<kit simulator> {bot}"`. Report every `READY` line, every WARNING and the `=== COPY THESE ===` block, word for word.
5. Before any submit, the kit simulator must show 0 exceptions and 0 illegal moves. If the kit allows it, also run a parity check (`examples/mock_kit.py` / `examples/kit2/simulate.py --parity` style) and get 100% identical decisions.
6. Submit only with `.venv/bin/python scripts/day.py submit <tag> --as <file name>`. Roll back with `.venv/bin/python scripts/day.py rollback`. Check what is live with `.venv/bin/python scripts/day.py status`.

## Never
- Never edit `frozen/` (release tags, sha-checked), `nolimit/runtime.py`, `nolimit/engine.py`, `nolimit/harness.py`, `nolimit/rivals.py` or `gpu/`. Strategy code is out of scope. If something there looks wrong, report it.
- Never change or hand-edit `params/*.json`. The params used per variant come only from `variants/PARAMS_MAP.json`, and only when the humans ask.
- Never submit a file that did not come from `day.py build` (it runs the checks, the kit simulator and the freeze). Never reuse a tag: rerun with a new `--tag`.
- Never use the network, and never `pip install`.
- Don't guess a rule. Ask.

## When something fails
- go.py stops at the failing step and prints why. Earlier tags stay frozen and submittable.
- The kit check fails: fix `my_adapter.py` (card ids, raise-to vs raise-by, check vs call, the pot), then rerun go.py with `--tag day2`.
- A bot misbehaves in a practice round: run `day.py rollback` first, then investigate.
- The table build is slow or crashed: keep v0 live. The log is `bench/dayof/go_<tag>_tables.log`, and it is resumable with `bash bench/dayof/go_<tag>_tables.sh`.

# Codex prompts for the day, in DAYOF.md order

Paste these one at a time. Replace the `<...>` parts. Codex reads `AGENTS.md` by itself.
After each prompt, check its answer against the **Check** line before going on.

**1. Rules into ANNOUNCE.json (T+0)**
> Read the starter kit README in `<kit path>` and the announcement text below. Copy `variants/ANNOUNCE.json` to `variants/day_announce.json`. Fill it in using `variants/ANNOUNCE.md`: variant (a preset name if the rules match one exactly, otherwise the mechanics), betting, players, starting stack, blinds, hands per level, ante, hand cap, points 1st..last, time limit per decision, special rules, and kit (raise-to or raise-by, card format, bot class and method, the file name to submit, the simulator command with `{bot}`). Don't guess: list anything the text leaves unclear. Then run `.venv/bin/python scripts/go.py variants/day_announce.json --check` and paste its output. Announcement: `<paste>`

Check: the summary line for each rule matches the announcement, the points are in the right order, and preset vs NEW variant is what you expect. Every WARNING and PLAN line is read out.

**2. Adapter (T+2 to T+10)**
> Copy `adapter_template.py` to `my_adapter.py`. Implement `to_obs`, `to_kit_action` and the kit's bot class `<class>.<method>`, following the checklist at the top of the template. `examples/answers/kit2_adapter.py` is a complete example for a kit with int cards and street totals. Map the kit's state to `Obs`: seat and button, sb/bb/ante, `hand_no`, street index, card ids, stacks behind, bets this street, `in_hand`, pot, `to_call`, `min_raise_to`/`max_raise_to` as raise-TO totals, and history with blinds as `POST` and antes left out. Keep the guarded `gc_settle` block. Then package it heuristically and run the kit simulator: `.venv/bin/python scripts/package_bot.py --variant <preset or variants/day.json> --adapter my_adapter.py --out dist/try.py` and `<kit simulator> dist/try.py`. If the kit lets you, run a parity check (the bot fed our `Obs` directly vs through the kit) and report the identical-decision rate.

Check: 0 exceptions, 0 illegal moves, parity 100% (or explained), and the raise amount conversion is right for raise-by kits.

**3. go.py (T+10)**
> Run `.venv/bin/python scripts/go.py variants/day_announce.json --adapter my_adapter.py --kit-cmd "<kit simulator> {bot}"`. Paste every `READY` line, every WARNING and PLAN line, the elapsed times, and the `=== COPY THESE ===` block, word for word. Don't submit anything.

Check: `day_v0 READY` appears, the kit check inside it passed, and "errors/illegal 0" is shown for both numpy and no-numpy. For a new variant, a table-build ETA and log path are printed.

**4. Submit v0 (T+12)**
> Run `.venv/bin/python scripts/day.py submit day_v0 --as <file name>`, then `.venv/bin/python scripts/day.py status`. Report the sha and the path of the file to upload.

Check: the status line ends in `matches`. Upload `dist/SUBMIT/<file name>` yourself.

**5. v1 (preset: minutes; new variant: when the tables finish)**
> Show the last 20 lines of `bench/dayof/go_day_tables.log` (new variant) or `bench/dayof/go_day.log` (preset). Has `day_v1` been built and frozen? If yes, run the A/B gate command go.py printed and report the mean and every cell. Don't submit.

Check: `day_v1 built` or `READY`, and a kit check with 0 errors. The A/B mean is positive, with no cell significantly negative. Then submit: `day.py submit day_v1`.

**6. Rule change mid-build**
> The organizers changed `<rule>` to `<value>`. Update `variants/day_announce.json`, run `go.py --check`, then run go.py again with `--tag day2 --v0 never` (preset) or the `day.py build day2_v1 ...` line from `DAYOF.md` (new variant, tables already built). Report the READY lines.

Check: the new value shows in the summary, and a new tag (never an old one) is built.

**7. Something misbehaves**
> The bot we submitted is `<symptom>` in the practice round. Run `.venv/bin/python scripts/day.py rollback` and `status` now. Then look for the cause in `my_adapter.py` and the latest `bench/dayof/go_*.log`, without editing `frozen/`, `nolimit/` or `params/`.

Check: the rollback ran first, and status shows the previous tag with `matches`.

**8. Between scored rounds (T1–T6)**
> Our results so far: `<round: points, place, score ÷ fair>`. Per `bench/adapt/README.md` and PLAYBOOK.md "T1–T6", should we keep the current bot or switch? Quote the rule you applied and the numbers it used. Don't change anything yet.

Check: the answer cites a specific rule and threshold. Decide once, before T3–T4. Don't switch back and forth.

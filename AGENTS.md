# AGENTS.md: briefing for Codex on tournament day

You are the coding assistant for a two-person team in a 60-minute poker-bot build phase
(No Limit tournament: 8-seat no-limit sit-and-go, 1 ms per decision in Python, 100 MB file,
points by finishing place). **The bot already exists in this repo.** Your job: write ONE
adapter file for the organizers' starter kit, fill in the rules file, and run the build /
check / submit commands. Do not write a new bot or change strategy.

Python is `.venv/bin/python` (run everything from the repo root). Work offline: no network,
no `pip install`.

## Hard rules (never break these)

- Never edit `frozen/` (sha-checked release tags), `nolimit/` (runtime.py is the strategy),
  `gpu/`, or `params/*.json`. Never hand-edit a packaged bot in `dist/`. If one of them looks
  wrong, stop and report it.
- `day.py build` freezes every tag. Never reuse a tag, never delete or overwrite anything in
  `frozen/`. If a tag exists, use a new name (`v0b`, `day2`, ...).
- Only submit a file built by `scripts/day.py build` (or `go.py`, which calls it). It runs
  the clean-interpreter checks, the kit simulator and the freeze.
- Before every submit: the build output shows `errors/illegal 0` for numpy and no numpy,
  and the kit simulator shows 0 exceptions and 0 illegal moves.
- A submitted bot misbehaves: `.venv/bin/python scripts/day.py rollback` FIRST, investigate after.
- Don't guess a rule. If the kit README or announcement is unclear, say so and ask.
- Long jobs (table builds) run in the background; never block the session waiting on them.
- Your sandbox hides the GPU: `torch.backends.mps.is_available()` is False inside it even
  though the laptop has MPS, so a table build started there runs on CPU (several times
  slower). Run `gpu.build_tables` / `gpu.range_eq` / `go.py` for a NEW variant (it starts
  them) only OUTSIDE the sandbox: request escalated permission for that one command. If
  you can't get it, don't run it: give the human `scripts/codex_day.sh build` to run in
  their own terminal, and carry on. go.py for a preset, day.py, package_bot.py and the kit
  simulator are fine inside the sandbox.

## Where things are

| What | Where |
|---|---|
| One-page day-of steps | `DAYOF.md` (if present), else `PLAYBOOK.md` "Build phase" |
| Rules file to fill in | `variants/ANNOUNCE.json` -> copy to `variants/day_announce.json`; key help in `variants/ANNOUNCE.md`; filled examples in `variants/examples/` |
| Adapter template (the only code you write) | `adapter_template.py` -> copy to `my_adapter.py` |
| Worked adapters | `examples/adapter_mock_solution.py` (string cards, raise-BY, dict actions); `examples/answers/kit2_adapter.py` if present (int cards, street totals, antes) |
| `Obs` definition | `class Obs` in `nolimit/runtime.py` (read only) |
| Rule types and what they cost | `VARIANTS.md` |
| Params per variant | `variants/PARAMS_MAP.json` (go.py reads it); summary below |

## The flow

1. **Rules.** `cp variants/ANNOUNCE.json variants/day_announce.json`, fill it from the kit
   README + announcement, then `.venv/bin/python scripts/go.py variants/day_announce.json --check`.
   Its summary must match the announcement line by line (deck, hole cards, hole cards used,
   board, ante, blinds, hands per level, stack, cap, points 1st..last, time limit, kit).
   `points` = place points 1st..last. If the kit says a raise is a street TOTAL, that is
   `raise-to`. `kit.sim_cmd` must be the exact simulator command that works (`{py}` = our
   python, `{bot}` = the bot file); go.py runs it for every build, and a wrong path fails the build.
2. **Adapter.** `cp adapter_template.py my_adapter.py`; implement `to_obs`, `to_kit_action`
   and the kit's class/method (e.g. `class PokerBot` with `get_move`). Keep `self.core =
   make_core()` in `__init__`, `make_core`, `_tables` and the guarded `gc_settle` block as
   they are. `Obs` conventions (most bugs are here):
   - cards: our id = `rank_index * v.suits + suit_index` with `v = _tables().v`, ranks in
     `v.ranks` order (deuce = 0). Decode the kit's encoding exactly as its README defines it.
   - `street` 0 = preflop, then 1, 2, 3; `seat`/`button` = indexes into the kit's seat order.
   - `stacks` = chips BEHIND; `bets` = chips put in THIS street; `pot` = everything committed
     this hand INCLUDING this street's bets and antes (if the kit's pot leaves out current
     bets, add `sum(bets)`).
   - `in_hand` = dealt in and not folded and not busted.
   - `to_call` in chips; `min_raise_to` / `max_raise_to` as raise-TO street totals;
     `min_raise_to = 0` when raising is not allowed; `max_raise_to` = all-in total
     `bets[me] + stacks[me]` ALWAYS (also when raising is not allowed; never 0 or None).
     Raise-BY kits: add the current top bet in, subtract on the way out.
   - `ante` = the per-player ante amount; antes are NOT in `history`.
   - `history` = `(seat, street, kind, amount_to, all_in)`: blinds `POST`, fold `FOLD`,
     check and call both `CALL`, bet/raise `RAISE`; an all-in is `RAISE` if it goes above
     the street's top bet, else `CALL`. `amount_to` = that seat's street total after the action.
     `all_in=True` only on a seat's LAST action and only if its stack is 0 now.
   - `hand_no` = anything that changes every hand.
   - `to_kit_action`: `CALL` must become "check" when `to_call == 0` and "call" otherwise
     (kits treat a wrong one as illegal); `RAISE` amount is a raise-to total.
3. **Quick test** (heuristic tables, ~10 s): `.venv/bin/python scripts/package_bot.py --variant
   <preset name or variants/day.json> --adapter my_adapter.py --out dist/try.py`, then the kit
   simulator on `dist/try.py`. Fix until 0 exceptions / 0 illegal. If the kit simulator has a
   parity mode (decisions vs our core fed `Obs` directly), it must be 100%.
4. **Build v0 + v1.** If `scripts/go.py` exists: `.venv/bin/python scripts/go.py
   variants/day_announce.json --adapter my_adapter.py --kit-cmd "<kit sim> {bot}"`. It builds
   `day_v0` (heuristic tables, exact rules), and for a preset also `day_v1`; for a new
   variant it starts the table build in the background (`bench/dayof/go_day_tables.log`,
   ends with `GO_TABLES_DONE`) which builds the table tags itself (`day_v1`, and `day_v2`
   with the range net if go.py splits them; its `=== COPY THESE ===` block lists them). Without go.py, use `day.py`:
   - new variant: write `variants/day.json` (keys: name, ranks, suits, n_hole, streets,
     hole_used, category_order, ace_low_straight; see `variants/example_day.json`), then
     `.venv/bin/python scripts/day.py build v0 --heuristic variants/day.json --adapter my_adapter.py --kit-cmd "<kit sim> {bot}"`
   - preset: `.venv/bin/python scripts/day.py build v1 --preset <p> --params <P> --points <1st,..,last> [--ante-bb <ante/bb>] --adapter my_adapter.py --kit-cmd "<kit sim> {bot}"`
   `{bot}` in `--kit-cmd` is replaced by the packaged file. Use `.venv/bin/python` in it.
5. **Submit** (local copy, sha-checked): `.venv/bin/python scripts/day.py submit <tag> --as <file name the kit wants>`,
   then `.venv/bin/python scripts/day.py status` (must end in `matches`). A human uploads
   `dist/SUBMIT/<file name>`.
6. **Rule change mid-build** (new points, antes): edit the JSON, rebuild under a NEW tag
   (`go.py ... --tag day2 --v0 never`, or `day.py build v2 ... --points <new>`). Push/fold is
   re-solved per build; a running table build is not restarted.
   NEW variant: rerunning go.py starts ANOTHER table build. After the first go.py run, rebuild
   with `day.py build` only: v0 fixes `day.py build <new> --heuristic variants/day.json ...`,
   table tags: the `day.py build ...` line from go.py's COPY THESE block, with a new tag and the new
   `--points` / `--ante-bb` (bundle `bundles/day/day_base_rng.nlb` = with range net, `day_base.nlb` = without).

## Params per variant (do not edit params files; pick the file)

| Variant | v1 params | Notes |
|---|---|---|
| NLHE preset | `params/cand3_nlhe.json` (upgraded bot) | fallbacks: `params/ev_t4.json`; rc1 bytes via `day.py build rc1k --from-frozen rc1 --adapter my_adapter.py --kit-cmd ...` |
| Other presets (plo4, plo5, shortdeck, shortdeck_triton, royal, holdem3) | `params/cand_<preset>.json` (see variants/PARAMS_MAP.json) | fallback `params/ev_t3.json` |
| New variant, hold'em-like (2 hole cards, any 5 of 7) | `params/ev_t4.json` | bundle built on the day |
| New variant, anything else | `params/ev_t3.json` | bundle built on the day |
| Heuristic v0 (`--heuristic`) | `params/nlhe_final_legacy.json` (day.py default) | |

`--points` = the kit's place points 1st..last. `--ante-bb` = ante / big blind at the levels
where shoving matters (a fixed 5-chip ante at 10/20 is 0.25). `--pure-python` if the host has
no numpy or the kit shows latency spikes with numpy.

## Where results live

- `dist/day/<tag>.py` packaged bot; `dist/day/<tag>.check.json` its checks (latency, memory, kit result).
- `frozen/<tag>/` frozen copy + `MANIFEST.json` sha.
- `dist/SUBMIT/<name>` + `dist/SUBMIT/STATE.json`: what is submitted, and the history.
- `bench/dayof/go_<tag>.log`, `bench/dayof/go_<tag>_tables.log`: go.py and table-build logs.
- `bench/codex/`: logs of `scripts/codex_day.sh` runs.

## "Should we switch strategy after T1?"

Answer from data, don't improvise. `bench/adapt/README.md` wins if it exists (per-round
rule). Otherwise HANDOFF.md "Live plan for T1-T6" and PLAYBOOK.md "When to fall back".

- **x-fair** = our points per table / fair share (fair = total points / 8). That is the
  number to compare with the tournament result.
- **"A-B % of fair"** (ab_test.py, `bench/final_upgrades/`, `bench/rivals/`) is a PAIRED
  DIFFERENCE between two bots, not x-fair. Never compare a tournament x-fair with it.
- Absolute x-fair calibration: the "A x fair" column of `bench/final_rc1_nlhe.txt` (rc1,
  NLHE: weak fields 1.7-2.1, mixed 1.6-1.9, strong 1.29-1.49, 7 attackers 0.74-0.90;
  `bench/final_rc1_<variant>.txt` for others) and `bench/github_bots/style_xfair_9922.txt`
  (cand_nlhe vs 7 copies of each style: 1.0-2.9).
- Rule: x-fair at or above the strong-field level (~1.3): stay. Far below it (~1.0 or
  less) means a strong or prepped field: switch to rc1k (or ev_t4) only if the data says
  that bot does better there; a bot with errors/timeouts: roll back now. Decide once, before
  T3-T4 (T4-T6 are 71% of the score); never switch back and forth. Quote the rule and numbers.

## When something fails

- Build stops: read the last 40 lines of its output. Most failures are the kit check: fix
  `my_adapter.py`, rebuild with a new tag. Earlier tags stay frozen and submittable.
- Table build slow or crashed: keep v0 live; log `bench/dayof/go_<tag>_tables.log`, rerun
  `bash bench/dayof/go_<tag>_tables.sh` (stages resume). "MPS backend out of memory" with
  large "other allocations" means other processes hold the GPU: tell the human to quit them
  (browsers, other builds) before the resume, or the retry fails the same way.
- Latency over 1 ms in checks: rebuild with `--pure-python`; next, `PrepBot.deadline = 0.0004`
  at the end of the adapter.
- Report in the answer: the tag, the sha (first 12), `errors/illegal`, kit simulator line,
  and the exact command for the human to run next.

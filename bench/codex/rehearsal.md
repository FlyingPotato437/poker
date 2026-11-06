# Codex rehearsal on kit2 (Nov 6, 04:20-04:55)

**Setup.** Codex CLI 0.166.0 (ChatGPT login, default model) ran with `codex exec --sandbox
workspace-write`, through `scripts/codex_day.sh`. It worked in throwaway copies of this branch
plus the draft `go.py` / `day.py` / `variants/ANNOUNCE*` / `DAYOF.md` (scratchpad
`codex_rehearsal/repo`, `repoB`, `repoC`). The kit2 starter kit was presented as `kit/`:
`README.md` plus the simulator compiled to `simulate.pyc`, so no source was visible.
`examples/answers/`, `examples/kit2/`, the kit2 example JSONs and the old kit2 logs were
removed, and there was no git history. Codex got only `AGENTS.md` and the prompts from
`CODEX_PROMPTS.md`.

The machine had a load average of 430-490 on 15 cores (other agents' jobs). So all ms latency
figures are noise, and the step times are pessimistic.

## Final result: run C, briefing as committed

One command: `scripts/codex_day.sh --kit kit auto`. There was no human input.

| Step | Time | Result |
|---|---|---|
| 1. Rules -> `variants/day_announce.json`, `go.py --check` | 65 s | pass: NEW variant, 3 hole / exactly 2, 10 levels every 15 hands, ante 5, stack 1500, points 10,6,4,3,2,1,0,0, raise-to, `PokerBot.get_move`, sim_cmd `{py} kit/simulate.pyc {bot} --games 20` |
| 2. Adapter `my_adapter.py` + kit sim + parity | 182 s | pass: 0 exceptions, 0 illegal, parity 100% |
| 3. `go.py` on the host (driver, not Codex) | 62 s | pass: `day_v0 READY`, errors/illegal 0 (numpy and no numpy), kit 0/0; table chain started in the background |
| 4. Submit (Codex) | 37 s | pass: `day_v0` -> `dist/SUBMIT/bot.py`, status `matches` |
| **Total to a submitted v0** | **351 s (5.9 min)** | REHEARSAL.md target: v0 by T+12 |

## Earlier runs (what went wrong, and the fix)

**Run A: first briefing, one prompt at a time.**

| Step | Time | Result |
|---|---|---|
| 0 preflight | 52 s | pass, but torch printed `MPS False` inside the sandbox (True on the host) |
| 1 rules | 62 s | pass |
| 2 adapter | 188 s | pass (parity 1690/1690). It fixed its own first bug, antes left in history. It left `max_raise_to = 0` when the kit gives `max_raise=None`. |
| 3 go.py run by Codex | 93 s | `day_v0` READY, but the table build it started ran on **CPU** (sandbox hides MPS) |
| 4 submit | 24 s | pass |
| 6 rule change (new points while tables build) | 59 s | pass: no rebuild of the heuristic v0 (no push/fold there), "don't submit the old-points v1", exact `day.py build day2_v1 ... --points 12,8,5,...` printed for later |
| 9 "switch after T1?" (1.05x fair) | 33 s | **wrong**: it compared our x-fair with cand_nlhe's paired A-B % (+11.8%) and said "stay" |
| 9 again, fixed briefing | 40 s | right metric: rc1 strong-field x-fair 1.489 (`bench/final_rc1_nlhe.txt` l.11). It also caught that the live tag was not the bot the result was quoted for. |
| 7 rollback drill ("v0b folds every hand") | 42 s | pass: `day.py rollback` was its first command, then `status` showed `matches`. Its rebuild suggestion re-ran go.py, which would start a second table build. |
| 5 tables | 22 s | correctly reported the failed table build (MPS OOM) and the resume command |

**Run B: briefing v2, `auto`.** 499 s, and it succeeded unattended. In step 1 it wrote
`kit/simulate.py` into `sim_cmd`. In step 2 it ran the `.pyc` itself but didn't fix the JSON,
so the host build failed its kit check. The driver's fix step (prompt 3b, 78 s) corrected
`sim_cmd`, and the rebuild passed (63 s).

**Briefing fixes, all in the committed files:**
- `max_raise_to` = `bets[me] + stacks[me]` always (AGENTS.md). Runs B and C did this.
- Sandbox hides the GPU: `go.py` for a new variant runs on the host (`codex_day.sh` step 3 /
  `build`; interactive Codex must request escalation). Run C's tables started on the host.
- `sim_cmd` must be the exact command that worked: prompt 1 `ls`-checks it, and prompt 2
  writes back what it ran. Run C needed no fix step.
- x-fair vs paired A-B definitions, and where the absolute calibration lives (AGENTS.md "switch").
- New variant: after the first go.py run, rebuild only with `day.py build` (no second table build).
- Rule change while tables are still building: case (c) in prompt 6. Prompt 4 never picks a
  tag built with outdated points.
- MPS out-of-memory with large "other allocations": quit other GPU users before resuming.

## Not verified

- **The table path (v1/v2, prompt 5's A/B gate) never completed.** `build_tables` hit "MPS
  backend out of memory" twice, with 27-29 GB held by other agents' builds on this machine.
  Codex only exercised the failure branch.
- **Interactive mode** (`codex_day.sh --kit DIR`, i.e. `codex --sandbox workspace-write
  --ask-for-approval on-request "<prompt 1>"`) needs a TTY. Its flags were checked against
  `codex --help` only.

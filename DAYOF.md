# Day of: one page, copy-paste in order

Everything runs on the laptop, offline, from the repo root. `<adapter>` = your filled-in
copy of `adapter_template.py`. Details: `PLAYBOOK.md` (who does what), `VARIANTS.md` (rule
types), `variants/ANNOUNCE.md` (every JSON key).

Codex: see AGENTS.md and CODEX_PROMPTS.md.

## T+0: write the rules down once

```bash
cp variants/ANNOUNCE.json variants/day_announce.json
```
Fill in `variants/day_announce.json` from the announcement: variant (a preset name, or the
mechanics), betting, players, stack, blinds, hands per level, antes, hand cap, **points**,
time limit, special rules, kit details (raise-to/by, card format, class/method, file name,
simulator command). Examples: `variants/examples/*.json`.

```bash
.venv/bin/python scripts/go.py variants/day_announce.json --check
```
It prints the plain-English summary, the warnings and the plan for anything the bot can't
model. Read it against the announcement. Fix the JSON until it matches.

## T+2: new variant? start the tables now, before the adapter exists

```bash
.venv/bin/python scripts/go.py variants/day_announce.json --tables-only
```
(Preset variants skip this: their bundle is on disk.) The table build runs in the
background (`bench/dayof/go_day_tables.log`) while Srikanth writes the adapter.

## T+5 to T+10: the one command, as soon as the adapter passes the kit simulator by hand

```bash
.venv/bin/python scripts/go.py variants/day_announce.json --adapter <adapter> --kit-cmd "<kit simulator> {bot}"
```
(`--kit-cmd` can live in the JSON as `kit.sim_cmd`; `{py}` there = our python.)

It validates the JSON and prints a summary, then picks the preset if the hand evaluation is
identical, or writes `variants/day.json`. It builds `day_v0` (heuristic tables, exact rules,
kit-checked, frozen) in 15–40 s idle (2 min measured under load). Then:
- **Preset:** it builds `day_v1` from the preset bundle, with the points/ante re-solve
  and the params from `variants/PARAMS_MAP.json`. Measured under load: 3.5–5.5 min; idle
  about 1 min.
- **New variant:** it starts the table chain, or picks it up if `--tables-only` already
  started it. `day_v1` is the bundle without the range net; it is frozen as soon as
  `build_tables` ends. `day_v2` adds the range net. Rerun the same command later and it
  builds whichever bundle is finished.

It ends with the exact submit, rollback and status lines and an A/B gate command with the
kit's rules. Log: `bench/dayof/go_day.log`.

## Submit v0 at once (before the first practice round)

```bash
.venv/bin/python scripts/day.py submit day_v0 --as <file name>     # upload dist/SUBMIT/<file name>
```

## Then each stronger bot as its READY / "built and froze" line appears

```bash
.venv/bin/python scripts/day.py submit day_v1                 # preset: minutes; new variant: tables done
tail -f bench/dayof/go_day_tables.log                         # new variant: v1, then v2, then GO_TABLES_DONE
.venv/bin/python scripts/day.py submit day_v2                 # new variant: with the range net
```
If the chain stopped, go.py printed the `day.py build day_v1/day_v2 ...` lines to run by
hand. Run the A/B gate first if there's time (go.py prints it).

## Rule changes mid-build (new points, antes)

Points/antes only need the push/fold re-solve (15 s idle). Edit the JSON and rerun with a
new tag; the preset/heuristic builds take minutes, a running table build is not restarted:
```bash
.venv/bin/python scripts/go.py variants/day_announce.json --adapter <adapter> --tag day2 --v0 never
```
For a new variant whose tables are done: the `day.py build day_v2 ...` line go.py printed,
with tag `day2_v2` and the new `--points` / `--ante-bb`.

## Always

```bash
.venv/bin/python scripts/day.py status        # what is live, sha-checked
.venv/bin/python scripts/day.py rollback      # one step back, 0.2 s
```

## What to do per rule type

| Rule | go.py does | You do |
|---|---|---|
| Preset variant (nlhe, plo4, plo5, shortdeck(_triton), royal, holdem3) | v0 + v1 from the preset bundle | Submit v1 |
| New mechanics (ranks, suits, hole cards, board layout, ranking, hole_used) | v0 now; tables in the background, then v1 (no range net), then v2 | Submit v0, v1, v2 in turn |
| Points, antes, BB ante | Exact push/fold re-solve | Nothing |
| Blinds, hands per level, stack, cap, seats 2–10 | Nothing needed (A/B command uses them) | Nothing |
| Time limit ≠ 1 ms | Adds `PrepBot.deadline = 0.6 × limit` to a copy of the adapter | Check p99.9 in the build output |
| No numpy on host | `--pure-python` everywhere | Nothing |
| Pot-limit / fixed-limit / raise cap | Warning + plan | Clamp `max_raise_to` / `min_raise_to` in `to_obs` |
| Hi-lo, lowball, badugi, wild cards | Warning + plan; v0 is a legal placeholder | New evaluator (VARIANTS.md section 3) |
| Discards, stud | Warning + plan | Adapter work (VARIANTS.md section 3) |
| 7-2, straddle, bomb pot, bounty, run it twice | Warning + plan | Adapter forced bets; otherwise ignore |
| Raise-by, card format, class name | Reminder, class/method check | Adapter |

## Fallbacks

- A build fails: go.py stops at that step and says which; the earlier tags stay frozen and
  submittable. Most failures are the kit check: fix the adapter, rerun with a new `--tag`.
- v1 misbehaves in a practice round: `day.py rollback` first, then investigate.
- A `cand_*` params file (from `variants/PARAMS_MAP.json`) misbehaves: rebuild with the rc1
  params: `day.py build v1b --preset <preset> --params params/ev_t3.json` (`ev_t4.json` for
  nlhe) `--points ... --ante-bb ... --adapter ... --kit-cmd ...`. Or use the rc1 bytes:
  `day.py build rc1k --from-frozen rc1 --adapter ...`.
- Slow or loaded laptop: `--tables quick`, which does about a third of fast's Monte Carlo
  work (its timing is an estimate, not measured). The `laptop` profile is the slow,
  most accurate one.
- Table build too slow / crashed: v0 stays live; rerun `bash bench/dayof/go_day_tables.sh` (stages
  are checkpointed in `bundles/day/work_day`; add `--reuse` by hand to skip finished ones).
- Unknown rule: write it in `special_rules.other`, submit v0, decide by hand.

## Measured (Nov 6, this M5 Pro, CPU, 3 threads, with other jobs loading the machine at 350–1000)

Times are from the go.py start. On this machine, every step ran 5–50× slower than on an
idle laptop: the push/fold solve took 3–12 min instead of 12 s. MPS ran out of memory
twice, because other jobs held 27 of 30 GB of GPU memory, so these runs used `--device
cpu`.

| Case | v0 (heuristic) | v1 | v2 (range net) |
|---|---|---|---|
| NLHE, points 12..0, ante 5 (preset, cand_nlhe) | 0:39 | 5:26 | – |
| PLO4 (preset) | 0:18 | 3:46 | – |
| kit2 Tahoe, 3 hole / exactly 2 (new, fast profile) | 1:49 (0:14 in an earlier run) | 30:48 | 39:00 |
| 7+ deck, flush > full house (new, fast profile) | 0:16 | build_tables 12:56 (+~2 min for the v1 build) | not rerun with the final range settings |

The `laptop` profile was not viable here. Its tahoe preflop pass alone ran for more than 10
min on MPS before running out of memory. That is why `fast` (fewer Monte Carlo samples, same
nets) is the default, and why v1 ships without the range net.

Quick-build table bot vs the heuristic v0, paired, 400 SNGs, zoo field:
- 7+ variant, `fast` tables without the range net: with the rules engine
  (`nlhe_final_legacy`, what go.py's v1 now uses) **+32.2% of fair ± 5.8**; with `ev_t4`,
  +24.3% ± 5.3 (`bench/dayof/go_ab_custom_v1*_vs_v0.txt`).
- kit2 under kit rules (stack 1500, ante 5, 15 hands per level, points 10..0), 800 SNGs,
  fields zoo / passive / aggressive (`bench/dayof/go_ab_kit2_800*.txt`):
  - v1 with `ev_t3`: **−9.3% ± 2.4**. The EV engine without a range net is worse than v0.
  - v1 with the rules engine (`nlhe_final_legacy`): **+1.8% ± 2.4** (+6.6 / −9.1 / +7.9).
    go.py now uses this (`PARAMS_MAP new_variant_no_range_net`).
  - v2 (range net) with `ev_t3`: **−0.6% ± 2.5** (+5.8 / −15.0 / +7.4). The 4v4 head to
    head is 1.14× fair.

  So the fast tables for a 3-hole/Omaha-style variant are no better than v0 within the noise,
  and they lose to passive fields (the same weak spot the Oct 31 rehearsal found). Submit
  v1/v2 there only if the go.py A/B gate under the kit's rules is positive. Otherwise keep
  v0 and tune `params/` on the day bundle if time allows (PLAYBOOK).

## T1–T6 (scored rounds, 20 min apart)

Follow the live plan in `bench/adapt/README.md` (per-round reading of score ÷ fair, when
to switch, decide once before T3–T4) and PLAYBOOK.md "T1–T6". Never submit an untested
package late: every submit goes through `day.py build` (kit check + freeze).

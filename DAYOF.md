# Day of: one page, copy-paste in order

Everything runs on the laptop, offline, from the repo root. `<adapter>` = your filled-in
copy of `adapter_template.py`. Details: `PLAYBOOK.md` (who does what), `VARIANTS.md` (rule
types), `variants/ANNOUNCE.md` (every JSON key).

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

## T+2: start go.py (Srikanth writes the adapter meanwhile; go.py waits for nothing else)

New variant? Start the tables before the adapter is done, so the GPU isn't idle:
```bash
.venv/bin/python scripts/go.py variants/day_announce.json --check      # shows "NEW variant" and the ETA
```
then, as soon as the adapter passes the kit simulator by hand:
```bash
.venv/bin/python scripts/go.py variants/day_announce.json --adapter <adapter> --kit-cmd "<kit simulator> {bot}"
```
(`--kit-cmd` can live in the JSON as `kit.sim_cmd`; `{py}` there = our python.)

What it does: (1) validate + summary; (2) preset if the hand evaluation is identical, else
writes `variants/day.json`; (3) new variant: starts the table build in the background
(`bench/dayof/go_day_tables.log`), which builds `day_v1` by itself when done; (4) builds
`day_v0` (heuristic tables, exact rules, kit-checked, frozen); (5) preset: builds `day_v1`
from the preset bundle with the points/ante re-solve and the params from
`variants/PARAMS_MAP.json`; (6) prints the commands below. Log: `bench/dayof/go_day.log`.

## T+5: submit v0 (before the first practice round)

```bash
.venv/bin/python scripts/day.py submit day_v0 --as <file name>     # upload dist/SUBMIT/<file name>
```

## T+6 to T+10: preset -> submit v1 as soon as go.py prints "day_v1 READY"

```bash
.venv/bin/python scripts/day.py submit day_v1
```

## New variant: v1 when the background build says GO_TABLES_DONE

```bash
tail -f bench/dayof/go_day_tables.log                      # "day_v1 built" then GO_TABLES_DONE
.venv/bin/python scripts/day.py submit day_v1
```
If the chain stopped after the range net, go.py printed the `day.py build day_v1 ...` line
to run by hand. A/B gate first if there's time (go.py prints it with the kit's rules).

## Rule changes mid-build (new points, antes)

Points/antes only need the push/fold re-solve (15 s idle). Edit the JSON and rerun with a
new tag; the preset/heuristic builds take minutes, a running table build is not restarted:
```bash
.venv/bin/python scripts/go.py variants/day_announce.json --adapter <adapter> --tag day2 --v0 never
```
For a new variant whose tables are done: `day.py build day2_v1 --bundle bundles/day/day_base_rng.nlb
--params <P> --points <new> --ante-bb <a> --adapter <adapter> --kit-cmd "..."`.

## Always

```bash
.venv/bin/python scripts/day.py status        # what is live, sha-checked
.venv/bin/python scripts/day.py rollback      # one step back, 0.2 s
```

## What to do per rule type

| Rule | go.py does | You do |
|---|---|---|
| Preset variant (nlhe, plo4, plo5, shortdeck(_triton), royal, holdem3) | v0 + v1 from the preset bundle | Submit v1 |
| New mechanics (ranks, suits, hole cards, board layout, ranking, hole_used) | v0 now, tables + v1 in the background | Submit v0, then v1 |
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
- Upgraded bot (NLHE `cand_nlhe`) misbehaves: `day.py build v1b --preset nlhe --params params/ev_t4.json --points ... --adapter ...`, or rc1 bytes: `day.py build rc1k --from-frozen rc1 --adapter ...`.
- Table build too slow / crashed: v0 stays live; rerun `bash bench/dayof/go_day_tables.sh` (stages
  are checkpointed in `bundles/day/work_day`; add `--reuse` by hand to skip finished ones).
- Unknown rule: write it in `special_rules.other`, submit v0, decide by hand.

## T1–T6 (scored rounds, 20 min apart)

Follow the live plan in `bench/adapt/README.md` (per-round reading of score ÷ fair, when
to switch, decide once before T3–T4) and PLAYBOOK.md "T1–T6". Never submit an untested
package late: every submit goes through `day.py build` (kit check + freeze).

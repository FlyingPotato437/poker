# Timed rehearsal (60 minutes, both of us, Wi-Fi off)

This is a dress rehearsal of the build phase against a kit neither of us has seen:
`examples/kit2/`. It covers:

- an unfamiliar variant (3 hole cards, exactly 2 used);
- antes;
- an unfamiliar points table;
- a new state format;
- one mid-build rule change;
- one broken submission that must be rolled back.

**Ground rules:**

- Before T+0, nobody opens `examples/kit2/simulate.py` or `examples/answers/`.
- At T+0, read `examples/kit2/README.md` only. That's the "starter kit".
- No Claude and no internet: Wi-Fi off from start to finish. That's how the day runs.
- Srikanth owns the adapter and submissions. Revanth owns the tables and the A/B gate.
  Either one must be able to run any command below.
- "Submit" means `python scripts/day.py submit <tag>`. The file to upload lands in
  `dist/SUBMIT/`.
- Log the real time of every checkpoint in the sheet at the bottom.

## Before T+0 (not timed)

```bash
rm -rf dist/SUBMIT dist/day bundles/day      # clean day-of state (frozen/rc1 stays)
.venv/bin/python -m pytest -q                # everything green, Wi-Fi already off
```

## Script

| Target | Who | Step |
|---|---|---|
| T+0 | both | Start the timer. Read the kit README. Write down variant, points, antes, schedule, interface. |
| T+3 | Revanth | `variants/day.json` from the rules. Check it with `scripts/variant_stats.py --variant variants/day.json`. |
| T+5 | Revanth | Start the table build (laptop, runs in the background): `gpu.build_tables --variant variants/day.json --laptop --payouts 10,6,4,3,2,1,0,0 --out bundles/day.nlb`, then `gpu.range_eq --bundle bundles/day.nlb --laptop --out bundles/day_rng.nlb`. Note the minutes each takes: that is our day-of build time for an Omaha-size variant, so far never measured. |
| T+3 to T+12 | Srikanth | `cp adapter_template.py my_adapter.py`. Fill in `to_obs`, `to_kit_action` and the kit's class (`PokerBot.get_move`). |
| **T+12** | Srikanth | **v0 submitted**: `scripts/day.py build v0 --heuristic variants/day.json --adapter my_adapter.py --kit-cmd "python examples/kit2/simulate.py {bot} --games 10"`, then `day.py submit v0`. |
| T+20 | Srikanth | Adapter parity: `python examples/kit2/simulate.py dist/day/v0.py --games 20 --parity` must print 100% identical moves. Fix the adapter until it does, then rebuild and submit as v0b. |
| **T+30** | (inject) | The organizer announces new points: **12, 8, 5, 3, 2, 1, 0, 0**. Every later build uses them. If the tables are still building, they don't restart: push/fold is re-solved per build by `day.py --points`. |
| T+30 to T+45 | Revanth | When `day_rng.nlb` lands: `day.py build v1 --bundle bundles/day_rng.nlb --params params/ev_t3.json --points 12,8,5,3,2,1,0,0 --ante-bb 0.25 --adapter my_adapter.py --kit-cmd "..."`. |
| T+45 | Revanth | A/B gate v1 vs v0, in-process, 2000 paired SNGs (~20 s), before Srikanth submits v1: `ab_test.py --bundle bundles/day/v1.nlb --keep-bundle --a prep:params/ev_t3.json --b heur:params/nlhe_final_legacy.json --sngs 2000 --points 12,8,5,3,2,1,0,0 --hands-per-level 15 --schedule 10/20,15/30,... --stack 1500 --ante 5 --fields zoo,passive,aggressive`. |
| **T+48** | (inject) | "v1 is folding every hand in the practice round." Run `day.py rollback` within 60 s. Then look for the cause; the drill is the rollback, not the bug. |
| T+55 | Srikanth | Final submission. `day.py status` must show the intended tag, and the file in `dist/SUBMIT/` must match its frozen sha. |
| T+60 | both | Stop. Fill in the sheet. |

`--ante-bb`: the kit's ante is 5 chips at the 10/20 level, i.e. 0.25 bb. Push/fold charts
are solved for one ante-to-bb ratio, so use the value for the levels where shoving matters
(with a fixed 5-chip ante that ratio shrinks every level). Picking it on the day is part of
the drill.

## Pass criteria

- v0 is submitted by T+12, and the kit simulator showed no exceptions, illegal moves or
  timeouts before every submit.
- Adapter parity is 100% before v1 is submitted.
- The points change is live in a submitted bot within 5 minutes.
- The rollback takes under 60 s, and `day.py status` shows it.
- At T+60 the submitted file is the one we meant, with sha checked.
- We recorded the real laptop build and range-net times for this variant.

## Sheet

| Step | Target | Actual | Problems |
|---|---|---|---|
| Kit read, rules written down | T+3 | | |
| day.json + variant_stats | T+5 | | |
| Table build started | T+5 | | |
| v0 submitted | T+12 | | |
| Parity 100% | T+20 | | |
| New points live | T+35 | | |
| build_tables done (min) | | | |
| range_eq done (min) | | | |
| v1 gate result | T+45 | | |
| Rollback done (s) | T+49 | | |
| Final submitted + status ok | T+55 | | |

Dry run by Claude, Oct 31, with the answer key: the whole path worked. Tables took 6.0 min,
the range net 8.0 min, each day.py build about 10 s, and parity was 100%. The v1 vs v0 gate
under kit rules gave +4.6% ±4.4 at 300 SNGs, and v1 was −10.8% on the passive field. That
passive field is the known weak spot; watch it on the day.

Answer key, for after the drill: `examples/answers/kit2_adapter.py` (100% parity, checked
Oct 31).

# rc2 decision rules

Written Oct 31, ~4:55 PM PT, before any gate result. rc1 stays the submission unless a
candidate passes every rule below.

## Data roles

| Role | What | Use |
|---|---|---|
| Training | tune.py fields W and R (zoo styles incl. FRESH and HELD_OUT) | fitting params |
| Validation | final_check fields weak, weak+crashed, strong, mixed at seed 9101; switch-study tables | choosing between candidates, fitting and checking the switch rule. Used, so development data from now on |
| Test | zoo OOS (chen, potodds, bluffy, brittle), plus a fresh seed on the gate fields | once, after params, switch rule and points preset are all frozen |

If the test run leads to any change, the test set becomes development data and no clean
test is left. In that case rc1 is kept.

## Gate (each candidate vs frozen rc1)

Each cell is 3000 paired SNGs (same seat, deck and opponents). Cells are the 4 fields at
2 blind speeds, so 8 per candidate. attack-on-B is not scored: its attackers were tuned
against rc1 only, so that cell favours any candidate.

A candidate passes only if all three hold:

1. **No significant loss in any cell.** In every cell, the upper bound of the 95% CI on A − B
   is above 0.
2. **A meaningful gain.** The equal-weight mean over the 8 cells is at least +1.0% of fair,
   and its 95% lower bound is above 0.
3. **Timing no worse.** In every cell, A's penalties (over-limit decisions plus errors, per
   1k decisions) are no more than 0.2 above B's. A's p99.9 decision time is within 0.1 ms
   of B's.

Results are reported per field and per blind speed. No guessed field mix decides anything.
If both NLHE candidates pass, the one with the higher mean is taken, and both are reported.
PLO4 is judged on its own under the same rules.

Timing-sensitive runs (final_check) use 8 of the box's 16 cores. Tuning and the switch study
run without the time deadline, so CPU load cannot change their results.

## Per-table switch

A rule is adopted only if both of these hold:

- Its 5-fold held-out gain has a 95% lower bound above 0 against staying on the base params.
- It also has a 95% lower bound above 0 against always switching to the best single arm.

The study tables never seat gate or test opponents. The packaged switching bot must then
pass the gate rules against the chosen non-switching bot. That run is end to end, so it
includes SNGs the bot leaves before the switch point.

## Points table

The ICM and push/fold tables are rebuilt on the day for the announced points table. That
makes them an exact match, so no nearest preset is used. A rebuild takes 12 s on the laptop
(`python -m gpu.pushfold --bundle ... --payouts ... --workers 4`).

Params presets are tuned for a few points tables (linear, top-heavy). The day-of rule is to
take the preset whose normalized points shape is nearest to the announced one. That rule is
only adopted if it beats rc1's params on points tables no preset was tuned for, with both
bots scored under that table's rebuilt tables. Otherwise rc1's params are used with the
exact tables.

## Test (one shot)

The test is one final_check, alone on the box with 8 workers. It covers the OOS field plus
the gate fields on a seed never used before.

rc2 ships only if both hold:

- The mean over cells has a 95% lower bound above −0.5% of fair.
- No cell shows a significant loss.

Otherwise rc1 is kept.

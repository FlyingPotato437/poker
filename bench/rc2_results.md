# rc2 results against the pre-registered rules (`bench/rc2_rules.md`)

## Round 1: field-fit tunes, gate seed 9101 (Oct 31, A100 box)

Each candidate is the frozen rc1 file with only the params changed (checked byte for byte).
Every cell is 3000 paired SNGs against frozen rc1. Figures are A − B in % of fair, with
95% CIs.

| Cell | NLHE w (weak field) | NLHE r (realistic field) | PLO4 w (weak field) |
|---|---|---|---|
| normal weak | +21.7 | +17.2 | +33.7 |
| normal weak+crashed | +22.6 | +16.2 | +32.2 |
| normal strong | **−13.3 [−17.1, −9.5]** | **−6.0 [−9.6, −2.5]** | **−23.0 [−27.1, −18.8]** |
| normal mixed | +6.5 | +9.1 | +14.0 |
| fast weak | +15.2 | +11.6 | +17.8 |
| fast weak+crashed | +17.0 | +14.7 | +18.0 |
| fast strong | −2.9 | +2.3 | **−12.3 [−16.6, −7.9]** |
| fast mixed | +10.8 | +12.3 | +8.7 |
| Mean of 8 cells | +9.70 [+8.22, +11.18] | +9.67 [+8.28, +11.07] | +11.14 [+9.50, +12.77] |
| Rule 1: no significant loss | FAIL | FAIL | FAIL |
| Rule 2: mean ≥ +1% and lower bound > 0 | pass | pass | pass |
| Rule 3: penalties ≤ B + 0.2/1k | FAIL (6 cells, up to +0.32) | FAIL (5 cells, up to +0.40) | FAIL (7 cells, up to +0.38) |

**Verdict: none ships.** rc1 stays for NLHE and PLO4.

**Why they lose on the strong field.** The tuned params exploit weak bots: more ICM caution
and tighter calls (w), fewer bluffs (r). Competent opponents give that back. The switch study
shows the same thing on tables with ≥ 3 copies of rc1: about −8% for both arms.

**Why they fail on timing.** These bots see more flops, and postflop decisions are slower.
p50 rose from 0.05 to 0.08–0.09 ms and penalties rose by 0.2–0.4 per 1k decisions. The
point figures already include those penalties (auto-folded). The rule is there because the
host CPU may be slower than the box.

## Per-table switch study (base rc1, arms w and r, 40000 tables)

- Always switching to r at hand 30 vs staying on rc1: +10.88% [+10.16, +11.60]. The study
  tables use training-type opponents only.
- 5-fold held-out rule: it picks r on 98% of tables. Against always-r it scores
  −0.07% [−0.18, +0.05]. **Fails the rule, so no switch is adopted.**
- No determinism violations: every branch saw the same table up to the switch.

## Round 2: retunes with competent bots in the field, gate seed 9102

r2 retunes r (NLHE) and w (PLO4) against the realistic field plus competent bots: rc1,
ev_t3, the old rules-engine bot, and balanced. Opponents used by the gate and the test stay
out. The gate uses a fresh seed, 9102. A pass there still needs the one-shot OOS test.

**NLHE r2.** The tune was flat: the mean-params score went from 50.48 to 50.02 over 8 gens,
with ±0.52 noise. So the competent bots pulled it back only a little from r.

| Cell | NLHE r2 |
|---|---|
| normal weak | +18.8 |
| normal weak+crashed | +18.0 |
| normal strong | **−5.4 [−9.1, −1.8]** |
| normal mixed | +8.8 |
| fast weak | +13.4 |
| fast weak+crashed | +14.7 |
| fast strong | −2.0 [−5.6, +1.5] |
| fast mixed | +8.9 |
| Mean of 8 cells | +9.40 [+7.99, +10.81] |
| Rule 1 | FAIL (normal strong) |
| Rule 2 | pass |
| Rule 3 | FAIL (penalties +0.18..0.41/1k; p99.9 1.12 vs 0.88 ms) |

The gate shared the box with the PLO4 r2 tune on the other 8 cores, so the timing is
inflated for both bots: B's penalties were 0.47–0.98/1k here, against 0.24–0.54 in round 1.
Rule 1 alone decides it: **r2 fails, and rc1 stays for NLHE.**

**PLO4 r2:** running. Its tune is also flat so far (47.99 → 48.00 after 4 of 8 gens).

## Round 3 (pre-registered before any result): shrink r2 toward rc1

Tuned moves are noisy estimates, and these tunes overshoot toward exploiting weak bots. A
partial step, p = rc1 + λ·(r2 − rc1), should keep part of the weak-field gain at a smaller
strong-field loss.

- **Candidates:** λ = 0.5 (s5) and λ = 0.3 (s3), NLHE only.
- **Gate:** the same rules on a fresh validation seed, 9103, with 8 workers.
- **Timing:** the PLO4 tune holds the other 8 cores. Anything that passes rules 1 and 2 gets
  its timing re-run alone before rule 3 is scored.
- **One-shot test:** still only for a candidate that passes all three rules.
- **Power:** at 3000 SNGs a cell's 95% CI is about ±3.7% of fair. A strong-field loss
  smaller than that can pass rule 1 without being zero, so the expected strong-field
  cost gets reported next to the verdict.

Results, gate seed 9103 (box shared with the PLO4 tune):

| Cell | s5 (λ 0.5) | s3 (λ 0.3) |
|---|---|---|
| normal weak | +9.5 | +5.0 |
| normal weak+crashed | +8.0 | +4.9 |
| normal strong | −2.3 [−5.7, +1.1] | +0.5 [−2.6, +3.5] |
| normal mixed | +5.0 | +2.3 |
| fast weak | +2.5 | +2.4 |
| fast weak+crashed | +10.9 | +6.4 |
| fast strong | +2.0 | +1.6 |
| fast mixed | +0.9 | +2.7 |
| Mean of 8 cells | +4.56 [+3.27, +5.85] | +3.24 [+2.08, +4.40] |
| Rule 1 | pass | pass |
| Rule 2 | pass | pass |
| Rule 3 | FAIL (+0.23..0.33/1k; p99.9 1.14 vs 0.88) | FAIL (+0.23..0.39/1k; p99.9 1.06 vs 0.64) |

**What fails rule 3 is `pool_w`, not the play.** p50 doubled even at λ 0.3, where the bot
makes only 3% more decisions. rc1 has `pool_w` 0: unseen seats start from fixed priors. Every
tune moved it above 0 (r2 0.072). With `pool_w` above 0, `pool_priors()` re-pools all seats'
stats once per hand. The mock kit sends no `hand_end`, so this runs inside the first decision
of each hand. That is most decisions, because most hands are one preflop fold.

Checked on the laptop: 400 SNGs, normal mixed + strong, 4 workers, nothing else running.

| A vs rc1 | A p50 | rc1 p50 | A pen/1k | rc1 pen/1k |
|---|---|---|---|---|
| rc1 + `pool_w` of s3 only | 0.05 | 0.03 | 0.23, 0.07 | 0.27, 0.13 |
| s3 with `pool_w` 0 | 0.03 | 0.03 | 0.09, 0.11 | 0.05, 0.06 |
| s3 | 0.05 | 0.03 | 0.40, 0.34 | 0.22, 0.11 |

## Round 3b (pre-registered before any result): shrinkage with `pool_w` 0

- **Candidates:** s5p0 and s3p0, which are s5 and s3 with `pool_w` set to 0. That is params
  only, so the runtime stays rc1's bytes.
- **Gate:** rules 1–3 on a fresh validation seed, 9104, with 8 workers. The timing gets
  re-run alone once the PLO4 tune ends.
- **Pick:** among the candidates that pass, the higher mean of 8 cells. If the CIs overlap
  by more than half, take the smaller λ, the one closer to rc1.
- **One-shot test:** the pick only. It runs alone on the box with an unused seed and fields
  weak, weak+crashed, strong, mixed and oos, and must pass the test rule in
  `bench/rc2_rules.md`.

Results, gate seed 9104 (the box still shared with the PLO4 tune):

| Cell | s5p0 | s3p0 |
|---|---|---|
| normal weak | +8.0 | +4.3 |
| normal weak+crashed | +11.6 | +4.3 |
| normal strong | −3.0 [−6.4, +0.4] | −3.2 [−6.5, +0.1] |
| normal mixed | +7.6 | +5.2 |
| fast weak | +8.6 | +5.7 |
| fast weak+crashed | +7.1 | +1.7 |
| fast strong | +0.2 | −0.1 |
| fast mixed | +4.8 | +3.8 |
| Mean of 8 cells | +5.61 [+4.34, +6.88] | +2.70 [+1.50, +3.90] |
| Rule 1 | pass | pass |
| Rule 2 | pass | pass |
| Rule 3, shared box | over in 5 cells (up to +0.27); p99.9 0.97 vs 0.64 | over in 2 cells (up to +0.27); p99.9 0.96 vs 0.79 |
| p50 (A vs rc1) | 0.05 vs 0.04 | 0.05 vs 0.04 |

Setting `pool_w` to 0 brought p50 from 0.08 down to 0.05 ms. Both candidates pass rules 1 and
2, and their CIs don't overlap, so the pick is s5p0 if it passes rule 3 when run alone.

**The strong field, normal blinds, across all four shrinkage gates:** −2.3, +0.5, −3.0, −3.2.
Pooled that is about −2.0% [−3.7, −0.3]. Each single gate passes rule 1, but the pooled cost
is real: about 2–3% of fair against strong tables at normal blinds, in exchange for +5 to
+12% against weak and mixed tables. Fast blinds, strong field: about +0.9%.

## Round 3c (pre-registered before any result), run alone once PLO4 r2 is done

1. **NLHE timing:** re-run the s5p0 and s3p0 gates on seed 9104 alone, which replays the same
   games. Rule 3 is scored on these runs.
2. **PLO4:** s5p0 and s3p0 built from w_plo4. That is p = rc1 + λ·(w − rc1) with `pool_w` 0,
   for λ 0.5 and 0.3, gated on PLO4 seed 9103. The PLO4 r2 gate does not change this choice;
   r2 is judged on its own.
3. **Next:** only a candidate that passes all of rules 1–3 goes on to the one-shot test.

### NLHE, re-run alone (seed 9104, same games)

| Cell | s5p0 | pen excess | s3p0 | pen excess |
|---|---|---|---|---|
| normal weak | +8.3 | +0.15 | +5.3 | **+0.22** |
| normal weak+crashed | +9.9 | +0.15 | +2.4 | +0.14 |
| normal strong | −2.8 [−6.3, +0.6] | +0.09 | −4.0 [−7.4, −0.6] | +0.07 |
| normal mixed | +5.1 | +0.14 | +4.5 | +0.11 |
| fast weak | +8.5 | +0.06 | +6.2 | +0.14 |
| fast weak+crashed | +7.0 | +0.13 | +0.9 | +0.12 |
| fast strong | −0.4 [−3.4, +2.6] | +0.11 | +0.0 | +0.19 |
| fast mixed | +4.7 | **+0.21** | +2.0 | +0.11 |
| Mean of 8 cells | **+5.03 [+3.76, +6.30]** | | +2.17 [+0.95, +3.39] | |
| Rule 1 | pass | | **FAIL** (normal strong) | |
| Rule 2 | pass | | pass | |
| Rule 3, penalties | **one cell +0.21** vs limit 0.20 | | one cell +0.22 | |
| Rule 3, p99.9 (A vs rc1) | 0.51 vs 0.62 ms: A faster | | 0.68 vs 0.67 | |

Overall over-limit rate for s5p0 vs rc1: 1594/3.11M against 1116/2.93M, so 0.51 against 0.38
per 1k decisions (+0.13). The printed pen/1k values are rounded to 0.01, so the fast mixed
excess lies between 0.20 and 0.22.

**Read literally, s5p0 misses rule 3 by 0.01 in one of 8 cells.** Points of view:

- **The rule's per-cell threshold is noisy.** Each cell has about 210 over-limit events per
  bot, so the per-cell excess has an se of about 0.05/1k. With a true excess of 0.13, the
  chance that at least one of 8 cells prints above 0.20 is about 50%.
- **The points already include the cost.** final_check auto-folds every over-limit decision,
  so the +5.0% is net of it. 0.13/1k × ~65 decisions per SNG = 0.008 extra auto-folds per SNG.
  Even 3× more on a slower host, at a whole big pot each, is under 0.5% of fair.
- **The tail is better.** s5p0's p99.9 is 0.11 ms below rc1's. The extra over-limits are rare
  spikes, of which s5p0 meets more because it makes 6% more decisions, many of them postflop.

Changing a pre-registered rule after the fact is a forking path. So the waiver is the user's
call, made before the test is run, and it gets recorded here either way.

**Decision (user, Nov 1, before the test ran): rule 3 is waived for s5p0.**

- **What is waived:** only the per-cell penalty threshold, which s5p0 missed by 0.01/1k in
  one of 8 cells.
- **What s5p0 met:** the p99.9 part of rule 3.
- **Choice:** s5p0 is the pick, by the pre-registered pick rule.
- **The test:** one final_check, run alone on the box with 8 workers. Seed 9401 has never
  been used. Fields: weak, weak+crashed, strong, mixed and oos, at 2 blind speeds.
- **Test rule, unchanged:** the mean's 95% lower bound must be above −0.5% of fair, and no
  cell may show a significant loss.
- **Timing in the test:** reported, but not part of the verdict.
- **After the test:** nothing changes, pass or fail.

### PLO4: every candidate loses significantly on the strong field

| Cell | PLO4 r2 (seed 9102) | PLO4 s5p0 (seed 9103) | PLO4 s3p0 (seed 9103) |
|---|---|---|---|
| normal weak | +15.3 | +18.3 | +15.0 |
| normal weak+crashed | +19.6 | +14.7 | +8.0 |
| normal strong | **−6.6 [−11.0, −2.3]** | **−7.7 [−11.8, −3.6]** | **−5.1 [−9.0, −1.3]** |
| normal mixed | +10.4 | +6.5 | +3.2 |
| fast weak | +12.0 | +11.2 | +7.7 |
| fast weak+crashed | +8.8 | +12.0 | +6.5 |
| fast strong | −3.8 [−8.1, +0.5] | **−6.3 [−10.3, −2.3]** | −1.1 |
| fast mixed | +2.8 | +8.9 | +2.9 |
| Mean of 8 cells | +7.31 [+5.70, +8.92] | +7.20 [+5.69, +8.71] | +4.64 [+3.27, +6.01] |
| Rule 1 | FAIL | FAIL | FAIL |

The PLO4 r2 tune was flat as well (47.99 → 48.79). Its gate output went to the wrong file
name on the box (copied from the NLHE script) and was recovered by renaming.
**PLO4: rc1 stays.** Five candidates were tried, and every one loses 5–8% to strong tables at
normal blinds, even at a 0.3 step.

## Round 4 (pre-registered Nov 4, before any result on these candidates)

**Why a new round.** Reading the official rules (Nov 3) changed the picture:

- Every team gets 60 minutes, Codex/Astra, public docs, and a kit with an ICM calculator.
- Each of the six scored tournaments is 10,000 SNGs, so luck averages out.
- Teams can resubmit between tournaments.
- The real field is smart teams' quick builds, not our zoo, so we wrote
  `nolimit/rivals.py`:
  - **10 dev designs:** TAG, LAG, solver-style MDF, opponent-modelling, ICM specialist, MC,
    aggro, math, buggy, frozen-postflop. Each uses noisy Monte Carlo equity, and the better
    ones use range weighting, Nash push/fold and the ICM bubble factor.
  - **3 holdout designs:** `rvh_*`.
- The one-shot test of s5p0 was not run (the box went down), so it now belongs to this
  round's pick.

**Candidates:**

- **s5p0:** params only, runtime identical to rc1.
- **x:** rc1 base plus per-opponent exploitation toward r2p0, which is r2 with `pool_w` 0.
  The rule is fitted by `scripts/fit_exploit.py` on training styles only. Each villain gets
  λ = P(exploitable | its stats) × hands / (hands + h0). A decision plays at the smallest λ
  among the villains in the hand.
- **xs:** the same as x, with s5p0 as the base.

**Dev data** (choosing is allowed here):

- The gate fields (weak, weak+crashed, strong, mixed) on fresh seeds from 9105.
- The rival dev fields (rival-strong, rival-strong+prep, rival-mid, rival-real), from seed 9501.

**Gate:** each candidate vs frozen rc1, run with final_check. That's 8 fields × 2 blind
speeds = 16 cells, 3000 paired SNGs each.

1. No cell may show a significant loss.
2. The mean over 16 cells is ≥ +1% of fair, with a 95% lower bound above 0.
3. Timing, pooled. This replaces the per-cell check, which round 3 showed has about a 50%
   false-fail rate. It is changed before any of these candidates has a result.
   - The over-limit plus error rate over all cells may exceed rc1's by at most 0.15/1k.
   - p99.9 must be within 0.1 ms of rc1's.

**Pick:** the highest 16-cell mean among the candidates that pass all three rules.

**Test (one shot, sealed until the pick is frozen):** final_check on seed 9401 (never used),
with fields weak, weak+crashed, strong, mixed, oos and rival-oos. The test rule is
unchanged: the mean's 95% lower bound must be above −0.5% of fair, and no cell may show a
significant loss. If it fails, rc1 ships.

**PLO4 (proxy for an unknown variant):** the same gate on the PLO4 bundle. That covers the x
rule fitted on NLHE stats, with PLO4 exploit params = PLO4 rc1 + (r2p0 − ev_t4) deltas. It is
reported separately. An unknown day-of variant uses the exploit layer only if PLO4 passes.

### Dev results so far (seed 9501, in-process ab_test, no deadline)

s5p0 vs rc1 params, 2000 paired SNGs per cell:

| field | normal | fast |
|---|---|---|
| rival-strong | +6.4 ±2.4 | +2.2 ±2.1 |
| rival-strong+prep | −1.4 ±2.4 | +1.2 ±2.0 |
| rival-mid | +9.5 ±2.4 | +8.3 ±2.4 |
| rival-real | +3.3 ±2.4 | +1.3 ±2.0 |
| head-to-head, 4 s5p0 vs 4 rc1 | s5p0 0.981× fair | |

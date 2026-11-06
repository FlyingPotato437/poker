# Live adaptation during T1–T6: does it pay?

**Short answer: barely.** With this portfolio and these field models, fixed `cand_nlhe` is the
best strategy, or within noise of the best, in 11 of 14 named fields. The oracle, which plays
the true best strategy in every tournament, beats fixed cand by only **+0.59%** of fair
(weighted event score). Every general adaptive policy we tried **loses** to fixed cand
(−0.1 to −0.9%), because the choice of strategy rests on estimates whose noise is bigger
than the edges. The one exception is a single narrow level-2 rule (loose-passive field →
`r2p0`). It gains **+0.23% ±0.02** on average, +5.3% in a station-heavy field, and never
loses more than 0.3%.

## Files

| file | what |
|---|---|
| `nolimit/adapt.py` | portfolio, archetypes, 14 named scenarios + `uniform` proposal, random Dirichlet fields, drift, hand-log stats recorder, paired multi-strategy runner, MIS reweighting |
| `scripts/make_counters.py` | writes the 3 counter-strategies `params/adapt_{calldown,value,steal}.json` (cand + a few param shifts, base and exploit layer) |
| `scripts/adapt_matrix.py` | plays every SNG once per strategy (same seat, opponents, deck); writes `rec_<sched>_<scenario>.json` and `matrix_<sched>.{json,md}` |
| `scripts/event_sim.py` | payoff/stats model, event simulator, policies, classifier evaluation; `event_sim.{json,md}`, `classifier.{json,md}` |
| `scripts/event_validate.py` | full events with real SNGs (`event_sim.py --validate`); `validation.{json,md}` |
| `tests/test_event_sim.py` | stats counting, drift, model fit, scoring, policy logic |

## Portfolio

cand (`cand_nlhe`), ev_t4 (rc1), x, xex2, s5p0, r2p0, and three counters:
- `c_calldown`: wider shove calls, less survival premium. Meant for jammers and maniacs.
- `c_value`: assume opponents continue more, fewer bluffs, bigger value bets. Meant for
  stations.
- `c_steal`: open and shove wider, steal harder. Meant for nits.

## Scenarios

Named fields:
- std_tag ("everyone did the same research"), realistic (rival-real + LLM bugs),
  strong_mixed, prepped_heavy;
- llm_heavy, github_heavy (the `github` field's weights), github_tough (gh_ladder, flash,
  hobbyraise, potodds);
- jammer_heavy, station_heavy, nit_heavy, maniac_heavy, broken_heavy (timeouts and
  crashes);
- zoo_default and rival_mid.

`uniform` is used only as a sampling proposal. Random fields are Dirichlet(0.6) over 10
style groups, sharpened toward one group half the time.

Drift: each step between tournaments, U(0, 16%) of the seats (mean 8%) move toward one
target per event: weak bots fixed, more push/fold, more prepped code, a random field, or
no drift. Sealed styles (FRESH, OOS, rvh_*) are never used.

## Payoff matrix (normal blinds; `matrix_normal.md`)

The matrix comes from 19,600 base SNGs × 9 strategies, paired. Named scenarios ran 2,000
SNGs each (the GitHub fields, strong_mixed and uniform 600; realistic 1,200), because the
shared machine was at load 200–900. Paired se per cell is 1.0–2.5% at 2,000 SNGs and about
3.5% at 600. **Fast blinds were not run**, for lack of compute.

cand is beaten clearly in only two fields:
- **station_heavy:** r2p0 **+7.4 ±1.9**, and x +2.4.
- **nit_heavy:** c_value **+4.1 ±1.5**, and c_steal +2.3.

Within noise:
- maniac_heavy: r2p0 +2.3 ±1.6.
- jammer_heavy: c_steal +1.1 ±1.3.
- std_tag: c_steal +0.9 ±2.5.
- github_heavy: c_value +2.9 ±3.3.
- strong_mixed: r2p0 +2.9 ±4.2. The additive model says cand.

ev_t4 trails cand by 4–23% in every field, including prepped_heavy (−2.4%). `c_calldown`
never wins, and it costs 16% vs stations.

## Classifier (level 2; `classifier.md`)

Opponent stats come from the hand log: VPIP, PFR, postflop aggression, all-in rate,
fold-to-bet, WTSD and showdown rate. A ridge model maps standardized stats and their
squares to each strategy's gain over cand.

| hands in log | picks true best (random / named) | gain vs cand (random / named) | oracle gain (random / named) |
|---|---|---|---|
| 200 | 52% / 48% | −0.50% / −0.14% | +0.52% / +1.53% |
| 1,000 | 52% / 51% | −0.45% / +0.33% | |
| 5,000 | 52% / 46% | −0.42% / +0.33% | |
| full (10k SNGs) | 51% / 50% | −0.45% / +0.39% | |

Fields are easy to tell apart: stations show VPIP 0.46 and a showdown rate of 0.45, against
VPIP ≈ 0.2 elsewhere. But "which strategy is best" is mostly a sub-2% question that the
classifier can't resolve. cand is the true best in 65% of random fields, so a pick that
never leaves cand is as accurate as the classifier. Sample size barely matters past 200
hands.

## Event simulation (`event_sim.md`; 3,000 events, weights 1..6)

Setup:
- **Truth and knowledge are split.** The "truth" payoff model is fitted on half of the
  SNGs (even seeds). The policies' knowledge (calibration, hypotheses, classifier) comes
  from the other half.
- **Level-1 feedback:** our score = truth + a per-event sim-to-real bias (sd 5%, common to
  all strategies) + 10k-SNG noise (sd 1.0%).
- **Level-2 feedback:** field stats from 1,000 practice hands before T1, then exact stats
  after each tournament.

| policy | mean | p5 | gain vs cand (±se) | worst vs cand | regret vs oracle |
|---|---|---|---|---|---|
| a fixed cand | 1.920 | 1.405 | 0 | 0 | 0.59 |
| b fixed ev_t4 | 1.770 | 1.301 | −15.05 ±0.09 | −24.9 | 15.64 |
| c HANDOFF calibration rule (thr tuned → 0.40, i.e. almost never switch) | 1.919 | 1.394 | −0.14 ±0.02 | −10.6 | 0.73 |
| c2 Bayes on own scores (L1) | 1.911 | 1.405 | −0.92 ±0.03 | −6.0 | 1.52 |
| d L2 classifier, margin 1% | 1.914 | 1.399 | −0.57 ±0.03 | −11.0 | 1.16 |
| d3 L2 classifier, margin 3% | 1.919 | 1.405 | −0.08 ±0.02 | −8.5 | 0.67 |
| d2 nearest-centroid (L2) | 1.912 | 1.405 | −0.85 ±0.03 | −5.9 | 1.45 |
| e explore T2 then exploit (L1) | 1.918 | 1.405 | −0.26 ±0.01 | −3.8 | 0.85 |
| g Bayes L1 + L2 | 1.915 | 1.405 | −0.52 ±0.03 | −6.0 | 1.12 |
| **h station rule (L2)** | **1.922** | 1.405 | **+0.23 ±0.02** | **−0.3** | 0.36 |
| f oracle | 1.926 | 1.405 | +0.59 ±0.02 | 0 | 0 |

These numbers are robust to:
- no practice, a 200-hand practice, or the full practice log (identical to ±0.05);
- sim-to-real bias of 0 or 10%;
- heavy drift of 20% per step: oracle +0.42, station rule +0.13, the rest still negative.

Per named field (oracle / station rule):
- station_heavy: +5.7 / +5.3.
- maniac_heavy: +2.5 / 0.
- nit_heavy: +1.1 / 0.
- All others: ≤ +1.1 / 0.

Calibration rule (c) caveat: it switches to ev_t4 exactly when the field is prepped-heavy,
which costs −3.5% there. A low T1 score in a strong field is not a reason to go to ev_t4,
because cand is also better there.

Caveats:
- The payoff model is additive in the opponent styles. It is checked against each
  scenario's own direct means in `event_sim.md`: its error on the gain vs cand is ≤ 2% in the
  8 fields with 2,000 SNGs each, and 3–9% in realistic and the thin 600-SNG ones (part of
  that is the direct means' own noise of about 3.5%).
- The station rule's thresholds were chosen after seeing the named fields' stats. Its gain
  in random, out-of-sample fields is only +0.03%.

## Real-SNG validation (`validation.md`)

There were 6 full events, 2 each in station_heavy, nit_heavy and realistic, with drift.
Each tournament was 300 real paired SNGs for every strategy a policy picked, plus cand, on
fresh seeds. Policies saw real scores and real hand-log stats. See `validation.md` for the
per-event table; the summary is in the report it was written with.

## Day-of procedure

1. **Ship cand for T1 and keep it by default.** No result here justifies switching
   strategies on score alone. Our own x-fair (level 1) can't separate a hard field from a
   sim-to-real gap, and the HANDOFF rule "switch to rc1 if T1 is far below calibration" is
   negative in expectation (−0.14%). It loses 3.5% exactly when it fires, in prepped fields.
2. **If hand logs are available (practice or T1),** compute the opponents' aggregate VPIP
   and PFR (per seat-hand; `nolimit/adapt.py: hand_stats` does this from a history).
   - **Switch to `r2p0` only if VPIP > 0.35 and PFR < 0.12** (a loose-passive, station
     field; ours: VPIP 0.46, PFR 0.06; every other field has VPIP < 0.34).
   - Keep re-checking after each tournament; switch back to cand if the field leaves that
     region.
3. **Otherwise don't switch.** That includes nit-looking fields, even though c_value is
   +4% vs our nit_heavy model: no policy captured it without losing more elsewhere.
4. **Resubmission budget:** spend it on fixes (crash, timeout, a rules mismatch), not on
   strategy rotation. Exploring an alternative in T1/T2 cost −0.26% and never paid for
   itself.

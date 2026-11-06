# Live adaptation during T1–T6: does it pay?

**Short answer: no measurable gain.** With this portfolio and these field models, fixed
`cand_nlhe` is the best strategy, or within noise of the best, in 14 of 16 named fields. That
includes the two event-like fields, built from bots modeled on public repos for this event.

The oracle, which plays the true best strategy in every tournament, beats fixed cand by
only **+0.52%** of fair on the weighted event score. Every general adaptive policy we tried
**loses** to fixed cand (−0.06 to −1.1%), because picking a strategy rests on estimates
whose noise is bigger than the edges.

One narrow level-2 rule (loose-passive field → `r2p0`) gains **+0.14% ±0.02** in the
model, +5.6% in a station-heavy field, and never loses more than 0.3%. Its edge was only
partly confirmed with real SNGs: about +1% vs +4.6% predicted.

## Files

| file | what |
|---|---|
| `nolimit/adapt.py` | portfolio, archetypes (zoo, rivals, LLM bugs, GitHub bots, event bots, prepped), named scenarios + `uniform` proposal, random Dirichlet fields, drift, hand-log stats recorder, paired multi-strategy runner, MIS reweighting |
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
- **event_like and event_like_prep** (EVENT_WEIGHTS over EVENT_BOTS, ± a prepped copy);
- jammer_heavy, station_heavy, nit_heavy, maniac_heavy, broken_heavy (timeouts and
  crashes);
- zoo_default and rival_mid.

`uniform` is used only as a sampling proposal. Random fields are Dirichlet(0.6) over 11
style groups, sharpened toward one group half the time.

Drift: each step between tournaments, U(0, 16%) of the seats (mean 8%) move toward one
target per event: weak bots fixed, more push/fold, more prepped code, a random field, or
no drift. Sealed styles (FRESH, OOS, rvh_*) are never used.

## Payoff matrix (`matrix_normal.md`, `matrix_fast.md`)

**Normal blinds:** 21,600 base SNGs × 9 strategies, paired.
- Most fields ran 2,000 SNGs each; realistic 1,200; event_like and event_like_prep 1,000;
  github_heavy, github_tough, strong_mixed and uniform 600. The shared machine sat at load
  200–900 for hours.
- Paired se per cell is 1.0–2.5% at 2,000 SNGs and about 3% at 600–1,000.

Where cand is beaten clearly (paired, % of fair):
- **station_heavy:** r2p0 **+7.4 ±1.9**, and x +2.4.
- **nit_heavy:** c_value **+4.1 ±1.5**, and c_steal +2.3.

Within noise:
- maniac_heavy: r2p0 +2.3 ±1.6.
- jammer_heavy: c_steal +1.1 ±1.3.
- std_tag: c_steal +0.9 ±2.5.
- github_heavy: c_value +2.9 ±3.3.
- strong_mixed: r2p0 +2.9 ±4.2.

cand is best in event_like (xex2 −0.9 ±2.3, every other strategy −1.5 to −12%), in
event_like_prep (xex2 −2.3, the rest −6 to −12%), and in realistic, prepped_heavy,
broken_heavy and github_tough.

ev_t4 trails cand by 3–23% in every field, including prepped_heavy. `c_calldown` never
wins, and it costs 16% vs stations.

**Fast blinds** (10 hands a level; 10 fields × 1,200 SNGs). The pattern is the same:
- **r2p0 wins clearly vs loose fields:** station_heavy **+9.8 ±2.6** and maniac_heavy
  **+4.5 ±1.9**.
- **cand is best or tied elsewhere:** event_like xex2 −0.7, event_like_prep xex2 +0.2
  ±1.4, prepped_heavy x +0.7 ±2.3.
- **nit_heavy:** c_value's normal-blind edge disappears (+0.6 ±1.9).

The event sim uses the normal-blind records only.

## Classifier (level 2; `classifier.md`)

Opponent stats come from the hand log: VPIP, PFR, postflop aggression, all-in rate,
fold-to-bet, WTSD and showdown rate. A ridge model maps standardized stats and their
squares to each strategy's gain over cand.

| hands in log | picks true best (random / named) | gain vs cand (random / named) | oracle gain (random / named) |
|---|---|---|---|
| 200 | 60% / 46% | −0.09% / +0.05% | +0.50% / +1.68% |
| 1,000 | 61% / 46% | −0.09% / +0.35% | |
| 5,000 | 60% / 43% | −0.13% / +0.41% | |
| full (10k SNGs) | 60% / 38% | −0.15% / +0.21% | |

Fields are easy to tell apart. Stations show VPIP 0.46, PFR 0.06 and a showdown rate of
0.45; other fields have VPIP 0.12–0.34. But "which strategy is best" is mostly a sub-2%
question that the classifier can't resolve. cand is the true best in 64% of random fields,
so "always cand" is as accurate as the classifier. Sample size doesn't matter past 200
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

Score = weighted x-fair:

| policy | mean | p5 | gain vs cand (±se) | worst vs cand | regret vs oracle |
|---|---|---|---|---|---|
| a fixed cand | 1.873 | 1.371 | 0 | 0 | 0.52 |
| b fixed ev_t4 | 1.726 | 1.274 | −14.69 ±0.09 | −24.9 | 15.21 |
| c HANDOFF calibration rule (thr tuned → 0.40, i.e. almost never switch) | 1.872 | 1.365 | −0.10 ±0.01 | −10.6 | 0.63 |
| c2 Bayes on own scores (L1), 1% margin | 1.872 | 1.370 | −0.06 ±0.01 | −4.9 | 0.59 |
| d L2 classifier, margin 1% | 1.868 | 1.371 | −0.53 ±0.03 | −10.4 | 1.05 |
| d3 L2 classifier, margin 3% | 1.871 | 1.371 | −0.20 ±0.02 | −10.2 | 0.72 |
| d2 nearest-centroid (L2) | 1.862 | 1.370 | −1.09 ±0.03 | −6.3 | 1.62 |
| e explore T2 then exploit (L1) | 1.871 | 1.369 | −0.17 ±0.01 | −5.2 | 0.70 |
| g Bayes L1 + L2 | 1.871 | 1.368 | −0.23 ±0.02 | −5.8 | 0.76 |
| **h station rule (L2)** | **1.874** | 1.371 | **+0.14 ±0.02** | **−0.3** | 0.39 |
| f oracle | 1.878 | 1.375 | +0.52 ±0.02 | 0 | 0 |

These numbers are robust to:
- no practice, a 200-hand practice, or the full practice log (identical to ±0.05);
- sim-to-real bias of 0 or 10%;
- heavy drift of 20% per step: oracle +0.37, station rule +0.06, the rest still negative.

Per named field (oracle / station rule):
- station_heavy: +5.9 / +5.6.
- maniac_heavy: +2.6 / 0.
- nit_heavy: +1.2 / 0.
- event_like: +1.0 / 0.
- All others: ≤ +1.2 / 0.

Calibration rule (c) caveat: it fires exactly in prepped fields, where switching to ev_t4
costs 2.9%. A low T1 score means a strong field, and cand is also better there.

Caveats:
- The payoff model is additive in the opponent styles. It is checked against each
  scenario's own direct means in `event_sim.md`: its error on the gain vs cand is ≤ 2% in
  the 2,000-SNG fields, and 3–9% in the thin 600–1,200-SNG ones (part of that is the direct
  means' own noise of about 3%).
- The station rule's thresholds were chosen after seeing the named fields' stats. Its gain
  in random, out-of-sample fields is only +0.03%.

## Real-SNG validation (`validation.md`)

There were 6 full events, 2 each in station_heavy, nit_heavy and realistic, with drift.
Each tournament was 300 real paired SNGs for every strategy a policy picked, plus cand, on
fresh seeds. Policies saw real scores and real hand-log stats. The validation started
before the event-like fields and rule h existed.

Mean gain vs fixed cand over the 6 events, real SNGs / payoff-model prediction (% of fair;
the real numbers have se ≈ 0.8):

| policy | real | model |
|---|---|---|
| fixed ev_t4 | −15.4 | −17.3 |
| HANDOFF rule | 0 (never fired) | 0 |
| Bayes L1 | −0.6 | −0.3 |
| classifier L2 (1% / 3% margin) | −0.15 / −0.16 | −0.17 / +0.29 |
| nearest centroid L2 | +1.1 | +0.7 |
| explore L1 | −0.4 | −0.2 |
| Bayes L1+L2 | −0.3 | 0.0 |
| model-oracle | +0.1 | +1.5 |

- **Fixed-strategy levels agree well.** Real per-round x-fair matches the model to within
  about 0.05–0.1.
- **The r2p0 edge in station fields mostly did not show.** In the two station events (both
  drifting away from stations), r2p0 − cand was about +0.9% real vs +4.6% predicted.
- **The centroid's +1.1% is noise.** It came from c_steal in the nit events (real +3 to
  +5%), which the model never predicted.
- **Overall: no policy shows a significant real gain over fixed cand.**

## Day-of procedure

1. **Ship cand for T1 and keep it by default.** No result here justifies switching
   strategies on score alone. Our own x-fair (level 1) can't separate a hard field from a
   sim-to-real gap. The HANDOFF rule "switch to rc1 if T1 is far below calibration" is
   negative in expectation, and it loses about 3% exactly when it fires, in prepped
   fields. Never switch to ev_t4 for strategic reasons.
2. **If hand logs are available (practice or T1),** compute the opponents' aggregate VPIP
   and PFR (per seat-hand; `nolimit/adapt.py: hand_stats` does this from a history).
   - **Switch to `r2p0` only if VPIP > 0.35 and PFR < 0.12** (a loose-passive, station
     field: ours shows VPIP 0.46, PFR 0.06; the event-like field shows 0.21 / 0.17).
   - Keep re-checking after each tournament; switch back to cand if the field leaves that
     region.
   - The upside is small and only half-confirmed. Treat it as optional; it is cheap
     because it almost never fires.
3. **Otherwise don't switch.** That includes nit-looking fields, even though c_value is
   +4% vs our nit_heavy model: no policy captured it without losing more elsewhere.
4. **Resubmission budget:** spend it on fixes (crash, timeout, a rules mismatch), not on
   strategy rotation. Exploring an alternative in T1/T2 cost −0.17% and never paid for
   itself.

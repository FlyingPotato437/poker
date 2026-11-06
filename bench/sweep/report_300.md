# Stipulation sweep: prep:params/cand_nlhe.json

Baseline `prep:params/ev_t4.json`; bundle `nlhe_rng.nlb`; 300 SNGs per cell (paired with the baseline when there is one), seed 7301, 2026-11-06 02:41, 767s.

Default cell: players=8, stack_bb=100, hands_per_level=25, ante=0, hand_cap=200, reopen_short=off, points=default, cap_scoring=icm, field=rival-real, variant=nlhe, special=none.

x-fair = points per table / fair share (1.00 = break-even). SD = SD of one table's x-fair. A-B = paired candidate minus baseline, % of fair. 95% CI = ±1.96 se. Flags: **bold** = significant at 95%, (ns) = point estimate only.

## Factors ranked by how much they move x-fair

| rank | factor | x-fair range | range / se | worst level | best level | SD range (min-max) | A-B range |
|---|---|---|---|---|---|---|---|
| 1 | points | 0.960 | 4.7 | slope (1.345) | wta (2.305) | 2.867 (0.60-3.47) | 14.0% |
| 2 | field | 0.828 | 10.7 | rival-strong (1.407) | zoo (2.235) | 0.204 (0.86-1.07) | 9.4% |
| 3 | hands_per_level | 0.547 | 7.6 | 5 (1.093) | 50 (1.640) | 0.255 (0.81-1.07) | 14.3% |
| 4 | special | 0.443 | 5.2 | 3-raise-cap (1.428) | straddle (1.870) | 0.177 (1.00-1.18) | 26.8% |
| 5 | stack_bb | 0.358 | 4.5 | 25 (1.288) | 200 (1.646) | 0.200 (0.87-1.07) | 7.7% |
| 6 | variant | 0.293 | 3.4 | shortdeck (1.301) | nlhe (1.594) | 0.065 (1.00-1.07) |  |
| 7 | hand_cap | 0.186 | 2.5 | 100 (1.408) | 200 (1.594) | 0.344 (0.73-1.07) | 9.3% |
| 8 | players | 0.171 | 2.1 | 9 (1.479) | 10 (1.650) | 0.319 (0.77-1.09) | 14.8% |
| 9 | ante | 0.166 | 1.9 | 0 (1.594) | 0.25bb (1.760) | 0.038 (1.07-1.10) | 8.7% |
| 10 | cap_scoring | 0.033 | 0.4 | icm (1.594) | chips (1.627) | 0.057 (1.07-1.12) | 3.3% |
| 11 | reopen_short | 0.020 | 0.2 | on (1.574) | off (1.594) | 0.008 (1.06-1.07) | 1.5% |

## Factors ranked by score variance (SD per table)

| rank | factor | SD min | SD max | max/min | level with max SD |
|---|---|---|---|---|---|
| 1 | points | 0.60 | 3.47 | 5.77 | wta |
| 2 | hand_cap | 0.73 | 1.07 | 1.47 | 400 |
| 3 | players | 0.77 | 1.09 | 1.41 | 6 |
| 4 | hands_per_level | 0.81 | 1.07 | 1.31 | 25 |
| 5 | field | 0.86 | 1.07 | 1.24 | rival-real |
| 6 | stack_bb | 0.87 | 1.07 | 1.23 | 100 |
| 7 | special | 1.00 | 1.18 | 1.18 | ko-10pts |
| 8 | variant | 1.00 | 1.07 | 1.06 | plo4 |
| 9 | cap_scoring | 1.07 | 1.12 | 1.05 | chips |
| 10 | ante | 1.07 | 1.10 | 1.04 | 0.1bb |
| 11 | reopen_short | 1.06 | 1.07 | 1.01 | off |

## Every cell

| factor | level | x-fair | ±se | SD | baseline x-fair | A-B % fair | ±se | flags | tables | errors |
|---|---|---|---|---|---|---|---|---|---|---|
| players | 2 | 1.640 | 0.044 | 0.77 | 1.447 | +19.3 | 5.1 |  | 300 | 0 |
| players | 3 | 1.572 | 0.059 | 1.02 | 1.474 | +9.8 | 6.9 |  | 300 | 0 |
| players | 4 | 1.625 | 0.060 | 1.04 | 1.523 | +10.2 | 6.7 |  | 300 | 0 |
| players | 6 | 1.528 | 0.063 | 1.09 | 1.482 | +4.5 | 6.5 |  | 300 | 0 |
| players | 8 (default) | 1.594 | 0.062 | 1.07 | 1.428 | +16.6 | 6.0 |  | 300 | 0 |
| players | 9 | 1.479 | 0.058 | 1.00 | 1.378 | +10.1 | 6.1 |  | 300 | 0 |
| players | 10 | 1.650 | 0.059 | 1.02 | 1.472 | +17.7 | 5.8 |  | 300 | 0 |
| stack_bb | 25 | 1.288 | 0.059 | 1.03 | 1.191 | +9.7 | 6.2 |  | 300 | 0 |
| stack_bb | 50 | 1.367 | 0.059 | 1.02 | 1.212 | +15.5 | 5.9 |  | 300 | 0 |
| stack_bb | 100 (default) | 1.594 | 0.062 | 1.07 | 1.428 | +16.6 | 6.0 |  | 300 | 0 |
| stack_bb | 200 | 1.646 | 0.054 | 0.93 | 1.494 | +15.2 | 5.8 |  | 300 | 0 |
| stack_bb | 300 | 1.612 | 0.050 | 0.87 | 1.522 | +8.9 | 4.8 |  | 300 | 0 |
| hands_per_level | 5 | 1.093 | 0.055 | 0.95 | 1.070 | +2.3 | 5.1 |  | 300 | 0 |
| hands_per_level | 10 | 1.274 | 0.058 | 1.01 | 1.183 | +9.1 | 6.0 |  | 300 | 0 |
| hands_per_level | 25 (default) | 1.594 | 0.062 | 1.07 | 1.428 | +16.6 | 6.0 |  | 300 | 0 |
| hands_per_level | 50 | 1.640 | 0.047 | 0.81 | 1.609 | +3.1 | 4.5 |  | 300 | 0 |
| ante | 0 (default) | 1.594 | 0.062 | 1.07 | 1.428 | +16.6 | 6.0 |  | 300 | 0 |
| ante | 0.1bb | 1.658 | 0.064 | 1.10 | 1.543 | +11.5 | 6.7 |  | 300 | 0 |
| ante | 0.25bb | 1.760 | 0.063 | 1.09 | 1.604 | +15.6 | 6.3 |  | 300 | 0 |
| ante | bb-ante | 1.754 | 0.064 | 1.10 | 1.674 | +7.9 | 6.8 |  | 300 | 0 |
| hand_cap | 100 | 1.408 | 0.042 | 0.73 | 1.335 | +7.3 | 3.6 |  | 300 | 0 |
| hand_cap | 200 (default) | 1.594 | 0.062 | 1.07 | 1.428 | +16.6 | 6.0 |  | 300 | 0 |
| hand_cap | 400 | 1.588 | 0.062 | 1.07 | 1.427 | +16.1 | 6.1 |  | 300 | 0 |
| hand_cap | none | 1.588 | 0.062 | 1.07 | 1.427 | +16.1 | 6.1 |  | 300 | 0 |
| reopen_short | off (default) | 1.594 | 0.062 | 1.07 | 1.428 | +16.6 | 6.0 |  | 300 | 0 |
| reopen_short | on | 1.574 | 0.061 | 1.06 | 1.424 | +15.1 | 6.0 |  | 300 | 0 |
| points | default (default) | 1.594 | 0.062 | 1.07 | 1.428 | +16.6 | 6.0 |  | 300 | 0 |
| points | top-heavy | 1.981 | 0.113 | 1.97 | 1.745 | +23.6 | 12.7 |  | 300 | 0 |
| points | linear | 1.387 | 0.035 | 0.60 | 1.254 | +13.3 | 3.6 |  | 300 | 0 |
| points | top-3 | 1.784 | 0.101 | 1.75 | 1.599 | +18.5 | 10.6 |  | 300 | 0 |
| points | wta | 2.305 | 0.200 | 3.47 | 2.188 | +11.6 | 25.4 |  | 300 | 0 |
| points | slope | 1.345 | 0.035 | 0.61 | 1.248 | +9.6 | 3.9 |  | 300 | 0 |
| cap_scoring | icm (default) | 1.594 | 0.062 | 1.07 | 1.428 | +16.6 | 6.0 |  | 300 | 0 |
| cap_scoring | chips | 1.627 | 0.065 | 1.12 | 1.428 | +19.9 | 6.3 |  | 300 | 0 |
| field | zoo | 2.235 | 0.050 | 0.86 | 2.048 | +18.6 | 4.5 |  | 300 | 0 |
| field | rival-real (default) | 1.594 | 0.062 | 1.07 | 1.428 | +16.6 | 6.0 |  | 300 | 0 |
| field | rival-strong | 1.407 | 0.059 | 1.02 | 1.182 | +22.5 | 6.4 |  | 300 | 0 |
| field | llm-bugs | 2.051 | 0.056 | 0.96 | 1.920 | +13.1 | 5.7 |  | 300 | 0 |
| variant | nlhe (default) | 1.594 | 0.062 | 1.07 | 1.428 | +16.6 | 6.0 |  | 300 | 0 |
| variant | shortdeck | 1.301 | 0.059 | 1.02 | — | — | — |  | 300 | 0 |
| variant | shortdeck_triton | 1.432 | 0.060 | 1.04 | — | — | — |  | 300 | 0 |
| variant | plo4 | 1.447 | 0.062 | 1.07 | — | — | — |  | 300 | 0 |
| variant | plo5 | 1.385 | 0.061 | 1.05 | — | — | — |  | 300 | 0 |
| variant | holdem3 | 1.321 | 0.058 | 1.00 | — | — | — |  | 300 | 0 |
| special | none (default) | 1.594 | 0.062 | 1.07 | 1.428 | +16.6 | 6.0 |  | 300 | 0 |
| special | 72-bounty | 1.591 | 0.062 | 1.07 | 1.434 | +15.7 | 6.1 |  | 300 | 0 |
| special | 72-bounty-noshow | 1.621 | 0.062 | 1.08 | 1.480 | +14.1 | 6.2 |  | 300 | 0 |
| special | 72-bounty-aware | 1.540 | 0.062 | 1.08 | 1.591 | -5.2 | 4.9 | < baseline (ns) | 300 | 0 |
| special | straddle | 1.870 | 0.060 | 1.05 | 1.800 | +7.0 | 6.3 |  | 300 | 0 |
| special | bomb/10 | 1.642 | 0.061 | 1.06 | 1.425 | +21.7 | 6.5 |  | 300 | 0 |
| special | run-twice | 1.543 | 0.058 | 1.00 | 1.329 | +21.5 | 6.5 |  | 300 | 0 |
| special | ko-10pts | 1.644 | 0.068 | 1.18 | 1.487 | +15.7 | 6.7 |  | 300 | 0 |
| special | bet-cap-30bb | 1.513 | 0.061 | 1.05 | 1.374 | +13.9 | 6.3 |  | 300 | 0 |
| special | 3-raise-cap | 1.428 | 0.061 | 1.05 | 1.234 | +19.4 | 6.1 |  | 300 | 0 |
| special | dead-button | 1.565 | 0.060 | 1.05 | 1.367 | +19.8 | 6.2 |  | 300 | 0 |
| special | uneven-stacks | 1.451 | 0.061 | 1.06 | 1.302 | +14.9 | 5.8 |  | 300 | 0 |

## Sample size (default cell)

Points SD per SNG for the candidate: 37.1 points (1.07 x-fair; fair = 34.8).
Paired A-B SD per SNG: 1.04 x-fair (0.98 of the unpaired SD).

SNGs needed to detect an edge of e (fraction of fair), 95% two-sided; 'CI' = 95% half-width equals e, '80% power' = (1.96 + 0.84)^2 (SD/e)^2.

| comparison | e=1% CI | e=1% 80% power | e=2% CI | e=2% 80% power | e=5% CI | e=5% 80% power |
|---|---|---|---|---|---|---|
| unpaired (one bot's score) | 43,733 | 89,250 | 10,933 | 22,313 | 1,749 | 3,570 |
| paired A-B (same seats and cards) | 41,773 | 85,251 | 10,443 | 21,313 | 1,671 | 3,410 |

One scored tournament (10,000 SNGs) pins our x-fair to ±0.021 (95%).

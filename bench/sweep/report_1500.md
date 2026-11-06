# Stipulation sweep: prep:params/cand_nlhe.json

Baseline `prep:params/ev_t4.json`; bundle `nlhe_rng.nlb`; 1500 SNGs per cell (paired with the baseline when there is one), seed 7301, 2026-11-06 04:56, 7910s.

Default cell: players=8, stack_bb=100, hands_per_level=25, ante=0, hand_cap=200, reopen_short=off, points=default, cap_scoring=icm, field=rival-real, variant=nlhe, special=none.

x-fair = points per table / fair share (1.00 = break-even). SD = SD of one table's x-fair. A-B = paired candidate minus baseline, % of fair. 95% CI = ±1.96 se. Flags: **bold** = significant at 95%, (ns) = point estimate only.

## Factors ranked by how much they move x-fair

| rank | factor | x-fair range | range / se | worst level | best level | SD range (min-max) | A-B range |
|---|---|---|---|---|---|---|---|
| 1 | points | 1.247 | 13.2 | slope (1.347) | wta (2.594) | 3.006 (0.61-3.61) | 26.9% |
| 2 | field | 0.809 | 23.3 | rival-strong (1.419) | zoo (2.228) | 0.201 (0.86-1.06) | 4.9% |
| 3 | hands_per_level | 0.557 | 16.8 | 5 (1.095) | 50 (1.652) | 0.199 (0.86-1.06) | 8.3% |
| 4 | stack_bb | 0.431 | 12.5 | 25 (1.245) | 300 (1.677) | 0.197 (0.86-1.06) | 7.4% |
| 5 | special | 0.382 | 10.0 | run-twice (1.423) | straddle (1.805) | 0.152 (1.01-1.16) | 22.9% |
| 6 | ante | 0.235 | 6.0 | 0 (1.548) | 0.25bb (1.782) | 0.040 (1.06-1.10) | 3.4% |
| 7 | variant | 0.186 | 4.8 | shortdeck (1.362) | nlhe (1.548) | 0.060 (1.03-1.09) |  |
| 8 | hand_cap | 0.178 | 5.4 | 100 (1.370) | 200 (1.548) | 0.362 (0.70-1.07) | 11.0% |
| 9 | players | 0.144 | 3.8 | 9 (1.515) | 4 (1.658) | 0.241 (0.84-1.08) | 8.2% |
| 10 | cap_scoring | 0.033 | 0.8 | icm (1.548) | chips (1.581) | 0.054 (1.06-1.11) | 3.0% |
| 11 | reopen_short | 0.014 | 0.4 | on (1.533) | off (1.548) | 0.005 (1.05-1.06) | 1.8% |

## Factors ranked by score variance (SD per table)

| rank | factor | SD min | SD max | max/min | level with max SD |
|---|---|---|---|---|---|
| 1 | points | 0.61 | 3.61 | 5.96 | wta |
| 2 | hand_cap | 0.70 | 1.07 | 1.51 | 400 |
| 3 | players | 0.84 | 1.08 | 1.29 | 6 |
| 4 | field | 0.86 | 1.06 | 1.23 | rival-real |
| 5 | hands_per_level | 0.86 | 1.06 | 1.23 | 25 |
| 6 | stack_bb | 0.86 | 1.06 | 1.23 | 100 |
| 7 | special | 1.01 | 1.16 | 1.15 | ko-10pts |
| 8 | variant | 1.03 | 1.09 | 1.06 | plo5 |
| 9 | cap_scoring | 1.06 | 1.11 | 1.05 | chips |
| 10 | ante | 1.06 | 1.10 | 1.04 | bb-ante |
| 11 | reopen_short | 1.05 | 1.06 | 1.01 | off |

## Every cell

| factor | level | x-fair | ±se | SD | baseline x-fair | A-B % fair | ±se | flags | tables | errors |
|---|---|---|---|---|---|---|---|---|---|---|
| players | 2 | 1.545 | 0.022 | 0.84 | 1.425 | +12.0 | 2.4 |  | 1500 | 0 |
| players | 3 | 1.628 | 0.026 | 1.01 | 1.476 | +15.2 | 3.0 |  | 1500 | 0 |
| players | 4 | 1.658 | 0.027 | 1.05 | 1.457 | +20.2 | 3.0 |  | 1500 | 0 |
| players | 6 | 1.578 | 0.028 | 1.08 | 1.454 | +12.4 | 2.9 |  | 1500 | 0 |
| players | 8 (default) | 1.548 | 0.027 | 1.06 | 1.422 | +12.5 | 2.9 |  | 1500 | 0 |
| players | 9 | 1.515 | 0.026 | 1.02 | 1.355 | +16.0 | 2.8 |  | 1500 | 0 |
| players | 10 | 1.541 | 0.026 | 1.00 | 1.381 | +16.0 | 2.7 |  | 1500 | 0 |
| stack_bb | 25 | 1.245 | 0.026 | 1.02 | 1.108 | +13.7 | 2.7 |  | 1500 | 0 |
| stack_bb | 50 | 1.366 | 0.026 | 1.02 | 1.271 | +9.5 | 2.8 |  | 1500 | 0 |
| stack_bb | 100 (default) | 1.548 | 0.027 | 1.06 | 1.422 | +12.5 | 2.9 |  | 1500 | 0 |
| stack_bb | 200 | 1.661 | 0.025 | 0.97 | 1.502 | +15.9 | 2.6 |  | 1500 | 0 |
| stack_bb | 300 | 1.677 | 0.022 | 0.86 | 1.592 | +8.5 | 2.3 |  | 1500 | 0 |
| hands_per_level | 5 | 1.095 | 0.025 | 0.95 | 1.053 | +4.2 | 2.3 |  | 1500 | 0 |
| hands_per_level | 10 | 1.182 | 0.025 | 0.97 | 1.103 | +7.9 | 2.5 |  | 1500 | 0 |
| hands_per_level | 25 (default) | 1.548 | 0.027 | 1.06 | 1.422 | +12.5 | 2.9 |  | 1500 | 0 |
| hands_per_level | 50 | 1.652 | 0.022 | 0.86 | 1.577 | +7.6 | 2.1 |  | 1500 | 0 |
| ante | 0 (default) | 1.548 | 0.027 | 1.06 | 1.422 | +12.5 | 2.9 |  | 1500 | 0 |
| ante | 0.1bb | 1.673 | 0.028 | 1.07 | 1.546 | +12.7 | 2.9 |  | 1500 | 0 |
| ante | 0.25bb | 1.782 | 0.028 | 1.09 | 1.647 | +13.5 | 2.9 |  | 1500 | 0 |
| ante | bb-ante | 1.774 | 0.028 | 1.10 | 1.673 | +10.1 | 3.0 |  | 1500 | 0 |
| hand_cap | 100 | 1.370 | 0.018 | 0.70 | 1.354 | +1.6 | 1.6 |  | 1500 | 0 |
| hand_cap | 200 (default) | 1.548 | 0.027 | 1.06 | 1.422 | +12.5 | 2.9 |  | 1500 | 0 |
| hand_cap | 400 | 1.544 | 0.028 | 1.07 | 1.422 | +12.1 | 2.9 |  | 1500 | 0 |
| hand_cap | none | 1.544 | 0.028 | 1.07 | 1.422 | +12.1 | 2.9 |  | 1500 | 0 |
| reopen_short | off (default) | 1.548 | 0.027 | 1.06 | 1.422 | +12.5 | 2.9 |  | 1500 | 0 |
| reopen_short | on | 1.533 | 0.027 | 1.05 | 1.426 | +10.7 | 2.8 |  | 1500 | 0 |
| points | default (default) | 1.548 | 0.027 | 1.06 | 1.422 | +12.5 | 2.9 |  | 1500 | 0 |
| points | top-heavy | 1.984 | 0.050 | 1.94 | 1.705 | +27.9 | 5.5 |  | 1500 | 0 |
| points | linear | 1.360 | 0.016 | 0.61 | 1.274 | +8.6 | 1.6 |  | 1500 | 0 |
| points | top-3 | 1.810 | 0.045 | 1.74 | 1.622 | +18.8 | 4.8 |  | 1500 | 0 |
| points | wta | 2.594 | 0.093 | 3.61 | 2.239 | +35.5 | 11.3 |  | 1500 | 0 |
| points | slope | 1.347 | 0.016 | 0.61 | 1.251 | +9.6 | 1.6 |  | 1500 | 0 |
| cap_scoring | icm (default) | 1.548 | 0.027 | 1.06 | 1.422 | +12.5 | 2.9 |  | 1500 | 0 |
| cap_scoring | chips | 1.581 | 0.029 | 1.11 | 1.426 | +15.6 | 3.0 |  | 1500 | 0 |
| field | zoo | 2.228 | 0.022 | 0.86 | 2.053 | +17.5 | 2.0 |  | 1500 | 0 |
| field | rival-real (default) | 1.548 | 0.027 | 1.06 | 1.422 | +12.5 | 2.9 |  | 1500 | 0 |
| field | rival-strong | 1.419 | 0.027 | 1.03 | 1.266 | +15.3 | 2.9 |  | 1500 | 0 |
| field | llm-bugs | 2.066 | 0.025 | 0.95 | 1.911 | +15.5 | 2.5 |  | 1500 | 0 |
| variant | nlhe (default) | 1.548 | 0.027 | 1.06 | 1.422 | +12.5 | 2.9 |  | 1500 | 0 |
| variant | shortdeck | 1.362 | 0.027 | 1.05 | — | — | — |  | 1500 | 0 |
| variant | shortdeck_triton | 1.373 | 0.027 | 1.04 | — | — | — |  | 1500 | 0 |
| variant | plo4 | 1.387 | 0.027 | 1.06 | — | — | — |  | 1500 | 0 |
| variant | plo5 | 1.425 | 0.028 | 1.09 | — | — | — |  | 1500 | 0 |
| variant | holdem3 | 1.403 | 0.027 | 1.03 | — | — | — |  | 1500 | 0 |
| special | none (default) | 1.548 | 0.027 | 1.06 | 1.422 | +12.5 | 2.9 |  | 1500 | 0 |
| special | 72-bounty | 1.549 | 0.027 | 1.06 | 1.426 | +12.3 | 2.9 |  | 1500 | 0 |
| special | 72-bounty-noshow | 1.590 | 0.028 | 1.08 | 1.461 | +12.9 | 2.9 |  | 1500 | 0 |
| special | 72-bounty-aware | 1.519 | 0.028 | 1.07 | 1.549 | -3.0 | 2.0 | < baseline (ns) | 1500 | 0 |
| special | straddle | 1.805 | 0.028 | 1.08 | 1.723 | +8.2 | 2.8 |  | 1500 | 0 |
| special | bomb/10 | 1.646 | 0.028 | 1.08 | 1.447 | +19.9 | 2.9 |  | 1500 | 0 |
| special | run-twice | 1.423 | 0.026 | 1.01 | 1.344 | +7.9 | 2.8 |  | 1500 | 0 |
| special | ko-10pts | 1.596 | 0.030 | 1.16 | 1.482 | +11.3 | 3.1 |  | 1500 | 0 |
| special | bet-cap-30bb | 1.524 | 0.027 | 1.05 | 1.414 | +11.0 | 2.9 |  | 1500 | 0 |
| special | 3-raise-cap | 1.438 | 0.027 | 1.06 | 1.328 | +11.0 | 2.9 |  | 1500 | 0 |
| special | dead-button | 1.565 | 0.027 | 1.06 | 1.415 | +15.0 | 2.9 |  | 1500 | 0 |
| special | uneven-stacks | 1.510 | 0.027 | 1.06 | 1.337 | +17.3 | 2.8 |  | 1500 | 0 |

## Sample size (default cell)

Points SD per SNG for the candidate: 36.8 points (1.06 x-fair; fair = 34.8).
Paired A-B SD per SNG: 1.10 x-fair (1.04 of the unpaired SD).

SNGs needed to detect an edge of e (fraction of fair), 95% two-sided; 'CI' = 95% half-width equals e, '80% power' = (1.96 + 0.84)^2 (SD/e)^2.

| comparison | e=1% CI | e=1% 80% power | e=2% CI | e=2% 80% power | e=5% CI | e=5% 80% power |
|---|---|---|---|---|---|---|
| unpaired (one bot's score) | 43,174 | 88,110 | 10,794 | 22,028 | 1,727 | 3,524 |
| paired A-B (same seats and cards) | 46,809 | 95,529 | 11,702 | 23,882 | 1,872 | 3,821 |

One scored tournament (10,000 SNGs) pins our x-fair to ±0.021 (95%).

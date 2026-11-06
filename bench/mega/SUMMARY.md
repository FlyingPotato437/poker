# bench/mega summary: cand_nlhe (A) vs ev_t4 (B), payouts default

CI = 95% (1.96 se). % of fair. FLAG = CI entirely below 0. h2h = A's share of fair in 4v4 (no se printed).


## run1_broad_5000_9981.txt

| blinds | field | A-B % fair | 95% CI | flag |
|---|---|---|---|---|
| normal | gate-weak | +15.8% | ±2.7 [+13.1, +18.5] |  |
| normal | gate-weak+crashed | +15.8% | ±2.8 [+13.0, +18.6] |  |
| normal | gate-strong | +4.9% | ±2.6 [+2.3, +7.5] |  |
| normal | gate-mixed | +12.4% | ±2.8 [+9.6, +15.2] |  |
| normal | rival-strong | +15.4% | ±3.0 [+12.4, +18.4] |  |
| normal | rival-strong+prep | +8.2% | ±2.9 [+5.3, +11.1] |  |
| normal | rival-mid | +22.3% | ±3.2 [+19.1, +25.5] |  |
| normal | rival-real | +14.7% | ±3.0 [+11.7, +17.7] |  |
| normal | llm-bugs | +12.8% | ±2.7 [+10.1, +15.5] |  |
| normal | llm-bugs+prep | +8.9% | ±2.7 [+6.2, +11.6] |  |
| normal | github | +16.7% | ±3.0 [+13.7, +19.7] |  |
| normal | github+prep | +10.7% | ±3.1 [+7.6, +13.8] |  |
| normal | aggressive | +4.4% | ±1.5 [+2.9, +5.9] |  |
| normal | passive | +16.7% | ±2.3 [+14.4, +19.0] |  |
| normal | sharks | +6.6% | ±2.5 [+4.1, +9.1] |  |
| normal | competent | +7.8% | ±2.7 [+5.1, +10.5] |  |
| fast | gate-weak | +7.8% | ±3.0 [+4.8, +10.8] |  |
| fast | gate-weak+crashed | +11.7% | ±3.1 [+8.6, +14.8] |  |
| fast | gate-strong | +3.7% | ±2.5 [+1.2, +6.2] |  |
| fast | gate-mixed | +9.1% | ±2.8 [+6.3, +11.9] |  |
| fast | rival-strong | +6.9% | ±2.7 [+4.2, +9.6] |  |
| fast | rival-strong+prep | +6.3% | ±2.5 [+3.8, +8.8] |  |
| fast | rival-mid | +14.6% | ±3.2 [+11.4, +17.8] |  |
| fast | rival-real | +5.8% | ±2.7 [+3.1, +8.5] |  |
| fast | llm-bugs | +10.0% | ±2.8 [+7.2, +12.8] |  |
| fast | llm-bugs+prep | +5.9% | ±2.7 [+3.2, +8.6] |  |
| fast | github | +12.0% | ±3.3 [+8.7, +15.3] |  |
| fast | github+prep | +8.5% | ±3.3 [+5.2, +11.8] |  |
| fast | aggressive | +4.9% | ±1.5 [+3.4, +6.4] |  |
| fast | passive | +22.5% | ±2.8 [+19.7, +25.3] |  |
| fast | sharks | +3.9% | ±2.3 [+1.6, +6.2] |  |
| fast | competent | +7.7% | ±2.5 [+5.2, +10.2] |  |

- default normal h2h 4v4 A 0.963x fair
- default fast h2h 4v4 A 0.963x fair
- mean over 32 cells: A-B +10.47% of fair (±0.25)  [14802s]

## run2_strong_8000_9982.txt

| blinds | field | A-B % fair | 95% CI | flag |
|---|---|---|---|---|
| normal | sharks | +5.5% | ±2.0 [+3.5, +7.5] |  |
| normal | competent | +8.6% | ±2.1 [+6.5, +10.7] |  |
| normal | rival-strong+prep | +9.4% | ±2.3 [+7.1, +11.7] |  |
| normal | github+prep | +13.4% | ±2.5 [+10.9, +15.9] |  |
| fast | sharks | +3.0% | ±1.7 [+1.3, +4.7] |  |
| fast | competent | +3.7% | ±2.0 [+1.7, +5.7] |  |
| fast | rival-strong+prep | +0.9% | ±2.0 [-1.1, +2.9] |  |
| fast | github+prep | +10.8% | ±2.6 [+8.2, +13.4] |  |

- default normal h2h 4v4 A 0.975x fair
- default fast h2h 4v4 A 0.966x fair
- mean over 8 cells: A-B +6.90% of fair (±0.39)  [12217s]

## run3_ante10_2000_9983.txt

| blinds | field | A-B % fair | 95% CI | flag |
|---|---|---|---|---|
| normal | rival-real | +12.9% | ±4.6 [+8.3, +17.5] |  |
| normal | github | +11.8% | ±4.2 [+7.6, +16.0] |  |
| normal | gate-mixed | +11.3% | ±4.2 [+7.1, +15.5] |  |
| normal | rival-strong+prep | +3.8% | ±4.8 [-1.0, +8.6] |  |

- default normal h2h 4v4 A 0.963x fair
- mean over 4 cells: A-B +9.97% of fair (±1.13)  [1457s]

## run3_ante5_2000_9983.txt

| blinds | field | A-B % fair | 95% CI | flag |
|---|---|---|---|---|
| normal | rival-real | +15.0% | ±5.0 [+10.0, +20.0] |  |
| normal | github | +17.9% | ±4.5 [+13.4, +22.4] |  |
| normal | gate-mixed | +12.7% | ±4.1 [+8.6, +16.8] |  |
| normal | rival-strong+prep | +5.5% | ±4.9 [+0.6, +10.4] |  |

- default normal h2h 4v4 A 0.953x fair
- mean over 4 cells: A-B +12.77% of fair (±1.18)  [1179s]

## run3_hpl15_2000_9983.txt

| blinds | field | A-B % fair | 95% CI | flag |
|---|---|---|---|---|
| kit | rival-real | +8.5% | ±4.7 [+3.8, +13.2] |  |
| kit | github | +17.5% | ±5.4 [+12.1, +22.9] |  |
| kit | gate-mixed | +13.6% | ±4.5 [+9.1, +18.1] |  |
| kit | rival-strong+prep | +2.7% | ±4.2 [-1.5, +6.9] |  |

- default kit h2h 4v4 A 0.966x fair
- mean over 4 cells: A-B +10.58% of fair (±1.20)  [339s]

## run3_hpl40_2000_9983.txt

| blinds | field | A-B % fair | 95% CI | flag |
|---|---|---|---|---|
| kit | rival-real | +9.6% | ±4.2 [+5.4, +13.8] |  |
| kit | github | +11.6% | ±3.8 [+7.8, +15.4] |  |
| kit | gate-mixed | +13.2% | ±3.7 [+9.5, +16.9] |  |
| kit | rival-strong+prep | +4.9% | ±4.2 [+0.7, +9.1] |  |

- default kit h2h 4v4 A 0.976x fair
- mean over 4 cells: A-B +9.85% of fair (±1.01)  [1100s]

## run3_stack1000_2000_9983.txt

| blinds | field | A-B % fair | 95% CI | flag |
|---|---|---|---|---|
| normal | rival-real | +9.5% | ±4.8 [+4.7, +14.3] |  |
| normal | github | +14.3% | ±5.1 [+9.2, +19.4] |  |
| normal | gate-mixed | +10.9% | ±4.6 [+6.3, +15.5] |  |
| normal | rival-strong+prep | +4.0% | ±4.4 [-0.4, +8.4] |  |

- default normal h2h 4v4 A 0.966x fair
- mean over 4 cells: A-B +9.68% of fair (±1.21)  [1027s]

## run3_stack4000_2000_9983.txt

| blinds | field | A-B % fair | 95% CI | flag |
|---|---|---|---|---|
| normal | rival-real | +12.8% | ±4.4 [+8.4, +17.2] |  |
| normal | github | +10.1% | ±4.1 [+6.0, +14.2] |  |
| normal | gate-mixed | +11.0% | ±3.7 [+7.3, +14.7] |  |
| normal | rival-strong+prep | +2.3% | ±4.5 [-2.2, +6.8] |  |

- default normal h2h 4v4 A 0.982x fair
- mean over 4 cells: A-B +9.06% of fair (±1.06)  [717s]

## Notes
- No cell has a 95% CI entirely below 0 in any run.
- The h2h 4v4 cells show 0.953 to 0.982x fair in every run (rough se ~0.006 at 5000 SNGs, ~0.01 at 2000), so cand loses to a table half-filled with ev_t4 copies.
- The weakest cells: fast/rival-strong+prep at 8000 SNGs gives +0.9% [-1.1, +2.9]. rival-strong+prep is also the weakest field in every run3 condition (+2.3 to +5.5%).
- run3 conditions used schedule normal (25 hands/level). The hpl runs replace it ("kit"). All runs used payouts default (fair 34.75).
- Workers: run1 3, run2 2, run3 2-3; 5 in total.

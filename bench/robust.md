# Benchmark: prep:params/nlhe_robust.json

Bundle `nlhe.nlb`, 600 SNGs per cell, 2026-10-30 01:57. Score = points per table / fair share (1.00 = break-even; mirror should be ~1.00).

## prep:params/nlhe_robust.json

| points | blinds | zoo | passive | aggressive | competent | exploiter | 3 of us + zoo | mirror (8 of us) |
|---|---|---|---|---|---|---|---|---|
| default | normal | 2.03 ±0.04 | 2.21 ±0.04 | 2.09 ±0.02 | 1.75 ±0.04 | 0.92 ±0.04 | 1.52 ±0.02 | 1.00 ±0.02 |
| default | fast | 1.76 ±0.04 | 1.75 ±0.05 | 1.90 ±0.03 | 1.43 ±0.04 | 0.94 ±0.04 | 1.40 ±0.02 | 1.00 ±0.02 |
| top-heavy | normal | 2.75 ±0.07 | 3.28 ±0.08 | 2.55 ±0.06 | 2.31 ±0.08 | 0.93 ±0.06 | 1.73 ±0.04 | 1.00 ±0.03 |
| top-heavy | fast | 2.26 ±0.08 | 2.49 ±0.09 | 2.16 ±0.06 | 1.61 ±0.07 | 0.94 ±0.06 | 1.57 ±0.04 | 1.00 ±0.03 |
| linear | normal | 1.67 ±0.02 | 1.67 ±0.02 | 1.74 ±0.01 | 1.48 ±0.02 | 0.89 ±0.03 | 1.39 ±0.01 | 1.00 ±0.01 |
| linear | fast | 1.49 ±0.02 | 1.40 ±0.03 | 1.67 ±0.01 | 1.29 ±0.02 | 0.89 ±0.03 | 1.29 ±0.01 | 1.00 ±0.01 |
| top-3 | normal | 2.61 ±0.06 | 2.91 ±0.07 | 2.73 ±0.04 | 2.16 ±0.07 | 0.93 ±0.06 | 1.73 ±0.04 | 1.00 ±0.03 |
| top-3 | fast | 2.08 ±0.07 | 2.19 ±0.08 | 2.42 ±0.04 | 1.53 ±0.07 | 0.95 ±0.06 | 1.49 ±0.04 | 1.00 ±0.03 |

Worst non-mirror cell: **0.89x** (linear, normal, exploiter). Errors: 0.

# Benchmark: prep:params/nlhe_final.json

Bundle `nlhe.nlb`, 800 SNGs per cell, 2026-10-30 02:16. Score = points per table / fair share (1.00 = break-even; mirror should be ~1.00).

## prep:params/nlhe_final.json

| points | blinds | zoo | passive | aggressive | competent | exploiter | 3 of us + zoo | mirror (8 of us) |
|---|---|---|---|---|---|---|---|---|
| default | normal | 2.01 ±0.03 | 2.18 ±0.04 | 2.07 ±0.02 | 1.74 ±0.04 | 1.05 ±0.04 | 1.51 ±0.02 | 1.00 ±0.02 |
| default | fast | 1.67 ±0.03 | 1.74 ±0.04 | 1.88 ±0.02 | 1.42 ±0.03 | 1.03 ±0.03 | 1.37 ±0.02 | 1.00 ±0.02 |
| top-heavy | normal | 2.70 ±0.06 | 3.19 ±0.07 | 2.53 ±0.05 | 2.24 ±0.07 | 1.25 ±0.06 | 1.73 ±0.03 | 1.00 ±0.03 |
| top-heavy | fast | 2.07 ±0.07 | 2.39 ±0.07 | 2.12 ±0.05 | 1.61 ±0.06 | 1.12 ±0.06 | 1.52 ±0.03 | 1.00 ±0.03 |
| linear | normal | 1.65 ±0.02 | 1.66 ±0.02 | 1.74 ±0.01 | 1.46 ±0.02 | 1.01 ±0.02 | 1.39 ±0.01 | 1.00 ±0.01 |
| linear | fast | 1.46 ±0.02 | 1.39 ±0.02 | 1.66 ±0.01 | 1.28 ±0.02 | 0.97 ±0.02 | 1.30 ±0.01 | 1.00 ±0.01 |
| top-3 | normal | 2.60 ±0.05 | 2.87 ±0.06 | 2.71 ±0.04 | 2.15 ±0.06 | 1.23 ±0.06 | 1.71 ±0.03 | 1.00 ±0.02 |
| top-3 | fast | 1.91 ±0.06 | 2.16 ±0.07 | 2.37 ±0.04 | 1.54 ±0.06 | 1.12 ±0.05 | 1.46 ±0.03 | 1.00 ±0.03 |

Worst non-mirror cell: **0.97x** (linear, fast, exploiter). Errors: 0.

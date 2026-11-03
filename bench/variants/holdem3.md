# Benchmark: prep:params/holdem3.json

Bundle `holdem3.nlb`, 400 SNGs per cell, 2026-10-30 02:22. Score = points per table / fair share (1.00 = break-even; mirror should be ~1.00).

## prep:params/holdem3.json

| points | blinds | zoo | passive | aggressive | competent | exploiter | 3 of us + zoo | mirror (8 of us) |
|---|---|---|---|---|---|---|---|---|
| default | normal | 1.90 ±0.04 | 2.11 ±0.05 | 2.04 ±0.03 | 1.64 ±0.05 | 1.17 ±0.05 | 1.47 ±0.03 | 1.00 ±0.02 |
| default | fast | 1.55 ±0.05 | 1.70 ±0.06 | 1.88 ±0.03 | 1.33 ±0.05 | 1.01 ±0.05 | 1.35 ±0.03 | 1.00 ±0.02 |
| top-heavy | normal | 2.46 ±0.09 | 3.04 ±0.10 | 2.42 ±0.07 | 2.06 ±0.09 | 1.28 ±0.08 | 1.63 ±0.05 | 1.00 ±0.04 |
| top-heavy | fast | 1.74 ±0.09 | 2.35 ±0.11 | 2.09 ±0.07 | 1.49 ±0.09 | 1.17 ±0.08 | 1.49 ±0.05 | 1.00 ±0.04 |

Worst non-mirror cell: **1.01x** (default, fast, exploiter). Errors: 0.

## prep:params/nlhe_final.json

| points | blinds | zoo | passive | aggressive | competent | exploiter | 3 of us + zoo | mirror (8 of us) |
|---|---|---|---|---|---|---|---|---|
| default | normal | 1.95 ±0.04 | 2.21 ±0.05 | 2.05 ±0.03 | 1.67 ±0.05 | 1.10 ±0.05 | 1.47 ±0.03 | 1.00 ±0.02 |
| default | fast | 1.60 ±0.05 | 1.71 ±0.06 | 1.87 ±0.03 | 1.34 ±0.05 | 0.99 ±0.05 | 1.36 ±0.03 | 1.00 ±0.02 |
| top-heavy | normal | 2.56 ±0.09 | 3.26 ±0.09 | 2.46 ±0.07 | 2.06 ±0.09 | 1.35 ±0.09 | 1.65 ±0.05 | 1.00 ±0.04 |
| top-heavy | fast | 1.88 ±0.09 | 2.42 ±0.11 | 2.14 ±0.07 | 1.58 ±0.09 | 1.19 ±0.08 | 1.54 ±0.05 | 1.00 ±0.04 |

Worst non-mirror cell: **0.99x** (default, fast, exploiter). Errors: 0.

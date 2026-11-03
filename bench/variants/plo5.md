# Benchmark: prep:params/plo5.json

Bundle `plo5.nlb`, 400 SNGs per cell, 2026-10-30 02:25. Score = points per table / fair share (1.00 = break-even; mirror should be ~1.00).

## prep:params/plo5.json

| points | blinds | zoo | passive | aggressive | competent | exploiter | 3 of us + zoo | mirror (8 of us) |
|---|---|---|---|---|---|---|---|---|
| default | normal | 1.84 ±0.05 | 1.93 ±0.06 | 2.04 ±0.03 | 1.43 ±0.05 | 1.16 ±0.05 | 1.43 ±0.03 | 1.00 ±0.02 |
| default | fast | 1.54 ±0.05 | 1.67 ±0.06 | 1.90 ±0.03 | 1.21 ±0.05 | 1.12 ±0.05 | 1.35 ±0.03 | 1.00 ±0.02 |
| top-heavy | normal | 2.32 ±0.09 | 2.76 ±0.11 | 2.45 ±0.07 | 1.64 ±0.09 | 1.29 ±0.09 | 1.60 ±0.05 | 1.00 ±0.04 |
| top-heavy | fast | 1.89 ±0.09 | 2.38 ±0.11 | 2.19 ±0.07 | 1.41 ±0.09 | 1.05 ±0.08 | 1.53 ±0.05 | 1.00 ±0.04 |

Worst non-mirror cell: **1.05x** (top-heavy, fast, exploiter). Errors: 0.

## prep:params/nlhe_final.json

| points | blinds | zoo | passive | aggressive | competent | exploiter | 3 of us + zoo | mirror (8 of us) |
|---|---|---|---|---|---|---|---|---|
| default | normal | 1.86 ±0.04 | 2.05 ±0.06 | 2.03 ±0.03 | 1.62 ±0.05 | 1.10 ±0.05 | 1.42 ±0.03 | 1.00 ±0.02 |
| default | fast | 1.55 ±0.05 | 1.71 ±0.06 | 1.89 ±0.03 | 1.21 ±0.05 | 1.02 ±0.05 | 1.36 ±0.03 | 1.00 ±0.02 |
| top-heavy | normal | 2.41 ±0.09 | 2.95 ±0.10 | 2.45 ±0.07 | 1.93 ±0.09 | 1.22 ±0.08 | 1.60 ±0.05 | 1.00 ±0.04 |
| top-heavy | fast | 1.87 ±0.09 | 2.43 ±0.11 | 2.19 ±0.07 | 1.47 ±0.09 | 1.01 ±0.08 | 1.49 ±0.05 | 1.00 ±0.04 |

Worst non-mirror cell: **1.01x** (top-heavy, fast, exploiter). Errors: 0.

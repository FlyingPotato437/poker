# Benchmark: prep:params/plo4.json

Bundle `plo4.nlb`, 400 SNGs per cell, 2026-10-30 02:24. Score = points per table / fair share (1.00 = break-even; mirror should be ~1.00).

## prep:params/plo4.json

| points | blinds | zoo | passive | aggressive | competent | exploiter | 3 of us + zoo | mirror (8 of us) |
|---|---|---|---|---|---|---|---|---|
| default | normal | 1.82 ±0.05 | 2.08 ±0.05 | 2.08 ±0.03 | 1.54 ±0.05 | 1.09 ±0.05 | 1.46 ±0.03 | 1.00 ±0.02 |
| default | fast | 1.54 ±0.05 | 1.64 ±0.06 | 1.88 ±0.03 | 1.31 ±0.05 | 0.99 ±0.05 | 1.38 ±0.03 | 1.00 ±0.02 |
| top-heavy | normal | 2.29 ±0.09 | 2.96 ±0.10 | 2.52 ±0.07 | 1.83 ±0.09 | 1.13 ±0.08 | 1.69 ±0.05 | 1.00 ±0.04 |
| top-heavy | fast | 1.80 ±0.09 | 2.29 ±0.11 | 2.09 ±0.07 | 1.42 ±0.09 | 1.09 ±0.08 | 1.54 ±0.05 | 1.00 ±0.04 |

Worst non-mirror cell: **0.99x** (default, fast, exploiter). Errors: 0.

## prep:params/nlhe_final.json

| points | blinds | zoo | passive | aggressive | competent | exploiter | 3 of us + zoo | mirror (8 of us) |
|---|---|---|---|---|---|---|---|---|
| default | normal | 1.91 ±0.05 | 2.15 ±0.05 | 2.08 ±0.03 | 1.61 ±0.05 | 1.03 ±0.05 | 1.47 ±0.03 | 1.00 ±0.02 |
| default | fast | 1.60 ±0.05 | 1.74 ±0.06 | 1.88 ±0.03 | 1.33 ±0.05 | 0.93 ±0.05 | 1.37 ±0.03 | 1.00 ±0.02 |
| top-heavy | normal | 2.45 ±0.09 | 3.17 ±0.10 | 2.55 ±0.07 | 1.92 ±0.09 | 1.11 ±0.08 | 1.65 ±0.05 | 1.00 ±0.04 |
| top-heavy | fast | 1.92 ±0.09 | 2.48 ±0.11 | 2.10 ±0.07 | 1.53 ±0.09 | 1.22 ±0.09 | 1.50 ±0.05 | 1.00 ±0.04 |

Worst non-mirror cell: **0.93x** (default, fast, exploiter). Errors: 0.

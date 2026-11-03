# Benchmark: prep:params/royal.json

Bundle `royal.nlb`, 400 SNGs per cell, 2026-10-30 02:12. Score = points per table / fair share (1.00 = break-even; mirror should be ~1.00).

## prep:params/royal.json

| points | blinds | zoo | passive | aggressive | competent | exploiter | 3 of us + zoo | mirror (8 of us) |
|---|---|---|---|---|---|---|---|---|
| default | normal | 1.93 ±0.05 | 2.28 ±0.05 | 2.06 ±0.03 | 1.58 ±0.05 | 1.14 ±0.05 | 1.47 ±0.03 | 1.00 ±0.02 |
| default | fast | 1.46 ±0.05 | 1.81 ±0.06 | 1.81 ±0.03 | 1.30 ±0.05 | 1.14 ±0.05 | 1.34 ±0.03 | 1.00 ±0.02 |
| top-heavy | normal | 2.50 ±0.10 | 3.42 ±0.09 | 2.57 ±0.08 | 1.98 ±0.10 | 1.33 ±0.08 | 1.68 ±0.05 | 1.00 ±0.04 |
| top-heavy | fast | 1.80 ±0.10 | 2.55 ±0.11 | 2.00 ±0.07 | 1.61 ±0.09 | 1.19 ±0.08 | 1.46 ±0.05 | 1.00 ±0.04 |

Worst non-mirror cell: **1.14x** (default, fast, exploiter). Errors: 0.

## prep:params/nlhe_final.json

| points | blinds | zoo | passive | aggressive | competent | exploiter | 3 of us + zoo | mirror (8 of us) |
|---|---|---|---|---|---|---|---|---|
| default | normal | 1.95 ±0.05 | 2.39 ±0.05 | 2.07 ±0.03 | 1.62 ±0.05 | 1.09 ±0.05 | 1.48 ±0.03 | 1.00 ±0.02 |
| default | fast | 1.48 ±0.05 | 1.89 ±0.06 | 1.82 ±0.03 | 1.35 ±0.05 | 1.06 ±0.05 | 1.36 ±0.03 | 1.00 ±0.02 |
| top-heavy | normal | 2.59 ±0.09 | 3.59 ±0.09 | 2.58 ±0.07 | 1.99 ±0.09 | 1.01 ±0.07 | 1.70 ±0.05 | 1.00 ±0.04 |
| top-heavy | fast | 1.74 ±0.09 | 2.69 ±0.11 | 2.07 ±0.07 | 1.58 ±0.09 | 1.14 ±0.08 | 1.50 ±0.05 | 1.00 ±0.04 |

Worst non-mirror cell: **1.01x** (top-heavy, normal, exploiter). Errors: 0.

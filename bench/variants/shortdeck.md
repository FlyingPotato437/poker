# Benchmark: prep:params/shortdeck.json

Bundle `shortdeck.nlb`, 400 SNGs per cell, 2026-10-30 02:23. Score = points per table / fair share (1.00 = break-even; mirror should be ~1.00).

## prep:params/shortdeck.json

| points | blinds | zoo | passive | aggressive | competent | exploiter | 3 of us + zoo | mirror (8 of us) |
|---|---|---|---|---|---|---|---|---|
| default | normal | 1.91 ±0.05 | 2.14 ±0.05 | 2.05 ±0.03 | 1.66 ±0.05 | 1.14 ±0.05 | 1.44 ±0.03 | 1.00 ±0.02 |
| default | fast | 1.54 ±0.05 | 1.80 ±0.06 | 1.84 ±0.03 | 1.34 ±0.05 | 1.06 ±0.05 | 1.31 ±0.03 | 1.00 ±0.02 |
| top-heavy | normal | 2.48 ±0.09 | 3.15 ±0.10 | 2.46 ±0.07 | 2.06 ±0.10 | 1.15 ±0.08 | 1.67 ±0.05 | 1.00 ±0.04 |
| top-heavy | fast | 1.89 ±0.09 | 2.53 ±0.11 | 2.10 ±0.07 | 1.39 ±0.09 | 1.07 ±0.08 | 1.50 ±0.05 | 1.00 ±0.04 |

Worst non-mirror cell: **1.06x** (default, fast, exploiter). Errors: 0.

## prep:params/nlhe_final.json

| points | blinds | zoo | passive | aggressive | competent | exploiter | 3 of us + zoo | mirror (8 of us) |
|---|---|---|---|---|---|---|---|---|
| default | normal | 1.87 ±0.05 | 2.30 ±0.05 | 2.00 ±0.03 | 1.62 ±0.05 | 1.05 ±0.05 | 1.46 ±0.03 | 1.00 ±0.02 |
| default | fast | 1.56 ±0.05 | 1.87 ±0.06 | 1.81 ±0.03 | 1.37 ±0.05 | 0.94 ±0.04 | 1.32 ±0.03 | 1.00 ±0.02 |
| top-heavy | normal | 2.45 ±0.09 | 3.31 ±0.09 | 2.34 ±0.07 | 2.03 ±0.10 | 1.16 ±0.08 | 1.66 ±0.05 | 1.00 ±0.04 |
| top-heavy | fast | 1.87 ±0.09 | 2.69 ±0.11 | 1.96 ±0.07 | 1.59 ±0.09 | 1.04 ±0.08 | 1.48 ±0.05 | 1.00 ±0.04 |

Worst non-mirror cell: **0.94x** (default, fast, exploiter). Errors: 0.

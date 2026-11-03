# Benchmark: prep:params/plo4.json

Bundle `plo4.nlb`, 400 SNGs per cell, 2026-10-30 03:03. Score = points per table / fair share (1.00 = break-even; mirror should be ~1.00).

## prep:params/plo4.json

| points | blinds | zoo | passive | aggressive | competent | exploiter | 3 of us + zoo | mirror (8 of us) |
|---|---|---|---|---|---|---|---|---|
| default | normal | 1.88 ±0.05 | 1.99 ±0.06 | 2.08 ±0.03 | 1.56 ±0.05 | 0.95 ±0.05 | 1.46 ±0.03 | 1.00 ±0.02 |
| default | fast | 1.59 ±0.05 | 1.62 ±0.06 | 1.93 ±0.03 | 1.37 ±0.05 | 0.94 ±0.05 | 1.36 ±0.03 | 1.00 ±0.02 |
| top-heavy | normal | 2.38 ±0.09 | 2.80 ±0.10 | 2.51 ±0.07 | 1.98 ±0.09 | 0.98 ±0.08 | 1.65 ±0.05 | 1.00 ±0.04 |
| top-heavy | fast | 1.86 ±0.09 | 2.23 ±0.11 | 2.21 ±0.07 | 1.57 ±0.09 | 1.04 ±0.08 | 1.54 ±0.05 | 1.00 ±0.04 |

Worst non-mirror cell: **0.94x** (default, fast, exploiter). Errors: 0.

## prep:params/nlhe_final.json

| points | blinds | zoo | passive | aggressive | competent | exploiter | 3 of us + zoo | mirror (8 of us) |
|---|---|---|---|---|---|---|---|---|
| default | normal | 1.93 ±0.05 | 2.11 ±0.05 | 2.07 ±0.03 | 1.65 ±0.05 | 0.91 ±0.05 | 1.49 ±0.03 | 1.00 ±0.02 |
| default | fast | 1.56 ±0.05 | 1.75 ±0.06 | 1.92 ±0.03 | 1.34 ±0.05 | 0.98 ±0.05 | 1.32 ±0.03 | 1.00 ±0.02 |
| top-heavy | normal | 2.55 ±0.09 | 3.07 ±0.10 | 2.51 ±0.07 | 2.11 ±0.10 | 0.93 ±0.07 | 1.69 ±0.05 | 1.00 ±0.04 |
| top-heavy | fast | 1.90 ±0.09 | 2.43 ±0.11 | 2.21 ±0.07 | 1.61 ±0.09 | 1.02 ±0.08 | 1.47 ±0.05 | 1.00 ±0.04 |

Worst non-mirror cell: **0.91x** (default, normal, exploiter). Errors: 0.

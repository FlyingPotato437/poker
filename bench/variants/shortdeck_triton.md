# Benchmark: prep:params/shortdeck_triton.json

Bundle `shortdeck_triton.nlb`, 400 SNGs per cell, 2026-10-30 02:23. Score = points per table / fair share (1.00 = break-even; mirror should be ~1.00).

## prep:params/shortdeck_triton.json

| points | blinds | zoo | passive | aggressive | competent | exploiter | 3 of us + zoo | mirror (8 of us) |
|---|---|---|---|---|---|---|---|---|
| default | normal | 1.91 ±0.04 | 2.12 ±0.05 | 2.03 ±0.03 | 1.60 ±0.05 | 1.07 ±0.05 | 1.44 ±0.03 | 1.00 ±0.02 |
| default | fast | 1.53 ±0.05 | 1.72 ±0.06 | 1.83 ±0.03 | 1.31 ±0.05 | 1.03 ±0.05 | 1.31 ±0.03 | 1.00 ±0.02 |
| top-heavy | normal | 2.44 ±0.09 | 3.06 ±0.10 | 2.44 ±0.07 | 2.12 ±0.09 | 1.32 ±0.09 | 1.63 ±0.05 | 1.00 ±0.04 |
| top-heavy | fast | 1.78 ±0.09 | 2.48 ±0.11 | 2.07 ±0.07 | 1.52 ±0.09 | 1.13 ±0.08 | 1.44 ±0.05 | 1.00 ±0.04 |

Worst non-mirror cell: **1.03x** (default, fast, exploiter). Errors: 0.

## prep:params/nlhe_final.json

| points | blinds | zoo | passive | aggressive | competent | exploiter | 3 of us + zoo | mirror (8 of us) |
|---|---|---|---|---|---|---|---|---|
| default | normal | 2.00 ±0.04 | 2.26 ±0.05 | 2.05 ±0.03 | 1.58 ±0.05 | 1.02 ±0.05 | 1.48 ±0.03 | 1.00 ±0.02 |
| default | fast | 1.62 ±0.05 | 1.82 ±0.06 | 1.83 ±0.03 | 1.33 ±0.05 | 1.04 ±0.05 | 1.31 ±0.03 | 1.00 ±0.02 |
| top-heavy | normal | 2.59 ±0.09 | 3.35 ±0.09 | 2.47 ±0.07 | 1.93 ±0.09 | 1.06 ±0.08 | 1.65 ±0.05 | 1.00 ±0.04 |
| top-heavy | fast | 1.94 ±0.09 | 2.55 ±0.11 | 2.05 ±0.07 | 1.50 ±0.09 | 1.03 ±0.08 | 1.46 ±0.05 | 1.00 ±0.04 |

Worst non-mirror cell: **1.02x** (default, normal, exploiter). Errors: 0.

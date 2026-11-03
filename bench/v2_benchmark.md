# Benchmark: prep:params/ev_t4.json

Bundle `nlhe_rng.nlb`, 1500 SNGs per cell, 2026-10-30 19:05. Score = points per table / fair share (1.00 = break-even).

## prep:params/ev_t4.json

| points | blinds | zoo | passive | aggressive | competent | 3 of us + zoo |
|---|---|---|---|---|---|---|
| default | normal | 2.04 ±0.02 | 2.21 ±0.03 | 2.08 ±0.02 | 1.75 ±0.03 | 1.52 ±0.01 |
| default | fast | 1.69 ±0.03 | 1.73 ±0.03 | 1.90 ±0.02 | 1.40 ±0.03 | 1.38 ±0.01 |
| top-heavy | normal | 2.77 ±0.05 | 3.24 ±0.05 | 2.58 ±0.04 | 2.20 ±0.05 | 1.76 ±0.03 |
| top-heavy | fast | 2.12 ±0.05 | 2.42 ±0.06 | 2.25 ±0.04 | 1.63 ±0.05 | 1.56 ±0.03 |

Worst cell: **1.38x** (default, fast, 3 of us + zoo). Errors: 0.

## Seat fairness (8 copies of the candidate, fixed seats)

Per-seat score; the mean over seats is 1.00 by construction. A seat beyond ~3 se would point at a simulator bias.

- prep:params/ev_t4.json default/normal: seats 1.01 1.01 1.00 1.01 0.99 0.98 1.01 0.99; worst seat 5 at -0.7 se
- prep:params/ev_t4.json default/fast: seats 1.01 1.00 0.97 1.01 0.96 1.00 1.03 1.03; worst seat 4 at -1.8 se
- prep:params/ev_t4.json top-heavy/normal: seats 1.03 0.99 1.00 0.99 1.02 0.97 1.01 0.99; worst seat 5 at -0.8 se
- prep:params/ev_t4.json top-heavy/fast: seats 1.01 1.00 1.00 1.03 0.94 0.98 1.00 1.05; worst seat 4 at -1.6 se

# rel_k middle ground: not adopted

Exploitability: 1 attacker + 7 copies, 600 SNGs, seed 8802, attacker's x-fair (se about ±0.04).
A/B: each variant minus cand_nlhe, 1000 SNGs, normal+fast, 8 fields, seed 9993 (32 cells).

| variant | arms_br2 | whale_br | A/B mean (±se) | worst cell |
|---|---:|---:|---:|---|
| cand (rel_k=1) | 1.55 | 1.46 | – | – |
| rel_k=2 | 1.60 | 1.41 | −0.19 ± 0.56 | normal rival-strong −5.4% (−2.6 se) |
| rel_k=3 | 1.48 | 1.35 | −0.62 ± 0.67 | normal rival-strong −6.3% (−2.3 se) |
| rel_k=4 | 1.43 | 1.31 | −1.89 ± 0.71 | normal rival-strong −6.6% (−2.3 se); top-heavy normal rival-strong −12.2% |

Raising rel_k lowers what a tuned attacker takes, but every variant loses significantly on
rival-strong, and the cost grows with rel_k. Keep rel_k = 1.

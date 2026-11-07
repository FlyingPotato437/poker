# Fallback v2: the full engine from notes (Nov 6)

Goal: a no-pre-written-code spec (`FALLBACK_SPEC.md`) whose from-scratch rebuild plays like the
final bot (`params/cand3_nlhe.json`, frozen rc2). All A/Bs: 1500 paired SNGs per cell, fields
github / llm-bugs / rival-real / gate-mixed, normal + fast blinds, vs `prep:params/cand3_nlhe.json`.

| bot | A − final bot, % of fair | x fair ratio | file |
|---|---|---|---|
| old spec bot (LITE) | −32.5 ±2.5 (normal only, 600) | 84% | decomp_spec.txt |
| PrepBot engine on spec formulas, grid curve | −4.32 ±0.99 | 97.6% | confirm_hyb_all_9811.txt |
| ... continuous curve (spec v1 reference) | −4.26 ±0.98 | 97.7% | confirm_hyb_allc_9811.txt |
| ... curve with the bundle's exact e1 (diagnostic) | −1.97 ±0.96 | 98.9% | diag_hyb_allt.txt |
| ... v2 e1 formula + refit curve (spec v2 reference) | −3.05 ±0.97 | 98.3% | confirm_hyb_allc2_9811.txt |
| **blind rebuild of spec v1** (sonnet, spec only) | −3.51 ±0.99 | 98.0% | blind1_vs_cand3_9821.txt |
| **blind rebuild of spec v2** (sonnet, spec only) | **−2.44 ±0.97** | **98.6%** | blind2_vs_cand3_9821.txt |

Decomposition (600–800 SNGs): preflop pct/eqr fit, push/fold charts and the BF formula cost
~0–1% together; the range-equity curve formula costs ~4% (v1), about half of it from the
rough e1 it starts from. Tuning six settings on top (`tune/`) found nothing beyond noise.

Blind rebuilds (fresh agents that read only the spec + self-tests): sonnet v1 145/145
self-tests in 3.5 min; sonnet v2 297/297; haiku v2 297/297 first run. Decision parity vs the
reference in real games (`scripts/parity_spec.py`, 60 SNGs): 99.95% preflop, 99.9–100% postflop;
the remaining differences are float edge cases in the HU any-two steal rule.

Tools: `scripts/hyb_tables.py` (spec formulas as a Tables stand-in), `scripts/ab_hyb.py`
(A/B with hyb_* and `BLIND_BOT=path` → `blind`), `scripts/parity_spec.py`,
`scripts/selftest_spec.py` (regenerates `selftest.md`; paste it into spec §9),
`scripts/fit_curve2.py`, `scripts/e1_feats.py`. Coefficients: `curve_th.json` (v1),
`e1_th.json` + `curve2_th.json` (v2).

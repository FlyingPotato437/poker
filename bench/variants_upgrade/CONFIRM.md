# Variant confirms: cand_<preset> vs ev_t3 (Nov 6)

`scripts/ab_test.py --bundle bundles/<preset>_rng.nlb --a prep:params/cand_<preset>.json --b prep:params/ev_t3.json
--payouts default --schedules normal,fast --fields gate-weak,gate-strong,gate-mixed,rival-real,llm-bugs,event --workers 4`.
That gives 12 cells. h2h 4v4 is reported in each run but isn't a gate cell. No sealed fields were used.
Verdict rule: ship cand if mean > 0 and no cell is significantly negative (below −2 se); otherwise ship ev_t3.

| Variant | Run | mean ± se (% of fair) | Worst cell | Verdict |
|---|---|---|---|---|
| plo4 | 1500 SNGs, seed 9942 (confirm) | +8.65% ± 0.82 | fast event −1.4% (−0.48 ± 1.03) | ship `params/cand_plo4.json` |
| shortdeck | 1500 SNGs, seed 9942 (confirm) | +7.31% ± 0.81 | normal gate-strong −0.2% (−0.06 ± 0.94) | ship `params/cand_shortdeck.json` |
| plo5 | 1500 SNGs, seed 9942 (confirm) | +7.61% ± 0.85 | fast event +0.5% (+0.19 ± 1.03) | ship `params/cand_plo5.json` |
| royal | 1500 SNGs, seed 9942 (confirm) | +7.61% ± 0.82 | fast gate-strong −1.4% (−0.49 ± 0.85) | ship `params/cand_royal.json` |
| holdem3 | 800 SNGs, seed 9941 (screen) | +9.75% ± 1.06 | fast event −1.6% (−0.55 ± 1.36) | ship `params/cand_holdem3.json` (screen only) |
| shortdeck_triton | 800 SNGs, seed 9941 (screen) | +8.48% ± 1.11 | normal gate-strong +0.7% (+0.25 ± 1.32) | ship `params/cand_shortdeck_triton.json` (screen only) |

The seed-9942 confirms replicate the seed-9941 screens (+7.6% to +10.2%). No cell in any run is below −0.5 se.
The weakest fields are again gate-strong and fast event, which are near zero. h2h 4v4 has cand at 0.92–0.98x fair
against ev_t3, the same self-play pattern as NLHE.

Raw output is in `<preset>_cand_vs_ev_t3_<seed>.txt`.

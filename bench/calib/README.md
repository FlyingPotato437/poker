# Sample-size-aware exploit rule (Nov 6)

Follow-up to `bench/learning/README.md` section 3. 4 workers throughout, pool_w 0, no sealed fields.

## Fit (`fit_p20.txt`)

`scripts/fit_exploit.py --calib --labels bench/rivals/style_d_r2p0.json --exploit params/cand_nlhe.json
--base params/cand_nlhe.json --min-d -0.5 --sngs 4000 --workers 4` (seed 9701).

- 522k unweighted seat snapshots at 22 hand counts (2..160). Each seat is a prepped copy
  (rival_prep, ev_t3, nlhe_final_legacy; label 0) with probability 0.2, else uniform over the 30
  labelled zoo/rival styles plus the 8 LLM-bug and 12 GitHub designs (label 1).
- Logit = [1, z, z^2]·beta + g(h)·[1, z, z^2]·beta_g, g(h) = 1/(1 + h/20); 30 weights.
- Report on the last 20% of SNGs (by SNG):

| hands | obs share | P_h mean | ECE P_h | ECE per-bucket refit | ECE current P | ECE current λ | P_h prep | P_h exploitable |
|---|---|---|---|---|---|---|---|---|
| 1–10 | .830 | .842 | .016 | .021 | .064 | .657 | .70 | .87 |
| 11–25 | .779 | .781 | .014 | .013 | .045 | .385 | .51 | .86 |
| 26–60 | .736 | .756 | .023 | .018 | .025 | .220 | .39 | .89 |
| 61–100 | .680 | .701 | .027 | .015 | .024 | .122 | .26 | .91 |
| 101+ | .669 | .678 | .022 | .018 | .023 | .086 | .23 | .90 |

P_h is calibrated in every bucket (the interaction form and per-bucket refits are about equal).
The current P is overconfident-low early (ECE .064). Calibrated or not, the early separation stays
weak: prep .70 vs .87 in hands 1–10. Strong rivals (rv_tag, rv_gto, rv_lag) sit at .5–.75.

## A/B vs cand_nlhe (8 fields × normal, fast; default points)

Screens, 800 SNGs, seed 9411:

| variant (exploit block) | mean % fair (±se) | event normal | rs+prep n / f | event+prep n / f |
|---|---|---|---|---|
| pure: λ = P_h, ×0.5 when P_h < 0.5 | +1.17 (0.73) | −7.4 | +3.9 / +2.2 | +1.1 / −1.5 |
| lo50: λ = (P_h − .5)/.5 | +0.97 (0.69) | −7.0 | +3.0 / +2.3 | +0.9 / +1.6 |
| lo65 | +0.50 (0.67) | −0.2 | +1.1 / +0.2 | −2.0 / +0.4 |
| **pureh5: pure × h/(h+5)** | **+1.29 (0.62)** | −5.2 | +2.3 / +1.9 | +2.0 / +1.7 |
| lo50h5 | +0.42 (0.57) | −1.6 | +1.3 / +0.4 | +0.5 / −0.3 |

Confirmation of pureh5, 1500 SNGs, seed 9412 (`ab_pureh5_9412.txt`): **+0.43% ±0.44**. No
significant cell; largest losses event normal −2.3 ±2.4, rival-strong+prep normal −1.2 ±1.6,
event+prep fast −1.2 ±1.6. As with h0 5, most of the screen's +1.3 was the winner's curse.

## Conclusion

The calibrated rule passes the letter of the keep rule (positive mean, no significant losing
cell) and is in `params/cand_calib_nlhe.json` (= `calib_pureh5_nlhe.json`), but its gain is not
significant. Exploiting earlier keeps costing on the event field under normal blinds (all
aggressive variants, both seeds). Cost: about +4 µs p50 per decision.

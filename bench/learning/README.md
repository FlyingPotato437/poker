# Learning while playing: how fast the exploit rule learns a table (Nov 6)

The bot's state resets at every table, and a table lasts at most 200 hands. Each villain gets
λ = P(exploitable | 7 seat stats) · h/(h + h0). This study measures how λ and P develop over
the hands of a table, where the chips come from, and whether a different ramp (h0) helps.

Scripts: `scripts/learning_curve.py`, plus `run.sh`, `run2.sh` and `run3.sh` here. All runs used
4 workers and pool_w 0. No sealed fields were used.

## 1. Learning curve: cand_nlhe vs the same params without the exploit block

File: `lc_cand_vs_noex.txt`. Seed 9990, 300 paired SNGs per field, normal blinds.

Definitions:
- **chips**: big blinds won per hand dealt, using that hand's blinds.
- **Δ**: A − B in bb per table-hand, paired.
- **λ and P**: per live opponent, by the seat's true class:
  - weak: zoo, LLM-bug and GitHub designs;
  - strong: rv_tag, rv_lag, rv_gto, rv_exploit, rv_icm, positional, barrel;
  - prep: our prepped bots.
- **acc**: P > 0.5 compared with the training label (exploitable = not prep).

Pooled over github, llm-bugs, rival-real and rival-strong+prep:

| hands | chips A | Δ bb/hand (±se) | lvl>0 | λ weak | P weak | λ strong | P strong | λ prep | P prep | acc |
|---|---|---|---|---|---|---|---|---|---|---|
| 1–25 | +0.69 | +0.052 (0.033) | 0.85 | 0.33 | 0.79 | 0.27 | 0.64 | 0.18 | 0.46 | 0.81 |
| 26–50 | +0.56 | +0.025 (0.039) | 0.92 | 0.61 | 0.86 | 0.47 | 0.66 | 0.17 | 0.25 | 0.83 |
| 51–100 | +0.40 | +0.026 (0.021) | 0.92 | 0.73 | 0.88 | 0.57 | 0.69 | 0.13 | 0.15 | 0.85 |
| 101–200 | +0.36 | +0.036 (0.010) | 0.96 | 0.78 | 0.87 | 0.63 | 0.71 | 0.13 | 0.15 | 0.85 |

Points gained by the exploit block: +15.7% of fair ±2.9 pooled. By field: github +15.5,
llm-bugs +16.5, rival-real +18.6, rival-strong+prep +12.2.

**Accuracy by field and hand bucket:**

| field | 1–25 | 26–50 | 51–100 | 101–200 |
|---|---|---|---|---|
| github | .96 | .97 | .98 | .97 |
| llm-bugs | .85 | .88 | .88 | .85 |
| rival-real | .75 | .76 | .77 | .79 |
| rival-strong+prep | .69 | .76 | .80 | .83 |

Findings:
- **Separation takes about 50 hands.** Prep bots start at the P of a fresh seat (0.73 at the
  PRIORS) and drop to P 0.25 by hands 26–50 and 0.15 after that. Weak seats reach 0.86–0.88.
- **The strong rivals stay ambiguous** at P 0.64–0.71 for the whole table, and they cause
  most of the classification errors on rival fields.
- **Where the edge comes from:** about 9 extra bb per table, spread over every bucket. Per
  hand, the largest gain is in hands 1–25, at +0.05 bb/hand. The only bucket that is
  significant is hands 101–200, at +0.036 ±0.010.
- **What the points come from:** the points gain (+5.5 points per table) is far larger than
  the chip gain. Most of the value is survival and ICM: fewer and later busts, at the high
  blind levels.

## 2. A/B screens vs cand_nlhe

Settings: 800 SNGs, seed 9995, normal and fast blinds, 14 cells: github, llm-bugs,
rival-real, gate-weak, gate-strong, gate-mixed, rival-strong+prep.

| variant | mean % fair (±se) | rival-strong+prep normal / fast | gate-strong normal / fast |
|---|---|---|---|
| h0 3 | +1.23 (0.65) | −2.3 / +2.0 | −2.8 / +0.3 |
| h0 5 | +1.21 (0.59) | −1.2 / +2.3 | −2.3 / +0.2 |
| h0 8 | +0.43 (0.48) | +0.6 / +0.1 | −2.3 / −0.3 |
| h0 25 | −0.66 (0.45) | −0.5 / −1.5 | −0.9 / −0.6 |
| degen_n 3, degen_fold_n 5 | −0.00 (0.03) | 0 / 0 | 0 / 0 |

**Confirmation, h0 5 at 1500 SNGs, seed 9996:** +0.43% ±0.42. rival-strong+prep is −0.7 ±1.4
(normal) and −1.9 ±1.1 (fast). The screen's +1.2 was mostly the winner's curse. Files:
`ab_*_vs_cand_9995.txt` and `ab_h5_vs_cand_9996.txt`.

**Per-bucket curve, h0 5 vs cand** (`lc_h5_vs_cand.txt`):
- A faster ramp lifts λ prep in hands 1–25 from 0.18 to 0.29, while P prep is still 0.47.
- On rival-strong+prep that costs −0.024 ±0.013 bb/hand in hands 1–25. Points are −0.6% there
  and +1.2% ±1.8 pooled.

## 3. Conclusions

1. **Faster learning helps weak fields and hurts against prepped bots.** In every screen and
   in the confirmation, the faster ramps (h0 3–8) gain on weak and mixed fields. They are
   neutral to negative on rival-strong+prep, and on gate-strong under normal blinds. The ramp
   exploits prepped bots before the classifier has separated them, which takes about 25–50
   hands.
2. **A slower ramp (h0 25) loses** −0.7 ±0.45.
3. **Recommendation:**
   - Keep h0 = 15. h0 = 8 is an acceptable alternative: +0.4, and no loss with prep at the
     table.
   - Don't ship h0 5: +0.43 ±0.42 isn't significant once confirmed, and it leans negative with
     prep present.
   - degen_* changes nothing.
   - The stat prior (PRIOR_WEIGHT 6, PRIORS) isn't exposed in params, so this study didn't
     test it.

**Structural change suggested** (main session, runtime.py and fit_exploit.py; not done here):
the ramp h/(h + h0) is a fixed discount. It is applied on top of a P that is miscalibrated at
small samples: P prep is 0.46 in hands 1–25, while the label is 0. Make P calibrated by sample
size instead:
- **Fit:** in `fit_exploit.py`, add the interaction features z_i·g(h) and z_i²·g(h), with
  g(h) = 1/(1 + h/20). Alternatively, fit separate betas for h ≤ 25, 26–60 and > 60.
- **Weights:** use the snapshots unweighted by hand count, so P(h) is the real posterior at h.
- **Runtime:** set λ = P_h(stats) with h0 → 0. Choose a shrink toward λ_min for P < 0.5, so
  that a seat that looks like a prep bot is never exploited early, while a clear weak seat
  (P_h > 0.85 by hand ~10) is.

That would give the gain from the fast ramp against weak fields without the early cost
against prep bots. Validate it with this script's per-bucket Δ on rival-strong+prep.

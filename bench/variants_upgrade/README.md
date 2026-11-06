# Variant upgrades: cand_<preset> vs ev_t3 (Nov 6)

All non-NLHE presets ship `params/ev_t3.json` today (frozen/rc1 MANIFEST, day.py default).
So every variant candidate is the same file, copied to `params/cand_<preset>.json`:

- `ev_t3` + short-handed opening (`sh_open 1.0`, `sh_open_scale 1.15`, `hu_sb_play 0.8`);
- plus the NLHE exploit block from `cand_nlhe` (logistic beta/mu/sd, `h0 15`, `rel 2`,
  `degen_n 5`, `degen_fold_n 8`). Its `params` are `params/xplo4_exploit.json`, which is
  exactly `ev_t3 + (x_nlhe exploit params - ev_t4)`: the same delta transplant as the NLHE
  build. No variant has its own fitted exploit model (`x_plo4.json` was never fitted). The
  seat-stat classifier is NLHE-fitted and used as is.
- `params/cand_sh_ev_t3.json` (short-handed keys only, no exploit block) is **untested**. It's
  a fallback if the exploit transplant looks wrong.

Gate: `scripts/ab_test.py --bundle bundles/<preset>_rng.nlb --payouts default --schedules
normal,fast --fields gate-weak,gate-strong,gate-mixed,rival-real,llm-bugs`, 3 workers.
The fields are in-process, so there's no deadline and no timing check.

| Variant | Recommended params | 800 SNGs, seed 9941: mean ± se | Worst cell | 1500 SNGs, seed 9942 |
|---|---|---|---|---|
| plo4 | `params/cand_plo4.json` | +8.13% ± 1.20 | fast gate-strong −2.0% (−0.69 ± 1.16) | partial: normal gate-weak +16.3%, gate-strong +1.7% |
| shortdeck | `params/cand_shortdeck.json` | +10.22% ± 1.17 | fast rival-real −0.4% (−0.14 ± 1.21) | not run |
| plo5 | `params/cand_plo5.json` | +8.69% ± 1.25 | normal rival-real +0.4% | not run |
| royal | `params/cand_royal.json` | +7.58% ± 1.22 | fast gate-strong −4.2% (−1.47 ± 1.28) | not run |
| holdem3 | `params/ev_t3.json` (untested; `cand_holdem3.json` plausible) | not run | – | – |
| shortdeck_triton | `params/ev_t3.json` (untested; `cand_shortdeck_triton.json` plausible, shortdeck proxy) | not run | – | – |

No cell lost significantly: the worst is −1.15 se. h2h 4v4 has the candidate at 0.92–0.97x
fair against ev_t3, the same pattern as NLHE (0.96x). It does worse in a table full of its
own kind and is not a gate cell.

The 1500-SNG confirms were cut short. The box load was 500–700 and each cell took about
15 min. To finish them, run with `--sngs 1500 --seed 9942` for plo4, then shortdeck, then
plo5, then royal. Then run the 800-SNG screen on holdem3 and shortdeck_triton.

# Standard play vs cand_nlhe

Measured: cand_nlhe, 400 SNGs vs rival-real (RR) and 400 vs github (GH). Raw stats in
`stats_rival_real.txt` and `stats_github.txt`; scripts in `scripts/`.

Standards: no-ante 8-max opens (pokercoaching.com/preflop-charts: UTG 11%, CO 26%, BTN 40%);
HU Nash at 10bb (HoldemResources: SB pushes 58%, BB calls 37%); MDF pot/(pot+bet), 33% max
fold vs a half-pot bet; GTO Wizard c-bet folds about 37% vs a 1/3-pot bet. 3-bet 6–10% and fold
to 3-bet 45–55% are consensus figures without one exact public source.

Some deviations are deliberate exploits tuned against weak fields; each needs an A/B, not a
blind change toward "standard".

| # | Deviation | Ours | Standard | Controls | Test |
|---|---|---|---|---|---|
| 1 | Check then fold vs a HU bet; no check-raise | folds 95% RR / 84% GH, raises 0% | defend to MDF | `_postflop_ev`, `risk_av` 1.03, `call_ev_margin` 0.084, `rng_bet_scale` 1.56 | `risk_av` 0.5, `call_ev_margin` 0.03, `rng_bet_scale` 1.2, `ev_margin` 0.10 |
| 2 | No 3-bets or flats outside the BB (likely bug) | 0–1% | 6–10% | `_preflop`: `eq**(1+0.6*(n_live-1))` counts players still to act as if already in | count only players with chips in, plus a small param for those behind |
| 3 | Opens too wide at 6–8-handed 100bb | UTG 39%, CO 59%, BTN 80% | 11 / 26 / 40% | `open_base` 0.264, `steal_exploit` 2.03 (uncapped) | `open_base` 0.16, `steal_exploit` 1.0 |
| 4 | Fold to 3-bet | 76–88% (GH 63–65%) | 45–55% | `pre_tighten` | `pre_tighten` 0.6 after 2 and 3 |
| 5 | Over-folding vs single bets | 63–71% vs ~half pot; c-bets 60–89% | ≤ 33% | as 1, `cont_b4` | as 1, `cont_b4` toward −1.5 |
| 6 | Push/fold up to 21bb, no antes | SB jams 64%, BTN 36% at 12–20bb; 99% of 3-bets are jams | push/fold ≲ 12–15bb | `pf_bb` 21.1 | `pf_bb` 14, 12 |
| 7 | OOP and multiway c-bets | 62–68% OOP, 39–48% multiway; ~30% pot+ sized | 30–45% / 25–35% | `ev_margin`, `realize_chk` | `ev_margin` 0.10, `realize_chk` 0.95 |
| 8 | Open size | 2.85bb at every depth | 2.0–2.5bb | `open_bb` | `open_bb` 2.3 |
| 9 | BB 3-bet | 2–4% | 10–14% | `reraise_eq` | `reraise_eq` 0.54 |
| 10 | HU shove calling at ≤12bb | BB calls 14% | Nash 37% | read = table shove rate ×1.5; `pf_call_scale` off after 12 hands | call if chart or read says call |

Near standard: BB defend vs 2–2.6x opens (62–70%), river bluff share (27% vs 20%).
W$SD low at 46% / 40% vs 50–55%.

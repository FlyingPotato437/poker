Standard-play A/B screens vs prep:params/cand_nlhe.json (B), % of fair, mean of cells ± se.
screen.py: same seatings/pairing as scripts/ab_test.py (default payouts, no h2h), B shared across arms.
Run from the repo root: python bench/standard/ab/screen.py OUT SNGS SEED FIELDS SCHEDULES B NAME='{json delta}' ...

s1_mw.txt     pre_mw_behind 0 / 0.25 / 0.5, 600 SNGs, seed 9601, 6 fields x normal,fast
s2_par.txt    one-param screens (open_base, steal_exploit, open_bb, pf_bb, risk_av, call_ev_margin,
              rng_bet_scale, ev_margin, reraise_eq, realize_chk), same setup
s3_greedy.txt combinations on pre_mw_behind 0.25, + event, event+prep
s4_confirm.txt 1500 SNGs, seed 9602, 10 fields x 2 schedules:
              c_mw  (pre_mw_behind 0.25)            -> params/cand_std_nlhe.json     +1.28 ± 0.42
              c_std (pre_mw_behind 0.25, pf_bb 14)  -> params/cand_std_pf_nlhe.json  +1.65 ± 0.48

#!/bin/sh
# Event-field runs (Nov 6): cand_nlhe vs ev_t4 on event, event+prep, then per-archetype x-fair.
# Three workers in all (shared machine).
cd "$(dirname "$0")/../.."
PY=/Users/revanthguda/poker/.venv/bin/python
$PY scripts/ab_test.py --bundle bundles/nlhe_rng.nlb --a prep:params/cand_nlhe.json --b prep:params/ev_t4.json \
  --sngs 1500 --payouts default --schedules normal,fast --fields event,event+prep --seed 9701 --workers 3 \
  > bench/event/ab_cand_vs_ev_t4.txt 2>&1
$PY scripts/style_xfair.py prep:params/cand_nlhe.json prep:params/ev_t4.json \
  ev_codex_tag,ev_ghcp_fastrange,ev_pushfold4,ev_mc_mwbug,ev_strong1,ev_reshover,ev_policybot,ev_cfr_pushfold,ev_gunslinger \
  600 9702 3 > bench/event/xfair_cand_vs_ev_t4.txt 2>&1

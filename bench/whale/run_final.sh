#!/usr/bin/env bash
# Final cells: counter-mode candidate vs cand_nlhe, 1500 SNGs, normal+fast, whale + normal
# fields, on 9931 (tuning seed) then once on 9932; then the whale baselines (cand vs ev_t4 /
# xex2). Usage: run_final.sh <candidate params name>
set -u
cd "$(dirname "$0")/../.."
PY=/Users/revanthguda/poker/.venv/bin/python
C=${1:?candidate}
F=whale1,whale-mirror,whale2,whale-br,gate-weak,gate-strong,gate-mixed,rival-strong,rival-strong+prep,rival-real,llm-bugs
for S in 9931 9932; do
  $PY scripts/ab_test.py --bundle bundles/nlhe_rng.nlb --a prep:params/$C.json --b prep:params/cand_nlhe.json \
      --sngs 1500 --payouts default --schedules normal,fast --seed $S --no-h2h --workers 4 --fields $F \
      > bench/whale/final_${C}_vs_cand_$S.txt 2>&1
  echo "final $C $S done $(date +%T)"
done
for B in ev_t4 xex2_nlhe; do
  $PY scripts/ab_test.py --bundle bundles/nlhe_rng.nlb --a prep:params/cand_nlhe.json --b prep:params/$B.json \
      --sngs 1500 --payouts default --schedules normal,fast --seed 9931 --no-h2h --workers 4 \
      --fields whale1,whale-mirror,whale2,whale-br > bench/whale/base_cand_vs_${B}_9931.txt 2>&1
  echo "base $B done $(date +%T)"
done

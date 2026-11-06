#!/usr/bin/env bash
# Counter-mode screening on seed 9931 (tuning seed): each variant vs cand_nlhe, 600 SNGs,
# normal blinds, whale fields + normal fields. Usage: run_tune9931.sh cw_det cw_safe ...
set -u
cd "$(dirname "$0")/../.."
PY=/Users/revanthguda/poker/.venv/bin/python
for V in "$@"; do
  $PY scripts/ab_test.py --bundle bundles/nlhe_rng.nlb --a prep:params/$V.json --b prep:params/cand_nlhe.json \
      --sngs ${SNGS:-600} --payouts default --schedules ${SCHED:-normal} --seed 9931 --no-h2h --workers 4 \
      --fields ${FIELDS:-whale1,whale-mirror,whale2,whale-br,gate-strong,rival-strong+prep,rival-real,llm-bugs} \
      > bench/whale/screen_${V}_9931.txt 2>&1
  echo "$V done $(date +%T)"
done

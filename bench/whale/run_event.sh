#!/usr/bin/env bash
# After run_final.sh: event-archetype whale tables (added late), 1500 SNGs, normal+fast, 9932.
set -u
cd "$(dirname "$0")/../.."
PY=/Users/revanthguda/poker/.venv/bin/python
until grep -q "base xex2_nlhe done" bench/whale/run_final.log; do sleep 30; done
for AB in "cw_safe cand_nlhe" "cand_nlhe ev_t4"; do
  set -- $AB
  $PY scripts/ab_test.py --bundle bundles/nlhe_rng.nlb --a prep:params/$1.json --b prep:params/$2.json \
      --sngs 1500 --payouts default --schedules normal,fast --seed 9932 --no-h2h --workers 4 \
      --fields whale-event,whale-event-cfr,whale-event-br,event > bench/whale/event_${1}_vs_${2}_9932.txt 2>&1
  echo "event $1 vs $2 done $(date +%T)"
done

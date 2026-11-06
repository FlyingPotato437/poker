#!/usr/bin/env bash
# Baseline at whale tables (seed 9931), 4 workers, run in sequence after the attacker tune.
set -u
cd "$(dirname "$0")/../.."
PY=/Users/revanthguda/poker/.venv/bin/python
while pgrep -f "tune.py.*whale_br.json" > /dev/null; do sleep 20; done
echo "tune done $(date +%T)"
$PY scripts/run_tournament.py --bundle bundles/nlhe_rng.nlb --sngs 1000 --workers 4 --seed 9931 \
    --fixed prep:params/whale_br.json --field prep:params/cand_nlhe.json > bench/whale/whale_br_eval.txt 2>&1
echo "br eval done $(date +%T)"
$PY scripts/whale_flow.py --bundle bundles/nlhe_rng.nlb --a prep:params/cand_nlhe.json --b prep:params/ev_t4.json \
    --fields whale1,whale-mirror,whale2,whale-br --sngs 1500 --seed 9931 --workers 4 \
    --stats bench/whale/stats_9931.jsonl > bench/whale/flow_cand_vs_ev_t4_9931.txt 2>&1
echo "flow done $(date +%T)"
for B in ev_t4 xex2_nlhe; do
  $PY scripts/ab_test.py --bundle bundles/nlhe_rng.nlb --a prep:params/cand_nlhe.json --b prep:params/$B.json \
      --sngs 1500 --payouts default --schedules normal,fast --seed 9931 --no-h2h --workers 4 \
      --fields whale1,whale-mirror,whale2,whale-br > bench/whale/base_cand_vs_${B}_9931.txt 2>&1
  echo "ab $B done $(date +%T)"
done

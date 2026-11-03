#!/usr/bin/env bash
# Population-tune every non-NLHE preset, starting from the NLHE params (transfer).
# Run detached after finish_bundles.sh:  setsid nohup bash scripts/tune_all.sh > params/tune_all.log 2>&1 &
set -u
cd "$(dirname "$0")/.."
PY=.venv/bin/python
INIT=${INIT:-params/nlhe_final.json}
FIELD="tag=2.5,lag=1.2,shover=1.5,nit=1,station=1,maniac=0.8,timeout=1.2,random=0.5,jammer=0.3,bully=0.3,trapper=1,prep=1.5,prep:params/br_vs_nlhe_full.json=1,prep:params/br_vs_nlhe_robust.json=1,prep:params/br_vs_nlhe_robust2.json=1"
for v in shortdeck holdem3 royal plo4 shortdeck_triton plo5; do
  [ -f bundles/$v.nlb ] || { echo "=== skip $v (no bundle)"; continue; }
  echo "=== tune $v start $(date +%T)"
  $PY scripts/tune.py --bundle bundles/$v.nlb --init "$INIT" --field "$FIELD" --self-weight 0.2 \
      --gens 8 --pop 16 --elite 4 --sigma 0.12 --sngs 600 --workers 8 --out params/$v.json > params/tune_$v.log 2>&1
  echo "=== tune $v done $(date +%T): $(tail -2 params/tune_$v.log | head -1)"
  $PY scripts/run_tournament.py --bundle bundles/$v.nlb --sngs 3000 --workers 8 \
      --fixed prep:params/$v.json,prep:$INIT,prep >> params/tune_$v.log 2>&1
  grep -E "^prep" params/tune_$v.log | tail -3
done
echo "=== tune_all done $(date +%T)"

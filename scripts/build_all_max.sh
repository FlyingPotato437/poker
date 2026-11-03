#!/usr/bin/env bash
# Max-accuracy bundles for every preset, one after another on a single GPU.
# Run detached so a dropped SSH session can't kill it:
#   nohup bash scripts/build_all_max.sh > bundles/build_all.log 2>&1 &
set -u
cd "$(dirname "$0")/.."
PY=.venv/bin/python
COMMON="--post-rollouts 64 --val-samples 8000 --epochs 20"

build() {
  local v=$1; shift
  echo "=== $v start $(date +%T)"
  $PY -m gpu.build_tables --variant "$v" --out "bundles/$v.nlb" $COMMON "$@" > "bundles/build_$v.log" 2>&1 \
    && echo "=== $v done $(date +%T): $(grep -E 'MAE' bundles/build_$v.log | tail -1)" \
    || echo "=== $v FAILED $(date +%T), see bundles/build_$v.log"
}

[ -f bundles/nlhe.nlb ] || build nlhe --rows-budget 2e8 --eq-cap 1000000 --chunk 1000000 --post-samples 3000000 --val-rollouts 2000
build shortdeck        --rows-budget 2e8 --eq-cap 1000000 --chunk 1000000 --post-samples 3000000 --val-rollouts 2000
build shortdeck_triton --rows-budget 2e8 --eq-cap 1000000 --chunk 1000000 --post-samples 3000000 --val-rollouts 2000
build royal            --rows-budget 1e8 --eq-cap 1000000 --chunk 1000000 --post-samples 2000000 --val-rollouts 2000
build holdem3          --rows-budget 4e8 --eq-cap 300000  --chunk 500000  --post-samples 2000000 --val-rollouts 1500
build plo4             --rows-budget 4e8 --eq-cap 300000  --chunk 400000  --post-samples 1500000 --val-rollouts 1000
build plo5             --rows-budget 4e8 --eq-cap 300000  --chunk 300000  --post-samples 1000000 --val-rollouts 1000
echo "=== all done $(date +%T)"

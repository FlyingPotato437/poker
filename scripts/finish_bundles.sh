#!/usr/bin/env bash
# After build_all_max.sh: give bundles built before the dual-MLP change both postflop
# models, then add push/fold charts + ICM bubble factors (placeholder points table) to all.
set -u
cd "$(dirname "$0")/.."
PY=.venv/bin/python
PAYOUTS=${PAYOUTS:-100,65,45,30,20,12,6,0}
for v in shortdeck shortdeck_triton; do
  # exits 0 (retrain) only when the bundle lacks the second model
  if [ -f bundles/work_$v/postflop_data.npz ] && $PY -c "import sys; from nolimit.bundle_io import read_bundle_np; sys.exit(int('mlpsmall_w1' in read_bundle_np('bundles/$v.nlb')[1]))"; then
    echo "=== retrain $v $(date +%T)"
    rm -f bundles/work_$v/postflop.npz
    $PY -m gpu.build_tables --variant $v --out bundles/$v.nlb --reuse --skip pushfold --epochs 20 > bundles/retrain_$v.log 2>&1 \
      && grep MAE bundles/retrain_$v.log | tail -2
  fi
done
for f in bundles/nlhe.nlb bundles/shortdeck.nlb bundles/shortdeck_triton.nlb bundles/royal.nlb bundles/holdem3.nlb bundles/plo4.nlb bundles/plo5.nlb; do
  [ -f "$f" ] && $PY -m gpu.pushfold --bundle "$f" --payouts "$PAYOUTS" > /dev/null && echo "=== pushfold+bf $f"
done
echo "=== finish done $(date +%T)"

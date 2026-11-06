#!/bin/sh
# Learning-curve study (bench/learning/README.md). 4 workers throughout.
cd "$(dirname "$0")/../.."
export OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OPENBLAS_NUM_THREADS=1
PY=/Users/revanthguda/poker/.venv/bin/python
F=github,llm-bugs,rival-real,gate-weak,gate-strong,gate-mixed,rival-strong+prep
$PY scripts/learning_curve.py --a prep:params/cand_nlhe.json --b prep:params/lc_noex_nlhe.json \
  --sngs 300 --seed 9990 --workers 4 > bench/learning/lc_cand_vs_noex.txt 2>/dev/null
for c in h8 h5 h25 dg; do
  $PY scripts/ab_test.py --bundle bundles/nlhe_rng.nlb --a prep:params/lc_${c}_nlhe.json --b prep:params/cand_nlhe.json \
    --sngs 800 --payouts default --schedules normal,fast --seed 9995 --fields $F --workers 4 \
    > bench/learning/ab_${c}_vs_cand_9995.txt 2>/dev/null
done
echo SCREENS_DONE

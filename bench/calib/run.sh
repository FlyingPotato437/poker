#!/bin/sh
# Calibrated exploit rule (bench/calib): screens vs cand_nlhe on seed 9411. 4 workers.
cd "$(dirname "$0")/../.."
export OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OPENBLAS_NUM_THREADS=1
PY=/Users/revanthguda/poker/.venv/bin/python
F=event,event+prep,github,llm-bugs,rival-real,rival-strong+prep,gate-strong,gate-mixed
for c in ${@:-lo50 lo65 pure}; do
  $PY scripts/ab_test.py --bundle bundles/nlhe_rng.nlb --a prep:params/calib_${c}_nlhe.json --b prep:params/cand_nlhe.json \
    --sngs 800 --payouts default --schedules normal,fast --seed 9411 --fields $F --workers 4 \
    > bench/calib/ab_${c}_9411.txt 2>/dev/null
done
echo SCREENS_DONE

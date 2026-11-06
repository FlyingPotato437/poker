#!/bin/sh
# Follow-up: h0 3 screen (after run.sh), then per-bucket learning curve of h5 vs cand.
cd "$(dirname "$0")/../.."
export OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OPENBLAS_NUM_THREADS=1
PY=/Users/revanthguda/poker/.venv/bin/python
F=github,llm-bugs,rival-real,gate-weak,gate-strong,gate-mixed,rival-strong+prep
while pgrep -f "bench/learning/run.sh" >/dev/null; do sleep 20; done
$PY scripts/ab_test.py --bundle bundles/nlhe_rng.nlb --a prep:params/lc_h3_nlhe.json --b prep:params/cand_nlhe.json \
  --sngs 800 --payouts default --schedules normal,fast --seed 9995 --fields $F --workers 4 \
  > bench/learning/ab_h3_vs_cand_9995.txt 2>/dev/null
$PY scripts/learning_curve.py --a prep:params/lc_h5_nlhe.json --b prep:params/cand_nlhe.json \
  --sngs 300 --seed 9990 --workers 4 > bench/learning/lc_h5_vs_cand.txt 2>/dev/null
echo RUN2_DONE

#!/bin/sh
# Confirmation of the screen pick (h0 5) at 1500 SNGs, seed 9996, after run2.sh.
cd "$(dirname "$0")/../.."
export OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 OPENBLAS_NUM_THREADS=1
PY=/Users/revanthguda/poker/.venv/bin/python
F=github,llm-bugs,rival-real,gate-weak,gate-strong,gate-mixed,rival-strong+prep
while pgrep -f "bench/learning/run2.sh" >/dev/null; do sleep 20; done
$PY scripts/ab_test.py --bundle bundles/nlhe_rng.nlb --a prep:params/lc_h5_nlhe.json --b prep:params/cand_nlhe.json \
  --sngs 1500 --payouts default --schedules normal,fast --seed 9996 --fields $F --workers 4 \
  > bench/learning/ab_h5_vs_cand_9996.txt 2>/dev/null
echo RUN3_DONE

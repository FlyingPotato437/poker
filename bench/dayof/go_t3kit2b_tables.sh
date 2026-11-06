#!/bin/bash
# go.py background table build for t3kit2b (fast profile)
cd /Users/revanthguda/poker/.claude/worktrees/agent-af59e2c142ba83ca8
export OMP_NUM_THREADS=3 MKL_NUM_THREADS=3 PYTORCH_ENABLE_MPS_FALLBACK=1 PYTHONUNBUFFERED=1 NOLIMIT_DEVICE=cpu
set -e
T0=$(date +%s); el() { echo "[go +$(( ($(date +%s) - T0) / 60 ))m$(( ($(date +%s) - T0) % 60 ))s] $*"; }
el build_tables start
/Users/revanthguda/poker/.venv/bin/python -m gpu.build_tables --variant variants/day_t3kit2.json --out bundles/day/t3kit2b_base.nlb --work bundles/day/work_t3kit2b --skip pushfold --payouts 10,6,4,3,2,1,0,0 --device cpu --laptop --rows-budget 2000000 --eq-cap 20000 --post-samples 60000 --post-rollouts 24 --val-samples 800 --val-rollouts 200 --epochs 10 || { el 'build_tables failed: retry with --chunk 50000 --reuse'; /Users/revanthguda/poker/.venv/bin/python -m gpu.build_tables --variant variants/day_t3kit2.json --out bundles/day/t3kit2b_base.nlb --work bundles/day/work_t3kit2b --skip pushfold --payouts 10,6,4,3,2,1,0,0 --device cpu --laptop --rows-budget 2000000 --eq-cap 20000 --post-samples 60000 --post-rollouts 24 --val-samples 800 --val-rollouts 200 --epochs 10 --chunk 50000 --reuse; }
el build_tables done
/Users/revanthguda/poker/.venv/bin/python scripts/day.py build t3kit2b_v1 --adapter examples/answers/kit2_adapter.py --sngs 20 --workers 3 --bundle bundles/day/t3kit2b_base.nlb --params params/ev_t3.json --points 10,6,4,3,2,1,0,0 --ante-bb 0.0625 --kit-cmd '/Users/revanthguda/poker/.venv/bin/python examples/kit2/simulate.py {bot} --games 10' || el 't3kit2b_v1 build FAILED (keep v0); going on to the range net'
el t3kit2b_v1 step done: if it says 'built and froze', python scripts/day.py submit t3kit2b_v1
/Users/revanthguda/poker/.venv/bin/python -m gpu.range_eq --bundle bundles/day/t3kit2b_base.nlb --out bundles/day/t3kit2b_base_rng.nlb --work bundles/day/work_t3kit2b --device cpu --laptop --samples 8000 --k 16 --val-samples 300 --val-k 64 --epochs 10 || { el 'range_eq failed: retry with --chunk 50000'; /Users/revanthguda/poker/.venv/bin/python -m gpu.range_eq --bundle bundles/day/t3kit2b_base.nlb --out bundles/day/t3kit2b_base_rng.nlb --work bundles/day/work_t3kit2b --device cpu --laptop --samples 8000 --k 16 --val-samples 300 --val-k 64 --epochs 10 --chunk 50000 --reuse; }
el range_eq done
/Users/revanthguda/poker/.venv/bin/python scripts/day.py build t3kit2b_v2 --adapter examples/answers/kit2_adapter.py --sngs 20 --workers 3 --bundle bundles/day/t3kit2b_base_rng.nlb --params params/ev_t3.json --points 10,6,4,3,2,1,0,0 --ante-bb 0.0625 --kit-cmd '/Users/revanthguda/poker/.venv/bin/python examples/kit2/simulate.py {bot} --games 10'
el t3kit2b_v2 built: python scripts/day.py submit t3kit2b_v2
echo GO_TABLES_DONE

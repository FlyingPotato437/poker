#!/bin/bash
# go.py background table build for t4custom (fast profile)
cd /Users/revanthguda/poker/.claude/worktrees/agent-af59e2c142ba83ca8
export OMP_NUM_THREADS=3 MKL_NUM_THREADS=3 PYTORCH_ENABLE_MPS_FALLBACK=1 PYTHONUNBUFFERED=1 NOLIMIT_DEVICE=cpu
set -e
T0=$(date +%s); el() { echo "[go +$(( ($(date +%s) - T0) / 60 ))m$(( ($(date +%s) - T0) % 60 ))s] $*"; }
el build_tables start
/Users/revanthguda/poker/.venv/bin/python -m gpu.build_tables --variant variants/day_t4custom.json --out bundles/day/t4custom_base.nlb --work bundles/day/work_t4custom --skip pushfold --payouts 100,65,45,30,20,12,6,0 --device cpu --laptop --rows-budget 2000000 --eq-cap 20000 --post-samples 60000 --post-rollouts 24 --val-samples 800 --val-rollouts 200 --epochs 10 || { el 'build_tables failed: retry with --chunk 50000 --reuse'; /Users/revanthguda/poker/.venv/bin/python -m gpu.build_tables --variant variants/day_t4custom.json --out bundles/day/t4custom_base.nlb --work bundles/day/work_t4custom --skip pushfold --payouts 100,65,45,30,20,12,6,0 --device cpu --laptop --rows-budget 2000000 --eq-cap 20000 --post-samples 60000 --post-rollouts 24 --val-samples 800 --val-rollouts 200 --epochs 10 --chunk 50000 --reuse; }
el build_tables done
/Users/revanthguda/poker/.venv/bin/python -m gpu.range_eq --bundle bundles/day/t4custom_base.nlb --out bundles/day/t4custom_base_rng.nlb --work bundles/day/work_t4custom --device cpu --laptop --samples 20000 --k 24 --val-samples 300 --val-k 64 --epochs 10 || { el 'range_eq failed: retry with --chunk 50000'; /Users/revanthguda/poker/.venv/bin/python -m gpu.range_eq --bundle bundles/day/t4custom_base.nlb --out bundles/day/t4custom_base_rng.nlb --work bundles/day/work_t4custom --device cpu --laptop --samples 20000 --k 24 --val-samples 300 --val-k 64 --epochs 10 --chunk 50000 --reuse; }
el range_eq done
/Users/revanthguda/poker/.venv/bin/python scripts/day.py build t4custom_v1 --adapter examples/adapter_mock_solution.py --sngs 20 --workers 3 --bundle bundles/day/t4custom_base_rng.nlb --params params/ev_t4.json --points 100,65,45,30,20,12,6,0 --ante-bb 0.0 --kit-cmd '/Users/revanthguda/poker/.venv/bin/python examples/mock_kit.py {bot} 5'
el t4custom_v1 built: python scripts/day.py submit t4custom_v1
echo GO_TABLES_DONE

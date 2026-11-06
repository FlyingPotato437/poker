#!/bin/bash
# quick-build (no range net) vs heuristic v0, custom 7+ variant
cd /Users/revanthguda/poker/.claude/worktrees/agent-af59e2c142ba83ca8
P=/Users/revanthguda/poker/.venv/bin/python
export OMP_NUM_THREADS=2
t0=$(date +%s)
$P -m gpu.pushfold --bundle bundles/day/t4custom_base.nlb --payouts 100,65,45,30,20,12,6,0 --out build/t4custom_q_pf.nlb --workers 2 > /dev/null
echo "pushfold $(( $(date +%s) - t0 ))s"
$P scripts/ab_test.py --bundle build/t4custom_q_pf.nlb --keep-bundle --a prep:params/ev_t4.json --b heur:params/nlhe_final_legacy.json --sngs 400 --workers 2 --points 100,65,45,30,20,12,6,0 --fields zoo --hands-per-level 25 --seed 7101
echo "total $(( $(date +%s) - t0 ))s"

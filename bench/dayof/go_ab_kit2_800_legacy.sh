#!/bin/bash
# kit2 (Tahoe) under kit rules: day-built table bots (fast profile, CPU, loaded machine) vs the heuristic v0.
# v1 = bundle without range net, v2 = with range net; both push/fold re-solved by day.py for 10,6,4,3,2,1,0,0 @ 0.0625 bb ante.
cd "$(dirname "$0")/../.."
P=${PY:-.venv/bin/python}
export OMP_NUM_THREADS=3
RULES="--points 10,6,4,3,2,1,0,0 --schedule 10/20,15/30,25/50,40/80,60/120,100/200,150/300,250/500,400/800,600/1200 --hands-per-level 15 --stack 1500 --ante 5 --max-hands 200"
$P scripts/ab_test.py --bundle bundles/day/t3kit2b_v1.nlb --keep-bundle --a prep:params/nlhe_final_legacy.json --b heur:params/nlhe_final_legacy.json --sngs 800 --workers 3 --fields zoo,passive,aggressive --seed 7301 $RULES
$P scripts/ab_test.py --bundle bundles/day/t3kit2b_v2.nlb --keep-bundle --a prep:params/nlhe_final_legacy.json --b heur:params/nlhe_final_legacy.json --sngs 800 --workers 3 --fields zoo,passive,aggressive --seed 7301 $RULES

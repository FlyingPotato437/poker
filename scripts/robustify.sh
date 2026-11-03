#!/usr/bin/env bash
# Population training for one variant. Each round: train a best-response attacker against
# the current params, then retune our params against the zoo, the exploit probes and every
# attacker so far. A last attacker measures what exploitability is left.
#   scripts/robustify.sh bundles/day.nlb params/day [ROUNDS] [extra tune/tournament flags]
#   scripts/robustify.sh bundles/plo4.nlb params/plo4_rb 2 --payouts 100,65,45,30,20,12,6,0
# Robustness does not transfer between variants: nlhe_final is +1.5% exploitable on NLHE but
# +4.0% on PLO4. Laptop cost per round ~15-20 min (PLO), ~10 min (NLHE-size).
# GENS/POP/SNGS/EVAL env vars shrink the run (e.g. GENS=5 SNGS=300 for a ~half-time round).
set -u
cd "$(dirname "$0")/.."
PY=.venv/bin/python
BUNDLE=${1:?usage: robustify.sh bundle out_prefix [rounds] [flags]}
PRE=${2:?usage: robustify.sh bundle out_prefix [rounds] [flags]}
ROUNDS=${3:-2}
shift $(( $# < 3 ? $# : 3 ))
INIT=${INIT:-params/nlhe_final.json}
GENS=${GENS:-10}; POP=${POP:-16}; SNGS=${SNGS:-600}; EVAL=${EVAL:-3000}   # smaller = faster, noisier
FIELD="tag=2.5,lag=1.2,shover=1.5,nit=1,station=1,maniac=0.8,timeout=1.2,random=0.5,jammer=0.3,bully=0.3,trapper=1,prep=1.5"
for f in params/br_vs_nlhe_full.json params/br_vs_nlhe_robust.json params/br_vs_nlhe_robust2.json; do
  [ -f "$f" ] && FIELD="$FIELD,prep:$f=0.5"
done

attack() {  # attack <params> <out> [flags]: train an attacker, score it 1 vs 7 copies of <params>
  local target=$1 out=$2 log=${2%.json}.log
  shift 2
  $PY scripts/tune.py --bundle "$BUNDLE" --field "prep:$target" --self-weight 0 --gens "$GENS" --pop "$POP" --elite 4 \
      --sigma 0.25 --sngs "$SNGS" "$@" --out "$out" > "$log" 2>&1 || return 1
  $PY scripts/run_tournament.py --bundle "$BUNDLE" --sngs "$EVAL" --fixed "prep:$out" --field "prep:$target" "$@" \
      >> "$log" 2>&1 || return 1
  local pts total
  pts=$(grep -E "^prep:$(basename "${out%.json}") " "$log" | awk '{print $3}')
  total=$(grep -oE "total points per table [0-9.]+" "$log" | awk '{print $5}')
  awk -v p="$pts" -v t="$total" -v a="$(basename "$out")" -v b="$(basename "$target")" \
      'BEGIN { f = t / 8; printf "attacker %s vs %s: %.2f pts/table, fair %.2f, edge %+.1f%%\n", a, b, p, f, 100 * (p / f - 1) }'
}

CUR=$INIT
for r in $(seq 1 "$ROUNDS"); do
  echo "=== round $r start $(date +%T)"
  attack "$CUR" "${PRE}_br$r.json" "$@" || { echo "attacker failed, see ${PRE}_br$r.log"; exit 1; }
  FIELD="$FIELD,prep:${PRE}_br$r.json=1"
  $PY scripts/tune.py --bundle "$BUNDLE" --init "$CUR" --field "$FIELD" --self-weight 0.2 --gens "$GENS" --pop "$POP" \
      --elite 4 --sigma 0.12 --sngs "$SNGS" "$@" --out "${PRE}_r$r.json" > "${PRE}_r$r.log" 2>&1 \
      || { echo "tune failed, see ${PRE}_r$r.log"; exit 1; }
  CUR=${PRE}_r$r.json
  echo "=== round $r done $(date +%T): $CUR"
done
attack "$CUR" "${PRE}_br_final.json" "$@" || exit 1
echo "=== robustify done $(date +%T). Next: benchmark $CUR against $INIT before submitting it."

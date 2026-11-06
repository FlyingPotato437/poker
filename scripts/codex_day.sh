#!/usr/bin/env bash
# Day-of Codex driver. Prompts live in CODEX_PROMPTS.md ("## N." + a ```prompt block); Codex
# reads AGENTS.md by itself.
#
#   scripts/codex_day.sh --kit ~/Downloads/starter_kit          # interactive Codex, prompt 1 preloaded
#   scripts/codex_day.sh --kit DIR 2                            # interactive, prompt 2 preloaded
#   scripts/codex_day.sh --kit DIR exec 2                       # non-interactive: run prompt 2, log, exit (exec 3 = host build)
#   scripts/codex_day.sh --kit DIR auto                         # unattended: 1 rules, 2 adapter (Codex), 3 go.py build
#                                                               # (on the host, GPU visible; Codex fixes a failure, prompt 3b),
#                                                               # 4 submit locally (Codex). Then upload dist/SUBMIT/<file>.
#   scripts/codex_day.sh --kit DIR auto 1 2 3                   # only these steps
#   scripts/codex_day.sh build [TAG]                            # go.py on the host, no Codex (default tag: first free day, day2, ...)
#   scripts/codex_day.sh exec 6 --set CHANGE="points are now 12,8,5,3,2,1,0,0"
#   scripts/codex_day.sh exec 7 --set SYMPTOM="folds every hand"
#   scripts/codex_day.sh exec 9 --set RESULTS="T1: 41.2 pts/table, fair 26"
#   scripts/codex_day.sh show 3                                 # print prompt 3 (to paste)
#   scripts/codex_day.sh list
#
# Logs: bench/codex/logs/<time>_step<N>.log (full transcript) and .last.txt (Codex's answer).
# Extra codex flags: CODEX_ARGS="-m <model>" scripts/codex_day.sh ...
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CODEX="${CODEX:-$(command -v codex || echo "$HOME/.local/bin/codex")}"
PROMPTS="$ROOT/CODEX_PROMPTS.md"
LOGDIR="$ROOT/bench/codex/logs"
KIT="${KIT:-}"
declare -a SETS=()

die() { echo "codex_day: $*" >&2; exit 1; }

prompt() {   # prompt N -> text of the ```prompt block under "## N."
  local text
  text="$(awk -v n="$1" '
    $0 ~ "^## "n"\\. " {sec=1; next}
    sec && /^## / {exit}
    sec && /^```prompt/ {inb=1; next}
    sec && inb && /^```/ {exit}
    sec && inb {print}' "$PROMPTS")"
  [ -n "$text" ] || die "no prompt $1 in CODEX_PROMPTS.md"
  if [[ "$text" == *"{KIT}"* ]]; then
    [ -n "$KIT" ] || die "prompt $1 needs --kit <starter kit dir>"
    text="${text//\{KIT\}/$KIT}"
  fi
  local kv k v
  for kv in "${SETS[@]+"${SETS[@]}"}"; do
    k="${kv%%=*}"; v="${kv#*=}"
    text="${text//\{$k\}/$v}"
  done
  for k in CHANGE SYMPTOM RESULTS LOG; do
    [[ "$text" != *"{$k}"* ]] || die "prompt $1 needs --set $k=\"...\""
  done
  printf '%s' "$text"
}

run_exec() {   # run_exec N: one non-interactive Codex turn, timed and logged
  local n="$1" text ts log t0 rc
  text="$(prompt "$n")"
  mkdir -p "$LOGDIR"
  ts="$(date +%H%M%S)"
  log="$LOGDIR/${ts}_step${n}.log"
  echo "=== step $n ($(date +%H:%M:%S)) -> $log"
  t0=$(date +%s)
  set +e
  # shellcheck disable=SC2086
  "$CODEX" exec --sandbox workspace-write --skip-git-repo-check -C "$ROOT" ${CODEX_ARGS:-} \
    -o "$LOGDIR/${ts}_step${n}.last.txt" "$text" < /dev/null 2>&1 | tee "$log"
  rc=${PIPESTATUS[0]}
  set -e
  echo "=== step $n done in $(( $(date +%s) - t0 )) s (exit $rc). Answer: $LOGDIR/${ts}_step${n}.last.txt"
  return "$rc"
}

gate() {   # after an auto step: stop if its deliverable isn't there
  local py="$ROOT/.venv/bin/python"
  case "$1" in
    1) "$py" "$ROOT/scripts/go.py" "$ROOT/variants/day_announce.json" --check > /dev/null \
         || die "step 1: go.py --check still reports errors; fix variants/day_announce.json (prompt 1 again)" ;;
    2) [ -f "$ROOT/my_adapter.py" ] && ! grep -q 'raise NotImplementedError("map the starter kit' "$ROOT/my_adapter.py" \
         || die "step 2: my_adapter.py missing or unfilled" ;;
    3) ls "$ROOT"/dist/day/*.check.json > /dev/null 2>&1 || die "step 3: no tag was built (see the step 3 log)" ;;
    4) "$py" "$ROOT/scripts/day.py" status | grep -q matches || die "step 4: day.py status does not show a matching submit" ;;
  esac
}

args=()
while [ $# -gt 0 ]; do
  case "$1" in
    --kit) KIT="$(cd "$2" && pwd)" || die "no kit dir $2"; shift 2 ;;
    --set) SETS+=("$2"); shift 2 ;;
    -h|--help) sed -n 2,17p "$0"; exit 0 ;;
    *) args+=("$1"); shift ;;
  esac
done
set -- "${args[@]+"${args[@]}"}"
[ -x "$CODEX" ] || die "codex not found (set CODEX=/path/to/codex)"
[ -f "$PROMPTS" ] || die "missing $PROMPTS"
cd "$ROOT"

free_tag() {   # first of day, day2, day3, ... whose <tag>_v0 / <tag>_v1 are not frozen yet
  local t=day i=1
  while [ -e "$ROOT/frozen/${t}_v0" ] || [ -e "$ROOT/frozen/${t}_v1" ] || [ -e "$ROOT/frozen/${t}_v2" ]; do i=$((i + 1)); t="day$i"; done
  echo "$t"
}

direct_build() {   # go.py on the host (not in Codex's sandbox, which hides the GPU); Codex fixes failures
  local py="$ROOT/.venv/bin/python" tag="${1:-$(free_tag)}" log t0
  mkdir -p "$LOGDIR"
  log="$LOGDIR/$(date +%H%M%S)_build_${tag}.log"
  t0=$(date +%s)
  echo "=== build: go.py --tag $tag on the host -> $log"
  set +e
  "$py" "$ROOT/scripts/go.py" "$ROOT/variants/day_announce.json" --adapter my_adapter.py --tag "$tag" 2>&1 | tee "$log"
  local rc=${PIPESTATUS[0]}
  set -e
  echo "=== build done in $(( $(date +%s) - t0 )) s (exit $rc)"
  LAST_BUILD_LOG="$log"
  return "$rc"
}

build_or_fix() {   # auto step 3: host build; on failure Codex fixes the adapter/JSON, then one rebuild
  direct_build && return 0
  echo "=== build failed: asking Codex to fix it (prompt 3b)"
  SETS+=("LOG=$LAST_BUILD_LOG")
  run_exec 3b || true
  direct_build || die "build failed twice: read $LAST_BUILD_LOG"
}

case "${1:-1}" in
  list) grep -E '^## [0-9]+[a-z]?\. ' "$PROMPTS" ;;
  build) direct_build ${2:+"$2"} ;;
  show) prompt "${2:?show N}"; echo ;;
  exec)
    if [ "${2:?exec N}" = 3 ] && [ "${CODEX_BUILD:-host}" = host ]; then
      build_or_fix        # go.py on the host so a new variant's table build gets the GPU (CODEX_BUILD=codex: Codex runs it)
    else
      run_exec "$2"
    fi ;;
  auto)
    shift
    steps=("$@"); [ ${#steps[@]} -gt 0 ] || steps=(1 2 3 4)
    T0=$(date +%s)
    for n in "${steps[@]}"; do
      if [ "$n" = 3 ] && [ "${CODEX_BUILD:-host}" = host ]; then
        build_or_fix        # go.py runs on the host so a new variant's table build gets the GPU
      else
        run_exec "$n" || die "step $n: codex exited non-zero"
      fi
      gate "$n"
    done
    echo "=== auto: steps ${steps[*]} done in $(( $(date +%s) - T0 )) s"
    "$ROOT/.venv/bin/python" "$ROOT/scripts/day.py" status || true ;;
  [0-9]*)
    # interactive: the human watches and approves anything outside the workspace
    # shellcheck disable=SC2086
    exec "$CODEX" --sandbox workspace-write --ask-for-approval on-request -C "$ROOT" ${CODEX_ARGS:-} "$(prompt "$1")" ;;
  *) die "unknown command $1 (list | show N | exec N | auto [N..] | build [TAG] | N)" ;;
esac

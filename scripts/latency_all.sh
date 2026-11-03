#!/usr/bin/env bash
# Decision latency for every bundle, numpy on and off, gc frozen. Run on an idle machine:
# anything else using the CPU shows up as >1 ms decisions.
#   scripts/latency_all.sh [params.json] > bench/latency.txt
set -u
cd "$(dirname "$0")/.."
P=${1:-params/ev_t3.json}
for v in nlhe shortdeck shortdeck_triton royal holdem3 plo4 plo5; do
  B="bundles/${v}_rng.nlb"
  [ -f "$B" ] || B="bundles/$v.nlb"
  [ -f "$B" ] || continue
  for mode in numpy --no-numpy; do
    flag=$([ "$mode" = numpy ] || echo --no-numpy)
    echo "## $v $mode ($B)"
    .venv/bin/python scripts/bench_latency.py --bundle "$B" --params "$P" --sngs 60 --gc freeze $flag | tail -n 3
  done
done

#!/usr/bin/env bash
# Show pipeline status on the GPU box, copy finished bundles + tuned params back,
# then fuzz and package every preset locally.
#   scripts/pull_from_gpu.sh ubuntu@216.81.200.237 30996
set -u
HOST=${1:?usage: pull_from_gpu.sh user@host [port]}
PORT=${2:-22}
KEY=${KEY:-$HOME/.ssh/thunder_ed25519}
SSH="ssh -o IdentityAgent=none -o IdentitiesOnly=yes -i $KEY -p $PORT"
cd "$(dirname "$0")/.."

echo "--- remote status"
$SSH "$HOST" 'cd ~/nolimit-prep && tail -n 3 bundles/build_all.log; tail -n 2 bundles/finish.log 2>/dev/null; grep "===" params/tune_all.log 2>/dev/null | tail -n 4'

echo "--- pulling"
rsync -az -e "$SSH" --include '*.nlb' --exclude '*' "$HOST:~/nolimit-prep/bundles/" bundles/
# Local NLHE params and attackers are authoritative; take only the per-variant tunes.
rsync -az -e "$SSH" --exclude 'nlhe*' --exclude 'br_*' "$HOST:~/nolimit-prep/params/" params/
ls -la bundles/*.nlb params/*.json

echo "--- fuzz + package"
.venv/bin/python scripts/fuzz.py --games 60 --cases 5000 || exit 1
for v in shortdeck shortdeck_triton royal holdem3 plo4 plo5; do
  [ -f "bundles/$v.nlb" ] || continue
  # Quick per-variant tunes lost to nlhe_final on independent fields; only robustify.sh output beats it.
  P=params/${v}_robust.json; [ -f "$P" ] || P=params/nlhe_final.json
  .venv/bin/python scripts/package_bot.py --bundle "bundles/$v.nlb" --params "$P" --out "dist/${v}_bot.py" | tail -n 1
done
.venv/bin/python scripts/package_bot.py --bundle bundles/nlhe.nlb --params params/nlhe_final.json --out dist/nlhe_bot.py | tail -n 1
echo "--- done. Stop the instance in the Thunder console when finished."

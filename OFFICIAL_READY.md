# Official interface preparation — November 6, 2026

**Pre-kit candidates, not submission-certified bots.** The signed-in Getting
started page still says the starter kit and uploads open when the variant is
announced. The generic interface documentation is already public. The SDK,
engine, pinned requirements, RULES.md and variant-specific actions are not yet
downloadable from that page.

Source: https://pokerbot.sequoiacap.com/tournament/competitions/5f8be52b-8038-4c43-a0fa-971abcacec1b/start

## What is prepared

- `nolimit/official_adapter.py`: explicit, versioned, bounded JSON memory; table
  identity check; fresh core every decision; event-delta history through folded
  hands; defensive reset for corrupt/truncated memory; deterministic retry RNG;
  offered-action checks and exact raise bounds. Model weights are shared, but
  hand-dependent prediction caches are recreated for each decision.
- `nolimit/official_payouts.py`: reads each table's actual payouts. Offline ICM
  rank-probability differences support arbitrary nonincreasing payout vectors.
  Push/fold charts are used only when their payout preferences and ante ratio
  match. Mismatched charts fall back to the existing heuristic; they are never
  silently treated as valid.
- `scripts/official.py`: extracts runtime, parameters and equity models from the
  hash-verified frozen rc2 files; rebuilds default push/fold charts; creates a
  reproducible zip with a small root `agent.py`, separate runtime and model files;
  checks 50 MB upload, 200 MB unpacked, 1 MB agent.py, archive paths and imports.
- `scripts/official_rehearsal.py`: exercises packaged Agent calls with fresh
  instances, returned memory, eight seats, 20 hands per blind level, 250-hand cap,
  and three payout schedules. Compares every observed history and cumulative
  opponent statistic with the simulator's independent reference.
  Royal uses seven seats because its 20-card deck cannot deal eight two-card
  hands plus a five-card board. It is not an eight-seat-compatible preset.
- `scripts/day.py prepare` selects this workflow. Historical `build`, `submit`
  and `rollback` require an explicit `--legacy-research` flag.

Frozen rc1/rc2 files are unchanged. Rebuilt payouts change strategic behavior;
these candidates have not earned a tournament-strength or improved-score claim.

## Payout limitations

Default payouts are 50/30/20/0/0/0/0/0. Live `state.config.payouts` takes priority.
The rank basis is exact ICM at the grid's hypothetical stacks, but preserves the
old strategy's approximation: opponents other than the hero and selected villain
share equal stacks; shares use nearest-grid lookup, with risk interpolation.
This is not an exact multiway tournament solver. New payout shapes disable
unmatched push/fold charts until rebuilt offline.

The production decision allowance is normally 1 ms plus a 100 ms table bank.
Upload validation has **zero bank**. Rehearsal timing includes our adapter and
serialization, but not official worker transport or sandbox overhead.

## When the kit drops

1. Download it through the tournament portal. Read actual `AGENTS.md`, `RULES.md`,
   `README.md`, protocol types and `requirements.txt`. Install in a fresh virtualenv
   on the team box. Follow kit instructions if they differ from this checklist.
2. Match the announced variant's complete rules to a prepared preset: deck,
   hole-card count/use, hand ranking, board streets, and betting/action semantics.
   Hole-card count alone is not enough. Add new variant logic where needed.
3. Verify the small SDK boundary: where `Action` is exported, actual variant ID,
   `state.blinds` fields, event kinds/amounts, seat IDs/statuses, and legal raise
   kind/min/max. These names are based on published docs, not installed SDK code.
4. Build a new candidate directory. Supply the actual variant ID explicitly:

   ```sh
   .venv/bin/python scripts/day.py prepare nlhe \
     --out build/official/event-v1 --variant-id ACTUAL_ID \
     --points 50,30,20,0,0,0,0,0
   ```

   An unrecognized variant or extra phase uses a legal check/fold/automatic
   fallback, not the known-game strategy. That is crash protection, not competitive
   support for an unknown game. Ante changes require `official.py build --ante-bb`.

5. Run the official static tools:

   ```sh
   .venv/bin/python scripts/official.py kit-check build/official/event-v1 \
     --kit /home/ubuntu/work/starter-kit
   ```

6. Run eight-seat official simulations, then the actual no-bank upload-equivalent
   harness. Check legality, failure counts, memory, p99/max latency and first
   decisions after import/fork. Default `poker-agent play` has a 100 ms bank and
   cannot certify no-bank acceptance by itself. Verify event/history parity with
   the real engine, including antes, all-ins and hands skipped after folding.
7. Upload only the checked zip; inspect the validation report and active-bot
   badge. Portal Format and Getting started pages differ about automatic
   activation, so the visible active status is authoritative.

## Commands before release

From a fresh clone, create a Python 3.12 environment and install `numpy` and
`pytest`. The preparation and chart-rebuilding commands below do not need a GPU
or PyTorch. The released starter kit will specify the production dependencies.
Frozen rc2 sources are included; generated `build/` files are intentionally not
tracked. Recreate them before running the package checks:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install numpy pytest
.venv/bin/python scripts/official.py basis
.venv/bin/python scripts/day.py prepare nlhe --out build/official/v2/nlhe
```

Repeat `prepare` with `plo4`, `plo5`, `shortdeck`, `shortdeck_triton`, `holdem3`
or `royal` and a matching output directory as needed. Each build refuses to
overwrite an existing candidate. Recorded rehearsals and their limits are in
`bench/official_prekit_20261106/`.

```sh
.venv/bin/python -m pytest tests/test_official_adapter.py tests/test_official_payouts.py tests/test_official_package.py -q
.venv/bin/python scripts/official.py check build/official/v2/nlhe.zip
.venv/bin/python scripts/official_rehearsal.py build/official/v2/nlhe --tables 24
.venv/bin/python scripts/freeze.py --tag rc1 --verify
.venv/bin/python scripts/freeze.py --tag rc2 --verify
```

Prepared presets are generated under `build/official/v2/`; each zip has a neighboring
manifest with source hashes, model rules, file hashes and missing official checks.
Never upload the whole repository or starter-kit directory.

# Day-of playbook

**Bay Area Regional, Fri Nov 6**, Sequoia HQ, 2800 Sand Hill Road, Suite 101, Menlo Park.
Team: Srikanth + Revanth. Doors 5:00 PM, **kickoff 6:00 PM sharp**. Confirm seats by
**Mon Nov 2, 11:59 PM PT** (draft reply with our rules questions: `organizer_reply.md`).

| Time (approx.) | What happens |
|---|---|
| 6:00 | Variant and starter kit revealed; 60-minute build starts |
| every 10 min during the build | Unscored practice round against the other teams' current bots |
| ~7:00 | T1: they freeze a copy of whatever is submitted at the start of the round |
| every 20 min after T1 | T2–T6 (T6 ~8:40) |

Later rounds carry more weight (the rules weight T1–T6 by 1–6, so **T4–T6 are 71% of the
score**). The real compute window is about 2 h 40 min (6:00 to the T6 freeze), not 60
minutes. What counts is what's submitted at each freeze, so never be without a working bot,
and get v0 in before the first practice round so the practice rounds test the adapter.

### Who does what

Two laptops, two jobs, so the table build never waits on the adapter (or the reverse):

| Srikanth: kit + submissions | Revanth: tables + tuning |
|---|---|
| Read the kit: Agent interface, card format, blind schedule, points table | Write `variants/day.json` from the announcement; `variant_stats.py` sanity check |
| Map `to_obs` / `to_kit_action` in `adapter_template.py`; test in the kit simulator | `build_tables --laptop`, then `gpu.range_eq --laptop`, then `gpu.pushfold` with the real points table |
| Submit v0 (preset bundle + `ev_t3`/`hyb_t1_g8` params) before the first practice round | Tune on the real bundle with the real schedule and points |
| Package, smoke-test, submit each new bot; owns "what is submitted" | Run the A/B gate (`ab_test.py`) on each candidate before it goes to Srikanth |
| Watch practice/scored results, report what the field looks like | Shift the zoo mix to match, retune between rounds |

Only the submitter submits. Pass bundles/params between laptops on a USB stick or AirDrop
(no network dependency).

## Before the event

- [ ] **Reply to the acceptance email by Mon Nov 2, 11:59 PM PT** (`organizer_reply.md`):
  confirms both seats and asks the open rules questions (pre-written code, numpy, file
  format, what the 1 ms covers, practice-round logs, bot lifetime, two submitters).
- [ ] **Set up Revanth's laptop** the same way: copy the repo with `bundles/`, `params/`,
  `dist/` (rsync or a USB stick), `uv sync`, then **with Wi-Fi off** run
  `.venv/bin/python -m pytest -q` and one `gpu.build_tables --quick` to check torch works
  offline (MPS on Apple silicon; CPU elsewhere is ~5–10x slower, so use `--quick`/preset
  bundles there).
- [ ] On the GPU box, build max-accuracy bundles for every preset (each one is a fallback
  for a "close" variant). Run detached so a dropped SSH session can't kill it:
  ```bash
  setsid nohup bash scripts/build_all_max.sh > bundles/build_all.log 2>&1 < /dev/null &
  ```
  Measured on a Thunder Compute RTX A6000 ($0.35/hr): NLHE at max settings in 10.8 min
  (1M rollouts per hand class, 9M postflop samples), ~14x faster than an M3 Pro laptop.
  Copy bundles back with `rsync` and run `python -m gpu.pushfold` and tuning on whichever
  machine has more CPU cores.
- [ ] Tune each preset (many-core CPU box), starting the next preset from the last one's params:
  ```bash
  .venv/bin/python scripts/tune.py --bundle bundles/nlhe.nlb --gens 20 --pop 32 --sngs 3000 --out params/nlhe.json
  ```
- [ ] Time the full build for one preset on the exact GPU you'll use on the day. That
  number sets the day-of schedule below.
- [ ] **Run `REHEARSAL.md` (timed 60 min, Wi-Fi off, both of us)** on the unseen kit
  `examples/kit2/` (new variant, antes, points change mid-build, rollback drill). Then the
  adapter drill on `examples/mock_kit.py`. Target: adapter written and tested in under 10
  minutes, v0 submitted by T+12.
- [ ] Laptop has the repo, `.venv`, and packaged fallbacks in `dist/`, and works offline.
- [ ] **Quit other apps on the day.** On Oct 30 this laptop had 18.6 of 19.5 GB swap in use;
  under that pressure one PLO5 latency run showed 23 decisions over 1 ms that a rerun did
  not reproduce (the code path was identical; it was the OS). Tuning and laptop builds also
  slow down when the machine is swapping.

## Build phase (T = announcement)

**Everything on the day runs on the laptop, offline.** No remote GPU, no `pip install`:
the `.venv` (numpy + torch with MPS) and the prebuilt bundles in `bundles/` are already on
disk. The submitted bot is one stdlib-only file with its tables embedded.

**One command per step: `scripts/day.py`.** `build <tag>` re-solves push/fold for the real
points (and antes), packages, checks the file in a clean interpreter (memory, import time,
latency with and without numpy, illegal actions), runs the kit simulator (`--kit-cmd`) and
freezes it. `submit <tag>` puts it in `dist/SUBMIT/`, `rollback` restores the previous one
in one step, and `status` shows what is live. Rule changes that are not presets:
`VARIANTS.md`. The commands below are what `day.py` runs, for when something needs doing by
hand.

**T+0–10: submit something before the first practice round.**
- [ ] Read the variant, the kit's Agent interface, the blind schedule and the points table.
- [ ] **Variant is a preset?** Skip the build. `dist/<preset>_bot.py` already exists (v2 EV
  engine, `bundles/<preset>_rng.nlb` + `params/ev_t4.json` for NLHE, `params/ev_t3.json` for
  the rest); only the adapter is missing. Below, `<P>` means that params file.
  Re-solve push/fold for the real points table (~15 s), write the adapter, package:
  ```bash
  .venv/bin/python -m gpu.pushfold --bundle bundles/<preset>_rng.nlb --payouts <points 1st..8th>
  ```
  ```bash
  .venv/bin/python scripts/package_bot.py --bundle bundles/<preset>_rng.nlb --params <P> --adapter my_adapter.py --out dist/day_v0.py
  ```
  If anything about v2 misbehaves in the kit, `dist/fallback/` has the Oct 30 rules-engine
  bots (old runtime, `nlhe_final` params): same adapter, package with
  `--bundle bundles/<preset>.nlb --params params/nlhe_final_legacy.json`.
- [ ] **New variant?** Write `variants/day.json`, check the ranking order, start the laptop
  build (Revanth; runs while the adapter gets written; NLHE-size ~5 min, Omaha-size longer):
  ```bash
  .venv/bin/python scripts/variant_stats.py --variant variants/day.json
  ```
  ```bash
  .venv/bin/python -m gpu.build_tables --variant variants/day.json --laptop --payouts <points 1st..8th> --out bundles/day.nlb
  ```
  Meanwhile submit v0 = heuristic tables for the exact rules (rules engine, rules-engine
  params; `--heuristic` accepts the JSON since Oct 31):
  ```bash
  .venv/bin/python scripts/day.py build v0 --heuristic variants/day.json --adapter my_adapter.py --kit-cmd "<kit simulator> {bot}"
  ```
- [ ] Before submitting anything: test it in the **kit's own simulator**. If the kit lets you
  build its state from ours, run a decision-parity check like `examples/mock_kit.py`: the
  packaged bot must make the same decision as the bot fed our `Obs` on every decision.

**T+10–40: real tables (Revanth), adapter hardening (Srikanth).**
- [ ] When `bundles/day.nlb` lands, add the range net (the EV engine needs it). Measured
  Oct 31 on this laptop (M3 Pro, MPS, other jobs running) for a 3-hole, exactly-2 variant:
  `build_tables --laptop` 6.0 min, `range_eq --laptop` 8.0 min, so v1 is about T+20 if the
  build starts at T+5. PLO4/PLO5-size is still unmeasured and will be slower:
  ```bash
  .venv/bin/python -m gpu.range_eq --bundle bundles/day.nlb --laptop --out bundles/day_rng.nlb
  ```
  Submit v1 = `day_rng.nlb` + `<P>` as soon as it passes the smoke test (`<P>` =
  `params/ev_t4.json` for a hold'em-like variant, `params/ev_t3.json` otherwise: ev_t4's
  preflop was tuned on NLHE and measured +6.2% there, +0.4% on PLO4, +1.9% on shortdeck).
- [ ] Put the kit's blind schedule and points table into every tune and A/B run
  (`--schedule 10/20,15/30,... --payouts ...`). If the schedule isn't known yet, tune with
  `--mix-hands-per-level 25,10` so params can't overfit one blind speed (that's how
  `ev_t3` fixed the fast-blind losses of the earlier tune).
- [ ] Tune from `<P>` against the population field:
  ```bash
  .venv/bin/python scripts/tune.py --bundle bundles/day_rng.nlb --init <P> --field "tag=2.5,lag=1.2,shover=1.5,nit=1,station=1,maniac=0.8,timeout=1.2,random=0.5,jammer=0.3,bully=0.3,trapper=1,prep:params/nlhe_final_legacy.json=1.5,prep:params/br_vs_nlhe_full_legacy.json=0.5,prep:params/br_vs_nlhe_robust_legacy.json=0.5,prep:params/br_vs_nlhe_robust2_legacy.json=0.5" --self-weight 0.2 --gens 6 --pop 24 --elite 6 --sigma 0.08 --sngs 1000 --payouts ... --schedule ... --out params/day.json
  ```
- [ ] **A/B gate** (Revanth): a candidate replaces the submitted bot only if the paired test
  is positive over the cells, not just in one:
  ```bash
  .venv/bin/python scripts/ab_test.py --bundle bundles/day_rng.nlb --a prep:params/day.json --b prep:<P> --sngs 500 --payouts default --schedules normal
  ```
  (Edit `PAYOUTS["default"]` / `SCHEDULES` in benchmark.py to the kit's values first.)
- [ ] Skip extra robustness rounds unless results show someone exploiting us. Measured Oct
  30: one hardening round cut a strong attacker's gain from 23% to 18% but cost 2.9% ±0.9
  against the normal fields.
- [ ] Bench latency (no numpy), package, smoke-test, kit simulator, submit. The packaged
  bot picks big or small models itself at import (timed on their machine), and a 0.6 ms
  deadline guard caps slow decisions. If the kit's simulator shows latency spikes with
  numpy, rebuild with `--pure-python`:
  ```bash
  .venv/bin/python scripts/bench_latency.py --bundle bundles/day_rng.nlb --params params/day.json --no-numpy --gc freeze
  ```
  ```bash
  .venv/bin/python scripts/package_bot.py --bundle bundles/day_rng.nlb --params params/day.json --adapter my_adapter.py --out dist/day_v2.py
  ```

**T+40–60:** longer tune runs; same A/B gate. Then a crash/latency check with the real
points table and schedule:
```bash
.venv/bin/python scripts/fuzz.py --bundles bundles/day_rng.nlb --games 60 --cases 5000
```

## T1–T6 (20 minutes apart)

- [ ] After each result: if the field looks passive, raise `shover`/`nit`/`timeout`
  weights in the zoo mix; if it looks wild, raise `maniac`/`lag`/`station`. Retune, then
  the A/B gate. In the rc1 final check (README), v2's lead over the old bot is mostly
  against strong fields (+17 to +29%). Against weak bots it is only +2 to +10%, and −3% on
  PLO4, so a field that looks weak is the case to retune for.
- [ ] Freeze what you submit, so you always know which bytes are in play:
  `.venv/bin/python scripts/freeze.py --tag t1 --files dist/day_v1.py` (once per
  submission; it refuses to overwrite a tag). A quick host-style check of a new file against
  the frozen previous one (both packaged with the template adapter):
  `.venv/bin/python scripts/final_check.py --variant day --a dist/day_v2.py --b frozen/t1/day_v1.py --sngs 150`.
- [ ] Submit before each freeze. Later tournaments count more, so **never submit an
  untested package late**. Always run the smoke test and the kit simulator first.
- [ ] Don't share the variant publicly before the event ends (rule 6.4).

## If something breaks

| Symptom | Fallback |
|---|---|
| A submitted bot misbehaves in a practice round | `python scripts/day.py rollback` first (one step, sha-checked), then investigate |
| Memory limit turns out to be RAM, not file size | Measured peak on Linux: NLHE 58 MB, PLO4 75, PLO5 209 (no numpy: 45 / 60 / 197). `--pure-python` saves ~13 MB; PLO5-size: try `--range-buckets 20` or `--sidecar` (unmeasured) |
| Laptop build too slow | `--quick` (~1 min), or `--skip postflop` (heuristic postflop) |
| No numpy in the sandbox | Already handled: pure-Python path; check with `bench_latency.py --no-numpy` |
| Bundle too big (PLO5) | `--range-buckets 20`, or `--sidecar` if a folder upload is allowed |
| Variant isn't covered by `Variant` | Submit the heuristic bot; extend `hand_value_5` + `TorchEval.eval5` together, then run `pytest tests/test_evaluator.py` |
| Kit engine rules differ (min-raise, antes, short all-in reopening) | Match `nolimit/engine.py` to the kit (`reopen_short` covers the all-in rule), rerun the tune |
| v2 bot misbehaves in the kit | `dist/fallback/<preset>_bot.py` style: `--bundle bundles/<preset>.nlb --params params/nlhe_final_legacy.json` |
| Decisions near 1 ms on their hardware | 1) `package_bot.py --pure-python` (numpy's BLAS threads caused most tail spikes on the slow test box). 2) Tighten the guard: add `PrepBot.deadline = 0.0004` to the adapter (seconds; default 0.0006). 3) Last resort, the cheaper rules engine: `--params params/nlhe_final_legacy.json` |

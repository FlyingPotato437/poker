# nolimit-prep

Prep kit for **No Limit: A Bot Building Tournament** (Sequoia / OpenAI / Citadel Securities,
[rules](https://pokerbot.sequoiacap.com/rules.html)). The variant is secret until the
build phase, bots get **1 ms per decision in Python**, **100 MB** max, and scoring is
**finishing-position points** (ICM at the 200-hand cap). So this kit does not ship a
solved strategy for one game. It ships a pipeline that turns *any* hold'em/Omaha-family
variant into lookup tables in minutes, plus a bot that runs on those tables in about
10–70 µs per decision.

> **Rules check first.** The rules don't say whether teams may bring pre-written code
> or use their own compute during the build phase (3.3–3.4 name only Astra and Codex;
> 5.4 allows code review before prizes). Ask the organizers in writing before relying
> on this. See [PLAYBOOK.md](PLAYBOOK.md) for the day-of plan.

## What's here

| Path | What it does |
|---|---|
| [nolimit/runtime.py](nolimit/runtime.py) | **Ships in the bot.** Variant spec + presets, prime-product evaluator, stdlib bundle reader, postflop features + MLP, opponent model, `PrepBot`. Stdlib only; uses numpy if present. |
| [nolimit/engine.py](nolimit/engine.py) | 8-seat NL sit-and-go simulator in the tournament format (2,000 chips, 10/20 start, +level every 25 hands, 200-hand cap, ICM survivors, side pots). |
| [nolimit/zoo.py](nolimit/zoo.py) | Opponent archetypes for a field of 60-minute bots (tag, lag, nit, shover, station, maniac, random, timeout), exploit probes (jammer, bully, trapper), styles first held out and later tuned against by the Oct 31 field-fit runs (sizer, cbet, mc, balanced, overbet; `FRESH`: limper, icmshort, potcontrol, adaptive), the `FINAL_WEAK`/`FINAL_STRONG` gate sets written after the rc1 freeze (flaky, sticky, minraise, overfold; positional, barrel), and the out-of-sample `OOS` set (chen, potodds, bluffy, brittle), played only in a last confirmation after a candidate is chosen. |
| [nolimit/harness.py](nolimit/harness.py) | Parallel SNG runner that scores the organizers' way (avg points per table). |
| [gpu/build_tables.py](gpu/build_tables.py) | GPU table builder: hand classes, preflop equities vs 1–7 opponents, HU equity vs top-y% ranges, postflop equity MLP, push/fold charts → one `.nlb` bundle. |
| [gpu/pushfold.py](gpu/pushfold.py) | ICM push/fold solver (fictitious play) and ICM bubble-factor tables. Re-run in seconds once the points table is announced. |
| [gpu/tensor_eval.py](gpu/tensor_eval.py) | Torch mirror of the evaluator/features (CUDA, MPS or CPU); parity-tested against runtime. |
| [gpu/range_eq.py](gpu/range_eq.py) | Range-equity net: hero equity vs the top x of the top y of hands, 5 × 9 grid per board. Adds `rng_*` to a bundle; this is what the EV engine reads ranges with. |
| [scripts/tune.py](scripts/tune.py) | Cross-entropy parameter search for `PrepBot` vs the zoo + itself, common random numbers; `--mix-hands-per-level` scores each candidate at several blind speeds. |
| [scripts/ab_test.py](scripts/ab_test.py) | Paired A/B: two bots in the same seat vs the same opponents and cards, A − B ± se per cell, plus 4 v 4 head-to-head. Sealed `fresh*` fields are opt-in, for final confirmation only. |
| [scripts/fit_model.py](scripts/fit_model.py) | Fits the range-reading and continue-probability params by least squares / maximum likelihood against simulator ground truth, with held-out calibration. |
| [scripts/run_tournament.py](scripts/run_tournament.py) | Score any field of bots. |
| [scripts/bench_latency.py](scripts/bench_latency.py) | p50/p99/p99.9/max decision latency, with or without numpy. |
| [scripts/fuzz.py](scripts/fuzz.py) | Crash/legality/latency fuzzing: real games under extreme setups + degraded adapter-style observations, every bundle and variant. |
| [scripts/benchmark.py](scripts/benchmark.py) | Robustness matrix: opponent fields × points tables × blind speeds, mirror fairness check, optional best-response attacker. Writes `bench/report.md`. |
| [scripts/robustify.sh](scripts/robustify.sh) | Population training on one variant: attacker → retune against all attackers → repeat, then a final attacker reports the exploitability left. |
| [scripts/latency_all.sh](scripts/latency_all.sh) | Latency for every bundle, numpy on/off. Run on an idle machine. |
| [scripts/build_all_max.sh](scripts/build_all_max.sh) | Max-accuracy bundles for every preset on one GPU (run detached). |
| [scripts/package_bot.py](scripts/package_bot.py) | One-file submission: runtime + embedded tables + params + adapter, then a clean-interpreter smoke test. |
| [scripts/freeze.py](scripts/freeze.py) | Copies the submission files read-only to `frozen/<tag>/` with a sha256 manifest of each part (runtime, params, tables, adapter); `--verify` re-checks them. |
| [scripts/final_check.py](scripts/final_check.py) | Plays frozen files through the mock-kit adapter with auto model size, the deadline guard and a real 1 ms auto-fold, vs opponents written after the freeze; paired vs the old bot (or `--a`/`--b` any two packaged files), per field type. `--fields oos` adds the out-of-sample field; `--attackers B=...` names which bot each attacker targets. |
| [scripts/day.py](scripts/day.py) | **Day-of, one command per step:** `build <tag>` (exact push/fold for the announced points and antes, package, clean-interpreter checks of memory / import / latency / illegal actions, kit simulator, freeze), `submit`, `rollback`, `status`. `--heuristic variants/day.json` packages a v0 for a new variant before its tables exist. |
| [scripts/switch_study.py](scripts/switch_study.py) | Per-table param switching: every table is played on the base params to hand N, then stays or switches to each arm from the same state; uplift regression on what the bot saw by hand N, cross-validated rule, 95% CIs. |
| [scripts/variant_stats.py](scripts/variant_stats.py) | Hand-category frequencies, to sanity-check a new variant's ranking order. |
| [adapter_template.py](adapter_template.py) | **The only part you write on the day:** map the starter kit's state/actions onto `Obs`. |
| [examples/mock_kit.py](examples/mock_kit.py) | Fake starter kit (string cards, raise-by, no hand-end callback) for rehearsal; checks the packaged bot makes the same decision as the bot fed our own `Obs`, on every decision. |
| [examples/kit2/](examples/kit2/) | Rehearsal kit #2 for the timed drill in [REHEARSAL.md](REHEARSAL.md): new variant (3 hole cards, exactly 2 used), antes, its own state format, timed simulator with `--parity`. Answer key in `examples/answers/`. |
| [VARIANTS.md](VARIANTS.md) | What each kind of rule change costs: parameters only, a variant JSON plus table build, or new code (and what to submit meanwhile). |
| [dist/](dist/) | Packaged bots, one per preset. `dist/fallback/` holds the previous, rules-engine bots (Oct 30). |
| [organizer_reply.md](organizer_reply.md) | Draft reply to the acceptance email: confirms seats, asks the open rules questions. |

Presets: `nlhe`, `shortdeck`, `shortdeck_triton`, `plo4`, `plo5`, `holdem3`, `royal`,
`pineapple_nodiscard`. Anything else that fits "deal hole cards, deal board in streets,
best 5-card hand" is a JSON file (see [variants/example_day.json](variants/example_day.json)).

## Setup

```bash
uv venv --python 3.12 .venv
```

```bash
uv pip install --python .venv/bin/python numpy torch pytest
```

```bash
.venv/bin/python -m pytest -q
```

On a CUDA box install the matching torch wheel; `--device auto` picks CUDA, then MPS, then CPU.

## Pipeline

```bash
# 1. Tables (full settings are sized for one big GPU; --quick for a laptop smoke test)
.venv/bin/python -m gpu.build_tables --variant nlhe --out bundles/nlhe.nlb --payouts 100,65,45,30,20,12,6,0
```

```bash
# 2. Range-equity net for the EV engine (adds rng_* to the bundle; --laptop on the day, ~7 min NLHE on MPS)
.venv/bin/python -m gpu.range_eq --bundle bundles/nlhe.nlb --out bundles/nlhe_rng.nlb
```

```bash
# 3. Tune params against the zoo at every blind speed (CPU-bound: more cores = more SNGs per generation)
.venv/bin/python scripts/tune.py --bundle bundles/nlhe_rng.nlb --init params/ev_t3.json --mix-hands-per-level 25,10 --gens 8 --pop 24 --sngs 1200 --out params/nlhe.json
```

```bash
# 4. Paired A/B against the current bot (same seats, opponents, cards; prints A-B ± se per cell)
.venv/bin/python scripts/ab_test.py --bundle bundles/nlhe_rng.nlb --a prep:params/nlhe.json --b prep:params/ev_t3.json --sngs 700
```

```bash
# 5. Check latency, then package and smoke-test the submission
.venv/bin/python scripts/bench_latency.py --bundle bundles/nlhe_rng.nlb --params params/nlhe.json --no-numpy --gc freeze
```

```bash
.venv/bin/python scripts/package_bot.py --bundle bundles/nlhe_rng.nlb --params params/nlhe.json --out dist/nlhe_bot.py
```

## How the bot decides

Preflop is rules plus ICM; postflop is an expected-value search over opponent ranges read
from their actions. In order, for one decision:

1. **Preflop, deep:** hand class → strength percentile; open the top x% (wider with fewer
   players behind, and wider still when the players behind fold a lot: `steal_exploit`);
   vs a raise, HU equity against the raiser's *observed* raise range (per-seat VPIP/PFR/
   shove stats with priors), pot odds, re-raise threshold.
2. **Preflop, ≤ `pf_bb` big blinds:** ICM push/fold charts by players left × position ×
   effective stack, widened against tables that rarely call; calls switch from the chart to
   equity vs the shover's observed range once there are 12+ hands of reads.
3. **Postflop, read each opponent's range.** Every live opponent gets a slice of hands:
   their preflop range is the top *y* of hands (from how often they raise/call, tightened
   per re-raise level), and inside that, the slice [a, b] by postflop strength. A bet keeps
   the top of the range in proportion to how often that player bets; a raise keeps less; a
   call removes the top (they would have raised) and the bottom (they would have folded); a
   check caps the range (removes much of what bets). A new card relaxes the read
   (`rng_persist`). All widths come from that player's own stats this game.
4. **Equity vs those ranges.** A second network (`rng_*` in the bundle, 45 outputs) gives
   the hero's equity against the top *x* of the top *y* of hands on a 5 × 9 grid for this
   exact board; the bot interpolates and integrates over each opponent's slice, then
   combines opponents multiway. Validation error 0.024 (NLHE) to 0.042 (PLO5) equity.
5. **Choose the action with the best EV.** Candidates: check, bets of 33/66/100/150% pot
   and all-in; or fold, call, raises of 80/130% pot and all-in. For each, the chance that
   each opponent continues comes from a logistic model of their fold stats, the price, and
   their range (fitted by maximum likelihood on simulated hands, then tuned), and what
   they continue with is the top of their slice. Win and loss terms are weighted by ICM
   bubble factors plus a survival premium that grows with the share of the stack at risk
   (`risk_av`) and fades when short (`risk_depth`), because busting early costs more
   finishing points than chip EV says.
6. **ICM everywhere:** every call uses the bubble factor BF = (ICM_now − ICM_lose) /
   (ICM_win − ICM_now) for the hero/villain stack shares and the fraction of stack at risk.
   Tables are precomputed per points table (2,527 spots in 0.7 s); the lookup is O(1).
7. **Never crashes, never illegal:** any internal exception becomes check/fold, and every
   action passes through `legalize()`. Bundle loads once per process, `warmup()` runs 300
   synthetic decisions at import, then `gc.freeze()`.

Two network sizes: big nets when numpy exists (postflop 1024×512, range 1024×512), 64×32
nets when it doesn't, so pure Python stays under 1 ms. With `ev_post=0` the bot uses the
older rules engine (thresholds on equity vs random hands, optionally blended with the range
equity via `rng_mix`): that's the "Hybrid" engine in the results below. All thresholds live
in `DEFAULT_PARAMS` / `PARAM_SPACE` in runtime.py, which is what `tune.py` searches.

## Final check: frozen release rc1 vs the old bot (Oct 31)

`scripts/freeze.py --tag rc1` copied the 14 submission files (7 v2 bots, 7 old bots) to
`frozen/rc1/` read-only, with a sha256 manifest. `scripts/final_check.py` then played those
exact files as a host would:
- **Adapter:** each file is rebuilt with the mock-kit adapter (everything above the adapter
  checked byte-identical to the frozen file).
- **Model choice and deadline:** the model size is picked by the bot itself at import, and
  its 0.6 ms deadline guard is on.
- **Timing and penalty:** each decision is timed around `get_action()`, and one over 1 ms
  is replaced with check/fold.
- **Opponents and seed:** opponent styles were written after the freeze (four weak, two
  strong) or had never been an opponent (`hyb_t1_g8`). The seed was never used before.

Paired, as in `ab_test.py`. NLHE: 2,000 paired SNGs per cell. Other variants: 1,000. All at
normal and fast blinds, default points table.

| Run | weak fields | mixed | strong | attackers | **all cells** | timeouts per 1k decisions, rc1 / old | rc1 p99.9 |
|---|---|---|---|---|---|---|---|
| NLHE, slow CPU (2.1 GHz Xeon) | +5.0% ±1.5 | +7.6% ±1.9 | +17.0% ±1.8 | +13.4% ±1.0 | **+10.2% ±0.7** | 0.46 / 0.43 | 0.71 ms |
| NLHE, slow CPU, no numpy | +4.4% ±2.4 | +9.8% ±3.1 | +16.8% ±2.7 | +13.2% ±1.6 | **+10.3% ±1.2** | 0.82 / 0.25 | 0.94 ms |
| NLHE, slow CPU, all 8 cores busy | +7.4% ±2.4 | +7.1% ±3.1 | +19.7% ±2.8 | +12.8% ±1.6 | **+11.2% ±1.2** | 1.21 / 1.10 | 1.27 ms |
| NLHE, M3 Pro laptop | +8.3% ±2.2 | +7.6% ±2.7 | +18.9% ±2.5 | +12.6% ±1.5 | **+11.4% ±1.1** | 0.17 / 0.15 | 0.37 ms |
| NLHE, laptop, big models forced | +4.4% ±2.2 | +8.1% ±2.7 | +20.1% ±2.5 | +14.2% ±1.5 | **+10.9% ±1.1** | 0.23 / 0.15 | 0.53 ms |
| shortdeck | +1.9% ±2.3 | +8.4% ±2.9 | +17.9% ±2.6 | | **+7.5% ±1.5** | 0.69 / 0.60 | 0.78 ms |
| shortdeck_triton | +3.7% ±2.2 | +6.7% ±2.9 | +21.5% ±2.6 | | **+8.9% ±1.5** | 0.72 / 0.59 | 0.80 ms |
| royal | +9.5% ±2.2 | +12.9% ±2.9 | +28.7% ±2.6 | | **+15.2% ±1.4** | 0.71 / 0.62 | 0.81 ms |
| holdem3 | +3.0% ±2.2 | +4.8% ±2.8 | +18.7% ±2.5 | | **+7.4% ±1.4** | 0.71 / 0.59 | 0.80 ms |
| plo4 | **−3.1% ±2.2** | +6.0% ±3.0 | +21.6% ±2.7 | | **+5.4% ±1.5** | 0.84 / 0.67 | 0.88 ms |
| plo5 | +2.1% ±2.3 | +13.5% ±3.0 | +22.4% ±2.7 | | **+10.0% ±1.6** | 0.80 / 0.58 | 0.87 ms |

Variants other than NLHE ran on the slow CPU. "Attackers" = 7 copies of an attacker tuned
against rc1, or against the old bot, around the seat. Per-cell tables are in
`bench/final_rc1_*.txt`.

What it shows:
- **rc1 is ahead overall in every run**, with no errors in ~16 million timed decisions.
- **The edge comes from strong fields** (+17 to +29%). Against weak bots rc1 is only a few
  percent ahead, and on PLO4 it is slightly behind (fast blinds −5.6% ±4.4). Both bots
  already take about 2× their fair share there.
- **Timeouts:** rc1 times out at about the same rate as the old, much lighter bot, so it is
  host noise, not the bot. The exception is pure Python on the slow CPU: 0.8 per 1k
  decisions, about 0.05 forced folds per SNG.
- **Model size:** the import-time calibration picked the small models on both machines. On
  the laptop, pool workers ran on slower cores, where they measured 3× slower than the main
  process. Forcing the big models changed nothing measurable (+10.9% vs +11.4%), so the
  ~3% small-model cost seen against the tuning zoo doesn't show against new opponents.
- **Exploitability** (NLHE, one attacker at a table of 7 copies of the bot it was tuned
  against, 600 SNGs): 1.31× fair ±0.04 against rc1, 1.47× ±0.04 against the old bot.

## Results: v2 EV engine (Oct 30–31)

**Method.** Every comparison is a paired A/B (`scripts/ab_test.py`): each SNG is played
twice with identical seats, opponents and deck, once with A in our seat and once with B,
so luck cancels and the paired difference has a small standard error. A cell is one
points table × blind speed × opponent field; "% of fair" is A − B in points per table over
the fair share (total points / 8). Fields: the tuning zoo, passive, aggressive, competent,
`held-out*` (five styles never tuned against), sharks (3 copies of the old bot + strong
zoo bots), and the **sealed** `fresh*` fields (four new styles plus three older tunes of
our own bot), which were written after all tuning and used only for the final checks.
The sealed runs also use a fresh seed and the corrected all-in rule.

**Sealed confirmation, NLHE** (3 fresh fields × 2 points tables × 2 blind speeds, 1,000
paired SNGs per cell, seed 4242):

| A vs B | mean A − B | head-to-head 4 v 4 |
|---|---|---|
| EV engine `ev_t3` vs old bot `nlhe_final` | **+9.6% ±1.6** | 1.05–1.15× |
| Hybrid `hyb_t1_g8` vs old bot | +2.1% ±1.5 | 1.03–1.07× |
| EV `ev_t3` vs Hybrid | **+7.5% ±1.6** | 1.02–1.08× |
| `ev_t4` (= `ev_t3` + Hybrid's preflop) vs `ev_t3`, seed 5151 | **+6.2% ±1.3** | 0.97–0.99× |

The same `ev_t4` vs `ev_t3` check on other variants: PLO4 +0.4% ±1.4, shortdeck +1.9% ±1.4.
Hybrid's preflop params were tuned on NLHE, so NLHE ships `ev_t4` and the rest ship `ev_t3`.
(This was a second look at the sealed fields, so it's slightly less clean than the first;
it repeats the +5.0% ±0.9 seen on the development matrix with different fields and seeds.)

**Development matrix, NLHE** (7 fields × 2 points tables × 2 blind speeds = 28 cells, 700
SNGs per cell; these fields were used for choosing, so they're optimistic):

| A vs B | mean A − B | note |
|---|---|---|
| `ev_t3` vs old bot | +3.8% ±1.2 | +14 to +34% vs competent/sharks; −7 to −10% vs passive/zoo at fast blinds |
| `ev_t3` vs Hybrid | +0.5% ±1.1 | EV wins competent fields and head-to-head, loses passive ones |
| Hybrid hardened 1 round (`hyb_r1`) vs Hybrid | −2.9% ±0.9 | attacker gain 23% → 18%, not worth the field cost |
| `pool_w` 0.5 (table-pooled opponent priors) vs `ev_t3` | +0.1% ±0.7 | no effect; left off |
| `ev_t3` with Hybrid's preflop params vs `ev_t3` | **+5.0% ±0.9** | +10 to +21% vs passive fields; loses head-to-head (0.94–0.99×) |

**Other variants** (`ev_t3` vs old bot, 7 fields × 2 blind speeds, 500 SNGs per cell; and
`ev_t3` vs the previous EV tune at fast blinds, the case `ev_t3` was tuned to fix):

| variant | vs old bot | vs previous EV tune, fast blinds |
|---|---|---|
| plo4 | +9.2% ±1.3 | +3.7% ±1.4 |
| plo5 | +10.7% ±1.4 | +4.6% ±1.4 |
| shortdeck | +7.9% ±1.3 | +6.6% ±1.4 |
| shortdeck_triton | +8.3% ±1.3 | +4.4% ±1.4 |
| royal | +6.9% ±1.3 | +4.1% ±1.4 |
| holdem3 | +5.5% ±1.3 | +5.0% ±1.4 |

**Exploitability** (best-response attacker initialised from the target, 1 vs 7 copies,
8 generations × 16 candidates × 500 SNGs, scored on 3,000 fresh SNGs): +38.3% against the
old bot, +22.9% against Hybrid, +17.9% against hardened Hybrid, **+15.3% against `ev_t3`**
and +20.9% against `ev_t4` (its looser preflop is what the attacker leans on; it still
wins +6.2% in the sealed fields, so it ships on NLHE). The attacker wins by
playing tighter than a table of 7 aggressive copies, which is a property of that setup
as much as of the bot. A smaller number is better, but none of these is proof the bot
can't be exploited; it only bounds what this search found.

**Adapter.** Through the mock kit (string cards, raise-by amounts, no hand-end callback),
the packaged v2 bot made the identical decision to the bot fed our own `Obs` on 8,748 of
8,748 decisions with numpy and 4,302 of 4,302 without. A first run found 3 mismatches in 8,678: the adapter flagged a seat's
earlier actions as all-in, which skewed its shove stats; fixed and added to the adapter
checklist.

**Speed (the 1 ms limit).** The EV engine does far more work than the old rules engine,
so it was measured on a deliberately slow CPU (the Thunder box: 2016 Xeon E5-2683 v4, 2.1
GHz) as well as the laptop. The first v2 build failed there: big models with numpy had a
postflop median of 0.39 ms and 99.9th percentile of 2–5 ms; pure Python had a 0.59 ms median.
Four fixes:

1. **Model size picked at import.** `warmup()` times the big models on the machine the bot
   is actually running on and switches to the small ones if a new street would cost more
   than 0.15 ms (laptop: 0.08 ms → big; Xeon: 0.19 ms → small). `NOLIMIT_NETS=big|small`
   overrides it.
2. **Deadline guard.** 0.6 ms into a decision the EV engine stops trying raise sizes and
   returns the best action found so far (check/call/fold are always evaluated first).
   Simulations switch it off (`PrepBot.deadline`) so the same seed always plays the same game.
3. **Less work in pure Python.** Heads-up pots skip the vs-random model (only multiway
   needs it); the range model computes its 45 output cells on demand (a decision reads
   about 2 of its 5 rows); layers 2–3 are C-level `sum(map(mul, ...))` over transposed
   weights. Same outputs as numpy to 3e-7 (tested).
4. **One BLAS thread.** The bot pins BLAS to one thread before importing numpy, which cut
   the >1 ms decisions 3–4×. If the host imports numpy first, this can't take effect;
   `package_bot.py --pure-python` builds a bot that never uses numpy.

Xeon, after the fixes (60 SNGs ≈ 33k decisions per row, 4 copies of our bot per table):

| path | postflop median | 99th pct | 99.9th pct | decisions > 1 ms | guard fired |
|---|---|---|---|---|---|
| numpy, small models (auto), BLAS pinned | 0.22 ms | 0.43 ms | 0.63–0.70 ms | 3–5 per 34k | ~12 per 34k |
| pure Python | 0.34–0.36 ms | 0.59–0.63 ms | 0.64–0.81 ms | 4–9 per 34k | 22–254 per 34k |

The remaining >1 ms decisions include trivial preflop ones (up to 1.5–6 ms on decisions
whose 99.9th percentile is 0.07 ms), so they look like the shared host, not the bot. On
the laptop (idle runs, numpy, big models) worst-case decisions in smoke tests are 0.2–0.35 ms.

**What the small models cost.** Same params, small vs big models (paired, development
fields): NLHE −2.7% ±0.8, PLO4 −3.5% ±1.0. So on a slow host, or without numpy, the bot
gives back about 3 points of its edge. A 256×128 middle size (postflop error 0.013 vs 0.009
big / 0.024 small) would likely fit a slow CPU with numpy and recover most of it; not built.

**Robustness.** Fuzz (`scripts/fuzz.py`, all 7 v2 bundles + 8 heuristic table sets,
numpy on and off, ~365k decisions incl. degraded adapter input): 0 crashes, 0 illegal
actions (rerun after the speed changes: 0 failures). **Seat fairness**, measured per seat
(8 copies of `ev_t4` in fixed seats, 1,500 SNGs, 2 points tables × 2 blind speeds): every
seat within 1.8 se of fair, as expected from noise alone over 32 seat-cells.
Field scores for `ev_t4` (`bench/v2_benchmark.md`): 1.38×–3.24× fair share in every cell.

## Measured on an M3 Pro laptop (MPS)

- Evaluator + features: exact parity torch vs pure Python on all 8 presets, CPU and MPS.
- Preflop tables (NLHE, 40k rollouts/class): AA 0.854, KK 0.824, QQ 0.796 vs known
  0.852 / 0.824 / 0.799. Laptop MPS throughput ≈ 11M hand evaluations/s.
- Full NLHE bundle at medium settings: ~4.5 min on the laptop; postflop MLP MAE 0.045.
  Quick bundles for plo4 / shortdeck / royal / holdem3 build in ~1–3 min each. PLO's
  16k classes need a bigger `--rows-budget` than the laptop can give (strength order is
  visibly noisy at quick settings).
- Tuning works: after 8 generations, tuned PrepBot scores **59.6 pts/table vs 46.4** for
  default params (±0.4, 6,000 SNGs vs the zoo, placeholder points table). Tuning is noisy
  under ~1,500 SNGs per candidate (per-table SD ≈ 32 points).
- Decision latency, `gc.freeze`: numpy p50 0.005 ms, p99.9 0.04 ms, max 0.21 ms. Pure
  Python p99.9 0.25 ms; rare >1 ms spikes (4 in 47k, including trivial preflop decisions,
  so likely OS jitter on a busy laptop).
- Harness: ~600 SNGs/s on 11 cores. Push/fold charts (182 spots): ~13 s.
- An always-fold bot scores mid-pack under position points: survival is worth a lot,
  and crashed bots in the real field will behave exactly like that.

## Verification (NLHE, Oct 29–30)

- **Max-accuracy tables** (Thunder A6000, 10.8 min): preflop AA/KK/QQ/JJ/TT 0.852 / 0.823 /
  0.799 / 0.774 / 0.750 vs known 0.852 / 0.824 / 0.799 / 0.775 / 0.751. Postflop MLP MAE
  0.017 (128×64) / 0.024 (64×32); 0.009 after the width sweep below (1024×512).
- **Push/fold solver vs known Nash** (heads-up = chip EV): 10 bb shove 58.8% / call 38.4%
  (published ≈58% / ≈37%); 20 bb 38.2% / 21.4% (≈37% / ≈21%).
- **ICM bubble factors:** heads-up 1.00 (exact); 8 left, equal stacks, all-in 1.76
  (calling off 100 bb needs 63.5% equity vs 49.6% chip EV); short vs big 1.56, big vs short 1.14.
- **Fuzz:** ~215k decisions over 16 table sets (every bundle + every preset), real games
  with 2–9 seats, 5–500 bb, antes, odd blinds, plus degraded adapter-style inputs. Found and
  fixed 3 bugs that would have auto-folded in a real event (no hand id, free-check fold,
  zero pot). Now 0 failures.
- **Python 3.9 / 3.11 / 3.12 / 3.13**, no numpy: packaged bot runs; 3.9 p99.9 0.16 ms,
  0 of 35.7k decisions over 1 ms.
- **Exploit probes** (1 of ours vs 7; fair share 34.75): vs always-all-in 75.6, vs
  min-raise bully 90.7, vs check-raise trapper 60.7.
- **Best-response attackers** (same strategy family, 10 generations, vs 7 of ours):
  +3.70 pts/table (+10.6%) against the first tuned params, +2.61 (+7.5%) after one round
  of population training, +0.53 (+1.5%, within 1 SE of zero) after two rounds. That only
  means this particular attacker search found no edge, not that the bot is unexploitable:
  a stronger search on Oct 30 (attacker initialised from the target itself, more SNGs per
  candidate) gained **+38%** against the same params (see the v2 results). The
  round-2 params (`params/nlhe_final.json`) also beat the first tuned params head-to-head
  in every field (+1.4 to +3.6 pts/table, 5,000 SNGs each).
- **Robustness matrix, final params** (`bench/final.md`, 800 SNGs/cell): 1.28×–3.19× fair
  share in every normal field (4 points tables × 2 blind speeds × 5 fields); vs 7 copies of
  an attacker trained against this exact bot 0.97×–1.25× (was 0.89×–0.95× before population
  training); 0 errors. (This report also showed "mirror 1.00×", which proves nothing: 8
  identical bots under one label average total/8 by construction. `benchmark.py` now scores
  each seat of the mirror separately.) Earlier versions:
  `bench/baseline.md`, `bench/robust.md`. Params tuned at 25 hands/level lose to defaults in some fast-blind
  cells, so retune with the real schedule on the day.

## Verification (all presets, Oct 30)

**Shipped bots** (`dist/<preset>_bot.py`, `nlhe_final` params, latency on an idle M3 Pro,
60 SNGs ≈ 33–38k decisions each, gc frozen; `scripts/latency_all.sh`):

| preset | postflop MAE numpy / pure Python | file | p99.9 numpy / pure Python | decisions >1 ms |
|---|---|---|---|---|
| nlhe | 0.0090 / 0.0243 | 3.0 MB | 0.17 / 0.10 ms | 0 |
| shortdeck | 0.0084 / 0.0311 | 3.0 MB | 0.05 / 0.09 ms | 0 |
| shortdeck_triton | 0.0083 / 0.0294 | 3.0 MB | 0.04 / 0.10 ms | 0 |
| royal | 0.0059 / 0.0178 | 2.9 MB | 0.04 / 0.10 ms | 0 |
| holdem3 | 0.0126 / 0.0294 | 3.4 MB | 0.06 / 0.10 ms | 0 |
| plo4 | 0.0160 / 0.0388 | 7.0 MB | 0.07 / 0.13 ms | 0 |
| plo5 | 0.0212 / 0.0478 | 37.4 MB | 0.08 / 0.12 ms | 0 |

- Every >1 ms decision seen during this pass (up to 52 ms) happened while other jobs
  saturated the CPU or the machine was deep in swap; idle reruns of the same seeds had none.
- Fuzz (`scripts/fuzz.py`, every final bundle, numpy on and off, ~170k decisions incl.
  degraded adapter input): 0 failures.
- Clean-interpreter smoke on Apple's system Python 3.9.6, 3.9.23 and 3.13.7, no numpy: all
  pass. PLO5 imports in 0.45–0.55 s; first decisions after import peak at 0.23 ms (warmup).
- Small-model fallback (no numpy) is 2–3× less accurate. Ask the organizers about numpy.

**Postflop model width.** The 128×64 nets were underfit. Retrained on the cached Monte Carlo
data (same samples, 20 epochs) and scored on held-out labels (1,000–2,000 rollouts each, so
~0.007–0.010 of the error is label noise):

| preset | 128×64 | 256×128 | 384×192 / 512×256 | 768×384 | **1024×512 (shipped)** | 64×32 (no numpy) |
|---|---|---|---|---|---|---|
| nlhe | 0.0173 | 0.0127 | 0.0104 | 0.0093 | **0.0090** | 0.0243 |
| shortdeck | 0.0182 | 0.0121 | 0.0103 | 0.0086 | **0.0084** | 0.0311 |
| shortdeck_triton | 0.0181 | 0.0122 | | 0.0086 | **0.0083** | 0.0294 |
| royal | 0.0092 | 0.0067 | | 0.0060 | **0.0059** | 0.0178 |
| holdem3 | 0.0230 | 0.0177 | 0.0150 | 0.0130 | **0.0126** | 0.0294 |
| plo4 | 0.0302 | 0.0236 | 0.0180 | 0.0164 | **0.0160** | 0.0388 |
| plo5 | 0.0383 | 0.0311 | 0.0246 | 0.0221 | **0.0212** | 0.0478 |

The same holds at `--laptop` data sizes (450k samples: NLHE 0.027 → 0.015, PLO4 0.037 →
0.023), so both profiles now default to 1024×512 (MPS training 29 s vs 19 s). The shipped
runtime reproduces these numbers through its own loader and forward pass. A numpy forward
pass is ~10–15 µs at any of these widths, so width costs nothing at decision time.

**Features tried and rejected.** Adding top rank, second rank and the hero's highest card in
the leading suit (nut-flush signal) cut PLO4 error only 3–4% in an A/B on identical cards.
Not worth a full data rebuild; width gave 5× more.

**Params per preset.** Quick per-preset tunes (8 generations, 600 SNGs each) vs the NLHE
population-trained `nlhe_final`, 400 SNGs per cell over zoo / passive / aggressive /
competent / "3 of us" fields × 2 points tables × 2 blind speeds (`bench/variants/*.md`):
`nlhe_final` had the higher mean in 5 of 6 presets (+0.04 to +0.06× fair share, winning
15–19 of 20 cells) and tied on shortdeck. The per-preset tunes overfit their tune field.
Packaged bots use `nlhe_final` unless a `params/<preset>_robust.json` exists.

**Adapter check was biased, now fixed.** `examples/mock_kit.py` seated the kit-wrapped bot
left of the always-fold `timeout` bot every game, so it scored 61.3 vs 50.0 for the same bot
direct (300 SNGs, ~4 SE), which looked like an adapter bug. With each deal played twice and
the two seats swapped, the result is 55.7 vs 56.2 (600 SNGs): the adapter is equivalent.

**Exploitability is per variant.** Fresh best-response attackers on the final PLO4 bundle
(1 vs 7, 3,000 SNGs, ±1.7%): +4.0% against `nlhe_final` (+9.7% on the old 128×64 bundle),
+0.3% against `plo4.json`. `nlhe_final` gains +1.5% on NLHE. In the field benchmark on the
final bundle `nlhe_final` still leads (+0.056× fair share, 14 of 20 cells) and scores about
the same as `plo4.json` against 7 copies of its own attacker (0.96× vs 0.98×), so it stays
the default. On the day, `scripts/robustify.sh` runs population rounds on the real variant;
keep its output only if it also wins the field benchmark.

## Known gaps

- Engine rule: since Oct 31 a short all-in no longer reopens raising for players who already
  acted (standard rule; `reopen_short=True` gives the old behaviour). Results before that
  date used the old rule. Check the kit's simulator and match it.
- Not modeled: hi-lo splits, discards (pineapple), wild cards, stud-style dealing, bounties.
  The bot still plays legally on those through the adapter, but tables/evaluator need new code.
- Exploitability measured on NLHE (and PLO4 for the old bot) only. A strong attacker (1 vs
  7 copies) still gains 15–21% against the v2 bots on NLHE, so exploitability is reduced,
  not solved.
- Real tournament hardware is unknown. On a slow CPU the bot drops to small models (−3%
  against the tuning zoo, not measurable against the final-check opponents). On a noisy
  host, 0.2–1.2 decisions per 1k still run past 1 ms, about the same rate as the old bot.
  Pure Python on a slow CPU is the tightest case (p99.9 0.94 ms).
- Weak fields: rc1's lead over the old bot there is small (+2 to +10%) and slightly negative
  on PLO4 (−3.1% ±2.2). Its large lead is against strong fields.
  Whether real opponents can find that edge in a 200-hand game is a separate question.
- Zoo is a guess at the field. Re-weight `DEFAULT_FIELD_MIX` once T1 results show what the field does.
- Push/fold model assumes equal stacks and no overcalls; the bot uses effective stack.

# Handoff (Nov 4): state of the bot work and what to run next

**Nov 6 preparation:** [OFFICIAL_READY.md](OFFICIAL_READY.md) is the current interface, memory, payout and packaging checklist. Use `scripts/day.py prepare`; older workflows below are historical research instructions. Pre-kit candidates still require the released SDK and variant checks.

Read this first, then `bench/rc2_results.md`, which has every result, decision rule and
verdict in order. The `README.md` covers the code layout, `PLAYBOOK.md` the day-of steps,
and `REHEARSAL.md` the timed drill.

## The tournament (official rules, read Nov 3)

Source: <https://pokerbot.sequoiacap.com/rules.html>. Automated fetches get a 403 from
robots.txt; a browser works.

**Event**
- Menlo Park regional on Fri Nov 6. Check-in from 5:30 PM, event 6:00–9:00 PM.
- Registration closes Tue Nov 3, 11:59 PM PT, and **both** teammates must register.

**Build phase**
- 60 minutes to build a Python bot for the provided Agent interface.
- Astra, Codex and public docs are allowed.
- The kit contains an agent template, a simulator, an ICM calculator, the payouts and the
  blind schedule.
- The variant is secret until the build starts.

**Scoring**
- Six scored tournaments, T1–T6, 20 minutes apart. Weights are 1 to 6, so T6 is 29% of
  the final score.
- Each tournament is 10,000 eight-bot SNGs with random seats. Luck averages out.
- Resubmit at most once every 5 minutes. The active bot is frozen at the start of each
  tournament.

**Table rules**
- Each bot starts with 2,000 chips. Blinds start at 10/20 and go up every 25 hands.
- Tables end at the 200-hand cap, which scores the survivors by ICM.
- Decision limit 1 ms (a timeout or error folds or checks). File limit 100 MB.
- Bot state resets at every table, and opponents are anonymized.

**Open risk: pre-written code.** The rules don't mention it, and prizes are subject to code
review. Get a written answer from the organizers (`organizer_reply.md`) before relying on
this repo on the day.

## What ships today

`frozen/rc1/` is the frozen, tested release candidate. Don't edit it; tags are never
overwritten. `scripts/day.py` builds, submits and rolls back on the day.

## Where the research stands

1. **Field-fit tunes, rounds 1–3.** Every full retune (w, r, r2; NLHE and PLO4) gained
   +10–30% vs weak zoo fields and lost significantly vs the gate's "strong" field, so they
   failed. Two findings:
   - **`pool_w > 0` is a timing bug.** Every tune switched it on. It runs `pool_priors()`
     inside the first decision of each hand: p50 0.04 → 0.08 ms. The tuner can't see this,
     because sims run with no deadline. **Always pin `pool_w = 0`.**
   - **s5p0 nearly passes.** It's rc1 + 0.5·(r2 − rc1) with `pool_w` 0, in
     `params/s5p0_nlhe.json`. Gate seed 9104: +5.0% [+3.8, +6.3], with no significant loss
     in any cell. Its timing passes under the pooled rule. Its one-shot test was never run:
     the box went down.
2. **Rival-team field** (`nolimit/rivals.py`). These are our best model of other teams'
   60-minute Codex builds, not buggy hackathon bots.
   - **Dev designs:**
     - `rv_tag`, `rv_lag`, `rv_gto`, `rv_exploit`, `rv_icm` (strong);
     - `rv_mc`, `rv_aggro`, `rv_math` (mid);
     - `rv_buggy`, `rv_frozen` (weak).
   - **Holdout:** `rvh_*`, sealed.
   - **Fields:** `rival-strong`, `rival-strong+prep`, `rival-mid`, `rival-real`, and
     `rival-oos` (sealed), in both `ab_test.py` and `final_check.py`.
   - **Realism:** noisy Monte Carlo equity, and range weighting, Nash push/fold and ICM
     bubble factors on the better designs. Thresholds vary per instance.
3. **Results on rival fields** (seed 9501, ab_test, 2000 paired SNGs, vs rc1's params):
   - r2: +8.5% mean, no negative cell.
   - s5p0: +3.9% mean; −1.4 ±2.4 when a prepped copy is at the table.
   - Details are in `bench/rivals/`.
4. **Per-style gain of full exploit params** (`params/r2p0_nlhe.json`, vs 7 copies of each
   style; `bench/rivals/style_d_r2p0.txt`):
   - **Gains vs every rival and zoo style:** +3 to +39%. Timeout and jammer are about 0.
   - **Loses only vs our own prepped bots:** rival_prep −4.0, ev_t3 −7.6, legacy −5.2.
5. **Per-opponent safe exploitation** (new runtime code). Fitted by `scripts/fit_exploit.py`
   into `params/x_nlhe.json`; tests in `tests/test_exploit.py`.
   - **The rule:** each villain gets λ = P(exploitable | 7 seat stats) · hands/(hands + 15),
     from a logistic model with linear and squared terms. The bot plays at the smallest λ
     among the villains in the hand, blending rc1 → r2p0 in 5 steps.
   - **Separation:** prepped bots score P ≈ 0.15–0.25 by hand 50–100, most rivals 0.7–1.0.
   - **Cost:** about 18 µs per hand, computed once per hand.
   - **Not yet measured:** whether it beats r2p0 or s5p0.

## Interrupted runs to redo (box, or an idle machine)

Stopped on the laptop when its load hit 48:

```bash
# Dev comparison, deadline off (points only). Seed 9502.
for c in x_nlhe r2p0_nlhe s5p0_nlhe; do
  .venv/bin/python scripts/ab_test.py --bundle bundles/nlhe_rng.nlb --a prep:params/$c.json \
    --b prep:params/ev_t4.json --sngs 2000 --payouts default --schedules normal,fast --seed 9502 \
    --fields gate-weak,gate-weak+crashed,gate-strong,gate-mixed,rival-strong,rival-strong+prep,rival-mid,rival-real \
    --workers 16 > bench/rivals/ab2_$c.txt
done
# PLO4 transfer (exploit params = PLO4 rc1 + NLHE r2p0 deltas), per style, then fit a PLO4 rule.
.venv/bin/python scripts/style_d.py --bundle bundles/plo4_rng.nlb --a prep:params/xplo4_full.json \
  --b prep:params/rc1_plo4.json --sngs 400 --seed 9602 --workers 16 --json bench/rivals/style_d_xplo4.json \
  --styles tag,lag,shover,nit,station,maniac,timeout,random,jammer,bully,trapper,sizer,cbet,mc,balanced,overbet,limper,icmshort,potcontrol,adaptive,rv_tag,rv_lag,rv_gto,rv_exploit,rv_icm,rv_mc,rv_aggro,rv_math,rv_buggy,rv_frozen,prep:params/rival_prep.json,prep:params/ev_t3.json,prep:params/nlhe_final_legacy.json
.venv/bin/python scripts/fit_exploit.py --bundle bundles/plo4_rng.nlb --labels bench/rivals/style_d_xplo4.json \
  --exploit params/xplo4_full.json --base params/rc1_plo4.json --sngs 2000 --min-d -0.5 --out params/x_plo4.json
```

## Then: Round 4 gate and test (pre-registered in `bench/rc2_results.md`; follow it as written)

1. **Package** each candidate with the current runtime. s5p0 can instead be the rc1 file
   with only its `_PARAMS` line swapped, which keeps rc1's runtime bytes.
   `python scripts/package_bot.py --bundle bundles/nlhe_rng.nlb --params params/x_nlhe.json --out build/x_nlhe_bot.py`
2. **Gate** with `final_check.py` against `frozen/rc1/nlhe_bot.py`:
   - fields weak, weak+crashed, strong, mixed, rival-strong, rival-strong+prep, rival-mid,
     rival-real;
   - 3000 SNGs, a fresh seed (9105 or later), `--exploit-sngs 0`;
   - **8 workers on a 16-core box with nothing else running**, because timing counts.
3. **Pick** the highest 16-cell mean among the candidates that pass rules 1–3. Rule 3 is
   pooled: overall over-limit excess ≤ 0.15/1k, and p99.9 within 0.1 ms.
4. **One-shot test** of the pick only, on seed 9401:
   - fields weak, weak+crashed, strong, mixed, oos, rival-oos;
   - pass: the mean's lower bound > −0.5%, and no significant loss in any cell;
   - if it passes, freeze rc2 (`scripts/freeze.py --tag rc2`); if not, ship rc1;
   - change nothing after seeing it.
5. **Full checks of the new runtime:** run them before rc2 is trusted.
   - `pytest` and `scripts/fuzz.py`;
   - Python 3.8–3.14, with and without numpy;
   - peak memory, with `day.py build` doing these checks.

## Live plan for T1–T6 (still to write into PLAYBOOK.md)

1. Submit the best validated bot for T1, and keep rc1 frozen as the alternative.
2. Read our T1 score ÷ fair against the calibration: the candidate's x-fair on each field,
   from the final_check output.
   - Far below the rival-real level means a strong or prepped field: switch to rc1, or the
     exploit layer if it isn't already shipping.
   - At or above the rival-real level: stay.
3. Decide once, before T3 or T4, which carry more weight. Don't thrash: changes between
   tournaments are confounded with other teams' resubmissions.

## Compute and safety

- **Box:** a Thunder Compute instance. The SSH key is the user's, at
  `~/.ssh/thunder_ed25519` on their laptop.
- **Billing:** the instance bills while running. The user starts and stops it.
- **Credentials:** never commit API tokens or keys.
- **Timing runs:** final_check runs alone, at 8 of 16 workers. Tunes and the style or
  switch studies don't use the deadline, so CPU load doesn't change their results.
- **Pitfalls:**
  - multiprocessing spawn pools hang when the main script comes from stdin; run pool code
    from a file.
  - a field entry with the same label as A or B breaks the pairing; that's why
    `params/rival_prep.json` is a copy of `ev_t4.json`.

## Team to-dos (people, not code)

- Register both teammates by Nov 3, 11:59 PM PT.
- Send `organizer_reply.md`, and get the pre-written-code answer in writing.
- Run `REHEARSAL.md` twice with Wi-Fi off, Revanth included.

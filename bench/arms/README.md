# Arms race: tuned attackers against cand_nlhe (Nov 6)

The question: how much can a team with plenty of compute take from us by tuning a bot
against ours? And can a params-only change harden cand without losing what it wins at
weak seats?

The work was done on the laptop with 4 workers. For the first two hours the load average
was 400–600, from other agents, so every budget here is small. Nothing in `nolimit/`,
`gpu/`, `frozen/` or `scripts/` was changed. Scratch drivers are described at the end.

## Protocol

- **Attacker tune.** `scripts/tune.py`, `--self-weight 0`, all 54 tunable keys except
  `pool_w` (which stays at 0).
  - The table is the attacker plus 7 seats drawn from `prep:TARGET=5` and a rival mix:
    rv_tag, rv_lag, rv_gto, rv_exploit and rv_icm at 0.3 each, rv_mc and rv_math at 0.15
    each, tag at 0.2. That's about 5 copies of the target per table.
  - Settings: pop 12, elite 3, sigma 0.25, 250 SNGs per candidate, 6 generations.
  - Logs: `tune_*.log`.
- **Warm start.** The cold-start attackers (`*_cold`: from the target's own params, 100
  SNGs × 10 × 5 gens) were too weak, at 1.07–1.10x. So the real attackers start from the
  existing `params/br_vs_ev_t4.json`.
  - br1 and br_ev_t4 each start from br_vs_ev_t4.
  - br2 starts from br1, so it carries the most compute.
- **Exploitability.** One attacker plus 7 copies of the target, 1,000 SNGs, seed 8801,
  shown as x fair (fair is 34.75). Files: `expl_<attacker>_vs_<target>.txt`. A second
  "mix" section in some files is the tuning table.

## Exploitability: attacker x fair, 1 vs 7 copies

| attacker (tuned vs)        | ev_t4 | cand_nlhe | arms_h1 (rel=1) | cand without exploit layer |
|----------------------------|------:|----------:|----------------:|---------------------------:|
| br_vs_ev_t4 (old)          | 1.27  | 1.42      | 1.30            | 1.26                       |
| arms_br_ev_t4 (ev_t4)      | 1.32  | **1.56**  |  –              |  –                         |
| arms_br1 (cand)            | 1.31  | 1.53      | 1.44            | 1.33                       |
| arms_br2 (h1)              | 1.34  | **1.61**  | 1.46            |  –                         |
| whale_br (other agent)     | 1.16  | 1.42      | 1.29            |  –                         |
| **best attacker**          | **1.34** | **1.61** | **1.46**      | ≥1.33                      |

The SE is about ±0.033 per cell. Rows share the seed, so the gaps between columns are
better resolved than that.

**cand is more exploitable than ev_t4 by every attacker**: about +0.15 to +0.27x fair, or
5–9 pts a table. That holds even for attackers tuned against ev_t4.

## Where the leak is: the exploit layer, mostly its `rel=2` rule

Each variant was played against br1 (same seed, `expl_br1_vs_*`), as pts per table:

| variant | pts |
|---|---:|
| cand | 53.2 |
| `sh_open`/`hu_sb_play` off | 48.8 (vs the old attacker; cand is 49.5 there) |
| intercept beta0 −1 | 54.9 |
| intercept beta0 −2 | 54.7 |
| intercept beta0 −3 | 52.3 |
| `degen_n` = 0 | 53.2 (identical: never fires) |
| `rel_k` = 2 | 54.2 |
| `rel_k` = 4 | 50.9 |
| **`rel` = 1** | **49.9** |
| **`rel` = 0** | **49.8** |
| exploit layer removed | 46.1 |

What the ablations show:
- `sh_open` and `hu_sb_play` are not the leak.
- The exploit layer as a whole accounts for about 7 pts.
- About half of that is `rel=2`. Preflop, it counts a seat still to act in proportion to its
  VPIP. Tight seats behind therefore stop blocking exploit mode, and cand opens and steals
  with the exploit params into an attacker that punishes it.
- This fits the other agent's diagnosis of cand's leaks: shoves too wide, and folds too
  often to 3-bets.

## Round 2: hardening

1. **Population retune** (`arms_h1_pop.json`, `tune_h1_pop.log`).
   - Method: a tune.py variant that moves both ends of the exploit blend by the same
     delta, plus an intercept dimension, with `pool_w` pinned at 0.
   - Population: arms_br1 1.2, br_vs_ev_t4 0.4, cand 0.8, ev_t4 0.8, rival-strong 2.0,
     github 1.44, llm-bugs 0.96, self 15%.
   - Budget: pop 12, 300 SNGs, 6 gens.
   - Result: **no hardening**. br1 takes 54.5 from it, against 53.2 from cand. With about
     one attacker seat per table, the attacker's cost is lost in the noise next to the
     weak-seat harvest.
2. **arms_h1 = cand with `exploit.rel = 1`.** This is the one-knob fix the ablations point
   to.
   - The best attacker's take falls from 1.61x to 1.46x. The round-3 attacker br2,
     warm-started from br1 and tuned against h1, could not push it past that.
   - It is still worse than ev_t4 (1.34x).

## Round 4: arms_h1 vs cand A/B (`ab_h1_vs_cand_9991.txt`)

Settings: 1,500 paired SNGs, seed 9991, default points, normal blinds.

| field | A−B % of fair | ±se |
|---|---:|---:|
| gate-weak | −0.6 | 1.8 |
| gate-strong | +3.6 | 2.0 |
| gate-mixed | −2.3 | 2.0 |
| **rival-strong** | **−6.2** | 2.4 |
| **rival-strong+prep** | **−6.4** | 2.5 |
| rival-real | −2.0 | 2.5 |
| llm-bugs | −0.9 | 1.8 |
| github | −2.1 | 2.1 |
| sharks | −2.0 | 1.9 |
| competent | −1.7 | 2.1 |
| att-mix (br1, br2, prep, rival-strong) | +2.7 | 2.3 |
| att-br1 (7× br1) | +2.4 | 2.0 |
| att-br2 (7× br2) | +1.6 | 1.7 |

h2h 4v4: A gets 1.018x fair. The mean of the 10 standard cells is **−2.1%**.

The run was stopped before the fast schedule, because h1 had already failed the rule with
significant losses on rival-strong (−2.6 se) and rival-strong+prep (−2.5 se).

**Verdict: reject arms_h1.** `rel=2` is a leak against a tuned attacker, but it is also
where much of cand's edge over rival designs comes from. The trade isn't worth it unless
we expect an attacker tuned against us specifically, and that is impossible on the day:
opponents are anonymized and the code is unseen. **Keep cand_nlhe.**

Two caveats:
- The measured exploitability is a worst case against a bot built to beat cand, at a table
  of 7 copies of cand.
- In realistic tables (att-mix), cand gives up only about 2–3% of fair to h1.

## Files

- **Attackers:** `params/arms_br1.json`, `arms_br2.json`, `arms_br_ev_t4.json`, and the
  `*_cold` versions.
- **Hardening attempts:** `params/arms_h1.json` (rel=1), `arms_h1_pop.json`.
- **Ablations:** `params/arms_abl_noex`, `arms_abl_nosh`, `arms_b0m{1,2,3}`,
  `arms_nodegen`, `arms_rel0`, `arms_rel1`, `arms_relk{2,4}`.
- **Scratch drivers** (in the session scratchpad, not committed):
  - `attack.sh` runs the tune.py command above.
  - `tune_shift.py` is tune.py plus the shift-both-ends rule and an intercept dimension.
  - `ab_arms.py` is ab_test.py with three extra fields: `att-br1` = {arms_br1: 1},
    `att-br2` = {arms_br2: 1}, `att-mix` = {arms_br1: 1.5, arms_br2: 1.5, rival_prep: 1,
    rival-strong: 1 each}.

## If someone continues

- **Leave `rel=2` alone and fix base leaks instead.** Target the wide shoves (`pf_margin`,
  `pf_shove_scale`) and the 3-bet folds (`raise_cont`, `reraise_eq`). The tuner can't do
  this in our budget: one attacker seat is too little signal. It needs a 1-vs-7 objective,
  or about 10x the SNGs.
- **Or try a middle setting between rel=1 and rel=2.** `rel_k=4` took 50.9 against
  cand's 53.2, and its A/B was never run.

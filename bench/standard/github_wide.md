# Wide GitHub survey (Nov 6): about 50 new repos

Method: GitHub search API and topic pages, plus raw files read with WebFetch. Nothing was cloned or run.
Star counts and push dates are as of Nov 6, 2026. **[inf]** marks an inference.

**Biggest finding:** at least three public repos were written in the last two weeks to
prepare for *this* tournament (No Limit, Sequoia). Two of them contain LLM-written field
bots and field statistics.

## Repos found (new, not on the skip list)

**Prep for the same event**
- `DavidZaa/nolimit-bot` (0★, pushed Nov 5): a team's SNG simulator plus its bot, and 4 unmodified one-shot LLM field bots in `engine/field_llm/`.
- `SpatheGithub/nolimit-arena` (Nov 3): simulates 8 Claude-Opus "teams" building bots in 20 min, then 6 tournaments. Has `LESSONS.md` with field stats.
- `incrediblecrab/flops-to-calls` (Nov 2): 11 one-shot bots written by Claude and Copilot from the real rules, a mirror SNG, and results.
- `ryankkhalil19/microholdem` (Oct 29): sub-ms NLHE engine with CFR+ push/fold and river tables, an ICM DP and an SNG sim.
- `amalkoch/pokerbot-lab` (Kuhn/Leduc drills, ICM risk example).
- `aniketxdey/pokerbots` ("practice for no limit": a harness of ~45 ported public bots, MIT 2020–26, neuron_poker, PPE).
- Not read: `JordanCa0/pokerbot`, `nullptrabhi/pokerbot`, `gurmansaran/pokerbot_practice`, `justmycode37/Pokerbot`, `AadamAftab/PokerBot`, `Brady-5300/pokerBot`, `manofshad/PokerBot`. All were pushed Nov 2–6 **[inf: likely teams for this event]**.

**Hackathons and competitions**
- `TimoJanssen1/tumbleweed`: Fullhouse 2026, 4th in the international final.
- `advitrocks9/fullhouse-bot` (10★): Deep CFR, 6-max, 15th of 64 in the final.
- `gonfdcg/fullhouse-poker-bots`: range-aware MC.
- `guardiancarefl/pokerbot`: 6-max SNG, Deep CFR + PSRO, ICM value function; no numbers on the page.
- `gtowizard-ai/mitpoker-2024` (76★): depth-limited runtime solving with all-in leaf values and a per-street TimeManager.
- MIT, IIT and Huskyholdem bots and engines:
  - `iitpokerbots/bot-engine-2026`
  - `kartikya2207/poker__bot_engine_kartikya`
  - `Bhavana-B-del/IITM-Pokerbots-2025`
  - `abh-win/auction-poker-bot`
  - `jesusCaraball0/pokerbots-2025` (DQN)
  - `mitpokerbots/class-resources-2025` and `-2026`
  - `kipiiler/poker-client`
  - `fallenraze/o72-unc-pokerbots`
  - `alexwaeseperlman/Pokerbots`

**Solvers and RL**
- `b-inary/postflop-solver` (380★), `wasm-postflop` (603★), `desktop-postflop` (355★): DCFR in Rust, suspended.
- `noambrown/poker_solver` (171★): river CFR/CFR+/DCFR/MCCFR.
- `krukah/robopoker` (229★, active).
- `MatthewPDingle/GTOpen` (78★): multiway preflop with ICM/payouts, GPU.
- `EricSteinberger/Deep-CFR` (336★).
- `ozzi7/Poker-MCCFRM` (113★).
- `elliottneilclark/rs-poker` (185★).
- `Lorekp/Pokerbot`: AoF CFR/RL.
- `hchen13/poker-gto-engine`: HU CFR+ as an LLM skill.

**Charts and ICM**
- `Julian-cloud-max/holdemmath-data`: push/fold JSON, HU/6/9-max, 4–20 bb, no ICM.
- `emanuelebermani/gto-poker-trainer`
- `sclav004dsbets-ux/burbuja`: Nash+ICM push/fold.
- `null22277/icm-calculator`: Malmuth-Harville plus Tysen's SICM.
- `piyoSakai/bubble-factor-mtt`
- `hft-studio/pokerdata-mcp`
- `cbaezp/Pokeria`
- `ghost11re/PokerICMPro`

**Opponent modelling and LLM agents**
- `rosbo/texas-holdem-poker-ai` (146★)
- `THETILTED1/TiltStack`
- `SonghaiFan/frankie-poker`
- `whoAngeel/pokerhub`
- `YiCheng996/TexasHoldemAgent` (29★)
- `bubbleptr/dsh-holdem`
- `kailiu0712/LLM-based-Opponent-Modeling-in-Heads-up-Poker`
- `uoftcprg/phh-dataset` (119★, hand histories)
- `PokerBotAI/awesome-poker-ai`, `apehex/awesome-poker` (lists)

**Avoid.** `a9876543245/DEEPFOLD-SOLVER` (415★), `luizfellipelopes65-ai/gto-poker-solver-lab`,
`Jotaeme961/gto-poker-solver-arena`, `ravinsen0102-star/RangeSoprano-Trainer` and
`dynamic95-lab/poker-trainer-lab` were all pushed on Nov 5–6 and carry about 55 stars each.
Most are HTML "2026 Trainer Suite" repos that ship a Windows app. That's the pattern of a
malware lure **[inf]**. Don't download them.

## Field evidence relevant to us (strongest first)

1. **nolimit-arena `LESSONS.md`.** Claude-built field, 8 bots, 6 tournaments, two events.
   - The AI field folds **73–81% to 3-bets** and **82–83% to shoves**, and over-applies ICM to calls (calls off at about 62% equity 8-handed).
   - **Both event winners were re-shovers** (b06): they re-shoved single opens at 8–30 bb.
     - Event 1: priced from the opener's fold-to-3-bet, prior 0.75 with weight 4.
     - Event 2: jammed when EV > 0.1 pot, assuming the opener calls with 45% of its open range. That gave 7.1 3-bets per 100 hands (others 1.3–3.4), 90% of them all-in and 79% uncontested, for +11.4 bb/100.
   - Re-steal rate vs final rank: ρ ≈ 0.83 (event 1), 0.69 (event 2).
   - **Ungated, the re-steal lost −5.2 vs a loose house zoo.** Gated on table VPIP ≤ 0.30, it scored −1.4 to +1.4.
   - Winners took *more* 7th/8th places (32%) but more 1sts. Under 100/60/40/25/15/10/5/0, 2nd instead of 1st costs 40 points.
   - Under doubling blinds, 0 of 6,000 tables reached the 200-hand cap.
   - Timeouts came from 0.45–0.5 ms MC budgets hitting 2–2.7 ms CPU peaks under load, and from an 8-player ICM call in `observe()`.
2. **flops-to-calls mirror** (2,000 SNGs, 1 ms limit, payouts 10/6/4/3/2/1/0/0, fair share 3.625; blinds 10/20, 15/30, 25/50, 50/100 … 200/400, 25 hands per level; 46–48% of tables hit the cap).

   | Bot | Seed 11 (mean pts) | Holdout seed 21 | Timeouts (seed 11) |
   |---|---|---|---|
   | ghcp_1 | **4.15** | 4.18 (1.15× fair) | 94 |
   | claude_2 | 3.73 | 3.61 | 7 |
   | claude_4 | 3.36 | 3.36 | 4 |
   | ghcp_2 | 3.33 | 3.36 | 55 |
   | claude_3 | 3.19 | 3.11 | 6 |
   | claude_1 | 3.07 | 3.23 | 6 |
   | adaptive (hand-built) | 2.78 | 2.72 | 17 |
   | tag (hand-built) | 2.39 | 2.42 | 3 |

   One-shot LLM bots beat the hand-built ones. So the realistic field is *formula-heavy LLM code*, not hobby bots.
3. **Fullhouse (tumbleweed).** The real top-64 field folded **87–88% to 3-bets** (MDF about 50%), 81% to a single open and 73% to a pot-sized bet. Gunslinger won by 3-betting about a third of hands, 4-betting its own opens and never 5-bet bluffing.

## (a) New archetypes to add to `rivals.py` (all specs read from source)

**A1 `llm_codex_tag`: the shared LLM default.** claude_2, claude_4 and DavidZaa llm2 share almost the same numbers, so this is the modal 60-minute build **[inf]**.
- **Open percentile** by players behind: 0:0.30 (bug: non-monotone), 1:0.45, 2:0.36–0.40, 3:0.27–0.28, 4:0.21, 5:0.17, 6:0.14, 7:0.12. Heads-up 0.65–0.75. ×0.55–0.6 per limper.
- **Open size:** 2.2 bb (eff < 25) or 2.5 bb, 3.0 bb with one player behind, +1 bb per limper.
- **Push/fold:**
  - Zone: eff ≤ 12–13 bb.
  - Push % = base[n] × (10/bb)^0.7–0.8, with base = {0:.55–.60, 1:.58, 2:.37–.40, 3:.27–.30, 4:.21–.24, 5:.17–.20, 6:.145–.17, 7:.125–.15}, ×0.9 if "ICM".
- **Facing an open:** raiser range r = (pfr + 0.15·8)/(h + 8), ×0.35 at the 3-bet level, ×0.2 at the 4-bet level.
  - 3-bet when p ≤ max(0.025, 0.22–0.3·r), to 3.0× IP or 3.6× OOP.
  - Call when p ≤ 0.65 r (0.9 r in the BB), with cost ≤ 8% (12% in the BB) of stack.
  - Facing a 3-bet: continue with the top ~3% only.
- **Committed rule:** to_call ≥ 35% of stack makes it jam-or-fold.
- **Sizing tell:** any raise ≥ 0.40–0.75 of the stack becomes all-in.
- **Postflop:** made-strength table, then hm = hs^(1 + 0.6–0.7(n−1)).
  - Value bet at hm ≥ 0.6–0.75, 0.6–0.72 pot.
  - Heads-up flop c-bet p = clamp(1.6·ftb − 0.1, .1, .85), 0.4–0.55 pot.
  - Facing a bet: discount = (0.03–0.05 + 0.07–0.08·size)·(1.35 − agg), raise at ≥ 0.78–0.88.
  - **No river bluffs.**
- **"ICM"** is only a flat margin: +0.03 needed when calling ≥ 50% of the stack.
- **Bugs:**
  - The fallback folds facing a bet.
  - "10" cards are parsed as rank 2.
  - All-in opponents count in the multiway exponent.
  - Shoves are detected as raises ≥ 0.85–0.9 of the starting stack.
- **Exploit:** 3-bet light (they continue with the top ~3%), and value-bet big on the river.

**A2 `ghcp_fastrange`: Copilot/GPT one-shot (best of 11).**
- **Opening width** by players behind: .65, .49, .45, .34, .27, .23, .20, .17 (heads-up .80), minus 1.1·risk.
- **Open size:** 2.15 bb if eff < 30, else 2.35 bb (+.35 bb with one player behind).
- **Push:** ≤ 11 bb if pct ≤ 0.84·open + .015 (+.10 at ≤ 5 bb, +.12 at ≤ 3 bb).
- **Facing a raise:**
  - Value 3-bet: pct ≤ min(.065, max(.028, .19·w)); .018 at the 4-bet level, .009 above.
  - Light 3-bet only with A2s–A5s vs width > .30, fold rate > .5, at 13% frequency.
  - Call: pct ≤ w·(.78 IP / .60 OOP), +.13 in the BB.
  - **Bug:** preflop never reads pot odds or equity, because the equity code is dead.
- **Postflop:**
  - MC vs sampled ranges: 96 samples (256 heads-up on the river), equity deadline 0.63 ms, ICM only if under 0.23 ms.
  - Value bet when eq ≥ .59 + .045(n−1) + .025 on the river.
  - Bluff flop/turn with p = .10 + .13 (aggressor) + .09 (IP) + .16 (draw) + .5·(fold − .43).
  - Exact ICM, heads-up only, when calling ≥ 30% of the stack.
  - "coin" is a deterministic hash of the visible state.
- **Timeouts:** 0.28 per 1k decisions.

**A3 `llm_pushfold4`: DavidZaa llm4.**
- **Push/fold at ≤ 15 bb:**
  - Prior = clamp(5.8/bb/n^0.75, .025, 1).
  - **Bug:** n = all live opponents, not players behind.
  - Real Malmuth-Harville at 50/30/20, blended toward chip rank from hand 150 to 200.
  - Villain ICM awareness 0.6.
- **Deep (> 15 bb):**
  - Opens pct ≤ min(.55, .9/(behind + 1.2)) to 2.3 bb.
  - 3-bets the top 3%, calls the top 8% if ≤ 12% of the stack, jams the top 2% vs a 3-bet.
  - BB defends the top 35% for ≤ 1.5 bb.
- **Bug:** in the shove branch (to_call ≥ 35% of the stack or ≤ 15 bb) it can't flat-call.
- **Postflop:** tiers. Two pair+ raises to 3×. TPTK calls pot odds ≤ .42 (≤ .34 on the river). Weak pair ≤ .25. Gutshots count as strong draws.
- **Bug:** two pair on a paired board is misclassified.

**A4 `llm_mc_mwbug`: DavidZaa llm3.**
- 0.3 ms wall-clock MC vs Chen-ranked ranges.
- **Bug:** thresholds are scaled as h^(n^0.75), so the 0.62 bet threshold falls to about 0.13 at 7 opponents: it **bets and raises with average hands multiway** while its call threshold stays unscaled.
- Every call at ≤ 15 bb becomes a re-shove, and every raise at ≤ 25 bb is all-in.
- Risk premium 0.05·share, applied only when the call is ≥ 25% of the stack.

**A5 `llm_strong1`: DavidZaa llm1.**
- **Opening width:** 0.52/n^0.78, × (fold-to-raise behind / 0.6)^1.2 clamped to [.65, 1.5].
- **Facing a raise:**
  - 3-bet when eq ≥ .555, to 3.0×/3.6×.
  - Call if eq·(.90 IP / .84 BB / .78 other) ≥ need.
- **Survival premium:** .05–.06 × risk fraction (+.04 for the chip leader after hand 180).
- **Postflop:**
  - Shoves instead of calling when the stack left after calling is < 30% of the pot.
  - bluff_f = clamp(ftb/.4, .2, 1.5).
- **Priors (pseudo-counts):** VPIP .28/8, PFR .14/8, fold-to-raise .6/6, fold-to-bet .4/6.

**A6 `arena_reshover`: nolimit-arena b06, the winner.**
- TAG base (opens ~14% with 7 behind, 3-bets top 3.5%, continues vs 3-bets with the top 2–5%).
- **Plus:** at 8–30 bb, vs a single open, jams if EV > 0.1 pot, assuming the opener calls 45% of its open range. Gated to tables with VPIP ≤ 0.30.
- Similar to the existing `LlmResteal`/`rvh_jam`, but wider and EV-priced from any position **[inf]**. A copy (or 2) of this is the most likely strong opponent.

**A7 `team_policybot`: DavidZaa's own bot (a real team).**
- **Steals:** P(all behind fold) is the product of per-seat fold-to-steal. At ≥ 0.9 it steals any two; otherwise the range × (observed/assumed fold), clamped to [0.5, 3].
- **"Broken" seats** (no voluntary chips yet) are removed from the players behind.
- **ICM:** bubble factor tightens calls vs the raiser and first-in shoves vs the deepest stack behind.
- **C-bets:** air only heads-up vs fold ≥ .35. 3/4 pot vs stations (ftb < .25).

**A8 `cfr_pushfold`: microholdem.**
- HU CFR+ push/fold tables 1–25 bb (SB jams 58.4% at 10 bb), plus a multiway first-in jam model, then an ICM re-check.
- Deep: positional thresholds.
- Postflop: MC vs ranges, 100 µs budget, ≤ 800 samples.
- HU river: CFR+ 10-bucket tables.
- A near-Nash short-stack player: hard to exploit, and it punishes our over-wide jams.

**A9 `gunslinger`: Fullhouse 4th place.** 3-bets about 33% vs opens, 4-bets its own opens, never 5-bet bluffs, multiway eq^(1 + .35(n−1)).

## (b) Techniques that might beat ours

1. **Enable a gated re-steal (highest value).**
   - **What we have:** `runtime._resteal` exists, but `resteal_on = 0` in every shipped param (`ev_t4`, `cand_nlhe`, `x_nlhe`) and is in `TUNE_EXCLUDE`. Its code notes "No fold-to-3-bet stat is kept", and it uses the postflop fold_to_bet instead.
   - **Change:** add a per-seat `f3b` (fold to 3-bet/jam over their open) with prior 0.75, weight 4. Enable `resteal_on = 1` at 8–30 bb, gated on the table's mean VPIP ≤ 0.30, or per opener on λ from the exploit layer.
   - **Expected benefit:** in two independent AI-field simulations it was *the* winning mechanism (ρ 0.7–0.8 with rank). The field folds 73–88% to 3-bets.
   - **Risk:** −5% ungated vs loose fields, and more 7th/8th finishes. Payout-dependent: good when 1st ≫ 2nd.
   - **Test:** ab_test on `rival-*` plus new A1/A6. Cost is about 10 µs, only when there's one open.
2. **Fold-to-steal product for opens.** `_preflop` line ~1568 widens on mean VPIP behind to the power 0.5·steal_exploit. Replace or augment it with ∏ fold_to_steal(s) over the players behind. Remove dead seats (0 voluntary chips after ≥ 8 hands) from the "behind" count. Allow any two when the product is ≥ 0.9.
   - **Benefit:** vs timeout/crashed bots (rivals `rv_buggy`, zoo `timeout`). HANDOFF says timeout styles currently show about 0 gain.
   - **Risk:** low.
3. **Light deep 3-bet (> pf_bb).** Today the re-raise needs equity vs the observed range. Add a bluff 3-bet with A2s–A5s and suited broadways vs openers with PFR > .30 and f3b > .6, at 3.0× IP / 3.6× OOP. This exploits A1, which continues with the top ~3%.
4. **Exact HU river tables (microholdem's CFR+, 10 buckets, 0.5–4 pot).** These could replace the EV choice only on heads-up rivers.
   - **Benefit:** balanced bluffing vs our current value-weighted logistic continue model.
   - **Risk:** our exploit edge comes from reads, and GTO tables give it up. Expected gain is small vs the LLM field **[inf]**. Low priority.
5. **Cap logic depends on the schedule.** 46–48% of tables hit the cap under +5–10 bb per level, and 0% under doubling. Keep `cap_hands` gated on the announced schedule (day.py).
6. **Timing hygiene** (confirms what we already do): keep `observe()`/hand-end callbacks O(1). Others timed out with 0.45–0.63 ms MC deadlines under load. We're fine at p99.9 ≈ 0.4–0.7 ms.

Not better than ours: Deep CFR (fullhouse-bot, 2 s/decision, 6-max cash), GTOpen, postflop-solver, robopoker, Pluribus clones. None fit 1 ms Python 8-max ICM without offline tables we already approximate.

## (c) Standard-play references

- **HU 10 bb chip-EV Nash:** SB jam **58.4%** (microholdem CFR+, exploitability < 5e-5 bb). holdemmath-data says 45.4% jam and 29.4% call. That disagrees with standard Nash (about 57–58% / 37%), so don't trust that file. Check `gpu/pushfold.py` HU chip-EV output against about 58%.
- **holdemmath-data JSON:** depths 4/6/8/10/12/15/20 bb, ante 0 or 0.1 bb. Its 6-max 6 bb UTG jam of 84.6% comes from a "single-caller" independent solve and is far too wide **[inf]**, so it's unusable for multiway.
- **LLM-default tables** (A1/A2 above) are the ranges most opponents will actually use. Our open/steal ranges should beat them. Check that our BB calling range vs a 12 bb CO jam from that table (top ~27–30%) is wide enough. They over-fold, and they also jam wide when short.
- **Field stats** to set priors: fold to 3-bet 0.73–0.88, fold to shove 0.82–0.83, fold to a single open about 0.81. Our PRIORS (fold_to_bet .45) are looser than this, so a resteal prior of 0.75 fits.
- **ICM risk example** (pokerbot-lab): stacks 40/40/20, payouts 50/30/20. Break-even equity is 60.3% vs 50% chip-EV. Use it as a unit test for our bubble factor.

# Codex prompts: rebuild the fallback bot in the 60-minute build

Use these only if pre-written code is not allowed. Paste them in order. Each prompt is
self-contained, and each step ends in something you can submit.

**Before you start:**
- Have [FALLBACK_SPEC_LITE.md](FALLBACK_SPEC_LITE.md) open. You paste its sections into the prompts,
  and those sections carry the tables.
- One teammate drives Codex. The other reads the starter kit and checks each step in the
  kit's simulator.

| step | minutes | what you can submit after it |
|---|---|---|
| 1 | 0–8 | always-legal check/fold bot, wired to the kit |
| 2 | 8–18 | push/fold + opening bot (**submit this**) |
| 3 | 18–28 | + postflop buckets (**submit**) |
| 4 | 28–35 | + opponent stats and exploits (optional: measured gain ~0; do step 5 first if late) |
| 5 | 35–45 | tests, speed check, final submit |
| — | 45–60 | slack. Fix whatever the kit simulator shows. Don't add features. |

Submit after every step that passes the kit simulator, because resubmission is allowed every
5 minutes. The last good version is always live.

---

## Prompt 1: skeleton and safety (spec §0, §6)

```
Read the starter kit: the Agent template, how the bot receives game state, and the action
format. Then write bot.py as a single file using only the Python standard library.

1. A function `to_obs(state)` that converts the kit's state into a plain object with these
   fields:
   - hole, board: cards as (rank 2..14, suit 0..3)
   - street: 0 preflop, 1 flop, 2 turn, 3 river
   - seat, button
   - stacks, bets: per seat; bets are chips put in this betting round
   - in_hand: per seat, still has cards
   - pot: all chips in the middle, current bets included
   - to_call
   - min_raise_to (0 if raising is not legal), max_raise_to (my all-in total)
   - sb, bb, hand_no
   - history: list of (seat, street, kind, amount_to, all_in) for this hand, with kind
     0 fold / 1 call or check / 2 raise / 3 blind post
   If the kit lacks a field, derive it, for example from the action log.
2. A function `from_action(kind, amount)` that converts my (kind, raise-to total) into the
   kit's action format. If the kit uses raise-by, subtract my current bet.
3. A SpecBot class:
   - act(obs) puts the decision in try/except Exception, returning check if to_call == 0,
     else fold;
   - every action passes through legal(): a raise needs min_raise_to > 0 and is clamped to
     [min_raise_to, max_raise_to]; if raising is not legal, call; a fold with to_call == 0
     becomes a check.
   For now the strategy is: check if possible, otherwise fold.
4. At import: gc.collect(); gc.freeze(); gc.disable(). Call gc.collect() only in the
   constructor or the per-table reset, never in act().
5. Wire it into the kit's Agent template and run the kit simulator for a few games. Show me
   any errors.
```

## Prompt 2: preflop tables, push/fold and opening (spec §1, §2, §3)

Paste §0–§3 of FALLBACK_SPEC_LITE.md after this:

```
Implement the preflop strategy exactly as specified below, in bot.py.

- Paste the tables (HAND_ORDER, E1, EQR, BF_FULL, BF_SHARE, PF_STACKS, SHOVE, CALL, SH_OPEN)
  as literals and parse them at import.
- Functions: hand_name(hole), pct(name), eqr(name, y), bubble_factor(...), need(obs, villain),
  action_order(obs), and interp(row, eff_bb), which is linear between PF_STACKS and clamped
  at the ends.
- preflop(obs) follows §2 when eff_bb <= 21, else §3.
- Raise sizing goes through one helper: target, at least min_raise_to; jam if at least 85% of
  max_raise_to.
- Postflop stays check/fold for now.
- Opponent stats don't exist yet: make a stub rate(seat, name) that returns the priors
  (vpip .35, pfr .18, shove .06, fold_to_bet .45, agg .45), and stub jammer(seat) as False.

Then check these spot values and print them:
- pct("AA") ~= 0.0045 and pct("32o") == 1.0;
- eqr("AA", 0.05) > 0.75, and eqr("KQo", 1.0) == 0.61;
- SHOVE for 8 dealt, SB (pos 6) at 10 bb is 95%;
- heads-up, the SB at 10 bb shoves 59% times 1.167.
Run the kit simulator again and show me the results.

<paste FALLBACK_SPEC_LITE.md §0-§3 here>
```

## Prompt 3: postflop (spec §4)

Paste §4 after this:

```
Implement postflop(obs) exactly as specified below.

- post_bucket(hole, board) returns 0..12, using a small category function (no full evaluator
  is needed): rank and suit counts, and a straight check with the ace also low.
- board_feats(hole, board) returns (hi, lo, flush_board, connected_board, paired_board).
- e1 = POST_EQ[street][bucket]/100 + dot(ADJ[GROUP[bucket]], features), clamped to
  [0.02, 0.99]. Paste the POST_EQ and ADJ tables exactly.
- Equity vs k opponents is e1 ** (k ** 0.88). The aggression adjustment uses rate(seat, "agg").
- Value bet / bluff / raise / call rules use the exact numbers given. The bluff uses
  random.random() from a Random seeded once in the constructor.

Then write these unit checks:
- AhAd on 2c7d9s -> 7;
- AhKd on Ac7d9s -> 6;
- 9h9d on 9c7d2s -> 9;
- Ah5h on Kh7h2s -> 2;
- Ah5h on Kh7h2h -> 11;
- 2c3d on KhKd9s9cAh -> 0.
Run the kit simulator.

<paste FALLBACK_SPEC_LITE.md §4 here>
```

## Prompt 4: opponent model and exploits (spec §5, optional)

Paste §5 after this:

```
Replace the rate() and jammer() stubs with a real per-seat model, as specified below.

- Seat counters: hands, vpip, pfr, shove, faced, folded, aggr, passive, acts, allin.
- ingest(history) updates them once per finished hand. Use the kit's hand-end callback if it
  has one. Otherwise, when hand_no changes, ingest the last history seen for the previous
  hand. Keep a set of ingested hand numbers so a hand is never counted twice.
- rate = (count + prior*6) / (opportunities + 6).
- jammer = acts >= 5 and allin >= 0.9*acts.
- Reset all stats when a new table starts (the per-table hook, or a change in seat count).

Exploits E1-E4 are already in the preflop/postflop code through rate(). Check they now use
real stats: in the kit simulator, a table of always-fold bots should get stolen from almost
every hand.

<paste FALLBACK_SPEC_LITE.md §5 here>
```

## Prompt 5: tests and speed (spec §6)

```
Write test_bot.py:
1. 5,000 random observations: 2-8 seats, every street, stacks 0-60 bb, to_call 0 / 1 bb /
   3 bb / all-in, some with min_raise_to = 0. Assert every action is legal (a raise is
   within [min_raise_to, max_raise_to] and only when min_raise_to > 0; never fold with
   to_call == 0) and that nothing raises an exception. Print p50/p99/max decision time with
   time.perf_counter(). The p99 must be under 0.2 ms.
2. act() given a broken observation (missing fields) returns check/fold without raising.
3. Ten full games in the kit simulator with 0 errors and 0 timeouts.
Fix anything that fails. Don't change the strategy numbers.
```

## If something goes wrong

- **The kit's state looks different:** fix only `to_obs` and `from_action`. Everything below
  them works on the normalized fields.
- **Timeouts in the kit:** look for logging, deep copies of the state, or anything that walks
  the whole game history every decision.
- **The bot is losing badly in the kit simulator:** check the position convention first
  (`pos 0` is first to act preflop, and the SB is `n-2`), then raise-to vs raise-by.
- **The variant is not NLHE:** see the end of FALLBACK_SPEC_LITE.md. Ask Codex for a 2-minute
  Monte Carlo that rebuilds HAND_ORDER, E1 and POST_EQ, and keep everything else.

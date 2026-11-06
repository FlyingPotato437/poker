# Fallback spec: our bot, rebuilt from notes in 20–30 minutes

Use this only if pre-written code is **not** allowed at the event. It describes the parts of
our bot that matter most, in priority order, with every number needed. Codex builds it from
these notes alone, using the prompts in [CODEX_FALLBACK_PROMPTS.md](CODEX_FALLBACK_PROMPTS.md).
The reference implementation is `fallback/spec_bot.py` (about 600 lines, stdlib only). It is
measured in [bench/fallback/](bench/fallback/).

The game assumed is NLHE: 8 seats, 2,000 chips, blinds 10/20 rising every 25 hands, a
200-hand cap with ICM, 1 ms per decision. For another variant, keep sections 0, 5 and 6, and
replace the tables in section 1 (see the end of this file).

**If time is short, build in this order** (from the ablations below):
1. Section 6 (safety), the push/fold charts (§2) and opening (§3). A preflop-only bot that
   checks and folds postflop scores 1.35x fair.
2. Postflop buckets **with the ADJ feature terms** (§4): +17% of fair over step 1. This is
   the biggest single lever; the buckets without ADJ lose a further 12%.
3. Opponent stats (§5): no measurable gain on these fields (−2 ±4%). Do this last, or skip it.

Push/fold covers every decision at or below 21 bb, which is most of the second half of each table.

## Measured (`scripts/ab_spec.py`, files in `bench/fallback/`)

The spec bot against our full bot (`prep:params/ev_t4.json`): 800 paired SNGs per cell,
default points, seed 9701. Both bots sit in the same seat against the same field and the same cards.

| blinds | field | spec x fair | full bot x fair | spec − full, % of fair |
|---|---|---|---|---|
| normal | github | 2.02 | 2.12 | −9.1 ±4.7 |
| normal | llm-bugs | 1.78 | 1.94 | −16.2 ±4.0 |
| normal | rival-real | 1.26 | 1.38 | −12.1 ±4.3 |
| normal | gate-mixed | 1.74 | 1.96 | −22.6 ±4.3 |
| fast | github | 1.71 | 1.76 | −4.9 ±4.7 |
| fast | llm-bugs | 1.50 | 1.63 | −13.0 ±4.4 |
| fast | rival-real | 1.09 | 1.15 | −6.0 ±3.7 |
| fast | gate-mixed | 1.50 | 1.66 | −16.0 ±4.3 |
| | **mean** | **1.57** | **1.70** | **−12.5 ±1.5** |

**Head-to-head** (4 spec + 4 full bots): spec 0.93x fair at normal blinds and 0.99x at fast.

**Reading it:**
- The spec bot keeps about 93% of the full bot's score against LLM-style fields.
- `params/cand_nlhe.json` is a further +10% over ev_t4, so the gap to our newest bot is about 20%.

**Where the rest goes** (seed 77, rival-real, 200 SNGs, `bench/fallback/diag_77.txt`):
- **Postflop equity is most of it.** With the bundle's equity net in place of the buckets,
  the spec bot gains 15% of fair; the ADJ terms recover most of that.
- **The preflop range-equity fit costs nothing measurable.**
- **The rules engine itself** (`nlhe_final_legacy` on exact tables) sits about 10% below the EV engine.

---

## 0. Conventions

- **Actions:** `FOLD = 0`, `CALL = 1` (a check when `to_call == 0`), and `RAISE = 2` with a
  *raise-to* total. If the kit uses raise-by, convert at the adapter.
- **Cards:** rank 2..14 (A = 14) and suit 0..3. Parse `"As"`, `"Td"` and `"10h"`, or ints
  with `rank = c // 4 + 2` and `suit = c % 4`.
- **Hand name:** higher rank first, then the lower rank. Pairs have no suffix (`"77"`), and
  other hands end in `s` (suited) or `o` (offsuit). Examples: `AKs`, `T9o`.
- **Percentile `pct(hand)`:** walk `HAND_ORDER` (§1) and add up the combos (pair 6, suited 4,
  offsuit 12), dividing by 1326. A hand's percentile is the share of hands at least as strong.
  "Play the top x" means `pct <= x`. AA = 0.0045 and 32o = 1.0.
- **Positions:** take the order of the seats dealt in, starting with the first to act preflop.
  So `pos = 0` is UTG, `n-2` is the SB and `n-1` is the BB. Heads-up, the SB/button has
  `pos = 0`.
  - `n` = number of seats dealt in this hand.
  - `behind` = seats after me in that order that are still in and not all-in.
- **Effective stack:** `eff_bb = min(my stack + my bet, the biggest opponent stack + bet) / bb`.

## 1. Tables (paste as literals)

```python
HAND_ORDER = """AA KK QQ JJ TT 99 88 AKs 77 AQs AJs AKo AQo ATs AJo KQs 66 A9s KJs ATo A8s KTs KQo A9o
A7s QJs KJo 55 K9s A6s A5s KTo QTs A8o A4s A7o A3s K8s QJo K9o A5o K7s A6o JTs Q9s QTo
A2s 44 K6s A4o Q8s A3o K8o K5s K7o J9s Q9o A2o JTo K4s Q7s K6o T9s J8s K3s Q6s K5o Q8o
33 J9o K2s Q5s J7s K4o T8s Q4s Q7o K3o J8o T9o T7s Q6o 98s Q3s J6s K2o 22 J5s Q2s Q5o
J7o Q4o T8o J4s T6s 97s Q3o J3s 98o T7o 87s J6o 96s J2s Q2o J5o T5s J4o T4s 86s 97o T6o
95s T3s J3o 76s 87o T2s 85s J2o T5o 96o 94s 75s T4o 86o 93s 65s 84s T3o 95o 92s 76o 74s
54s T2o 85o 64s 83s 94o 82s 75o 65o 93o 73s 53s 63s 84o 92o 43s 74o 72s 54o 64o 52s 62s
83o 82o 42s 73o 53o 63o 32s 43o 72o 52o 62o 42o 32o"""
# HU equity % vs a random hand, same order (169 numbers)
E1 = """85 82 80 77 75 72 69 67 66 66 65 65 64 65 64 63 63 63 63 63 62 62 61 61 61 60 61 60 60
60 60 60 59 60 59 59 58 58 58 58 58 58 58 58 58 57 57 57 57 57 56 56 56 56 55 56 55 55
55 55 54 54 54 54 54 54 53 54 54 53 53 53 52 52 52 52 52 51 52 52 51 51 51 51 51 50 50
50 50 50 50 49 50 49 49 49 48 48 48 48 48 48 47 47 47 47 47 46 47 46 46 46 46 46 45 45
45 45 45 44 44 44 44 44 44 43 43 43 43 43 43 42 42 42 42 42 41 41 41 41 40 40 40 40 40
40 39 39 39 39 39 38 38 38 38 38 38 37 37 37 36 36 36 35 35 34 34 33 32"""
```

**Equity vs a range `eqr(hand, y)`:** this is the heads-up equity against the top-`y` share
of hands.
- Compute `r = ln(clamp(pct/y, 0.05, 20))` and `L = logit(E1/100)`.
- At each grid row, `z = c0 + c1*L + c2*[pair] + c3*min(r,0) + c4*max(r,0)`.
- Interpolate `z` linearly in `y` between rows, then take `eq = 1/(1+e^-z)`.
- Clamp `y` to [0.03, 1]. At `y = 1`, `eq = E1`. The mean error is 0.02.

```python
EQR = [  # y,     c0,     c1,     c2,     c3,     c4
 (0.03, -0.950, 0.629, -0.497, -0.971, -0.110), (0.06, -0.821, 0.350, -0.078, -0.657, -0.057),
 (0.10, -0.682, 0.215,  0.025, -0.554, -0.077), (0.15, -0.572, 0.182,  0.036, -0.480, -0.118),
 (0.20, -0.548, 0.218,  0.030, -0.438, -0.114), (0.30, -0.549, 0.430,  0.019, -0.344, -0.010),
 (0.45, -0.488, 0.793, -0.048, -0.206,  0.227), (0.65, -0.308, 1.056, -0.091, -0.078,  0.551),
 (1.00,  0.000, 1.000,  0.000,  0.000,  0.000)]
```

**ICM bubble factor `BF`:** this is how much a lost chip is worth relative to a won chip. It
comes from points 100/65/45/30/20/12/6/0.
- `n` = players with chips, `f` = call / effective stack, and `sh(x) = x / total chips`.
- Class each stack as short (`sh < 0.7/n`), big (`sh > 1.4/n`) or even, for both hero and villain.
- Then `BF = 1 + (BF_FULL[n]-1) * BF_SHARE[hero class][villain class] * f**1.2`.
- Weight it as `bf = 1 + 0.96*(BF-1)`.

```python
BF_FULL  = {2: 1.00, 3: 1.41, 4: 1.57, 5: 1.64, 6: 1.73, 7: 1.75, 8: 1.76}
BF_SHARE = [[0.41, 0.53, 0.81],   # hero short  vs villain short / even / big
            [0.29, 1.00, 1.49],   # hero even
            [0.15, 0.44, 2.36]]   # hero big
```

**Equity needed to call:** `need = bf*c / (bf*c + pot)`. Here `c = to_call` and `pot` is every
chip already in the middle, current bets included.

## 2. Push/fold at `eff_bb <= 21`: the biggest single edge

These are ICM Nash charts solved for the default points. Columns are `eff_bb` in
`PF_STACKS = 2 3 4 5 6 8 10 12 15 18 21`; interpolate linearly, and clamp outside the range.
Values are the top % of hands.

**Open-shove when folded to you.** Each row of a cell is one position, `pos = 0 .. n-2`:

```python
SHOVE = {
 2: "90 78 74 74 70 65 59 54 48 41 37",
 3: "36 49 51 49 46 44 40 34 28 25 21 | 67 77 78 77 75 69 64 63 57 52 47",
 4: "34 45 42 43 41 36 29 25 21 19 16 | 38 51 52 52 54 50 45 39 32 24 22 | 68 80 85 84 86 82 82 73 68 62 62",
 5: "31 37 38 37 33 26 24 21 17 15 13 | 33 43 44 46 43 39 29 27 22 21 17 | 37 51 51 53 54 53 48 41 32 26 26 | 69 83 87 87 88 87 86 82 76 71 66",
 6: "28 32 33 27 26 23 18 17 15 14 14 | 30 37 39 38 33 27 24 20 17 16 15 | 34 43 44 46 44 38 31 28 25 22 18 | 37 50 53 55 56 54 54 42 34 28 26 | 70 83 87 88 94 95 90 91 83 80 67",
 7: "26 28 26 23 24 18 17 15 14 13 12 | 28 31 32 27 26 23 19 17 15 14 14 | 30 36 37 38 34 27 23 21 18 16 15 | 33 42 44 46 44 38 31 28 24 24 19 | 36 49 54 56 57 54 54 43 37 27 27 | 69 84 87 91 96 97 91 92 84 82 69",
 8: "22 24 22 23 19 17 15 14 14 12 8 | 25 28 26 25 25 18 18 15 15 14 13 | 28 32 33 27 27 23 20 19 15 15 15 | 30 36 39 39 33 29 25 22 19 16 16 | 33 43 46 46 47 37 32 28 26 22 20 | 37 49 54 58 60 56 55 50 37 30 31 | 71 85 91 95 97 100 95 97 89 83 75",
}
```

**Shoving:**
- **Chart value:** `thr = SHOVE[n][pos](eff_bb)`.
- **Exploit E2:** if anyone is behind, multiply by `(0.35 / avg VPIP of those behind) ** 0.805`.
- **Scale:** multiply by **1.167**, cap at 1, then shove if `pct <= thr`; otherwise fold.
- **Limped to you in the BB** (`to_call == 0`): there is no chart row, so use
  `thr = 0.9/(1+0.35*len(behind)) * sqrt(6/eff_bb)`. Shove if `pct <= 0.6*thr`, else check.

**Calling an all-in.** Each key is the top % of hands:
- `"hu"` heads-up;
- `"3:KJ"` with 3 dealt;
- `"KJ"` with 4 or more dealt.

`K` is the number of players behind the shover when he shoved (`n-1-shover_pos`, capped at
4), and `J` is the number still behind you (`n-1-pos`, capped at 2).

```python
CALL = {
 "hu":   "99.9 92.7 72.7 61.7 54.7 44.6 38.4 32.8 27.5 23.4 20.7",
 "3:10": "91.8 60.1 48.8 40.5 35.4 28.3 23.2 19.3 15.7 13.2 11.5",
 "3:20": "80.5 41.9 32.8 27.5 23.2 17.2 13.6 10.6 8.4 7.1 6.1",
 "3:21": "8.6 15.2 13.7 12.2 11.1 9.8 8.5 8.0 7.1 5.8 5.4",
 "10": "70.7 49.6 39.0 32.4 27.3 21.0 17.1 14.4 11.7 9.8 8.5",
 "20": "53.0 32.2 25.6 20.2 17.3 12.4 9.3 7.7 6.2 5.4 5.1",
 "21": "14.6 15.3 12.5 11.5 9.7 8.5 7.5 6.5 5.4 4.6 3.3",
 "30": "49.7 28.5 21.0 16.3 12.8 8.5 6.9 5.7 5.2 3.6 3.0",
 "31": "13.1 12.9 10.7 9.0 8.1 7.0 5.5 5.3 3.3 3.0 2.9",
 "32": "6.7 7.2 7.1 6.8 6.4 5.4 5.0 3.4 3.0 3.0 2.5",
 "40": "39.6 20.9 13.4 9.9 7.7 5.8 4.4 3.7 2.9 2.5 2.1",
 "41": "11.7 9.8 8.2 7.0 6.1 4.7 3.9 2.9 2.5 2.1 1.8",
 "42": "6.2 6.1 5.6 4.8 4.2 3.3 2.7 2.4 2.0 1.7 1.5",
}
```

**Calling:**
- **Before reads** (the shover has fewer than 12 hands seen): call if
  `pct <= CALL[key](eff_bb) * 1.348`. The opponents in this field shove wider than Nash.
- **Exploit E3:** if the shover has 12 or more hands, or is a jammer (§5), use
  `y = clamp(1.5 * max(shove_rate, 0.8 * pfr), 0.02, 1)`, with `y = 1` for a jammer. Call if
  `eqr(hand, y) >= need + 0.019`.
- **Multiway:** if more than one opponent is in, call only if the rule above says call and
  `eqr(hand, 0.08) >= 0.5`.
- **Facing a non-all-in raise at `eff_bb <= 21`:** same rule. Jam if calling, otherwise fold.

## 3. Preflop at `eff_bb > 21`

**Nobody raised, `to_call > 0` (open or fold):**
- **Base threshold:** `n_others = max(n-1, 1)` and
  `thr = 0.264 + (0.426-0.264) * (1 - len(behind)/n_others)`.
- **Short-handed curve:** `thr = max(thr, 1.15 * SH_OPEN[min(len(behind),7)])`, with
  `SH_OPEN = (0.50, 0.50, 0.42, 0.28, 0.23, 0.19, 0.16, 0.14)`. This is what makes the HU SB
  and 3-handed button open wide.
- **Limpers:** if anyone limped, `thr = 0.103` (isolate).
- **Exploit E1 (steal):** `thr = min(1, thr * (0.35 / avg VPIP behind) ** 1.015)`.
- **Raise or limp:** if `pct <= thr`, raise to `2.965*bb + limpers*bb`. Otherwise, in the SB
  with no limpers and `to_call <= bb/2+1`, complete if `pct <= 0.727` (0.80 heads-up).
  Otherwise fold.

**No raise, `to_call == 0`** (our option after limps): raise to `(3 + limpers)*bb` if
`pct <= 0.103`, else check.

**Facing a raise:**
- **Raiser's range:** `y = PFR(raiser) * 0.438**(raises-1)`. If the last raise was all-in,
  `y = min(y, 2.5*shove_rate)`, and if the raiser is a jammer, `y = 1`.
- **Equity:** `eq = eqr(hand, clamp(y, .01, 1))`. Multiway, `eq **= 1 + 0.6*(opponents-1)`.
- **Re-raise:** if `eq >= 0.588`, there are fewer than 4 raises and raising is legal, re-raise
  to `3.22 * max(bets)`. Jam instead if that is at least 35% of my stack.
- **Call or fold:** call if `0.922*eq >= need(raiser)`, else fold.

**Raise sizing:**
- Use `max(min_raise_to, target)`.
- If that is at least 85% of the all-in amount, jam.
- Never go past `max_raise_to`.

## 4. Postflop (rules engine, about 30 µs)

**Equity estimate:**
- **Hand bucket.** Use the first rule that matches, with the category computed over hole + board:

| bucket | group | hand | flop | turn | river |
|---|---|---|---|---|---|
| 12 | 3 | full house+, better than the board alone | 97 | 96 | 99 |
| 11 | 3 | flush, the board alone is not a flush | 104 | 100 | 102 |
| 10 | 3 | straight, the board alone is not a straight | 96 | 95 | 98 |
| 9 | 3 | trips/set using a hole card | 94 | 96 | 98 |
| 8 | 3 | both hole cards pair the board | 86 | 88 | 89 |
| 7 | 2 | pocket pair above the top board card | 73 | 75 | 77 |
| 6 | 2 | top pair, kicker ≥ T | 72 | 75 | 77 |
| 5 | 2 | top pair, kicker < T | 75 | 77 | 79 |
| 4 | 1 | weaker pair (incl. pocket pair) + strong draw | 80 | 75 | 65 |
| 3 | 1 | weaker pair (incl. pocket pair below top card) | 68 | 66 | 65 |
| 2 | 0 | no pair, strong draw | 49 | 35 | 16 |
| 1 | 0 | no pair, weak draw | 33 | 26 | 16 |
| 0 | 0 | nothing (incl. hands that only play the board) | 28 | 21 | 16 |

The table values are intercepts, not equities. Add the feature terms, then clamp the result
to [0.02, 0.99]:

`e1 = table/100 + ADJ[group] · (hi, lo, flush_board, connected_board, paired_board)`

- `hi` and `lo` are the hole ranks scaled as `(rank-8)/6`, so a deuce is −1 and an ace is +1.
- `flush_board` = 3 or more board cards of one suit.
- `connected_board` = 3 distinct board ranks within a span of 4.
- `paired_board` = the board has a pair.

```python
ADJ = [(0.193, 0.028, -0.037, -0.032,  0.057),   # group 0 air
       (0.056, 0.112, -0.073, -0.044,  0.047),   # group 1 weak pair
       (0.088, 0.041, -0.079, -0.049,  0.001),   # group 2 top pair / overpair
       (0.028, 0.012, -0.086, -0.041, -0.024)]   # group 3 two pair+
```

This was fitted to our bundle's equity net. The mean error is 0.034 on the flop and 0.07 on
the river; the buckets alone give 0.08.

- **Draw definitions.** A strong draw is either of these, before the river:
  - a 4-card flush that uses a hole card;
  - 2 or more straight-completing ranks (each one makes a straight that the board plus that
    rank does not).

  A weak draw is one such rank, or two overcards.
- **Base equity.** `e1` is equity vs **one random hand**. With `k` opponents,
  `eq = e1 ** (k ** 0.88)`.
- **Aggression.** Add up `w = clamp(0.45 / agg(seat), 0.4, 2.0)` over every postflop bet or
  raise by opponents this hand, then take `eq = eq ** (1 + 0.79*sum(w))`.

**Not facing a bet:**
- **Value threshold:** `vb = 0.648 - 0.20 * max(0, 0.45 - avg fold_to_bet)`. This is
  exploit E4: thinner value bets against calling stations.
- **Value bet:** if `eq >= vb`, bet 0.76 pot. Jam if `stack <= 1.52*pot` and `eq >= 0.59`.
- **Bluff:** otherwise, with 1–2 opponents and `eq <= 0.402`, bet 0.584 pot with probability
  `0.381 * avg fold_to_bet / 0.45 / k`. This bluffs less against stations and more against folders.
- **Otherwise:** check.

**Facing a bet:**
- **Raise:** if `eq >= 0.813`, raise to `max(bets) + 0.821*(pot + to_call)`. Jam instead if
  that is at least 40% of my stack, or if `stack <= 1.52*pot`.
- **Call or fold:** call if `0.823*eq >= need(aggressor) + 0.094`, else fold. The aggressor is
  the last raiser this street.

## 5. Opponent model (per seat, reset each table)

**Counts** (kept from each finished hand's history):
- `hands` and `vpip` (preflop call or raise);
- `pfr` (preflop raise) and `shove` (preflop all-in raise);
- postflop: `faced` and `folded` (facing a bet), `aggr` (bets and raises) and `passive` (calls);
- `acts` and `allin` (every non-blind action, and how many of them were all-in).

**Rates.** Each rate is a Beta-smoothed mean: `(count + prior*6) / (opportunities + 6)`, with
priors vpip .35, pfr .18, shove .06, fold_to_bet .45 and agg .45. The opportunities are:

| rate | opportunities |
|---|---|
| `vpip`, `pfr`, `shove` | `hands` |
| `fold_to_bet` | `faced` |
| `agg` | `aggr + passive` |

**Jammer** (the degenerate-bot fast path): `acts >= 5` and `allin >= 0.9*acts`. Treat its
range as any two cards. Seats that time out or always check/fold need no special case:
VPIP goes to 0, so E1 and E2 steal and shove wider into them automatically.

**When to update.** Update on the kit's hand-end callback if it has one. Otherwise, when
`hand_no` changes, take the last history seen for the previous hand. Never update twice.

**Exploits, by value:**

| | exploit | section |
|---|---|---|
| E1 | steal more vs tight players behind | §3 |
| E2 | shove more vs tables that rarely call | §2 |
| E3 | call jams on equity vs the shover's real range | §2 |
| E4 | vs stations, bluff less and value-bet thinner | §4 |

Aggression weighting (§4) calls down maniacs more and folds more to nits.

## 6. Safety: never lose a decision to a crash or the clock

- **Errors:** wrap `act` in `try/except Exception` and return check if `to_call == 0`, else fold.
- **Legal actions:** pass the result through `legal()` every time.
  - A raise needs `min_raise_to > 0`; clamp it to `[min_raise_to, max_raise_to]`.
  - If raising is illegal, return a call.
  - A fold with `to_call == 0` becomes a check.
- **Garbage collection:**
  - at import, call `gc.collect(); gc.freeze(); gc.disable()`;
  - call `gc.collect()` only in the per-table reset or the constructor, never inside `act`;
  - if the kit has no per-table hook, use `gc.set_threshold(50000, 50, 50)` instead of disabling.
- **Deadline:** record `t0 = perf_counter()` at the top of `act`. The bot is about 50 µs, but
  anything optional (logging, extra loops) must check `perf_counter() - t0 < 0.0006` and skip
  itself past that.
- **No I/O, no imports, and no randomness seeding from time inside `act`.**
- **Testing:** run 5,000 random observations (all streets, stacks of 0–60 bb, `min_raise_to = 0`
  cases), then full games in the kit simulator. Check for 0 exceptions, every action legal,
  and a p99 under 0.2 ms.

## Another variant on the day

- **Unchanged:** §0, §3–§6 and every rule. Only the tables in §1–§2 and §4 are NLHE-specific.
- **`HAND_ORDER` and `E1`:** have Codex write a 2-minute Monte Carlo (hand vs random hand,
  about 300 runouts per class) and sort by equity.
- **`EQR`:** use `eq = E1` for every `y` (losing about 2–3%).
- **Push/fold:** scale the NLHE charts. This is safe for any hold'em-like game.
- **Postflop:** re-measure the 13 bucket equities by simulation (Monte Carlo, about 2 minutes).
  For Omaha, change "uses a hole card" to "uses exactly 2 hole cards".

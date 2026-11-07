# Fallback spec v2: the full bot, rebuilt from notes

Use this only if pre-written code is **not** allowed at the event. It describes our final bot
(`frozen/rc2`, NLHE params `cand3_nlhe`) exactly: the same decision engine, the same settings,
with the precomputed data files replaced by short formulas (§1–§2).

**Measured** (`bench/fallback2/`, 12,000 paired SNGs vs the final bot, 8 fields x 2 blind speeds):
fresh AI assistants given only this file rebuilt the bot, passed every self-test (§9) on the
first or second run, matched our reference on 99.95% of decisions in real games, and scored
**98.6% of the final bot** (1.78 vs 1.80 x fair; −2.4 ±1.0% of fair). The older, simpler
fallback (`fallback/FALLBACK_SPEC_LITE.md`) scores about 84%.

**NLHE only.** The formulas in §1–§2 are fitted to Texas Hold'em. For another variant, the
pre-written bot (DAYOF.md) is the plan; without it, use the LITE spec's variant notes.

Every number is here. Nothing is random: the same inputs always give the same action, so the
self-test values in §9 can be checked exactly.

**Build order** (each step is a working bot):
1. §0 interface, §8 safety, §1 tables, §5 preflop (charts + opening rules). Postflop: check, or
   fold to a bet.
2. §2 postflop equity + §6 EV engine. This is most of the strength.
3. §3 opponent stats + §4 exploit levels. Until then, use level 0 params and prior rates.

Game assumed: NLHE, 8 seats, 2,000 chips, blinds rising every 25 hands, 1 ms per decision.

---

## 0. Interface and conventions

**Actions:** `FOLD = 0`, `CALL = 1` (a check when `to_call == 0`), `RAISE = 2` with a *raise-to*
street total. `POST = 3` (a blind) appears only in the history.

**Observation** (build this in the adapter from the kit's format):

| field | meaning |
|---|---|
| `hole`, `board` | cards: ints `rank_index*4 + suit` with deuce = 0, ace = 12 (so `rank = c//4 + 2`, 2..14) |
| `street` | 0 preflop, 1 flop, 2 turn, 3 river |
| `seat`, `button` | indexes into the seat list |
| `stacks[i]` | chips **behind** (not yet bet) |
| `bets[i]` | chips seat i put in **this street** (blinds count preflop) |
| `in_hand[i]` | dealt in, not folded (all-in seats count as in) |
| `pot` | every chip committed this hand, **including** this street's bets and antes |
| `to_call` | chips I need to call |
| `min_raise_to` | smallest legal raise-to total; **0 if raising is not allowed** |
| `max_raise_to` | my all-in total, `bets[me] + stacks[me]` |
| `bb` | big blind |
| `hand_no` | changes every hand |
| `history` | list of `(seat, street, kind, amount_to, all_in)` for this hand in order. `kind` is POST, FOLD, CALL (check or call), RAISE (bet or raise). `amount_to` = that seat's street total after the action. An all-in is RAISE if it goes over the current top bet, else CALL. Antes are not in it. |

**Helpers used everywhere:**
- `clamp(x, lo, hi)`, `sigmoid(z) = 1/(1+exp(-z))` (clamp z to ±60), `logit(p) = ln(p/(1-p))` with p clamped to [1e-4, 1-1e-4].
- `opps` = seats `s != me` with `in_hand[s]`.
- `raise_to(target)`: if `min_raise_to <= 0` return CALL. `amt = max(min_raise_to, int(target))`;
  if `amt >= 0.85*max_raise_to`, `amt = max_raise_to`; return `(RAISE, min(amt, max_raise_to))`.
- `jam()`: if `min_raise_to <= 0` return CALL, else `(RAISE, max_raise_to)`.

**Hand name:** higher rank first. Pairs `"77"`, else suffix `s` (suited) or `o`. E.g. `AKs`, `T9o`.

---

## 1. Preflop tables (paste as literals)

```python
HAND_ORDER = """AA KK QQ JJ TT 99 88 AKs 77 AQs AJs AKo AQo ATs AJo KQs 66 A9s KJs ATo A8s KTs KQo A9o
A7s QJs KJo 55 K9s A6s A5s KTo QTs A8o A4s A7o A3s K8s QJo K9o A5o K7s A6o JTs Q9s QTo
A2s 44 K6s A4o Q8s A3o K8o K5s K7o J9s Q9o A2o JTo K4s Q7s K6o T9s J8s K3s Q6s K5o Q8o
33 J9o K2s Q5s J7s K4o T8s Q4s Q7o K3o J8o T9o T7s Q6o 98s Q3s J6s K2o 22 J5s Q2s Q5o
J7o Q4o T8o J4s T6s 97s Q3o J3s 98o T7o 87s J6o 96s J2s Q2o J5o T5s J4o T4s 86s 97o T6o
95s T3s J3o 76s 87o T2s 85s J2o T5o 96o 94s 75s T4o 86o 93s 65s 84s T3o 95o 92s 76o 74s
54s T2o 85o 64s 83s 94o 82s 75o 65o 93o 73s 53s 63s 84o 92o 43s 74o 72s 54o 64o 52s 62s
83o 82o 42s 73o 53o 63o 32s 43o 72o 52o 62o 42o 32o"""
# heads-up equity % vs a random hand, same order (169 numbers)
E1 = """85 82 80 77 75 72 69 67 66 66 65 65 64 65 64 63 63 63 63 63 62 62 61 61 61 60 61 60 60
60 60 60 59 60 59 59 58 58 58 58 58 58 58 58 58 57 57 57 57 57 56 56 56 56 55 56 55 55
55 55 54 54 54 54 54 54 53 54 54 53 53 53 52 52 52 52 52 51 52 52 51 51 51 51 51 50 50
50 50 50 50 49 50 49 49 49 48 48 48 48 48 48 47 47 47 47 47 46 47 46 46 46 46 46 45 45
45 45 45 44 44 44 44 44 44 43 43 43 43 43 43 42 42 42 42 42 41 41 41 41 40 40 40 40 40
40 39 39 39 39 39 38 38 38 38 38 38 37 37 37 36 36 36 35 35 34 34 33 32"""
```

**Percentile `pct(hand)`:** walk `HAND_ORDER`, adding combos (pair 6, suited 4, offsuit 12),
divided by 1326, *including the hand itself*. `pct(AA) = 6/1326 = 0.004525`, `pct(32o) = 1.0`.
"Top x" means `pct <= x`. `e1(hand) = E1/100`.

**Equity vs a range `eqr(hand, y)`** (heads-up, vs the top-`y` share of hands):
- `y = clamp(y, 0.03, 1)`. `r = ln(clamp(pct/y, 0.05, 20))`, `L = logit(e1)`, `pair` = 1 for pairs.
- For a grid row `(y0, c0..c4)`: `z = c0 + c1*L + c2*pair + c3*min(r,0) + c4*max(r,0)`.
- Find the two rows with `y_lo < y <= y_hi` (if `y <= 0.03` use the first two, t = 0),
  `t = (y - y_lo)/(y_hi - y_lo)`, `z = z_lo*(1-t) + z_hi*t`, return `sigmoid(z)`.
  If `y` is 1 exactly, the last row gives `z = L`, so `eqr = e1`.

```python
EQR = [  # y,     c0,     c1,     c2,     c3,     c4
 (0.03, -0.950, 0.629, -0.497, -0.971, -0.110), (0.06, -0.821, 0.350, -0.078, -0.657, -0.057),
 (0.10, -0.682, 0.215,  0.025, -0.554, -0.077), (0.15, -0.572, 0.182,  0.036, -0.480, -0.118),
 (0.20, -0.548, 0.218,  0.030, -0.438, -0.114), (0.30, -0.549, 0.430,  0.019, -0.344, -0.010),
 (0.45, -0.488, 0.793, -0.048, -0.206,  0.227), (0.65, -0.308, 1.056, -0.091, -0.078,  0.551),
 (1.00,  0.000, 1.000,  0.000,  0.000,  0.000)]
```

**ICM bubble factor `BF(n, hero_share, villain_share, risk)`** (how much a lost chip costs vs a
won chip). `n` = players with chips, shares are fractions of all chips, `risk` = chips risked /
effective stack.
- If `n < 2` return 1. Class each share: short `< 0.7/n`, big `> 1.4/n`, else even (index 0/1/2).
- `BF = 1 + (BF_FULL[min(n,8)] - 1) * BF_SHARE[hero class][villain class] * clamp(risk,0,1)**1.2`.

```python
BF_FULL  = {2: 1.00, 3: 1.41, 4: 1.57, 5: 1.64, 6: 1.73, 7: 1.75, 8: 1.76}
BF_SHARE = [[0.41, 0.53, 0.81],   # hero short  vs villain short / even / big
            [0.29, 1.00, 1.49],   # hero even
            [0.15, 0.44, 2.36]]   # hero big
```

**Equity needed to call `need(villain)`:**
- `c = to_call`; `n_alive` = seats with `stacks[s] + bets[s] > 0` or `in_hand[s]`;
  `total = sum(stacks) + max(pot, sum(bets))`; `mine = stacks[me] + bets[me]`;
  `theirs = stacks[v] + bets[v]`; `eff = min(mine, theirs)`.
- If `total > 0` and `eff > 0`: `bf = 1 + icm_weight * (BF(n_alive, mine/total, theirs/total, c/eff) - 1)`, else `bf = 1`.
- `need = bf*c / max(bf*c + pot, 1)`.

**Push/fold charts** (ICM Nash for 8-player SNG points). Columns are effective stacks in bb:
`PF_STACKS = 2 3 4 5 6 8 10 12 15 18 21`. Look up a row at `eff_bb` by **linear interpolation**
between columns (clamp below 2 and above 21). Values are the top % of hands (divide by 100).

Open-shove when no one has raised. `SHOVE[n]` has one row per position `pos = 0 .. n-2`
(0 = first to act; HU: row 0 is the SB/button). No row for the big blind.

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

Call an all-in. Key: `"hu"` when `n == 2`. Otherwise `K = min(n-1-shover_pos, 4)`,
`J = min(n-1-my_pos, 2)`, key `"3:KJ"` when `n == 3`, else `"KJ"` (e.g. `"41"`).
Defined only when `shover_pos < my_pos < n` and `2 <= n <= 8`; a missing key means "no chart".

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

---

## 2. Postflop equity formulas

### 2a. Hand bucket (first rule that matches; categories over hole + board)

Category of 5+ cards: 6 full house or better (quads and straight flushes count), 5 flush, 4 straight (ace plays
low too), 3 trips, 2 two pair, 1 pair, 0 high card. `cat` = category of hole+board, `bcat` =
category of the board alone (0 if fewer than 3 board cards). `hr` = hole ranks, `br` = board
ranks, `top = max(br)`, `pocket = hr[0] == hr[1]`, `paired` = distinct hole ranks that are on the board.

| bucket | group | rule |
|---|---|---|
| 12 | 3 | `cat >= 6 and bcat < 6` |
| 11 | 3 | `cat == 5 and bcat < 5` |
| 10 | 3 | `cat == 4 and bcat < 4` |
| 9 | 3 | `cat` is 3 or 6, and some hole rank r has (count of r in hole + board) >= 3 |
| 8 | 3 | both distinct hole ranks are on the board (`len(paired) == 2`) |
| 7 | 2 | pocket pair above `top` |
| 6 | 2 | top pair (a paired rank == top) with kicker >= T (rank 10) (kicker = the other hole rank; a pocket pair counts as its own rank) |
| 5 | 2 | top pair, kicker < T |
| 4 | 1 | a weaker pair (paired rank below top, or a pocket pair below top) **and** a strong draw |
| 3 | 1 | a weaker pair, no strong draw |
| 2 | 0 | no pair, strong draw |
| 1 | 0 | no pair, weak draw |
| 0 | 0 | nothing |

Draws exist only before the river (board of 3 or 4):
- **strong**: some suit has 4 cards in hole+board and one of my hole cards is that suit; **or**
  `outs >= 2`, where `outs` = number of ranks x (2..14) not in hole+board ranks such that
  hole+board ranks ∪ {x} contain a straight while board ranks ∪ {x} do not.
- **weak**: not strong, and (`outs == 1` or both hole ranks are above `top`).

Check order exactly: 12, 11, 10, 9, 8, then compute draws, then 7 (pocket above top), then if
`paired` is non-empty use its first rank r: r == top → 6 or 5; else 4/3; then pocket (below
top) → 4/3; then 2/1/0.

### 2b. Equity vs one random hand `e1`

Eleven features of the hand, `f = (hi, lo, fb, cb, pb, top, mine, over, fdn, fb4, sb4)`:
- `hi`, `lo`: the higher / lower hole rank scaled `(rank-8)/6` (deuce −1, ace +1).
- `fb` = 1 if 3+ board cards share a suit. `cb` = 1 if some 3 distinct board ranks lie within a
  span of 4 (sorted distinct board ranks, any `br[i+2] - br[i] <= 4`). `pb` = 1 if the board has a pair.
- `top = (max board rank - 8)/6`.
- `mine`: the first hole rank (hole ranks sorted high to low) that is also on the board; if none,
  the higher hole rank. Scaled `(mine-8)/6`.
- `over` = `min(number of distinct board ranks above mine, 2) / 2` (mine unscaled here).
- `fdn` = 1 if, for some suit with 2+ board cards, I hold the ace of that suit.
- `fb4` = 1 if 4+ board cards share a suit.
- `sb4` = 1 if the board alone has 4 distinct ranks within a span of 4 (`u[i+3] - u[i] <= 4` over
  the sorted distinct board ranks, where an ace on the board also adds a rank 1).

`e1 = clamp(I[bucket] + W[group] · f, 0.02, 0.99)`, with `I` the street's 13 intercepts and `W`
the street's 11 weights for the bucket's group (§2a). Buckets 1, 2 and 4 never occur on the river.

```python
POST_E1 = {  # street: (intercepts for buckets 0..12), then 11 weights per group 0..3
 1: ((0.233, 0.309, 0.451, 0.738, 0.880, 0.732, 0.740, 0.740, 0.871, 0.940, 0.972, 1.056, 0.981),
     (0.099, 0.026, -0.056, -0.027, 0.059, 0.046, 0.099, 0.026, 0.028, 0.000, 0.000),
     (0.042, 0.027, -0.097, -0.045, 0.012, 0.002, 0.069, -0.104, 0.018, 0.000, 0.000),
     (0.019, 0.026, -0.090, -0.048, 0.002, 0.032, 0.055, 0.000, 0.026, 0.000, 0.000),
     (0.021, 0.008, -0.114, -0.053, -0.016, 0.019, -0.013, -0.025, 0.016, 0.000, 0.000)),
 2: ((0.126, 0.181, 0.269, 0.763, 0.843, 0.769, 0.780, 0.790, 0.871, 0.966, 0.974, 1.053, 0.983),
     (0.115, 0.029, -0.033, -0.019, 0.079, 0.048, 0.115, 0.042, 0.032, -0.079, -0.010),
     (0.038, 0.026, -0.064, -0.040, 0.022, -0.011, 0.076, -0.125, 0.008, -0.163, -0.117),
     (0.017, 0.021, -0.064, -0.039, -0.006, 0.049, 0.015, 0.000, 0.021, -0.266, -0.126),
     (0.041, 0.008, -0.069, -0.028, -0.051, 0.019, -0.016, -0.024, 0.012, -0.156, -0.100)),
 3: ((0.027, 0.000, 0.000, 0.798, 0.000, 0.806, 0.815, 0.833, 0.882, 0.990, 1.007, 1.074, 1.014),
     (0.142, 0.027, -0.018, -0.024, 0.092, 0.029, 0.142, 0.083, 0.057, -0.044, -0.028),
     (0.033, 0.035, -0.031, -0.032, 0.048, -0.028, 0.093, -0.149, -0.009, -0.205, -0.140),
     (0.021, 0.019, -0.040, -0.014, -0.004, 0.037, -0.006, 0.000, 0.000, -0.279, -0.165),
     (0.033, 0.012, -0.035, -0.005, -0.066, 0.014, -0.006, -0.020, -0.014, -0.192, -0.113)),
}
```

### 2c. Equity vs a slice of a range `RE(y, x)`

Uses `e1` from §2b. The engine needs my equity against an opponent holding the top `x` (0..1, strongest first) of
the top-`y` preflop range. With `L = logit(e1)`, `lx = ln(clamp(x, 0.05, 1))`,
`ly = ln(clamp(y, 0.08, 1))`, and the bucket's row `(A, B, C)` for this street:

```
z = L + c0 + A*lx + B*ly + C*lx*ly + d1*L*lx + d2*L*ly + d3*L*lx*ly + d4*lx² + d5*L*lx² + d6*ly²
RE = sigmoid(z)
```

```python
CURVE = {  # street: (c0, d1, d2, d3, d4, d5, d6), then (A, B, C) for buckets 0..12
 1: ((-0.070, 0.153, 0.303, 0.049, 0.133, -0.046, 0.003),
     [(1.405, 0.747, 0.165), (0.979, 0.327, 0.032), (0.712, 0.156, 0.024), (1.127, 0.304, 0.040),
      (0.825, 0.089, 0.035), (0.855, 0.004, -0.169), (0.571, -0.152, -0.253), (0.591, -0.344, -0.229),
      (0.287, -0.393, -0.206), (0.119, -0.690, -0.227), (0.180, -0.662, -0.160), (0.238, -0.589, -0.127),
      (-0.246, -0.869, -0.185)]),
 2: ((-0.076, 0.068, 0.294, 0.063, 0.197, -0.072, 0.005),
     [(2.136, 1.122, 0.277), (1.483, 0.517, 0.129), (1.192, 0.365, 0.083), (1.759, 0.441, 0.066),
      (1.322, 0.197, 0.044), (1.375, 0.012, -0.223), (1.122, -0.197, -0.278), (1.155, -0.434, -0.268),
      (0.842, -0.407, -0.257), (0.556, -0.662, -0.306), (0.728, -0.693, -0.149), (0.753, -0.471, -0.211),
      (0.472, -0.727, -0.305)]),
 3: ((-0.047, -0.323, 0.299, 0.093, 0.643, -0.231, 0.027),
     [(4.303, 1.673, 0.666), (2.782, -0.207, -0.210), (2.782, -0.207, -0.210), (4.309, 0.798, 0.238),
      (2.782, -0.207, -0.210), (3.729, -0.055, -0.319), (3.374, -0.426, -0.439), (3.159, -0.810, -0.474),
      (3.037, -0.637, -0.414), (2.338, -0.766, -0.484), (2.329, -0.802, -0.242), (2.200, -0.495, -0.401),
      (1.825, -0.757, -0.442)]),
}
```

**Interval equity `IE(y, a, b)`** (vs the slice from `a` to `b` of the range, 0 = strongest):
- if `b - a < 0.04`: `b = min(1, a + 0.04)`, `a = b - 0.04`.
- `eb = RE(y, b)`; if `a < 0.002` return `eb`.
- `ea = RE(y, a)`; return `clamp((b*eb - a*ea) / (b - a), 0, 1)`.

Compute bucket, `e1` and `L` once per decision.

---

## 3. Opponent stats (per seat, reset at each new table)

Counters per seat: `hands vpip pfr shove faced folded raised faced_ab folded_ab bet_opp bets
aggr passive acts allin minr fs_n fs_f fs_r`, all 0.

**Rates** (Beta-smoothed, weight 6): `rate = (num + prior*6) / (den + 6)`.

| rate | num | den | prior |
|---|---|---|---|
| vpip | vpip | hands | 0.35 |
| pfr | pfr | hands | 0.18 |
| shove | shove | hands | 0.06 |
| fold_to_bet | folded | faced | 0.45 |
| agg | aggr | aggr + passive | 0.45 |
| bet | bets | bet_opp | 0.40 |
| raise | raised | faced | 0.12 |
| fold_nb | folded − folded_ab | faced − faced_ab | 0.35 |
| fold_ab | folded_ab | faced_ab | 0.15 |

**Ingest one finished hand's history** (once per hand; see "when" below). Walk the entries in
order with this state: `street = -1`, `bets = {}` (seat → street total), `aggr_set = set()`,
`bb = inc = 1`, `n_r = 0` (preflop raises so far), `opener = -1`, `acted0 = set()`, and sets
`seen, vp, pr, sh`.

For each `(seat, st, kind, amt, all_in)`:
1. `seen.add(seat)`. If `st != street`: `street = st`, `bets = {}`, `aggr_set = set()`, `inc = bb`.
2. `cur = max(bets.values())` (0 if empty), `prev = bets.get(seat, 0)`.
3. If `kind == POST`: `bets[seat] = amt`; if `amt > bb`: `bb = inc = amt`. Next entry.
4. `acts += 1`; if `all_in`: `allin += 1`.
5. If RAISE: if `amt - cur > inc`: `inc = amt - cur`; elif not `all_in`: `minr += 1`.
6. **Preflop (`st == 0`):**
   - if `n_r == 0` and RAISE and not `all_in`: `opener = seat`.
   - if `n_r == 1` and `opener >= 0` and `seat != opener` and `seat not in acted0`:
     `fs_n += 1`; FOLD → `fs_f += 1`; RAISE → `fs_r += 1`.
   - `acted0.add(seat)`.
   - RAISE: `n_r += 1`; add seat to `vp` and `pr`; if `all_in` add to `sh`.
     CALL with `amt > prev`: add seat to `vp`.
7. **Postflop:**
   - if `cur > prev` (facing a bet): `faced += 1`, and `faced_ab += 1` if seat in `aggr_set`;
     FOLD → `folded += 1` (and `folded_ab += 1` if seat in `aggr_set`); RAISE → `raised += 1`.
   - else: `bet_opp += 1`; RAISE → `bets += 1`.
   - RAISE → `aggr += 1`, `aggr_set.add(seat)`; CALL with `amt > prev` → `passive += 1`.
8. If CALL or RAISE: `bets[seat] = amt`.

After the walk, for each seat in `seen`: `hands += 1`, `vpip += seat in vp`, `pfr += seat in pr`,
`shove += seat in sh`.

**When:** if the kit reports the end of each hand with its history, ingest that. Otherwise,
when a decision arrives with a new `(hand_no, hole)`, ingest the last history seen in the
previous hand. Never ingest a hand twice.

---

## 4. Exploit level and params

**Settings at level 0 (base) and level 4 (exploit).** At level `L` in 0..4, every setting is
`base + (L/4) * (exploit - base)`.

| setting | base | exploit | | setting | base | exploit |
|---|---|---|---|---|---|---|
| open_base | 0.2643 | 0.2654 | | realize | 0.8195 | 0.8219 |
| open_late | 0.4262 | 0.4165 | | realize_chk | 0.8665 | 0.8811 |
| open_bb | 2.965 | 2.842 | | ev_margin | 0.04654 | 0.03703 |
| steal_exploit | 2.031 | 1.752 | | call_ev_margin | 0.08401 | 0.07154 |
| iso_pct | 0.1030 | 0.1541 | | risk_av | 1.032 | 1.228 |
| sb_complete_pct | 0.7267 | 0.7694 | | risk_depth | 28.24 | 26.98 |
| reraise_eq | 0.5884 | 0.6112 | | raise_cont | 0.9975 | 1.072 |
| reraise_mult | 3.221 | 2.903 | | call_width | 1.445 | 1.415 |
| pre_realize | 0.9222 | 0.9486 | | cont_b0 | 1.035 | 1.175 |
| pre_tighten | 0.4378 | 0.4141 | | cont_b1 | 1.633 | 1.713 |
| pf_bb | 21.09 | 16.54 | | cont_b2 | −1.784 | −1.766 |
| pf_shove_scale | 1.167 | 1.087 | | cont_b3 | −0.267 | −0.3887 |
| pf_call_scale | 1.348 | 1.384 | | cont_b4 | −2.719 | −2.337 |
| pf_exploit | 1.609 | 1.325 | | rng_y_scale | 2.126 | 1.834 |
| pf_margin | 0.01941 | 0.02509 | | rng_bet_scale | 1.556 | 1.590 |
| icm_weight | 0.9605 | 0.8630 | | rng_check_cap | 0.6540 | 0.3317 |
| | | | | rng_call_cut | 0.9865 | 0.9073 |
| | | | | rng_persist | 0.3338 | 0.3326 |

Fixed: `SH_OPEN = (0.50, 0.50, 0.42, 0.28, 0.23, 0.19, 0.16, 0.14)`, `POST_SIZES = (0.33, 0.66,
1.0, 1.5)`, `RAISE_SIZES = (0.8, 1.3)`, `PO_REF = 0.65/2.3`.

**Per-seat exploitability `lam(s)`** (recompute when the seat's `hands` changes):
- `r` = the seat's rates `(vpip, pfr, agg, fold_to_bet, shove, bet, fold_nb)`.
- `z = 16.0915 + Σ r_i * (a_i + b_i * r_i)` with

  | rate | a | b |
  |---|---|---|
  | vpip | −42.0452 | 77.96 |
  | pfr | −1.6526 | −27.8091 |
  | agg | 5.9021 | −3.169 |
  | fold_to_bet | −16.0593 | 6.8088 |
  | shove | 11.7009 | 26.4823 |
  | bet | −10.378 | 1.5881 |
  | fold_nb | −8.5967 | 9.9044 |

- `lam = 0` if `hands == 0` or `z < -30`, else `lam = hands/(hands + 15) * sigmoid(z)`.
- `kind = 2` (degenerate: jams or min-raises everything) if `acts >= 5` and
  (`allin >= 0.9*acts` or `minr >= 0.75*acts`); else `kind = 1` (never plays) if `hands >= 8`
  and `vpip == aggr == passive == 0`; else `kind = 0`.

**Level of a decision.** Start `lam = 1`.
- **Preflop:** `acted` = seats with a non-POST entry in the history; `raisers` = seats with a RAISE.
  For each `s` in `opps`:
  - if `s in acted`: skip it if `s not in raisers`; else `x = lam(s)`, or 1 if `kind(s) == 2`.
  - else (still to act): skip it if `stacks[s] <= 0`; else `x = 1` if `kind(s) != 0`, otherwise
    `x = 1 - (1 - lam(s)) * min(1, vpip_rate(s))`.
  - `lam = min(lam, x)`.
- **Postflop:** for each `s` in `opps`: `x = lam(s)`, or 1 if `kind(s) == 2`; `lam = min(lam, x)`.
- `level = int(lam*4 + 0.5)`; use that level's settings for the whole decision.

---

## 5. Preflop

**Action order:** `posts` = seats of the POST entries in order. `bb_seat = posts[1]` if 2+ posts,
`posts[0]` if 1, else `button`. `dealt` = seats in the history ∪ seats with `in_hand`.
`order` = seats `(bb_seat + k) % n_seats` for `k = 1..n_seats` that are in `dealt` (first to act
... big blind). `pos` = my index in `order` (0 if absent; `behind` is then `order[1:]`, as written).

**Common values:** `my_total = stacks[me] + bets[me]`;
`eff_bb = min(my_total, max over opps of stacks[s] + bets[s]) / bb`;
`raises` = preflop RAISE entries. If `opps` is empty, check.
**If `eff_bb <= pf_bb` go to push/fold.**

### 5a. Deep (`eff_bb > pf_bb`), no raise yet
- `behind` = seats after me in `order` with `in_hand` and `stacks > 0`.
- `limpers` = preflop CALL entries with `amount_to > 0`.
- If `to_call == 0` (I am the big blind, limped to): raise to `3*bb + limpers*bb` if `pct <= iso_pct`,
  else check. Either way, stop here.
- `thr = open_base + (open_late - open_base) * (1 - len(behind) / max(len(order)-1, 1))`.
- `thr = max(thr, SH_OPEN[min(len(behind), 7)] * 1.15)`.
- If `limpers`: `thr = iso_pct`.
- If `behind`: `vp` = mean `vpip` rate over `behind`;
  `thr = min(1, thr * (0.35 / max(vp, 0.05)) ** (0.5 * steal_exploit))`.
  Then, if no limpers: `prod = 1`; for each `s` in `behind` with `vpip_count(s) > 0` or
  `hands(s) < 10`: `prod *= (fs_f + 6*0.8) / (fs_n + 6)`. If `prod >= 0.8 - 1e-9`: `thr = 1`
  (use the tolerance: one fresh seat gives exactly 0.8, which floats can round just below).
- If `pct <= thr`: `raise_to(open_bb*bb + limpers*bb)`.
- `comp = 0.8` if `len(order) == 2` else `sb_complete_pct`. If no limpers and
  `to_call <= bb//2 + 1` and `pct <= comp`: call (complete). Else fold.

### 5b. Deep, facing a raise
- `raiser` = seat of the last raise. `y = pfr(raiser) * pre_tighten ** (len(raises) - 1)`; if
  that raise was all-in, `y = min(y, 2.5 * shove(raiser))`. `y = clamp(y, 0.01, 1)`.
- `eq = eqr(hand, y)`.
- `n_in` = opps with a preflop CALL or RAISE entry; `n_live = n_in + 0.25 * (len(opps) - n_in)`.
  If `n_live > 1`: `eq = eq ** (1 + 0.6 * (n_live - 1))`.
- If `eq >= reraise_eq` and `len(raises) < 4` and `min_raise_to > 0`: `target = max(bets) *
  reraise_mult`; jam if `target >= 0.35 * my_total`, else `raise_to(target)`.
- Else call if `eq * pre_realize >= need(raiser)`, else fold.

### 5c. Push/fold (`eff_bb <= pf_bb`), `n = len(order)`
**No raise yet:**
- `behind` = seats after me in `order` with `in_hand` (stack not checked here).
- `thr = SHOVE chart(n, pos, eff_bb)`; if there is no row (`n > 8` or I am the big blind):
  `thr = clamp(0.9 / (1 + 0.35*len(behind)) * sqrt(6 / max(eff_bb, 1)), 0.03, 1)`.
- If `behind`: `thr *= (0.35 / max(mean vpip rate of behind, 0.05)) ** (0.5 * pf_exploit)`.
- `thr = clamp(thr * pf_shove_scale, 0, 1)`.
- If `to_call == 0`: jam if `pct <= 0.6 * thr`, else check.
- Jam if `pct <= thr`, else fold.

**Facing a raise** (any size): `shover` = last raiser, `spos` its index in `order`.
- `need_pf = need(shover) + pf_margin`.
- `t = CALL chart(n, spos, pos, eff_bb)`. If there is no chart or `hands(shover) >= 12`:
  `y = clamp(1.5 * max(shove(shover), 0.8 * pfr(shover)), 0.02, 1)`, `call = eqr(hand, y) >= need_pf`.
  Else `call = pct <= t * pf_call_scale`.
- If more than one opponent in `order` is `in_hand`: `call = call and eqr(hand, 0.08) >= 0.5`.
- If `call`: jam (or call if `min_raise_to <= 0`). Else fold.

---

## 6. Postflop EV engine

Pick the action with the highest ICM-weighted chip EV. If `opps` is empty, check.

**Ranges.** For each opponent `s`, compute `y_s = pre_y(s)` and `(a_s, b_s, ag_s) = post_slice(s)`.

`pre_y(s)`: walk the history while `street == 0` (stop at the first postflop entry).
`bets = {}`, `n = 0`, `y = 1`. POST: `bets[seat] = amt`, next. `prev = bets.get(seat, 0)`.
RAISE: `n += 1`; if `seat == s`: `yr = pfr(s) * pre_tighten**(n-1)`, if all-in `yr = min(yr,
2.5*shove(s))`, `y = min(y, yr)`. CALL by `s` with `amt > prev`: `y = min(y, vpip(s) *
pre_tighten**max(n-1, 0))`. After CALL/RAISE: `bets[seat] = amt`.
Return `clamp(y * rng_y_scale, 0.02, 1)`.

`post_slice(s)`: `g_bet = clamp(bet(s) * rng_bet_scale, 0.03, 1)`,
`g_raise = clamp(raise(s) * rng_bet_scale, 0.02, 1)`, `cont = clamp(1 - fold_nb(s), 0.05, 1)`.
`a, b = 0, 1`; `street = 0`; `bets = {}`; `cur = 0`; `ag = False`; `k = rng_persist`.
For each postflop entry `(seat, st, kind, amt, _)` (skip `st == 0`):
- if `st != street`: if `street > 0`: `a, b = a*k, 1 - (1-b)*k`. Then `street = st`, `bets = {}`, `cur = 0`.
- `prev = bets.get(seat, 0)`. If `seat == s`: `w = b - a`;
  - RAISE: `b = a + w * (g_raise if cur > prev else g_bet)`; `ag = (st == current street)`.
  - CALL: if `cur > prev`: `a, b = a + w*g_raise*rng_call_cut, a + w*max(cont, g_raise)`;
    else (a check): `a = a + w*g_bet*rng_check_cap`.
- RAISE: `cur = amt`. CALL/RAISE: `bets[seat] = amt`.
After the walk: if `street > 0` and `street != current street`: `a, b = a*k, 1 - (1-b)*k`.

**Equities.**
- `n = len(opps)`. `corr = 1`; if `n > 1`: `K = n**0.88` if `n <= 3` else `3**0.88 * n/3`;
  `corr = e1 ** ((K - n) / n)`.
- `real = 1` on the river, else `realize`.
- `eq_vs(s, f=1) = min(1, IE(y_s, a_s, a_s + (b_s - a_s)*f) * corr)`.
- `W_now = Π_s (eq_vs(s) * real)` (product over opps of each term).

**Risk weight `bfw(risk)`.** `P = pot`; `total = sum(stacks) + max(P, sum(bets))`;
`mine = stacks[me] + bets[me]`; `n_alive` as in `need`; `big` = the opp with the most
`stacks + bets`, `theirs` = that amount; `eff = max(min(mine, theirs), 1)`;
`ra = risk_av * min(1, mine / bb / risk_depth)`.
`bfw(risk)`: 1 if `risk <= 0` or `total <= 0`; else
`(1 + ra * min(risk / max(mine,1), 1))**2 * (1 + icm_weight * (BF(n_alive, mine/total, theirs/total, risk/eff) - 1))`.

**Continue probability** of `s` facing pot odds `po`: `c0 = clamp(1 - (fold_ab(s) if ag_s else
fold_nb(s)), 0.01, 0.99)`; `z = cont_b0 + cont_b1*logit(c0) + cont_b2*ln(max(po, 0.01)/PO_REF) +
cont_b3*ag_s + cont_b4*(a_s + b_s)/2`; `cont = sigmoid(z)`.

**EV of raising to `R`:**
```
R = min(R, max over opps of stacks[s] + bets[s])
A = max(R - bets[me], 0); pot_after = P + A; W = 1; parts = []
for s in opps:
    d = max(min(R, stacks[s] + bets[s]) - bets[s], 0)
    if d <= 0 or stacks[s] == 0: c = 1
    else: c = clamp(cont(s, d / max(pot_after + d, 1)) * cmul, 0.02, 1)
    q = eq_vs(s, min(1, c * call_width)) * real
    w = (1 - c) + c*q;  W *= w;  parts.append((c*q*d, w))
gain = P*W + Σ cqd * W / max(w, 1e-9)
return gain - A * (1 - W) * bfw(A)
```
`cmul = raise_cont` when facing a bet, else 1.

**Choose:**
- **Not facing a bet** (`to_call == 0`): best = check with EV `P*W_now*realize_chk + ev_margin*P`.
  Targets: `bets[me] + f*P` for f in POST_SIZES.
- **Facing a bet:** `A = min(to_call, stacks[me])`; best = fold with EV 0.
  `ev_call = P*W_now - A*(1 - W_now)*bfw(A) - call_ev_margin*A`; if `> 0`, best = call.
  Targets: `max(bets) + f*(P + to_call)` for f in RAISE_SIZES.
- If `min_raise_to > 0`: for each `R` in targets + `[max_raise_to]`, in that order:
  `R = int(clamp(R, min_raise_to, max_raise_to))`; if `R >= 0.85*max_raise_to`: `R = max_raise_to`;
  skip an `R` already tried; if `ev_raise(R)` > best EV (strictly), best = `(RAISE, R)`.
- Return best.

---

## 7. The per-decision flow

```
act(obs):
    t0 = perf_counter()
    try: return legal(decide(obs))
    except Exception: return CALL if to_call == 0 else FOLD

decide(obs):
    if number of seats changed: reset stats
    if (hand_no, hole) is new: ingest the previous hand if not yet ingested (§3)
    level = exploit level (§4); p = settings at level
    street 0 -> §5, else -> §6
```
`legal(a)`: FOLD with `to_call <= 0` → CALL. RAISE with `min_raise_to <= 0` → CALL; else clamp
the amount to `[min_raise_to, max(max_raise_to, min_raise_to)]`. Anything else → CALL.

---

## 8. Safety (1 ms per decision)

- At import: `gc.collect(); gc.freeze(); gc.disable()`. Call `gc.collect()` only at a new table
  or in the constructor, never inside `act`. With no per-table hook: `gc.set_threshold(50000, 50, 50)` instead of disabling.
- Cache bucket/`e1`/`L` per decision; `RE` costs ~13 multiplies. A decision is ~0.1 ms.
- If `perf_counter() - t0 > 0.0006` at the top of a raise-loop iteration, stop trying sizes and return
  the best so far. (This is the only timing-dependent rule; it never fires at ~0.1 ms per decision.
  Turn it off when comparing against the self-tests.)
- No I/O, no imports, no randomness inside `act`.

---

## 9. Self-test values (check these before anything else)

Test functions are yours to name. Floats are printed to 4 decimals: check to 5e-4.

Generated by `scripts/selftest_spec.py` from the reference. Cards: int = rank_index*4 + suit, suits c d h s = 0 1 2 3, deuce = 0.

### Preflop

| hand | pct | e1 | eqr(0.10) | eqr(0.30) | eqr(0.05) |
|---|---|---|---|---|---|
| AA | 0.0045 | 0.85 | 0.7983 | 0.7767 | 0.8200 |
| AKs | 0.0347 | 0.67 | 0.5142 | 0.6219 | 0.4325 |
| AKo | 0.0543 | 0.65 | 0.4475 | 0.5757 | 0.3553 |
| QQ | 0.0136 | 0.80 | 0.6786 | 0.7496 | 0.6284 |
| T9s | 0.3454 | 0.54 | 0.3224 | 0.3819 | 0.2815 |
| A5s | 0.1508 | 0.60 | 0.3483 | 0.4655 | 0.3172 |
| 72o | 0.9638 | 0.35 | 0.2710 | 0.3043 | 0.2044 |
| 32o | 1.0000 | 0.32 | 0.2648 | 0.2921 | 0.1944 |

### Bubble factor

| n | hero share | villain share | risk | BF |
|---|---|---|---|---|
| 5 | 0.2 | 0.3 | 0.5 | 1.4151 |
| 3 | 0.1 | 0.5 | 1.0 | 1.3321 |
| 8 | 0.125 | 0.125 | 1.0 | 1.7600 |
| 4 | 0.4 | 0.3 | 0.3 | 1.0591 |
| 2 | 0.5 | 0.5 | 1.0 | 1.0000 |

### Postflop equity

| hole | board | bucket | e1 | RE(1,1) | RE(0.3,0.2) | RE(0.08,0.05) | IE(0.3, 0.1, 0.6) |
|---|---|---|---|---|---|---|---|
| AhKh | Qh7h2c | 2 | 0.7293 | 0.7153 | 0.3437 | 0.1875 | 0.5449 |
| AsKd | Ac9h4d | 6 | 0.8677 | 0.8594 | 0.4350 | 0.0693 | 0.7652 |
| 8c8d | KsTd3h | 3 | 0.6357 | 0.6193 | 0.1651 | 0.0549 | 0.3960 |
| JhTh | 9h8c2d | 2 | 0.5663 | 0.5491 | 0.2868 | 0.2186 | 0.4266 |
| 7s6s | AsKs2d5c | 2 | 0.3110 | 0.2950 | 0.1061 | 0.1142 | 0.1960 |
| QcQd | Qs9h4d2c | 9 | 0.9900 | 0.9892 | 0.8722 | 0.2466 | 1.0000 |
| AdJc | Kh9h5s3d7c | 0 | 0.3247 | 0.3144 | 0.0015 | 0.0023 | 0.0170 |
| 5h4h | AsKd9c2h7d | 0 | 0.0200 | 0.0191 | 0.0001 | 0.0038 | 0.0013 |
| KcKs | 8d8h3c3s2d | 7 | 0.8573 | 0.8515 | 0.1151 | 0.0045 | 0.7872 |
| 9c8c | 7d6h2s | 2 | 0.4763 | 0.4589 | 0.2606 | 0.2355 | 0.3706 |

### Exploitability lam (seat counters -> lam, kind)

| counters | lam | kind |
|---|---|---|
| {"hands": 20, "vpip": 12, "pfr": 2, "aggr": 3, "passive": 10, "faced": 10, "folded": 2, "bet_opp": 8, "bets": 1} | 0.5714 | 0 |
| {"hands": 30, "vpip": 6, "pfr": 5, "aggr": 8, "passive": 3, "faced": 8, "folded": 5, "bet_opp": 10, "bets": 5} | 0.1845 | 0 |
| {"hands": 10, "vpip": 10, "pfr": 10, "shove": 10, "acts": 10, "allin": 10} | 0.4000 | 2 |
| {"hands": 9} | 0.3389 | 1 |
| {"hands": 40, "vpip": 25, "pfr": 15, "aggr": 30, "passive": 10, "faced": 20, "folded": 3, "bet_opp": 20, "bets": 14, "shove": 2} | 0.7268 | 0 |

### Ingest one history (fresh counters)

History: `[[0, 0, 3, 10, false], [1, 0, 3, 20, false], [2, 0, 2, 60, false], [3, 0, 0, 0, false], [4, 0, 1, 60, false], [5, 0, 0, 0, false], [6, 0, 2, 200, false], [7, 0, 0, 0, false], [0, 0, 0, 10, false], [1, 0, 0, 20, false], [2, 0, 1, 200, false], [4, 0, 0, 60, false], [2, 1, 1, 0, false], [6, 1, 2, 150, false], [2, 1, 2, 500, false], [6, 1, 1, 500, false], [2, 2, 2, 300, false], [6, 2, 0, 300, false]]`

| seat | hands | vpip | pfr | shove | faced | folded | aggr | passive | bet_opp | bets | raised | faced_ab | folded_ab | acts | allin | minr | fs_n | fs_f | fs_r |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |
| 2 | 1 | 1 | 1 | 0 | 1 | 0 | 2 | 0 | 2 | 1 | 1 | 0 | 0 | 5 | 0 | 0 | 0 | 0 | 0 |
| 3 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 | 1 | 0 |
| 4 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 1 | 0 | 0 |
| 5 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 1 | 1 | 0 |
| 6 | 1 | 1 | 1 | 0 | 2 | 1 | 1 | 1 | 1 | 1 | 0 | 1 | 0 | 4 | 0 | 0 | 1 | 0 | 1 |
| 7 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |

### Decisions (a fresh bot: every seat at its priors; preflop levels still follow §4: an unacted seat with lam 0 gives x = 0.65, level 3)

Each line: the observation, then the expected action `(kind, amount)`. Fields as in §0; `history` entries are (seat, street, kind, amount_to, all_in) with kind 0 fold 1 call 2 raise 3 post.

1. `{"hole":[51,33],"board":[9,43,21,47],"street":2,"seat":6,"button":5,"stacks":[395,1590,2964,1822,5528,1481,1772,0],"bets":[0,0,0,0,0,0,0,0],"in_hand":[false,false,false,false,false,true,true,false],"pot":448,"to_call":0,"min_raise_to":50,"max_raise_to":1772,"bb":50,"hand_no":65,"history":[[6,0,3,25,false],[0,0,3,50,false],[1,0,0,0,false],[2,0,0,0,false],[3,0,0,0,false],[4,0,0,0,false],[5,0,2,110,false],[6,0,1,110,false],[0,0,0,50,false],[6,1,2,89,false],[5,1,1,89,false]],"cards":"As Td | 4d Qs 7d Ks"}` → `(1, 0)`
2. `{"hole":[29,21],"board":[44,14,32],"street":1,"seat":4,"button":2,"stacks":[1910,2064,2054,1804,2142,1092,0,4739],"bets":[0,0,0,0,0,0,0,0],"in_hand":[false,false,true,false,true,false,false,false],"pot":195,"to_call":0,"min_raise_to":30,"max_raise_to":2142,"bb":30,"hand_no":33,"history":[[3,0,3,15,false],[4,0,3,30,false],[5,0,0,0,false],[7,0,0,0,false],[0,0,0,0,false],[1,0,0,0,false],[2,0,2,90,false],[3,0,0,15,false],[4,0,1,90,false]],"cards":"9d 7d | Kc 5h Tc"}` → `(1, 0)`
3. `{"hole":[34,21],"board":[3,14,47,39,37],"street":3,"seat":3,"button":0,"stacks":[5032,1693,0,1351,2555,0,3892,0],"bets":[0,0,0,0,0,0,0,0],"in_hand":[true,false,false,true,false,false,false,false],"pot":1477,"to_call":0,"min_raise_to":50,"max_raise_to":1351,"bb":50,"hand_no":51,"history":[[1,0,3,25,false],[3,0,3,50,false],[4,0,0,0,false],[6,0,0,0,false],[0,0,2,125,false],[1,0,0,25,false],[3,0,1,125,false],[3,1,2,181,false],[0,1,1,181,false],[3,2,2,420,false],[0,2,1,420,false]],"cards":"Th 7d | 2s 5h Ks Js Jd"}` → `(1, 0)`
4. `{"hole":[31,29],"board":[11,40,14,9],"street":2,"seat":5,"button":6,"stacks":[0,0,1623,4726,1715,2150,1620,3229],"bets":[0,0,0,0,0,0,0,0],"in_hand":[false,false,false,true,false,true,false,false],"pot":937,"to_call":0,"min_raise_to":50,"max_raise_to":2150,"bb":50,"hand_no":56,"history":[[7,0,3,25,false],[2,0,3,50,false],[3,0,2,150,false],[4,0,0,0,false],[5,0,1,150,false],[6,0,0,0,false],[7,0,0,25,false],[2,0,0,50,false],[3,1,2,281,false],[5,1,1,281,false],[3,2,1,0,false]],"cards":"9s 9d | 4s Qc 5h 4d"}` → `(2, 309)`
5. `{"hole":[51,40],"board":[14,17,13],"street":1,"seat":4,"button":2,"stacks":[1928,5451,2297,0,2003,2538,1577,0],"bets":[0,0,0,0,0,0,0,0],"in_hand":[true,false,false,false,true,false,false,false],"pot":206,"to_call":0,"min_raise_to":30,"max_raise_to":2003,"bb":30,"hand_no":43,"history":[[4,0,3,15,false],[5,0,3,30,false],[6,0,0,0,false],[0,0,2,88,false],[1,0,0,0,false],[2,0,0,0,false],[4,0,1,88,false],[5,0,0,30,false]],"cards":"As Qc | 5h 6d 5d"}` → `(2, 67)`
6. `{"hole":[4,22],"board":[51,6,29],"street":1,"seat":4,"button":1,"stacks":[1664,1338,0,0,4500,5992,1646,0],"bets":[0,0,0,0,0,0,0,0],"in_hand":[false,false,false,false,true,true,false,false],"pot":860,"to_call":0,"min_raise_to":150,"max_raise_to":4500,"bb":150,"hand_no":114,"history":[[4,0,3,75,false],[5,0,3,150,false],[6,0,0,0,false],[0,0,0,0,false],[1,0,0,0,false],[4,0,2,430,false],[5,0,1,430,false]],"cards":"3c 7h | As 3h 9d"}` → `(2, 283)`
7. `{"hole":[6,49],"board":[7,45,46],"street":1,"seat":4,"button":1,"stacks":[2089,1582,1841,110,1930,2066,1979,3888],"bets":[0,194,0,0,0,0,0,0],"in_hand":[false,true,false,false,true,false,false,true],"pot":515,"to_call":194,"min_raise_to":388,"max_raise_to":1930,"bb":20,"hand_no":22,"history":[[2,0,3,10,false],[3,0,3,20,false],[4,0,2,57,false],[5,0,0,0,false],[6,0,0,0,false],[7,0,2,97,false],[0,0,0,0,false],[1,0,1,97,false],[2,0,0,10,false],[3,0,0,20,false],[4,0,1,97,false],[4,1,1,0,false],[7,1,1,0,false],[1,1,2,194,false]],"cards":"3h Ad | 3s Kd Kh"}` → `(0, 0)`
8. `{"hole":[47,38],"board":[1,18,17,43,50],"street":3,"seat":6,"button":6,"stacks":[2016,1970,2020,2212,1816,2034,1658,1867],"bets":[0,0,0,0,0,0,0,53],"in_hand":[false,false,false,false,false,false,true,true],"pot":407,"to_call":53,"min_raise_to":106,"max_raise_to":1658,"bb":20,"hand_no":7,"history":[[7,0,3,10,false],[0,0,3,20,false],[1,0,0,0,false],[2,0,0,0,false],[3,0,0,0,false],[4,0,0,0,false],[5,0,0,0,false],[6,0,2,57,false],[7,0,2,97,false],[0,0,0,20,false],[6,0,1,97,false],[7,1,1,0,false],[6,1,2,70,false],[7,1,1,70,false],[7,2,1,0,false],[6,2,1,0,false],[7,3,2,53,false]],"cards":"Ks Jh | 2d 6h 6d Qs Ah"}` → `(0, 0)`
9. `{"hole":[46,12],"board":[43,19,32],"street":1,"seat":3,"button":6,"stacks":[3454,1970,2523,1295,1977,0,4539,0],"bets":[108,0,0,0,0,0,0,0],"in_hand":[true,false,false,true,false,false,false,false],"pot":242,"to_call":108,"min_raise_to":216,"max_raise_to":1295,"bb":20,"hand_no":23,"history":[[0,0,3,10,false],[1,0,3,20,false],[2,0,0,0,false],[3,0,2,57,false],[4,0,0,0,false],[6,0,0,0,false],[0,0,1,57,false],[1,0,0,20,false],[0,1,2,108,false]],"cards":"Kh 5c | Qs 6s Tc"}` → `(0, 0)`
10. `{"hole":[35,49],"board":[9,21,37],"street":1,"seat":3,"button":4,"stacks":[2000,2000,2000,1323,1990,1850,4589,0],"bets":[0,0,0,0,0,32,0,0],"in_hand":[false,false,false,true,false,true,false,false],"pot":248,"to_call":32,"min_raise_to":64,"max_raise_to":1323,"bb":20,"hand_no":1,"history":[[5,0,3,10,false],[6,0,3,20,false],[0,0,0,0,false],[1,0,0,0,false],[2,0,0,0,false],[3,0,2,58,false],[4,0,0,0,false],[5,0,2,98,false],[6,0,0,20,false],[3,0,1,98,false],[5,1,2,32,false]],"cards":"Ts Ad | 4d 7d Jd"}` → `(1, 0)`
11. `{"hole":[40,48],"board":[43,50,45],"street":1,"seat":4,"button":4,"stacks":[2890,5222,0,0,1984,2364,2554,0],"bets":[244,0,0,0,0,0,0,0],"in_hand":[true,false,false,false,true,false,false,false],"pot":986,"to_call":244,"min_raise_to":488,"max_raise_to":1984,"bb":100,"hand_no":85,"history":[[5,0,3,50,false],[6,0,3,100,false],[0,0,2,296,false],[1,0,0,0,false],[4,0,1,296,false],[5,0,0,50,false],[6,0,0,100,false],[0,1,2,244,false]],"cards":"Qc Ac | Qs Ah Kd"}` → `(1, 0)`
12. `{"hole":[13,15],"board":[0,31,43],"street":1,"seat":4,"button":5,"stacks":[1993,5222,0,0,3088,2364,2504,0],"bets":[205,0,0,0,0,0,0,0],"in_hand":[true,false,false,false,true,false,false,false],"pot":829,"to_call":205,"min_raise_to":410,"max_raise_to":3088,"bb":100,"hand_no":86,"history":[[6,0,3,50,false],[0,0,3,100,false],[1,0,0,0,false],[4,0,2,287,false],[5,0,0,0,false],[6,0,0,50,false],[0,0,1,287,false],[0,1,2,205,false]],"cards":"5d 5s | 2c 9s Qs"}` → `(1, 0)`
13. `{"hole":[39,18],"board":[],"street":0,"seat":4,"button":1,"stacks":[1835,2300,2204,1634,2030,1002,0,4920],"bets":[0,0,25,50,0,0,0,0],"in_hand":[true,true,true,true,true,true,false,true],"pot":75,"to_call":50,"min_raise_to":100,"max_raise_to":2030,"bb":50,"hand_no":53,"history":[[2,0,3,25,false],[3,0,3,50,false]],"cards":"Js 6h | "}` → `(0, 0)`
14. `{"hole":[1,17],"board":[],"street":0,"seat":5,"button":2,"stacks":[0,81,1100,1028,6387,3194,2180,1880],"bets":[0,0,0,50,100,0,0,0],"in_hand":[false,true,true,true,true,true,true,true],"pot":150,"to_call":100,"min_raise_to":200,"max_raise_to":3194,"bb":100,"hand_no":95,"history":[[3,0,3,50,false],[4,0,3,100,false]],"cards":"2d 6d | "}` → `(0, 0)`
15. `{"hole":[33,16],"board":[],"street":0,"seat":5,"button":1,"stacks":[551,2331,1700,2233,3729,1072,2338,1971],"bets":[0,0,25,50,0,0,0,0],"in_hand":[true,true,true,true,false,true,true,true],"pot":75,"to_call":50,"min_raise_to":100,"max_raise_to":1072,"bb":50,"hand_no":59,"history":[[2,0,3,25,false],[3,0,3,50,false],[4,0,0,0,false]],"cards":"Td 6c | "}` → `(0, 0)`
16. `{"hole":[17,29],"board":[],"street":0,"seat":3,"button":1,"stacks":[1686,2020,1819,1473,1900,2443,4579,0],"bets":[50,0,10,20,0,0,0,0],"in_hand":[true,false,false,true,false,false,false,false],"pot":80,"to_call":30,"min_raise_to":80,"max_raise_to":1493,"bb":20,"hand_no":12,"history":[[2,0,3,10,false],[3,0,3,20,false],[4,0,0,0,false],[5,0,0,0,false],[6,0,0,0,false],[0,0,2,50,false],[1,0,0,0,false],[2,0,0,10,false]],"cards":"6d 9d | "}` → `(1, 0)`
17. `{"hole":[33,19],"board":[],"street":0,"seat":6,"button":5,"stacks":[2036,1970,2020,2212,1816,2034,1865,1893],"bets":[0,0,0,0,0,0,57,97],"in_hand":[false,false,false,false,false,false,true,true],"pot":154,"to_call":40,"min_raise_to":137,"max_raise_to":1922,"bb":20,"hand_no":6,"history":[[6,0,3,10,false],[7,0,3,20,false],[0,0,0,0,false],[1,0,0,0,false],[2,0,0,0,false],[3,0,0,0,false],[4,0,0,0,false],[5,0,0,0,false],[6,0,2,57,false],[7,0,2,97,false]],"cards":"Td 6s | "}` → `(1, 0)`
18. `{"hole":[25,41],"board":[],"street":0,"seat":4,"button":2,"stacks":[1453,2497,3529,1684,2315,727,0,3610],"bets":[0,0,0,25,50,0,0,110],"in_hand":[false,false,false,false,true,false,false,true],"pot":185,"to_call":60,"min_raise_to":170,"max_raise_to":2365,"bb":50,"hand_no":68,"history":[[3,0,3,25,false],[4,0,3,50,false],[5,0,0,0,false],[7,0,2,110,false],[0,0,0,0,false],[1,0,0,0,false],[2,0,0,0,false],[3,0,0,25,false]],"cards":"8d Qd | "}` → `(1, 0)`
19. `{"hole":[48,1],"board":[],"street":0,"seat":4,"button":4,"stacks":[2016,5496,1695,0,2076,2723,1949,0],"bets":[0,0,0,0,0,15,30,0],"in_hand":[false,false,false,false,true,true,true,false],"pot":45,"to_call":30,"min_raise_to":60,"max_raise_to":2076,"bb":30,"hand_no":38,"history":[[5,0,3,15,false],[6,0,3,30,false],[0,0,0,0,false],[1,0,0,0,false],[2,0,0,0,false]],"cards":"Ac 2d | "}` → `(2, 86)`
20. `{"hole":[50,7],"board":[],"street":0,"seat":6,"button":6,"stacks":[0,0,0,0,4516,0,11184,0],"bets":[0,0,0,0,200,0,100,0],"in_hand":[false,false,false,false,true,false,true,false],"pot":300,"to_call":100,"min_raise_to":400,"max_raise_to":11284,"bb":200,"hand_no":136,"history":[[6,0,3,100,false],[4,0,3,200,false]],"cards":"Ah 3s | "}` → `(2, 574)`
21. `{"hole":[51,17],"board":[],"street":0,"seat":6,"button":3,"stacks":[295,1440,2657,1597,5339,1799,2723,0],"bets":[0,0,0,0,50,100,0,0],"in_hand":[true,true,true,true,true,true,true,false],"pot":150,"to_call":100,"min_raise_to":200,"max_raise_to":2723,"bb":100,"hand_no":77,"history":[[4,0,3,50,false],[5,0,3,100,false]],"cards":"As 6d | "}` → `(2, 287)`
22. `{"hole":[20,42],"board":[],"street":0,"seat":4,"button":1,"stacks":[2684,5372,0,0,990,3258,3250,0],"bets":[296,0,0,0,50,100,0,0],"in_hand":[true,false,false,false,true,true,false,false],"pot":446,"to_call":246,"min_raise_to":492,"max_raise_to":1040,"bb":100,"hand_no":79,"history":[[4,0,3,50,false],[5,0,3,100,false],[6,0,0,0,false],[0,0,2,296,false],[1,0,0,0,false]],"cards":"7c Qh | "}` → `(0, 0)`
23. `{"hole":[3,35],"board":[],"street":0,"seat":6,"button":6,"stacks":[0,0,0,0,2934,0,12616,0],"bets":[0,0,0,0,300,0,150,0],"in_hand":[false,false,false,false,true,false,true,false],"pot":450,"to_call":150,"min_raise_to":600,"max_raise_to":12766,"bb":300,"hand_no":152,"history":[[6,0,3,150,false],[4,0,3,300,false]],"cards":"2s Ts | "}` → `(0, 0)`
24. `{"hole":[42,10],"board":[],"street":0,"seat":4,"button":5,"stacks":[0,2577,0,0,8526,2651,1946,0],"bets":[0,200,0,0,0,0,100,0],"in_hand":[false,true,false,false,true,true,true,false],"pot":300,"to_call":200,"min_raise_to":400,"max_raise_to":8526,"bb":200,"hand_no":135,"history":[[6,0,3,100,false],[1,0,3,200,false]],"cards":"Qh 4h | "}` → `(0, 0)`
25. `{"hole":[23,21],"board":[],"street":0,"seat":6,"button":4,"stacks":[0,0,0,0,0,0,12184,0],"bets":[0,0,0,0,3616,0,200,0],"in_hand":[false,false,false,false,true,false,true,false],"pot":3816,"to_call":3416,"min_raise_to":0,"max_raise_to":12384,"bb":200,"hand_no":143,"history":[[4,0,3,100,false],[6,0,3,200,false],[4,0,2,3616,true]],"cards":"7s 7d | "}` → `(1, 0)`
26. `{"hole":[51,43],"board":[],"street":0,"seat":6,"button":2,"stacks":[0,40,0,0,6216,0,7313,0],"bets":[0,0,2206,0,75,0,150,0],"in_hand":[false,false,true,false,false,false,true,false],"pot":2431,"to_call":2056,"min_raise_to":0,"max_raise_to":7463,"bb":150,"hand_no":124,"history":[[4,0,3,75,false],[6,0,3,150,false],[1,0,0,0,false],[2,0,2,2206,true],[4,0,0,75,false]],"cards":"As Qs | "}` → `(1, 0)`
27. `{"hole":[35,33],"board":[],"street":0,"seat":6,"button":4,"stacks":[0,0,0,0,0,0,10582,0],"bets":[0,0,0,0,5118,0,300,0],"in_hand":[false,false,false,false,true,false,true,false],"pot":5418,"to_call":4818,"min_raise_to":0,"max_raise_to":10882,"bb":300,"hand_no":163,"history":[[4,0,3,150,false],[6,0,3,300,false],[4,0,2,5118,true]],"cards":"Ts Td | "}` → `(1, 0)`
28. `{"hole":[43,47],"board":[],"street":0,"seat":5,"button":5,"stacks":[0,0,0,0,5752,9798,0,0],"bets":[0,0,0,0,300,150,0,0],"in_hand":[false,false,false,false,true,true,false,false],"pot":450,"to_call":150,"min_raise_to":600,"max_raise_to":9948,"bb":300,"hand_no":157,"history":[[5,0,3,150,false],[4,0,3,300,false]],"cards":"Qs Ks | "}` → `(2, 861)`
29. `{"hole":[49,47],"board":[],"street":0,"seat":6,"button":6,"stacks":[0,0,0,0,5118,0,10432,0],"bets":[0,0,0,0,300,0,150,0],"in_hand":[false,false,false,false,true,false,true,false],"pot":450,"to_call":150,"min_raise_to":600,"max_raise_to":10582,"bb":300,"hand_no":162,"history":[[6,0,3,150,false],[4,0,3,300,false]],"cards":"Ad Ks | "}` → `(2, 861)`
30. `{"hole":[23,35],"board":[],"street":0,"seat":6,"button":6,"stacks":[0,0,0,0,3616,0,12084,0],"bets":[0,0,0,0,200,0,100,0],"in_hand":[false,false,false,false,true,false,true,false],"pot":300,"to_call":100,"min_raise_to":400,"max_raise_to":12184,"bb":200,"hand_no":144,"history":[[6,0,3,100,false],[4,0,3,200,false]],"cards":"7s Ts | "}` → `(2, 574)`

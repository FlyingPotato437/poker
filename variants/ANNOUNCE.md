# ANNOUNCE.json: every rule knob, what to write, what the bot does with it

Copy the template, fill it from the announcement, run go.py:

```bash
cp variants/ANNOUNCE.json variants/day_announce.json      # edit this copy
.venv/bin/python scripts/go.py variants/day_announce.json --check              # summary + warnings, no build
.venv/bin/python scripts/go.py variants/day_announce.json --adapter my_adapter.py
```

Keys starting with `_` are comments. Anything left out takes the official default (8
players, 2000 chips, 25 hands per level, 200-hand cap, 1 ms). Worked examples:
`variants/examples/*.json` (NLHE with antes and new points, PLO4, kit2's 3-hole game, a 7+
short deck with flush over full house).

## variant (hand mechanics)

| Key | Write | Notes |
|---|---|---|
| `preset` | `nlhe`, `plo4`, `plo5`, `shortdeck` (6+, trips > straight; FH < flush), `shortdeck_triton` (straight < trips), `royal` (T+), `holdem3` (3 hole, any 5), or `null` | Starting point. The other keys override it. |
| `ranks` | lowest first, e.g. `"789TJQKA"` | 7+ short deck. At most 16 ranks. |
| `suits` | 1..7 | 5+ suits makes five of a kind possible. |
| `n_hole` | hole cards per player | |
| `streets` | board cards per street, e.g. `[3,1,1]`, `[4,1]`, `[3,1,1,1]` | 4-card flop: `[4,1,1]`. |
| `hole_used` | `null` = best 5 of all; `2` = exactly 2 hole cards (Omaha) | |
| `category_order` | 10 names weakest first: `high, pair, two_pair, trips, straight, flush, full_house, quads, straight_flush, five_kind` (ints 0..9 also work) | Flush beats full house: swap `flush` and `full_house`. All 10 must appear. go.py prints the frequencies (`variant_stats.py`); "rarer beats commoner" is the usual rule. |
| `ace_low_straight` | `true` / `false` | `true` = A2345 (A6789 in 6+). |

go.py uses a preset's bundle only when every one of these is identical to the preset.
Anything else is a new variant: it writes `variants/day.json` and builds tables.

## game_type

`high` (normal). The rest can't be modeled by the evaluator. go.py still builds a legal,
kit-tested v0 and prints the plan from VARIANTS.md section 3:

| Value | What to do |
|---|---|
| `hi-lo`, `lowball-27`, `lowball-a5`, `badugi` | New `hand_value_5` + `TorchEval.eval5` (20–40 min). v0 is only a placeholder. |
| `wild-cards` | `Evaluator.best`: treat the wild card as the best-improving card. |
| `discard` (pineapple) | Write the variant after the discard (`n_hole` = cards kept); the adapter does the discard. |
| `stud` | Adapter treats up-cards as board cards. Low quality. |

## betting

| Key | Write | Bot |
|---|---|---|
| `type` | `no-limit` / `pot-limit` / `fixed-limit` | Strategy is no-limit. Pot-limit: the adapter passes the pot-limit max as `max_raise_to`. Fixed-limit: `min_raise_to = max_raise_to` = the fixed size. |
| `raise_cap` | raises per street, or `null` | Adapter sets `min_raise_to = None` once the cap is hit. |
| `short_allin_reopens` | `true` / `false` | Fine either way (legal range comes from the state). Add `--reopen-short` to tune/A-B runs. |

## Table, schedule, points

| Key | Write | Used for |
|---|---|---|
| `players` | 2..10 | Points length check; push/fold covers up to 8 left. |
| `starting_stack` | chips | Picking the ante level; A/B command. |
| `blinds` | `"10/20,15/30,..."`, or `"sb/bb/ante"` per level when the ante changes by level | Ante level; A/B command. |
| `hands_per_level` | int | A/B command. |
| `ante.type` | `none` / `every-player` / `bb-ante` | Push/fold is re-solved with antes. |
| `ante.chips` | fixed ante in chips (if not in `blinds`) | |
| `ante.ante_bb_override` | ante ÷ bb to solve at, or `null` | Default: the ratio at the first level where the starting stack is ≤ 25 bb (that's where shoving starts). BB ante: 1 ÷ players. |
| `hand_cap` | int or `null` | A/B command. |
| `points` | list 1st..last (one per player; shorter is padded with 0) | **Required.** Exact push/fold + bubble-factor re-solve (~15 s). |
| `time_limit_ms` | per decision | Not 1 ms: go.py appends `PrepBot.deadline = 0.6 × limit` to a copy of the adapter (`dist/day/<tag>_adapter.py`). |

## special_rules

All `true`/`false`. None of them is modeled; go.py prints what to do:

| Key | Plan |
|---|---|
| `seven_deuce` | Ignore (small EV) or add a preflop override in the adapter if the bonus is big. |
| `straddle` | Adapter: straddle is a `POST` in history and part of `bets`. |
| `bomb_pot` | Adapter: forced chips go in `pot`; street comes from the state. |
| `bounty` | Not in the points model; the bot plays for place points only. |
| `run_it_twice` | Doesn't change decisions. |
| `other` | Free text. Logged as a warning; decide by hand with VARIANTS.md. |

## kit

| Key | Write | Used for |
|---|---|---|
| `raise_semantics` | `raise-to` / `raise-by` | Reminder: `to_obs` must give raise-TO totals; `to_kit_action` converts back. |
| `card_format` | free text | Reminder for `card_id()`. |
| `bot_class`, `method` | e.g. `PokerBot`, `get_move` | go.py checks the adapter defines them. |
| `file_name` | what to upload, e.g. `bot.py` | `day.py submit ... --as <file_name>`. |
| `sim_cmd` | kit simulator with `{bot}` (and `{py}` = our python), e.g. `{py} kit/simulate.py {bot} --games 10` | Every build runs it; a failure stops the freeze. Same as `--kit-cmd`. |
| `numpy_available` | `true` / `false` / `null` | `false`: every build uses `--pure-python`. |
| `reuses_bot_across_tables` | `true` / `false` | `true`: build a new core at the kit's new-game hook. |

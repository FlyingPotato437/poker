# Variant mechanics: what each kind of rule change costs us

Read the announcement against this table first. The rows tell us whether it's a parameter
change, a table build or new code. If it's new code, they say what to submit while the code
gets written.

Checked Oct 31:

- The bot plays 2 to 10 seats with no internal errors.
- Packaged files run on Python 3.8 to 3.14, with or without numpy.
- Peak memory on Linux, with numpy: NLHE 58 MB, PLO4 75 MB, PLO5 209 MB. Without numpy:
  45, 60 and 197 MB.
- The points rebuild takes 12 s on the laptop.

## 1. Parameters only (no rebuild, minutes)

| Rule | What to do |
|---|---|
| Points table | Exact push/fold re-solve: `day.py build ... --points 1st,..,8th` (12 s). Never use the nearest preset's tables. |
| Antes | `--ante-bb <ante / bb>` in the same build. The engine posts antes. In the adapter, set `Obs.ante` and leave antes out of `history`. |
| Blind schedule, hands per level, starting stack, hand cap | Nothing in the bot: it reads blinds and stacks from the state. In tune runs, use `--schedule 10/20,... --hands-per-level --stack --max-hands --ante`. In the A/B gate, `ab_test.py` takes the same flags plus `--points`. |
| Player count 2–10 (6-max, heads-up, 9–10 seats) | Nothing: checked at 2, 3, 6, 9 and 10 seats. `--points` needs one entry per place; pushfold solved a 10-place table fine. |
| Different time limit | Deadline guard: add `PrepBot.deadline = <seconds>` to the adapter (default 0.0006 s), about 60% of the limit. The env var `NOLIMIT_DEADLINE_MS` is read at import, before the adapter runs. |
| Card format, ids, raise-by vs raise-to, check vs call, pot with or without current bets | Adapter only (the T+0 to T+12 work, `REHEARSAL.md`). |
| A short all-in reopens the betting | `--reopen-short` in tune and A/B runs (engine default: it doesn't). The bot already takes the legal raise range from the state. |

## 2. Variant JSON plus a table build (`variants/day.json`)

Write the JSON first. Then submit v0 at once with `day.py build v0 --heuristic
variants/day.json`, which uses the exact rules on heuristic tables. Then build:
`gpu.build_tables --laptop`, then `gpu.range_eq --laptop`, then `day.py build v1 --bundle
bundles/day_rng.nlb`.

| Rule | JSON field |
|---|---|
| Fewer ranks (short deck 6+, 7+, ...) | `ranks` |
| More or fewer suits (5+ suits allows five of a kind) | `suits` |
| Hand ranking changed (flush beats full house, trips beat straight) | `category_order`, weakest first. Check it with `variant_stats.py`; "rarer beats more common" is the usual rule. |
| More hole cards (3–5) | `n_hole` |
| Must use exactly k hole cards (Omaha: 2) | `hole_used` |
| Different board layout (4-card flop, 2 turn cards, ...) | `streets`, e.g. `[3,1,1]` |
| Ace can't play low | `ace_low_straight: false` |

If a preset is close (`nlhe`, `shortdeck`, `shortdeck_triton`, `plo4`, `plo5`, `royal`,
`holdem3`), take its bundle. Use a near preset's tables only if the hand evaluation is
identical. Otherwise the heuristic v0 with the exact rules is safer than a wrong table.

## 3. New code: what to submit meanwhile

| Rule | What breaks | Plan |
|---|---|---|
| Pot-limit or fixed-limit betting | Strategy assumes no-limit, but play stays legal if the adapter passes the kit's max raise as `max_raise_to` | Submit as-is with the adapter clamping to the kit's limits. Tune with the engine changed to the kit's raise cap (engine `_betting`), if time allows. |
| Hi-lo split, lowball (2-7, A-5), badugi | Evaluator ranks high hands only | Write a new `hand_value_5` and `TorchEval.eval5` (see `tests/test_evaluator.py`). Meanwhile submit a check/call-down bot: only call or check, never fold for free, fold big bets with a weak high hand. Probably 20–40 min of code. |
| Wild cards or jokers | Evaluator | Same as above. As an interim, treat a wild card as the card that best improves the hand: add it in `Evaluator.best`. |
| Discards (pineapple, crazy pineapple) or draws | Engine and state have no discard step | Adapter-level: keep the 2 cards whose `T.hole_class` scores best, or the best made hand with the board after the flop. Play with the 2-card (nlhe) tables. About 15 min. |
| Stud (up cards, bring-in) | Engine, state and tables | Rules engine on heuristic tables with the up cards treated as board cards seen by all. Low quality; mostly the adapter. |
| Two boards, run it twice | Settlement | Run it twice doesn't change decisions, so ignore it (simulate with `--run-twice`). For two boards, evaluate against board 1 only and fix if there's time. |
| Straddles, bomb pots | Forced bets | Adapter: add forced bets as `POST` in history and include them in `bets`. A bomb pot skips preflop, which the bot handles because street is taken from the state. Simulate with `--straddle`, `--bomb-every N --bomb-bb K`. |
| BB ante, 7-2 bounty, knockout points, bet or raise caps, dead button | Forced bets, payouts or betting limits | Engine flags `--bb-ante`, `--bounty-72`, `--ko-points`, `--max-bet-bb`, `--max-raises`, `--dead-button` (scripts/rules_cli.py) in run_tournament, ab_test, tune and the sweep. The bot knows none of the bounty rules; `scripts/stipulation_sweep.py` measures what each costs. |

## 4. Always, whatever the variant

- v0 must be submitted before the first practice round, even if it's the heuristic bot.
- Every submit goes through `day.py build`. That runs the kit simulator via `--kit-cmd`,
  the clean-interpreter checks and the freeze.
- If anything misbehaves in a practice round, run `day.py rollback` first, then investigate.

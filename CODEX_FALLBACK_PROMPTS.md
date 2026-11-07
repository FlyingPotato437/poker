# Codex prompts: rebuild the full bot from FALLBACK_SPEC.md (no pre-written code)

Use these only if pre-written code is not allowed. You bring two documents:
[FALLBACK_SPEC.md](FALLBACK_SPEC.md) (the bot, every number) and its self-test values (§9 of the
spec, or `bench/fallback2/selftest.md`). Codex writes all the code.

**Tested:** fresh AI assistants given only these two files rebuilt the bot, passed all
self-tests in under 5 minutes, and agreed with our reference on 99.9% of decisions in real
games. The rebuilt bot scores about 98% of the final bot (`bench/fallback2/`).

| step | minutes | result |
|---|---|---|
| 1 | 0–10 | `spec_bot.py`: the whole bot, passing every self-test |
| 2 | 10–25 | `agent.py`: wired to the kit, state carried in `memory`, passes `poker-agent check` and `play` |
| 3 | 25–35 | speed and safety tests, then **upload** |
| — | 35–60 | slack: fix what the kit's test match or `play` shows. Don't change numbers. |

Upload as soon as step 2 passes `play` with 0 failed decisions; re-upload after step 3.

---

## Prompt 1: the bot (paste the whole spec and the self-tests after it)

```
Implement the poker bot in the specification below EXACTLY, as one file spec_bot.py using
only the Python standard library. Do not change any number or rule; do not "improve" anything.

It must define class SpecBot with: new_table(seat, n_seats); act(obs) -> (kind, amount) where
obs has attributes hole, board, street, seat, button, stacks, bets, in_hand, pot, to_call,
min_raise_to, max_raise_to, bb, hand_no, history (see §0); and observe(("hand_end",
{"hand_no": n, "history": [...]})) to ingest a finished hand (§3).

Then write test_spec.py that checks EVERY value in the self-test section (tables, bubble
factors, postflop equities, ingestion counters, lam values, and all 30 decisions: fresh
SpecBot(), new_table(seat, len(stacks)), act(obs)). Run it and fix spec_bot.py until every
check passes. If a value does not match, re-read that section of the spec; the spec is right.
Report the pass count and anything you had to guess.

<paste FALLBACK_SPEC.md here>
<paste the self-test values here>
```

## Prompt 2: wire it to the kit (state travels in `memory`)

```
Read the kit's README.md, AGENTS.md, RULES.md and agent.py. Write agent.py (our bot is
spec_bot.py next to it) so that class Agent(poker_agent_sdk.Agent).act(state, memory)
returns (action, memory_bytes).

Rules from the kit that matter:
- self and globals cannot be relied on between calls: any copy may answer any table. So ALL
  per-table state goes into memory: the per-seat counters of §3 (19 ints per seat), the
  current hand number, the hand's history so far in spec format, and the last ingested hand.
  Encode compactly (json with short keys + zlib, or struct), stay under 16 KB, and if memory
  is empty or fails to parse, start fresh instead of raising.
- Each call: decode memory -> rebuild a SpecBot and restore its counters -> convert
  state.events (everything since my last turn) into history entries -> if the events show a
  new hand started, first ingest the previous hand's complete history (§3) -> build the
  obs of §0 from state -> act -> convert the action -> encode memory.
- Event -> history: blind -> POST with amount_to = the posted chips; check -> CALL with
  amount_to = that seat's current street total; call (amount = chips ADDED) -> CALL with
  amount_to = street total + added; raise (amount = the raiser's TOTAL bet this round) ->
  RAISE with amount_to = amount. all_in = that seat's stack is 0 after the action. Antes are
  not in the history but are in the pot. Ignore unknown event kinds.
- obs: stacks = chips behind, bets = this street, pot includes current bets (add them if the
  kit's pot does not), min_raise_to / max_raise_to from state.can("raise") (0 if raising is
  not offered), max_raise_to = my bets + stack.
- Action out: FOLD -> Action.fold() if offered, else check. CALL -> Action.check() if
  to_call == 0 else Action.call(). RAISE -> Action.raise_to(int total), clamped to the
  offered min_amount..max_amount (an out-of-range total is a failed decision). Return ints.
- Cards are strings like "As", "Td": spec int = rank_index*4 + suit_index with ranks
  "23456789TJQKA" and suits "cdhs".
Then run: poker-agent check agent.py, and poker-agent play with 8 seats (our folder 4 times
plus the two examples) for 200 tables. Show me failed decisions and errors.
```

## Prompt 3: speed and safety

```
Write test_agent.py:
1. Time act() (memory decode/encode included) over 3,000 realistic states from `play` or
   replayed hand histories; print p50/p99/max with time.perf_counter_ns(). p99 must be under
   0.5 ms and max under 1 ms. If not: cache the bucket/e1 per decision and skip work.
2. 5,000 random observations straight into SpecBot: every action legal, no exceptions.
3. act() with garbage memory (b"", random bytes, truncated) returns a legal action.
4. A fresh Agent() per call (simulating forked copies) plays identically to one long-lived
   Agent over 50 tables with the same seed.
Fix anything that fails without changing strategy numbers. Then pack and upload.
```

## If something goes wrong

- **Self-test mismatch:** it is always a spec detail: float tolerance in §5a (`prod >= 0.8 - 1e-9`),
  the order of bucket rules (§2a), or `W_now` (product of `eq_vs * real` per opponent).
- **Kit state looks different:** fix only the adapter. The bot works on the normalized obs.
- **Failed decisions in `play`:** almost always the action conversion: check vs call, or a
  raise total outside the offered range.
- **The variant is not NLHE:** use [fallback/FALLBACK_SPEC_LITE.md](fallback/FALLBACK_SPEC_LITE.md)
  "Another variant on the day" for the tables, and keep this engine.

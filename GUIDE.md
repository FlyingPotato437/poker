# The poker bot, explained simply

This is a plain-language tour of this folder: what the bot is, what each part does, and what
was upgraded overnight and why it helps. No coding knowledge needed.

## What the bot is

The competition is a poker tournament between computer programs ("bots"). Eight bots sit at a
table, each starts with 2,000 chips, and the forced bets (the "blinds") go up every 25 hands.
After 200 hands, or when one bot has everything, the table ends and points are given out by
finishing place. Each bot gets only **1 millisecond** (a thousandth of a second) to decide each
move.

One millisecond is too short to "think" the way a human does. So this bot does most of its
thinking **ahead of time**: before the tournament, big computer runs produce **lookup tables**:
cheat sheets that say how strong every possible hand is, and when to go all-in. During the game
the bot mostly looks things up and does a little quick arithmetic.

It also **watches its opponents** while it plays. If a bot at the table folds too often, calls
too often, or always goes all-in, ours notices within a few dozen hands and adjusts to take
advantage.

## What each folder does

Think of the folder as a workshop with a few rooms.

| Folder or file | In plain terms |
|---|---|
| `nolimit/` | **The bot's brain and the practice table.** `runtime.py` is the bot itself: how it decides every move. `engine.py` is a poker table simulator that deals cards and enforces the rules. `zoo.py`, `rivals.py` hold dozens of practice opponents with different personalities and bugs. `harness.py` runs thousands of practice games at once. |
| `bundles/` | **The cheat sheets** (lookup tables), one file per game type: normal Texas Hold'em, Omaha, short deck, and more. |
| `params/` | **The bot's settings.** Each file is a set of dials (how aggressive, how often to bluff...). The best one is `cand_nlhe.json`; others are older or experimental versions. |
| `gpu/` | **The cheat-sheet factory.** Programs that build new lookup tables when a new kind of poker is announced. |
| `scripts/` | **Tools.** Run practice tournaments, compare two bots fairly (`ab_test.py`), test the bot under rule changes (`stipulation_sweep.py`), package it into one file for submission (`package_bot.py`), and the day-of tools (`day.py`, `go.py`). |
| `frozen/` | **The safe copy.** `rc1` is the last fully tested bot, locked so nobody can change it. It's the fallback if anything goes wrong. |
| `bench/` | **The lab notebook.** Results of every simulation, kept so decisions are based on evidence. |
| `tests/` | **Automatic checks** (240 of them) that make sure nothing is broken: legal moves, no crashes, correct hand rankings. |
| `variants/` | **Rule sheets** for different kinds of poker, including the template you fill in on the day (`ANNOUNCE.json`). |
| `examples/` | **A fake competition kit** used to rehearse the day. |
| `fallback/` | **A simpler backup bot** that can be rebuilt from scratch in 20–30 minutes if bringing our own code isn't allowed. |
| `adapter_template.py` | **The plug adapter.** The competition gives its own way of talking to bots; this small file translates between their format and ours. It's the one part written fresh on the day. |
| `DAYOF.md` | **The one page to follow at the event.** |
| `AGENTS.md`, `CODEX_PROMPTS.md` | **Instructions for Codex** (OpenAI's coding assistant, the one allowed at the event) so it knows how to drive this folder. |
| `FALLBACK_SPEC.md`, `CODEX_FALLBACK_PROMPTS.md` | The backup plan if pre-written code isn't allowed. |
| `VARIANTS.md` | What to do for each possible rule change. |
| `HANDOFF.md`, `PLAYBOOK.md`, `REHEARSAL.md`, `README.md` | The original notes, the day-of playbook, a practice drill, and the technical overview. |

## How we know a change is really better

Poker has a lot of luck, so "it won a few games" proves nothing. Every change was tested with
**paired games**: the old and new bot each play the exact same deals against the exact same
opponents, thousands of times, and we compare. A change was only kept if it won overall **and**
didn't lose clearly against any type of opponent. Many ideas failed this test and were left out.

Results are shown as "**% of fair**": a fair share of points is what you'd get by luck alone
(1/8 of the total). "+10%" means the new bot earns 10% more than the old one, relative to that
fair share.

## What was upgraded, and how it helps

**1. Faster decisions.** The bot used to pause occasionally while the computer cleaned up its
memory, sometimes in the middle of a decision. Now cleanup happens between tables. Omaha hands
are also scored about twice as fast. *Helps:* fewer decisions run over the 1 ms limit (a
timeout counts as a fold).

**2. Smarter opponent exploitation.** Before, if even one tough bot sat anywhere at the table,
ours stopped taking advantage of everyone. Now it judges each opponent who's actually in the
hand, and it spots obviously broken bots (always all-in, always folding) within about 5 hands.
*Helps:* most of our edge comes from beating weak bots; this lets us do it at far more tables.

**3. Wider play when few players are left.** With 2 or 3 players left, you should play many
more hands than at a full table, but the old bot played almost as tightly as with 8. Now it
loosens up properly, and plays about 80% of hands heads-up from the small blind. *Helps:* the
end of each table, which decides the biggest points, is played much better.

**4. A bug fix: it now re-raises and calls raises properly.** Facing a raise, the old bot
counted players who hadn't acted yet as if they'd already put chips in, so on the button it
folded hands like JJ and AK to an ordinary raise. *Helps:* stops throwing away strong hands.

**5. A smarter steal.** When everyone left to act almost always folds to raises, the bot now
raises with any two cards (ignoring players who never put chips in, like crashed bots).
*Helps:* free chips from tight and broken bots.

**6. Upgraded settings for every other kind of poker we prepared** (Omaha 4 and 5, short deck
and its Triton version, royal, 3-card hold'em), in case one of those is announced. *Helps:*
+7% to +10% in those games too.

**Combined result:** the final bot (frozen as `frozen/rc2`) beats the old one (`frozen/rc1`) by
**+11.3% of fair** in the official timing check (96,000 games, real 1 ms limit, all 16
matchups positive) and **+9.1%** in a one-time test against opponents never used before (all 12
positive). Earlier tests of the same upgrades showed **+14%** against bots copied from public
GitHub projects, gains against bots modeled on other teams' real preparation for this event,
and gains under all five different scoring tables tested (40 of 40 positive).

## What we tested and decided NOT to add

- **Switching strategies between tournaments:** simulated 3,000 full events: keeping the new
  bot was best or tied in 14 of 16 kinds of field. Switching mostly lost points.
- **A special mode against a "supercomputer" bot:** our bot already beats every strong-bot
  stand-in we built, because most points come from beating weak bots fastest. The special mode
  cost points.
- **Several ideas from GitHub bots** (bet-size reading, small stabs, bigger opens): none beat
  the new bot.
- **Re-shoving all-in over raises, smarter multiway calls, special play near the hand cap:**
  re-tested with better data; still neutral or losing.
- **Learning about opponents faster, or a "harder to exploit" setting:** each won in one
  place and lost in another (usually against strong rival bots), so the current settings stay.
- **More "textbook" play** (folding less, opening fewer hands, smaller raises): these lost
  points. Our bot's unusual habits are deliberate edges against weak bots.

## On the day, in one line

Fill in the announced rules, run one command (or let Codex run it with `scripts/codex_day.sh`),
submit the safe bot within minutes, then the stronger one once its checks pass. Details are in
`DAYOF.md`.

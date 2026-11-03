# Starter kit: "Tahoe Turbo" (rehearsal kit #2)

This folder plays the role of the organizers' starter kit for the timed rehearsal. Read this
file only, at T+0. Do not open `simulate.py` or `examples/answers/` before you finish:
reading the engine is not possible on the day.

## The game

**Tahoe Hold'em, no-limit, 8 players, sit-and-go.**

- 52-card deck. Each player gets **3 hole cards**.
- 5 community cards: flop 3, turn 1, river 1.
- A hand is the best five cards using **exactly 2 hole cards and 3 board cards** (as in
  Omaha). Standard hand ranking; the ace plays high or low in straights.
- Starting stack 1500.
- **Ante 5 chips from every player, every hand**, plus blinds.
- Blinds go up **every 15 hands**: 10/20, 15/30, 25/50, 40/80, 60/120, 100/200, 150/300,
  250/500, 400/800, 600/1200.
- The game ends when one player has all the chips, or after **200 hands**. In that case the
  remaining players are ranked by ICM on their stacks.
- **Points by finishing place**: 10, 6, 4, 3, 2, 1, 0, 0.

## Your bot

Submit **one Python file** that defines `class PokerBot`:

```python
class PokerBot:
    def __init__(self, player_id: str): ...
    def get_move(self, state) -> tuple: ...
```

The kit creates one `PokerBot` per seat per game and calls `get_move` once per decision.

**Time limit: 1 ms per `get_move` call, wall clock.** A call that runs over, raises, or
returns an illegal move is treated as a fold. That includes `"check"` when there is a bet to
call. There is no end-of-hand callback.

### `state` (attributes)

| Attribute | Meaning |
|---|---|
| `hand_number` | 1, 2, 3, ... |
| `street` | `"PREFLOP"`, `"FLOP"`, `"TURN"`, `"RIVER"` |
| `my_id` | your player id, e.g. `"p4"` |
| `dealer_id` | id of the button |
| `players` | list in seat order (clockwise); see below |
| `my_cards` | your hole cards as ints (encoding below) |
| `board` | community cards as ints |
| `pot` | chips in the pot from **earlier streets** (and antes); this street's bets are in `players[i].street_bet` |
| `to_call` | chips you need to add to call |
| `min_raise` / `max_raise` | smallest and largest legal raise as your **total bet for this street** (`max_raise` = all-in); `None` if you cannot raise |
| `small_blind`, `big_blind`, `ante` | current amounts |
| `history` | this hand's actions so far: `(player_id, street, action, street_total)`, where action is `"ante"`, `"sb"`, `"bb"`, `"fold"`, `"check"`, `"call"`, `"raise"` or `"allin"` and `street_total` is that player's total bet on this street after the action |

Each entry of `players` has `id`, `stack` (chips behind, not counting `street_bet`),
`street_bet`, `folded`, `all_in` and `busted` (out of the game).

### Cards

Each card is an int `0..51`: `card = suit * 13 + rank`, where rank `0..12` = `2 3 4 5 6 7 8 9
T J Q K A` and suit `0..3` = spades, hearts, diamonds, clubs.

### Moves

Return one of:

- `("fold", 0)`
- `("check", 0)`
- `("call", 0)`
- `("raise", total)`, where `total` is your street total and `min_raise <= total <= max_raise`
- `("allin", 0)`

## Test locally

```bash
python examples/kit2/simulate.py my_bot.py --games 20
```

It prints points per game, timeouts, exceptions and illegal moves, and exits non-zero if
there were any exceptions or illegal moves. `--parity` also checks that a bot packaged with
our `package_bot.py` plays exactly as its core does when fed our own `Obs` (adapter check).

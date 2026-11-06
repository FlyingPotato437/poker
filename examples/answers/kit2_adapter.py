# ===========================================================================
# Answer key for rehearsal kit #2 (examples/kit2). Don't read before the drill.
#
# scripts/package_bot.py appends this file to nolimit/runtime.py plus the embedded
# tables, so everything in runtime.py (Obs, PrepBot, FOLD/CALL/RAISE/POST, ...) is in
# scope. Lines tagged "PACKAGE: strip" only exist so this file also runs unpackaged.
#
# Map the kit's state onto Obs (see the Obs docstring in runtime.py):
#   [ ] seat, button, sb/bb/ante amounts, hand_no (any id that changes every hand)
#   [ ] street: 0 preflop, then 1, 2, ... per board street
#   [ ] hole, board as our card ids (card_id() below handles "As"/"Td"/"10d")
#   [ ] stacks: chips BEHIND per seat (0 if busted); bets: chips put in THIS round
#   [ ] in_hand: dealt in and not folded; pot: everything committed this hand
#   [ ] to_call, min_raise_to, max_raise_to as raise-TO totals (convert if kit uses raise-BY)
#   [ ] history: (seat, street, kind, amount_to, all_in) incl. blinds as POST; if the kit
#       has no action log, build one by diffing bets between calls. all_in is True only on
#       a seat's LAST action when its stack is 0 now (flagging its earlier actions too skews
#       the shove stats: measured 3 wrong decisions in 8,678 on the mock kit)
#   [ ] check: python examples/mock_kit.py-style parity (same seed, our Obs vs the kit's
#       state) should agree on every decision
#   [ ] return value: map (FOLD|CALL|RAISE, raise_to) to the kit's action format
# Then run: python scripts/package_bot.py ... and test dist/bot.py in the kit simulator.
# ===========================================================================
import os  # noqa: E402

from nolimit.runtime import *  # noqa: F401,F403  # PACKAGE: strip
from nolimit.runtime import base64  # noqa: F401  # PACKAGE: strip

_TABLES = None


def _tables():
    """Load once per process; the host may build a fresh bot for every table."""
    global _TABLES
    if _TABLES is None:
        g = globals()
        if "_BUNDLE_B64" in g:
            _TABLES = Tables(base64.b64decode(g["_BUNDLE_B64"]))
        elif "_BUNDLE_FILE" in g:
            here = os.path.dirname(os.path.abspath(__file__))
            with open(os.path.join(here, g["_BUNDLE_FILE"]), "rb") as fh:
                _TABLES = Tables(fh.read())
        elif os.environ.get("NOLIMIT_BUNDLE"):
            with open(os.environ["NOLIMIT_BUNDLE"], "rb") as fh:
                _TABLES = Tables(fh.read())
        else:
            _TABLES = HeuristicTables(os.environ.get("NOLIMIT_VARIANT", "nlhe"))
    return _TABLES


def make_core(seed=None):
    return PrepBot(_tables(), globals().get("_PARAMS"), seed=seed)


# Pay load cost at import, then move everything into the permanent GC generation and turn
# automatic collection off, so no collector pause lands inside a decision.
warmup(_tables())   # fill caches now: cold first decisions measured at 1-6 ms
gc_settle()         # collect + freeze, then no automatic GC; each new table collects first

_RANK_ALIASES = {"10": "T", "1": "A"}
_SUIT_ALIASES = {"c": 0, "d": 1, "h": 2, "s": 3, "♣": 0, "♦": 1, "♥": 2, "♠": 3}


def card_id(c, v=None):
    """Kit card -> our id (rank_index * suits + suit_index). Any suit bijection works."""
    v = v or _tables().v
    if isinstance(c, int):
        return c          # assumes the kit already uses our encoding: CHECK THIS
    if isinstance(c, (tuple, list)):
        r, s = str(c[0]), str(c[1])
    else:
        c = str(c).strip()
        r, s = c[:-1], c[-1]
    r = _RANK_ALIASES.get(r.upper(), r.upper())
    return v.ranks.index(r) * v.suits + _SUIT_ALIASES[s.lower()]


_STREET = {"PREFLOP": 0, "FLOP": 1, "TURN": 2, "RIVER": 3}


def kit_card(c, v):
    """Kit int (suit * 13 + rank, rank 0 = deuce) -> our id. Any suit bijection works."""
    return (c % 13) * v.suits + c // 13


def to_obs(s, agent):
    v = _tables().v
    ids = [p.id for p in s.players]
    me = ids.index(s.my_id)
    stacks = tuple(p.stack for p in s.players)
    bets = tuple(p.street_bet for p in s.players)
    log = [h for h in s.history if h[2] != "ante"]
    last = {h[0]: i for i, h in enumerate(log)}
    history, top = [], {}
    for i, (pid, street, act, total) in enumerate(log):
        seat, st = ids.index(pid), _STREET[street]
        if act in ("sb", "bb"):
            kind = POST
        elif act == "fold":
            kind = FOLD
        elif act == "raise" or (act == "allin" and total > top.get(st, 0)):
            kind = RAISE
        else:
            kind = CALL
        top[st] = max(top.get(st, 0), total)
        # all_in only on a seat's last action, and only if it has no chips now
        history.append((seat, st, kind, total, last[pid] == i and stacks[seat] == 0 and kind != FOLD))
    return Obs(hole=tuple(kit_card(c, v) for c in s.my_cards), board=tuple(kit_card(c, v) for c in s.board),
               street=_STREET[s.street], seat=me, button=ids.index(s.dealer_id), stacks=stacks, bets=bets,
               in_hand=tuple(not (p.folded or p.busted) for p in s.players),
               pot=s.pot + sum(bets), to_call=s.to_call,
               min_raise_to=s.min_raise or 0,
               max_raise_to=s.max_raise if s.max_raise is not None else bets[me] + stacks[me],
               sb=s.small_blind, bb=s.big_blind, ante=s.ante, hand_no=s.hand_number, history=tuple(history))


def to_kit_action(kind, amount, s):
    if kind == FOLD:
        return ("fold", 0)
    if kind == CALL:
        return ("check", 0) if s.to_call == 0 else ("call", 0)
    return ("raise", amount)


class PokerBot:
    def __init__(self, player_id):
        self.core = make_core()

    def get_move(self, state):
        # PrepBot.act never raises; a bug in to_obs/to_kit_action would, and the kit folds us.
        kind, amount = self.core.act(to_obs(state, self))
        return to_kit_action(kind, amount, state)

# ===========================================================================
# Adapter: starter-kit Agent interface -> PrepBot.  THIS IS THE PART TO EDIT ON THE DAY.
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
import gc  # noqa: E402
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


# Pay load cost at import, then move everything into the permanent GC generation so
# collector pauses during play stay small.
warmup(_tables())   # fill caches now: cold first decisions measured at 1-6 ms
gc.collect()
gc.freeze()

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


def to_obs(state, agent):
    """Starter-kit state -> Obs. Fill in once the kit's interface is known."""
    raise NotImplementedError("map the starter kit's state onto Obs (checklist at top)")


def to_kit_action(kind, amount, state):
    """(FOLD | CALL | RAISE, raise_to) -> whatever the kit's act() must return."""
    raise NotImplementedError("map our action onto the kit's action format")


class Bot:
    """Rename / subclass to match the kit (e.g. `class MyAgent(Agent)`) and rename act()."""

    def __init__(self, *args, **kwargs):
        self.core = make_core()

    def act(self, state):
        # PrepBot.act never raises (it checks/folds on internal errors); a bug in
        # to_obs/to_kit_action still does, and the host then folds us. Test them.
        kind, amount = self.core.act(to_obs(state, self))
        return to_kit_action(kind, amount, state)

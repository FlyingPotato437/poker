# Answer key for the mock-kit rehearsal (examples/mock_kit.py). Same shape as
# adapter_template.py with to_obs / to_kit_action filled in for the mock format.
import os  # noqa: E402

from nolimit.runtime import *  # noqa: F401,F403  # PACKAGE: strip
from nolimit.runtime import base64  # noqa: F401  # PACKAGE: strip

_TABLES = None


def _tables():
    global _TABLES
    if _TABLES is None:
        g = globals()
        if "_BUNDLE_B64" in g:
            _TABLES = Tables(base64.b64decode(g["_BUNDLE_B64"]))
        elif "_BUNDLE_FILE" in g:
            here = os.path.dirname(os.path.abspath(__file__))
            with open(os.path.join(here, g["_BUNDLE_FILE"]), "rb") as fh:
                _TABLES = Tables(fh.read())
        else:
            _TABLES = HeuristicTables(os.environ.get("NOLIMIT_VARIANT", "nlhe"))
    return _TABLES


def make_core(seed=None):
    return PrepBot(_tables(), globals().get("_PARAMS"), seed=seed)


warmup(_tables())   # fill caches now: cold first decisions measured at 1-6 ms
if "gc_settle" in globals():   # collect + freeze, then no automatic GC; each new table collects first
    gc_settle()
else:                          # rc1's runtime (frozen/rc1) has no gc_settle: same adapter works there
    import gc
    gc.collect()
    gc.freeze()

_STREET = {"preflop": 0, "flop": 1, "turn": 2, "river": 3}
_KIND = {"blind": POST, "fold": FOLD, "check": CALL, "call": CALL, "raise": RAISE, "bet": RAISE}


def card_id(c, v=None):
    v = v or _tables().v
    return v.ranks.index(c[0]) * v.suits + "cdhs".index(c[1])


def to_obs(s, agent):
    v = _tables().v
    players = s["players"]
    stacks = tuple(p["chips"] for p in players)
    bets = tuple(p["round_bet"] for p in players)
    cur = max(bets)
    # A seat with no chips left went all-in on its latest action, and only that one.
    last = {e["seat"]: i for i, e in enumerate(s["log"])}
    history = tuple((e["seat"], _STREET[e["street"]], _KIND[e["action"]], e["total"],
                     last[e["seat"]] == i and stacks[e["seat"]] == 0 and e["action"] != "fold")
                    for i, e in enumerate(s["log"]))
    return Obs(hole=tuple(card_id(c, v) for c in s["hole_cards"]),
               board=tuple(card_id(c, v) for c in s["community"]),
               street=_STREET[s["street"]], seat=s["me"], button=s["dealer"],
               stacks=stacks, bets=bets, in_hand=tuple(p["active"] for p in players),
               pot=s["pot"], to_call=s["amount_to_call"],
               min_raise_to=(cur + s["min_raise_by"]) if s["min_raise_by"] is not None else 0,
               max_raise_to=(cur + s["max_raise_by"]) if s["max_raise_by"] is not None else bets[s["me"]] + stacks[s["me"]],
               sb=s["blinds"]["small"], bb=s["blinds"]["big"], ante=0,
               hand_no=s["hand_id"], history=history)


def to_kit_action(kind, amount, s):
    if kind == FOLD:
        return {"action": "fold"}
    if kind == CALL:
        return {"action": "check" if s["amount_to_call"] == 0 else "call"}
    cur = max(p["round_bet"] for p in s["players"])
    return {"action": "raise", "amount": amount - cur}


class Bot:
    def __init__(self, *args, **kwargs):
        self.core = make_core()

    def get_action(self, state):
        kind, amount = self.core.act(to_obs(state, self))
        return to_kit_action(kind, amount, state)

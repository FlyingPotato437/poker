"""A fake starter kit for rehearsing the adapter. Its interface is deliberately different
from ours: string cards, street names, raise-BY amounts, dict actions, no hand_end callback.

Rehearsal: copy adapter_template.py, fill in to_obs/to_kit_action for this format
(answer key: examples/adapter_mock_solution.py), package it, then run:

    python scripts/package_bot.py --bundle bundles/nlhe.nlb --adapter my_adapter.py --out dist/mock.py
    python examples/mock_kit.py dist/mock.py

The real kit will differ; the point is to practice the mapping under time pressure.
"""
import importlib.util
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nolimit.engine import SNG  # noqa: E402
from nolimit.runtime import CALL, FOLD, POST, RAISE, BotBase, card_str  # noqa: E402
from nolimit.zoo import ZOO  # noqa: E402

STREETS = ("preflop", "flop", "turn", "river")
KIND_NAMES = {FOLD: "fold", CALL: "call", RAISE: "raise"}


def kit_state(obs, v):
    """What the mock kit hands to Agent.get_action()."""
    log = []
    for seat, st, kind, amt, _ai in obs.history:
        if kind == POST:
            log.append({"seat": seat, "street": "preflop", "action": "blind", "total": amt})
        else:
            log.append({"seat": seat, "street": STREETS[st], "action": KIND_NAMES[kind], "total": amt})
    cur = max(obs.bets)
    return {
        "hand_id": f"h{obs.hand_no}",
        "street": STREETS[obs.street],
        "hole_cards": [card_str(v, c) for c in obs.hole],
        "community": [card_str(v, c) for c in obs.board],
        "me": obs.seat,
        "dealer": obs.button,
        "blinds": {"small": obs.sb, "big": obs.bb},
        "players": [{"seat": i, "chips": obs.stacks[i], "round_bet": obs.bets[i],
                     "active": obs.in_hand[i]} for i in range(len(obs.stacks))],
        "pot": obs.pot,
        "amount_to_call": obs.to_call,
        "min_raise_by": (obs.min_raise_to - cur) if obs.min_raise_to else None,
        "max_raise_by": (obs.max_raise_to - cur) if obs.min_raise_to else None,
        "log": log,
    }


class KitSeat(BotBase):
    """Runs a kit-style agent (get_action(state) -> dict) inside our engine.

    With a `shadow` (the same bot, same seed, fed our own Obs directly), every decision is
    compared: a lossless adapter makes the two agree on every single action."""

    def __init__(self, kit_agent, variant, shadow=None):
        self.kit = kit_agent
        self.v = variant
        self.shadow = shadow
        self.decisions = self.mismatches = 0
        self.first_mismatch = None

    def act(self, obs):
        want = self.shadow.act(obs) if self.shadow else None
        a = self.kit.get_action(kit_state(obs, self.v))
        name = a["action"]
        if name == "fold":
            got = (FOLD, 0)
        elif name in ("check", "call"):
            got = (CALL, 0)
        else:
            got = (RAISE, max(obs.bets) + int(a["amount"]))
        if want is not None:
            self.decisions += 1
            if (want[0], want[1] if want[0] == RAISE else 0) != got:
                self.mismatches += 1
                self.first_mismatch = self.first_mismatch or (obs, want, got)
        return got


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    spec = importlib.util.spec_from_file_location("kit_bot", sys.argv[1])
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    T = mod._tables()
    v = T.v.to_dict()
    # Parity compares the adapter only: the per-decision deadline depends on timing (the
    # shadow pays the cold cache, the kit-side copy then hits it), so switch it off here.
    mod.PrepBot.deadline = 1e9
    totals = [0.0, 0.0]
    decisions = mismatches = 0
    first = None
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    for g in range(n):
        # The packaged bot through the mock-kit interface and the same bot direct, in seats 0
        # and 1, each deal played twice with the two swapped: seat 0 sits left of the
        # always-fold timeout bot and steals its blinds, worth ~10 pts/table on its own.
        for swap in (False, True):
            kit_bot = mod.Bot()
            kit_bot.core = mod.make_core(seed=g + 1000)     # same seed as the shadow
            kit, core = KitSeat(kit_bot, T.v, shadow=mod.make_core(seed=g + 1000)), mod.make_core(seed=g)
            agents = [core, kit] if swap else [kit, core]
            agents += [ZOO[k](T, seed=g) for k in ("tag", "lag", "shover", "nit", "station", "timeout")]
            sng = SNG(v, agents, rng=random.Random(g))
            pts = sng.run()
            ki, ci = (1, 0) if swap else (0, 1)
            assert sng.errors[ki] == 0, "adapter raised: the kit would have auto-folded these decisions"
            totals[0] += pts[ki]
            totals[1] += pts[ci]
            decisions += kit.decisions
            mismatches += kit.mismatches
            first = first or kit.first_mismatch
    print(f"{2 * n} SNGs: via mock kit {totals[0] / (2 * n):.1f} pts/table, direct {totals[1] / (2 * n):.1f} "
          f"(similar numbers = adapter maps state correctly)")
    print(f"decision parity: {decisions - mismatches}/{decisions} identical to the bot fed our Obs directly"
          + (f"; first mismatch: wanted {first[1]}, got {first[2]} at hand {first[0].hand_no} "
             f"street {first[0].street}" if first else ""))
    if mismatches > max(1, decisions // 1000):
        sys.exit("adapter loses information: more than 0.1% of decisions differ")


if __name__ == "__main__":
    main()

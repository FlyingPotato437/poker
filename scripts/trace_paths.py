"""Play kit2 games with a packaged bot and count how often the upgraded code paths fire.

    python scripts/trace_paths.py dist/day/k1.py 20

Exploit level per decision, degenerate-seat flags, sh_open lookups, gc state after import
and gc collections per table (gc_settle: one per PokerBot built)."""
import collections
import gc
import importlib.util
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "examples", "kit2"))
import simulate as K  # noqa: E402
from nolimit.engine import SNG  # noqa: E402
from nolimit.runtime import HeuristicTables  # noqa: E402
from nolimit.zoo import ZOO  # noqa: E402

path, games = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 20
mod = K.load(path)
print("gc enabled after import:", gc.isenabled(), " _GC_CONTROL:", mod._GC_CONTROL, " freeze count:", gc.get_freeze_count())

levels, kinds = collections.Counter(), collections.Counter()
orig = mod.PrepBot._ex_level


def traced(self, obs):
    lv = orig(self, obs)
    levels[(obs.street > 0, lv)] += 1
    for s, c in self._ex_cache.items():
        if c[2]:
            kinds[c[2]] += 1
    return lv


mod.PrepBot._ex_level = traced


class Count(list):
    n = 0

    def __getitem__(self, i):
        Count.n += 1
        return list.__getitem__(self, i)


mod.SH_OPEN = Count(mod.SH_OPEN)
hu_calls = [0]
house_tables = HeuristicTables(K.VARIANT)
collects = [0]
gc.callbacks.append(lambda phase, info: collects.__setitem__(0, collects[0] + (phase == "start")))
seats = []
for g in range(games):
    rng = random.Random(g)
    house = [ZOO[k](house_tables, seed=g * 10 + i) for i, k in enumerate(rng.sample(K.HOUSE, 7))]
    slot = g % 8
    seat = K.KitSeat(mod.PokerBot(f"p{slot}"), K.VARIANT, 8)
    agents = house[:slot] + [seat] + house[slot:]
    SNG(K.VARIANT, agents, rng=random.Random(1000 + g), **K.RULES).run()
    seats.append(seat)
tot = {k: sum(getattr(s, k) for s in seats) for k in ("decisions", "timeouts", "exceptions", "illegal")}
print("kit2 totals:", tot, " max ms", round(max(s.max_ms for s in seats), 2))
print("exploit level by (postflop, level 0-4):", dict(sorted(levels.items())))
print("degenerate-seat flags seen (1 = check/fold, 2 = jam/min-raise):", dict(kinds))
print("sh_open curve lookups:", Count.n)
print("gc collections during play (one per PokerBot built = per table):", collects[0], "for", games, "tables")

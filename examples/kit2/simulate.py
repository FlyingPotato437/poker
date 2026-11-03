"""Mock starter kit #2 ("Tahoe Turbo"): the kit's simulator. README.md is the kit's documentation.

    python examples/kit2/simulate.py my_bot.py [--games 20] [--parity]

The submitted file is loaded the way a host would (fresh module, PokerBot per seat per game),
plays one seat against 7 house bots, and every get_move() is timed: over 1 ms, an exception
or an illegal move counts and is played as a fold. Under the hood it is our own engine
(nolimit/engine.py) with this kit's rules; the point is the interface, which is deliberately
unlike both ours and mock kit #1: int cards in suit*13+rank order, string player ids, a pot
that leaves out this street's bets, raise-to street totals, check vs call enforced, antes.
"""
import argparse
import importlib.util
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from nolimit.engine import SNG  # noqa: E402
from nolimit.runtime import CALL, FOLD, POST, RAISE, BotBase, HeuristicTables, Variant  # noqa: E402
from nolimit.zoo import ZOO  # noqa: E402

VARIANT = Variant("tahoe", n_hole=3, hole_used=2)
POINTS = (10, 6, 4, 3, 2, 1, 0, 0)
SCHEDULE = ((10, 20), (15, 30), (25, 50), (40, 80), (60, 120), (100, 200), (150, 300), (250, 500),
            (400, 800), (600, 1200))
RULES = {"start_stack": 1500, "schedule": SCHEDULE, "hands_per_level": 15, "ante": 5, "payouts": POINTS,
         "max_hands": 200}
STREETS = ("PREFLOP", "FLOP", "TURN", "RIVER")
HOUSE = ("tag", "lag", "nit", "station", "shover", "maniac", "limper", "timeout")
LIMIT_MS = 1.0


class Player:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class State:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def kit_card(c, v):
    return (c % v.suits) * 13 + (c // v.suits)


def kit_state(obs, v, n_seats):
    pid = [f"p{i}" for i in range(n_seats)]
    busted = [not obs.in_hand[i] and obs.stacks[i] == 0 for i in range(n_seats)]
    hist = [(pid[s], "PREFLOP", "ante", 0) for s in range(n_seats) if obs.ante and not busted[s]]
    total, posts = {}, 0
    for seat, st, kind, amt, all_in in obs.history:
        if kind == POST:
            name, posts = ("sb", "bb")[min(posts, 1)], posts + 1
        elif kind == FOLD:
            name = "fold"
        elif all_in:
            name = "allin"
        elif kind == CALL:
            name = "check" if amt == total.get((seat, st), 0) else "call"
        else:
            name = "raise"
        total[(seat, st)] = amt
        hist.append((pid[seat], STREETS[st], name, amt))
    me = obs.seat
    return State(
        hand_number=obs.hand_no + 1, street=STREETS[obs.street], my_id=pid[me], dealer_id=pid[obs.button],
        players=[Player(id=pid[i], stack=obs.stacks[i], street_bet=obs.bets[i], busted=busted[i],
                        folded=not obs.in_hand[i] and not busted[i], all_in=obs.in_hand[i] and obs.stacks[i] == 0)
                 for i in range(n_seats)],
        my_cards=[kit_card(c, v) for c in obs.hole], board=[kit_card(c, v) for c in obs.board],
        pot=obs.pot - sum(obs.bets), to_call=obs.to_call,
        min_raise=obs.min_raise_to or None, max_raise=obs.max_raise_to if obs.min_raise_to else None,
        small_blind=obs.sb, big_blind=obs.bb, ante=obs.ante, history=hist)


class KitSeat(BotBase):
    """The submitted PokerBot inside our engine, timed and checked like the kit would."""

    def __init__(self, bot, v, n_seats, shadow=None, timed=True):
        self.bot, self.v, self.n, self.shadow, self.timed = bot, v, n_seats, shadow, timed
        self.decisions = self.timeouts = self.exceptions = self.illegal = self.mismatches = 0
        self.max_ms = 0.0
        self.first_bad = None

    def act(self, obs):
        want = self.shadow.act(obs) if self.shadow else None
        st = kit_state(obs, self.v, self.n)
        self.decisions += 1
        t0 = time.perf_counter()
        try:
            move = self.bot.get_move(st)
        except Exception as e:      # noqa: BLE001
            self.exceptions += 1
            self.first_bad = self.first_bad or f"exception: {e!r}"
            return (CALL, 0) if obs.to_call == 0 else (FOLD, 0)
        ms = (time.perf_counter() - t0) * 1000
        self.max_ms = max(self.max_ms, ms)
        got = self._parse(move, st, obs)
        if want is not None and (want[0], want[1] if want[0] == RAISE else 0) != got:
            self.mismatches += 1
        if self.timed and ms > LIMIT_MS:
            self.timeouts += 1
            return (CALL, 0) if obs.to_call == 0 else (FOLD, 0)
        return got

    def _parse(self, move, st, obs):
        try:
            name, amt = move[0], int(move[1])
        except Exception:           # noqa: BLE001
            name, amt = None, 0
        me = obs.seat
        if name == "fold":
            return (FOLD, 0)
        if name == "check" and st.to_call == 0:
            return (CALL, 0)
        if name == "call" and st.to_call > 0:
            return (CALL, 0)
        if name == "allin":
            all_in_to = obs.bets[me] + obs.stacks[me]
            return (RAISE, all_in_to) if obs.min_raise_to and all_in_to > max(obs.bets) else (CALL, 0)
        if name == "raise" and st.min_raise is not None and st.min_raise <= amt <= st.max_raise:
            return (RAISE, amt)
        self.illegal += 1
        self.first_bad = self.first_bad or f"illegal move {move!r} (to_call {st.to_call}, raise {st.min_raise}..{st.max_raise})"
        return (CALL, 0) if obs.to_call == 0 else (FOLD, 0)


def load(path):
    spec = importlib.util.spec_from_file_location(f"submitted_{random.random():.9f}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bot")
    ap.add_argument("--games", type=int, default=20)
    ap.add_argument("--parity", action="store_true",
                    help="our packaged bots only: compare every move with the bot's core fed our Obs directly")
    args = ap.parse_args()
    t0 = time.perf_counter()
    mod = load(args.bot)
    print(f"loaded {args.bot} in {time.perf_counter() - t0:.2f}s")
    if args.parity:
        mod.PrepBot.deadline = 1e9     # parity compares the adapter, not timing
    house_tables = HeuristicTables(VARIANT)
    seat_stats = []
    pts_total = 0.0
    for g in range(args.games):
        rng = random.Random(g)
        house = [ZOO[k](house_tables, seed=g * 10 + i) for i, k in enumerate(rng.sample(HOUSE, 7))]
        slot = g % 8
        bot = mod.PokerBot(f"p{slot}")
        shadow = None
        if args.parity:
            bot.core = mod.make_core(seed=g)
            shadow = mod.make_core(seed=g)
        seat = KitSeat(bot, VARIANT, 8, shadow=shadow, timed=not args.parity)
        agents = house[:slot] + [seat] + house[slot:]
        sng = SNG(VARIANT, agents, rng=random.Random(1000 + g), **RULES)
        pts = sng.run()
        pts_total += pts[slot]
        seat_stats.append(seat)
        print(f"game {g + 1:>3}: seat p{slot}  points {pts[slot]:5.2f}  hands {sng.hands_played:>3}  "
              f"decisions {seat.decisions:>4}  max {seat.max_ms:6.3f} ms")
    tot = {k: sum(getattr(s, k) for s in seat_stats) for k in ("decisions", "timeouts", "exceptions", "illegal",
                                                                "mismatches")}
    fair = sum(POINTS) / 8
    print(f"\n{args.games} games: {pts_total / args.games:.2f} points per game (fair share {fair:.2f}); "
          f"{tot['decisions']} decisions, {tot['timeouts']} over {LIMIT_MS} ms, {tot['exceptions']} exceptions, "
          f"{tot['illegal']} illegal")
    bad = next((s.first_bad for s in seat_stats if s.first_bad), None)
    if bad:
        print("first problem: " + bad)
    if args.parity:
        print(f"parity: {tot['decisions'] - tot['mismatches']}/{tot['decisions']} moves identical to the core fed "
              f"our Obs directly")
    if tot["exceptions"] or tot["illegal"] or (args.parity and tot["mismatches"] > tot["decisions"] // 1000):
        sys.exit(1)


if __name__ == "__main__":
    main()

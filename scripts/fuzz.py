"""Fuzz PrepBot for crashes, illegal actions and slow decisions.

    python scripts/fuzz.py                       # every bundle in bundles/ + heuristic tables
    python scripts/fuzz.py --games 400 --no-numpy
    python scripts/fuzz.py --params params/cand_nlhe.json   # tuned params (exploit, sh_open, ... paths)

Layer 1 plays real SNGs under extreme setups (2-9 seats, 5-500 bb stacks, antes, odd
blinds) with PrepBot in debug mode, so any internal exception fails loudly, and checks
every action it returns before the engine can coerce it.
Layer 2 feeds degraded observations of the kind a rushed adapter produces: empty or
blind-less history, string hand ids, inconsistent bets. The bot must still answer legally.
"""
import argparse
import glob
import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


PARAMS = None    # --params: tuned params for every PrepBot (default: DEFAULT_PARAMS)


class Violation(Exception):
    pass


def check_action(obs, a):
    from nolimit.runtime import CALL, FOLD, RAISE
    if not (isinstance(a, tuple) and len(a) == 2):
        raise Violation(f"bad action shape {a!r}")
    kind, amt = a
    if kind not in (FOLD, CALL, RAISE):
        raise Violation(f"bad kind {kind}")
    if kind == FOLD and obs.to_call == 0:
        raise Violation("folded when checking was free")
    if kind == RAISE:
        if obs.min_raise_to <= 0:
            raise Violation("raised when raising was not allowed")
        if not obs.min_raise_to <= amt <= obs.max_raise_to:
            raise Violation(f"raise to {amt} outside [{obs.min_raise_to}, {obs.max_raise_to}]")


def layer1(T, games, seed, worst):
    from nolimit.engine import SNG
    from nolimit.runtime import PrepBot
    from nolimit.zoo import ZOO

    class Checked(PrepBot):
        def act(self, obs):
            t0 = time.perf_counter()
            a = PrepBot.act(self, obs)
            dt = (time.perf_counter() - t0) * 1000
            worst.append(dt)
            check_action(obs, a)
            return a

    rng = random.Random(seed)
    decisions = 0
    for g in range(games):
        n = rng.choice((2, 3, 4, 6, 8, 8, 8, 9))
        bb = rng.choice((2, 20, 20, 50))
        sb = rng.choice((bb // 2, bb // 2, bb))
        stack = bb * rng.choice((5, 10, 25, 100, 100, 500))
        ante = rng.choice((0, 0, 0, max(1, bb // 10)))
        sched = tuple((sb * m, bb * m) for m in (1, 2, 3, 5, 8, 12))
        agents = []
        for i in range(n):
            if rng.random() < 0.5:
                agents.append(Checked(T, PARAMS, seed=g * 10 + i, debug=True))
            else:
                agents.append(ZOO[rng.choice(list(ZOO))](T, seed=g * 10 + i))
        if not any(isinstance(a, Checked) for a in agents):
            agents[0] = Checked(T, PARAMS, seed=g, debug=True)
        sng = SNG(T.v, agents, rng=random.Random(g), start_stack=stack, schedule=sched,
                  hands_per_level=rng.choice((5, 25)), max_hands=rng.choice((30, 200)), ante=ante,
                  payouts=sorted((rng.random() * 100 for _ in range(n)), reverse=True))
        sng.run()
        for i, a in enumerate(agents):
            if isinstance(a, Checked) and sng.errors[i]:
                raise Violation(f"game {g}: seat {i} raised inside act()")
        if sum(sng.stacks) != n * stack:
            raise Violation(f"game {g}: chips not conserved")
        decisions += sum(t.count for i, t in enumerate(sng.timing) if isinstance(agents[i], Checked))
    return decisions


def layer2(T, n, seed, worst):
    from nolimit.runtime import CALL, FOLD, POST, RAISE, Obs, PrepBot
    rng = random.Random(seed)
    v = T.v
    bot = PrepBot(T, PARAMS, seed=seed, debug=True)
    for i in range(n):
        seats = rng.choice((2, 3, 6, 8, 9))
        me = rng.randrange(seats)
        street = rng.randrange(len(v.streets) + 1)
        n_board = sum(v.streets[:street])
        cards = rng.sample(range(v.D), v.n_hole + n_board)
        bb = rng.choice((2, 20, 100))
        stacks = [rng.choice((0, 1, bb, 5 * bb, 50 * bb, 300 * bb)) for _ in range(seats)]
        stacks[me] = max(stacks[me], 1)
        bets = [rng.choice((0, 0, bb // 2, bb, 3 * bb, 20 * bb)) for _ in range(seats)]
        in_hand = [rng.random() < 0.7 for _ in range(seats)]
        in_hand[me] = True
        if sum(in_hand) < 2:
            in_hand[(me + 1) % seats] = True
        cur = max(bets)
        to_call = max(0, cur - bets[me])
        max_to = bets[me] + stacks[me]
        min_to = min(cur + max(bb, 1), max_to) if max_to > cur and rng.random() < 0.85 else 0
        hist_kind = rng.choice(("good", "empty", "noposts", "garbage"))
        hist = []
        if hist_kind in ("good", "noposts"):
            if hist_kind == "good":
                hist += [((me + 1) % seats, 0, POST, bb // 2, False), ((me + 2) % seats, 0, POST, bb, False)]
            for _ in range(rng.randrange(6)):
                s = rng.randrange(seats)
                hist.append((s, rng.randrange(street + 1), rng.choice((FOLD, CALL, RAISE)),
                             rng.choice((0, bb, 3 * bb)), rng.random() < 0.1))
        elif hist_kind == "garbage":
            hist = [(rng.randrange(seats), rng.randrange(4), rng.randrange(4), rng.randrange(10 ** 6), False)
                    for _ in range(rng.randrange(10))]
        obs = Obs(hole=tuple(cards[:v.n_hole]), board=tuple(cards[v.n_hole:]), street=street, seat=me,
                  button=rng.randrange(seats), stacks=tuple(stacks), bets=tuple(bets), in_hand=tuple(in_hand),
                  pot=sum(bets) + rng.choice((0, bb, 40 * bb)), to_call=to_call, min_raise_to=min_to,
                  max_raise_to=max_to, sb=bb // 2, bb=bb, ante=0,
                  hand_no=rng.choice((i, f"h{i}", None)), history=tuple(hist))
        t0 = time.perf_counter()
        try:
            a = bot.act(obs)
        except Exception as e:
            raise Violation(f"layer2 case {i} ({hist_kind} history): {type(e).__name__}: {e}") from e
        worst.append((time.perf_counter() - t0) * 1000)
        check_action(obs, a)
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--games", type=int, default=150, help="layer-1 games per table set")
    ap.add_argument("--cases", type=int, default=20000, help="layer-2 random observations per table set")
    ap.add_argument("--no-numpy", action="store_true")
    ap.add_argument("--bundles", nargs="*")
    ap.add_argument("--params", help="tuned params JSON for the fuzzed PrepBots")
    ap.add_argument("--no-heuristic", action="store_true", help="skip the heuristic table sets")
    args = ap.parse_args()
    global PARAMS
    if args.params:
        import json
        with open(args.params) as fh:
            PARAMS = json.load(fh)
    if args.no_numpy:
        os.environ["NOLIMIT_NO_NUMPY"] = "1"
    from nolimit.runtime import PRESETS, HeuristicTables, Tables, np

    sets = []
    for path in args.bundles or sorted(glob.glob(os.path.join(ROOT, "bundles", "*.nlb"))):
        with open(path, "rb") as fh:
            sets.append((os.path.basename(path), Tables(fh.read())))
    for name in () if args.no_heuristic else PRESETS:
        sets.append((f"heuristic:{name}", HeuristicTables(name)))
    print(f"numpy {'on' if np is not None else 'off'}; {len(sets)} table sets; params {args.params or 'default'}")
    failed = 0
    for name, T in sets:
        worst = []
        try:
            d1 = layer1(T, args.games, 1, worst)
            d2 = layer2(T, args.cases, 2, worst)
            worst.sort()
            print(f"  ok   {name:<28} {d1 + d2:>7,} decisions  p99.9 {worst[int(.999 * len(worst))]:.3f} ms"
                  f"  max {worst[-1]:.3f} ms")
        except Violation as e:
            failed += 1
            print(f"  FAIL {name:<28} {e}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

"""Fallback spec bot (fallback/spec_bot.py): legal actions, no exceptions, fast, sane tables."""
import random
import time

from fallback import spec_bot as S
from nolimit.engine import SNG
from nolimit.runtime import CALL, FOLD, RAISE, HeuristicTables, Obs, PRESETS
from nolimit.zoo import ZOO


def test_tables_parse():
    assert len(S.HAND) == 169
    assert abs(S.HAND["32o"][0] - 1.0) < 1e-9 and S.HAND["AA"][0] < 0.005
    for n, rows in S._SHOVE.items():
        assert len(rows) == n - 1 and all(len(r) == len(S.PF_STACKS) for r in rows)
    assert all(len(r) == len(S.PF_STACKS) for r in S._CALL.values())
    assert all(len(r) == 13 for r in S.POST_EQ.values())
    # equity vs range is monotone-ish and sane
    assert S.eq_vs_range("AA", 0.05) > 0.75 and S.eq_vs_range("72o", 0.05) < 0.3
    assert abs(S.eq_vs_range("KQo", 1.0) - S.HAND["KQo"][1]) < 1e-9


def test_cards_and_buckets():
    assert S.card("As") == (14, 3) and S.card("10h") == (10, 2) and S.card(0) == (2, 0)
    assert S.hand_name(["Ah", "Kh"]) == "AKs" and S.hand_name([51, 46]) == "AKo"
    assert S.post_bucket(["Ah", "Ad"], ["2c", "7d", "9s"]) == 7          # overpair
    assert S.post_bucket(["Ah", "Kd"], ["Ac", "7d", "9s"]) == 6          # top pair, good kicker
    assert S.post_bucket(["9h", "9d"], ["9c", "7d", "2s"]) == 9          # set
    assert S.post_bucket(["Ah", "5h"], ["Kh", "7h", "2s"]) == 2          # flush draw
    assert S.post_bucket(["Ah", "5h"], ["Kh", "7h", "2h"]) == 11         # flush
    assert S.post_bucket(["2c", "3d"], ["Kh", "Kd", "9s", "9c", "Ah"]) == 0   # plays the board


def _random_obs(rng):
    n = rng.choice((2, 3, 6, 8))
    me = rng.randrange(n)
    street = rng.choice((0, 0, 1, 2, 3))
    cards = rng.sample(range(52), 2 + (0, 3, 4, 5)[street])
    bb = rng.choice((20, 100, 400))
    stacks = [rng.choice((0, bb, 5 * bb, 15 * bb, 60 * bb)) for _ in range(n)]
    stacks[me] = max(stacks[me], bb)
    to_call = rng.choice((0, 0, bb, 3 * bb, stacks[me] + bb))
    bets = [0] * n
    bets[(me + 1) % n] = to_call
    hist = (((me + 1) % n, 0, 3, bb // 2, False), ((me + 2) % n, 0, 3, bb, False))
    if to_call:
        hist += (((me + 1) % n, street, RAISE, to_call, rng.random() < 0.3),)
    mr = 0 if rng.random() < 0.2 else min(to_call + bb, stacks[me])
    return Obs(hole=tuple(cards[:2]), board=tuple(cards[2:]), street=street, seat=me, button=(me + n - 1) % n,
               stacks=tuple(stacks), bets=tuple(bets), in_hand=tuple(rng.random() < 0.8 or s == me for s in range(n)),
               pot=int(1.5 * bb) + to_call, to_call=min(to_call, stacks[me]), min_raise_to=mr, max_raise_to=stacks[me] + bets[me],
               sb=bb // 2, bb=bb, ante=0, hand_no=rng.randrange(5), history=hist)


def test_random_obs_legal_and_fast():
    rng = random.Random(7)
    bot = S.SpecBot(seed=1)
    cpu = []
    for _ in range(5000):
        obs = _random_obs(rng)
        t = time.process_time()
        kind, amt = bot.act(obs)
        cpu.append(time.process_time() - t)
        assert kind in (FOLD, CALL, RAISE)
        if kind == RAISE:
            assert obs.min_raise_to > 0 and obs.min_raise_to <= amt <= max(obs.max_raise_to, obs.min_raise_to)
        if kind == FOLD:
            assert obs.to_call > 0
    # CPU time, not wall time, so a loaded machine does not fail the test; typical is 20-60 us.
    assert sum(cpu) / len(cpu) < 0.0002
    assert sorted(cpu)[len(cpu) // 2] < 0.0002


def test_garbage_obs_falls_back():
    bot = S.SpecBot()
    assert bot.act({"to_call": 0}) == (CALL, 0)
    assert bot.act({"to_call": 10}) == (FOLD, 0)


def test_full_games_no_errors():
    T = HeuristicTables(PRESETS["nlhe"])
    for g in range(4):
        agents = [S.SpecBot(seed=g)] + [ZOO[k](T, seed=g + i) for i, k in
                                         enumerate(("tag", "station", "nit", "lag", "shover", "timeout", "maniac"))]
        sng = SNG(T.v, agents, rng=random.Random(g))
        sng.run()
        assert sng.errors[0] == 0
        assert sng.timing[0].count > 10

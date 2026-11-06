"""Short-stack / short-handed preflop features: off by default (same games), and each one
does what it says on a hand-built spot."""
import os
import random

import pytest

from nolimit.engine import SNG
from nolimit.runtime import CALL, FOLD, POST, RAISE, Obs, PrepBot, Tables
from nolimit.zoo import ZOO

BUNDLE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bundles", "nlhe_rng.nlb")
need_bundle = pytest.mark.skipif(not os.path.exists(BUNDLE), reason="bundles/nlhe_rng.nlb not built")
OFF = {"resteal_on": 0.0, "sh_open": 0.0, "hu_sb_play": 0.0, "mw_call": 0.0, "cap_fade": 0.0}


@pytest.fixture(scope="module")
def T():
    return Tables(open(BUNDLE, "rb").read())


def _play(T, params, g):
    hero = PrepBot(T, params, seed=g, debug=True)
    agents = [hero] + [ZOO[k](T, seed=g + i) for i, k in enumerate(("tag", "station", "nit", "lag", "shover", "timeout", "maniac"))]
    sng = SNG(T.v, agents, rng=random.Random(g))
    pts = sng.run()
    assert sum(sng.errors) == 0
    return pts, hero


def hole(T, s):
    from nolimit.runtime import parse_cards
    return tuple(parse_cards(T.v, s))


def _obs(T, cards, **kw):
    """BB (seat 1) facing an open from the button (seat 0), heads-up-ish 3 seats, 15 bb."""
    d = dict(hole=hole(T, cards), board=(), street=0, seat=1, button=0, stacks=(1700, 285, 0),
             bets=(60, 20, 0), in_hand=(True, True, False), pot=90, to_call=40, min_raise_to=100,
             max_raise_to=305, sb=10, bb=20, ante=0, hand_no=5,
             history=((2, 0, POST, 10, False), (1, 0, POST, 20, False), (0, 0, RAISE, 60, False)))
    d.update(kw)
    return Obs(**d)


@need_bundle
def test_defaults_play_the_same(monkeypatch, T):
    monkeypatch.setattr(PrepBot, "deadline", 1e9)
    for g in range(2):
        assert _play(T, None, g)[0] == _play(T, OFF, g)[0]


@need_bundle
def test_resteal(T):
    bot = PrepBot(T, {"resteal_on": 2.0, "resteal_call": 1.5, "pf_bb": 20.0}, seed=1)
    bot.new_table(1, 3)
    assert bot.act(_obs(T, "AhAd")) == (RAISE, 305)
    bot.new_table(1, 3)
    assert bot.act(_obs(T, "7h2d")) == (FOLD, 0)


@need_bundle
def test_hu_sb_opens_wider(T):
    # Heads-up, SB (= button, seat 0) first to act, 50 bb deep, with a hand around the 40th percentile.
    cards = next(c for c in ("Ts8h", "Js7h", "Qs5h", "9s7h", "Kh4d") if 0.33 < T.pct(T.hole_class(hole(T, c))) < 0.48)
    obs = Obs(hole=hole(T, cards), board=(), street=0, seat=0, button=0, stacks=(990, 980), bets=(10, 20),
              in_hand=(True, True), pot=30, to_call=10, min_raise_to=40, max_raise_to=1000, sb=10, bb=20,
              ante=0, hand_no=3, history=((0, 0, POST, 10, False), (1, 0, POST, 20, False)))
    base = {"open_base": 0.25, "open_late": 0.4, "sb_complete_pct": 0.0, "steal_exploit": 0.0}
    old = PrepBot(T, base, seed=1)
    old.new_table(0, 2)
    assert old.act(obs) == (FOLD, 0)
    new = PrepBot(T, dict(base, sh_open=1.0), seed=1)
    new.new_table(0, 2)
    assert new.act(obs)[0] == RAISE


@need_bundle
def test_cap_fade_counts_hands(T):
    bot = PrepBot(T, {"cap_fade": 10.0, "cap_hands": 20.0, "risk_av": 1.0}, seed=1)
    bot.new_table(1, 3)
    for h in range(20):
        bot.act(_obs(T, "7h2d", hand_no=h))
        if h < 10:
            assert bot.p["risk_av"] == 1.0
    assert bot._nh == 20 and bot.p["risk_av"] == 0.0
    bot._unfade()
    assert bot.p["risk_av"] == 1.0

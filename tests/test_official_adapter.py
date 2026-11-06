"""Contract tests against published documentation, not the unreleased SDK."""
import copy
import json
from types import SimpleNamespace as NS

import pytest

from nolimit.official_adapter import (OfficialBridge, STAT_FIELDS, action_to_sdk, consume_events,
                                     decode_memory, encode_memory, fresh_memory, identity, restore_stats)
from nolimit.runtime import CALL, FOLD, RAISE, HeuristicTables, ingest_history


class Action:
    def __init__(self, kind, amount=None):
        self.kind, self.amount = kind, amount

    @classmethod
    def check(cls):
        return cls("check")

    @classmethod
    def fold(cls):
        return cls("fold")

    @classmethod
    def call(cls):
        return cls("call")

    @classmethod
    def raise_to(cls, amount):
        return cls("raise", amount)


def ev(kind, seat=None, amount=0, cards=()):
    return NS(kind=kind, seat=seat, amount=amount, cards=cards)


def state(table_id="a", cards=("As", "Ah"), **updates):
    s = NS(config=NS(table_id=table_id, seat=0, variant="nlhe", players=3, starting_stack=2000,
                     payouts=[50, 30, 20], decision_ms=100, memory_bytes=65536),
           seat=0, button=0, cards=cards, board=(), pot=30, to_call=20, phase="betting", hand_number=0,
           blinds=NS(small=10, big=20, ante=0),
           seats=[NS(seat=0, stack=2000, bet=0, status="active"),
                  NS(seat=1, stack=1990, bet=10, status="active"),
                  NS(seat=2, stack=1980, bet=20, status="active")],
           events=[ev("hand", amount=0), ev("blind", 1, 10), ev("blind", 2, 20)],
           legal_actions=[NS(kind="fold", min_amount=None, max_amount=None),
                          NS(kind="call", min_amount=None, max_amount=None),
                          NS(kind="raise", min_amount=40, max_amount=2000)])
    s.history = s.events[1:]
    for key, value in updates.items():
        setattr(s, key, value)
    s.can = lambda kind: next((a for a in s.legal_actions if a.kind == kind), None)
    return s


@pytest.fixture(scope="module")
def tables():
    return HeuristicTables("nlhe")


def call(bridge, s, memory=b""):
    a, b = bridge.act(s, memory, Action)
    assert s.can(a.kind) is not None
    if a.kind == "raise":
        assert s.can("raise").min_amount <= a.amount <= s.can("raise").max_amount
    return (a.kind, a.amount), b


def test_worker_recreation_and_interleaving(tables):
    bridge = OfficialBridge(tables, None, {}, ["nlhe"])
    a = state("a")
    b = state("b", cards=("2c", "7d"))
    a1, mem = call(bridge, a)
    assert a1[0] == "raise", "Must exercise core, not quietly fall back"
    call(bridge, b)
    assert call(OfficialBridge(tables, None, {}, ["nlhe"]), a) == (a1, mem)
    # The same old memory and replayed events after a failed decision are idempotent.
    assert call(bridge, a) == (a1, mem)
    # Empty memory cannot inherit a different table's stats, RNG, or history.
    assert call(bridge, b) == call(OfficialBridge(tables, None, {}, ["nlhe"]), b)
    assert not tables._post_cache


def test_multiple_hands_after_hero_folds_count_once(tables):
    bridge = OfficialBridge(tables, None, {}, ["nlhe"])
    s = state()
    _, old = call(bridge, s)
    s.hand_number = 2
    s.events = [ev("fold", 0), ev("fold", 1), ev("stack", 0, 2000), ev("stack", 1, 1990),
                ev("stack", 2, 2010), ev("hand", amount=1), ev("blind", 0, 10), ev("blind", 1, 20),
                ev("fold", 2), ev("raise", 0, 60), ev("fold", 1),
                ev("stack", 0, 2020), ev("stack", 1, 1970), ev("stack", 2, 2010),
                ev("hand", amount=2), ev("blind", 1, 10), ev("blind", 2, 20)]
    _, new = call(bridge, s, old)
    d = json.loads(new)
    assert [row[STAT_FIELDS.index("hands")] for row in d["stats"]] == [2, 2, 2]
    assert d["stats"][0][STAT_FIELDS.index("pfr")] == 1
    assert call(bridge, s, old)[1] == new
    s.events = []
    assert json.loads(call(bridge, s, new)[1])["stats"] == d["stats"]


def test_calls_are_deltas_raises_totals_antes_not_blinds():
    d = fresh_memory("x", 3, 100)
    stats = restore_stats(d["stats"])
    events = [ev("hand", amount=1), ev("ante", 0, 5), ev("ante", 1, 5), ev("ante", 2, 5),
              ev("blind", 0, 10), ev("blind", 1, 20), ev("raise", 2, 40),
              ev("call", 0, 30), ev("call", 1, 20), ev("board", cards=("2c", "3c", "4c")),
              ev("check", 0), ev("raise", 1, 55), ev("call", 2, 55), ev("fold", 0)]
    consume_events(d, stats, events, {i: i for i in range(3)}, (3, 1, 1))
    assert [r[3] for r in d["hist"][:5]] == [10, 20, 40, 40, 40]
    assert d["hist"][2][4] is False
    assert d["hist"][6][4] is True
    assert d["hist"][7][4] is True
    consume_events(d, stats, [ev("hand", amount=2)], {i: i for i in range(3)}, (3, 1, 1))
    assert stats[2].pfr == 1 and stats[2].shove == 0
    assert stats[0].folded == 1


@pytest.mark.parametrize("bad", [b"", b"{", b"null", b"[]", b"\xff", b"x" * 65537,
                                  b'{"v":1}', b'{"v":1,"ctx":"x","turn":NaN}'])
def test_corrupt_memory_recovers(tables, bad):
    bridge = OfficialBridge(tables, None, {}, ["nlhe"])
    assert call(bridge, state(), bad) == call(bridge, state())


def test_memory_wrong_table_and_small_limit(tables):
    bridge = OfficialBridge(tables, None, {}, ["nlhe"])
    _, mem = call(bridge, state("x"))
    assert call(bridge, state("y"), mem) == call(bridge, state("y"))
    s = state()
    s.config.memory_bytes = 10
    a, blob = call(bridge, s)
    assert a[0] == "raise" and blob == b""


def test_reset_midhand_uses_full_current_history(tables):
    s = state(events=[ev("call", 1, 10)])
    s.history = [ev("blind", 1, 10), ev("blind", 2, 20), ev("call", 1, 10)]
    s.seats[1].bet = 20
    s.seats[1].stack = 1980
    _, blob = call(OfficialBridge(tables, None, {}, ["nlhe"]), s, b"truncated")
    assert [r[3] for r in json.loads(blob)["hist"]] == [10, 20, 20]


def test_legal_actions_only_and_exact_raise_bounds():
    s = state()
    assert action_to_sdk(s, RAISE, 39.9, Action).amount == 40
    assert action_to_sdk(s, RAISE, 9000, Action).amount == 2000
    s.legal_actions = [NS(kind="check")]
    for k in (FOLD, CALL, RAISE):
        assert action_to_sdk(s, k, 0, Action).kind == "check"
    s.legal_actions = [NS(kind="draw", min_amount=1, max_amount=3)]
    assert action_to_sdk(s, RAISE, 0, Action).kind == "draw"


def test_unknown_variant_or_phase_uses_legal_fallback(tables):
    b = OfficialBridge(tables, None, {}, ["nlhe"])
    s = state()
    s.config.variant = "unannounced-new-game"
    assert call(b, s) == (("fold", None), b"")
    s.config.variant = "nlhe"
    s.phase = "draw"
    s.legal_actions = [NS(kind="draw", min_amount=0, max_amount=3)]
    assert call(b, s) == (("draw", 0), b"")


def test_noncontiguous_seat_ids(tables):
    s = state()
    ids = {0: 7, 1: 9, 2: 4}
    for seat in s.seats:
        seat.seat = ids[seat.seat]
    for e in s.events:
        if e.seat is not None:
            e.seat = ids[e.seat]
    s.seat = s.button = 7
    a, blob = call(OfficialBridge(tables, None, {}, ["nlhe"]), s)
    assert a[0] == "raise" and blob


def test_stored_schema_validation_rejects_wrong_numeric_types():
    d = fresh_memory("x", 3, 2000)
    d["stats"][1][0] = True
    blob = json.dumps(d).encode()
    recovered, ok = decode_memory(blob, "x", 3, 2000)
    assert not ok and recovered["stats"][1][0] == 0


def test_no_cross_table_model_cache(tables):
    b = OfficialBridge(tables, None, {}, ["nlhe"])
    s = state(board=("2c", "3d", "Kh"), to_call=0, pot=300)
    s.events += [ev("call", 0, 20), ev("call", 1, 10), ev("check", 2),
                 ev("board", cards=s.board)]
    s.legal_actions = [NS(kind="check"), NS(kind="raise", min_amount=20, max_amount=2000)]
    call(b, s)
    assert tables._post_cache == {}


def test_reject_impossible_deck_capacity():
    royal = HeuristicTables("royal")
    b = OfficialBridge(royal, None, {}, ["royal"])
    s = state(cards=("As", "Ah"))
    s.config.variant = "royal"
    s.seats = [NS(seat=i, stack=2000, bet=0, status="active") for i in range(8)]
    assert call(b, s) == (("fold", None), b"")

"""Bridge for the published Nov 6 interface, pending verification against the kit.

Only returned bytes carry table state. Events are deltas since the last accepted
decision; replay after a timeout uses the old bytes and must not double-count.
This module deliberately does not import the SDK: the thin agent.py binds it.
"""
import hashlib
import json
import math
import time

from .runtime import CALL, FOLD, POST, RAISE, Obs, PrepBot, SeatStats, ingest_history
from .official_payouts import DecisionTables

VERSION = 1
STAT_FIELDS = tuple(k for k in SeatStats.__slots__ if k != "prior")
MAX_HISTORY = 512
MAX_MEMORY = 65536
KINDS = {"blind": POST, "fold": FOLD, "check": CALL, "call": CALL, "raise": RAISE}


def field(obj, name, default=None):
    return obj.get(name, default) if isinstance(obj, dict) else getattr(obj, name, default)


def chips(x):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or x < 0:
        raise ValueError("Invalid chip amount")
    return int(x)


def identity(state, seat_ids):
    cfg = state.config
    raw = json.dumps([field(cfg, "table_id"), state.seat, field(cfg, "variant"), seat_ids],
                     separators=(",", ":")).encode()
    return hashlib.blake2b(raw, digest_size=12).hexdigest()


def fresh_memory(context, n, stack, hand=None):
    return {"v": VERSION, "ctx": context, "turn": 0, "hand": hand, "street": 0, "board": 0,
            "stats": [[0] * len(STAT_FIELDS) for _ in range(n)], "hist": [],
            "bets": [0] * n, "left": [stack] * n}


def decode_memory(blob, context, n, stack):
    """No pickle; bounded schema validation. Corrupt or truncated state resets."""
    try:
        if not isinstance(blob, bytes) or not 0 < len(blob) <= MAX_MEMORY:
            raise ValueError("Missing or oversized memory")
        d = json.loads(blob)
        if not isinstance(d, dict) or d.get("v") != VERSION or d.get("ctx") != context:
            raise ValueError("Wrong memory context")
        for name in ("turn", "street", "board"):
            if type(d[name]) is not int or not 0 <= d[name] <= 1000000:
                raise ValueError("Invalid memory counter")
        if d["hand"] is not None and (type(d["hand"]) is not int or d["hand"] < 0):
            raise ValueError("Invalid hand number")
        for name, width in (("stats", len(STAT_FIELDS)), ("bets", None), ("left", None)):
            rows = d[name]
            if not isinstance(rows, list) or len(rows) != n:
                raise ValueError("Invalid memory seats")
            for row in rows:
                values = row if width else [row]
                if width and (not isinstance(row, list) or len(row) != width):
                    raise ValueError("Invalid statistics")
                if any(type(x) is not int or not 0 <= x <= 10**12 for x in values):
                    raise ValueError("Invalid memory number")
        if not isinstance(d["hist"], list) or len(d["hist"]) > MAX_HISTORY:
            raise ValueError("Invalid history length")
        for row in d["hist"]:
            if not isinstance(row, list) or len(row) != 5:
                raise ValueError("Invalid history row")
            s, street, kind, amount, all_in = row
            if (type(s) is not int or not 0 <= s < n or type(street) is not int
                    or not 0 <= street <= 20 or type(kind) is not int or kind not in KINDS.values()
                    or type(amount) is not int or not 0 <= amount <= 10**12 or type(all_in) is not bool):
                raise ValueError("Invalid history fields")
        return d, True
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError, OverflowError):
        return fresh_memory(context, n, stack), False


def encode_memory(d, limit):
    blob = json.dumps(d, separators=(",", ":"), allow_nan=False).encode()
    # A complete reset is preferable to the host repeatedly returning broken JSON.
    return blob if len(blob) <= min(MAX_MEMORY, max(0, int(limit))) else b""


def restore_stats(rows):
    stats = []
    for row in rows:
        st = SeatStats()
        for name, value in zip(STAT_FIELDS, row):
            setattr(st, name, value)
        stats.append(st)
    return stats


def finish_hand(d, stats):
    if d["hist"]:
        ingest_history(stats, d["hist"])
    d["hist"] = []


def consume_events(d, stats, events, seat_map, streets):
    for event in events:
        kind = field(event, "kind")
        if kind == "hand":
            hand = chips(field(event, "amount"))
            if d["hand"] != hand:
                finish_hand(d, stats)
                d.update(hand=hand, street=0, board=0, bets=[0] * len(stats))
            continue
        if kind == "board":
            d["board"] += len(field(event, "cards", ()) or ())
            total = 0
            for i, count in enumerate(streets, 1):
                total += count
                if d["board"] <= total:
                    d["street"] = i
                    break
            d["bets"] = [0] * len(stats)
            continue
        seat = seat_map.get(field(event, "seat"))
        if seat is None:
            continue
        if kind == "stack":
            d["left"][seat] = chips(field(event, "amount"))
            continue
        if kind == "ante":
            d["left"][seat] = max(0, d["left"][seat] - chips(field(event, "amount")))
            continue
        if kind not in KINDS:
            continue
        previous = d["bets"][seat]
        amount = chips(field(event, "amount", 0))
        if kind in ("blind", "call"):
            total = previous + amount
        elif kind == "raise":
            total = amount
        else:
            total = previous
        if kind in ("blind", "call", "raise"):
            d["left"][seat] = max(0, d["left"][seat] - max(0, total - previous))
            d["bets"][seat] = total
        if len(d["hist"]) >= MAX_HISTORY:
            # Exceptional histories remain legal but lose statistical detail.
            d["hist"] = []
        d["hist"].append([seat, d["street"], KINDS[kind], total,
                          kind not in ("fold", "check") and d["left"][seat] == 0])


def board_street(count, streets):
    if count == 0:
        return 0
    total = 0
    for i, size in enumerate(streets, 1):
        total += size
        if count == total:
            return i
    raise ValueError("Board does not match this model's betting streets")


def card_id(card, variant):
    # The published contract uses strings; accepting arbitrary ints would hide
    # an incompatible SDK encoding.
    if not isinstance(card, str) or len(card) != 2:
        raise ValueError("Expected two-character card string")
    return variant.ranks.index(card[0].upper()) * variant.suits + "cdhs".index(card[1].lower())


def blind_amounts(state):
    b = state.blinds
    if isinstance(b, (list, tuple)) and 2 <= len(b) <= 3:
        return chips(b[0]), chips(b[1]), chips(b[2]) if len(b) == 3 else 0
    # Exact field names must be checked against the released protocol.
    sb = field(b, "small", field(b, "small_blind", field(b, "sb")))
    bb = field(b, "big", field(b, "big_blind", field(b, "bb")))
    return chips(sb), chips(bb), chips(field(b, "ante", 0))


def fallback(state, Action):
    for kind in ("check", "fold", "call"):
        if state.can(kind) is not None:
            return getattr(Action, kind)()
    offered = state.legal_actions[0]
    return Action(field(offered, "kind"), field(offered, "min_amount"))


def action_to_sdk(state, kind, amount, Action):
    if kind == RAISE:
        offered = state.can("raise")
        if offered is not None:
            lo, hi = chips(field(offered, "min_amount")), chips(field(offered, "max_amount"))
            if lo <= hi:
                return Action.raise_to(min(max(int(amount), lo), hi))
    if kind == CALL or kind == RAISE:
        for name in ("check", "call"):
            if state.can(name) is not None:
                return getattr(Action, name)()
    return fallback(state, Action)


class OfficialBridge:
    """Shared instance holds only models/config; act recreates all table state."""
    def __init__(self, tables, basis, params, variant_ids):
        if params.get("alt"):
            raise ValueError("Unvalidated table selector is not supported by this adapter")
        self.tables, self.basis = tables, basis
        self.params = dict(params)
        if self.params.get("pool_w", 0) != 0:
            raise ValueError("pool_w must remain zero for the decision deadline")
        self.variant_ids = frozenset(variant_ids)

    def act(self, state, memory, Action):
        started = time.perf_counter()
        # A new variant/phase cannot silently be played as ordinary hold'em.
        if field(state.config, "variant") not in self.variant_ids or state.phase != "betting":
            return fallback(state, Action), b""
        try:
            return self._act(state, memory, Action, started)
        except (ValueError, TypeError, KeyError, IndexError, AttributeError, OverflowError):
            # Bad input/memory must not poison every later decision at the table.
            return fallback(state, Action), b""

    def _act(self, state, memory, Action, started):
        seats = list(state.seats)
        seat_ids = [field(s, "seat") for s in seats]
        seat_map = {s: i for i, s in enumerate(seat_ids)}
        n = len(seats)
        if len(seat_map) != n or not 2 <= n <= 10:
            raise ValueError("Invalid seat identities")
        if n * self.tables.v.n_hole + self.tables.v.n_board > self.tables.v.D:
            raise ValueError("This preset cannot deal a complete board at this table size")
        me = seat_map[state.seat]
        ctx = identity(state, seat_ids)
        d, restored = decode_memory(memory, ctx, n, chips(field(state.config, "starting_stack")))
        stats = restore_stats(d["stats"])
        events = list(state.events)
        if not restored and not any(field(e, "kind") == "hand" for e in events):
            # Current full history repairs a reset mid-hand. No guessed earlier
            # statistics or all-in flags: seed balances backwards from this hand.
            d["hand"] = chips(state.hand_number)
            events = list(state.history)
            d["left"] = [10**12] * n
        consume_events(d, stats, events, seat_map, self.tables.v.streets)
        if d["hand"] != state.hand_number:
            finish_hand(d, stats)
            d.update(hand=chips(state.hand_number), street=0, board=0, bets=[0] * n)
        stacks = tuple(chips(field(s, "stack")) for s in seats)
        bets = tuple(chips(field(s, "bet")) for s in seats)
        # Synchronize current public balances and only the latest action's all-in
        # flag. An earlier raise before a later shove was not itself all-in.
        last = {row[0]: i for i, row in enumerate(d["hist"])}
        for s, i in last.items():
            row = d["hist"][i]
            row[4] = field(seats[s], "status") == "all_in" and row[2] != FOLD
        d["left"] = list(stacks)
        d["bets"] = list(bets)
        sb, bb, ante = blind_amounts(state)
        v = self.tables.v
        hole = tuple(card_id(c, v) for c in state.cards)
        board = tuple(card_id(c, v) for c in state.board)
        if len(hole) != v.n_hole or len(set(hole + board)) != len(hole + board) or bb <= 0:
            raise ValueError("Cards or blinds do not match model")
        street = board_street(len(board), v.streets)
        offered = state.can("raise")
        obs = Obs(hole=hole, board=board, street=street, seat=me, button=seat_map[state.button],
                  stacks=stacks, bets=bets,
                  in_hand=tuple(field(s, "status") in ("active", "all_in") for s in seats),
                  pot=chips(state.pot), to_call=min(chips(state.to_call), stacks[me]),
                  min_raise_to=chips(field(offered, "min_amount")) if offered is not None else 0,
                  max_raise_to=chips(field(offered, "max_amount")) if offered is not None else bets[me] + stacks[me],
                  sb=sb, bb=bb, ante=ante, hand_no=state.hand_number,
                  history=tuple(tuple(row) for row in d["hist"]))
        tables = DecisionTables(self.tables, self.basis, field(state.config, "payouts"), n, ante / bb)
        # Fresh core; deterministic per-table, per-turn randomness survives worker
        # changes and retries without serializing Python's 624-word RNG state.
        seed = int(ctx[:16], 16) ^ d["turn"]
        core = PrepBot(tables, self.params, seed=seed, debug=True)
        core.stats, core.seat = stats, me
        core._hand_key = (obs.hand_no, hole)
        core._cls = tables.hole_class(hole)
        core._hist = obs.history
        # Count adapter time against the search budget, leaving room for JSON and
        # host overhead. This is a guard, not proof of a real 1 ms host deadline.
        allowance = float(field(state.config, "decision_ms", 1)) / 1000
        core.deadline = min(0.0006, max(0, allowance * 0.75 - (time.perf_counter() - started)))
        kind, amount = core.act(obs)
        d["stats"] = [[getattr(s, k) for k in STAT_FIELDS] for s in stats]
        d["turn"] += 1
        d["street"], d["board"] = street, len(board)
        out = encode_memory(d, field(state.config, "memory_bytes", MAX_MEMORY))
        return action_to_sdk(state, kind, amount, Action), out

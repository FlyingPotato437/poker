# ===========================================================================
# Adapter for the real kit (Nov 6 announcement): poker_agent_sdk, memory-based state.
#
#   class Agent(poker_agent_sdk.Agent):
#       def act(self, state, memory): return action, memory
#
# "self and globals cannot be relied on between calls": every call may land on a different
# forked copy of this file. So ALL per-table state (per-seat SeatStats counters, this hand's
# history in our Obs format, tracked stacks / street bets / committed chips, hand number,
# hands seen) travels in `memory` (bytes, struct-packed, versioned, crc-checked, ~1.5 KB at
# 8 seats, constant in the number of hands). Every call:
#   1. decode memory (any problem: start fresh, never raise)
#   2. reset the process-wide PrepBot to an empty table and pour the counters back in
#   3. replay state.events (since our last turn) into the tracked hand; a "hand" event first
#      ingests the previous hand's complete history into the counters (what hand_end does)
#   4. build Obs, PrepBot.act, map to Action, encode memory
# Module globals hold only load-once data (tables, the PrepBot object, its params): no table
# state, so nothing leaks between tables and any copy can answer any table.
#
# Mock + parity test: examples/sdk2026_mock/run_mock.py (fake poker_agent_sdk, our engine).
#
# KIT-CHECK list (unknown field formats; each spot is marked "# KIT-CHECK:" below). On the
# day, open the kit README / SDK source and confirm or fix each:
#   K1  import path / class names: poker_agent_sdk.Agent, poker_agent_sdk.Action
#   K2  Agent.__init__ signature (does the SDK base class take arguments?)
#   K3  memory type: bytes (we also accept str / bytearray / None)
#   K4  event attribute names (kind, seat, amount, cards) and kind spellings
#       ("hand", "ante", "blind", "fold", "check", "call", "raise", "board", "show", "win",
#       "stack"); is there a separate "bet" kind? (treated like "raise": a street TOTAL)
#   K5  "call" amount = chips ADDED (not the total); "raise" amount = street TOTAL
#   K6  "blind" amount = chips posted; a straddle / dead blind / BB-ante also a "blind"?
#   K7  do events include OUR OWN actions? (handled both ways: see _apply_pending)
#   K8  "board" event: one per street with the new cards, or one per card (both handled)
#   K9  "stack" events at hand end for every seat incl. busted ones (needed for all-in flags)
#   K10 seat numbers in table order? (we map sorted seat numbers -> 0..n-1; rotation is ok)
#   K11 state.seats[i].stack = chips BEHIND (not incl. the current bet); .bet = THIS round
#   K12 state.seats[i].status spellings: active / folded / all_in / busted
#   K13 state.blinds format ((sb, bb), (sb, bb, ante), object or dict) -> _blinds()
#   K14 state.pot: we do NOT use it (pot = chips committed per events); compare once
#   K15 state.can(kind) argument: a string "raise"/"call"/... or an enum? legal_actions kinds
#   K16 Action.raise_to(total) total = whole bet for the round (announcement says so)
#   K17 card strings "As", "Td" (maybe "10d"): card_id() handles both
#   K18 state.config.starting_stack (first hand's stacks before any stack event)
#   K19 hand event amount = hand number (any id that changes every hand is enough)
# ===========================================================================
import math  # noqa: E402
import operator  # noqa: E402
import os  # noqa: E402
import random  # noqa: E402
import struct  # noqa: E402
import zlib  # noqa: E402

from nolimit.runtime import *  # noqa: F401,F403  # PACKAGE: strip
from nolimit.runtime import base64  # noqa: F401  # PACKAGE: strip

try:
    # KIT-CHECK: K1 module and class names as in the kit README.
    import poker_agent_sdk as _sdk
    _SdkAgent = _sdk.Agent
    Action = _sdk.Action
except Exception:          # our own smoke tests (package_bot.py, day.py) have no SDK
    _sdk = None

    class _SdkAgent:
        def __init__(self, *args, **kwargs):
            pass

    class Action:
        def __init__(self, kind, amount=None):
            self.kind, self.amount = kind, amount

        @staticmethod
        def fold():
            return Action("fold")

        @staticmethod
        def check():
            return Action("check")

        @staticmethod
        def call():
            return Action("call")

        @staticmethod
        def raise_to(total):
            return Action("raise", total)

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


# Pay load cost at import, then move everything into the permanent GC generation and turn
# automatic collection off, so no collector pause lands inside a decision.
warmup(_tables())   # fill caches now: cold first decisions measured at 1-6 ms
if "gc_settle" in globals():   # collect + freeze, then no automatic GC; each new table collects first
    gc_settle()
else:                          # rc1's runtime (frozen/rc1) has no gc_settle: same adapter works there
    import gc
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
        c = str(c).strip()     # KIT-CHECK: K17 "As" / "Td" strings (announcement); "10d" also ok
        r, s = c[:-1], c[-1]
    r = _RANK_ALIASES.get(r.upper(), r.upper())
    return v.ranks.index(r) * v.suits + _SUIT_ALIASES[s.lower()]


# ---------------------------------------------------------------------------
# Memory format (version 1). Little-endian struct, then crc32 of everything before it.
#   header: magic "N6", version, n seats, my seat, street, board cards seen, flags,
#           hand_no, hands seen, hands ingested, alt arm, pending kind, n history,
#           pending amount, hand ante
#   per seat: behind, street bet, committed this hand, live (dealt in, not folded)
#   per seat: SeatStats counters (all slots but `prior`, which is derived)
#   history:  (seat, street, kind, all_in, amount_to) per entry, this hand only
# ---------------------------------------------------------------------------
_MAGIC, _VER = b"N6", 1
_HDR = "<2sBBBbBBiHHbBHii"
_HDR_N = struct.calcsize(_HDR)
_CRC = struct.Struct("<I")
_SLOTS = tuple(s for s in SeatStats.__slots__ if s != "prior")
_GET = operator.attrgetter(*_SLOTS)
# st.<slot> = vals[i + j] for every slot, unrolled once at import (3x faster than setattr)
_ns = {}
exec("def _restore(st, v, i):\n" + "".join("    st.%s = v[i + %d]\n" % (k, j) for j, k in enumerate(_SLOTS)), _ns)
_restore = _ns["_restore"]
del _ns
_F_HAND, _F_PARTIAL = 1, 2      # a hand is in progress / we joined it mid-way (do not ingest)
_P_NONE, _P_FOLD, _P_CHECK, _P_CALL, _P_RAISE = 0, 1, 2, 3, 4
_FMT = {}
_DEBUG = bool(os.environ.get("NOLIMIT_SDK_DEBUG"))   # re-raise instead of the safe fallback
ERRORS = [0]                                           # adapter exceptions caught (tests read it)


def _fmt(n, nh):
    key = (n, nh)
    s = _FMT.get(key)
    if s is None:
        s = _FMT[key] = struct.Struct(_HDR + "iiiB" * n + "I" * (n * len(_SLOTS)) + "BBBBi" * nh)
    return s


def _name(k):
    """Event / action / status kind -> lower-case string (str, enum with .value or .name)."""
    if isinstance(k, str):
        return k.lower()
    s = getattr(k, "value", None)
    if not isinstance(s, str):
        s = getattr(k, "name", None)
    return (s if isinstance(s, str) else str(k)).lower()


class _Rng:
    """PrepBot.rng (rules-mode bluffs only), seeded from the decision itself so every copy of
    the bot makes the same choice; built only if used (the EV engine never touches it)."""
    __slots__ = ("seed", "r")

    def __init__(self, seed):
        self.seed, self.r = seed, None

    def random(self):
        if self.r is None:
            self.r = random.Random(self.seed)
        return self.r.random()

    def __getattr__(self, name):
        if name in _Rng.__slots__:
            raise AttributeError(name)
        if self.r is None:
            self.r = random.Random(self.seed)
        return getattr(self.r, name)


class _Table:
    """One table's tracked state, rebuilt from memory on every call."""
    __slots__ = ("n", "me", "street", "board_n", "flags", "hand_no", "nh", "ning", "arm",
                 "pend", "pend_amt", "ante", "behind", "bets", "comm", "live", "hist", "core",
                 "cum")

    def fresh(self, core, n, me, start_stack):
        self.n, self.me, self.core = n, me, core
        self.street, self.board_n, self.flags, self.hand_no = -1, 0, 0, -1
        self.nh = self.ning = 0
        self.arm, self.pend, self.pend_amt, self.ante = -1, _P_NONE, 0, 0
        self.behind = [start_stack] * n
        self.bets = [0] * n
        self.comm = [0] * n
        self.live = [False] * n
        self.hist = []
        core.new_table(me, n, _collect=False)

    def load(self, core, mem, n, me):
        """False if the memory is not ours / damaged (caller then starts fresh)."""
        if len(mem) < _HDR_N + 4:
            return False
        body = mem[:-4]
        if _CRC.unpack_from(mem, len(mem) - 4)[0] != zlib.crc32(body):
            return False
        h = struct.unpack_from(_HDR, body)
        if h[0] != _MAGIC or h[1] != _VER or h[2] != n or h[3] != me:
            return False
        nh = h[12]
        f = _fmt(n, nh)
        if len(body) != f.size:
            return False
        vals = f.unpack(body)
        (_, _, _, _, self.street, self.board_n, self.flags, self.hand_no, self.nh, self.ning,
         self.arm, self.pend, _, self.pend_amt, self.ante) = vals[:15]
        self.n, self.me, self.core = n, me, core
        i = 15
        self.behind = list(vals[i:i + 4 * n:4])
        self.bets = list(vals[i + 1:i + 4 * n:4])
        self.comm = list(vals[i + 2:i + 4 * n:4])
        self.live = [bool(x) for x in vals[i + 3:i + 4 * n:4]]
        i += 4 * n
        core.new_table(me, n, _collect=False)
        k = len(_SLOTS)
        for st in core.stats:
            _restore(st, vals, i)
            i += k
        self.hist = [(vals[j], vals[j + 1], vals[j + 2], vals[j + 4], bool(vals[j + 3]))
                     for j in range(i, i + 5 * nh, 5)]
        if self.arm >= 0 and core._arms:
            core.p = core._arms[self.arm]     # new_table() reset it to the base params
            core.arm = self.arm
        w = core.p.get("pool_w", 0.0)
        if w > 0:
            pool_priors(core.stats, me, w)
        return True

    def dump(self):
        n, hist = self.n, self.hist
        vals = [_MAGIC, _VER, n, self.me, self.street, min(self.board_n, 255), self.flags,
                self.hand_no, min(self.nh, 65535), min(self.ning, 65535), self.arm, self.pend,
                len(hist), self.pend_amt, self.ante]
        for i in range(n):
            vals += (self.behind[i], self.bets[i], self.comm[i], self.live[i])
        for st in self.core.stats:
            vals.extend(_GET(st))
        for h in hist:
            vals += (h[0], h[1], h[2], h[4], h[3])
        body = _fmt(n, len(hist)).pack(*vals)
        return body + _CRC.pack(zlib.crc32(body))

    # -- events -----------------------------------------------------------
    def _end_hand(self):
        """Ingest the finished hand into the counters (what PrepBot.observe(hand_end) does)."""
        if self.flags & _F_HAND and not self.flags & _F_PARTIAL and self.hist:
            core = self.core
            ingest_history(core.stats, self.hist)
            self.ning += 1
            w = core.p.get("pool_w", 0.0)
            if w > 0:
                pool_priors(core.stats, self.me, w)
            r = core._rule
            if r and self.ning == r["from_hand"]:
                core._ingested, core._ingested_keys = set(range(self.ning)), set()
                core._choose_params()
                self.arm = core.arm
        self.flags = 0

    def _new_hand(self, hand_no):
        self._end_hand()
        self.nh += 1
        self.hand_no = hand_no
        self.street, self.board_n, self.ante = 0, 0, 0
        n = self.n
        self.bets, self.comm = [0] * n, [0] * n
        self.live = [b > 0 for b in self.behind]
        self.hist = []
        self.flags = _F_HAND

    def _act(self, s, kind, amount):
        """One betting event for seat index s; kind in fold/check/call/raise/bet/blind."""
        bets, behind = self.bets, self.behind
        if kind == "fold":
            self.live[s] = False
            self.hist.append((s, self.street, FOLD, bets[s], False))
        elif kind == "check":
            self.hist.append((s, self.street, CALL, bets[s], False))
        elif kind == "call":
            a = int(amount or 0)      # KIT-CHECK: K5 call amount = chips ADDED this action
            behind[s] -= a
            bets[s] += a
            self.comm[s] += a
            self.hist.append((s, self.street, CALL, bets[s], behind[s] <= 0))
        elif kind in ("raise", "bet"):
            tot = int(amount)        # KIT-CHECK: K5 raise amount = raiser's street TOTAL
            top = max(bets)
            a = tot - bets[s]
            behind[s] -= a
            self.comm[s] += a
            bets[s] = tot
            # a short all-in that does not go over the top bet is a call in our history
            self.hist.append((s, self.street, RAISE if tot > top else CALL, tot, behind[s] <= 0))
        elif kind == "blind":
            a = int(amount or 0)      # KIT-CHECK: K6 blind amount = chips posted
            behind[s] -= a
            bets[s] += a
            self.comm[s] += a
            self.hist.append((s, 0, POST, bets[s], behind[s] <= 0))

    def _apply_pending(self, events, idx):
        """Our own last action, if the kit leaves it out of the events.
        KIT-CHECK: K7 if events DO include our actions this is a no-op (first action event
        after our turn is ours); if they don't, we apply the action we returned last time."""
        if self.pend == _P_NONE:
            return
        p, self.pend = self.pend, _P_NONE
        for e in events:
            k = _name(e.kind)
            if k in ("fold", "check", "call", "raise", "bet"):
                if idx.get(e.seat) == self.me:
                    return                 # the kit reports our own actions
                break
            if k in ("hand", "board", "ante", "blind", "show", "win", "stack"):
                break
        if not self.flags & _F_HAND:
            return
        me = self.me
        if p == _P_FOLD:
            self._act(me, "fold", 0)
        elif p == _P_CHECK:
            self._act(me, "check", 0)
        elif p == _P_CALL:
            self._act(me, "call", self.pend_amt)
        else:
            self._act(me, "raise", self.pend_amt)

    def feed(self, events, idx):
        self._apply_pending(events, idx)
        cum = self.cum
        for e in events:
            # KIT-CHECK: K4 attribute names kind / seat / amount / cards
            k = _name(e.kind)
            if k == "hand":
                self._new_hand(int(e.amount))        # KIT-CHECK: K19 amount = hand number
                continue
            s = idx.get(e.seat)
            if k == "board":
                if not self.flags & _F_HAND:
                    continue
                cards = e.cards                        # KIT-CHECK: K8 only the NEW cards
                self.board_n += len(cards) if cards else (cum[self.street] - self.board_n if self.street < len(cum) else 1)
                st = sum(1 for c in cum if c <= self.board_n)
                if st != self.street:
                    self.street = st
                    self.bets = [0] * self.n
                continue
            if s is None:
                continue
            if k == "stack":
                self.behind[s] = int(e.amount)       # KIT-CHECK: K9 stack at hand end
            elif k == "ante":
                if self.flags & _F_HAND:
                    a = int(e.amount or 0)
                    self.behind[s] -= a
                    self.comm[s] += a
                    if a > self.ante:
                        self.ante = a
            elif k in ("fold", "check", "call", "raise", "bet", "blind"):
                if self.flags & _F_HAND:
                    self._act(s, k, e.amount)
            # show / win / unknown kinds: nothing to track


def _blinds(state):
    """(sb, bb, ante or None) from state.blinds.
    KIT-CHECK: K13 format of state.blinds (tuple, object, dict); fix here if none fits."""
    b = getattr(state, "blinds", None)
    if isinstance(b, dict):
        g = b.get
        sb, bb, an = g("small", g("sb")), g("big", g("bb")), g("ante")
    elif isinstance(b, (tuple, list)):
        sb, bb = b[0], b[1]
        an = b[2] if len(b) > 2 else None
    else:
        sb = getattr(b, "small", getattr(b, "sb", None))
        bb = getattr(b, "big", getattr(b, "bb", None))
        an = getattr(b, "ante", None)
    return int(sb or 0), int(bb or 0), an


def _can(state, kind):
    """Legal action of this kind (with min_amount / max_amount) or None.
    KIT-CHECK: K15 state.can() takes a string here; if it takes an enum, pass that instead."""
    f = getattr(state, "can", None)
    if f is not None:
        try:
            return f(kind)
        except Exception:
            pass
    for a in getattr(state, "legal_actions", None) or ():
        if _name(getattr(a, "kind", a)) == kind:
            return a
    return None


_LIVE = ("active", "all_in", "allin", "all-in")       # KIT-CHECK: K12 status spellings
_ALLIN = ("all_in", "allin", "all-in")


def _street_of(cum, n_board):
    return sum(1 for c in cum if c <= n_board)


def _cum(v):
    out, t = [], 0
    for x in v.streets:
        t += x
        out.append(t)
    return out


def _prepare(core, state, memory):
    """Memory + events -> (_Table, Obs) with core restored. Everything but the decision."""
    T = core.T
    v = T.v
    # KIT-CHECK: K10 seat numbers (anonymized per table) -> 0..n-1 in sorted order; that must
    # be table (clockwise) order, a rotation is fine (mock --rotate: 100% parity).
    seats = sorted(state.seats, key=lambda s: s.seat)
    idx = {s.seat: i for i, s in enumerate(seats)}
    n = len(seats)
    me = idx[state.seat]
    t = _Table()
    if isinstance(memory, str):                       # KIT-CHECK: K3 memory is bytes
        memory = memory.encode("latin-1")
    elif memory is not None and not isinstance(memory, bytes):
        memory = bytes(memory)
    ok = False
    if memory:
        try:
            ok = t.load(core, memory, n, me)
        except Exception:
            ok = False
    if not ok:
        cfg = getattr(state, "config", None)
        start = getattr(cfg, "starting_stack", None)    # KIT-CHECK: K18
        if start is None:
            start = max(s.stack + s.bet for s in seats)
        t.fresh(core, n, me, int(start))
    t.cum = _cum(v)
    t.feed(state.events or (), idx)

    # -- the decision's own view: the kit's state is authoritative for "now" --
    stacks = [int(s.stack) for s in seats]   # KIT-CHECK: K11 chips BEHIND (not incl. bet)
    bets = [int(s.bet) for s in seats]       # KIT-CHECK: K11 chips put in THIS round
    status = [_name(s.status) for s in seats]
    in_hand = tuple(st in _LIVE for st in status)
    board = tuple(card_id(c, v) for c in state.board)
    hole = tuple(card_id(c, v) for c in state.cards)
    street = _street_of(t.cum, len(board))
    if not t.flags & _F_HAND:
        # Joined mid-hand (no "hand" event seen, e.g. memory lost): what the state shows.
        t.nh += 1
        t.flags = _F_HAND | _F_PARTIAL
        t.hand_no = int(getattr(state, "hand_number", 0) or 0)
        t.street, t.board_n = street, len(board)
        t.bets, t.comm = list(bets), list(bets)
        t.live = list(in_hand)
        t.hist = []
    # all-in flags from the kit's status (exact now, tracking covers seats gone since)
    hist = t.hist
    for s in range(n):
        if status[s] in _ALLIN:
            for j in range(len(hist) - 1, -1, -1):
                h = hist[j]
                if h[0] == s and h[2] != FOLD:
                    if not h[4]:
                        hist[j] = (h[0], h[1], h[2], h[3], True)
                    break
    t.behind, t.bets, t.street, t.board_n = list(stacks), list(bets), street, len(board)
    sb, bb, an = _blinds(state)
    ante = t.ante if an is None else int(an)
    r = _can(state, "raise")
    to_call = int(state.to_call or 0)
    obs = Obs(hole=hole, board=board, street=street, seat=me,
              button=idx.get(state.button, 0), stacks=tuple(stacks), bets=tuple(bets),
              in_hand=in_hand,
              # KIT-CHECK: K14 pot = everything committed this hand incl. current bets (events)
              pot=sum(t.comm) if not t.flags & _F_PARTIAL else max(sum(bets), int(getattr(state, "pot", 0) or 0)),
              to_call=to_call,
              min_raise_to=math.ceil(r.min_amount) if r is not None else 0,
              max_raise_to=bets[me] + stacks[me],
              sb=sb, bb=bb, ante=ante, hand_no=t.hand_no, history=tuple(hist))
    core.seat = me
    core._nh = t.nh
    core._hand_key = (t.hand_no, hole)
    core._cls = T.hole_class(hole)
    core._hist = obs.history
    tid = getattr(getattr(state, "config", None), "table_id", "")
    core.rng = _Rng(zlib.crc32(("%s/%d/%d" % (tid, t.hand_no, len(hist))).encode()))
    return t, obs


def to_kit_action(kind, amount, state):
    """(FOLD | CALL | RAISE, raise_to) -> an Action from state.legal_actions."""
    if kind == RAISE:
        r = _can(state, "raise")
        if r is not None:
            lo = math.ceil(r.min_amount)     # int, never below the minimum
            hi = int(r.max_amount)                         # KIT-CHECK: K16 raise_to = round total
            return Action.raise_to(max(lo, min(int(amount), hi)))
        kind = CALL
    if kind == FOLD and _can(state, "fold") is not None:
        return Action.fold()
    if _can(state, "check") is not None:
        return Action.check()
    if _can(state, "call") is not None:
        return Action.call()
    return Action.fold()


def _pending(t, kind, amount, obs, state):
    """Remember what we returned, in case the kit leaves our own actions out of the events."""
    me = obs.seat
    if kind == RAISE and _can(state, "raise") is not None:
        r = _can(state, "raise")
        t.pend = _P_RAISE
        t.pend_amt = max(math.ceil(r.min_amount), min(int(amount), int(r.max_amount)))
    elif kind == FOLD and obs.to_call > 0:
        t.pend, t.pend_amt = _P_FOLD, 0
    elif obs.to_call > 0:
        t.pend, t.pend_amt = _P_CALL, min(obs.to_call, obs.stacks[me])
    else:
        t.pend, t.pend_amt = _P_CHECK, 0


def _safe(state):
    if _can(state, "check") is not None:
        return Action.check()
    if _can(state, "fold") is not None:
        return Action.fold()
    return Action.call()


class Agent(_SdkAgent):
    # KIT-CHECK: K2 if the SDK's Agent.__init__ needs arguments, pass them through (we do).
    def __init__(self, *args, **kwargs):
        try:
            super().__init__(*args, **kwargs)
        except TypeError:
            super().__init__()
        self.core = make_core()

    def act(self, state, memory):
        t = None
        try:
            t, obs = _prepare(self.core, state, memory)
            kind, amount = self.core.act(obs)        # never raises (checks/folds on errors)
            action = to_kit_action(kind, amount, state)
            _pending(t, kind, amount, obs, state)
            return action, t.dump()
        except Exception:
            ERRORS[0] += 1
            if _DEBUG:
                raise
            mem = b""
            if t is not None:
                try:
                    t.flags |= _F_PARTIAL       # this hand's history is suspect: don't ingest it
                    t.pend = _P_NONE
                    mem = t.dump()
                except Exception:
                    mem = b""
            try:
                return _safe(state), mem
            except Exception:
                return Action.fold(), mem

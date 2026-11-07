"""Mock of the real kit's protocol (Nov 6 announcement) around our engine, for adapter_sdk2026.py.

    .venv/bin/python scripts/package_bot.py --bundle bundles/nlhe_rng.nlb --params params/cand3_nlhe.json \
        --adapter adapter_sdk2026.py --out /tmp/sdk_bot.py
    .venv/bin/python examples/sdk2026_mock/run_mock.py /tmp/sdk_bot.py --games 30

What it does, per SNG (nolimit/engine.py, 8 seats):
  * `--sdk-seats` seats (default 2) play through the fake poker_agent_sdk: each decision gets a
    State (seat, cards "As", board, pot, to_call, legal_actions, seats, button, blinds, config,
    events since that seat's last turn) and that seat's memory bytes, and a FRESH
    `Agent()` instance answers (a forked copy that never saw this table). The returned memory
    is truncated at config.memory_bytes and handed back next turn.
  * events follow the announcement: hand (amount = hand number), ante, blind (chips posted),
    fold, check, call (chips ADDED), raise (street TOTAL), board (new cards only), show,
    win, stack (stack at hand end). Our own actions are included (--omit-own drops them).
  * --crash-rate p: that share of calls is treated as a timeout/exception: the action is
    replaced by check/fold, the memory is NOT updated and the same events are delivered again
    next turn (as the announcement says the host does).
  * parity: every decision is compared with a PrepBot shadow (same params/tables) fed our Obs
    and hand_end directly, i.e. PrepBot driven directly. Target 100%.
  * checks: 0 adapter exceptions (the adapter re-raises here), 0 illegal actions (kind not in
    legal_actions, raise amount not an int in min..max, memory not bytes).
  * --rotate: kit seat numbers rotated so we are always seat 0 (anonymized seats).
  * timing: the adapter's own work per call (decode memory + replay events + restore PrepBot +
    build Obs + encode memory, everything but PrepBot.act) and the memory size.
"""
import argparse
import importlib.util
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)        # the fake poker_agent_sdk
sys.path.insert(0, ROOT)

import poker_agent_sdk as sdk  # noqa: E402
from nolimit.engine import DEFAULT_SCHEDULE, SNG  # noqa: E402
from nolimit.runtime import CALL, FOLD, POST, RAISE, BotBase, card_str  # noqa: E402
from nolimit.zoo import ZOO  # noqa: E402

PHASES = ("preflop", "flop", "turn", "river", "street4", "street5")


class MockSNG(SNG):
    """Our engine plus a public event log in the announced format."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.log = []
        self.cum = []
        t = 0
        for x in self.v.streets:
            t += x
            self.cum.append(t)

    def _play_hand(self, alive):
        n = self.n
        self._start = list(self.stacks)
        self._dealt = [self.stacks[s] > 0 for s in range(n)]
        self._h_emit, self._st_emit, self._mb = 0, 0, [0] * n
        self.history, self.board = [], []
        self.log.append(sdk.Event("hand", None, self.hand_no + 1))
        level = min(self.hand_no // self.hands_per_level, len(self.schedule) - 1)
        bb = self.schedule[level][1]
        ante = int(round(self.ante_bb * bb)) if self.ante_bb else self.ante_amt
        if ante:
            for s in alive:
                self.log.append(sdk.Event("ante", s, min(ante, self.stacks[s])))
        super()._play_hand(alive)
        self.sync(len(self.v.streets))
        if sum(self.in_hand) > 1:
            for s in range(n):
                if self.in_hand[s]:
                    self.log.append(sdk.Event("show", s, None, [card_str(self.v, c) for c in self.hole[s]]))
        for s in alive:
            won = self.stacks[s] - self._start[s] + self.contrib[s]
            if won > 0:
                self.log.append(sdk.Event("win", s, won))
        for s in alive:
            self.log.append(sdk.Event("stack", s, self.stacks[s]))

    def _board_to(self, street):
        while self._st_emit < street and len(self.board) >= self.cum[self._st_emit]:
            lo = self.cum[self._st_emit - 1] if self._st_emit else 0
            cards = [card_str(self.v, c) for c in self.board[lo:self.cum[self._st_emit]]]
            self.log.append(sdk.Event("board", None, None, cards))
            self._st_emit += 1
            self._mb = [0] * self.n

    def sync(self, street):
        """Append events for every history entry not logged yet, then boards up to `street`."""
        h = self.history
        while self._h_emit < len(h):
            seat, st, kind, amt, _ai = h[self._h_emit]
            self._h_emit += 1
            self._board_to(st)
            prev = self._mb[seat]
            if kind == POST:
                self.log.append(sdk.Event("blind", seat, amt - prev))
            elif kind == FOLD:
                self.log.append(sdk.Event("fold", seat))
                continue
            elif kind == CALL:
                if amt == prev:
                    self.log.append(sdk.Event("check", seat))
                else:
                    self.log.append(sdk.Event("call", seat, amt - prev))
            else:
                self.log.append(sdk.Event("raise", seat, amt))
            self._mb[seat] = amt
        self._board_to(street)


class SdkSeat(BotBase):
    """Engine seat played by the adapter through the fake SDK, with a direct PrepBot shadow."""

    def __init__(self, mod, shadow, args, rng, table_id):
        self.mod, self.shadow, self.args, self.rng, self.table_id = mod, shadow, args, rng, table_id
        self.memory = b""
        self.cursor = 0
        self.sng = None
        self.decisions = self.mismatches = self.illegal = self.errors = self.crashes = 0
        self.first_mismatch = None
        self.overhead = []
        self.total = []
        self.mem_sizes = []

    def new_table(self, seat, n_seats):
        self.seat, self.n = seat, n_seats
        self.memory, self.cursor = b"", 0
        self.shadow.new_table(seat, n_seats)

    def observe(self, event):
        self.shadow.observe(event)

    def _kit_seat(self, s):
        return (s - self.seat) % self.n if self.args.rotate else s

    def state(self, obs, events):
        sng, v, a = self.sng, self.sng.v, self.args
        ks = self._kit_seat
        legal = []
        if obs.to_call <= 0:
            legal.append(sdk.LegalAction("check"))
        else:
            legal.append(sdk.LegalAction("fold"))
            legal.append(sdk.LegalAction("call", obs.to_call, obs.to_call))
        if obs.min_raise_to > 0:
            legal.append(sdk.LegalAction("raise", obs.min_raise_to, obs.max_raise_to))
        seats = []
        for s in range(self.n):
            if not sng._dealt[s]:
                status = "busted"
            elif not obs.in_hand[s]:
                status = "folded"
            elif obs.stacks[s] == 0:
                status = "all_in"
            else:
                status = "active"
            seats.append(sdk.SeatInfo(ks(s), obs.stacks[s], obs.bets[s], status))
        if a.rotate:
            seats.sort(key=lambda x: x.seat)
        hist = [{"seat": ks(h[0]), "street": h[1], "kind": ("fold", "call", "raise", "blind")[h[2]],
                 "amount": h[3]} for h in obs.history]
        level = min(sng.hand_no // sng.hands_per_level, len(sng.schedule) - 1)
        cfg = sdk.Config(table_id=self.table_id, seat=ks(self.seat), variant=v.name, players=self.n,
                         starting_stack=a.stack, blinds=tuple(sng.schedule),
                         hands_per_level=sng.hands_per_level, hand_cap=sng.max_hands,
                         payouts=tuple(sng.payouts), decision_ms=1, time_bank_ms=0,
                         memory_bytes=a.memory_bytes)
        return sdk.State(
            seat=ks(self.seat), cards=[card_str(v, c) for c in obs.hole],
            board=[card_str(v, c) for c in obs.board],
            pot=obs.pot - (sum(obs.bets) if a.pot_excl_bets else 0), to_call=obs.to_call,
            legal_actions=legal, history=hist, phase=PHASES[obs.street], seats=seats,
            button=ks(obs.button), blind_level=level, blinds=(obs.sb, obs.bb),
            hands_until_next_level=sng.hands_per_level - sng.hand_no % sng.hands_per_level,
            hand_number=obs.hand_no + 1, players_remaining=sum(1 for x in sng._dealt if x),
            bust_order=[], config=cfg, events=list(events))

    def act(self, obs):
        sng, mod, a = self.sng, self.mod, self.args
        sng.sync(obs.street)
        events = sng.log[self.cursor:]
        if a.omit_own:
            events = [e for e in events
                      if not (e.seat == self.seat and e.kind in ("fold", "check", "call", "raise"))]
        if a.rotate:
            events = [sdk.Event(e.kind, None if e.seat is None else self._kit_seat(e.seat), e.amount, e.cards)
                      for e in events]
        st = self.state(obs, events)
        want = self.shadow.act(obs)
        want = (want[0], want[1] if want[0] == RAISE else 0)
        # overhead probe: everything the adapter does except PrepBot.act (separate core)
        t0 = time.perf_counter()
        t, _o = mod._prepare(self.probe_core, st, self.memory)
        t.dump()
        self.overhead.append(time.perf_counter() - t0)
        agent = mod.Agent()                      # fresh instance: a forked copy
        t0 = time.perf_counter()
        try:
            action, mem = agent.act(st, self.memory)
        except Exception:
            self.errors += 1
            if self.errors <= 3:
                import traceback
                traceback.print_exc()
            action, mem = None, None
        self.total.append(time.perf_counter() - t0)
        got = None
        if action is not None:
            got = self.legal(action, st)
            if got is None or not isinstance(mem, bytes):
                self.illegal += 1
                got = None
        self.decisions += 1
        if got != want:
            self.mismatches += 1
            if self.first_mismatch is None:
                self.first_mismatch = (obs.hand_no, obs.street, want, got)
        if got is None or self.rng.random() < a.crash_rate:
            # timeout / exception / crash: host plays check-or-fold, keeps the old memory and
            # delivers these events again next turn
            self.crashes += got is not None
            return (CALL, 0) if obs.to_call == 0 else (FOLD, 0)
        self.memory = mem[:a.memory_bytes]
        self.mem_sizes.append(len(self.memory))
        self.cursor = len(sng.log)
        return got

    @staticmethod
    def legal(action, st):
        k = action.kind
        la = st.can(k)
        if la is None:
            return None
        if k == "fold":
            return (FOLD, 0)
        if k in ("check", "call"):
            return (CALL, 0)
        amt = action.amount
        if not isinstance(amt, int) or not la.min_amount <= amt <= la.max_amount:
            return None
        return (RAISE, amt)


def load(path):
    spec = importlib.util.spec_from_file_location("sdk_bot", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * (len(xs) - 1) + 0.5))] * 1e3 if xs else 0.0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bot", help="packaged bot built with --adapter adapter_sdk2026.py")
    ap.add_argument("--games", type=int, default=30)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--sdk-seats", type=int, default=2)
    ap.add_argument("--crash-rate", type=float, default=0.03)
    ap.add_argument("--omit-own", action="store_true", help="events leave out our own actions")
    ap.add_argument("--rotate", action="store_true", help="kit seat numbers rotated: we are seat 0")
    ap.add_argument("--pot-excl-bets", action="store_true", help="state.pot leaves out current bets")
    ap.add_argument("--ante", type=int, default=0, help="fixed ante chips per player")
    ap.add_argument("--stack", type=int, default=2000)
    ap.add_argument("--memory-bytes", type=int, default=65536)
    ap.add_argument("--field", default="tag,shover,station,lag,nit,maniac,timeout",
                    help="zoo bots to fill the other seats (plus 2 PrepBot copies)")
    args = ap.parse_args()
    mod = load(args.bot)
    mod._DEBUG = True                  # adapter exceptions propagate here and are counted
    mod.PrepBot.deadline = 1e9         # the time deadline makes play depend on load: off for parity
    T = mod._tables()
    field = args.field.split(",")
    tot = dict(dec=0, mis=0, ill=0, err=0, crash=0, hands=0)
    over, total, sizes = [], [], []
    first = None
    big_mem = (0, 0)
    t_start = time.time()
    for g in range(args.games):
        grng = random.Random(1000 * args.seed + g)
        sdk_agents = [SdkSeat(mod, mod.make_core(seed=g), args, random.Random(g * 7 + 1), f"T{g}")
                      for _ in range(args.sdk_seats)]
        for s in sdk_agents:
            s.probe_core = mod.make_core(seed=g)
        others = [mod.make_core(seed=g + 50), mod.make_core(seed=g + 51)]
        others += [ZOO[k](T, seed=g) for k in grng.sample(field, 8 - args.sdk_seats - 2)]
        agents = sdk_agents + others
        grng.shuffle(agents)
        sng = MockSNG(T.v.to_dict(), agents, rng=random.Random(g), ante=args.ante,
                      start_stack=args.stack, schedule=DEFAULT_SCHEDULE)
        for s in sdk_agents:
            s.sng = sng
        sng.run()
        tot["hands"] += sng.hands_played
        for i, a in enumerate(agents):
            if a in sdk_agents:
                assert sng.errors[i] == 0, "engine saw an exception from the SDK seat"
        for s in sdk_agents:
            tot["dec"] += s.decisions
            tot["mis"] += s.mismatches
            tot["ill"] += s.illegal
            tot["err"] += s.errors
            tot["crash"] += s.crashes
            over += s.overhead
            total += s.total
            sizes += s.mem_sizes
            if s.mem_sizes and max(s.mem_sizes) > big_mem[0]:
                big_mem = (max(s.mem_sizes), sng.hands_played)
            first = first or s.first_mismatch
    d = tot["dec"]
    print(f"{args.games} SNGs, {tot['hands']} hands, {args.sdk_seats} SDK seats/table, crash rate "
          f"{args.crash_rate} ({tot['crash']} simulated), omit_own={args.omit_own}, rotate={args.rotate}, "
          f"ante={args.ante}  [{time.time() - t_start:.0f}s]")
    print(f"exceptions {tot['err']}  illegal {tot['ill']}")
    print(f"decision parity vs PrepBot driven directly: {d - tot['mis']}/{d} = "
          f"{100.0 * (d - tot['mis']) / max(d, 1):.3f}%"
          + (f"  first mismatch (hand, street, want, got): {first}" if first else ""))
    print(f"adapter overhead per call (decode+events+restore+obs+encode) ms: p50 {pct(over, .5):.4f} "
          f"p99 {pct(over, .99):.4f} max {pct(over, 1):.4f}")
    print(f"whole Agent.act per call ms: p50 {pct(total, .5):.4f} p99 {pct(total, .99):.4f} "
          f"max {pct(total, 1):.4f}")
    print(f"memory bytes: p50 {sorted(sizes)[len(sizes) // 2] if sizes else 0} max {big_mem[0]} "
          f"(table of {big_mem[1]} hands)")
    if tot["err"] or tot["ill"] or tot["mis"]:
        sys.exit(1)


if __name__ == "__main__":
    main()

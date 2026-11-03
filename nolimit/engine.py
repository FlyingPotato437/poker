"""Eight-seat no-limit sit-and-go simulator mirroring the No Limit tournament format.

Defaults follow the published rules: 2,000 chips, blinds from 10/20 rising every 25
hands, 200-hand cap with ICM for survivors. The real blind schedule and points table
come in the starter kit on the day; pass them in via `schedule` and `payouts`.

Raises follow the standard no-limit rule: an all-in for less than a full raise does not
reopen raising for players who already acted (they may only call or fold), unless the
short all-ins add up to a full raise. `reopen_short=True` restores the older, simpler rule
where any raise reopens the action. Check the starter-kit simulator and match it.
"""
import random
import time

from .icm import icm
from .runtime import CALL, FOLD, POST, RAISE, Evaluator, Obs, get_variant

DEFAULT_SCHEDULE = ((10, 20), (15, 30), (25, 50), (50, 100), (75, 150), (100, 200),
                    (150, 300), (200, 400), (300, 600))
# Placeholder until the real points table is announced at the start of the build phase.
DEFAULT_PAYOUTS = (100, 65, 45, 30, 20, 12, 6, 0)


class SeatTiming:
    __slots__ = ("count", "total", "max", "over")

    def __init__(self):
        self.count = 0
        self.total = 0.0
        self.max = 0.0
        self.over = 0


class SNG:
    def __init__(self, variant, agents, rng=None, evaluator=None, start_stack=2000,
                 schedule=DEFAULT_SCHEDULE, hands_per_level=25, max_hands=200,
                 payouts=DEFAULT_PAYOUTS, ante=0, time_limit_ms=None, reopen_short=False):
        self.v = get_variant(variant)
        self.ev = evaluator or Evaluator(self.v)
        self.agents = agents
        self.n = len(agents)
        self.rng = rng or random.Random()
        self.stacks = [start_stack] * self.n
        self.schedule = schedule
        self.hands_per_level = hands_per_level
        self.max_hands = max_hands
        self.payouts = list(payouts) + [0] * max(0, self.n - len(payouts))
        self.ante_amt = ante
        self.time_limit_ms = time_limit_ms
        self.reopen_short = reopen_short
        self.points = [0.0] * self.n
        self.timing = [SeatTiming() for _ in range(self.n)]
        self.errors = [0] * self.n
        self.hand_no = 0
        self.button = None
        self.hands_played = 0

    # ------------------------------------------------------------------
    def run(self):
        for s, a in enumerate(self.agents):
            a.new_table(s, self.n)
        while self.hand_no < self.max_hands:
            alive = [s for s in range(self.n) if self.stacks[s] > 0]
            if len(alive) <= 1:
                break
            self._play_hand(alive)
            self.hand_no += 1
        alive = [s for s in range(self.n) if self.stacks[s] > 0]
        if len(alive) == 1:
            self.points[alive[0]] += self.payouts[0]
        elif alive:
            eq = icm([self.stacks[s] for s in alive], self.payouts[:len(alive)])
            for s, e in zip(alive, eq):
                self.points[s] += e
        self.hands_played = self.hand_no
        return self.points

    def _next_alive(self, seat):
        for k in range(1, self.n + 1):
            s = (seat + k) % self.n
            if self.stacks[s] > 0:
                return s
        return seat

    # ------------------------------------------------------------------
    def _play_hand(self, alive):
        n, v, rng = self.n, self.v, self.rng
        start = list(self.stacks)
        if self.button is None:
            self.button = rng.choice(alive)
        else:
            self.button = self._next_alive(self.button)
        level = min(self.hand_no // self.hands_per_level, len(self.schedule) - 1)
        self.sb_amt, self.bb_amt = self.schedule[level]
        if len(alive) == 2:
            sb = self.button
            bb = self._next_alive(sb)
        else:
            sb = self._next_alive(self.button)
            bb = self._next_alive(sb)
        self.bets = [0] * n
        self.contrib = [0] * n
        self.in_hand = [self.stacks[s] > 0 for s in range(n)]
        self.history = []
        if self.ante_amt:
            for s in alive:
                a = min(self.ante_amt, self.stacks[s])
                self.stacks[s] -= a
                self.contrib[s] += a
        for seat, amt in ((sb, self.sb_amt), (bb, self.bb_amt)):
            amt = min(amt, self.stacks[seat])
            self.stacks[seat] -= amt
            self.bets[seat] += amt
            self.contrib[seat] += amt
            self.history.append((seat, 0, POST, self.bets[seat], self.stacks[seat] == 0))
        deck = list(range(v.D))
        rng.shuffle(deck)
        h = v.n_hole
        self.hole = [None] * n
        for i, s in enumerate(alive):
            self.hole[s] = tuple(deck[i * h:(i + 1) * h])
        rest = deck[len(alive) * h:]
        self.board = []
        first = self.button if len(alive) == 2 else self._next_alive(bb)
        self._betting(0, first)
        street = 0
        for n_cards in v.streets:
            if sum(self.in_hand) <= 1:
                break
            street += 1
            self.board.extend(rest[:n_cards])
            rest = rest[n_cards:]
            self.bets = [0] * n
            self._betting(street, self._next_alive(self.button))
        self._settle(rest)
        busted = [s for s in alive if self.stacks[s] == 0]
        if busted:
            places = list(range(len(alive) - len(busted), len(alive)))   # 0-indexed places
            busted.sort(key=lambda s: -start[s])
            i = 0
            while i < len(busted):
                j = i
                while j + 1 < len(busted) and start[busted[j + 1]] == start[busted[i]]:
                    j += 1
                share = sum(self.payouts[places[k]] for k in range(i, j + 1)) / (j - i + 1)
                for k in range(i, j + 1):
                    self.points[busted[k]] += share
                i = j + 1
        showdown = {s: self.hole[s] for s in range(n) if self.in_hand[s]} if sum(self.in_hand) > 1 else {}
        info = {"hand_no": self.hand_no, "history": tuple(self.history), "showdown": showdown,
                "board": tuple(self.board)}
        for a in self.agents:
            try:
                a.observe(("hand_end", info))
            except Exception:
                pass

    def _can_act(self, s):
        return self.in_hand[s] and self.stacks[s] > 0

    def _betting(self, street, first):
        n = self.n
        order = [(first + k) % n for k in range(n)]
        pending = [s for s in order if self._can_act(s)]
        cur = max(self.bets)
        min_inc = self.bb_amt
        faced = {}    # seat -> the bet it matched when it last acted this round
        while pending:
            if sum(self.in_hand) <= 1:
                return
            s = pending.pop(0)
            if not self._can_act(s):
                continue
            to_call = cur - self.bets[s]
            others = any(self._can_act(t) for t in range(n) if t != s)
            if to_call <= 0 and not others:
                continue
            max_to = self.bets[s] + self.stacks[s]
            reopened = self.reopen_short or s not in faced or cur - faced[s] >= min_inc
            min_to = min(cur + min_inc, max_to) if (max_to > cur and others and reopened) else 0
            obs = Obs(hole=self.hole[s], board=tuple(self.board), street=street, seat=s,
                      button=self.button, stacks=tuple(self.stacks), bets=tuple(self.bets),
                      in_hand=tuple(self.in_hand), pot=sum(self.contrib), to_call=max(to_call, 0),
                      min_raise_to=min_to, max_raise_to=max_to, sb=self.sb_amt, bb=self.bb_amt,
                      ante=self.ante_amt, hand_no=self.hand_no, history=tuple(self.history))
            kind, amt = self._ask(s, obs)
            if kind == FOLD and to_call <= 0:
                kind = CALL
            if kind == RAISE and min_to == 0:
                kind = CALL
            if kind == FOLD:
                self.in_hand[s] = False
                self.history.append((s, street, FOLD, self.bets[s], False))
            elif kind == CALL:
                pay = min(max(to_call, 0), self.stacks[s])
                self.stacks[s] -= pay
                self.bets[s] += pay
                self.contrib[s] += pay
                self.history.append((s, street, CALL, self.bets[s], self.stacks[s] == 0))
            else:
                amt = max(min_to, min(int(amt), max_to))
                pay = amt - self.bets[s]
                self.stacks[s] -= pay
                self.bets[s] += pay
                self.contrib[s] += pay
                if amt - cur >= min_inc:
                    min_inc = amt - cur
                cur = amt
                self.history.append((s, street, RAISE, amt, self.stacks[s] == 0))
            faced[s] = cur
            if kind == RAISE:
                i = order.index(s)
                pending = [t for t in order[i + 1:] + order[:i] if self._can_act(t)]

    def _ask(self, s, obs):
        t0 = time.perf_counter()
        try:
            a = self.agents[s].act(obs)
            kind, amt = int(a[0]), int(a[1])
            if kind not in (FOLD, CALL, RAISE):
                raise ValueError(a)
        except Exception:
            self.errors[s] += 1
            kind, amt = (CALL if obs.to_call == 0 else FOLD), 0
        dt = (time.perf_counter() - t0) * 1000.0
        tm = self.timing[s]
        tm.count += 1
        tm.total += dt
        if dt > tm.max:
            tm.max = dt
        if self.time_limit_ms is not None and dt > self.time_limit_ms:
            tm.over += 1
            kind, amt = (CALL if obs.to_call == 0 else FOLD), 0
        return kind, amt

    def _settle(self, rest):
        n = self.n
        live = [s for s in range(n) if self.in_hand[s]]
        if len(live) == 1:
            self.stacks[live[0]] += sum(self.contrib)
            return
        need = self.v.n_board - len(self.board)
        if need > 0:
            self.board.extend(rest[:need])
        values = {s: self.ev.best(self.hole[s], self.board) for s in live}
        remaining = list(self.contrib)
        seat_order = [(self.button + k) % n for k in range(1, n + 1)]
        last_winners = live
        while sum(remaining) > 0:
            contenders = [s for s in live if remaining[s] > 0]
            if contenders:
                m = min(remaining[s] for s in contenders)
            else:
                m = max(remaining)
            pot = 0
            for s in range(n):
                take = min(remaining[s], m)
                pot += take
                remaining[s] -= take
            if contenders:
                best = max(values[s] for s in contenders)
                winners = [s for s in seat_order if s in contenders and values[s] == best]
                last_winners = winners
            else:
                winners = [s for s in seat_order if s in last_winners]
            share, odd = divmod(pot, len(winners))
            for i, s in enumerate(winners):
                self.stacks[s] += share + (1 if i < odd else 0)


def play_sng(variant, agents, seed=None, **kw):
    sng = SNG(variant, agents, rng=random.Random(seed), **kw)
    sng.run()
    return sng

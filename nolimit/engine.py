"""Eight-seat no-limit sit-and-go simulator mirroring the No Limit tournament format.

Defaults follow the published rules: 2,000 chips, blinds from 10/20 rising every 25
hands, 200-hand cap with ICM for survivors. The real blind schedule and points table
come in the starter kit on the day; pass them in via `schedule` and `payouts`.

Raises follow the standard no-limit rule: an all-in for less than a full raise does not
reopen raising for players who already acted (they may only call or fold), unless the
short all-ins add up to a full raise. `reopen_short=True` restores the older, simpler rule
where any raise reopens the action. Check the starter-kit simulator and match it.

Optional house rules, all off by default. With every one off the engine deals, asks and
pays exactly as before they existed (tests/test_special_rules.py checks this action for
action against a frozen copy of the old engine):

    ante_bb=0.1        ante from every player as a fraction of the current big blind
                       (`ante` stays a fixed chip amount; ante_bb overrides it when set)
    bb_ante=1.0        big-blind ante: the big blind posts this many BB of dead money, before
                       the blinds (so a short big blind pays the ante first)
    straddle=True      UTG (first after the BB, 3+ players) posts 2 BB; it acts last preflop
                       and the minimum raise preflop is one straddle
    bomb_every=N, bomb_bb=K
                       every Nth hand everyone posts K BB, no blinds or antes, play starts
                       on the flop
    run_twice=True     once nobody can bet any more with the board incomplete, the rest of the
                       board is dealt twice and every pot is split half and half by the runouts
    bounty_72=X        whoever wins a pot at showdown holding 7-2 offsuit (two hole cards only)
                       collects X BB from every other player still in the tournament;
                       bounty_72_noshow=True also pays it when everyone else folded
    ko_points=P        P points to the player(s) who win the last chips of a busted player
                       (total points per table then vary; score against the table's total)
    max_bet_bb=C       a bet or raise may add at most C BB over the current bet
    max_raises=K       at most K bets/raises per betting round (then call or fold only)
    dead_button=True   dead-button rule: the big blind always moves one live seat on, the
                       small blind and button follow it, and either can be dead (no small blind
                       posted when its seat busted; the button can sit on an empty seat)
    cap_scoring="chips"  at the hand cap, survivors split the points left in proportion to
                       chips instead of by ICM
    stack_spread=f     uneven starting stacks: each seat starts with start_stack * (1 + u*f),
                       u uniform in [-1, 1] (from a generator seeded off the table's rng)
    log_hands=True     per-hand records in self.hand_log (seat, position, hole class, stack,
                       chips won, all-in), see _log_hand
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
                 payouts=DEFAULT_PAYOUTS, ante=0, time_limit_ms=None, reopen_short=False,
                 ante_bb=0.0, bb_ante=0.0, straddle=False, bomb_every=0, bomb_bb=0.0,
                 run_twice=False, bounty_72=0.0, bounty_72_noshow=False, ko_points=0.0,
                 max_bet_bb=0.0, max_raises=0, dead_button=False, cap_scoring="icm",
                 stack_spread=0.0, log_hands=False):
        self.v = get_variant(variant)
        self.ev = evaluator or Evaluator(self.v)
        self.agents = agents
        self.n = len(agents)
        self.rng = rng or random.Random()
        self.stacks = [start_stack] * self.n
        if stack_spread:
            srng = random.Random(self.rng.random())
            self.stacks = [max(1, int(round(start_stack * (1 + srng.uniform(-1, 1) * stack_spread))))
                           for _ in range(self.n)]
        self.schedule = schedule
        self.hands_per_level = hands_per_level
        self.max_hands = max_hands
        self.payouts = list(payouts) + [0] * max(0, self.n - len(payouts))
        self.ante_amt = ante
        self.time_limit_ms = time_limit_ms
        self.reopen_short = reopen_short
        self.ante_bb = ante_bb
        self.bb_ante = bb_ante
        self.straddle = straddle
        self.bomb_every = int(bomb_every or 0)
        self.bomb_bb = bomb_bb
        self.run_twice = run_twice
        self.bounty_72 = bounty_72
        self.bounty_72_noshow = bounty_72_noshow
        self.ko_points = ko_points
        self.max_bet_bb = max_bet_bb
        self.max_raises = int(max_raises or 0)
        self.dead_button = dead_button
        self.cap_scoring = cap_scoring
        self.bounties = [0] * self.n          # chips won (+) or paid (-) in 7-2 bounties
        self.kos = [0] * self.n               # knockouts credited (fractions when split)
        self.hand_log = [] if log_hands else None
        self.hand_ante = ante
        self._min_inc0 = None
        self._runout_from = None
        self._last_layer = {}
        self._prev_sb = self._prev_bb = self._sb_pos = None
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
            if self.cap_scoring == "chips":
                left = sum(self.payouts[:len(alive)])
                tot = sum(self.stacks[s] for s in alive)
                eq = [left * self.stacks[s] / tot for s in alive]
            else:
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

    def _positions(self, alive):
        """(button, sb or None, bb) for this hand."""
        if self._prev_bb is not None and len(alive) > 2:
            # Dead button: the big blind moves one live seat on; the small blind sits on last
            # hand's big-blind seat (dead if that player busted), the button on last hand's
            # small-blind seat (possibly empty).
            bb = self._next_alive(self._prev_bb)
            sb_pos, button = self._prev_bb, self._prev_sb
            if button not in (bb, sb_pos) and sb_pos != bb:
                self.button = button
                self._sb_pos = sb_pos
                return button, (sb_pos if self.stacks[sb_pos] > 0 else None), bb
        if self.button is None:
            self.button = self.rng.choice(alive)
        else:
            self.button = self._next_alive(self.button)
        if len(alive) == 2:
            sb = self.button
        else:
            sb = self._next_alive(self.button)
        self._sb_pos = sb
        return self.button, sb, self._next_alive(sb)

    # ------------------------------------------------------------------
    def _play_hand(self, alive):
        n, v, rng = self.n, self.v, self.rng
        start = list(self.stacks)
        self._b0 = list(self.bounties)
        if self.dead_button:
            button, sb, bb = self._positions(alive)
        else:
            if self.button is None:
                self.button = rng.choice(alive)
            else:
                self.button = self._next_alive(self.button)
            if len(alive) == 2:
                sb = self.button
                bb = self._next_alive(sb)
            else:
                sb = self._next_alive(self.button)
                bb = self._next_alive(sb)
        level = min(self.hand_no // self.hands_per_level, len(self.schedule) - 1)
        self.sb_amt, self.bb_amt = self.schedule[level]
        self.bets = [0] * n
        self.contrib = [0] * n
        self.in_hand = [self.stacks[s] > 0 for s in range(n)]
        self.history = []
        self._min_inc0 = None
        self._runout_from = None
        self._last_layer = {}
        bomb = self.bomb_every > 0 and (self.hand_no + 1) % self.bomb_every == 0
        ante_amt = int(round(self.ante_bb * self.bb_amt)) if self.ante_bb else self.ante_amt
        self.hand_ante = ante_amt
        if ante_amt and not bomb:
            for s in alive:
                a = min(ante_amt, self.stacks[s])
                self.stacks[s] -= a
                self.contrib[s] += a
        straddler = None
        if bomb:
            # Everyone posts the bomb; it is dead money and the hand starts on the flop.
            for s in alive:
                a = min(int(round(self.bomb_bb * self.bb_amt)), self.stacks[s])
                self.stacks[s] -= a
                self.bets[s] += a
                self.contrib[s] += a
                self.history.append((s, 0, POST, self.bets[s], self.stacks[s] == 0))
        else:
            if self.bb_ante:
                a = min(int(round(self.bb_ante * self.bb_amt)), self.stacks[bb])
                self.stacks[bb] -= a
                self.contrib[bb] += a
            for seat, amt in ((sb, self.sb_amt), (bb, self.bb_amt)):
                if seat is None:          # dead small blind
                    continue
                amt = min(amt, self.stacks[seat])
                self.stacks[seat] -= amt
                self.bets[seat] += amt
                self.contrib[seat] += amt
                self.history.append((seat, 0, POST, self.bets[seat], self.stacks[seat] == 0))
            if self.straddle and len(alive) >= 3:
                straddler = self._next_alive(bb)
                amt = min(2 * self.bb_amt, self.stacks[straddler])
                self.stacks[straddler] -= amt
                self.bets[straddler] += amt
                self.contrib[straddler] += amt
                self.history.append((straddler, 0, POST, self.bets[straddler], self.stacks[straddler] == 0))
                self._min_inc0 = 2 * self.bb_amt
        if self.dead_button:
            self._prev_sb, self._prev_bb = self._sb_pos, bb
        deck = list(range(v.D))
        rng.shuffle(deck)
        h = v.n_hole
        self.hole = [None] * n
        for i, s in enumerate(alive):
            self.hole[s] = tuple(deck[i * h:(i + 1) * h])
        rest = deck[len(alive) * h:]
        self.board = []
        if not bomb:
            first = self.button if len(alive) == 2 else self._next_alive(bb)
            if straddler is not None:
                first = self._next_alive(straddler)
            self._betting(0, first)
            self._min_inc0 = None
        street = 0
        for n_cards in v.streets:
            if sum(self.in_hand) <= 1:
                break
            if self.run_twice and sum(1 for s in range(n) if self._can_act(s)) <= 1:
                self._runout_from = len(self.board)      # all in: the rest is dealt twice
                break
            street += 1
            self.board.extend(rest[:n_cards])
            rest = rest[n_cards:]
            self.bets = [0] * n
            self._betting(street, self._next_alive(self.button))
        won = self._settle(rest)
        if self.bounty_72 and won:
            self._pay_bounties(won, alive)
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
            if self.ko_points:
                for s in busted:
                    who = [w for w in self._last_layer.get(s, ()) if w != s and self.stacks[w] > 0]
                    for w in who:
                        self.points[w] += self.ko_points / len(who)
                        self.kos[w] += 1.0 / len(who)
        showdown = {s: self.hole[s] for s in range(n) if self.in_hand[s]} if sum(self.in_hand) > 1 else {}
        info = {"hand_no": self.hand_no, "history": tuple(self.history), "showdown": showdown,
                "board": tuple(self.board)}
        if self.hand_log is not None:
            self._log_hand(alive, start)
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
        min_inc = self.bb_amt if self._min_inc0 is None else self._min_inc0
        cap_inc = self.max_bet_bb * self.bb_amt if self.max_bet_bb else 0
        n_raises = 0
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
            if cap_inc:
                max_to = min(max_to, cur + int(cap_inc))
            reopened = self.reopen_short or s not in faced or cur - faced[s] >= min_inc
            if self.max_raises and n_raises >= self.max_raises:
                reopened = False
            min_to = min(cur + min_inc, max_to) if (max_to > cur and others and reopened) else 0
            obs = Obs(hole=self.hole[s], board=tuple(self.board), street=street, seat=s,
                      button=self.button, stacks=tuple(self.stacks), bets=tuple(self.bets),
                      in_hand=tuple(self.in_hand), pot=sum(self.contrib), to_call=max(to_call, 0),
                      min_raise_to=min_to, max_raise_to=max_to, sb=self.sb_amt, bb=self.bb_amt,
                      ante=self.hand_ante, hand_no=self.hand_no, history=tuple(self.history))
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
                n_raises += 1
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
        """Pay out the pots. Returns {seat: (chips won, at showdown)}."""
        n = self.n
        live = [s for s in range(n) if self.in_hand[s]]
        if len(live) == 1:
            self.stacks[live[0]] += sum(self.contrib)
            for s in range(n):
                if self.contrib[s]:
                    self._last_layer[s] = (live[0],)
            return {live[0]: (sum(self.contrib), False)}
        need = self.v.n_board - len(self.board)
        boards = None
        if self._runout_from is not None and need > 0 and len(rest) >= 2 * need:
            boards = [self.board + rest[:need], self.board + rest[need:2 * need]]
        if need > 0:
            self.board.extend(rest[:need])
        won = {}
        if boards is None:
            self._split_pots(live, self.board, list(self.contrib), won)
        else:
            # Run it twice: every pot layer splits in halves (the odd chip goes to the first run).
            self._split_pots(live, boards[0], [c - c // 2 for c in self.contrib], won)
            first = dict(self._last_layer)
            self._split_pots(live, boards[1], [c // 2 for c in self.contrib], won)
            for s, w in first.items():
                self._last_layer[s] = tuple(w) + tuple(self._last_layer.get(s, ()))
            self.boards = boards
        return {s: (c, True) for s, c in won.items()}

    def _split_pots(self, live, board, remaining, won):
        n = self.n
        values = {s: self.ev.best(self.hole[s], board) for s in live}
        seat_order = [(self.button + k) % n for k in range(1, n + 1)]
        last_winners = live
        while sum(remaining) > 0:
            contenders = [s for s in live if remaining[s] > 0]
            if contenders:
                m = min(remaining[s] for s in contenders)
            else:
                m = max(remaining)
            pot = 0
            takers = []
            for s in range(n):
                take = min(remaining[s], m)
                if take:
                    takers.append(s)
                pot += take
                remaining[s] -= take
            if contenders:
                best = max(values[s] for s in contenders)
                winners = [s for s in seat_order if s in contenders and values[s] == best]
                last_winners = winners
            else:
                winners = [s for s in seat_order if s in last_winners]
            for s in takers:
                self._last_layer[s] = tuple(winners)
            share, odd = divmod(pot, len(winners))
            for i, s in enumerate(winners):
                amt = share + (1 if i < odd else 0)
                self.stacks[s] += amt
                won[s] = won.get(s, 0) + amt

    # ------------------------------------------------------------------
    def is_72o(self, hole):
        if hole is None or len(hole) != 2:
            return False
        v = self.v
        r = sorted(v.ranks[c // v.suits] for c in hole)
        return r == ["2", "7"] and hole[0] % v.suits != hole[1] % v.suits

    def _pay_bounties(self, won, alive):
        """7-2 offsuit wins a pot: X BB from every other player still in the tournament."""
        amt = int(round(self.bounty_72 * self.bb_amt))
        for w, (chips, shown) in won.items():
            if chips <= 0 or not (shown or self.bounty_72_noshow) or not self.is_72o(self.hole[w]):
                continue
            for s in alive:
                if s != w and self.stacks[s] > 0:
                    pay = min(amt, self.stacks[s])
                    self.stacks[s] -= pay
                    self.stacks[w] += pay
                    self.bounties[s] -= pay
                    self.bounties[w] += pay

    @staticmethod
    def position_names(k):
        """Position labels by offset from the button, for k players dealt in."""
        if k == 2:
            return ("BTN", "BB")
        mid = k - 3
        tail = ["LJ", "HJ", "CO"][-mid:] if mid else []
        n_head = mid - len(tail)
        head = (["UTG"] + [f"UTG+{i}" for i in range(1, n_head)])[:n_head]
        return tuple(["BTN", "SB", "BB"] + head + tail)

    def hole_class_name(self, hole):
        v = self.v
        rs = sorted((c // v.suits for c in hole), reverse=True)
        name = "".join(v.ranks[r] for r in rs)
        if len(hole) == 2 and rs[0] != rs[1]:
            name += "s" if hole[0] % v.suits == hole[1] % v.suits else "o"
        elif len(hole) > 2:
            suits = [c % v.suits for c in hole]
            name += ":" + "".join(str(c) for c in sorted((suits.count(x) for x in set(suits)), reverse=True))
        return name

    def _log_hand(self, alive, start):
        """One record per player dealt in. pos is by seat offset from the button among the
        players dealt in (a dead button counts from the next live seat)."""
        k = len(alive)
        btn = self.button if self.button in alive else self._next_alive(self.button)
        bi = alive.index(btn) if btn in alive else 0
        names = self.position_names(k)
        raised = {hh[0] for hh in self.history if hh[2] == RAISE}
        showdown = sum(self.in_hand) > 1
        for i, s in enumerate(alive):
            off = (i - bi) % k
            self.hand_log.append({
                "hand_no": self.hand_no, "seat": s, "n_alive": k, "pos": names[off], "offset": off,
                "hole": self.hole_class_name(self.hole[s]), "stack_bb": start[s] / self.bb_amt,
                "bb": self.bb_amt, "delta": self.stacks[s] - start[s],
                "allin": self.contrib[s] >= start[s],       # every chip went in this hand
                "raised": s in raised, "showdown": bool(showdown and self.in_hand[s]),
                "busted": self.stacks[s] == 0, "bounty": self.bounties[s] - self._b0[s]})


def play_sng(variant, agents, seed=None, **kw):
    sng = SNG(variant, agents, rng=random.Random(seed), **kw)
    sng.run()
    return sng

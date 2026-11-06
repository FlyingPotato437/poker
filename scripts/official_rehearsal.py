"""Published-contract rehearsal using our simulator, NOT the official SDK/host.

Exercises the packaged Agent with fresh instances each decision, explicit memory,
event deltas, and eight seats. Independent reference stats catch event loss after
folds. Timing includes the adapter and memory codec but excludes host transport.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import random
import sys
import time
import types

for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[name] = "1"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nolimit.engine import SNG
from nolimit.runtime import BotBase, CALL, FOLD, POST, RAISE, SeatStats, ingest_history, card_str
from nolimit.official_adapter import STAT_FIELDS
from nolimit.official_payouts import DEFAULT_PAYOUTS, HAND_CAP, HANDS_PER_LEVEL
from nolimit.zoo import ZOO

NS = types.SimpleNamespace


class ContractAction:
    def __init__(self, kind, amount=None):
        self.kind, self.amount = kind, amount

    @classmethod
    def fold(cls):
        return cls("fold")

    @classmethod
    def check(cls):
        return cls("check")

    @classmethod
    def call(cls):
        return cls("call")

    @classmethod
    def raise_to(cls, amount):
        return cls("raise", amount)


def event(kind, seat=None, amount=0, cards=()):
    return NS(kind=kind, seat=seat, amount=amount, cards=cards)


def load_candidate(path):
    # This explicitly labelled stub exists only in the rehearsal process. It is
    # never part of the candidate zip or evidence of SDK import compatibility.
    stub = types.ModuleType("poker_agent_sdk")
    stub.Agent, stub.Action = object, ContractAction
    sys.modules["poker_agent_sdk"] = stub
    sys.path.insert(0, str(path))
    spec = importlib.util.spec_from_file_location("rehearsed_agent", path / "agent.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ContractSeat(BotBase):
    def __init__(self, module, table_id, payouts, decision_ms=1):
        self.mod, self.table_id, self.payouts, self.decision_ms = module, table_id, payouts, decision_ms
        self.host = None
        self.timings, self.mem_sizes = [], []
        self.illegal = self.resets = self.stats_mismatches = self.history_mismatches = 0
        self.mismatch_examples = []

    def new_table(self, seat, n):
        self.seat, self.n = seat, n
        self.memory = b""
        self.pending = []
        self.hand = None
        self.history_count = self.street = self.board_count = 0
        self.round_bets = [0] * n
        self.reference_stats = [SeatStats() for _ in range(n)]

    def _advance(self, hand, history, board):
        v = self.mod.TABLES.v
        if hand != self.hand:
            self.hand = hand
            self.history_count = self.street = self.board_count = 0
            self.round_bets = [0] * self.n
            self.pending.append(event("hand", amount=hand))
        for s, street, kind, total, all_in in history[self.history_count:]:
            while self.street < street:
                count = v.streets[self.street]
                self.pending.append(event("board", cards=tuple(card_str(v, c) for c in board[self.board_count:self.board_count + count])))
                self.board_count += count
                self.street += 1
                self.round_bets = [0] * self.n
            previous = self.round_bets[s]
            name = {FOLD: "fold", POST: "blind", RAISE: "raise", CALL: "call" if total > previous else "check"}[kind]
            amount = total if kind == RAISE else max(0, total - previous) if kind in (CALL, POST) else 0
            self.pending.append(event(name, s, amount))
            if kind in (CALL, POST, RAISE):
                self.round_bets[s] = total
        self.history_count = len(history)
        while self.board_count < len(board):
            count = v.streets[self.street]
            self.pending.append(event("board", cards=tuple(card_str(v, c) for c in board[self.board_count:self.board_count + count])))
            self.board_count += count
            self.street += 1
            self.round_bets = [0] * self.n

    def observe(self, info):
        _, info = info
        self._advance(info["hand_no"], info["history"], info["board"])
        for seat, stack in enumerate(self.host.stacks):
            self.pending.append(event("stack", seat, stack))
        ingest_history(self.reference_stats, info["history"])

    def act(self, obs):
        self._advance(obs.hand_no, obs.history, obs.board)
        v = self.mod.TABLES.v
        legal = [NS(kind="check", min_amount=None, max_amount=None)] if obs.to_call == 0 else [
            NS(kind="fold", min_amount=None, max_amount=None), NS(kind="call", min_amount=None, max_amount=None)]
        if obs.min_raise_to > 0:
            legal.append(NS(kind="raise", min_amount=obs.min_raise_to, max_amount=obs.max_raise_to))
        s = NS(config=NS(table_id=self.table_id, seat=self.seat, variant=self.mod.CONFIG["variant_ids"][0],
                         players=self.n, starting_stack=2000, payouts=self.payouts,
                         hands_per_level=HANDS_PER_LEVEL, hand_cap=HAND_CAP, decision_ms=self.decision_ms,
                         time_bank_ms=0, memory_bytes=65536),
               seat=self.seat, button=obs.button, cards=tuple(card_str(v, c) for c in obs.hole),
               board=tuple(card_str(v, c) for c in obs.board), pot=obs.pot, to_call=obs.to_call,
               phase="betting", hand_number=obs.hand_no, blinds=NS(small=obs.sb, big=obs.bb, ante=obs.ante),
               legal_actions=legal, events=list(self.pending), history=[],
               seats=[NS(seat=i, stack=obs.stacks[i], bet=obs.bets[i],
                         status=("all_in" if obs.stacks[i] == 0 else "active") if obs.in_hand[i]
                         else ("folded" if obs.stacks[i] > 0 else "busted")) for i in range(self.n)])
        s.can = lambda kind: next((a for a in legal if a.kind == kind), None)
        t0 = time.perf_counter_ns()
        # A fresh object every call exercises the required worker migration path.
        action, self.memory = self.mod.Agent().act(s, self.memory)
        self.timings.append((time.perf_counter_ns() - t0) / 1e6)
        self.mem_sizes.append(len(self.memory))
        self.pending = []
        if not self.memory:
            self.resets += 1
        else:
            d = json.loads(self.memory)
            want = [[getattr(st, k) for k in STAT_FIELDS] for st in self.reference_stats]
            self.stats_mismatches += d["stats"] != want
            got_history = [tuple(row) for row in d["hist"]]
            self.history_mismatches += got_history != list(obs.history)
            if len(self.mismatch_examples) < 2 and got_history != list(obs.history):
                self.mismatch_examples.append({"table": self.table_id, "hand": obs.hand_no,
                                               "expected": list(obs.history), "got": got_history,
                                               "stacks": obs.stacks})
        offered = s.can(action.kind)
        if offered is None or (action.kind == "raise" and not offered.min_amount <= action.amount <= offered.max_amount):
            self.illegal += 1
            raise ValueError("Illegal packaged action")
        return {"fold": FOLD, "check": CALL, "call": CALL, "raise": RAISE}[action.kind], action.amount or 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("candidate", type=Path)
    ap.add_argument("--tables", type=int, default=24)
    ap.add_argument("--seed", type=int, default=1062601)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--decision-ms", type=float, default=1)
    args = ap.parse_args()
    start = time.perf_counter()
    mod = load_candidate(args.candidate.resolve())
    load_s = time.perf_counter() - start
    all_seats = []
    # Royal has only 20 cards: eight 2-card hands leave no room for a 5-card
    # board. The historical simulator does not enforce this constraint itself.
    players = min(8, (mod.TABLES.v.D - mod.TABLES.v.n_board) // mod.TABLES.v.n_hole)
    for i in range(args.tables):
        payouts = (DEFAULT_PAYOUTS, (100, 0, 0, 0, 0, 0, 0, 0), tuple(range(8, 0, -1)))[i % 3]
        bots = [ContractSeat(mod, f"rehearsal-{args.seed}-{i}", payouts, args.decision_ms) for _ in range(2)]
        styles = ("tag", "lag", "shover", "station", "nit", "random")[:players - 2]
        agents = bots + [ZOO[k](mod.TABLES, seed=args.seed + i) for k in styles]
        random.Random(args.seed + i).shuffle(agents)
        game = SNG(mod.TABLES.v, agents, rng=random.Random(args.seed + i), evaluator=mod.TABLES.ev,
                   hands_per_level=HANDS_PER_LEVEL, max_hands=HAND_CAP, payouts=payouts)
        for b in bots:
            b.host = game
        game.run()
        all_seats.extend(bots)
    timings = sorted(t for b in all_seats for t in b.timings)
    q = lambda p: timings[min(int(p * len(timings)), len(timings) - 1)]
    report = {"scope": "published-contract mock, not official SDK/host", "tables": args.tables, "players": players,
              "hero_seats_per_table": 2, "decisions": len(timings), "import_s": load_s,
              "p50_ms": q(.5), "p99_ms": q(.99), "p999_ms": q(.999), "max_ms": timings[-1],
              "over_1ms": sum(t > 1 for t in timings),
              "max_memory_bytes": max(m for b in all_seats for m in b.mem_sizes),
              "illegal": sum(b.illegal for b in all_seats), "unexpected_memory_resets": sum(b.resets for b in all_seats),
              "stats_mismatches": sum(b.stats_mismatches for b in all_seats),
              "history_mismatches": sum(b.history_mismatches for b in all_seats)}
    report["mismatch_examples"] = [e for b in all_seats for e in b.mismatch_examples][:4]
    text = json.dumps(report, indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n")
    print(text)
    if any(report[k] for k in ("illegal", "unexpected_memory_resets", "stats_mismatches", "history_mismatches")):
        raise SystemExit("Contract rehearsal failed")


if __name__ == "__main__":
    main()

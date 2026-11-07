"""Fake `poker_agent_sdk` built from the organizers' Nov 6 announcement (the real kit is only
downloadable at the event). Field names follow the announcement; where it gives no format
(state.history entries, whether pot includes current bets, state.blinds) this mock picks one,
and adapter_sdk2026.py marks those spots with KIT-CHECK.
"""


class Action:
    __slots__ = ("kind", "amount")

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

    def __repr__(self):
        return f"Action({self.kind!r}, {self.amount!r})"


class LegalAction:
    __slots__ = ("kind", "min_amount", "max_amount")

    def __init__(self, kind, min_amount=None, max_amount=None):
        self.kind, self.min_amount, self.max_amount = kind, min_amount, max_amount

    def __repr__(self):
        return f"LegalAction({self.kind!r}, {self.min_amount!r}, {self.max_amount!r})"


class Event:
    __slots__ = ("kind", "seat", "amount", "cards")

    def __init__(self, kind, seat=None, amount=None, cards=None):
        self.kind, self.seat, self.amount, self.cards = kind, seat, amount, cards

    def __repr__(self):
        return f"Event({self.kind!r}, {self.seat!r}, {self.amount!r}, {self.cards!r})"


class SeatInfo:
    __slots__ = ("seat", "stack", "bet", "status", "shown_cards")

    def __init__(self, seat, stack, bet, status, shown_cards=None):
        self.seat, self.stack, self.bet, self.status = seat, stack, bet, status
        self.shown_cards = shown_cards


class Config:
    def __init__(self, **kw):
        self.table_id = kw.get("table_id", "t0")
        self.seat = kw.get("seat", 0)
        self.variant = kw.get("variant", "nlhe")
        self.players = kw.get("players", 8)
        self.starting_stack = kw.get("starting_stack", 2000)
        self.blinds = kw.get("blinds", ())
        self.hands_per_level = kw.get("hands_per_level", 25)
        self.hand_cap = kw.get("hand_cap", 200)
        self.payouts = kw.get("payouts", ())
        self.decision_ms = kw.get("decision_ms", 1)
        self.time_bank_ms = kw.get("time_bank_ms", 0)
        self.memory_bytes = kw.get("memory_bytes", 65536)


class State:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

    def can(self, kind):
        for a in self.legal_actions:
            if a.kind == kind:
                return a
        return None


class Agent:
    def act(self, state, memory):
        raise NotImplementedError

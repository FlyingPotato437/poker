"""Opponent archetypes: what a field of 60-minute Codex-built bots tends to look like.

Table-aware bots share the same Tables as PrepBot, so they model "competent but
simple" opponents rather than blind ones.
"""
import random

from .runtime import CALL, FOLD, RAISE, BotBase, SeatStats, ingest_history


class _Base(BotBase):
    def __init__(self, tables=None, seed=None):
        self.T = tables
        self.rng = random.Random(seed)

    def _raise(self, obs, target):
        if obs.min_raise_to <= 0:
            return (CALL, 0)
        return (RAISE, max(obs.min_raise_to, min(int(target), obs.max_raise_to)))

    def _shove(self, obs):
        return (RAISE, obs.max_raise_to) if obs.min_raise_to > 0 else (CALL, 0)

    def _cf(self, obs):
        return (CALL, 0) if obs.to_call == 0 else (FOLD, 0)

    def _n_opp(self, obs):
        return max(1, sum(1 for s, h in enumerate(obs.in_hand) if h and s != obs.seat))

    def _strength(self, obs):
        """(preflop pct or None, postflop equity vs live opponents or None)."""
        if obs.street == 0:
            return self.T.pct(self.T.hole_class(obs.hole)), None
        e = self.T.post_equity(obs.hole, obs.board)
        n = self._n_opp(obs)
        return None, (e[n - 1] if n <= 3 else e[2] ** (n / 3.0))


class TimeoutBot(_Base):
    """Bots that crash or blow the 1 ms limit get auto check/folded."""

    def act(self, obs):
        return self._cf(obs)


class RandomBot(_Base):
    def act(self, obs):
        r = self.rng.random()
        if r < 0.25:
            return self._cf(obs)
        if r < 0.8:
            return (CALL, 0)
        return self._raise(obs, obs.min_raise_to + self.rng.random() * obs.pot)


class StationBot(_Base):
    def act(self, obs):
        return (CALL, 0)


class ManiacBot(_Base):
    def act(self, obs):
        r = self.rng.random()
        if r < 0.12:
            return self._shove(obs)
        if r < 0.6:
            return self._raise(obs, max(obs.bets) + obs.pot * (0.5 + self.rng.random()))
        return (CALL, 0)


class NitBot(_Base):
    def act(self, obs):
        pct, eq = self._strength(obs)
        if obs.street == 0:
            if pct <= 0.06:
                return self._raise(obs, max(obs.bets) * 3 + obs.bb)
            if pct <= 0.10:
                return (CALL, 0)
            return self._cf(obs)
        if eq >= 0.75:
            return self._raise(obs, max(obs.bets) + 0.75 * obs.pot)
        if eq >= 0.58:
            return (CALL, 0)
        return self._cf(obs)


class TagBot(_Base):
    """The 'ask Codex for a solid bot' baseline: strength thresholds + pot odds."""

    def act(self, obs):
        pct, eq = self._strength(obs)
        if obs.street == 0:
            raised = max(obs.bets) > obs.bb
            if not raised and pct <= 0.22:
                return self._raise(obs, 3 * obs.bb)
            if raised and pct <= 0.06:
                return self._raise(obs, max(obs.bets) * 3)
            if raised and pct <= 0.14:
                return (CALL, 0)
            if not raised and obs.to_call <= obs.bb // 2 + 1 and pct <= 0.35:
                return (CALL, 0)
            return self._cf(obs)
        if obs.to_call == 0:
            return self._raise(obs, 0.6 * obs.pot) if eq >= 0.6 else (CALL, 0)
        po = obs.to_call / (obs.pot + obs.to_call)
        if eq >= 0.8:
            return self._raise(obs, max(obs.bets) + obs.pot)
        return (CALL, 0) if eq >= po + 0.05 else (FOLD, 0)


class LagBot(_Base):
    def act(self, obs):
        pct, eq = self._strength(obs)
        if obs.street == 0:
            raised = max(obs.bets) > obs.bb
            if not raised and pct <= 0.45:
                return self._raise(obs, 2.5 * obs.bb)
            if raised and pct <= 0.12:
                return self._raise(obs, max(obs.bets) * 3)
            if raised and pct <= 0.30:
                return (CALL, 0)
            return self._cf(obs)
        if obs.to_call == 0:
            if eq >= 0.5 or self.rng.random() < 0.35:
                return self._raise(obs, 0.7 * obs.pot)
            return (CALL, 0)
        po = obs.to_call / (obs.pot + obs.to_call)
        if eq >= 0.72:
            return self._raise(obs, max(obs.bets) + obs.pot)
        return (CALL, 0) if eq >= po else (FOLD, 0)


class ShoverBot(_Base):
    """Preflop all-in with the top 20% else fold. A very common quick-build bot."""

    def act(self, obs):
        pct, eq = self._strength(obs)
        if obs.street == 0:
            return self._shove(obs) if pct <= 0.20 else self._cf(obs)
        return self._shove(obs) if eq >= 0.6 else self._cf(obs)


class JammerBot(_Base):
    """Exploit probe: all-in every hand. Punishes bots whose calling ranges are too tight."""

    def act(self, obs):
        return self._shove(obs)


class BullyBot(_Base):
    """Exploit probe: min-raise at every chance. Punishes bots that over-fold to aggression."""

    def act(self, obs):
        if obs.min_raise_to > 0 and self.rng.random() < 0.85:
            return (RAISE, obs.min_raise_to)
        return (CALL, 0)


class TrapperBot(_Base):
    """Exploit probe: checks strong hands, check-raises bets. Punishes autopilot bluffing."""

    def act(self, obs):
        pct, eq = self._strength(obs)
        if obs.street == 0:
            if pct <= 0.30:
                return (CALL, 0)
            return self._cf(obs)
        if obs.to_call == 0:
            return (CALL, 0)
        if eq >= 0.65:
            return self._raise(obs, max(obs.bets) * 3)
        po = obs.to_call / max(obs.pot + obs.to_call, 1)
        return (CALL, 0) if eq >= po else (FOLD, 0)


# ---------------------------------------------------------------------------
# Held-out styles: never in a tuning field, only in benchmarks, so a gain against them
# says the bot generalizes rather than fits the zoo above.

class SizerBot(_Base):
    """Bet size proportional to strength, a very common generated-bot pattern (a size tell)."""

    def act(self, obs):
        pct, eq = self._strength(obs)
        if obs.street == 0:
            raised = max(obs.bets) > obs.bb
            s = 1.0 - pct
            if pct <= 0.25:
                return self._raise(obs, max(obs.bets) + obs.bb * (1 + 6 * s * s))
            if pct <= 0.45 and (not raised or obs.to_call <= 3 * obs.bb):
                return (CALL, 0)
            return self._cf(obs)
        po = obs.to_call / max(obs.pot + obs.to_call, 1)
        if eq >= 0.85:
            return self._raise(obs, max(obs.bets) + eq * 1.5 * obs.pot)
        if obs.to_call == 0:
            return self._raise(obs, eq * obs.pot) if eq >= 0.5 else (CALL, 0)
        return (CALL, 0) if eq >= po else (FOLD, 0)


class CbetBot(_Base):
    """Chart-style preflop, always c-bets the flop small as the raiser, then value only."""

    pfr_hand = None

    def new_table(self, seat, n_seats):
        self.pfr_hand = None

    def act(self, obs):
        pct, eq = self._strength(obs)
        raises = [h for h in obs.history if h[1] == 0 and h[2] == 2]
        if obs.street == 0:
            if not raises:
                if pct <= 0.20:
                    self.pfr_hand = obs.hand_no
                    return self._raise(obs, 2.5 * obs.bb)
                return (CALL, 0) if obs.to_call <= obs.bb // 2 + 1 and pct <= 0.30 else self._cf(obs)
            if pct <= 0.05:
                self.pfr_hand = obs.hand_no
                return self._raise(obs, max(obs.bets) * 3)
            return (CALL, 0) if pct <= 0.12 else self._cf(obs)
        po = obs.to_call / max(obs.pot + obs.to_call, 1)
        if obs.to_call == 0:
            if obs.street == 1 and self.pfr_hand == obs.hand_no:
                return self._raise(obs, 0.33 * obs.pot)
            need = 0.55 if obs.street == 2 else 0.65
            return self._raise(obs, 0.66 * obs.pot) if eq >= need else (CALL, 0)
        if eq >= 0.82:
            return self._raise(obs, max(obs.bets) * 3)
        return (CALL, 0) if eq >= po - 0.03 else (FOLD, 0)


class MCBot(_Base):
    """'Monte Carlo equity vs everyone left, compare to pot odds': the textbook hackathon bot."""

    def act(self, obs):
        n = self._n_opp(obs)
        if obs.street == 0:
            eq = self.T.eq(self.T.hole_class(obs.hole), n)
        else:
            eq = self._strength(obs)[1]
        fair = 1.0 / (n + 1)
        po = obs.to_call / max(obs.pot + obs.to_call, 1)
        if eq >= 2.0 * fair and eq >= 0.45:
            return self._raise(obs, max(obs.bets) + obs.pot)
        if obs.to_call == 0:
            return (CALL, 0)
        return (CALL, 0) if eq >= po * 1.1 else (FOLD, 0)


class BalancedBot(_Base):
    """Solver-flavoured: bets 2/3 pot with value and a fixed share of air, defends by MDF."""

    def act(self, obs):
        pct, eq = self._strength(obs)
        if obs.street == 0:
            raised = max(obs.bets) > obs.bb
            if not raised:
                if pct <= 0.22 or (pct <= 0.4 and self.rng.random() < 0.3):
                    return self._raise(obs, 2.5 * obs.bb)
                return self._cf(obs) if obs.to_call > obs.bb // 2 + 1 else (CALL, 0) if pct <= 0.4 else self._cf(obs)
            if pct <= 0.05 or (pct <= 0.2 and self.rng.random() < 0.15):
                return self._raise(obs, max(obs.bets) * 3)
            return (CALL, 0) if pct <= 0.16 else self._cf(obs)
        if obs.to_call == 0:
            if eq >= 0.62 or (eq <= 0.3 and self.rng.random() < 0.33):
                return self._raise(obs, 0.66 * obs.pot)
            return (CALL, 0)
        mdf = obs.pot / max(obs.pot + obs.to_call, 1)     # defend this share of hands
        if eq >= 0.85:
            return self._raise(obs, max(obs.bets) * 2.5)
        return (CALL, 0) if eq >= 1.0 - mdf * 0.9 else (FOLD, 0)


class OverbetBot(_Base):
    """Polarized: overbets strong hands and some air, checks everything in between."""

    def act(self, obs):
        pct, eq = self._strength(obs)
        if obs.street == 0:
            if pct <= 0.15:
                return self._raise(obs, max(obs.bets) * 3 + obs.bb)
            return (CALL, 0) if pct <= 0.35 and obs.to_call <= 2 * obs.bb else self._cf(obs)
        if obs.to_call == 0:
            if eq >= 0.75 or (eq <= 0.2 and self.rng.random() < 0.25):
                return self._raise(obs, 1.8 * obs.pot)
            return (CALL, 0)
        po = obs.to_call / max(obs.pot + obs.to_call, 1)
        if eq >= 0.8:
            return self._shove(obs)
        return (CALL, 0) if eq >= po + 0.08 else (FOLD, 0)


# ---------------------------------------------------------------------------
# Sealed set (FRESH) for the ev_t3 confirmation. Unsealed Oct 31: the field-fit tunes
# (params/w_*, r_*) train on limper, icmshort, potcontrol and adaptive.
# ---------------------------------------------------------------------------

class LimperBot(_Base):
    """Loose-passive: limps and calls most hands, raises only the very top, pays off."""

    def act(self, obs):
        pct, eq = self._strength(obs)
        if obs.street == 0:
            if pct <= 0.04:
                return self._raise(obs, max(obs.bets) * 3)
            if pct <= 0.55 and obs.to_call <= 4 * obs.bb:
                return (CALL, 0)
            return self._cf(obs)
        if obs.to_call == 0:
            return self._raise(obs, 0.5 * obs.pot) if eq >= 0.7 else (CALL, 0)
        po = obs.to_call / max(obs.pot + obs.to_call, 1)
        return (CALL, 0) if eq >= po else (FOLD, 0)


class ICMShortBot(_Base):
    """Tournament-minded: push/fold at 20 bb or less (tighter with more players left),
    min-raise-or-fold above it, postflop jams good hands and gives up the rest."""

    def act(self, obs):
        pct, eq = self._strength(obs)
        bb = max(obs.bb, 1)
        left = sum(1 for x in obs.stacks if x > 0)
        depth = (obs.stacks[obs.seat] + obs.bets[obs.seat]) / bb
        if obs.street == 0:
            raised = max(obs.bets) > obs.bb
            if depth <= 20:
                shove = (0.10 + 0.35 * (1 - depth / 20)) * (4.0 / max(left, 4)) ** 0.5
                if raised:
                    shove *= 0.45
                return self._shove(obs) if pct <= shove else self._cf(obs)
            if not raised and pct <= 0.15:
                return self._raise(obs, 2 * obs.bb)
            if raised and pct <= 0.04:
                return self._shove(obs)
            return self._cf(obs)
        if eq >= 0.62:
            return self._shove(obs)
        if obs.to_call == 0:
            return (CALL, 0)
        po = obs.to_call / max(obs.pot + obs.to_call, 1)
        return (CALL, 0) if eq >= po + 0.1 else (FOLD, 0)


class PotControlBot(_Base):
    """Solid TAG with a plan: 3-bets light vs late opens, half-pot value bets, check-calls
    medium hands, check-raises monsters, semi-bluffs some draws on the flop."""

    def act(self, obs):
        pct, eq = self._strength(obs)
        if obs.street == 0:
            raises = [h for h in obs.history if h[1] == 0 and h[2] == RAISE]
            if not raises:
                return self._raise(obs, 2.5 * obs.bb) if pct <= 0.2 else (
                    (CALL, 0) if obs.to_call == 0 else self._cf(obs))
            late = raises and (obs.button - raises[0][0]) % len(obs.stacks) <= 1
            if pct <= 0.04 or (late and len(raises) == 1 and pct <= 0.12):
                return self._raise(obs, max(obs.bets) * 3)
            return (CALL, 0) if pct <= 0.15 else self._cf(obs)
        if obs.to_call == 0:
            if eq >= 0.85 and obs.street < 3 and self.rng.random() < 0.6:
                return (CALL, 0)                                   # check to raise
            if eq >= 0.58 or (obs.street == 1 and 0.35 <= eq <= 0.45 and self.rng.random() < 0.4):
                return self._raise(obs, 0.5 * obs.pot)
            return (CALL, 0)
        po = obs.to_call / max(obs.pot + obs.to_call, 1)
        if eq >= 0.82:
            return self._raise(obs, max(obs.bets) * 3)
        return (CALL, 0) if eq >= po + 0.03 else (FOLD, 0)


class AdaptiveBot(_Base):
    """Exploitative: keeps per-seat stats, bluffs players who over-fold, calls down players
    who over-bluff, steals from tight blinds. The kind of bot a strong team ships."""

    def new_table(self, seat, n_seats):
        self.stats = [SeatStats() for _ in range(n_seats)]

    def observe(self, event):
        kind, info = event
        if kind == "hand_end":
            ingest_history(self.stats, info["history"])

    def _villains(self, obs):
        return [s for s, h in enumerate(obs.in_hand) if h and s != obs.seat]

    def act(self, obs):
        if not hasattr(self, "stats") or len(self.stats) != len(obs.stacks):
            self.new_table(obs.seat, len(obs.stacks))
        pct, eq = self._strength(obs)
        vs = self._villains(obs)
        folds = sum(self.stats[s].rate("fold_to_bet") for s in vs) / max(len(vs), 1)
        agg = sum(self.stats[s].rate("agg") for s in vs) / max(len(vs), 1)
        if obs.street == 0:
            raised = max(obs.bets) > obs.bb
            vpip = sum(self.stats[s].rate("vpip") for s in vs) / max(len(vs), 1)
            if not raised:
                width = 0.18 * (0.35 / max(vpip, 0.1)) ** 0.5
                return self._raise(obs, 2.5 * obs.bb) if pct <= min(width, 0.45) else self._cf(obs) \
                    if obs.to_call > 0 else (CALL, 0)
            raiser = [h[0] for h in obs.history if h[1] == 0 and h[2] == RAISE][-1]
            rp = self.stats[raiser].rate("pfr")
            if pct <= 0.3 * rp:
                return self._raise(obs, max(obs.bets) * 3)
            return (CALL, 0) if pct <= 0.7 * rp else self._cf(obs)
        po = obs.to_call / max(obs.pot + obs.to_call, 1)
        if obs.to_call == 0:
            if eq >= 0.62:
                return self._raise(obs, 0.66 * obs.pot)
            if folds > 0.5 and len(vs) <= 2 and self.rng.random() < (folds - 0.3):
                return self._raise(obs, 0.5 * obs.pot)
            return (CALL, 0)
        if eq >= 0.8:
            return self._raise(obs, max(obs.bets) * 3)
        light = 0.08 * (agg - 0.45) / 0.45          # call lighter against frequent aggressors
        return (CALL, 0) if eq >= po + 0.04 - light else (FOLD, 0)


# ---------------------------------------------------------------------------
# Final-check set (scripts/final_check.py): written after the release candidate was frozen,
# so nothing was ever tuned or chosen against them. Four weak quick-build styles, two
# strong ones.
# ---------------------------------------------------------------------------

class FlakyBot(_Base):
    """A slow Monte-Carlo build: plays a plain TAG game, but a share of its decisions blow
    the time limit and get auto check/folded (more often postflop, where it simulates)."""

    def act(self, obs):
        if self.rng.random() < (0.08 if obs.street == 0 else 0.3):
            return self._cf(obs)
        pct, eq = self._strength(obs)
        if obs.street == 0:
            raised = max(obs.bets) > obs.bb
            if pct <= (0.05 if raised else 0.16):
                return self._raise(obs, max(obs.bets) * 3)
            return (CALL, 0) if pct <= 0.28 and obs.to_call <= 4 * obs.bb else self._cf(obs)
        if obs.to_call == 0:
            return self._raise(obs, 0.66 * obs.pot) if eq >= 0.6 else (CALL, 0)
        po = obs.to_call / max(obs.pot + obs.to_call, 1)
        return (CALL, 0) if eq >= po else (FOLD, 0)


class StickyBot(_Base):
    """'Never fold a pair': calls any bet up to pot with a piece of the board, ignores pot
    odds, calls all-ins with any decent hand, raises only the nuts-ish."""

    def act(self, obs):
        pct, eq = self._strength(obs)
        if obs.street == 0:
            if pct <= 0.03:
                return self._raise(obs, max(obs.bets) * 3)
            return (CALL, 0) if pct <= 0.7 and obs.to_call <= 10 * obs.bb else self._cf(obs)
        if eq >= 0.85:
            return self._raise(obs, max(obs.bets) + 0.75 * obs.pot)
        if obs.to_call == 0:
            return (CALL, 0)
        all_in = obs.to_call >= obs.stacks[obs.seat]
        if all_in:
            return (CALL, 0) if eq >= 0.5 else (FOLD, 0)
        return (CALL, 0) if eq >= 0.33 and obs.to_call <= obs.pot else (FOLD, 0)


class MinRaiseBot(_Base):
    """Strength buckets -> min-raise / call / fold, the shape a model writes when asked for a
    bot in five minutes. Never sizes up, never bluffs."""

    def act(self, obs):
        pct, eq = self._strength(obs)
        strong = pct <= 0.10 if obs.street == 0 else eq >= 0.7
        medium = pct <= 0.35 if obs.street == 0 else eq >= 0.45
        if strong and obs.min_raise_to > 0:
            return (RAISE, obs.min_raise_to)
        if medium or strong:
            return (CALL, 0)
        return self._cf(obs)


class OverfoldBot(_Base):
    """Scared money: open-limps a wide range, gives up to any raise without a premium,
    folds postflop to any bet without a strong hand, bets small for value only."""

    def act(self, obs):
        pct, eq = self._strength(obs)
        if obs.street == 0:
            raised = max(obs.bets) > obs.bb
            if pct <= 0.06:
                return self._raise(obs, max(obs.bets) * 3)
            if not raised and pct <= 0.4:
                return (CALL, 0)
            return self._cf(obs)
        if obs.to_call == 0:
            return self._raise(obs, 0.33 * obs.pot) if eq >= 0.75 else (CALL, 0)
        return (CALL, 0) if eq >= 0.65 else (FOLD, 0)


class PositionalBot(_Base):
    """Strong TAG: opening ranges by position, 3-bet or fold vs opens, flop c-bet as the
    preflop raiser, two-thirds-pot value bets, folds medium hands to big bets, and
    push/fold under 12 bb."""

    def act(self, obs):
        pct, eq = self._strength(obs)
        n = len(obs.stacks)
        bb = max(obs.bb, 1)
        depth = (obs.stacks[obs.seat] + obs.bets[obs.seat]) / bb
        if obs.street == 0:
            raised = max(obs.bets) > obs.bb
            if depth <= 12:
                left = sum(1 for x in obs.stacks if x > 0)
                width = (0.12 if raised else 0.30) * (6.0 / max(left, 3)) ** 0.5
                return self._shove(obs) if pct <= width else self._cf(obs)
            if not raised:
                dist = (obs.button - obs.seat) % n          # 0 button, 1 cutoff, ..., n-1 small blind
                width = 0.30 if dist == n - 1 else 0.10 if dist == n - 2 else \
                    (0.40, 0.30, 0.22, 0.17)[dist] if dist < 4 else 0.12
                if pct <= width:
                    return self._raise(obs, 2.5 * obs.bb)
                return (CALL, 0) if obs.to_call == 0 else (FOLD, 0)
            if pct <= 0.05:
                return self._raise(obs, max(obs.bets) * 3)
            return (CALL, 0) if pct <= 0.12 and obs.to_call <= 0.1 * obs.stacks[obs.seat] else self._cf(obs)
        raiser = [h[0] for h in obs.history if h[1] == 0 and h[2] == RAISE]
        aggressor = bool(raiser) and raiser[-1] == obs.seat
        if obs.to_call == 0:
            if eq >= 0.65:
                return self._raise(obs, 0.66 * obs.pot)
            if obs.street == 1 and aggressor and self._n_opp(obs) <= 2 and (eq >= 0.35 or self.rng.random() < 0.5):
                return self._raise(obs, 0.33 * obs.pot)
            return (CALL, 0)
        po = obs.to_call / max(obs.pot + obs.to_call, 1)
        if eq >= 0.85:
            return self._raise(obs, max(obs.bets) * 3)
        big = obs.to_call >= 0.66 * (obs.pot - obs.to_call)
        return (CALL, 0) if eq >= po + (0.12 if big else 0.03) else (FOLD, 0)


class BarrelBot(_Base):
    """Strong LAG: steals wide late, 3-bets light in position, fires a second barrel with
    any equity heads-up, gives up rivers without a hand, re-shoves short."""

    def act(self, obs):
        pct, eq = self._strength(obs)
        n = len(obs.stacks)
        bb = max(obs.bb, 1)
        depth = (obs.stacks[obs.seat] + obs.bets[obs.seat]) / bb
        late = (obs.button - obs.seat) % n <= 2                     # button, cutoff, hijack
        if obs.street == 0:
            raised = max(obs.bets) > obs.bb
            if raised and depth <= 18:
                return self._shove(obs) if pct <= 0.10 else self._cf(obs)
            if not raised:
                width = 0.5 if late else 0.18
                return self._raise(obs, 2.2 * obs.bb) if pct <= width else self._cf(obs)
            if pct <= (0.12 if late else 0.05):
                return self._raise(obs, max(obs.bets) * 3)
            return (CALL, 0) if pct <= 0.18 else self._cf(obs)
        heads_up = self._n_opp(obs) == 1
        if obs.to_call == 0:
            if eq >= 0.6:
                return self._raise(obs, 0.75 * obs.pot)
            if heads_up and obs.street < 3 and eq >= 0.25 and self.rng.random() < 0.6:
                return self._raise(obs, 0.6 * obs.pot)
            return (CALL, 0)
        po = obs.to_call / max(obs.pot + obs.to_call, 1)
        if eq >= 0.78:
            return self._shove(obs) if depth <= 25 else self._raise(obs, max(obs.bets) * 3)
        return (CALL, 0) if eq >= po + 0.02 else (FOLD, 0)


# ---------------------------------------------------------------------------
# Out-of-sample set (Oct 31, written before the field-fit tunes finished): plays only in
# the last confirmation run, after the candidate is chosen on FINAL_WEAK/FINAL_STRONG.
# ---------------------------------------------------------------------------

class ChenBot(_Base):
    """Size-aware TAG: opens 4 bb, folds medium hands to anything over half pot, calls
    small bets wide. The 'pot-size-matters' bot a careful quick build ends up with."""

    def act(self, obs):
        pct, eq = self._strength(obs)
        if obs.street == 0:
            raised = max(obs.bets) > obs.bb
            if not raised:
                return self._raise(obs, 4 * obs.bb) if pct <= 0.18 else self._cf(obs)
            if pct <= 0.04:
                return self._raise(obs, max(obs.bets) * 3)
            return (CALL, 0) if pct <= 0.10 and obs.to_call <= 6 * obs.bb else self._cf(obs)
        if obs.to_call == 0:
            return self._raise(obs, 0.5 * obs.pot) if eq >= 0.55 else (CALL, 0)
        small = obs.to_call <= 0.5 * (obs.pot - obs.to_call)
        if eq >= 0.8:
            return self._raise(obs, max(obs.bets) * 2.5)
        return (CALL, 0) if eq >= (0.4 if small else 0.6) else (FOLD, 0)


class PotOddsBot(_Base):
    """'Implied odds' caller: raises a tight range preflop, calls raises wide, then calls
    any bet its equity nearly covers and almost never raises after the flop."""

    def act(self, obs):
        pct, eq = self._strength(obs)
        if obs.street == 0:
            raised = max(obs.bets) > obs.bb
            if pct <= 0.12 and not raised:
                return self._raise(obs, 3 * obs.bb)
            return (CALL, 0) if pct <= 0.30 and obs.to_call <= 5 * obs.bb else self._cf(obs)
        if eq >= 0.9:
            return self._raise(obs, max(obs.bets) + obs.pot)
        if obs.to_call == 0:
            return (CALL, 0)
        return (CALL, 0) if eq * (obs.pot + obs.to_call) >= 0.8 * obs.to_call else (FOLD, 0)


class BluffyBot(_Base):
    """Aggressive quick build: opens top 30% to 2 bb, 3-bets top 15%, bets pot when checked
    to with value or a fifth of its air, barrels the turn half the time, jams strong rivers."""

    def act(self, obs):
        pct, eq = self._strength(obs)
        if obs.street == 0:
            raised = max(obs.bets) > obs.bb
            if not raised:
                return self._raise(obs, 2 * obs.bb) if pct <= 0.30 else self._cf(obs)
            if pct <= 0.15:
                return self._raise(obs, max(obs.bets) * 3)
            return (CALL, 0) if pct <= 0.22 else self._cf(obs)
        if obs.to_call == 0:
            if eq >= 0.6:
                return self._shove(obs) if obs.street == 3 and eq >= 0.8 else self._raise(obs, obs.pot)
            if self.rng.random() < (0.2 if obs.street != 2 else 0.5):
                return self._raise(obs, obs.pot)
            return (CALL, 0)
        po = obs.to_call / max(obs.pot + obs.to_call, 1)
        if eq >= 0.75:
            return self._raise(obs, max(obs.bets) * 3)
        return (CALL, 0) if eq >= po + 0.05 else (FOLD, 0)


class BrittleBot(_Base):
    """A decent TAG with edge-case bugs: it throws (and gets auto check/folded) whenever it
    faces an all-in or three or more players see the flop, the spots quick builds rarely test."""

    def act(self, obs):
        if obs.to_call >= obs.stacks[obs.seat] or (obs.street > 0 and self._n_opp(obs) >= 2):
            return self._cf(obs)
        pct, eq = self._strength(obs)
        if obs.street == 0:
            raised = max(obs.bets) > obs.bb
            if pct <= (0.05 if raised else 0.2):
                return self._raise(obs, max(obs.bets) * 3 if raised else 2.5 * obs.bb)
            return (CALL, 0) if pct <= 0.12 else self._cf(obs)
        if obs.to_call == 0:
            return self._raise(obs, 0.6 * obs.pot) if eq >= 0.6 else (CALL, 0)
        po = obs.to_call / max(obs.pot + obs.to_call, 1)
        return (CALL, 0) if eq >= po + 0.05 else (FOLD, 0)


ZOO = {
    "timeout": TimeoutBot, "random": RandomBot, "station": StationBot, "maniac": ManiacBot,
    "nit": NitBot, "tag": TagBot, "lag": LagBot, "shover": ShoverBot,
    "jammer": JammerBot, "bully": BullyBot, "trapper": TrapperBot,
    "sizer": SizerBot, "cbet": CbetBot, "mc": MCBot, "balanced": BalancedBot, "overbet": OverbetBot,
    "limper": LimperBot, "icmshort": ICMShortBot, "potcontrol": PotControlBot, "adaptive": AdaptiveBot,
    "flaky": FlakyBot, "sticky": StickyBot, "minraise": MinRaiseBot, "overfold": OverfoldBot,
    "positional": PositionalBot, "barrel": BarrelBot,
    "chen": ChenBot, "potodds": PotOddsBot, "bluffy": BluffyBot, "brittle": BrittleBot,
}
HELD_OUT = ("sizer", "cbet", "mc", "balanced", "overbet")
FRESH = ("limper", "icmshort", "potcontrol", "adaptive")
FINAL_WEAK = ("flaky", "sticky", "minraise", "overfold")
FINAL_STRONG = ("positional", "barrel")
OOS = ("chen", "potodds", "bluffy", "brittle")

# Guess at the field of a 60-minute build. Tune this after watching T1 results.
DEFAULT_FIELD_MIX = {
    "tag": 0.25, "lag": 0.12, "shover": 0.15, "nit": 0.10, "station": 0.10,
    "maniac": 0.08, "timeout": 0.12, "random": 0.08,
}

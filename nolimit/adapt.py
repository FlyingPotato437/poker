"""Live-adaptation study: portfolio, field scenarios, paired multi-strategy runner, hand-log stats.

Everything here is simulation tooling for scripts/adapt_matrix.py and scripts/event_sim.py.
Nothing in it ships in the bot.

* PORTFOLIO: the params files we could submit on the day.
* ARCHETYPES: opponent styles a field is drawn from (zoo, rivals, LLM bugs, prepped bots).
  Sealed styles (FRESH, OOS, rvh_*) are left out on purpose.
* SCENARIOS: named mixtures over ARCHETYPES; random_mixture() draws Dirichlet fields.
* run_paired(): every SNG is played once per portfolio strategy in the same seat with the
  same opponents and deck, so strategies are compared on identical deals. The first
  strategy's run also records the opponents' aggregate hand-log stats (level-2 feedback).
* mis_*: multiple-importance-sampling reweighting of the pooled per-SNG records, which gives
  the x-fair of any strategy (and the expected stats) in any mixture over ARCHETYPES,
  including drifted fields, without new SNGs.
"""
import math
import random

from .runtime import CALL, FOLD, POST, RAISE

PORTFOLIO = {
    "cand": "params/cand_nlhe.json",
    "ev_t4": "params/ev_t4.json",
    "x": "params/x_nlhe.json",
    "xex2": "params/xex2_nlhe.json",
    "s5p0": "params/s5p0_nlhe.json",
    "r2p0": "params/r2p0_nlhe.json",
    "c_calldown": "params/adapt_calldown.json",
    "c_value": "params/adapt_value.json",
    "c_steal": "params/adapt_steal.json",
}

PREP = {"prep_ev_t4": "prep:params/rival_prep.json", "prep_ev_t3": "prep:params/ev_t3.json",
        "prep_legacy": "prep:params/nlhe_final_legacy.json", "prep_hyb": "prep:params/hyb_t1_g8.json"}

ARCHETYPES = (
    # zoo
    "timeout", "random", "station", "maniac", "nit", "tag", "lag", "shover", "jammer", "bully",
    "trapper", "sizer", "cbet", "mc", "balanced", "overbet", "flaky", "sticky", "minraise",
    "overfold", "positional", "barrel",
    # rival-team designs (dev set only)
    "rv_tag", "rv_lag", "rv_gto", "rv_exploit", "rv_icm", "rv_mc", "rv_aggro", "rv_math",
    "rv_buggy", "rv_frozen",
    # LLM-bug designs
    "phase", "raiseby", "huequity", "revsizer", "limpjam", "resteal", "capclock", "ftsbluff",
    # prepped teams like us
    "prep_ev_t4", "prep_ev_t3", "prep_legacy", "prep_hyb",
)

# Style groups: the unit random mixtures and drift work on.
GROUPS = {
    "standard": ("rv_tag", "rv_gto", "rv_icm", "tag", "positional", "balanced", "rv_exploit"),
    "prepped": ("prep_ev_t4", "prep_ev_t3", "prep_legacy", "prep_hyb"),
    "llm": ("phase", "raiseby", "huequity", "revsizer", "limpjam", "resteal", "capclock", "ftsbluff"),
    "jammer": ("jammer", "shover", "limpjam", "rv_aggro"),
    "station": ("station", "sticky", "random", "huequity", "mc"),
    "nit": ("nit", "overfold", "minraise", "trapper"),
    "maniac": ("maniac", "lag", "bully", "rv_lag", "overbet", "barrel", "cbet", "sizer"),
    "broken": ("timeout", "flaky", "rv_buggy", "rv_frozen"),
    "mid": ("rv_mc", "rv_aggro", "rv_math", "mc"),
}


def _norm(w):
    w = {k: v for k, v in w.items() if v > 0}
    t = sum(w.values())
    return {k: v / t for k, v in w.items()}


def group_mix(gw):
    """Group weights -> archetype mixture (uniform inside each group)."""
    out = {}
    for g, x in gw.items():
        for a in GROUPS[g]:
            out[a] = out.get(a, 0.0) + x / len(GROUPS[g])
    return _norm(out)


SCENARIOS = {
    # "everyone did the same research": sound TAG/GTO-ish designs
    "std_tag": _norm({"rv_tag": 2, "rv_gto": 2, "rv_icm": 1.5, "tag": 1, "positional": 1, "balanced": 0.5,
                      "rv_exploit": 1}),
    "llm_heavy": _norm({**{k: 1 for k in GROUPS["llm"]}, "rv_mc": 0.5, "rv_aggro": 0.5, "tag": 0.5}),
    "jammer_heavy": _norm({"jammer": 2, "shover": 2, "limpjam": 1.5, "rv_aggro": 1, "tag": 1, "rv_tag": 0.5}),
    "station_heavy": _norm({"station": 2, "sticky": 1.5, "random": 1, "huequity": 1, "mc": 1, "rv_mc": 0.5,
                            "tag": 0.5}),
    "nit_heavy": _norm({"nit": 2, "overfold": 1.5, "minraise": 1, "trapper": 1, "rv_tag": 1, "tag": 0.5}),
    "maniac_heavy": _norm({"maniac": 2, "lag": 1, "bully": 1, "rv_lag": 1, "overbet": 1, "barrel": 1}),
    "prepped_heavy": _norm({"prep_ev_t4": 2.5, "prep_ev_t3": 1, "prep_legacy": 1, "prep_hyb": 1,
                            "rv_exploit": 1, "rv_gto": 1}),
    "broken_heavy": _norm({"timeout": 3, "flaky": 1.5, "rv_buggy": 1, "rv_frozen": 1, "tag": 1, "rv_tag": 1}),
    # rival-real (our best guess at a regional) plus LLM bugs
    "realistic": _norm({"rv_tag": 1, "rv_lag": 1, "rv_gto": 1, "rv_exploit": 1, "rv_icm": 1,
                        "rv_mc": 0.6, "rv_aggro": 0.6, "rv_math": 0.6, "rv_buggy": 0.4, "rv_frozen": 0.4,
                        "prep_ev_t4": 0.5, "timeout": 0.2, **{k: 0.25 for k in GROUPS["llm"]}}),
    "zoo_default": _norm({"tag": 0.25, "lag": 0.12, "shover": 0.15, "nit": 0.10, "station": 0.10,
                          "maniac": 0.08, "timeout": 0.12, "random": 0.08}),
    "rival_mid": _norm({"rv_mc": 1, "rv_aggro": 1, "rv_math": 1}),
    "strong_mixed": _norm({"rv_tag": 1, "rv_lag": 1, "rv_gto": 1, "rv_exploit": 1, "rv_icm": 1,
                           "prep_ev_t4": 1.5, "positional": 1, "barrel": 1}),
    # broad proposal with full support: makes MIS reweighting to random mixtures possible
    "uniform": _norm({k: 1 for k in ARCHETYPES}),
}
NAMED = tuple(k for k in SCENARIOS if k != "uniform")


def random_mixture(rng, alpha=0.6, spike=0.5):
    """A random field: Dirichlet(alpha) over style groups, optionally sharpened toward one group."""
    gs = list(GROUPS)
    x = [rng.gammavariate(alpha, 1.0) for _ in gs]
    if spike and rng.random() < spike:
        x[rng.randrange(len(gs))] += sum(x)
    gw = dict(zip(gs, x))
    return group_mix(gw)


# Drift: between tournaments a fraction of seats change design. Targets of the switch.
DRIFT_TARGETS = {
    "fix": group_mix({"standard": 1}),                 # broken / LLM-bug bots get fixed
    "pushfold": group_mix({"jammer": 1}),              # teams move to push/fold
    "prep": group_mix({"prepped": 1, "standard": 0.5}),  # teams import stronger code
}


def drift(mix, frac, target):
    """Move `frac` of the seats from `mix` to `target` (both archetype dicts)."""
    keys = set(mix) | set(target)
    return {k: (1 - frac) * mix.get(k, 0.0) + frac * target.get(k, 0.0) for k in keys}


def entry_spec(arch):
    return PREP.get(arch, arch)


# ---------------------------------------------------------------- hand-log stats
STAT_KEYS = ("vpip", "pfr", "agg", "allin", "ftb", "wtsd", "sd")
# numerator/denominator counters per stat
_CNT = ("dealt", "vpip", "pfr", "post_act", "post_agg", "allin", "faced", "ftb", "flop", "sd")


def hand_stats(history, showdown, skip_seat, acc, board_len=5):
    """Add one hand's opponent counts (every seat but `skip_seat`) to `acc` (dict of counters).

    wtsd = showdowns / hands that saw the flop (still in after preflop, board dealt)."""
    bet = {}
    cur = 0
    street = 0
    seen = set()
    vp, pr, ai, fold0 = set(), set(), set(), set()
    for seat, st, kind, amt, allin in history:
        if st != street:
            street, cur, bet = st, 0, {}
        if kind == POST:
            bet[seat] = amt
            cur = max(cur, amt)
            continue
        if seat == skip_seat:
            if kind == RAISE:
                cur = amt
            bet[seat] = amt if kind != FOLD else bet.get(seat, 0)
            continue
        seen.add(seat)
        prev = bet.get(seat, 0)
        facing = cur > prev
        if st == 0:
            if kind == RAISE or (kind == CALL and amt > prev):
                vp.add(seat)
            if kind == RAISE:
                pr.add(seat)
            if kind == FOLD:
                fold0.add(seat)
        else:
            acc["post_act"] += 1
            if kind == RAISE:
                acc["post_agg"] += 1
            if facing:
                acc["faced"] += 1
                if kind == FOLD:
                    acc["ftb"] += 1
        if allin and kind in (CALL, RAISE):
            ai.add(seat)
        if kind == RAISE:
            cur = amt
        if kind != FOLD:
            bet[seat] = amt
    acc["dealt"] += len(seen)
    acc["vpip"] += len(vp)
    acc["pfr"] += len(pr)
    acc["allin"] += len(ai)
    acc["flop"] += len(seen - fold0) if board_len >= 3 else 0
    acc["sd"] += sum(1 for s in showdown if s != skip_seat and s in seen)


def new_counts():
    return {k: 0 for k in _CNT}


def stats_from_counts(c):
    """Counters -> the 7 rates (vpip, pfr, agg, allin, ftb, wtsd, sd)."""
    d = max(c["dealt"], 1)
    return [c["vpip"] / d, c["pfr"] / d, c["post_agg"] / max(c["post_act"], 1), c["allin"] / d,
            c["ftb"] / max(c["faced"], 1), c["sd"] / max(c["flop"], 1), c["sd"] / d]


class Recorder:
    """Wraps our bot; on every hand end adds the opponents' action counts to self.counts."""

    def __init__(self, bot):
        self.bot = bot
        self.counts = new_counts()
        self.hands = 0
        self.seat = None

    def new_table(self, seat, n):
        self.seat = seat
        return self.bot.new_table(seat, n)

    def act(self, obs):
        return self.bot.act(obs)

    def observe(self, event):
        kind, info = event
        if kind == "hand_end":
            self.hands += 1
            try:
                hand_stats(info["history"], info["showdown"], self.seat, self.counts, len(info.get("board", ())))
            except Exception:
                pass
        return self.bot.observe(event)

    def __getattr__(self, name):
        return getattr(self.bot, name)


# ---------------------------------------------------------------- paired runner (pool worker side)
_P = {}


def _worker_init(bundle):
    from . import harness
    harness._init(bundle, None)
    _P["entries"] = {}


def _entry(spec):
    from .harness import parse_entry
    e = _P["entries"].get(spec)
    if e is None:
        e = _P["entries"][spec] = parse_entry(spec)
    return e


def _play_game(job):
    """job = (opp archetypes (7), seed, [strategy params paths], sng_kw, record_stats).

    Returns (seed, opps, [our points per strategy], counts or None, hands)."""
    import random as _r
    from .engine import SNG
    from .harness import _W, make_agent
    opps, seed, strats, sng_kw, record = job
    rng = _r.Random(seed)
    slot = rng.randrange(8)
    pts = []
    counts, hands = None, 0
    for k, path in enumerate(strats):
        seats = [entry_spec(a) for a in opps]
        seats.insert(slot, "prep:" + path)
        agents = [make_agent(_entry(s), seed * 31 + i) for i, s in enumerate(seats)]
        rec = None
        if record and k == 0:
            rec = agents[slot] = Recorder(agents[slot])
        sng = SNG(_W["variant"], agents, rng=_r.Random(seed), evaluator=_W["tables"].ev, **sng_kw)
        p = sng.run()
        pts.append(p[slot])
        if rec is not None:
            counts, hands = rec.counts, rec.hands
    return seed, list(opps), pts, counts, hands


def _play_chunk(jobs):
    return [_play_game(j) for j in jobs]


def make_games(mix, n, seed):
    """n SNGs: 7 opponents drawn i.i.d. from `mix` (archetype -> weight)."""
    rng = random.Random(seed)
    keys = sorted(mix)
    w = [mix[k] for k in keys]
    return [(tuple(rng.choices(keys, weights=w, k=7)), seed * 1_000_003 + g) for g in range(n)]


def run_paired(pool, games, strats, sng_kw=None, record=True, chunk=4):
    jobs = [(o, s, strats, sng_kw or {}, record) for o, s in games]
    parts = [jobs[i:i + chunk] for i in range(0, len(jobs), chunk)]
    out = []
    for part in pool.imap_unordered(_play_chunk, parts):
        out.extend(part)
    return out


# ---------------------------------------------------------------- MIS reweighting
def log_q(opps, mix):
    s = 0.0
    for a in opps:
        p = mix.get(a, 0.0)
        if p <= 0:
            return -math.inf
        s += math.log(p)
    return s


class Pool:
    """Pooled per-SNG records from several proposal mixtures, reweighted to any target.

    recs: list of dicts {opps, pts (list per strategy), counts, hands, scenario}.
    proposals: {scenario: (mix, n_sngs)}."""

    def __init__(self, recs, proposals):
        self.recs = recs
        self.prop = proposals
        n = sum(c for _, c in proposals.values())
        self.lmix = []
        for r in recs:
            terms = [math.log(c / n) + log_q(r["opps"], m) for m, c in proposals.values() if c]
            mx = max(terms)
            self.lmix.append(mx + math.log(sum(math.exp(t - mx) for t in terms)))

    def weights(self, target):
        lw = [log_q(r["opps"], target) - lm for r, lm in zip(self.recs, self.lmix)]
        mx = max(lw)
        w = [math.exp(x - mx) if x > -math.inf else 0.0 for x in lw]
        t = sum(w)
        return [x / t for x in w]

    @staticmethod
    def ess(w):
        return 1.0 / sum(x * x for x in w)

    def payoff(self, target, fair):
        """x-fair per strategy, its se, and the ESS."""
        w = self.weights(target)
        k = len(self.recs[0]["pts"])
        out, se = [], []
        for j in range(k):
            m = sum(wi * r["pts"][j] for wi, r in zip(w, self.recs))
            v = sum(wi * wi * (r["pts"][j] - m) ** 2 for wi, r in zip(w, self.recs))
            out.append(m / fair)
            se.append(math.sqrt(v) / fair)
        return out, se, self.ess(w)

    def stats(self, target):
        w = self.weights(target)
        c = {k: sum(wi * r["counts"][k] for wi, r in zip(w, self.recs)) for k in _CNT}
        return stats_from_counts(c)

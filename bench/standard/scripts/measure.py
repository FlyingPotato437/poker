"""Play SNGs of cand_nlhe vs a field and log every decision our bot makes.

usage: python measure.py FIELD N_SNGS SEED OUT.jsonl   (run from the repo root)
"""
import json
import multiprocessing as mp
import os
import random
import sys

ROOT = "/Users/revanthguda/poker"
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from nolimit import harness  # noqa: E402
from nolimit.engine import SNG  # noqa: E402
from nolimit.runtime import CALL, FOLD, POST, RAISE, PrepBot  # noqa: E402
from nolimit.rivals import github_fields, rival_fields  # noqa: E402

BUNDLE = os.path.join(ROOT, "bundles/nlhe_rng.nlb")
PARAMS = json.load(open(os.path.join(ROOT, "params/cand_nlhe.json")))


def fields():
    f = dict(rival_fields())
    f.update(github_fields())
    return f


class LogBot(PrepBot):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.log = []
        self.cur = None   # this hand's records

    def act(self, obs):
        out = super().act(obs)
        T = self.T
        pct = T.pct(self._cls) if self._cls is not None else None
        self.log.append({
            "hand": obs.hand_no, "street": obs.street, "seat": obs.seat, "button": obs.button,
            "hole": list(obs.hole), "board": list(obs.board), "stacks": list(obs.stacks),
            "bets": list(obs.bets), "in_hand": list(obs.in_hand), "pot": obs.pot,
            "to_call": obs.to_call, "min_to": obs.min_raise_to, "max_to": obs.max_raise_to,
            "bb": obs.bb, "sb": obs.sb, "hist": [list(h) for h in obs.history],
            "act": int(out[0]), "amt": int(out[1]), "pct": pct,
            "lam_params_pfbb": self.p.get("pf_bb"),
        })
        return out

    def observe(self, event):
        super().observe(event)
        kind, info = event
        if kind == "hand_end":
            sd = info["showdown"]
            self.log.append({"end": info["hand_no"], "showdown": {str(k): list(v) for k, v in sd.items()},
                             "board": list(info["board"]), "hist": [list(h) for h in info["history"]]})


def job(args):
    field_name, games = args
    harness._init(BUNDLE, None)
    f = fields()[field_name]
    entries = [harness.parse_entry(k, w) for k, w in f.items()]
    weights = [e["weight"] for e in entries]
    out = []
    for gseed in games:
        rng = random.Random(gseed)
        seats = rng.choices(entries, weights=weights, k=7)
        me = rng.randrange(8)
        agents = []
        for i in range(8):
            if i == me:
                agents.append(LogBot(harness._W["tables"], PARAMS, seed=gseed * 31 + i))
            else:
                e = seats.pop()
                agents.append(harness.make_agent(e, gseed * 31 + i))
        sng = SNG(harness._W["variant"], agents, rng=random.Random(gseed), evaluator=harness._W["tables"].ev)
        pts = sng.run()
        out.append({"seed": gseed, "me": me, "pts": pts[me], "hands": sng.hands_played,
                    "log": agents[me].log})
    return out


def main():
    field_name, n, seed, path = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    games = [seed * 100003 + g for g in range(n)]
    chunks = [(field_name, games[i:i + 10]) for i in range(0, n, 10)]
    with mp.get_context("spawn").Pool(2) as pool, open(path, "w") as fh:
        for part in pool.imap_unordered(job, chunks):
            for r in part:
                fh.write(json.dumps(r) + "\n")
            fh.flush()


if __name__ == "__main__":
    main()

"""Decision parity: a candidate rebuild of FALLBACK_SPEC.md shadows the reference
(PrepBot + HybTablesC + cand3 params) in real games. The reference's action is played; the
candidate sees the same observations and hand-end events, and every disagreement is counted.

    python scripts/parity_spec.py path/to/candidate.py [--sngs 40] [--field rival-real] [--show 15]

The candidate file must define SpecBot() with act(obs), observe(event), new_table(seat, n).
"""
import argparse, importlib.util, json, os, random, sys, traceback
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.chdir(ROOT)
import nolimit.harness as H
from nolimit.engine import SNG
from nolimit.runtime import PrepBot, load_tables
import hyb_tables as HT
HT.load_curve(); HT.load_e1(); HT.CURVE2_TH.update({int(k): v for k, v in json.load(open("bench/fallback2/curve2_th.json")).items()})
P = json.load(open("params/cand3_nlhe.json"))
NAMES = {0: "F", 1: "C", 2: "R"}


class Shadow:
    def __init__(self, ref, cand, tally):
        self.ref, self.cand, self.t = ref, cand, tally

    def new_table(self, seat, n):
        self.ref.new_table(seat, n)
        try:
            self.cand.new_table(seat, n)
        except Exception:
            self.t["cand_exc"] += 1

    def observe(self, ev):
        self.ref.observe(ev)
        try:
            self.cand.observe(ev)
        except Exception:
            self.t["cand_exc"] += 1

    def act(self, obs):
        a = self.ref.act(obs)
        try:
            b = self.cand.act(obs)
            b = (int(b[0]), int(b[1]))
        except Exception:
            self.t["cand_exc"] += 1
            if self.t["cand_exc"] <= 3:
                traceback.print_exc()
            b = None
        st = "pre" if obs.street == 0 else "post"
        self.t["n_" + st] += 1
        same_kind = b is not None and a[0] == b[0]
        same = same_kind and (a[0] != 2 or abs(a[1] - b[1]) <= max(1, 0.02 * a[1]))
        if same:
            self.t["ok_" + st] += 1
        elif len(self.t["bad"]) < self.t["show"]:
            self.t["bad"].append((st, NAMES[a[0]] + str(a[1]), None if b is None else NAMES.get(b[0], "?") + str(b[1]),
                                 dict(hole=list(obs.hole), board=list(obs.board), seat=obs.seat, stacks=list(obs.stacks),
                                      bets=list(obs.bets), pot=obs.pot, to_call=obs.to_call, mn=obs.min_raise_to,
                                      mx=obs.max_raise_to, bb=obs.bb, hist=[list(h) for h in obs.history])))
        return a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cand")
    ap.add_argument("--sngs", type=int, default=40)
    ap.add_argument("--field", default="rival-real")
    ap.add_argument("--seed", type=int, default=5)
    ap.add_argument("--show", type=int, default=10)
    args = ap.parse_args()
    spec = importlib.util.spec_from_file_location("cand_bot", args.cand)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    H._init("bundles/nlhe_rng.nlb", None)
    T = H._W["tables"]
    from ab_test import AB_FIELDS
    field = [H.parse_entry(k, w) for k, w in AB_FIELDS[args.field].items()]
    seatings = H.build_seatings(field, args.sngs, args.seed, fixed=[{"label": "slot"}])
    t = {"n_pre": 0, "ok_pre": 0, "n_post": 0, "ok_post": 0, "cand_exc": 0, "bad": [], "show": args.show}
    for seats, seed in seatings:
        agents = []
        for i, e in enumerate(seats):
            if e.get("label") == "slot":
                agents.append(Shadow(PrepBot(HT.HybTablesC2(T, HT_FLAGS), P, seed=1), mod.SpecBot(), t))
            else:
                agents.append(H.make_agent(e, seed * 31 + i))
        SNG(H._W["variant"], agents, rng=random.Random(seed), evaluator=T.ev,
            payouts=[100, 65, 45, 30, 20, 12, 6, 0], hands_per_level=25).run()
    for st in ("pre", "post"):
        n, ok = t["n_" + st], t["ok_" + st]
        print(f"{st:5s} agree {ok}/{n} = {100.0 * ok / max(n, 1):.2f}%")
    print("candidate exceptions:", t["cand_exc"])
    for st, a, b, o in t["bad"]:
        print(f"\n[{st}] ref {a}  cand {b}\n  {json.dumps(o)}")


HT_FLAGS = ["curve", "e1", "pre", "pf", "bf"]
if __name__ == "__main__":
    main()

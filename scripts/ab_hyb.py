"""ab_spec.py with hybrid bots seatable: hyb_<flag>+<flag> = PrepBot(cand3 params) on HybTables.
    python scripts/ab_hyb.py --bundle bundles/nlhe_rng.nlb --a hyb_curve --b prep:params/cand3_nlhe.json ...
"""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.chdir(ROOT)
import nolimit.harness as H
from nolimit.runtime import PrepBot
import hyb_tables as HT
import ab_spec
HT.load_curve(); HT.load_e1(); HT.CURVE2_TH.update({int(k): v for k, v in json.load(open("bench/fallback2/curve2_th.json")).items()})
P = json.load(open(os.environ.get("HYB_PARAMS", "params/cand3_nlhe.json")))
FLAGS = ["curve", "e1", "pre", "pf", "bf"]
import itertools
for r in range(1, 6):
    for combo in itertools.combinations(FLAGS, r):
        name = "hyb_" + "+".join(combo)
        H.ZOO[name] = (lambda c: lambda T, seed=None: PrepBot(HT.HybTables(T, c), P, seed=seed))(combo)
H.ZOO["hyb_all"] = H.ZOO["hyb_curve+e1+pre+pf+bf"]
H.ZOO["hyb_allc"] = lambda T, seed=None: PrepBot(HT.HybTablesC(T, FLAGS), P, seed=seed)
H.ZOO["hyb_allt"] = lambda T, seed=None: PrepBot(HT.HybTablesT(T, FLAGS), P, seed=seed)
H.ZOO["hyb_allc2"] = lambda T, seed=None: PrepBot(HT.HybTablesC2(T, FLAGS), P, seed=seed)
H.ZOO["hyb_curvec_only"] = lambda T, seed=None: PrepBot(HT.HybTablesC(T, ["curve"]), P, seed=seed)
if os.environ.get("BLIND_BOT"):
    import importlib.util
    _sp = importlib.util.spec_from_file_location("blind_bot", os.environ["BLIND_BOT"])
    _bm = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(_bm)
    H.ZOO["blind"] = lambda T, seed=None: _bm.SpecBot()
if __name__ == "__main__":
    ab_spec.main()

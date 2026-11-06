"""Write the counter-mode variants of cand_nlhe (params/cw_*.json) from one detector rule."""
import json
import os
import sys

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
DET = json.loads(sys.argv[1])
cand = json.load(open("params/cand_nlhe.json"))
VARIANTS = {
    "cw_det": {"lam0": 1},
    "cw_safe": {"lam0": 1, "pf_tax": 0.03, "pre_tax": 0.03, "call_tax": 0.05, "cont": 1.15, "steal": 0.8},
    "cw_boost": {"lam0": 1, "boost": 0.3},
    "cw_f3": {"lam0": 1, "f3_k": 0.5, "f3_thr": 0.5, "f3_n": 6},
    "cw_shove": {"lam0": 1, "shove": 0.8, "pf_tax": 0.03},
    "cw_all": {"lam0": 1, "pf_tax": 0.03, "pre_tax": 0.03, "call_tax": 0.05, "cont": 1.15, "steal": 0.8,
               "boost": 0.3, "f3_k": 0.5, "f3_thr": 0.5, "f3_n": 6, "shove": 0.8},
}
for name, extra in VARIANTS.items():
    p = json.loads(json.dumps(cand))
    p["exploit"]["strong"] = dict(DET, **extra)
    for k, v in list(p["exploit"]["strong"].items()):
        if isinstance(v, list):
            p["exploit"]["strong"][k] = tuple(v)
    with open(f"params/{name}.json", "w") as fh:
        json.dump(p, fh, indent=1, sort_keys=True)
    print(name, p["exploit"]["strong"])

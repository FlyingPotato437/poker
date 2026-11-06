"""Write the three targeted counter-strategies (cand_nlhe + a few param shifts) for the adaptation study.

    python scripts/make_counters.py

Each shift is applied to cand's base params and to its exploit-layer params, clamped to
runtime.PARAM_SPACE.
  adapt_calldown: vs jammers/maniacs - call shoves and big bets wider, less survival premium.
  adapt_value:    vs stations - assume opponents continue more (fewer bluffs, thinner/bigger value).
  adapt_steal:    vs nits - open and shove wider, steal harder vs tables that rarely play.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from nolimit.runtime import PARAM_SPACE  # noqa: E402

SHIFTS = {
    "adapt_calldown": {"pf_call_scale": ("mul", 1.25), "call_ev_margin": ("mul", 0.4), "risk_av": ("mul", 0.6),
                       "bust_tax": ("mul", 0.5), "commit_eq": ("add", -0.06), "call_margin": ("add", -0.04),
                       "call_width": ("mul", 1.15)},
    "adapt_value": {"cont_b0": ("add", 0.6), "bluff_freq": ("mul", 0.4), "vbet_eq": ("add", -0.05),
                    "vbet_frac": ("mul", 1.25), "ev_margin": ("add", -0.02)},
    "adapt_steal": {"open_base": ("add", 0.05), "open_late": ("add", 0.10), "steal_exploit": ("add", 0.5),
                    "pf_exploit": ("add", 0.5), "pf_shove_scale": ("mul", 1.15), "iso_pct": ("add", 0.04)},
}


def shift(p, sh):
    q = dict(p)
    for k, (op, x) in sh.items():
        v = q[k] * x if op == "mul" else q[k] + x
        lo, hi = PARAM_SPACE.get(k, (-1e9, 1e9))
        q[k] = min(max(v, lo), hi)
    return q


def main():
    base = json.load(open(os.path.join(ROOT, "params", "cand_nlhe.json")))
    for name, sh in SHIFTS.items():
        out = shift({k: v for k, v in base.items() if k != "exploit"}, sh)
        ex = dict(base["exploit"])
        ex["params"] = shift(ex["params"], sh)
        out["exploit"] = ex
        with open(os.path.join(ROOT, "params", name + ".json"), "w") as fh:
            json.dump(out, fh, indent=2, sort_keys=True)
        print("wrote params/%s.json" % name)


if __name__ == "__main__":
    main()

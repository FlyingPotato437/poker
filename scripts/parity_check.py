"""Parity of the engine with every house rule off against the frozen pre-rules engine
(tests/legacy_engine.py), on real tables and the real bots: same seeds -> same decisions,
same points, same errors, per seat. Also checks that hand logging changes nothing.

    python scripts/parity_check.py --bundle bundles/nlhe_rng.nlb --sngs 60
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from nolimit import harness  # noqa: E402
from nolimit.engine import SNG as New  # noqa: E402
from nolimit.rivals import rival_fields  # noqa: E402
from nolimit.zoo import DEFAULT_FIELD_MIX  # noqa: E402
from tests.legacy_engine import SNG as Legacy  # noqa: E402


def key(rows):
    return sorted((r[0], round(r[1], 9), r[2], r[6], r[7]) for r in rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", default="bundles/nlhe_rng.nlb")
    ap.add_argument("--candidate", default="prep:params/cand_nlhe.json")
    ap.add_argument("--sngs", type=int, default=60)
    args = ap.parse_args()
    me = harness.parse_entry(args.candidate)
    me["label"] = "me"
    ok = True
    for fname, mix in (("rival-real", rival_fields()["rival-real"]), ("zoo", DEFAULT_FIELD_MIX)):
        games = harness.build_seatings([harness.parse_entry(k, w) for k, w in mix.items()], args.sngs, 7, fixed=[me])
        for kw in ({}, {"hands_per_level": 10, "ante": 5}):
            res = {}
            for name, cls in (("new", New), ("legacy", Legacy)):
                harness.SNG = cls
                res[name] = harness.run_games(games, bundle=args.bundle, workers=1, raw=True, sng_kw=kw)
            harness.SNG = New
            logged, logs = harness.run_games(games, bundle=args.bundle, workers=1, raw=True, sng_kw=kw,
                                             log_labels=["me"])
            same = key(res["new"]) == key(res["legacy"]) == key(logged)
            ok &= same
            print(f"{fname:<11} {str(kw):<38} decisions {sum(r[2] for r in res['new']):>7}  "
                  f"hand records {len(logs):>6}  identical: {same}")
    print("PARITY OK" if ok else "PARITY FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

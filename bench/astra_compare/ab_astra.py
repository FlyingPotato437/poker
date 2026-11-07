"""A/B our rc2 (cand3) against the teammate's push (Sriki, origin/main 364b0b4).

Their packaged NLHE strategy = frozen/rc1/nlhe_bot.py bytes (sha 8a3af61dca46) wrapped in
nolimit/official_payouts.DecisionTables (payout-linear ICM basis + charts only if payouts match).
Bots registered (all on the harness's rebundled tables for the tested payouts):
  astra_rc1   PrepBot(their embedded params) on our tables
  astra_full  PrepBot(their params) on DecisionTables(T, basis, payouts)   = their package's strategy
  c3_astra    PrepBot(cand3) on DecisionTables(...)                        = their ICM layer + our strategy
  c3_nochart  PrepBot(cand3), push/fold charts disabled                    = their fallback when payouts mismatch
"""
import importlib.util, json, os, sys
ROOT = os.path.expanduser("~/poker")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.chdir(ROOT)
import nolimit.harness as H
from nolimit.runtime import PrepBot
from nolimit.runtime import read_bundle
import ab_spec

_sp = importlib.util.spec_from_file_location("astra_payouts", os.path.join(HERE, "main/nolimit/official_payouts.py"))
OP = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(OP)
_m, _a = read_bundle(open(os.path.join(HERE, "icm_basis.nlb"), "rb").read())  # as their agent.py does
BASIS = OP.PayoutBasis(_m, _a)


def _embedded_params(path):
    for line in open(path):
        if line.startswith("_PARAMS = "):
            return json.loads(line[len("_PARAMS = "):])
    raise ValueError(path)


P_RC1 = _embedded_params(os.path.join(HERE, "main/frozen/rc2/nlhe_bot.py"))
P_C3 = json.load(open(os.path.join(ROOT, "params/cand3_nlhe.json")))


def _dt(T):
    pay = T.meta.get("payouts") or OP.DEFAULT_PAYOUTS
    # their build stamps pf_ante_bb on rebuilt charts; our rebundle does not, so stamp it (ante 0)
    T.meta.setdefault("pf_ante_bb", 0.0)
    return OP.DecisionTables(T, BASIS, pay, 8, 0.0)


class _NoChart:
    def __init__(self, T):
        self._T = T

    def __getattr__(self, k):
        return getattr(self._T, k)

    has_pushfold = False

    def shove_threshold(self, *a):
        return None

    def call_threshold(self, *a):
        return None


H.ZOO["astra_rc1"] = lambda T, seed=None: PrepBot(T, P_RC1, seed=seed)
H.ZOO["astra_full"] = lambda T, seed=None: PrepBot(_dt(T), P_RC1, seed=seed)
H.ZOO["c3_astra"] = lambda T, seed=None: PrepBot(_dt(T), P_C3, seed=seed)
H.ZOO["c3_nochart"] = lambda T, seed=None: PrepBot(_NoChart(T), P_C3, seed=seed)



# Bot built for the WRONG payouts (our default 100/65/45/30/20/12/6/0, as frozen rc2 is), played
# under whatever payouts the run uses: what a build-time --points mistake costs. c3_live = the
# same tables but ICM from live payouts via their DecisionTables (charts drop if they mismatch).
from benchmark import rebundle as _rb, PAYOUTS as _PO
from nolimit.runtime import Tables as _Tab
_WRONG = {}


def _wrong_T():
    if "T" not in _WRONG:
        _WRONG["T"] = _Tab(open(_rb(os.path.join(ROOT, "bundles/nlhe_rng.nlb"), _PO["default"]), "rb").read())
    return _WRONG["T"]


def _live(T):
    W = _wrong_T()
    W.meta.setdefault("pf_ante_bb", 0.0)
    return OP.DecisionTables(W, BASIS, T.meta.get("payouts"), 8, 0.0)


H.ZOO["c3_wrongpay"] = lambda T, seed=None: PrepBot(_wrong_T(), P_C3, seed=seed)
H.ZOO["c3_live"] = lambda T, seed=None: PrepBot(_live(T), P_C3, seed=seed)

if __name__ == "__main__":
    ab_spec.main()

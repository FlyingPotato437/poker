"""SpecBot: poker bot implemented from SPEC.md only (blind3 test). Standard library only."""
import gc
import math
from time import perf_counter

gc.collect()
gc.freeze()
gc.disable()

FOLD, CALL, RAISE, POST = 0, 1, 2, 3
COUNTERS = ("hands", "vpip", "pfr", "shove", "faced", "folded", "raised",
            "faced_ab", "folded_ab", "bet_opp", "bets", "aggr", "passive",
            "acts", "allin", "minr", "fs_n", "fs_f", "fs_r")
RANKS = "23456789TJQKA"


# ----------------------------------------------------------------- helpers (SPEC 0)
def clamp(x, lo, hi):
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def sigmoid(z):
    z = clamp(z, -60.0, 60.0)
    return 1.0 / (1.0 + math.exp(-z))


def logit(p):
    p = clamp(p, 1e-4, 1.0 - 1e-4)
    return math.log(p / (1.0 - p))


# ----------------------------------------------------------------- preflop tables (SPEC 1)
HAND_ORDER = """AA KK QQ JJ TT 99 88 AKs 77 AQs AJs AKo AQo ATs AJo KQs 66 A9s KJs ATo A8s KTs KQo A9o
A7s QJs KJo 55 K9s A6s A5s KTo QTs A8o A4s A7o A3s K8s QJo K9o A5o K7s A6o JTs Q9s QTo
A2s 44 K6s A4o Q8s A3o K8o K5s K7o J9s Q9o A2o JTo K4s Q7s K6o T9s J8s K3s Q6s K5o Q8o
33 J9o K2s Q5s J7s K4o T8s Q4s Q7o K3o J8o T9o T7s Q6o 98s Q3s J6s K2o 22 J5s Q2s Q5o
J7o Q4o T8o J4s T6s 97s Q3o J3s 98o T7o 87s J6o 96s J2s Q2o J5o T5s J4o T4s 86s 97o T6o
95s T3s J3o 76s 87o T2s 85s J2o T5o 96o 94s 75s T4o 86o 93s 65s 84s T3o 95o 92s 76o 74s
54s T2o 85o 64s 83s 94o 82s 75o 65o 93o 73s 53s 63s 84o 92o 43s 74o 72s 54o 64o 52s 62s
83o 82o 42s 73o 53o 63o 32s 43o 72o 52o 62o 42o 32o""".split()

_E1_TXT = """85 82 80 77 75 72 69 67 66 66 65 65 64 65 64 63 63 63 63 63 62 62 61 61 61 60 61 60 60
60 60 60 59 60 59 59 58 58 58 58 58 58 58 58 58 57 57 57 57 57 56 56 56 56 55 56 55 55
55 55 54 54 54 54 54 54 53 54 54 53 53 53 52 52 52 52 52 51 52 52 51 51 51 51 51 50 50
50 50 50 50 49 50 49 49 49 48 48 48 48 48 48 47 47 47 47 47 46 47 46 46 46 46 46 45 45
45 45 45 44 44 44 44 44 44 43 43 43 43 43 43 42 42 42 42 42 41 41 41 41 40 40 40 40 40
40 39 39 39 39 39 38 38 38 38 38 38 37 37 37 36 36 36 35 35 34 34 33 32"""
E1_VALS = [int(x) for x in _E1_TXT.split()]
assert len(HAND_ORDER) == 169 and len(E1_VALS) == 169

_PCT = {}
_E1 = {}
_cum = 0
for _i, _h in enumerate(HAND_ORDER):
    _cum += 6 if len(_h) == 2 else (4 if _h[2] == "s" else 12)
    _PCT[_h] = _cum / 1326.0
    _E1[_h] = E1_VALS[_i] / 100.0

EQR = [  # y, c0, c1, c2, c3, c4
    (0.03, -0.950, 0.629, -0.497, -0.971, -0.110), (0.06, -0.821, 0.350, -0.078, -0.657, -0.057),
    (0.10, -0.682, 0.215, 0.025, -0.554, -0.077), (0.15, -0.572, 0.182, 0.036, -0.480, -0.118),
    (0.20, -0.548, 0.218, 0.030, -0.438, -0.114), (0.30, -0.549, 0.430, 0.019, -0.344, -0.010),
    (0.45, -0.488, 0.793, -0.048, -0.206, 0.227), (0.65, -0.308, 1.056, -0.091, -0.078, 0.551),
    (1.00, 0.000, 1.000, 0.000, 0.000, 0.000)]

BF_FULL = {2: 1.00, 3: 1.41, 4: 1.57, 5: 1.64, 6: 1.73, 7: 1.75, 8: 1.76}
BF_SHARE = [[0.41, 0.53, 0.81],
            [0.29, 1.00, 1.49],
            [0.15, 0.44, 2.36]]

PF_STACKS = (2, 3, 4, 5, 6, 8, 10, 12, 15, 18, 21)
_SHOVE_RAW = {
    2: "90 78 74 74 70 65 59 54 48 41 37",
    3: "36 49 51 49 46 44 40 34 28 25 21 | 67 77 78 77 75 69 64 63 57 52 47",
    4: "34 45 42 43 41 36 29 25 21 19 16 | 38 51 52 52 54 50 45 39 32 24 22 | 68 80 85 84 86 82 82 73 68 62 62",
    5: "31 37 38 37 33 26 24 21 17 15 13 | 33 43 44 46 43 39 29 27 22 21 17 | 37 51 51 53 54 53 48 41 32 26 26 | 69 83 87 87 88 87 86 82 76 71 66",
    6: "28 32 33 27 26 23 18 17 15 14 14 | 30 37 39 38 33 27 24 20 17 16 15 | 34 43 44 46 44 38 31 28 25 22 18 | 37 50 53 55 56 54 54 42 34 28 26 | 70 83 87 88 94 95 90 91 83 80 67",
    7: "26 28 26 23 24 18 17 15 14 13 12 | 28 31 32 27 26 23 19 17 15 14 14 | 30 36 37 38 34 27 23 21 18 16 15 | 33 42 44 46 44 38 31 28 24 24 19 | 36 49 54 56 57 54 54 43 37 27 27 | 69 84 87 91 96 97 91 92 84 82 69",
    8: "22 24 22 23 19 17 15 14 14 12 8 | 25 28 26 25 25 18 18 15 15 14 13 | 28 32 33 27 27 23 20 19 15 15 15 | 30 36 39 39 33 29 25 22 19 16 16 | 33 43 46 46 47 37 32 28 26 22 20 | 37 49 54 58 60 56 55 50 37 30 31 | 71 85 91 95 97 100 95 97 89 83 75",
}
SHOVE_CHART = {n: [[float(v) / 100.0 for v in row.split()] for row in raw.split("|")]
               for n, raw in _SHOVE_RAW.items()}
_CALL_RAW = {
    "hu": "99.9 92.7 72.7 61.7 54.7 44.6 38.4 32.8 27.5 23.4 20.7",
    "3:10": "91.8 60.1 48.8 40.5 35.4 28.3 23.2 19.3 15.7 13.2 11.5",
    "3:20": "80.5 41.9 32.8 27.5 23.2 17.2 13.6 10.6 8.4 7.1 6.1",
    "3:21": "8.6 15.2 13.7 12.2 11.1 9.8 8.5 8.0 7.1 5.8 5.4",
    "10": "70.7 49.6 39.0 32.4 27.3 21.0 17.1 14.4 11.7 9.8 8.5",
    "20": "53.0 32.2 25.6 20.2 17.3 12.4 9.3 7.7 6.2 5.4 5.1",
    "21": "14.6 15.3 12.5 11.5 9.7 8.5 7.5 6.5 5.4 4.6 3.3",
    "30": "49.7 28.5 21.0 16.3 12.8 8.5 6.9 5.7 5.2 3.6 3.0",
    "31": "13.1 12.9 10.7 9.0 8.1 7.0 5.5 5.3 3.3 3.0 2.9",
    "32": "6.7 7.2 7.1 6.8 6.4 5.4 5.0 3.4 3.0 3.0 2.5",
    "40": "39.6 20.9 13.4 9.9 7.7 5.8 4.4 3.7 2.9 2.5 2.1",
    "41": "11.7 9.8 8.2 7.0 6.1 4.7 3.9 2.9 2.5 2.1 1.8",
    "42": "6.2 6.1 5.6 4.8 4.2 3.3 2.7 2.4 2.0 1.7 1.5",
}
CALL_CHART = {k: [float(v) / 100.0 for v in raw.split()] for k, raw in _CALL_RAW.items()}

SH_OPEN = (0.50, 0.50, 0.42, 0.28, 0.23, 0.19, 0.16, 0.14)
POST_SIZES = (0.33, 0.66, 1.0, 1.5)
RAISE_SIZES = (0.8, 1.3)
PO_REF = 0.65 / 2.3

# ----------------------------------------------------------------- postflop tables (SPEC 2)
GROUP = (0, 0, 0, 1, 1, 2, 2, 2, 3, 3, 3, 3, 3)  # bucket -> group

# street: (intercepts for buckets 0..12, weights group 0, group 1, group 2, group 3)
POST_E1 = {
    1: ((0.233, 0.309, 0.451, 0.738, 0.880, 0.732, 0.740, 0.740, 0.871, 0.940, 0.972, 1.056, 0.981),
        (0.099, 0.026, -0.056, -0.027, 0.059, 0.046, 0.099, 0.026, 0.028, 0.000, 0.000),
        (0.042, 0.027, -0.097, -0.045, 0.012, 0.002, 0.069, -0.104, 0.018, 0.000, 0.000),
        (0.019, 0.026, -0.090, -0.048, 0.002, 0.032, 0.055, 0.000, 0.026, 0.000, 0.000),
        (0.021, 0.008, -0.114, -0.053, -0.016, 0.019, -0.013, -0.025, 0.016, 0.000, 0.000)),
    2: ((0.126, 0.181, 0.269, 0.763, 0.843, 0.769, 0.780, 0.790, 0.871, 0.966, 0.974, 1.053, 0.983),
        (0.115, 0.029, -0.033, -0.019, 0.079, 0.048, 0.115, 0.042, 0.032, -0.079, -0.010),
        (0.038, 0.026, -0.064, -0.040, 0.022, -0.011, 0.076, -0.125, 0.008, -0.163, -0.117),
        (0.017, 0.021, -0.064, -0.039, -0.006, 0.049, 0.015, 0.000, 0.021, -0.266, -0.126),
        (0.041, 0.008, -0.069, -0.028, -0.051, 0.019, -0.016, -0.024, 0.012, -0.156, -0.100)),
    3: ((0.027, 0.000, 0.000, 0.798, 0.000, 0.806, 0.815, 0.833, 0.882, 0.990, 1.007, 1.074, 1.014),
        (0.142, 0.027, -0.018, -0.024, 0.092, 0.029, 0.142, 0.083, 0.057, -0.044, -0.028),
        (0.033, 0.035, -0.031, -0.032, 0.048, -0.028, 0.093, -0.149, -0.009, -0.205, -0.140),
        (0.021, 0.019, -0.040, -0.014, -0.004, 0.037, -0.006, 0.000, 0.000, -0.279, -0.165),
        (0.033, 0.012, -0.035, -0.005, -0.066, 0.014, -0.006, -0.020, -0.014, -0.192, -0.113)),
}

# street: ((c0, d1, d2, d3, d4, d5, d6), [(A, B, C) for buckets 0..12])
CURVE = {
    1: ((-0.070, 0.153, 0.303, 0.049, 0.133, -0.046, 0.003),
        [(1.405, 0.747, 0.165), (0.979, 0.327, 0.032), (0.712, 0.156, 0.024), (1.127, 0.304, 0.040),
         (0.825, 0.089, 0.035), (0.855, 0.004, -0.169), (0.571, -0.152, -0.253), (0.591, -0.344, -0.229),
         (0.287, -0.393, -0.206), (0.119, -0.690, -0.227), (0.180, -0.662, -0.160), (0.238, -0.589, -0.127),
         (-0.246, -0.869, -0.185)]),
    2: ((-0.076, 0.068, 0.294, 0.063, 0.197, -0.072, 0.005),
        [(2.136, 1.122, 0.277), (1.483, 0.517, 0.129), (1.192, 0.365, 0.083), (1.759, 0.441, 0.066),
         (1.322, 0.197, 0.044), (1.375, 0.012, -0.223), (1.122, -0.197, -0.278), (1.155, -0.434, -0.268),
         (0.842, -0.407, -0.257), (0.556, -0.662, -0.306), (0.728, -0.693, -0.149), (0.753, -0.471, -0.211),
         (0.472, -0.727, -0.305)]),
    3: ((-0.047, -0.323, 0.299, 0.093, 0.643, -0.231, 0.027),
        [(4.303, 1.673, 0.666), (2.782, -0.207, -0.210), (2.782, -0.207, -0.210), (4.309, 0.798, 0.238),
         (2.782, -0.207, -0.210), (3.729, -0.055, -0.319), (3.374, -0.426, -0.439), (3.159, -0.810, -0.474),
         (3.037, -0.637, -0.414), (2.338, -0.766, -0.484), (2.329, -0.802, -0.242), (2.200, -0.495, -0.401),
         (1.825, -0.757, -0.442)]),
}

# ----------------------------------------------------------------- exploit settings (SPEC 4)
SETTINGS = {  # name: (base at level 0, exploit at level 4)
    "open_base": (0.2643, 0.2654), "open_late": (0.4262, 0.4165), "open_bb": (2.965, 2.842),
    "steal_exploit": (2.031, 1.752), "iso_pct": (0.1030, 0.1541), "sb_complete_pct": (0.7267, 0.7694),
    "reraise_eq": (0.5884, 0.6112), "reraise_mult": (3.221, 2.903), "pre_realize": (0.9222, 0.9486),
    "pre_tighten": (0.4378, 0.4141), "pf_bb": (21.09, 16.54), "pf_shove_scale": (1.167, 1.087),
    "pf_call_scale": (1.348, 1.384), "pf_exploit": (1.609, 1.325), "pf_margin": (0.01941, 0.02509),
    "icm_weight": (0.9605, 0.8630), "realize": (0.8195, 0.8219), "realize_chk": (0.8665, 0.8811),
    "ev_margin": (0.04654, 0.03703), "call_ev_margin": (0.08401, 0.07154), "risk_av": (1.032, 1.228),
    "risk_depth": (28.24, 26.98), "raise_cont": (0.9975, 1.072), "call_width": (1.445, 1.415),
    "cont_b0": (1.035, 1.175), "cont_b1": (1.633, 1.713), "cont_b2": (-1.784, -1.766),
    "cont_b3": (-0.267, -0.3887), "cont_b4": (-2.719, -2.337), "rng_y_scale": (2.126, 1.834),
    "rng_bet_scale": (1.556, 1.590), "rng_check_cap": (0.6540, 0.3317), "rng_call_cut": (0.9865, 0.9073),
    "rng_persist": (0.3338, 0.3326),
}

# (a, b) per rate for lam(s), SPEC 4
LAM_COEF = {
    "vpip": (-42.0452, 77.96), "pfr": (-1.6526, -27.8091), "agg": (5.9021, -3.169),
    "ftb": (-16.0593, 6.8088), "shove": (11.7009, 26.4823), "bet": (-10.378, 1.5881),
    "fold_nb": (-8.5967, 9.9044),
}


def settings(level):
    f = level / 4.0
    return {k: b + f * (e - b) for k, (b, e) in SETTINGS.items()}


# ----------------------------------------------------------------- cards and hand names
def hole_name(hole):
    a, b = hole[0], hole[1]
    ra, rb = a // 4 + 2, b // 4 + 2
    hi, lo = max(ra, rb), min(ra, rb)
    if hi == lo:
        return RANKS[hi - 2] * 2
    suited = (a % 4) == (b % 4)
    return RANKS[hi - 2] + RANKS[lo - 2] + ("s" if suited else "o")


def pct_hole(hole):
    return _PCT[hole_name(hole)]


def e1_pre(hole):
    return _E1[hole_name(hole)]


def eqr(name, y):
    """Equity vs the top-y share of hands (SPEC 1)."""
    y = clamp(y, 0.03, 1.0)
    r = math.log(clamp(_PCT[name] / y, 0.05, 20.0))
    L = logit(_E1[name])
    pair = 1.0 if name[0] == name[1] else 0.0
    if y <= 0.03:
        lo, hi, t = 0, 1, 0.0
    else:
        hi = 1
        while EQR[hi][0] < y:
            hi += 1
        lo = hi - 1
        t = (y - EQR[lo][0]) / (EQR[hi][0] - EQR[lo][0])
    z_lo = _row_z(EQR[lo], L, pair, r)
    z_hi = _row_z(EQR[hi], L, pair, r)
    return sigmoid(z_lo * (1.0 - t) + z_hi * t)


def _row_z(row, L, pair, r):
    c0, c1, c2, c3, c4 = row[1:]
    return c0 + c1 * L + c2 * pair + c3 * min(r, 0.0) + c4 * max(r, 0.0)


def eqr_hole(hole, y):
    return eqr(hole_name(hole), y)


def BF(n, hero_share, villain_share, risk):
    """ICM bubble factor (SPEC 1)."""
    if n < 2:
        return 1.0
    hc = _share_class(hero_share, n)
    vc = _share_class(villain_share, n)
    return 1.0 + (BF_FULL[min(n, 8)] - 1.0) * BF_SHARE[hc][vc] * clamp(risk, 0.0, 1.0) ** 1.2


def _share_class(share, n):
    if share < 0.7 / n:
        return 0
    if share > 1.4 / n:
        return 2
    return 1


def _interp(vals, x):
    if x <= PF_STACKS[0]:
        return vals[0]
    if x >= PF_STACKS[-1]:
        return vals[-1]
    for i in range(len(PF_STACKS) - 1):
        a, b = PF_STACKS[i], PF_STACKS[i + 1]
        if a <= x <= b:
            t = (x - a) / (b - a)
            return vals[i] * (1.0 - t) + vals[i + 1] * t
    return vals[-1]


def _shove_chart(n, pos, eff_bb):
    if n not in SHOVE_CHART or pos > n - 2:
        return None
    return _interp(SHOVE_CHART[n][pos], eff_bb)


def _call_key(n, spos, pos):
    if not (2 <= n <= 8 and spos < pos < n):
        return None
    if n == 2:
        return "hu"
    K = min(n - 1 - spos, 4)
    J = min(n - 1 - pos, 2)
    kj = "%d%d" % (K, J)
    return "3:" + kj if n == 3 else kj


def _call_chart(n, spos, pos, eff_bb):
    key = _call_key(n, spos, pos)
    if key is None or key not in CALL_CHART:
        return None
    return _interp(CALL_CHART[key], eff_bb)


# ----------------------------------------------------------------- hand categories and buckets (SPEC 2a)
def _has_straight(ranks):
    s = set(ranks)
    if 14 in s:
        s.add(1)
    return any(all((lo + i) in s for i in range(5)) for lo in range(1, 11))


def _cat(cards):
    """0 high, 1 pair, 2 two pair, 3 trips, 4 straight, 5 flush, 6 full house or better."""
    cnt = {}
    suit = {}
    for c in cards:
        r = c // 4 + 2
        cnt[r] = cnt.get(r, 0) + 1
        suit.setdefault(c % 4, []).append(r)
    vals = sorted(cnt.values(), reverse=True)
    flush = [s for s in suit if len(suit[s]) >= 5]
    for s in flush:
        if _has_straight(suit[s]):
            return 6
    if vals[0] >= 4:
        return 6
    if vals[0] >= 3 and len(vals) > 1 and vals[1] >= 2:
        return 6
    if flush:
        return 5
    if _has_straight(cnt.keys()):
        return 4
    if vals[0] >= 3:
        return 3
    if len(vals) > 1 and vals[1] >= 2:
        return 2
    if vals[0] >= 2:
        return 1
    return 0


def _draws(hole, board):
    """(strong, weak) draws; only meaningful before the river."""
    allc = list(hole) + list(board)
    hr = [c // 4 + 2 for c in hole]
    top = max(c // 4 + 2 for c in board)
    strong = False
    for s in range(4):
        if sum(1 for c in allc if c % 4 == s) == 4 and any(c % 4 == s for c in hole):
            strong = True
    hset = {c // 4 + 2 for c in allc}
    bset = {c // 4 + 2 for c in board}
    outs = 0
    for x in range(2, 15):
        if x in hset:
            continue
        if _has_straight(hset | {x}) and not _has_straight(bset | {x}):
            outs += 1
    if outs >= 2:
        strong = True
    weak = (not strong) and (outs == 1 or min(hr) > top)
    return strong, weak


def _bucket(hole, board):
    """Returns (bucket 0..12, group 0..3) per SPEC 2a."""
    allc = list(hole) + list(board)
    hr = [c // 4 + 2 for c in hole]
    br = [c // 4 + 2 for c in board]
    cat = _cat(allc)
    bcat = _cat(board) if len(board) >= 3 else 0
    top = max(br)
    pocket = hr[0] == hr[1]
    allcnt = {}
    for c in allc:
        r = c // 4 + 2
        allcnt[r] = allcnt.get(r, 0) + 1
    paired = [r for r in dict.fromkeys(hr) if r in br]
    if cat >= 6 and bcat < 6:
        bk = 12
    elif cat == 5 and bcat < 5:
        bk = 11
    elif cat == 4 and bcat < 4:
        bk = 10
    elif cat in (3, 6) and any(allcnt[r] >= 3 for r in set(hr)):
        bk = 9
    elif len(paired) == 2:
        bk = 8
    else:
        strong, weak = _draws(hole, board) if len(board) in (3, 4) else (False, False)
        if pocket and hr[0] > top:
            bk = 7
        elif paired:
            r = paired[0]
            if r == top:
                kick = hr[1] if hr[0] == r else hr[0]
                bk = 6 if kick >= 10 else 5
            else:
                bk = 4 if strong else 3
        elif pocket:
            bk = 4 if strong else 3
        elif strong:
            bk = 2
        elif weak:
            bk = 1
        else:
            bk = 0
    return bk, GROUP[bk]


def _features(hole, board):
    """The 11 features f of SPEC 2b."""
    hr = sorted([c // 4 + 2 for c in hole], reverse=True)
    br = [c // 4 + 2 for c in board]
    bs = [c % 4 for c in board]
    bset = sorted(set(br))
    hi = (hr[0] - 8) / 6.0
    lo = (hr[1] - 8) / 6.0
    max_suit = max(bs.count(s) for s in range(4))
    fb = 1.0 if max_suit >= 3 else 0.0
    cb = 1.0 if any(bset[i + 2] - bset[i] <= 4 for i in range(len(bset) - 2)) else 0.0
    pb = 1.0 if len(set(br)) < len(br) else 0.0
    top = (bset[-1] - 8) / 6.0
    mine_r = next((r for r in hr if r in bset), hr[0])
    mine = (mine_r - 8) / 6.0
    over = min(sum(1 for r in bset if r > mine_r), 2) / 2.0
    fdn = 0.0
    for c in hole:
        if c // 4 + 2 == 14 and bs.count(c % 4) >= 2:
            fdn = 1.0
    fb4 = 1.0 if max_suit >= 4 else 0.0
    u = list(bset)
    if 14 in bset:
        u = [1] + u
    sb4 = 1.0 if any(u[i + 3] - u[i] <= 4 for i in range(len(u) - 3)) else 0.0
    return (hi, lo, fb, cb, pb, top, mine, over, fdn, fb4, sb4)


def _e1_post(hole, board, st, bk, grp):
    intercepts = POST_E1[st][0]
    w = POST_E1[st][1 + grp]
    f = _features(hole, board)
    z = intercepts[bk] + sum(wi * fi for wi, fi in zip(w, f))
    return clamp(z, 0.02, 0.99)


def post_ctx(hole, board):
    """(street, bucket, e1, L) for a flop/turn/river spot."""
    st = {3: 1, 4: 2, 5: 3}[len(board)]
    bk, grp = _bucket(hole, board)
    e1 = _e1_post(hole, board, st, bk, grp)
    return st, bk, e1, logit(e1)


def post_bucket(hole, board):
    return _bucket(hole, board)[0]


def post_e1(hole, board):
    return post_ctx(hole, board)[2]


def _re(st, bk, L, y, x):
    """Equity vs the top-x slice of the top-y range (SPEC 2c)."""
    (c0, d1, d2, d3, d4, d5, d6), abc = CURVE[st]
    A, B, C = abc[bk]
    lx = math.log(clamp(x, 0.05, 1.0))
    ly = math.log(clamp(y, 0.08, 1.0))
    z = (L + c0 + A * lx + B * ly + C * lx * ly + d1 * L * lx + d2 * L * ly + d3 * L * lx * ly
         + d4 * lx * lx + d5 * L * lx * lx + d6 * ly * ly)
    return sigmoid(z)


def _ie(st, bk, L, y, a, b):
    if b - a < 0.04:
        b = min(1.0, a + 0.04)
        a = b - 0.04
    eb = _re(st, bk, L, y, b)
    if a < 0.002:
        return eb
    ea = _re(st, bk, L, y, a)
    return clamp((b * eb - a * ea) / (b - a), 0.0, 1.0)


def re_val(hole, board, y, x):
    st, bk, _, L = post_ctx(hole, board)
    return _re(st, bk, L, y, x)


def ie_val(hole, board, y, a, b):
    st, bk, _, L = post_ctx(hole, board)
    return _ie(st, bk, L, y, a, b)


# ----------------------------------------------------------------- stats (SPEC 3, 4)
def rates(c):
    def r(num, den, prior, w=6.0):
        return (num + prior * w) / (den + w)
    return {
        "vpip": r(c["vpip"], c["hands"], 0.35),
        "pfr": r(c["pfr"], c["hands"], 0.18),
        "shove": r(c["shove"], c["hands"], 0.06),
        "ftb": r(c["folded"], c["faced"], 0.45),
        "agg": r(c["aggr"], c["aggr"] + c["passive"], 0.45),
        "bet": r(c["bets"], c["bet_opp"], 0.40),
        "raise": r(c["raised"], c["faced"], 0.12),
        "fold_nb": r(c["folded"] - c["folded_ab"], c["faced"] - c["faced_ab"], 0.35),
        "fold_ab": r(c["folded_ab"], c["faced_ab"], 0.15),
    }


def lam_kind(counters):
    """(lam, kind) for one seat's counters (missing keys count as 0)."""
    c = dict.fromkeys(COUNTERS, 0)
    c.update(counters)
    r = rates(c)
    z = 16.0915 + sum(r[k] * (a + b * r[k]) for k, (a, b) in LAM_COEF.items())
    if c["hands"] == 0 or z < -30:
        lam = 0.0
    else:
        lam = c["hands"] / (c["hands"] + 15.0) * sigmoid(z)
    acts = c["acts"]
    if acts >= 5 and (c["allin"] >= 0.9 * acts or c["minr"] >= 0.75 * acts):
        kind = 2
    elif c["hands"] >= 8 and c["vpip"] == 0 and c["aggr"] == 0 and c["passive"] == 0:
        kind = 1
    else:
        kind = 0
    return lam, kind


def _n_alive(o):
    return sum(1 for s in range(len(o.stacks)) if o.stacks[s] + o.bets[s] > 0 or o.in_hand[s])


def _need(o, me, v, p):
    """Equity needed to call (SPEC 0)."""
    c = o.to_call
    total = sum(o.stacks) + max(o.pot, sum(o.bets))
    mine = o.stacks[me] + o.bets[me]
    theirs = o.stacks[v] + o.bets[v]
    eff = min(mine, theirs)
    if total > 0 and eff > 0:
        bf = 1.0 + p["icm_weight"] * (BF(_n_alive(o), mine / total, theirs / total, c / eff) - 1.0)
    else:
        bf = 1.0
    return bf * c / max(bf * c + o.pot, 1)


# ----------------------------------------------------------------- the bot
class SpecBot:
    def __init__(self):
        self.seat = 0
        self.n_seats = 0
        self.stats = {}
        self._key = None
        self._last_hist = None
        self._done = set()
        self.last_error = None
        self.time_budget = 0.0006

    # --- lifecycle
    def new_table(self, seat, n_seats):
        self.seat = seat
        self.n_seats = n_seats
        self._reset()
        gc.collect()

    def _reset(self):
        self.stats = {}
        self._key = None
        self._last_hist = None
        self._done = set()

    def _c(self, s):
        c = self.stats.get(s)
        if c is None:
            c = dict.fromkeys(COUNTERS, 0)
            self.stats[s] = c
        return c

    def _rt(self, s):
        return rates(self._c(s))

    # --- ingestion (SPEC 3)
    def observe(self, event):
        try:
            kind, data = event
            if kind == "hand_end" and data.get("history") is not None:
                self._ingest_once(data.get("hand_no"), data["history"])
        except Exception as exc:  # never let stats break play
            self.last_error = exc

    def _ingest_once(self, hand_no, history):
        if hand_no in self._done:
            return
        self._done.add(hand_no)
        self._ingest(history)

    def _ingest(self, history):
        street = -1
        bets = {}
        aggr_set = set()
        bb = 1
        inc = 1
        n_r = 0
        opener = -1
        acted0 = set()
        seen = set()
        vp = set()
        pr = set()
        sh = set()
        for seat, st, kind, amt, all_in in history:
            seen.add(seat)
            if st != street:
                street = st
                bets = {}
                aggr_set = set()
                inc = bb
            cur = max(bets.values()) if bets else 0
            prev = bets.get(seat, 0)
            if kind == POST:
                bets[seat] = amt
                if amt > bb:
                    bb = inc = amt
                continue
            c = self._c(seat)
            c["acts"] += 1
            if all_in:
                c["allin"] += 1
            if kind == RAISE:
                if amt - cur > inc:
                    inc = amt - cur
                elif not all_in:
                    c["minr"] += 1
            if st == 0:
                if n_r == 0 and kind == RAISE and not all_in:
                    opener = seat
                if n_r == 1 and opener >= 0 and seat != opener and seat not in acted0:
                    c["fs_n"] += 1
                    if kind == FOLD:
                        c["fs_f"] += 1
                    elif kind == RAISE:
                        c["fs_r"] += 1
                acted0.add(seat)
                if kind == RAISE:
                    n_r += 1
                    vp.add(seat)
                    pr.add(seat)
                    if all_in:
                        sh.add(seat)
                elif kind == CALL and amt > prev:
                    vp.add(seat)
            else:
                if cur > prev:
                    c["faced"] += 1
                    if seat in aggr_set:
                        c["faced_ab"] += 1
                    if kind == FOLD:
                        c["folded"] += 1
                        if seat in aggr_set:
                            c["folded_ab"] += 1
                    elif kind == RAISE:
                        c["raised"] += 1
                else:
                    c["bet_opp"] += 1
                    if kind == RAISE:
                        c["bets"] += 1
                if kind == RAISE:
                    c["aggr"] += 1
                    aggr_set.add(seat)
                elif kind == CALL and amt > prev:
                    c["passive"] += 1
            if kind in (CALL, RAISE):
                bets[seat] = amt
        for seat in seen:
            c = self._c(seat)
            c["hands"] += 1
            if seat in vp:
                c["vpip"] += 1
            if seat in pr:
                c["pfr"] += 1
            if seat in sh:
                c["shove"] += 1

    # --- decision entry point (SPEC 7)
    def act(self, obs):
        t0 = perf_counter()
        o = obs
        try:
            n = len(o.stacks)
            if n != self.n_seats:
                self._reset()
                self.n_seats = n
            key = (o.hand_no, tuple(o.hole))
            if key != self._key:
                if self._key is not None and self._last_hist is not None:
                    self._ingest_once(self._key[0], self._last_hist)
                self._key = key
            self._last_hist = list(o.history)
            res = self._decide(o, t0)
            return self._legal(o, res)
        except Exception as exc:
            self.last_error = exc
            return (CALL, 0) if o.to_call <= 0 else (FOLD, 0)

    @staticmethod
    def _legal(o, a):
        kind, amt = a
        if kind == FOLD:
            return (CALL, 0) if o.to_call <= 0 else (FOLD, 0)
        if kind == RAISE:
            if o.min_raise_to <= 0:
                return (CALL, 0)
            hi = max(o.max_raise_to, o.min_raise_to)
            return (RAISE, int(clamp(amt, o.min_raise_to, hi)))
        return (CALL, 0)

    def _level(self, o, me, opps):
        lam = 1.0
        if o.street == 0:
            hist = o.history
            acted = {h[0] for h in hist if h[2] != POST}
            raisers = {h[0] for h in hist if h[2] == RAISE}
            for s in opps:
                c = self._c(s)
                l_s, k_s = lam_kind(c)
                if s in acted:
                    if s not in raisers:
                        continue
                    x = 1.0 if k_s == 2 else l_s
                else:
                    if o.stacks[s] <= 0:
                        continue
                    if k_s != 0:
                        x = 1.0
                    else:
                        x = 1.0 - (1.0 - l_s) * min(1.0, rates(c)["vpip"])
                lam = min(lam, x)
        else:
            for s in opps:
                l_s, k_s = lam_kind(self._c(s))
                x = 1.0 if k_s == 2 else l_s
                lam = min(lam, x)
        return int(lam * 4 + 0.5)

    def _decide(self, o, t0):
        me = o.seat
        n = len(o.stacks)
        opps = [s for s in range(n) if s != me and o.in_hand[s]]
        if not opps:
            return (CALL, 0)
        level = self._level(o, me, opps)
        p = settings(level)
        if o.street == 0:
            return self._preflop(o, me, opps, p)
        return self._postflop(o, me, opps, p, t0)

    # ------------------------------------------------------------- preflop (SPEC 5)
    @staticmethod
    def _raise_to(o, target):
        if o.min_raise_to <= 0:
            return (CALL, 0)
        amt = max(o.min_raise_to, int(target))
        if amt >= 0.85 * o.max_raise_to:
            amt = o.max_raise_to
        return (RAISE, min(amt, o.max_raise_to))

    @staticmethod
    def _jam(o):
        if o.min_raise_to <= 0:
            return (CALL, 0)
        return (RAISE, o.max_raise_to)

    def _preflop(self, o, me, opps, p):
        n = len(o.stacks)
        hist = o.history
        bb = o.bb
        posts = [h[0] for h in hist if h[2] == POST]
        if len(posts) >= 2:
            bb_seat = posts[1]
        elif len(posts) == 1:
            bb_seat = posts[0]
        else:
            bb_seat = o.button
        dealt = {h[0] for h in hist} | {s for s in range(n) if o.in_hand[s]}
        order = []
        for k in range(1, n + 1):
            s = (bb_seat + k) % n
            if s in dealt:
                order.append(s)
        pos = order.index(me) if me in order else 0
        after = order[pos + 1:]
        my_total = o.stacks[me] + o.bets[me]
        eff_bb = min(my_total, max(o.stacks[s] + o.bets[s] for s in opps)) / bb
        name = hole_name(o.hole)
        pc = _PCT[name]
        raises = [h for h in hist if h[1] == 0 and h[2] == RAISE]
        if eff_bb <= p["pf_bb"]:
            return self._pushfold(o, me, opps, order, pos, after, raises, p, name, pc, eff_bb)
        if not raises:
            return self._open(o, opps, order, pos, after, p, pc, bb)
        return self._vs_raise_deep(o, me, opps, raises, my_total, p, name)

    def _open(self, o, opps, order, pos, after, p, pc, bb):
        hist = o.history
        limpers = sum(1 for h in hist if h[1] == 0 and h[2] == CALL and h[3] > 0)
        if o.to_call == 0:
            if pc <= p["iso_pct"]:
                return self._raise_to(o, 3 * bb + limpers * bb)
            return (CALL, 0)
        behind = [s for s in after if o.in_hand[s] and o.stacks[s] > 0]
        thr = p["open_base"] + (p["open_late"] - p["open_base"]) * (
            1.0 - len(behind) / max(len(order) - 1, 1))
        thr = max(thr, SH_OPEN[min(len(behind), 7)] * 1.15)
        if limpers:
            thr = p["iso_pct"]
        if behind:
            vp = sum(self._rt(s)["vpip"] for s in behind) / len(behind)
            thr = min(1.0, thr * (0.35 / max(vp, 0.05)) ** (0.5 * p["steal_exploit"]))
            if not limpers:
                prod = 1.0
                for s in behind:
                    c = self._c(s)
                    if c["vpip"] > 0 or c["hands"] < 10:
                        prod *= (c["fs_f"] + 6 * 0.8) / (c["fs_n"] + 6)
                if prod >= 0.8 - 1e-9:
                    thr = 1.0
        if pc <= thr:
            return self._raise_to(o, p["open_bb"] * bb + limpers * bb)
        comp = 0.8 if len(order) == 2 else p["sb_complete_pct"]
        if not limpers and o.to_call <= bb // 2 + 1 and pc <= comp:
            return (CALL, 0)
        return (FOLD, 0)

    def _vs_raise_deep(self, o, me, opps, raises, my_total, p, name):
        raiser, rr_all_in = raises[-1][0], raises[-1][4]
        rs = self._rt(raiser)
        y = rs["pfr"] * p["pre_tighten"] ** (len(raises) - 1)
        if rr_all_in:
            y = min(y, 2.5 * rs["shove"])
        y = clamp(y, 0.01, 1.0)
        eq = eqr(name, y)
        n_in = sum(1 for s in opps
                   if any(h[0] == s and h[1] == 0 and h[2] in (CALL, RAISE) for h in o.history))
        n_live = n_in + 0.25 * (len(opps) - n_in)
        if n_live > 1:
            eq = eq ** (1.0 + 0.6 * (n_live - 1))
        if eq >= p["reraise_eq"] and len(raises) < 4 and o.min_raise_to > 0:
            target = max(o.bets) * p["reraise_mult"]
            if target >= 0.35 * my_total:
                return self._jam(o)
            return self._raise_to(o, target)
        if eq * p["pre_realize"] >= _need(o, me, raiser, p):
            return (CALL, 0)
        return (FOLD, 0)

    def _pushfold(self, o, me, opps, order, pos, after, raises, p, name, pc, eff_bb):
        n = len(order)
        if not raises:
            behind = [s for s in after if o.in_hand[s]]
            thr = _shove_chart(n, pos, eff_bb)
            if thr is None:
                thr = clamp(0.9 / (1.0 + 0.35 * len(behind)) * math.sqrt(6.0 / max(eff_bb, 1.0)),
                            0.03, 1.0)
            if behind:
                vp = sum(self._rt(s)["vpip"] for s in behind) / len(behind)
                thr *= (0.35 / max(vp, 0.05)) ** (0.5 * p["pf_exploit"])
            thr = clamp(thr * p["pf_shove_scale"], 0.0, 1.0)
            if o.to_call == 0:
                return self._jam(o) if pc <= 0.6 * thr else (CALL, 0)
            return self._jam(o) if pc <= thr else (FOLD, 0)
        shover = raises[-1][0]
        spos = order.index(shover) if shover in order else -1
        need_pf = _need(o, me, shover, p) + p["pf_margin"]
        t = _call_chart(n, spos, pos, eff_bb)
        c_sh = self._c(shover)
        if t is None or c_sh["hands"] >= 12:
            rs = rates(c_sh)
            y = clamp(1.5 * max(rs["shove"], 0.8 * rs["pfr"]), 0.02, 1.0)
            call = eqr(name, y) >= need_pf
        else:
            call = pc <= t * p["pf_call_scale"]
        if len(opps) > 1:
            call = call and eqr(name, 0.08) >= 0.5
        return self._jam(o) if call else (FOLD, 0)

    # ------------------------------------------------------------- postflop (SPEC 6)
    def _pre_y(self, o, s, p):
        rs = self._rt(s)
        bets = {}
        n = 0
        y = 1.0
        for seat, st, kind, amt, all_in in o.history:
            if st != 0:
                break
            if kind == POST:
                bets[seat] = amt
                continue
            prev = bets.get(seat, 0)
            if kind == RAISE:
                n += 1
                if seat == s:
                    yr = rs["pfr"] * p["pre_tighten"] ** (n - 1)
                    if all_in:
                        yr = min(yr, 2.5 * rs["shove"])
                    y = min(y, yr)
            elif kind == CALL and seat == s and amt > prev:
                y = min(y, rs["vpip"] * p["pre_tighten"] ** max(n - 1, 0))
            if kind in (CALL, RAISE):
                bets[seat] = amt
        return clamp(y * p["rng_y_scale"], 0.02, 1.0)

    def _post_slice(self, o, s, p):
        rs = self._rt(s)
        g_bet = clamp(rs["bet"] * p["rng_bet_scale"], 0.03, 1.0)
        g_raise = clamp(rs["raise"] * p["rng_bet_scale"], 0.02, 1.0)
        cont_s = clamp(1.0 - rs["fold_nb"], 0.05, 1.0)
        a, b = 0.0, 1.0
        street = 0
        bets = {}
        cur = 0
        ag = False
        k = p["rng_persist"]
        for seat, st, kind, amt, _ in o.history:
            if st == 0:
                continue
            if st != street:
                if street > 0:
                    a, b = a * k, 1.0 - (1.0 - b) * k
                street = st
                bets = {}
                cur = 0
            prev = bets.get(seat, 0)
            if seat == s:
                w = b - a
                if kind == RAISE:
                    b = a + w * (g_raise if cur > prev else g_bet)
                    ag = (st == o.street)
                elif kind == CALL:
                    if cur > prev:
                        a, b = (a + w * g_raise * p["rng_call_cut"],
                                a + w * max(cont_s, g_raise))
                    else:
                        a = a + w * g_bet * p["rng_check_cap"]
            if kind == RAISE:
                cur = amt
            if kind in (CALL, RAISE):
                bets[seat] = amt
        if street > 0 and street != o.street:
            a, b = a * k, 1.0 - (1.0 - b) * k
        return a, b, ag

    def _postflop(self, o, me, opps, p, t0):
        hole = list(o.hole)
        board = list(o.board)
        st = o.street
        bk, grp = _bucket(hole, board)
        e1 = _e1_post(hole, board, st, bk, grp)
        L = logit(e1)
        real = 1.0 if st == 3 else p["realize"]

        rng = {}
        for s in opps:
            y = self._pre_y(o, s, p)
            a, b, ag = self._post_slice(o, s, p)
            rng[s] = (y, a, b, ag)

        n = len(opps)
        corr = 1.0
        if n > 1:
            K = n ** 0.88 if n <= 3 else 3 ** 0.88 * n / 3.0
            corr = e1 ** ((K - n) / n)

        def eq_vs(s, f=1.0):
            y, a, b, _ = rng[s]
            return min(1.0, _ie(st, bk, L, y, a, a + (b - a) * f) * corr)

        W_now = 1.0
        for s in opps:
            W_now *= eq_vs(s) * real

        P = o.pot
        mine = o.stacks[me] + o.bets[me]
        total = sum(o.stacks) + max(P, sum(o.bets))
        n_alive = _n_alive(o)
        big = max(opps, key=lambda s: o.stacks[s] + o.bets[s])
        theirs = o.stacks[big] + o.bets[big]
        eff = max(min(mine, theirs), 1)
        ra = p["risk_av"] * min(1.0, mine / o.bb / p["risk_depth"])

        def bfw(risk):
            if risk <= 0 or total <= 0:
                return 1.0
            return ((1.0 + ra * min(risk / max(mine, 1), 1.0)) ** 2
                    * (1.0 + p["icm_weight"] * (
                        BF(n_alive, mine / total, theirs / total, risk / eff) - 1.0)))

        def cont(s, po):
            _, _, _, ag_s = rng[s]
            rs = self._rt(s)
            _, a_s, b_s, _ = rng[s]
            c0 = clamp(1.0 - (rs["fold_ab"] if ag_s else rs["fold_nb"]), 0.01, 0.99)
            z = (p["cont_b0"] + p["cont_b1"] * logit(c0)
                 + p["cont_b2"] * math.log(max(po, 0.01) / PO_REF)
                 + p["cont_b3"] * (1.0 if ag_s else 0.0)
                 + p["cont_b4"] * (a_s + b_s) / 2.0)
            return sigmoid(z)

        facing = o.to_call > 0
        cmul = p["raise_cont"] if facing else 1.0

        def ev_raise(R):
            R = min(R, max(o.stacks[s] + o.bets[s] for s in opps))
            A = max(R - o.bets[me], 0)
            pot_after = P + A
            W = 1.0
            parts = []
            for s in opps:
                d = max(min(R, o.stacks[s] + o.bets[s]) - o.bets[s], 0)
                if d <= 0 or o.stacks[s] == 0:
                    c = 1.0
                else:
                    c = clamp(cont(s, d / max(pot_after + d, 1)) * cmul, 0.02, 1.0)
                q = eq_vs(s, min(1.0, c * p["call_width"])) * real
                w = (1.0 - c) + c * q
                W *= w
                parts.append((c * q * d, w))
            gain = P * W + sum(cqd * W / max(w, 1e-9) for cqd, w in parts)
            return gain - A * (1.0 - W) * bfw(A)

        if not facing:
            best = (CALL, 0)  # check
            best_ev = P * W_now * p["realize_chk"] + p["ev_margin"] * P
            targets = [o.bets[me] + f * P for f in POST_SIZES]
        else:
            A = min(o.to_call, o.stacks[me])
            ev_call = P * W_now - A * (1.0 - W_now) * bfw(A) - p["call_ev_margin"] * A
            if ev_call > 0:
                best, best_ev = (CALL, 0), ev_call
            else:
                best, best_ev = (FOLD, 0), 0.0
            targets = [max(o.bets) + f * (P + o.to_call) for f in RAISE_SIZES]

        if o.min_raise_to > 0:
            tried = set()
            for R in targets + [o.max_raise_to]:
                if perf_counter() - t0 > self.time_budget:
                    break
                R = int(clamp(R, o.min_raise_to, o.max_raise_to))
                if R >= 0.85 * o.max_raise_to:
                    R = o.max_raise_to
                if R in tried:
                    continue
                tried.add(R)
                ev = ev_raise(R)
                if ev > best_ev:
                    best_ev = ev
                    best = (RAISE, R)
        return best

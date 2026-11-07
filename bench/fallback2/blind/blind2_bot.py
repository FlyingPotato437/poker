import gc
import math
from math import exp, log, sqrt
from time import perf_counter

gc.collect()
gc.freeze()
gc.disable()

FOLD, CALL, RAISE, POST = 0, 1, 2, 3


def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def sigmoid(z):
    z = clamp(z, -60.0, 60.0)
    return 1.0 / (1.0 + exp(-z))


def logit(p):
    p = clamp(p, 1e-4, 1 - 1e-4)
    return log(p / (1 - p))


# ---------------------------------------------------------------- tables
HAND_ORDER = """AA KK QQ JJ TT 99 88 AKs 77 AQs AJs AKo AQo ATs AJo KQs 66 A9s KJs ATo A8s KTs KQo A9o
A7s QJs KJo 55 K9s A6s A5s KTo QTs A8o A4s A7o A3s K8s QJo K9o A5o K7s A6o JTs Q9s QTo
A2s 44 K6s A4o Q8s A3o K8o K5s K7o J9s Q9o A2o JTo K4s Q7s K6o T9s J8s K3s Q6s K5o Q8o
33 J9o K2s Q5s J7s K4o T8s Q4s Q7o K3o J8o T9o T7s Q6o 98s Q3s J6s K2o 22 J5s Q2s Q5o
J7o Q4o T8o J4s T6s 97s Q3o J3s 98o T7o 87s J6o 96s J2s Q2o J5o T5s J4o T4s 86s 97o T6o
95s T3s J3o 76s 87o T2s 85s J2o T5o 96o 94s 75s T4o 86o 93s 65s 84s T3o 95o 92s 76o 74s
54s T2o 85o 64s 83s 94o 82s 75o 65o 93o 73s 53s 63s 84o 92o 43s 74o 72s 54o 64o 52s 62s
83o 82o 42s 73o 53o 63o 32s 43o 72o 52o 62o 42o 32o""".split()
E1 = """85 82 80 77 75 72 69 67 66 66 65 65 64 65 64 63 63 63 63 63 62 62 61 61 61 60 61 60 60
60 60 60 59 60 59 59 58 58 58 58 58 58 58 58 58 57 57 57 57 57 56 56 56 56 55 56 55 55
55 55 54 54 54 54 54 54 53 54 54 53 53 53 52 52 52 52 52 51 52 52 51 51 51 51 51 50 50
50 50 50 50 49 50 49 49 49 48 48 48 48 48 48 47 47 47 47 47 46 47 46 46 46 46 46 45 45
45 45 45 44 44 44 44 44 44 43 43 43 43 43 43 42 42 42 42 42 41 41 41 41 40 40 40 40 40
40 39 39 39 39 39 38 38 38 38 38 38 37 37 37 36 36 36 35 35 34 34 33 32""".split()
assert len(HAND_ORDER) == 169 and len(E1) == 169

PCT = {}
E1H = {}
_cum = 0
for _h, _e in zip(HAND_ORDER, E1):
    _cum += 6 if len(_h) == 2 and _h[0] == _h[1] else (4 if _h.endswith("s") else 12)
    PCT[_h] = _cum / 1326.0
    E1H[_h] = int(_e) / 100.0

EQR = [
    (0.03, -0.950, 0.629, -0.497, -0.971, -0.110), (0.06, -0.821, 0.350, -0.078, -0.657, -0.057),
    (0.10, -0.682, 0.215, 0.025, -0.554, -0.077), (0.15, -0.572, 0.182, 0.036, -0.480, -0.118),
    (0.20, -0.548, 0.218, 0.030, -0.438, -0.114), (0.30, -0.549, 0.430, 0.019, -0.344, -0.010),
    (0.45, -0.488, 0.793, -0.048, -0.206, 0.227), (0.65, -0.308, 1.056, -0.091, -0.078, 0.551),
    (1.00, 0.000, 1.000, 0.000, 0.000, 0.000)]

BF_FULL = {2: 1.00, 3: 1.41, 4: 1.57, 5: 1.64, 6: 1.73, 7: 1.75, 8: 1.76}
BF_SHARE = [[0.41, 0.53, 0.81],
            [0.29, 1.00, 1.49],
            [0.15, 0.44, 2.36]]

PF_STACKS = [2, 3, 4, 5, 6, 8, 10, 12, 15, 18, 21]


def _row(s):
    return [float(x) / 100.0 for x in s.split()]


_SHOVE_RAW = {
    2: "90 78 74 74 70 65 59 54 48 41 37",
    3: "36 49 51 49 46 44 40 34 28 25 21 | 67 77 78 77 75 69 64 63 57 52 47",
    4: "34 45 42 43 41 36 29 25 21 19 16 | 38 51 52 52 54 50 45 39 32 24 22 | 68 80 85 84 86 82 82 73 68 62 62",
    5: "31 37 38 37 33 26 24 21 17 15 13 | 33 43 44 46 43 39 29 27 22 21 17 | 37 51 51 53 54 53 48 41 32 26 26 | 69 83 87 87 88 87 86 82 76 71 66",
    6: "28 32 33 27 26 23 18 17 15 14 14 | 30 37 39 38 33 27 24 20 17 16 15 | 34 43 44 46 44 38 31 28 25 22 18 | 37 50 53 55 56 54 54 42 34 28 26 | 70 83 87 88 94 95 90 91 83 80 67",
    7: "26 28 26 23 24 18 17 15 14 13 12 | 28 31 32 27 26 23 19 17 15 14 14 | 30 36 37 38 34 27 23 21 18 16 15 | 33 42 44 46 44 38 31 28 24 24 19 | 36 49 54 56 57 54 54 43 37 27 27 | 69 84 87 91 96 97 91 92 84 82 69",
    8: "22 24 22 23 19 17 15 14 14 12 8 | 25 28 26 25 25 18 18 15 15 14 13 | 28 32 33 27 27 23 20 19 15 15 15 | 30 36 39 39 33 29 25 22 19 16 16 | 33 43 46 46 47 37 32 28 26 22 20 | 37 49 54 58 60 56 55 50 37 30 31 | 71 85 91 95 97 100 95 97 89 83 75",
}
SHOVE = {n: [_row(r) for r in s.split("|")] for n, s in _SHOVE_RAW.items()}

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
CALLCH = {k: _row(v) for k, v in _CALL_RAW.items()}


def chart_interp(row, eff_bb):
    if eff_bb <= PF_STACKS[0]:
        return row[0]
    if eff_bb >= PF_STACKS[-1]:
        return row[-1]
    for i in range(len(PF_STACKS) - 1):
        x0, x1 = PF_STACKS[i], PF_STACKS[i + 1]
        if x0 <= eff_bb <= x1:
            t = (eff_bb - x0) / (x1 - x0)
            return row[i] * (1 - t) + row[i + 1] * t
    return row[-1]


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

_SETTINGS_RAW = """open_base 0.2643 0.2654
open_late 0.4262 0.4165
open_bb 2.965 2.842
steal_exploit 2.031 1.752
iso_pct 0.1030 0.1541
sb_complete_pct 0.7267 0.7694
reraise_eq 0.5884 0.6112
reraise_mult 3.221 2.903
pre_realize 0.9222 0.9486
pre_tighten 0.4378 0.4141
pf_bb 21.09 16.54
pf_shove_scale 1.167 1.087
pf_call_scale 1.348 1.384
pf_exploit 1.609 1.325
pf_margin 0.01941 0.02509
icm_weight 0.9605 0.8630
realize 0.8195 0.8219
realize_chk 0.8665 0.8811
ev_margin 0.04654 0.03703
call_ev_margin 0.08401 0.07154
risk_av 1.032 1.228
risk_depth 28.24 26.98
raise_cont 0.9975 1.072
call_width 1.445 1.415
cont_b0 1.035 1.175
cont_b1 1.633 1.713
cont_b2 -1.784 -1.766
cont_b3 -0.267 -0.3887
cont_b4 -2.719 -2.337
rng_y_scale 2.126 1.834
rng_bet_scale 1.556 1.590
rng_check_cap 0.6540 0.3317
rng_call_cut 0.9865 0.9073
rng_persist 0.3338 0.3326"""
SETTINGS = {}
for _l in _SETTINGS_RAW.split("\n"):
    _n, _b, _x = _l.split()
    SETTINGS[_n] = (float(_b), float(_x))
LEVELS = []
for _L in range(5):
    LEVELS.append({k: b + (_L / 4.0) * (x - b) for k, (b, x) in SETTINGS.items()})

SH_OPEN = (0.50, 0.50, 0.42, 0.28, 0.23, 0.19, 0.16, 0.14)
POST_SIZES = (0.33, 0.66, 1.0, 1.5)
RAISE_SIZES = (0.8, 1.3)
PO_REF = 0.65 / 2.3

RCH = "23456789TJQKA"


def hand_name(hole):
    r = sorted([c // 4 + 2 for c in hole], reverse=True)
    s = [c % 4 for c in hole]
    if r[0] == r[1]:
        return RCH[r[0] - 2] * 2
    return RCH[r[0] - 2] + RCH[r[1] - 2] + ("s" if s[0] == s[1] else "o")


# ---------------------------------------------------------------- equity
def eqr_from(pct, e1, pair, y):
    y = clamp(y, 0.03, 1.0)
    r = log(clamp(pct / y, 0.05, 20.0))
    L = logit(e1)

    def zrow(row):
        return row[1] + row[2] * L + row[3] * pair + row[4] * min(r, 0.0) + row[5] * max(r, 0.0)

    if y <= 0.03:
        return sigmoid(zrow(EQR[0]))
    for i in range(len(EQR) - 1):
        if EQR[i][0] < y <= EQR[i + 1][0]:
            t = (y - EQR[i][0]) / (EQR[i + 1][0] - EQR[i][0])
            z = zrow(EQR[i]) * (1 - t) + zrow(EQR[i + 1]) * t
            return sigmoid(z)
    return sigmoid(zrow(EQR[-1]))


def eqr(hand, y):
    return eqr_from(PCT[hand], E1H[hand], 1 if hand[0] == hand[1] else 0, y)


def BF(n, hs, vs, risk):
    if n < 2:
        return 1.0

    def cls(x):
        if x < 0.7 / n:
            return 0
        if x > 1.4 / n:
            return 2
        return 1

    return 1 + (BF_FULL[min(n, 8)] - 1) * BF_SHARE[cls(hs)][cls(vs)] * clamp(risk, 0, 1) ** 1.2


def has_straight(rs):
    s = set(rs)
    if 14 in s:
        s.add(1)
    for hi in range(14, 4, -1):
        if all((hi - i) in s for i in range(5)):
            return True
    return False


def category(cards):
    ranks = [c // 4 + 2 for c in cards]
    suits = [c % 4 for c in cards]
    cnt = {}
    for r in ranks:
        cnt[r] = cnt.get(r, 0) + 1
    vals = sorted(cnt.values(), reverse=True)
    flush = False
    for su in range(4):
        rs = set(r for r, s in zip(ranks, suits) if s == su)
        n_su = sum(1 for s in suits if s == su)
        if n_su >= 5:
            flush = True
            if has_straight(rs):
                return 6
    if vals[0] >= 4:
        return 6
    if vals[0] == 3 and len(vals) > 1 and vals[1] >= 2:
        return 6
    if flush:
        return 5
    if has_straight(set(ranks)):
        return 4
    if vals[0] == 3:
        return 3
    if vals[0] == 2 and len(vals) > 1 and vals[1] == 2:
        return 2
    if vals[0] == 2:
        return 1
    return 0


BUCKET_GROUP = {12: 3, 11: 3, 10: 3, 9: 3, 8: 3, 7: 2, 6: 2, 5: 2, 4: 1, 3: 1, 2: 0, 1: 0, 0: 0}


def bucket_of(hole, board):
    hr = sorted([c // 4 + 2 for c in hole], reverse=True)
    br = [c // 4 + 2 for c in board]
    brset = set(br)
    top = max(br)
    cat = category(list(hole) + list(board))
    bcat = category(list(board)) if len(board) >= 3 else 0
    if cat >= 6 and bcat < 6:
        return 12
    if cat == 5 and bcat < 5:
        return 11
    if cat == 4 and bcat < 4:
        return 10
    allr = hr + br
    if cat in (3, 6) and any(allr.count(r) >= 3 for r in hr):
        return 9
    distinct_hr = []
    for r in hr:
        if r not in distinct_hr:
            distinct_hr.append(r)
    paired = [r for r in distinct_hr if r in brset]
    if len(paired) == 2:
        return 8
    strong = weak = False
    if len(board) in (3, 4):
        suits = [c % 4 for c in list(hole) + list(board)]
        hsuits = [c % 4 for c in hole]
        for su in range(4):
            if suits.count(su) >= 4 and su in hsuits:
                strong = True
        hbr = set(allr)
        outs = 0
        for x in range(2, 15):
            if x in hbr:
                continue
            if has_straight(hbr | {x}) and not has_straight(brset | {x}):
                outs += 1
        if outs >= 2:
            strong = True
        if not strong and (outs == 1 or (hr[0] > top and hr[1] > top)):
            weak = True
    pocket = hr[0] == hr[1]
    if pocket and hr[0] > top:
        return 7
    if paired:
        r = paired[0]
        if r == top:
            kicker = r if pocket else (hr[1] if hr[0] == r else hr[0])
            return 6 if kicker >= 10 else 5
        return 4 if strong else 3
    if pocket:
        return 4 if strong else 3
    if strong:
        return 2
    if weak:
        return 1
    return 0


def features(hole, board):
    hr = sorted([c // 4 + 2 for c in hole], reverse=True)
    br = [c // 4 + 2 for c in board]
    bsuits = [c % 4 for c in board]
    u = sorted(set(br))
    fb = 1 if any(bsuits.count(s) >= 3 for s in range(4)) else 0
    cb = 1 if any(u[i + 2] - u[i] <= 4 for i in range(len(u) - 2)) else 0
    pb = 1 if len(u) < len(br) else 0
    top = (max(br) - 8) / 6.0
    mine = hr[0]
    for r in hr:
        if r in u:
            mine = r
            break
    over = min(sum(1 for r in u if r > mine), 2) / 2.0
    fdn = 0
    for s in range(4):
        if bsuits.count(s) >= 2 and any(c == 12 * 4 + s for c in hole):
            fdn = 1
    fb4 = 1 if any(bsuits.count(s) >= 4 for s in range(4)) else 0
    uu = ([1] + u) if 14 in u else u
    sb4 = 1 if any(uu[i + 3] - uu[i] <= 4 for i in range(len(uu) - 3)) else 0
    return ((hr[0] - 8) / 6.0, (hr[1] - 8) / 6.0, fb, cb, pb, top, (mine - 8) / 6.0, over, fdn, fb4, sb4)


def post_e1(hole, board, street):
    b = bucket_of(hole, board)
    f = features(hole, board)
    I, *W = POST_E1[street]
    w = W[BUCKET_GROUP[b]]
    e1 = clamp(I[b] + sum(x * y for x, y in zip(w, f)), 0.02, 0.99)
    return b, e1


def RE(street, bucket, e1, y, x):
    L = logit(e1)
    lx = log(clamp(x, 0.05, 1.0))
    ly = log(clamp(y, 0.08, 1.0))
    (c0, d1, d2, d3, d4, d5, d6), rows = CURVE[street]
    A, B, C = rows[bucket]
    z = (L + c0 + A * lx + B * ly + C * lx * ly + d1 * L * lx + d2 * L * ly + d3 * L * lx * ly
         + d4 * lx * lx + d5 * L * lx * lx + d6 * ly * ly)
    return sigmoid(z)


def IE(street, bucket, e1, y, a, b):
    if b - a < 0.04:
        b = min(1.0, a + 0.04)
        a = b - 0.04
    eb = RE(street, bucket, e1, y, b)
    if a < 0.002:
        return eb
    ea = RE(street, bucket, e1, y, a)
    return clamp((b * eb - a * ea) / (b - a), 0.0, 1.0)


# ---------------------------------------------------------------- stats
COUNTERS = "hands vpip pfr shove faced folded raised faced_ab folded_ab bet_opp bets aggr passive acts allin minr fs_n fs_f fs_r".split()

LAM_COEF = [("vpip", -42.0452, 77.96), ("pfr", -1.6526, -27.8091), ("agg", 5.9021, -3.169),
            ("fold_to_bet", -16.0593, 6.8088), ("shove", 11.7009, 26.4823), ("bet", -10.378, 1.5881),
            ("fold_nb", -8.5967, 9.9044)]


class Seat:
    def __init__(self):
        for c in COUNTERS:
            setattr(self, c, 0)

    def _r(self, num, den, prior):
        return (num + prior * 6.0) / (den + 6.0)

    def rate(self, name):
        if name == "vpip":
            return self._r(self.vpip, self.hands, 0.35)
        if name == "pfr":
            return self._r(self.pfr, self.hands, 0.18)
        if name == "shove":
            return self._r(self.shove, self.hands, 0.06)
        if name == "fold_to_bet":
            return self._r(self.folded, self.faced, 0.45)
        if name == "agg":
            return self._r(self.aggr, self.aggr + self.passive, 0.45)
        if name == "bet":
            return self._r(self.bets, self.bet_opp, 0.40)
        if name == "raise":
            return self._r(self.raised, self.faced, 0.12)
        if name == "fold_nb":
            return self._r(self.folded - self.folded_ab, self.faced - self.faced_ab, 0.35)
        if name == "fold_ab":
            return self._r(self.folded_ab, self.faced_ab, 0.15)
        raise KeyError(name)

    def lam(self):
        if self.hands == 0:
            return 0.0
        z = 16.0915
        for name, a, b in LAM_COEF:
            r = self.rate(name)
            z += r * (a + b * r)
        if z < -30:
            return 0.0
        return self.hands / (self.hands + 15.0) * sigmoid(z)

    def kind(self):
        if self.acts >= 5 and (self.allin >= 0.9 * self.acts or self.minr >= 0.75 * self.acts):
            return 2
        if self.hands >= 8 and self.vpip == 0 and self.aggr == 0 and self.passive == 0:
            return 1
        return 0


def ingest_history(seats, history):
    street = -1
    bets = {}
    aggr_set = set()
    bb = inc = 1
    n_r = 0
    opener = -1
    acted0 = set()
    seen, vp, pr, sh = set(), set(), set(), set()
    for (seat, st, kind, amt, all_in) in history:
        seen.add(seat)
        S = seats.setdefault(seat, Seat())
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
        S.acts += 1
        if all_in:
            S.allin += 1
        if kind == RAISE:
            if amt - cur > inc:
                inc = amt - cur
            elif not all_in:
                S.minr += 1
        if st == 0:
            if n_r == 0 and kind == RAISE and not all_in:
                opener = seat
            if n_r == 1 and opener >= 0 and seat != opener and seat not in acted0:
                S.fs_n += 1
                if kind == FOLD:
                    S.fs_f += 1
                elif kind == RAISE:
                    S.fs_r += 1
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
                S.faced += 1
                if seat in aggr_set:
                    S.faced_ab += 1
                if kind == FOLD:
                    S.folded += 1
                    if seat in aggr_set:
                        S.folded_ab += 1
                elif kind == RAISE:
                    S.raised += 1
            else:
                S.bet_opp += 1
                if kind == RAISE:
                    S.bets += 1
            if kind == RAISE:
                S.aggr += 1
                aggr_set.add(seat)
            elif kind == CALL and amt > prev:
                S.passive += 1
        if kind == CALL or kind == RAISE:
            bets[seat] = amt
    for s in seen:
        S = seats.setdefault(s, Seat())
        S.hands += 1
        S.vpip += 1 if s in vp else 0
        S.pfr += 1 if s in pr else 0
        S.shove += 1 if s in sh else 0


# ---------------------------------------------------------------- bot
class SpecBot:
    def __init__(self):
        gc.collect()
        self.seat = 0
        self.n_seats = 8
        self.reset()

    def reset(self):
        self.seats = {}
        self.last_key = None
        self.last_hist = None
        self.last_hand_no = None
        self.ingested = set()

    def new_table(self, seat, n_seats):
        self.seat = seat
        self.n_seats = n_seats
        self.reset()
        gc.collect()

    def S(self, s):
        x = self.seats.get(s)
        if x is None:
            x = self.seats[s] = Seat()
        return x

    def observe(self, event):
        try:
            kind, info = event
            if kind == "hand_end":
                hn = info.get("hand_no")
                if hn in self.ingested:
                    return
                h = info.get("history")
                if h is not None:
                    ingest_history(self.seats, [tuple(e) for e in h])
                    self.ingested.add(hn)
        except Exception:
            pass

    # ------------------------------------------------------------ act
    def act(self, obs):
        try:
            return self.legal(obs, self.decide(obs))
        except Exception:
            return (CALL, 0) if obs.to_call <= 0 else (FOLD, 0)

    def legal(self, o, a):
        kind, amt = a
        if kind == FOLD:
            return (CALL, 0) if o.to_call <= 0 else (FOLD, 0)
        if kind == RAISE:
            if o.min_raise_to <= 0:
                return (CALL, 0)
            amt = int(clamp(amt, o.min_raise_to, max(o.max_raise_to, o.min_raise_to)))
            return (RAISE, amt)
        return (CALL, 0)

    def decide(self, o):
        if len(o.stacks) != self.n_seats:
            self.n_seats = len(o.stacks)
            self.reset()
        key = (o.hand_no, tuple(o.hole))
        if key != self.last_key:
            if self.last_key is not None and self.last_hist is not None \
                    and self.last_hand_no not in self.ingested:
                ingest_history(self.seats, self.last_hist)
                self.ingested.add(self.last_hand_no)
            self.last_key = key
        self.last_hist = [tuple(e) for e in o.history]
        self.last_hand_no = o.hand_no
        self.o = o
        self.me = o.seat
        self.n = len(o.stacks)
        self.opps = [s for s in range(self.n) if s != self.me and o.in_hand[s]]
        self.p = LEVELS[self.level(o)]
        if o.street == 0:
            return self.preflop(o)
        return self.postflop(o)

    # ------------------------------------------------------------ level
    def level(self, o):
        lam = 1.0
        if o.street == 0:
            acted = set(e[0] for e in o.history if e[2] != POST)
            raisers = set(e[0] for e in o.history if e[2] == RAISE)
            for s in self.opps:
                S = self.S(s)
                if s in acted:
                    if s not in raisers:
                        continue
                    x = 1.0 if S.kind() == 2 else S.lam()
                else:
                    if o.stacks[s] <= 0:
                        continue
                    if S.kind() != 0:
                        x = 1.0
                    else:
                        x = 1 - (1 - S.lam()) * min(1.0, S.rate("vpip"))
                lam = min(lam, x)
        else:
            for s in self.opps:
                S = self.S(s)
                x = 1.0 if S.kind() == 2 else S.lam()
                lam = min(lam, x)
        return int(lam * 4 + 0.5)

    # ------------------------------------------------------------ helpers
    def raise_to(self, target):
        o = self.o
        if o.min_raise_to <= 0:
            return (CALL, 0)
        amt = max(o.min_raise_to, int(target))
        if amt >= 0.85 * o.max_raise_to:
            amt = o.max_raise_to
        return (RAISE, min(amt, o.max_raise_to))

    def jam(self):
        o = self.o
        if o.min_raise_to <= 0:
            return (CALL, 0)
        return (RAISE, o.max_raise_to)

    def n_alive(self, o):
        return sum(1 for s in range(self.n) if o.stacks[s] + o.bets[s] > 0 or o.in_hand[s])

    def need(self, o, v):
        p = self.p
        me = self.me
        c = o.to_call
        n_alive = self.n_alive(o)
        total = sum(o.stacks) + max(o.pot, sum(o.bets))
        mine = o.stacks[me] + o.bets[me]
        theirs = o.stacks[v] + o.bets[v]
        eff = min(mine, theirs)
        if total > 0 and eff > 0:
            bf = 1 + p["icm_weight"] * (BF(n_alive, mine / total, theirs / total, c / eff) - 1)
        else:
            bf = 1.0
        return bf * c / max(bf * c + o.pot, 1)

    # ------------------------------------------------------------ preflop
    def preflop(self, o):
        p = self.p
        me = self.me
        n = self.n
        opps = self.opps
        if not opps:
            return (CALL, 0)
        hand = hand_name(o.hole)
        pct = PCT[hand]
        hist = [e for e in o.history if e[1] == 0]
        posts = [e[0] for e in hist if e[2] == POST]
        if len(posts) >= 2:
            bb_seat = posts[1]
        elif len(posts) == 1:
            bb_seat = posts[0]
        else:
            bb_seat = o.button
        dealt = set(e[0] for e in o.history) | set(s for s in range(n) if o.in_hand[s])
        order = [(bb_seat + k) % n for k in range(1, n + 1) if (bb_seat + k) % n in dealt]
        pos = order.index(me) if me in order else 0
        my_total = o.stacks[me] + o.bets[me]
        eff_bb = min(my_total, max(o.stacks[s] + o.bets[s] for s in opps)) / o.bb
        raises = [e for e in hist if e[2] == RAISE]
        if eff_bb <= p["pf_bb"]:
            return self.pushfold(o, hand, pct, order, pos, eff_bb, raises)
        if not raises:
            return self.deep_open(o, hand, pct, order, pos)
        return self.deep_facing(o, hand, pct, raises, hist, my_total)

    def deep_open(self, o, hand, pct, order, pos):
        p = self.p
        me = self.me
        bb = o.bb
        behind = [s for s in order[pos + 1:] if o.in_hand[s] and o.stacks[s] > 0] if me in order else []
        limpers = sum(1 for e in o.history if e[1] == 0 and e[2] == CALL and e[3] > 0)
        if o.to_call == 0:
            if pct <= p["iso_pct"]:
                return self.raise_to(3 * bb + limpers * bb)
            return (CALL, 0)
        thr = p["open_base"] + (p["open_late"] - p["open_base"]) * (1 - len(behind) / max(len(order) - 1, 1))
        thr = max(thr, SH_OPEN[min(len(behind), 7)] * 1.15)
        if limpers:
            thr = p["iso_pct"]
        if behind:
            vp = sum(self.S(s).rate("vpip") for s in behind) / len(behind)
            thr = min(1.0, thr * (0.35 / max(vp, 0.05)) ** (0.5 * p["steal_exploit"]))
            if not limpers:
                prod = 1.0
                for s in behind:
                    S = self.S(s)
                    if S.vpip > 0 or S.hands < 10:
                        prod *= (S.fs_f + 6 * 0.8) / (S.fs_n + 6)
                if prod >= 0.8 - 1e-9:
                    thr = 1.0
        if pct <= thr:
            return self.raise_to(p["open_bb"] * bb + limpers * bb)
        comp = 0.8 if len(order) == 2 else p["sb_complete_pct"]
        if not limpers and o.to_call <= bb // 2 + 1 and pct <= comp:
            return (CALL, 0)
        return (FOLD, 0)

    def deep_facing(self, o, hand, pct, raises, hist, my_total):
        p = self.p
        last = raises[-1]
        raiser = last[0]
        R = self.S(raiser)
        y = R.rate("pfr") * p["pre_tighten"] ** (len(raises) - 1)
        if last[4]:
            y = min(y, 2.5 * R.rate("shove"))
        y = clamp(y, 0.01, 1.0)
        eq = eqr(hand, y)
        inset = set(e[0] for e in hist if e[2] in (CALL, RAISE))
        n_in = sum(1 for s in self.opps if s in inset)
        n_live = n_in + 0.25 * (len(self.opps) - n_in)
        if n_live > 1:
            eq = eq ** (1 + 0.6 * (n_live - 1))
        if eq >= p["reraise_eq"] and len(raises) < 4 and o.min_raise_to > 0:
            target = max(o.bets) * p["reraise_mult"]
            if target >= 0.35 * my_total:
                return self.jam()
            return self.raise_to(target)
        if eq * p["pre_realize"] >= self.need(o, raiser):
            return (CALL, 0)
        return (FOLD, 0)

    def pushfold(self, o, hand, pct, order, pos, eff_bb, raises):
        p = self.p
        me = self.me
        n = len(order)
        if not raises:
            behind = [s for s in order[pos + 1:] if o.in_hand[s]] if me in order else []
            rows = SHOVE.get(n)
            if rows is not None and pos <= n - 2:
                thr = chart_interp(rows[pos], eff_bb)
            else:
                thr = clamp(0.9 / (1 + 0.35 * len(behind)) * sqrt(6 / max(eff_bb, 1)), 0.03, 1.0)
            if behind:
                vp = sum(self.S(s).rate("vpip") for s in behind) / len(behind)
                thr *= (0.35 / max(vp, 0.05)) ** (0.5 * p["pf_exploit"])
            thr = clamp(thr * p["pf_shove_scale"], 0.0, 1.0)
            if o.to_call == 0:
                if pct <= 0.6 * thr:
                    return self.jam()
                return (CALL, 0)
            if pct <= thr:
                return self.jam()
            return (FOLD, 0)
        shover = raises[-1][0]
        SS = self.S(shover)
        spos = order.index(shover) if shover in order else -1
        need_pf = self.need(o, shover) + p["pf_margin"]
        t = None
        if 2 <= n <= 8 and 0 <= spos < pos < n:
            if n == 2:
                key = "hu"
            else:
                K = min(n - 1 - spos, 4)
                J = min(n - 1 - pos, 2)
                key = ("3:%d%d" if n == 3 else "%d%d") % (K, J)
            if key in CALLCH:
                t = chart_interp(CALLCH[key], eff_bb)
        if t is None or SS.hands >= 12:
            y = clamp(1.5 * max(SS.rate("shove"), 0.8 * SS.rate("pfr")), 0.02, 1.0)
            call = eqr(hand, y) >= need_pf
        else:
            call = pct <= t * p["pf_call_scale"]
        if len(self.opps) > 1:
            call = call and eqr(hand, 0.08) >= 0.5
        if call:
            return self.jam()
        return (FOLD, 0)

    # ------------------------------------------------------------ postflop
    def pre_y(self, o, s):
        p = self.p
        S = self.S(s)
        bets = {}
        n = 0
        y = 1.0
        for (seat, st, kind, amt, all_in) in o.history:
            if st != 0:
                break
            if kind == POST:
                bets[seat] = amt
                continue
            prev = bets.get(seat, 0)
            if kind == RAISE:
                n += 1
                if seat == s:
                    yr = S.rate("pfr") * p["pre_tighten"] ** (n - 1)
                    if all_in:
                        yr = min(yr, 2.5 * S.rate("shove"))
                    y = min(y, yr)
            elif kind == CALL and seat == s and amt > prev:
                y = min(y, S.rate("vpip") * p["pre_tighten"] ** max(n - 1, 0))
            if kind == CALL or kind == RAISE:
                bets[seat] = amt
        return clamp(y * p["rng_y_scale"], 0.02, 1.0)

    def post_slice(self, o, s):
        p = self.p
        S = self.S(s)
        g_bet = clamp(S.rate("bet") * p["rng_bet_scale"], 0.03, 1.0)
        g_raise = clamp(S.rate("raise") * p["rng_bet_scale"], 0.02, 1.0)
        cont = clamp(1 - S.rate("fold_nb"), 0.05, 1.0)
        a, b = 0.0, 1.0
        street = 0
        bets = {}
        cur = 0
        ag = False
        k = p["rng_persist"]
        for (seat, st, kind, amt, _) in o.history:
            if st == 0:
                continue
            if st != street:
                if street > 0:
                    a, b = a * k, 1 - (1 - b) * k
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
                        a, b = a + w * g_raise * p["rng_call_cut"], a + w * max(cont, g_raise)
                    else:
                        a = a + w * g_bet * p["rng_check_cap"]
            if kind == RAISE:
                cur = amt
            if kind == CALL or kind == RAISE:
                bets[seat] = amt
        if street > 0 and street != o.street:
            a, b = a * k, 1 - (1 - b) * k
        return a, b, ag

    def postflop(self, o):
        t0 = perf_counter()
        p = self.p
        me = self.me
        opps = self.opps
        if not opps:
            return (CALL, 0)
        st = o.street
        bucket, e1 = post_e1(o.hole, o.board, st)
        n = len(opps)
        corr = 1.0
        if n > 1:
            K = n ** 0.88 if n <= 3 else 3 ** 0.88 * n / 3
            corr = e1 ** ((K - n) / n)
        real = 1.0 if st == 3 else p["realize"]
        info = {}
        for s in opps:
            y = self.pre_y(o, s)
            a, b, ag = self.post_slice(o, s)
            info[s] = (y, a, b, ag)

        def eq_vs(s, f=1.0):
            y, a, b, ag = info[s]
            return min(1.0, IE(st, bucket, e1, y, a, a + (b - a) * f) * corr)

        W_now = 1.0
        for s in opps:
            W_now *= eq_vs(s) * real

        P = o.pot
        bb = o.bb
        total = sum(o.stacks) + max(P, sum(o.bets))
        mine = o.stacks[me] + o.bets[me]
        n_alive = self.n_alive(o)
        big = max(opps, key=lambda s: o.stacks[s] + o.bets[s])
        theirs = o.stacks[big] + o.bets[big]
        eff = max(min(mine, theirs), 1)
        ra = p["risk_av"] * min(1.0, mine / bb / p["risk_depth"])

        def bfw(risk):
            if risk <= 0 or total <= 0:
                return 1.0
            return (1 + ra * min(risk / max(mine, 1), 1.0)) ** 2 * \
                (1 + p["icm_weight"] * (BF(n_alive, mine / total, theirs / total, risk / eff) - 1))

        def cont_p(s, po):
            y, a, b, ag = info[s]
            S = self.S(s)
            c0 = clamp(1 - (S.rate("fold_ab") if ag else S.rate("fold_nb")), 0.01, 0.99)
            z = (p["cont_b0"] + p["cont_b1"] * logit(c0) + p["cont_b2"] * log(max(po, 0.01) / PO_REF)
                 + p["cont_b3"] * (1 if ag else 0) + p["cont_b4"] * (a + b) / 2)
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
                    c = clamp(cont_p(s, d / max(pot_after + d, 1)) * cmul, 0.02, 1.0)
                q = eq_vs(s, min(1.0, c * p["call_width"])) * real
                w = (1 - c) + c * q
                W *= w
                parts.append((c * q * d, w))
            gain = P * W + sum(cqd * W / max(w, 1e-9) for cqd, w in parts)
            return gain - A * (1 - W) * bfw(A)

        if not facing:
            best = (CALL, 0)
            best_ev = P * W_now * p["realize_chk"] + p["ev_margin"] * P
            targets = [o.bets[me] + f * P for f in POST_SIZES]
        else:
            A = min(o.to_call, o.stacks[me])
            best = (FOLD, 0)
            best_ev = 0.0
            ev_call = P * W_now - A * (1 - W_now) * bfw(A) - p["call_ev_margin"] * A
            if ev_call > 0:
                best = (CALL, 0)
                best_ev = ev_call
            targets = [max(o.bets) + f * (P + o.to_call) for f in RAISE_SIZES]
        if o.min_raise_to > 0:
            tried = set()
            for R in targets + [o.max_raise_to]:
                if perf_counter() - t0 > 0.0006:
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

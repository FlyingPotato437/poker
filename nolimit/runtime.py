"""Self-contained bot runtime: variant spec, evaluator, table bundle, features, PrepBot.

This file ships inside the submitted bot (scripts/package_bot.py inlines it), so it
must only depend on the standard library. numpy is used when importable, for the
postflop equity MLP, and everything falls back to pure Python without it.
"""
from __future__ import annotations

import base64
import bisect
import gc
import itertools
import json
import math
import os
import random
import struct
import sys
import time
import zlib
from array import array
from operator import mul as _mul

# Python 3.12+: one C call per dot product. Older Pythons use sum(map(mul, ...)).
_sumprod = getattr(math, "sumprod", None)

# Our matmuls are tiny; a multi-threaded BLAS only adds jitter (measured on a 2.1 GHz Xeon:
# decisions over 1 ms dropped from 16-19 to 4-5 per 34k with one thread). This only takes
# effect if the host hasn't imported numpy before us.
for _var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_var, "1")

try:
    if os.environ.get("NOLIMIT_NO_NUMPY"):
        raise ImportError("numpy disabled by NOLIMIT_NO_NUMPY")
    import numpy as np
    # macOS Accelerate's matmul raises spurious divide/overflow/invalid flags on finite
    # inputs; the warnings machinery then costs time inside decisions. Results are unchanged.
    np.seterr(all="ignore")
except Exception:  # numpy is optional at runtime
    np = None

# ---------------------------------------------------------------------------
# Variant spec
# ---------------------------------------------------------------------------

HIGH, PAIR, TWO_PAIR, TRIPS, STRAIGHT, FLUSH, FULL_HOUSE, QUADS, STRAIGHT_FLUSH, FIVE_KIND = range(10)
N_CATEGORIES = 10
CATEGORY_NAMES = ("high", "pair", "two_pair", "trips", "straight", "flush",
                  "full_house", "quads", "straight_flush", "five_kind")
STANDARD_ORDER = (HIGH, PAIR, TWO_PAIR, TRIPS, STRAIGHT, FLUSH, FULL_HOUSE, QUADS,
                  STRAIGHT_FLUSH, FIVE_KIND)
SUIT_CHARS = "cdhsxyz"


class Variant:
    """Everything about the game that changes hand strength. Betting is always no-limit.

    ranks:           rank characters, lowest first ("6789TJQKA" for short deck)
    suits:           number of suits
    n_hole:          hole cards per player
    streets:         board cards dealt before each postflop betting round
    hole_used:       None = best 5 of any cards; k = exactly k hole cards (Omaha: 2)
    category_order:  hand categories weakest -> strongest
    ace_low_straight: ace may play low (A2345, or A6789 in short deck)
    """

    def __init__(self, name, ranks="23456789TJQKA", suits=4, n_hole=2, streets=(3, 1, 1),
                 hole_used=None, category_order=STANDARD_ORDER, ace_low_straight=True):
        self.name = name
        self.ranks = ranks
        self.suits = int(suits)
        self.n_hole = int(n_hole)
        self.streets = tuple(int(x) for x in streets)
        self.hole_used = None if hole_used is None else int(hole_used)
        self.category_order = tuple(int(c) for c in category_order)
        self.ace_low_straight = bool(ace_low_straight)
        self.R = len(ranks)
        self.D = self.R * self.suits
        self.n_board = sum(self.streets)
        if self.R > 16:
            raise ValueError("at most 16 ranks supported")
        if sorted(self.category_order) != list(range(N_CATEGORIES)):
            raise ValueError("category_order must be a permutation of all 10 categories")
        if self.hole_used is not None and self.hole_used > self.n_hole:
            raise ValueError("hole_used > n_hole")

    def to_dict(self):
        return {"name": self.name, "ranks": self.ranks, "suits": self.suits,
                "n_hole": self.n_hole, "streets": list(self.streets),
                "hole_used": self.hole_used, "category_order": list(self.category_order),
                "ace_low_straight": self.ace_low_straight}

    @classmethod
    def from_dict(cls, d):
        return cls(**d)

    def max_opponents(self, cap=7):
        """Most opponents that can be dealt in alongside a full board."""
        return max(1, min(cap, (self.D - self.n_board - self.n_hole) // self.n_hole))

    def __repr__(self):
        return f"Variant({self.to_dict()})"


_SHORT_ORDER = (HIGH, PAIR, TWO_PAIR, TRIPS, STRAIGHT, FULL_HOUSE, FLUSH, QUADS,
                STRAIGHT_FLUSH, FIVE_KIND)
_TRITON_ORDER = (HIGH, PAIR, TWO_PAIR, STRAIGHT, TRIPS, FULL_HOUSE, FLUSH, QUADS,
                 STRAIGHT_FLUSH, FIVE_KIND)

PRESETS = {
    "nlhe": Variant("nlhe"),
    "shortdeck": Variant("shortdeck", ranks="6789TJQKA", category_order=_SHORT_ORDER),
    "shortdeck_triton": Variant("shortdeck_triton", ranks="6789TJQKA", category_order=_TRITON_ORDER),
    "plo4": Variant("plo4", n_hole=4, hole_used=2),
    "plo5": Variant("plo5", n_hole=5, hole_used=2),
    "holdem3": Variant("holdem3", n_hole=3),
    "royal": Variant("royal", ranks="TJQKA"),
    "pineapple_nodiscard": Variant("pineapple_nodiscard", n_hole=3),
}


def get_variant(name_or_dict):
    if isinstance(name_or_dict, Variant):
        return name_or_dict
    if isinstance(name_or_dict, dict):
        return Variant.from_dict(name_or_dict)
    if hasattr(name_or_dict, "to_dict"):   # Variant from a packaged copy of this module
        return Variant.from_dict(name_or_dict.to_dict())
    if name_or_dict.lstrip().startswith("{"):   # variant JSON, e.g. NOLIMIT_VARIANT for a new variant
        return Variant.from_dict(json.loads(name_or_dict))
    return PRESETS[name_or_dict]


def card_str(v, c):
    return v.ranks[c // v.suits] + SUIT_CHARS[c % v.suits]


def parse_cards(v, s):
    s = s.replace(" ", "")
    return [v.ranks.index(s[i]) * v.suits + SUIT_CHARS.index(s[i + 1]) for i in range(0, len(s), 2)]


# ---------------------------------------------------------------------------
# Hand evaluation
# ---------------------------------------------------------------------------

_PRIMES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53)


def hand_value_5(ranks, is_flush, strength, R, ace_low):
    """Reference 5-card value: (category strength << 20) | tiebreak nibbles.

    gpu/tensor_eval.py mirrors this exactly; tests/test_evaluator.py checks parity.
    """
    counts = {}
    for r in ranks:
        counts[r] = counts.get(r, 0) + 1
    ordered = sorted(ranks, key=lambda r: (counts[r], r), reverse=True)
    distinct = len(counts)
    top = max(counts.values())
    straight_high = -1
    if distinct == 5:
        srt = sorted(ranks)
        if srt[4] - srt[0] == 4:
            straight_high = srt[4]
        elif ace_low and R >= 6 and srt == [0, 1, 2, 3, R - 1]:
            straight_high = 3
    if top == 5:
        cat = FIVE_KIND
    elif straight_high >= 0 and is_flush:
        cat = STRAIGHT_FLUSH
    elif top == 4:
        cat = QUADS
    elif top == 3 and distinct == 2:
        cat = FULL_HOUSE
    elif is_flush:
        cat = FLUSH
    elif straight_high >= 0:
        cat = STRAIGHT
    elif top == 3:
        cat = TRIPS
    elif top == 2 and distinct == 3:
        cat = TWO_PAIR
    elif top == 2:
        cat = PAIR
    else:
        cat = HIGH
    if cat in (STRAIGHT, STRAIGHT_FLUSH):
        tb = straight_high << 16
    else:
        tb = (ordered[0] << 16) | (ordered[1] << 12) | (ordered[2] << 8) | (ordered[3] << 4) | ordered[4]
    return (strength[cat] << 20) | tb


class Evaluator:
    """Fast pure-Python evaluator built from a Variant (prime-product lookup)."""

    def __init__(self, variant):
        v = self.v = variant
        S = v.suits
        self.strength = [0] * N_CATEGORIES
        for i, c in enumerate(v.category_order):
            self.strength[c] = i
        self.cat_of_strength = list(v.category_order)
        self.prime = [_PRIMES[c // S] for c in range(v.D)]
        self.suit = [c % S for c in range(v.D)]
        self.rank = [c // S for c in range(v.D)]
        self.nonflush = {}
        self.flush = {}
        for combo in itertools.combinations_with_replacement(range(v.R), 5):
            if max(combo.count(r) for r in combo) > S:
                continue
            key = 1
            for r in combo:
                key *= _PRIMES[r]
            self.nonflush[key] = hand_value_5(combo, False, self.strength, v.R, v.ace_low_straight)
            if len(set(combo)) == 5:
                self.flush[key] = hand_value_5(combo, True, self.strength, v.R, v.ace_low_straight)
        self._combos = {}
        # Must-use-k-hole variants (Omaha): best() combines hole-subset and board-subset prime
        # products and looks only flush-capable suits up in the flush table. That needs a
        # flush to be worth at least the same ranks unsuited (flush > high card, straight
        # flush > straight), true of every preset; otherwise keep the per-combo loop.
        # Setting _split = None forces the per-combo loop (the reference in tests).
        nf, fl = self.nonflush, self.flush
        hu = v.hole_used
        self._split = hu if hu is not None and 0 < hu < 5 and all(fl[k] >= nf[k] for k in fl) else None
        self._subsets = {}

    def combos(self, n_hole, n_board):
        """5-card index tuples into (hole + board) that the variant allows."""
        key = (n_hole, n_board)
        got = self._combos.get(key)
        if got is not None:
            return got
        hu = self.v.hole_used
        if hu is None:
            out = tuple(itertools.combinations(range(n_hole + n_board), 5)) if n_hole + n_board >= 5 else ()
        elif n_board < 5 - hu or n_hole < hu:
            out = ()
        else:
            out = tuple(h + tuple(n_hole + b for b in bc)
                        for h in itertools.combinations(range(n_hole), hu)
                        for bc in itertools.combinations(range(n_board), 5 - hu))
        self._combos[key] = out
        return out

    def eval5(self, cards):
        p = self.prime
        key = p[cards[0]] * p[cards[1]] * p[cards[2]] * p[cards[3]] * p[cards[4]]
        s = self.suit
        if s[cards[0]] == s[cards[1]] == s[cards[2]] == s[cards[3]] == s[cards[4]]:
            return self.flush[key]
        return self.nonflush[key]

    def best(self, hole, board):
        """Best value for hole + board, or -1 if no legal 5-card hand exists yet."""
        if self._split is not None:
            return self._best_split(hole, board, self._split)
        cards = tuple(hole) + tuple(board)
        p = self.prime
        s = self.suit
        nf = self.nonflush
        fl = self.flush
        best = -1
        for a, b, c, d, e in self.combos(len(hole), len(board)):
            ca, cb, cc, cd, ce = cards[a], cards[b], cards[c], cards[d], cards[e]
            key = p[ca] * p[cb] * p[cc] * p[cd] * p[ce]
            if s[ca] == s[cb] == s[cc] == s[cd] == s[ce]:
                val = fl[key]
            else:
                val = nf[key]
            if val > best:
                best = val
        return best

    def _subset_idx(self, n, k):
        key = (n, k)
        got = self._subsets.get(key)
        if got is None:
            got = self._subsets[key] = tuple(itertools.combinations(range(n), k))
        return got

    def _best_split(self, hole, board, hu):
        """best() for variants that use exactly hu hole cards: same value as the per-combo loop."""
        nb = 5 - hu
        if len(board) < nb or len(hole) < hu:
            return -1
        p = self.prime
        ph = [p[c] for c in hole]
        pb = [p[c] for c in board]
        if hu == 2:
            hp = [ph[i] * ph[j] for i, j in self._subset_idx(len(hole), 2)]
        else:
            hp = [math.prod([ph[i] for i in c]) for c in self._subset_idx(len(hole), hu)]
        if nb == 3:
            bp = [pb[i] * pb[j] * pb[k] for i, j, k in self._subset_idx(len(board), 3)]
        else:
            bp = [math.prod([pb[i] for i in c]) for c in self._subset_idx(len(board), nb)]
        nf = self.nonflush
        best = max([nf[a * b] for a in hp for b in bp])
        # A flush needs nb board cards and hu hole cards of one suit.
        s = self.suit
        S = self.v.suits
        cnt = [0] * S
        for c in board:
            cnt[s[c]] += 1
        for su in range(S):
            if cnt[su] < nb:
                continue
            hs = [p[c] for c in hole if s[c] == su]
            if len(hs) < hu:
                continue
            bs = [p[c] for c in board if s[c] == su]
            fl = self.flush
            for hc in itertools.combinations(hs, hu):
                a = math.prod(hc)
                for bc in itertools.combinations(bs, nb):
                    val = fl[a * math.prod(bc)]
                    if val > best:
                        best = val
        return best

    def category(self, value):
        return self.cat_of_strength[value >> 20]


class ComboIndexer:
    """Colex rank of a k-card set: sum C(c_i, i+1) over ascending cards."""

    def __init__(self, D, k):
        self.k = k
        self.B = [[0] * (k + 1) for _ in range(D + 1)]
        for n in range(D + 1):
            self.B[n][0] = 1
            for r in range(1, min(n, k) + 1):
                self.B[n][r] = self.B[n - 1][r - 1] + (self.B[n - 1][r] if r <= n - 1 else 0)
        self.total = self.B[D][k]

    def index(self, cards):
        B = self.B
        return sum(B[c][i + 1] for i, c in enumerate(sorted(cards)))


# ---------------------------------------------------------------------------
# Postflop features (gpu/tensor_eval.py mirrors this; parity tested)
# ---------------------------------------------------------------------------

def straight_windows(v):
    """Rank sets of every possible straight, as tuples of rank indices."""
    if v.R < 5:
        return ()
    wins = [tuple(range(lo, lo + 5)) for lo in range(v.R - 4)]
    if v.ace_low_straight and v.R >= 6:
        wins.append((0, 1, 2, 3, v.R - 1))
    return tuple(wins)


# Range-equity grid (gpu/range_eq.py): opponent holds the top x, by postflop strength, of
# the top y of hands by preflop strength. Flattened y-major.
RANGE_Y = (1.0, 0.55, 0.3, 0.16, 0.08)
RANGE_X = (1.0, 0.7, 0.5, 0.35, 0.25, 0.17, 0.12, 0.08, 0.05)


def feature_dim(v):
    return 2 * v.R + 2 * v.suits + N_CATEGORIES + len(v.streets) + 2


def postflop_features(v, ev, windows, hole, board):
    """Dense feature list for (hole, board). Requires a legal 5-card hand (postflop)."""
    R, S = v.R, v.suits
    f = [0.0] * feature_dim(v)
    hs = [0] * S
    bs = [0] * S
    hp = [False] * R
    cp = [False] * R
    for c in hole:
        r = c // S
        f[r] += 0.5
        hs[c % S] += 1
        hp[r] = True
        cp[r] = True
    for c in board:
        r = c // S
        f[R + r] += 0.5
        bs[c % S] += 1
        cp[r] = True
    order = sorted(range(S), key=lambda i: ((hs[i] + bs[i]) * 8 + hs[i]), reverse=True)
    o = 2 * R
    for j, i in enumerate(order):
        f[o + 2 * j] = hs[i] * 0.25
        f[o + 2 * j + 1] = bs[i] * 0.25
    o += 2 * S
    val = ev.best(hole, board)
    f[o + ev.category(val)] = 1.0
    o += N_CATEGORIES
    n_b = len(board)
    cum = 0
    for k, n in enumerate(v.streets):
        cum += n
        if cum == n_b:
            f[o + k] = 1.0
    o += len(v.streets)
    best_all = 0
    best_hole = 0
    for w in windows:
        cnt = 0
        uses_hole = False
        for r in w:
            if cp[r]:
                cnt += 1
                if hp[r]:
                    uses_hole = True
        if cnt > best_all:
            best_all = cnt
        if uses_hole and cnt > best_hole:
            best_hole = cnt
    f[o] = best_all / 5.0
    f[o + 1] = best_hole / 5.0
    return f


# ---------------------------------------------------------------------------
# Table bundle (stdlib reader; nolimit/bundle_io.py writes with numpy)
# ---------------------------------------------------------------------------

BUNDLE_MAGIC = b"NLB1"
_TYPECODES = {"float32": "f", "int32": "i", "int16": "h", "int8": "b", "uint8": "B"}
assert array("i").itemsize == 4 and array("f").itemsize == 4


def read_bundle(data):
    """Return (meta dict, {name: (flat array, shape)}) from bundle bytes."""
    if data[:4] != BUNDLE_MAGIC:
        raise ValueError("not a NoLimit bundle")
    (hlen,) = struct.unpack("<I", data[4:8])
    header = json.loads(data[8:8 + hlen].decode())
    payload = zlib.decompress(data[8 + hlen:])
    arrays = {}
    for name, info in header["arrays"].items():
        a = array(_TYPECODES[info["dtype"]])
        a.frombytes(payload[info["offset"]:info["offset"] + info["nbytes"]])
        if sys.byteorder == "big":
            a.byteswap()
        arrays[name] = (a, tuple(info["shape"]))
    return header["meta"], arrays


class Tables:
    """Lookups the bot needs: preflop strength, equities, postflop MLP, push/fold charts."""

    def __init__(self, data):
        meta, arrs = read_bundle(data)
        self.meta = meta
        v = self.v = Variant.from_dict(meta["variant"])
        self.ev = Evaluator(v)
        self.indexer = ComboIndexer(v.D, v.n_hole)
        self.windows = straight_windows(v)
        self.combo_class = arrs["combo_class"][0]
        self.class_pct = arrs["class_pct"][0]
        self.k_max = meta["k_max"]
        self.class_eq = arrs["class_eq"][0]
        self.Y = meta["range_buckets"]
        self.eq_range = arrs["eq_range"][0]
        self.has_mlp = "mlp_w1" in arrs
        if self.has_mlp:
            self._load_mlp(arrs)
        self.has_rng = "rng_w1" in arrs
        if self.has_rng:
            self.rng_net, self.rng_kind = self._load_net(arrs, "rng_", "rngsmall_")
            self._ry = [math.log(g) for g in meta["rng_y"]]
            self._rx = [math.log(g) for g in meta["rng_x"]]
        self._rng_cache = {}
        self._feat_cache = {}
        self.has_pushfold = "pf_shove" in arrs
        if self.has_pushfold:
            self.pf_shove = arrs["pf_shove"][0]
            self.pf_call = arrs["pf_call"][0]
            self.pf_stacks = meta["pf_stacks"]
            self.pf_nmax = meta["pf_nmax"]
        self.has_bf = "icm_bf" in arrs
        if self.has_bf:
            self.bf = arrs["icm_bf"][0]
            self.bf_shares = meta["bf_shares"]
            self.bf_fracs = meta["bf_fracs"]
            self._bf_mids = _midpoints(self.bf_shares)
        self._post_cache = {}

    # -- preflop ----------------------------------------------------------
    def hole_class(self, hole):
        return self.combo_class[self.indexer.index(hole)]

    def pct(self, cls):
        """0 = strongest hand, 1 = weakest (fraction of combos stronger or equal)."""
        return self.class_pct[cls]

    def eq(self, cls, n_opp):
        n = min(max(n_opp, 1), self.k_max)
        return self.class_eq[cls * self.k_max + n - 1]

    def eq_vs_range(self, cls, y):
        """Heads-up equity vs an opponent playing the top y fraction of hands."""
        Y = self.Y
        x = min(max(y, 1.0 / Y), 1.0) * Y - 1.0
        i = int(x)
        base = cls * Y
        if i >= Y - 1:
            return self.eq_range[base + Y - 1]
        t = x - i
        return self.eq_range[base + i] * (1 - t) + self.eq_range[base + i + 1] * t

    # -- postflop ---------------------------------------------------------
    def _load_net(self, arrs, big, small):
        """(weights, kind). The big model needs numpy to stay fast; pure Python uses the small one.

        With numpy the small model is loaded too (`self._spare`), so `select_nets` can switch
        to it on hardware where the big one would push decisions toward the time limit."""
        pre = big if np is not None or small + "w1" not in arrs else small
        if np is not None:
            def load(pfx):
                return [np.frombuffer(arrs[pfx + k][0].tobytes(), dtype="<f4").reshape(arrs[pfx + k][1])
                        for k in ("w1", "b1", "w2", "b2", "w3", "b3")]
            net = load(pre)
            if pre == big and small + "w1" in arrs:
                self._spare = getattr(self, "_spare", {})
                self._spare[big] = ((net, big.rstrip("_")), (load(small), small.rstrip("_")))
        else:
            # Pure Python: w1 by input row (features are sparse), w2/w3 by output column so
            # each unit is one C-level sum(map(mul, ...)).
            def rows(name):
                a, (r, c) = arrs[pre + name]
                return [list(a[i * c:(i + 1) * c]) for i in range(r)]

            def cols(name):
                return [list(col) for col in zip(*rows(name))]
            net = [rows("w1"), list(arrs[pre + "b1"][0]), cols("w2"),
                   list(arrs[pre + "b2"][0]), cols("w3"), list(arrs[pre + "b3"][0])]
        return net, pre.rstrip("_")

    def _load_mlp(self, arrs):
        self.mlp, self.mlp_kind = self._load_net(arrs, "mlp_", "mlpsmall_")
        pre = self.mlp_kind + "_"
        self.mlp_shapes = [arrs[pre + k][1] for k in ("w1", "w2", "w3")]

    def select_nets(self, size):
        """'big' or 'small': which postflop/range models to run (numpy only; else a no-op)."""
        spare = getattr(self, "_spare", {})
        i = 0 if size == "big" else 1
        if "mlp_" in spare:
            self.mlp, self.mlp_kind = spare["mlp_"][i]
        if "rng_" in spare:
            self.rng_net, self.rng_kind = spare["rng_"][i]
        self._post_cache.clear()
        self._rng_cache.clear()
        self._feat_cache.clear()

    def _features(self, key, hole, board):
        """Postflop features, shared by the two models for the same (hole, board)."""
        f = self._feat_cache.get(key)
        if f is None:
            if len(self._feat_cache) > 256:
                self._feat_cache.clear()
            f = self._feat_cache[key] = postflop_features(self.v, self.ev, self.windows, hole, board)
        return f

    def _mlp_forward(self, f, net=None):
        w1, b1, w2, b2, w3, b3 = net or self.mlp
        if np is not None:
            h = np.maximum(np.asarray(f, dtype=np.float32) @ w1 + b1, 0.0)
            h = np.maximum(h @ w2 + b2, 0.0)
            o = h @ w3 + b3
            return (1.0 / (1.0 + np.exp(-np.clip(o, -60.0, 60.0)))).tolist()
        h2 = self._hidden(f, net or self.mlp)
        if _sumprod is not None:
            return [1.0 / (1.0 + _exp(-(b + _sumprod(h2, col)))) for b, col in zip(b3, w3)]
        return [1.0 / (1.0 + _exp(-(b + sum(map(_mul, h2, col))))) for b, col in zip(b3, w3)]

    @staticmethod
    def _hidden(f, net):
        """Pure Python: activations of the second hidden layer."""
        w1, b1, w2, b2 = net[:4]
        xs, rows = [], []
        for x, r in zip(f, w1):
            if x:                       # features are sparse: only nonzero inputs contribute
                xs.append(x)
                rows.append(r)
        if _sumprod is not None:
            h = [b + _sumprod(xs, col) for b, col in zip(b1, zip(*rows))] if xs else list(b1)
            h = [x if x > 0.0 else 0.0 for x in h]
            h2 = [b + _sumprod(h, col) for b, col in zip(b2, w2)]
            return [x if x > 0.0 else 0.0 for x in h2]
        h = [b + sum(map(_mul, xs, col)) for b, col in zip(b1, zip(*rows))] if xs else list(b1)
        h = [x if x > 0.0 else 0.0 for x in h]
        h2 = [b + sum(map(_mul, h, col)) for b, col in zip(b2, w2)]
        return [x if x > 0.0 else 0.0 for x in h2]

    def post_equity(self, hole, board):
        """Equity vs (1, 2, 3) random opponents, from the MLP (cached)."""
        key = (tuple(hole), tuple(board))
        got = self._post_cache.get(key)
        if got is not None:
            return got
        if self.has_mlp:
            out = self._mlp_forward(self._features(key, hole, board))
        else:
            out = heuristic_post_equity(self.v, self.ev, hole, board)
        if len(self._post_cache) > 4096:
            self._post_cache.clear()
        self._post_cache[key] = out
        return out

    def post_curve(self, hole, board):
        """Heads-up equity on the RANGE_Y x RANGE_X grid (y-major), from the range MLP (cached)."""
        key = (tuple(hole), tuple(board))
        got = self._rng_cache.get(key)
        if got is None:
            f = self._features(key, hole, board)
            if np is None:
                # Pure Python: output cells are computed when a lookup touches them (a decision
                # reads ~2 of the 5 rows), which skips most of the costliest layer.
                got = _LazyCurve(self._hidden(f, self.rng_net), self.rng_net[4], self.rng_net[5])
            else:
                got = self._mlp_forward(f, self.rng_net)
            if len(self._rng_cache) > 4096:
                self._rng_cache.clear()
            self._rng_cache[key] = got
        return got

    def range_equity(self, curve, y, x):
        """Equity vs the top x (postflop) of the top y (preflop): bilinear in log y, log x."""
        iy, ty = _grid_pos(self._ry, y)
        ix, tx = _grid_pos(self._rx, x)
        nx = len(self._rx)
        r = iy * nx + ix
        e0 = curve[r] + (curve[r + 1] - curve[r]) * tx if tx else curve[r]
        if not ty:
            return e0
        r += nx
        e1 = curve[r] + (curve[r + 1] - curve[r]) * tx if tx else curve[r]
        return e0 + (e1 - e0) * ty

    def interval_equity(self, curve, y, a, b):
        """Equity vs the slice [a, b] of the opponent's range (0 = their strongest hands)."""
        if b - a < 0.04:
            b = min(1.0, a + 0.04)
            a = b - 0.04
        eb = self.range_equity(curve, y, b)
        if a < 0.002:
            return eb
        ea = self.range_equity(curve, y, a)
        return _clamp((b * eb - a * ea) / (b - a), 0.0, 1.0)

    # -- push/fold --------------------------------------------------------
    def _pf_bucket(self, eff_bb):
        st = self.pf_stacks
        if eff_bb <= st[0]:
            return 0
        for i in range(len(st) - 1):
            if eff_bb < (st[i] + st[i + 1]) / 2:
                return i
        return len(st) - 1

    def shove_threshold(self, n, pos, eff_bb):
        """Top fraction of hands to open-shove when folded to `pos` (0 = first to act)."""
        if not self.has_pushfold or not 2 <= n <= self.pf_nmax or pos >= n - 1:
            return None
        P, K = self.pf_nmax, len(self.pf_stacks)
        return self.pf_shove[((n - 2) * P + pos) * K + self._pf_bucket(eff_bb)]

    def call_threshold(self, n, shover_pos, caller_pos, eff_bb):
        if not self.has_pushfold or not 2 <= n <= self.pf_nmax or not shover_pos < caller_pos < n:
            return None
        P, K = self.pf_nmax, len(self.pf_stacks)
        return self.pf_call[(((n - 2) * P + shover_pos) * P + caller_pos) * K + self._pf_bucket(eff_bb)]

    def bubble_factor(self, n, hero_share, villain_share, risk_frac):
        """ICM bubble factor for risking risk_frac of the effective stack vs one villain."""
        if not self.has_bf or n < 2:
            return None
        n = min(n, len(self.bf) // (len(self.bf_shares) ** 2 * len(self.bf_fracs)) + 1)
        sh = self.bf_shares
        i = _nearest(sh, self._bf_mids, hero_share)
        j = _nearest(sh, self._bf_mids, villain_share)
        fr = self.bf_fracs
        F = len(fr)
        base = (((n - 2) * len(sh) + i) * len(sh) + j) * F
        f = _clamp(risk_frac, fr[0], fr[-1])
        for k in range(F - 1):
            if f <= fr[k + 1]:
                t = (f - fr[k]) / (fr[k + 1] - fr[k])
                return self.bf[base + k] * (1 - t) + self.bf[base + k + 1] * t
        return self.bf[base + F - 1]


def _midpoints(grid):
    return [(a + b) / 2 for a, b in zip(grid, grid[1:])]


def _nearest(grid, mids, x):
    """Index of the grid point nearest x, ties to the lower index: the same answer as
    min(range(len(grid)), key=lambda k: abs(grid[k] - x)) for an ascending grid, in O(log n).
    Bisecting the midpoints finds the cell; the neighbour checks redo the exact abs()
    comparison so float rounding at a midpoint can't pick a different index. Far outside
    the grid (or NaN) every distance can round to the same value, so scan as before."""
    if not -4.0 < x < 4.0:
        return min(range(len(grid)), key=lambda k: abs(grid[k] - x))
    k = bisect.bisect_left(mids, x)
    if k and abs(grid[k - 1] - x) <= abs(grid[k] - x):
        return k - 1
    if k + 1 < len(grid) and abs(grid[k + 1] - x) < abs(grid[k] - x):
        return k + 1
    return k


class _LazyCurve:
    """Range-model output whose cells are computed on first access (pure-Python path)."""
    __slots__ = ("h2", "w3", "b3", "vals")

    def __init__(self, h2, w3, b3):
        self.h2, self.w3, self.b3 = h2, w3, b3
        self.vals = [None] * len(b3)

    def __getitem__(self, j):
        v = self.vals[j]
        if v is None:
            if _sumprod is not None:
                z = _sumprod(self.h2, self.w3[j])
            else:
                z = sum(map(_mul, self.h2, self.w3[j]))
            v = self.vals[j] = 1.0 / (1.0 + _exp(-(self.b3[j] + z)))
        return v

    def __len__(self):
        return len(self.b3)

    def __iter__(self):
        return (self[j] for j in range(len(self.b3)))


def _exp(x):
    return math.exp(_clamp(x, -60.0, 60.0))


def _grid_pos(logs, v):
    """(i, t) so that log v sits a fraction t from logs[i] to logs[i + 1] (descending grid)."""
    lv = math.log(_clamp(v, 1e-6, 1.0))
    if lv >= logs[0]:
        return 0, 0.0
    for i in range(len(logs) - 1):
        if lv >= logs[i + 1]:
            return i, (logs[i] - lv) / (logs[i] - logs[i + 1])
    return len(logs) - 1, 0.0


_HEUR_CAT_EQ = {HIGH: 0.22, PAIR: 0.52, TWO_PAIR: 0.72, TRIPS: 0.82, STRAIGHT: 0.86,
                FLUSH: 0.88, FULL_HOUSE: 0.94, QUADS: 0.985, STRAIGHT_FLUSH: 0.995, FIVE_KIND: 0.998}


def heuristic_post_equity(v, ev, hole, board):
    """Crude made-hand equity, used before the MLP is trained for a new variant."""
    val = ev.best(hole, board)
    cat = ev.category(val)
    # Equity follows strength rank, so reordered variants (short deck) map correctly.
    e1 = _HEUR_CAT_EQ[STANDARD_ORDER[val >> 20]]
    top = ((val >> 16) & 15) / max(v.R - 1, 1)
    e1 = min(0.99, e1 + 0.06 * (top - 0.5))
    if len(board) < v.n_board and cat in (HIGH, PAIR):
        S = v.suits
        suits = [0] * S
        for c in tuple(hole) + tuple(board):
            suits[c % S] += 1
        if max(suits) >= 4:
            e1 = max(e1, 0.42)
    return [e1, e1 ** 1.6, e1 ** 2.1]


class HeuristicTables:
    """Same interface as Tables with no precomputed bundle: the minute-5 fallback."""

    has_pushfold = False
    has_mlp = False
    has_rng = False

    def __init__(self, variant, seed=0, samples=3000):
        v = self.v = get_variant(variant)
        self.ev = Evaluator(v)
        self.windows = straight_windows(v)
        rng = random.Random(seed)
        deck = list(range(v.D))
        self._scores = sorted(self._score(rng.sample(deck, v.n_hole)) for _ in range(samples))
        self.k_max = v.max_opponents()
        self._post_cache = {}

    def _score(self, hole):
        v = self.v
        S = v.suits
        ranks = sorted((c // S for c in hole), reverse=True)
        s = sum(r / (v.R - 1) for r in ranks[:2]) + 0.25 * sum(r / (v.R - 1) for r in ranks[2:])
        if len(set(ranks)) < len(ranks):
            s += 0.6 + 0.4 * max(r for r in ranks if ranks.count(r) > 1) / (v.R - 1)
        suits = [c % S for c in hole]
        if len(set(suits)) < len(suits):
            s += 0.15
        if len(ranks) >= 2 and abs(ranks[0] - ranks[1]) <= 2:
            s += 0.08
        return s

    def hole_class(self, hole):
        return tuple(hole)

    def pct(self, cls):
        import bisect
        s = self._score(cls)
        return 1.0 - bisect.bisect_left(self._scores, s) / len(self._scores)

    def eq(self, cls, n_opp):
        e1 = 0.35 + 0.5 * (1 - self.pct(cls))
        return e1 ** (max(n_opp, 1) ** 0.8)

    def eq_vs_range(self, cls, y):
        p = self.pct(cls)
        mid = max(y, 0.0) / 2
        return min(0.95, max(0.05, 0.5 + 0.35 * (mid - p) / max(mid, p, 0.02)))

    def post_equity(self, hole, board):
        return heuristic_post_equity(self.v, self.ev, hole, board)

    def shove_threshold(self, n, pos, eff_bb):
        return None

    def call_threshold(self, n, shover_pos, caller_pos, eff_bb):
        return None

    def bubble_factor(self, n, hero_share, villain_share, risk_frac):
        return None


_TABLES_CACHE = {}


def load_tables(path=None, data=None, variant=None):
    """Module-level cache so per-table bot instances don't reload the bundle."""
    key = path or (id(data) if data is not None else ("heur", str(variant)))
    got = _TABLES_CACHE.get(key)
    if got is None:
        if data is not None:
            got = Tables(data)
        elif path is not None:
            with open(path, "rb") as fh:
                got = Tables(fh.read())
        else:
            got = HeuristicTables(variant)
        _TABLES_CACHE[key] = got
    return got


# ---------------------------------------------------------------------------
# Observation / action protocol (engine.py speaks this; adapter maps the real one)
# ---------------------------------------------------------------------------

FOLD, CALL, RAISE, POST = 0, 1, 2, 3   # CALL with to_call == 0 is a check


class Obs:
    """What a bot sees at a decision. Amounts in chips.

    bets:         chips each seat put in during this betting round (blinds count preflop)
    pot:          all chips committed this hand, including current bets and antes
    min_raise_to: smallest legal raise-to total, 0 if raising is not allowed
    max_raise_to: hero's all-in raise-to total
    history:      ((seat, street, kind, amount_to, all_in), ...) for this hand; blinds are POST
    """

    __slots__ = ("hole", "board", "street", "seat", "button", "stacks", "bets", "in_hand",
                 "pot", "to_call", "min_raise_to", "max_raise_to", "sb", "bb", "ante",
                 "hand_no", "history")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw[k])


class BotBase:
    def new_table(self, seat, n_seats):
        pass

    def act(self, obs):
        raise NotImplementedError

    def observe(self, event):
        """event: ("hand_end", {"hand_no", "history", "showdown": {seat: hole}, "board"})"""


# ---------------------------------------------------------------------------
# Opponent model
# ---------------------------------------------------------------------------

PRIORS = {"vpip": 0.35, "pfr": 0.18, "shove": 0.06, "fold_to_bet": 0.45, "agg": 0.45,
          "bet": 0.40, "raise": 0.12, "fold_nb": 0.35, "fold_ab": 0.15}
PRIOR_WEIGHT = 6.0
# Seat stats the per-opponent exploitation rule reads (scripts/fit_exploit.py), and how many
# blend steps between the base and the exploit params are precomputed.
EXPLOIT_FEATS = ("vpip", "pfr", "agg", "fold_to_bet", "shove", "bet", "fold_nb")
EXPLOIT_LEVELS = 5


def _ex_rates(st):
    """SeatStats.rate() for each of EXPLOIT_FEATS, inlined: it runs for every villain on the
    first decision of each hand, inside the 1 ms."""
    w, pr = PRIOR_WEIGHT, st.prior
    h = st.hands + w
    return ((st.vpip + pr["vpip"] * w) / h, (st.pfr + pr["pfr"] * w) / h,
            (st.aggr + pr["agg"] * w) / (st.aggr + st.passive + w),
            (st.folded + pr["fold_to_bet"] * w) / (st.faced + w), (st.shove + pr["shove"] * w) / h,
            (st.bets + pr["bet"] * w) / (st.bet_opp + w),
            (st.folded - st.folded_ab + pr["fold_nb"] * w) / (st.faced - st.faced_ab + w))


class SeatStats:
    __slots__ = ("hands", "vpip", "pfr", "shove", "faced", "folded", "aggr", "passive",
                 "bet_opp", "bets", "raised", "faced_ab", "folded_ab", "prior")

    def __init__(self):
        self.hands = self.vpip = self.pfr = self.shove = 0
        self.faced = self.folded = self.aggr = self.passive = 0
        self.bet_opp = self.bets = self.raised = self.faced_ab = self.folded_ab = 0
        self.prior = PRIORS

    def rate(self, name):
        num, den = self.counts(name)
        return (num + self.prior[name] * PRIOR_WEIGHT) / (den + PRIOR_WEIGHT)

    def counts(self, name):
        if name == "fold_to_bet":
            num, den = self.folded, self.faced
        elif name == "agg":
            num, den = self.aggr, self.aggr + self.passive
        elif name == "bet":        # postflop: bet when nobody has bet yet this street
            num, den = self.bets, self.bet_opp
        elif name == "raise":      # postflop: raise when facing a bet
            num, den = self.raised, self.faced
        elif name == "fold_nb":    # fold to a bet without having bet this street
            num, den = self.folded - self.folded_ab, self.faced - self.faced_ab
        elif name == "fold_ab":    # fold to a raise of our own bet
            num, den = self.folded_ab, self.faced_ab
        else:
            num, den = getattr(self, name), self.hands
        return num, den


def pool_priors(stats, skip, weight):
    """Shrink each seat toward what the rest of the table does instead of a fixed guess.

    The pooled rate is itself shrunk toward PRIORS (PRIOR_WEIGHT x 3 pseudo-hands), then
    blended in by `weight` (0 = fixed PRIORS, 1 = pooled). Each seat's own hands are left
    out of its pool so a seat never counts its own sample twice."""
    if weight <= 0:
        return
    tot = {k: [0, 0] for k in PRIORS}
    per = []
    for i, st in enumerate(stats):
        c = {k: st.counts(k) for k in PRIORS} if i != skip else None
        per.append(c)
        if c:
            for k, (n, d) in c.items():
                tot[k][0] += n
                tot[k][1] += d
    w0 = PRIOR_WEIGHT * 3
    for i, st in enumerate(stats):
        if per[i] is None:
            continue
        pr = {}
        for k, base in PRIORS.items():
            n, d = tot[k][0] - per[i][k][0], tot[k][1] - per[i][k][1]
            pr[k] = base + weight * ((n + base * w0) / (d + w0) - base)
        st.prior = pr


def ingest_history(stats, history):
    """Update per-seat stats from one complete (or partial) hand history."""
    seen = set()
    vp = set()
    pr = set()
    sh = set()
    street = -1
    bets = {}
    aggr = set()
    for seat, st, kind, amt, all_in in history:
        seen.add(seat)
        if st != street:
            street = st
            bets = {}
            aggr = set()
        cur = max(bets.values()) if bets else 0
        prev = bets.get(seat, 0)
        if kind == POST:
            bets[seat] = amt
            continue
        s = stats[seat]
        if st == 0:
            if kind == RAISE:
                vp.add(seat)
                pr.add(seat)
                if all_in:
                    sh.add(seat)
            elif kind == CALL and amt > prev:
                vp.add(seat)
        else:
            if cur > prev:
                s.faced += 1
                if seat in aggr:
                    s.faced_ab += 1
                if kind == FOLD:
                    s.folded += 1
                    if seat in aggr:
                        s.folded_ab += 1
                elif kind == RAISE:
                    s.raised += 1
            else:
                s.bet_opp += 1
                if kind == RAISE:
                    s.bets += 1
            if kind == RAISE:
                s.aggr += 1
                aggr.add(seat)
            elif kind == CALL and amt > prev:
                s.passive += 1
        if kind in (CALL, RAISE):
            bets[seat] = amt
    for seat in seen:
        s = stats[seat]
        s.hands += 1
        s.vpip += seat in vp
        s.pfr += seat in pr
        s.shove += seat in sh


# ---------------------------------------------------------------------------
# PrepBot
# ---------------------------------------------------------------------------

DEFAULT_PARAMS = {
    # preflop, deep stacks
    "open_base": 0.12,        # open top x% with the whole table behind
    "open_late": 0.32,        # ... widening to this with nobody behind
    "open_bb": 2.5,           # open size in big blinds
    "steal_exploit": 1.0,     # how hard to widen opens vs players behind who rarely play
    "iso_pct": 0.15,         # raise over limpers / from a limped BB
    "sb_complete_pct": 0.40,
    "reraise_eq": 0.62,       # HU equity vs raiser's range needed to re-raise
    "reraise_mult": 3.0,
    "pre_realize": 0.92,      # equity realization when calling preflop
    "pre_tighten": 0.45,      # each extra raise shrinks the assumed range by this factor
    # push/fold
    "pf_bb": 12.0,            # effective stack (bb) at or below which we push/fold
    "pf_shove_scale": 1.0,
    "pf_call_scale": 1.0,
    "pf_exploit": 1.0,        # how hard to widen shoves vs tables that rarely call
    "pf_margin": 0.02,        # equity over pot odds demanded when calling off (ICM tax)
    # postflop
    "vbet_eq": 0.62,
    "vbet_frac": 0.65,
    "bluff_freq": 0.25,
    "bluff_max_eq": 0.35,
    "bluff_frac": 0.5,
    "raise_eq": 0.80,
    "raise_frac": 0.8,
    "call_margin": 0.03,
    "realize": 0.95,
    "tighten": 0.35,          # per opponent bet/raise: eq -> eq ** (1 + tighten * w)
    "commit_spr": 1.2,
    "commit_eq": 0.55,
    "bust_tax": 0.04,         # extra equity when a call risks elimination (no ICM tables)
    "icm_weight": 1.0,        # 0 = chip EV, 1 = full ICM bubble factor on every call
    # postflop EV engine (needs the range MLP; see _postflop_ev)
    "ev_post": 1.0,           # >= 0.5: EV engine, else the threshold rules above
    "rng_mix": 0.0,           # rules mode: weight of equity vs read ranges (vs the tighten hack)
    "rng_y_scale": 1.0,       # scales preflop range widths read from VPIP/PFR
    "rng_bet_scale": 1.0,     # scales how much a bet/raise narrows the range (1 = bet rate)
    "rng_check_cap": 0.6,     # share of the betting range a check removes
    "rng_call_cut": 0.5,      # share of the raising range a call removes
    "rng_persist": 0.75,      # how much of a street's narrowing survives the next card
    # continue prob vs our bet: sigmoid(b0 + b1 logit(c_stat) + b2 log(po / PO_REF)
    #                                   + b3 [bet this street] + b4 range midpoint)
    "cont_b0": 0.0, "cont_b1": 1.0, "cont_b2": -0.7, "cont_b3": 0.0, "cont_b4": 0.0,
    "call_width": 1.0,        # callers hold the top min(1, c * call_width) of their range
    "raise_cont": 1.0,        # extra continue rate when we raise a bettor
    "realize_chk": 0.9,       # equity realized by checking
    "ev_margin": 0.0,         # pot fraction a bet must beat checking by
    "call_ev_margin": 0.0,    # share of the call a call must win back over folding
    "risk_av": 0.0,           # survival premium over ICM: losses x (1 + risk_av * share of stack)^2
    "risk_depth": 0.0,        # premium fades below this many big blinds (0 = never fades)
    "pool_w": 0.0,            # unknown seats start from the table's pooled stats (0 = fixed PRIORS)
}

PARAM_SPACE = {
    "open_base": (0.04, 0.30), "open_late": (0.15, 0.70), "open_bb": (2.0, 4.0),
    "steal_exploit": (0.0, 2.5),
    "iso_pct": (0.05, 0.35), "sb_complete_pct": (0.0, 0.8), "reraise_eq": (0.5, 0.8),
    "reraise_mult": (2.2, 4.5), "pre_realize": (0.7, 1.1), "pre_tighten": (0.2, 0.9),
    "pf_bb": (6.0, 25.0), "pf_shove_scale": (0.5, 1.8), "pf_call_scale": (0.5, 1.8),
    "pf_exploit": (0.0, 2.5), "pf_margin": (-0.05, 0.10),
    "vbet_eq": (0.5, 0.8), "vbet_frac": (0.3, 1.2), "bluff_freq": (0.0, 0.6),
    "bluff_max_eq": (0.1, 0.5), "bluff_frac": (0.3, 1.0), "raise_eq": (0.65, 0.95),
    "raise_frac": (0.5, 1.5), "call_margin": (-0.05, 0.12), "realize": (0.75, 1.1),
    "tighten": (0.0, 1.0), "commit_spr": (0.3, 3.0), "commit_eq": (0.4, 0.75),
    "bust_tax": (0.0, 0.12), "icm_weight": (0.0, 1.5),
    "ev_post": (0.0, 1.0), "rng_mix": (0.0, 1.0), "rng_y_scale": (0.5, 3.0), "rng_bet_scale": (0.4, 2.0),
    "rng_check_cap": (0.0, 1.0), "rng_call_cut": (0.0, 1.0), "rng_persist": (0.3, 1.0),
    "cont_b0": (-2.0, 2.0), "cont_b1": (0.0, 2.0), "cont_b2": (-4.0, 0.0), "cont_b3": (-1.0, 3.0),
    "cont_b4": (-3.0, 3.0), "call_width": (0.5, 2.5), "raise_cont": (0.5, 1.6),
    "realize_chk": (0.6, 1.1), "ev_margin": (-0.05, 0.2), "call_ev_margin": (-0.1, 0.4),
    "risk_av": (0.0, 3.0), "risk_depth": (0.0, 60.0), "pool_w": (0.0, 1.0),
}
# The EV engine is a mode switch, not something to search over.
TUNE_EXCLUDE = ("ev_post",)
POST_SIZES = (0.33, 0.66, 1.0, 1.5)    # bet sizes, fractions of the pot
RAISE_SIZES = (0.8, 1.3)               # raise sizes, fractions of the pot after calling
PO_REF = 0.65 / 2.3                    # pot odds of the 0.65-pot bets the stats mostly see
# The limit is 1 ms per decision. Past this many seconds into a decision the EV engine stops
# trying raise sizes and returns the best action found so far (check/call/fold always exist).
DEADLINE_S = float(os.environ.get("NOLIMIT_DEADLINE_MS", "0.6")) / 1000.0
# warmup() switches to the small models when the big ones take longer than this per decision.
NET_BUDGET_S = 0.15 / 1000.0


def _clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def legalize(obs, action):
    """Last line of defense: whatever the strategy said, return a legal action."""
    kind, amt = action
    if kind == FOLD:
        return (CALL, 0) if obs.to_call <= 0 else (FOLD, 0)
    if kind == RAISE:
        if obs.min_raise_to <= 0:
            return (CALL, 0)
        return (RAISE, int(_clamp(int(amt), obs.min_raise_to, max(obs.max_raise_to, obs.min_raise_to))))
    return (CALL, 0)


class PrepBot(BotBase):
    deadline = DEADLINE_S      # simulations set this off (nolimit/harness.py) so play is reproducible

    def __init__(self, tables, params=None, seed=None, debug=False):
        self.T = tables
        self.p = dict(DEFAULT_PARAMS)
        if params:
            self.p.update(params)
        # Optional per-table param sets ("arms"). After `from_hand` hands the bot plays the arm
        # with the highest predicted gain from a linear rule on what the other seats did, or
        # stays on the base params if none is > 0 (rules fitted by scripts/switch_study.py):
        # {"from_hand": n, "mu": {...}, "sd": {...}, "arms": [{"params": {...}, "beta": {...}}]}
        alt = self.p.pop("alt", None)
        # Optional per-opponent exploitation (rule fitted by scripts/fit_exploit.py):
        # {"params": {...}, "feats": [...], "mu": [...], "sd": [...], "beta": [...], "h0": n}.
        # Each villain gets lam = P(exploitable | its stats) * hands / (hands + h0); a decision
        # plays base + lam * (exploit - base) with the smallest lam among the villains still in
        # the hand, so the bot exploits only when everyone it is up against looks exploitable.
        ex = self.p.pop("exploit", None)
        self._ex = ex
        if ex:
            assert tuple(ex["feats"]) == EXPLOIT_FEATS, "exploit rule fitted on other features"
            # z = b0 + sum(bl * v + bq * v^2), v = (r - mu) / sd, expanded into a + b*r per rate.
            k, beta = len(ex["mu"]), ex["beta"]
            c0, ab = beta[0], []
            for i, (m, s) in enumerate(zip(ex["mu"], ex["sd"])):
                bl, bq = beta[1 + i], beta[1 + k + i]
                c0 += -bl * m / s + bq * m * m / (s * s)
                ab.append((bl / s - 2 * bq * m / (s * s), bq / (s * s)))
            self._ex_coef = (c0, tuple(ab))
            tgt = dict(self.p, **ex["params"])
            self._ex_levels = [{k: (1 - t) * v + t * tgt[k] if isinstance(v, float) else (tgt[k] if t >= 0.5 else v)
                                for k, v in self.p.items()}
                               for t in (i / (EXPLOIT_LEVELS - 1) for i in range(EXPLOIT_LEVELS))]
        self._p_base = self.p
        self._rule = alt
        self._arms = [dict(self.p, **a["params"]) for a in alt["arms"]] if alt else []
        self.rng = random.Random(seed)
        self.debug = debug
        self._t0 = time.perf_counter()
        self.deadline_hits = 0
        self.new_table(0, 8)

    def new_table(self, seat, n_seats, _collect=True):
        if _collect and _GC_CONTROL:
            # Table start is outside any decision: clear the last table's garbage here, so
            # the collector (disabled or rarely triggered, see gc_settle) never runs mid-act.
            gc.collect()
            gc.freeze()
        self.seat = seat
        self.p = self._p_base
        self.view, self.arm = None, -1       # table features at the switch point, arm played
        self.stats = [SeatStats() for _ in range(n_seats)]
        self._hand_key = None    # (hand_no, hole): works even if the host gives no hand id
        self._hist = ()
        self._ingested = set()   # hand_no values the host already reported via hand_end
        self._ingested_keys = set()
        self._cls = None
        self._ex_cache = {}      # seat -> (hands seen, lam) for the exploitation rule

    def observe(self, event):
        kind, info = event
        if kind == "hand_end" and info["hand_no"] not in self._ingested:
            self._ingested.add(info["hand_no"])
            ingest_history(self.stats, info["history"])
            pool_priors(self.stats, self.seat, self.p["pool_w"])
            if self._rule:
                self._choose_params()

    def act(self, obs):
        self._t0 = time.perf_counter()
        try:
            return legalize(obs, self._act(obs))
        except Exception:
            if self.debug:
                raise
            return (CALL, 0) if obs.to_call == 0 else (FOLD, 0)

    # -----------------------------------------------------------------------
    def _act(self, obs):
        if len(self.stats) != len(obs.stacks):
            self.new_table(obs.seat, len(obs.stacks), _collect=False)   # timed path: no gc
        key = (obs.hand_no, tuple(obs.hole))
        if key != self._hand_key:
            # Fall back to our own partial view if the host never sent hand_end.
            prev = self._hand_key
            if prev is not None and prev[0] not in self._ingested and prev not in self._ingested_keys:
                self._ingested_keys.add(prev)
                ingest_history(self.stats, self._hist)
                pool_priors(self.stats, self.seat, self.p["pool_w"])
                if self._rule:
                    self._choose_params()
            self._hand_key = key
            self._cls = self.T.hole_class(obs.hole)
        self._hist = obs.history
        self.seat = obs.seat
        if self._ex:
            self.p = self._ex_levels[self._ex_level(obs)]
        if obs.street == 0:
            return self._preflop(obs)
        return self._postflop(obs)

    def _ex_level(self, obs):
        lam = 1.0
        for s, live in enumerate(obs.in_hand):
            if live and s != obs.seat:
                lam = min(lam, self._ex_lam(s))
                if lam <= 0.0:
                    break
        return int(lam * (EXPLOIT_LEVELS - 1) + 0.5)

    def _ex_lam(self, s):
        st = self.stats[s]
        got = self._ex_cache.get(s)
        if got is not None and got[0] == st.hands:
            return got[1]
        c = self._ex_coef
        z = c[0]
        for (a, b), r in zip(c[1], _ex_rates(st)):
            z += r * (a + b * r)
        lam = 0.0 if z < -30 or not st.hands else st.hands / (st.hands + self._ex["h0"]) / (1.0 + math.exp(-z))
        self._ex_cache[s] = (st.hands, lam)
        return lam

    def table_view(self):
        """Mean VPIP, PFR, aggression and fold-to-bet of the other seats seen so far, and the
        share of them that never voluntarily played. None before anyone was seen."""
        opp = [st for i, st in enumerate(self.stats) if i != self.seat and st.hands > 0]
        if not opp:
            return None
        f = {k: sum(st.rate(k) for st in opp) / len(opp) for k in ("vpip", "pfr", "agg", "fold_to_bet")}
        f["never"] = sum(st.hands >= 5 and st.vpip == 0 for st in opp) / len(opp)
        return f

    def _choose_params(self):
        """Once, at `from_hand` hands seen: the arm with the highest predicted gain, if > 0."""
        r = self._rule
        if len(self._ingested) + len(self._ingested_keys) != r["from_hand"]:
            return
        self.view = f = self.table_view()
        if f is None:
            return
        best = 0.0
        for i, arm in enumerate(r["arms"]):
            b = arm["beta"]
            z = b["const"] + sum(b[k] * (f[k] - r["mu"][k]) / r["sd"][k] for k in r["mu"])
            if z > best:
                best, self.arm = z, i
        if self.arm >= 0:
            self.p = self._arms[self.arm]

    def _raise(self, obs, target):
        if obs.min_raise_to <= 0:
            return (CALL, 0)
        amt = max(obs.min_raise_to, int(target))
        if amt >= obs.max_raise_to * 0.85:
            amt = obs.max_raise_to
        return (RAISE, min(amt, obs.max_raise_to))

    def _shove(self, obs):
        if obs.min_raise_to <= 0:
            return (CALL, 0)
        return (RAISE, obs.max_raise_to)

    def _aggressor(self, obs):
        """Seat whose bet we face: last raiser this street, else the biggest bet."""
        for seat, st, kind, _amt, _ai in reversed(obs.history):
            if st == obs.street and kind == RAISE and seat != obs.seat:
                return seat
        return max((s for s in range(len(obs.bets)) if s != obs.seat), key=lambda s: obs.bets[s])

    def _need(self, obs, villain, fallback):
        """Equity needed to call: BF*c / (BF*c + pot) with the ICM bubble factor.

        Falls back to `fallback` (chip-EV pot odds + bust tax) without ICM tables.
        """
        c = obs.to_call
        n_alive = sum(1 for s in range(len(obs.stacks)) if obs.stacks[s] + obs.bets[s] > 0 or obs.in_hand[s])
        total = sum(obs.stacks) + max(obs.pot, sum(obs.bets))
        me = obs.seat
        mine = obs.stacks[me] + obs.bets[me]
        theirs = obs.stacks[villain] + obs.bets[villain]
        eff = min(mine, theirs)
        bf = None
        if total > 0 and eff > 0:
            bf = self.T.bubble_factor(n_alive, mine / total, theirs / total, c / eff)
        if bf is None:
            if fallback is not None:
                return fallback
            bf = 1.0
        bf = 1.0 + self.p["icm_weight"] * (bf - 1.0)
        return bf * c / max(bf * c + obs.pot, 1)

    def _check_fold(self, obs):
        return (CALL, 0) if obs.to_call == 0 else (FOLD, 0)

    def _action_order(self, obs):
        """Preflop action order of the seats dealt in (first to act ... big blind)."""
        n_seats = len(obs.stacks)
        posts = [h[0] for h in obs.history if h[2] == POST]
        dealt = {h[0] for h in obs.history}
        dealt.update(i for i in range(n_seats) if obs.in_hand[i])
        if len(posts) >= 2:
            bb_seat = posts[1]
        elif posts:
            bb_seat = posts[0]
        else:
            bb_seat = obs.button
        order = []
        for k in range(1, n_seats + 1):
            s = (bb_seat + k) % n_seats
            if s in dealt:
                order.append(s)
        return order

    def _preflop(self, obs):
        p, T, me = self.p, self.T, obs.seat
        cls = self._cls
        pct = T.pct(cls)
        opps = [s for s in range(len(obs.stacks)) if obs.in_hand[s] and s != me]
        if not opps:
            return (CALL, 0)
        my_total = obs.stacks[me] + obs.bets[me]
        eff = min(my_total, max(obs.stacks[s] + obs.bets[s] for s in opps))
        eff_bb = eff / max(obs.bb, 1)
        raises = [h for h in obs.history if h[1] == 0 and h[2] == RAISE]
        order = self._action_order(obs)
        if eff_bb <= p["pf_bb"]:
            return self._pushfold(obs, cls, pct, order, raises, eff_bb)

        pos = order.index(me) if me in order else 0
        behind = [s for s in order[pos + 1:] if obs.in_hand[s] and obs.stacks[s] > 0]
        cur_bet = max(obs.bets)
        if not raises:
            limpers = sum(1 for h in obs.history if h[1] == 0 and h[2] == CALL and h[3] > 0)
            if obs.to_call == 0:
                return self._raise(obs, 3 * obs.bb + limpers * obs.bb) if pct <= p["iso_pct"] else (CALL, 0)
            n_others = max(len(order) - 1, 1)
            thr = p["open_base"] + (p["open_late"] - p["open_base"]) * (1 - len(behind) / n_others)
            if limpers:
                thr = p["iso_pct"]
            if behind:
                # Steal wider when the players left to act rarely play (crashed bots fold).
                vp = sum(self.stats[s].rate("vpip") for s in behind) / len(behind)
                thr = min(1.0, thr * (PRIORS["vpip"] / max(vp, 0.05)) ** (0.5 * p["steal_exploit"]))
            if pct <= thr:
                return self._raise(obs, p["open_bb"] * obs.bb + limpers * obs.bb)
            if limpers == 0 and obs.to_call <= obs.bb // 2 + 1 and pct <= p["sb_complete_pct"]:
                return (CALL, 0)
            return (FOLD, 0)

        raiser = raises[-1][0]
        y = self.stats[raiser].rate("pfr") * (p["pre_tighten"] ** (len(raises) - 1))
        if raises[-1][4]:
            y = min(y, self.stats[raiser].rate("shove") * 2.5)
        y = _clamp(y, 0.01, 1.0)
        eq = T.eq_vs_range(cls, y)
        n_live = len(opps)
        if n_live > 1:
            eq = eq ** (1 + 0.6 * (n_live - 1))
        pot_odds = obs.to_call / max(obs.pot + obs.to_call, 1)
        risk = obs.to_call >= obs.stacks[me]
        if eq >= p["reraise_eq"] and len(raises) < 4 and obs.min_raise_to > 0:
            target = cur_bet * p["reraise_mult"]
            if target >= 0.35 * my_total:
                return self._shove(obs)
            return self._raise(obs, target)
        if eq * p["pre_realize"] >= self._need(obs, raiser, pot_odds + (p["bust_tax"] if risk else 0.0)):
            return (CALL, 0)
        return (FOLD, 0)

    def _pushfold(self, obs, cls, pct, order, raises, eff_bb):
        p, T, me = self.p, self.T, obs.seat
        n = len(order)
        pos = order.index(me) if me in order else 0
        if not raises:
            behind = [s for s in order[pos + 1:] if obs.in_hand[s]]
            thr = T.shove_threshold(n, pos, eff_bb)
            if thr is None:
                # No chart: shove wider the shorter we are and the fewer players behind.
                thr = _clamp(0.9 / (1 + 0.35 * len(behind)) * (6.0 / max(eff_bb, 1.0)) ** 0.5, 0.03, 1.0)
            if behind:
                call_rate = sum(self.stats[s].rate("vpip") for s in behind) / len(behind)
                thr *= (PRIORS["vpip"] / max(call_rate, 0.05)) ** (0.5 * p["pf_exploit"])
            thr = _clamp(thr * p["pf_shove_scale"], 0.0, 1.0)
            if obs.to_call == 0:
                # Limped to the big blind: shove for value only.
                return self._shove(obs) if pct <= thr * 0.6 else (CALL, 0)
            if pct <= thr:
                return self._shove(obs)
            return (FOLD, 0)

        shover = raises[-1][0]
        spos = order.index(shover) if shover in order else 0
        need = self._need(obs, shover, None) + p["pf_margin"]
        if obs.to_call >= obs.stacks[me] and not getattr(T, "has_bf", False):
            need += p["bust_tax"]   # the bubble factor already prices elimination risk
        st = self.stats[shover]
        thr = T.call_threshold(n, spos, pos, eff_bb)
        if thr is None or st.hands >= 12:
            # Enough reads (or no chart): call on equity vs the shover's estimated range.
            y = _clamp(max(st.rate("shove"), st.rate("pfr") * 0.8) * 1.5, 0.02, 1.0)
            call = T.eq_vs_range(cls, y) >= need
        else:
            call = pct <= thr * p["pf_call_scale"]
        n_in = sum(1 for s in order if obs.in_hand[s] and s != me)
        if n_in > 1:
            call = call and T.eq_vs_range(cls, 0.08) >= 0.5
        if not call:
            return (FOLD, 0)
        return self._shove(obs) if obs.min_raise_to > 0 else (CALL, 0)

    def _postflop(self, obs):
        if self.T.has_rng and self.p["ev_post"] >= 0.5:
            return self._postflop_ev(obs)
        return self._postflop_rules(obs)

    def _postflop_rules(self, obs):
        p, T, me = self.p, self.T, obs.seat
        opps = [s for s in range(len(obs.stacks)) if obs.in_hand[s] and s != me]
        if not opps:
            return (CALL, 0)
        e = T.post_equity(obs.hole, obs.board)
        n = len(opps)
        eq = e[n - 1] if n <= 3 else e[2] ** (n / 3.0)
        aggr = 0.0
        for seat, st, kind, _amt, _ai in obs.history:
            if st > 0 and kind == RAISE and seat != me:
                aggr += _clamp(PRIORS["agg"] / max(self.stats[seat].rate("agg"), 0.05), 0.4, 2.0)
        eq = eq ** (1 + p["tighten"] * aggr)
        if p["rng_mix"] > 0 and T.has_rng:
            # Blend in equity vs each opponent's range as read from this hand's actions.
            curve = T.post_curve(obs.hole, obs.board)
            corr = (e[min(n, 3) - 1] / max(e[0] ** min(n, 3), 1e-6)) ** (1.0 / min(n, 3)) if n > 1 else 1.0
            er = 1.0
            for s in opps:
                y = self._pre_y(s, obs.history)
                a, b, _ag = self._post_slice(s, obs.history, obs.street)
                er *= min(1.0, T.interval_equity(curve, y, a, b) * corr)
            eq = (1.0 - p["rng_mix"]) * eq + p["rng_mix"] * er
        pot = obs.pot
        my_stack = obs.stacks[me]
        my_total = my_stack + obs.bets[me]
        cur_bet = max(obs.bets)
        if obs.to_call == 0:
            if eq >= p["vbet_eq"]:
                if my_stack <= p["commit_spr"] * pot and eq >= p["commit_eq"]:
                    return self._shove(obs)
                return self._raise(obs, p["vbet_frac"] * pot)
            if n <= 2 and eq <= p["bluff_max_eq"]:
                folds = sum(self.stats[s].rate("fold_to_bet") for s in opps) / n
                if self.rng.random() < p["bluff_freq"] * folds / PRIORS["fold_to_bet"] / n:
                    return self._raise(obs, p["bluff_frac"] * pot)
            return (CALL, 0)
        pot_odds = obs.to_call / max(pot + obs.to_call, 1)
        if eq >= p["raise_eq"] and obs.min_raise_to > 0:
            target = cur_bet + p["raise_frac"] * (pot + obs.to_call)
            if target >= 0.4 * my_total or my_stack <= p["commit_spr"] * pot:
                return self._shove(obs)
            return self._raise(obs, target)
        need = self._need(obs, self._aggressor(obs), pot_odds + (p["bust_tax"] if obs.to_call >= my_stack else 0.0))
        need += p["call_margin"]
        if eq * p["realize"] >= need:
            return (CALL, 0)
        return (FOLD, 0)

    # -- postflop EV engine ---------------------------------------------------
    def _pre_y(self, s, hist):
        """Preflop range width of seat s this hand, as a top fraction of hands."""
        p, st = self.p, self.stats[s]
        y = 1.0
        n_raises = 0
        bets = {}
        for seat, street, kind, amt, ai in hist:
            if street != 0:
                break
            if kind == POST:
                bets[seat] = amt
                continue
            prev = bets.get(seat, 0)
            if kind == RAISE:
                n_raises += 1
                if seat == s:
                    yr = st.rate("pfr") * p["pre_tighten"] ** (n_raises - 1)
                    if ai:
                        yr = min(yr, st.rate("shove") * 2.5)
                    y = min(y, yr)
            elif kind == CALL and seat == s and amt > prev:
                y = min(y, st.rate("vpip") * p["pre_tighten"] ** max(n_raises - 1, 0))
            if kind in (CALL, RAISE):
                bets[seat] = amt
        return _clamp(y * p["rng_y_scale"], 0.02, 1.0)

    def _post_slice(self, s, hist, street_now):
        """Slice [a, b] of seat s's range (0 = strongest) implied by its postflop actions,
        and whether s has bet or raised on the current street."""
        p, st = self.p, self.stats[s]
        g_bet = _clamp(st.rate("bet") * p["rng_bet_scale"], 0.03, 1.0)
        g_raise = _clamp(st.rate("raise") * p["rng_bet_scale"], 0.02, 1.0)
        cont = _clamp(1.0 - st.rate("fold_nb"), 0.05, 1.0)
        a, b = 0.0, 1.0
        street = 0
        bets = {}
        cur = 0
        aggr = False
        for seat, stt, kind, amt, _ai in hist:
            if stt == 0:
                continue
            if stt != street:
                if street > 0:      # a new card reshuffles part of the ranking
                    k = p["rng_persist"]
                    a, b = a * k, 1.0 - (1.0 - b) * k
                street = stt
                bets = {}
                cur = 0
            prev = bets.get(seat, 0)
            if seat == s:
                w = b - a
                if kind == RAISE:
                    b = a + w * (g_raise if cur > prev else g_bet)
                    aggr = stt == street_now
                elif kind == CALL:
                    if cur > prev:
                        a, b = a + w * g_raise * p["rng_call_cut"], a + w * max(cont, g_raise)
                    else:
                        a = a + w * g_bet * p["rng_check_cap"]
            if kind == RAISE:
                cur = amt
            if kind in (CALL, RAISE):
                bets[seat] = amt
        if street != street_now and street > 0:
            k = p["rng_persist"]
            a, b = a * k, 1.0 - (1.0 - b) * k
        return a, b, aggr

    def _cont(self, s, po, rng):
        """Probability seat s continues (calls or raises) facing pot odds po."""
        p = self.p
        _y, a, b, ag = rng
        c0 = _clamp(1.0 - self.stats[s].rate("fold_ab" if ag else "fold_nb"), 0.01, 0.99)
        z = (p["cont_b0"] + p["cont_b1"] * math.log(c0 / (1.0 - c0))
             + p["cont_b2"] * math.log(max(po, 0.01) / PO_REF) + p["cont_b3"] * ag + p["cont_b4"] * (a + b) / 2)
        return 1.0 / (1.0 + _exp(-z))

    def _postflop_ev(self, obs):
        """Pick the action with the highest ICM-weighted chip EV.

        Each opponent's range is a slice of their preflop range (read off VPIP/PFR and
        this hand's actions); the range MLP gives our equity against any slice. A bet of
        size B gets a continue rate per opponent from their fold-to-bet rate, scaled by
        pot odds, and is called by the top of that opponent's slice. Losses are weighted
        by the ICM bubble factor.
        """
        p, T, me = self.p, self.T, obs.seat
        opps = [s for s in range(len(obs.stacks)) if obs.in_hand[s] and s != me]
        if not opps:
            return (CALL, 0)
        curve = T.post_curve(obs.hole, obs.board)
        n = len(opps)
        corr = 1.0
        if n > 1:
            # Multiway: equities vs each range don't simply multiply; correct by how equity vs
            # n random hands compares to (equity vs one)^n. Heads-up doesn't need this model.
            e = T.post_equity(obs.hole, obs.board)
            erand = e[n - 1] if n <= 3 else e[2] ** (n / 3.0)
            corr = (erand / max(e[0] ** n, 1e-6)) ** (1.0 / n)
        real = 1.0 if len(obs.board) >= T.v.n_board else p["realize"]
        hist = obs.history
        rngs = {s: (self._pre_y(s, hist),) + self._post_slice(s, hist, obs.street) for s in opps}

        def eq_vs(s, frac=1.0):
            y, a, b, _ag = rngs[s]
            return min(1.0, T.interval_equity(curve, y, a, a + (b - a) * frac) * corr)

        P = obs.pot
        bets, stacks = obs.bets, obs.stacks
        my_bet = bets[me]
        total = sum(stacks) + max(P, sum(bets))
        mine = stacks[me] + my_bet
        n_alive = sum(1 for s in range(len(stacks)) if stacks[s] + bets[s] > 0 or obs.in_hand[s])
        big = max(opps, key=lambda s: stacks[s] + bets[s])
        theirs = stacks[big] + bets[big]
        eff = max(min(mine, theirs), 1)
        w_icm = p["icm_weight"]

        # Surviving protects our edge over future hands; short stacks have few left to protect.
        ra = p["risk_av"]
        if p["risk_depth"] > 0:
            ra *= min(1.0, mine / max(obs.bb, 1) / p["risk_depth"])

        def bf(risk):
            """Weight on a chip lost: ICM bubble factor, plus a premium for staying alive
            (ICM assumes equal skill; an edge over the field makes busting cost more)."""
            if risk <= 0 or total <= 0:
                return 1.0
            prem = (1.0 + ra * min(risk / max(mine, 1), 1.0)) ** 2
            v = T.bubble_factor(n_alive, mine / total, theirs / total, risk / eff)
            if v is None:
                return prem * (1.0 + (p["bust_tax"] * 10 if risk >= stacks[me] else 0.0))
            return prem * (1.0 + w_icm * (v - 1.0))

        facing = obs.to_call > 0
        cmul = p["raise_cont"] if facing else 1.0

        def ev_raise(R):
            R = min(R, max(stacks[s] + bets[s] for s in opps))   # excess comes back
            A = max(R - my_bet, 0)
            pot_after = P + A
            W = 1.0
            parts = []
            dbg = []
            for s in opps:
                d = max(min(R, stacks[s] + bets[s]) - bets[s], 0)
                if d <= 0 or stacks[s] == 0:
                    c = 1.0
                else:
                    po = d / max(pot_after + d, 1)
                    c = _clamp(self._cont(s, po, rngs[s]) * cmul, 0.02, 1.0)
                q = eq_vs(s, min(1.0, c * p["call_width"])) * real
                w = (1.0 - c) + c * q
                W *= w
                parts.append((c * q * d, w))
                if self.debug:
                    dbg.append((c, q))
            gain = P * W + sum(cq * W / max(w, 1e-9) for cq, w in parts)
            if self.debug:
                fold_all = 1.0
                for c, _q in dbg:
                    fold_all *= 1.0 - c
                sc = sum(c for c, _q in dbg)
                self._ev_dbg[R] = (fold_all, sum(c * q for c, q in dbg) / max(sc, 1e-9))
            return gain - A * (1.0 - W) * bf(A)

        W_now = 1.0
        for s in opps:
            W_now *= eq_vs(s) * real
        if self.debug:
            self._ev_dbg = {}
        can_raise = obs.min_raise_to > 0
        best_ev, best = None, None
        if not facing:
            best_ev, best = P * W_now * p["realize_chk"] + p["ev_margin"] * P, (CALL, 0)
            alt_ev = best_ev - p["ev_margin"] * P
            targets = [my_bet + f * P for f in POST_SIZES]
        else:
            A = min(obs.to_call, stacks[me])
            best_ev, best = 0.0, (FOLD, 0)
            ev_call = P * W_now - A * (1.0 - W_now) * bf(A) - p["call_ev_margin"] * A
            if ev_call > best_ev:
                best_ev, best = ev_call, (CALL, 0)
            alt_ev = ev_call
            cur = max(bets)
            targets = [cur + f * (P + obs.to_call) for f in RAISE_SIZES]
        if can_raise:
            seen = set()
            for R in targets + [obs.max_raise_to]:
                R = int(_clamp(R, obs.min_raise_to, obs.max_raise_to))
                if R >= 0.85 * obs.max_raise_to:
                    R = obs.max_raise_to
                if R in seen:
                    continue
                if time.perf_counter() - self._t0 > self.deadline:
                    self.deadline_hits += 1
                    break
                seen.add(R)
                v = ev_raise(R)
                if v > best_ev:
                    best_ev, best = v, (RAISE, R)
        if self.debug:
            dbg = self._ev_dbg.get(best[1]) if best[0] == RAISE else None
            self.trace = {"W_now": W_now, "eq": {s: eq_vs(s) for s in opps}, "best": best, "dbg": dbg,
                          "best_ev": best_ev, "alt_ev": alt_ev,
                          "pfold": dbg[0] if dbg else None, "qcall": dbg[1] if dbg else None,
                          "rngs": rngs, "real": real}
        return best


_GC_CONTROL = False


def gc_settle(mode="off"):
    """Keep the cyclic garbage collector out of decisions. Call once after warmup().

    Collects and freezes everything allocated so far (the tables, caches and module state
    move to the permanent generation, so they are never scanned again), then either
    disables automatic collection ("off") or makes it rare ("threshold"). From then on every
    PrepBot built or reset by the host (new_table) runs gc.collect() + gc.freeze() first,
    which is outside the timed act() path; that bounds what one table can leave behind.
    """
    global _GC_CONTROL
    gc.collect()
    gc.freeze()
    if mode == "off":
        gc.disable()
    elif mode == "threshold":
        gc.set_threshold(50000, 50, 50)
    _GC_CONTROL = True


def embedded_bundle_bytes(b64):
    return base64.b64decode(b64)


def warmup(tables, decisions=300, seed=12345):
    """Run synthetic decisions so the first real ones don't pay for cold caches.

    Measured: without this, the first decisions in a fresh process can take 1-6 ms.
    """
    v = tables.v
    rng = random.Random(seed)
    bot = PrepBot(tables, seed=seed)
    for i in range(decisions):
        seats = rng.choice((2, 4, 8))
        me = rng.randrange(seats)
        street = i % (len(v.streets) + 1)
        cards = rng.sample(range(v.D), v.n_hole + sum(v.streets[:street]))
        bb = 20
        bets = [0] * seats
        to_call = rng.choice((0, bb, 4 * bb))
        bets[(me + 1) % seats] = to_call
        hist = (((me + 1) % seats, 0, POST, bb // 2, False), ((me + 2) % seats, 0, POST, bb, False))
        if to_call:
            hist += (((me + 1) % seats, street, RAISE, to_call, False),)
        stack = rng.choice((5, 15, 100)) * bb
        obs = Obs(hole=tuple(cards[:v.n_hole]), board=tuple(cards[v.n_hole:]), street=street, seat=me,
                  button=(me + seats - 1) % seats, stacks=tuple([stack] * seats), bets=tuple(bets),
                  in_hand=tuple([True] * seats), pot=3 * bb + to_call, to_call=to_call,
                  min_raise_to=to_call + bb if to_call else bb, max_raise_to=stack, sb=bb // 2, bb=bb,
                  ante=0, hand_no=-1 - i, history=hist)
        bot.act(obs)
    calibrate_nets(tables, rng)
    if hasattr(tables, "_post_cache"):
        tables._post_cache.clear()


def calibrate_nets(tables, rng=None, reps=40):
    """Time the big models on this machine; use the small ones if the big ones are too slow.

    The time limit is per decision on hardware we can't see in advance. A decision on a new
    street runs both models once, so their combined cost is what matters. NOLIMIT_NETS=big
    or =small overrides the measurement. Returns the choice."""
    if not hasattr(tables, "select_nets") or not getattr(tables, "_spare", None):
        return None
    forced = os.environ.get("NOLIMIT_NETS")
    if forced in ("big", "small"):
        tables.select_nets(forced)
        tables.net_choice = (forced, None)
        return forced
    rng = rng or random.Random(7)
    v = tables.v
    tables.select_nets("big")
    samples = []
    for _ in range(reps):
        cards = rng.sample(range(v.D), v.n_hole + sum(v.streets))
        f = postflop_features(v, tables.ev, tables.windows, cards[:v.n_hole], cards[v.n_hole:])
        t0 = time.perf_counter()
        tables._mlp_forward(f)
        if tables.has_rng:
            tables._mlp_forward(f, tables.rng_net)
        samples.append(time.perf_counter() - t0)
    samples.sort()
    cost = samples[int(0.9 * (len(samples) - 1))]      # 90th percentile, robust to one hiccup
    choice = "big" if cost <= NET_BUDGET_S else "small"
    tables.select_nets(choice)
    tables.net_choice = (choice, cost * 1000.0)
    return choice

"""Vectorized torch mirror of nolimit.runtime's evaluator and features (CUDA, MPS or CPU)."""
import gc
import itertools
import math
import os

import torch

from nolimit.runtime import (FIVE_KIND, FLUSH, FULL_HOUSE, HIGH, N_CATEGORIES, PAIR, QUADS,
                             STRAIGHT, STRAIGHT_FLUSH, TRIPS, TWO_PAIR, feature_dim, get_variant,
                             straight_windows)

DEVICE_ENV = "NOLIMIT_DEVICE"        # cpu | mps | cuda | auto
THREADS_ENV = "NOLIMIT_THREADS"      # torch CPU threads (default: torch's own choice)
EVAL_BATCH_ENV = "NOLIMIT_EVAL_BATCH"
# 5-card hands per eval5 call. eval5 keeps ~0.5 KB of intermediates per hand (the 5x5
# rank-count matrix dominates), so 1M hands is a few hundred MB whatever the chunk size.
DEFAULT_EVAL_BATCH = 1 << 20
# best() looks 5-card values up in a table of all C(D, 5) hands (built once with eval5;
# 21 MB for 52 cards), several times faster than eval5 on CPU. NOLIMIT_EVAL_LUT=0 disables it.
LUT_ENV = "NOLIMIT_EVAL_LUT"
LUT_MAX = 8_000_000


def pick_device(name="auto", log=None):
    """--device beats $NOLIMIT_DEVICE beats auto. auto = CUDA if present, else CPU.

    MPS is opt-in (--device mps or NOLIMIT_DEVICE=mps): it shares unified memory with
    everything else on the Mac, and with other jobs running it ran out of memory mid-build.
    A device that is asked for but missing falls back to CPU with a warning.
    """
    name = (name or "auto").lower()
    if name == "auto":
        name = (os.environ.get(DEVICE_ENV) or "auto").lower()
    if name == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ok = {"cuda": torch.cuda.is_available, "mps": torch.backends.mps.is_available}.get(
        name.split(":")[0], lambda: True)
    if not ok():
        (log or print)(f"device {name} not available, using cpu")
        return torch.device("cpu")
    return torch.device(name)


def set_threads(n=None):
    """Cap torch's CPU threads (n, else $NOLIMIT_THREADS); returns the count in effect."""
    n = n or int(os.environ.get(THREADS_ENV) or 0)
    if n > 0:
        torch.set_num_threads(n)
    return torch.get_num_threads()


def is_oom(exc):
    oom = getattr(torch, "OutOfMemoryError", None)
    return (oom is not None and isinstance(exc, oom)) or (
        isinstance(exc, RuntimeError) and "out of memory" in str(exc).lower())


def free_device_memory(dev):
    gc.collect()
    if dev.type == "mps":
        torch.mps.empty_cache()
    elif dev.type == "cuda":
        torch.cuda.empty_cache()


def run_with_fallback(fn, dev, log=print):
    """fn(dev); if a CUDA/MPS device runs out of memory, free it and run fn(cpu) once.

    fn should skip work it already finished (build_tables keeps the stages done in this run).
    """
    if dev.type == "cpu":
        return fn(dev)
    try:
        return fn(dev)
    except Exception as e:  # noqa: BLE001 - only OOM is handled, the rest is re-raised
        if not is_oom(e):
            raise
        msg = str(e).splitlines()[0][:200]
    # Outside the except block, so the traceback (and the device tensors it pins) is gone.
    log(f"{dev} out of memory ({msg}); continuing on cpu")
    free_device_memory(dev)
    return fn(torch.device("cpu"))


class TorchEval:
    def __init__(self, variant, device, eval_batch=None, use_lut=None):
        v = self.v = get_variant(variant)
        self.dev = device
        self.eval_batch = int(eval_batch or os.environ.get(EVAL_BATCH_ENV) or DEFAULT_EVAL_BATCH)
        strength = [0] * N_CATEGORIES
        for i, c in enumerate(v.category_order):
            strength[c] = i
        self.strength = torch.tensor(strength, device=device)
        self.cat_of_strength = torch.tensor(list(v.category_order), device=device)
        self.wheel = (torch.tensor([0, 1, 2, 3, v.R - 1], device=device)
                      if v.ace_low_straight and v.R >= 6 else None)
        wins = straight_windows(v)
        W = torch.zeros(max(len(wins), 1), v.R, device=device)
        for i, w in enumerate(wins):
            W[i, list(w)] = 1.0
        self.windows = W if wins else None
        self._combo_idx = {}
        self._lut = None
        if use_lut is None:
            use_lut = os.environ.get(LUT_ENV, "1") != "0"
        self.use_lut = bool(use_lut) and math.comb(v.D, 5) <= LUT_MAX
        k = max(v.n_hole, 5)
        B = [[0] * (k + 1) for _ in range(v.D + 1)]
        for n in range(v.D + 1):
            B[n][0] = 1
            for r in range(1, min(n, k) + 1):
                B[n][r] = B[n - 1][r - 1] + (B[n - 1][r] if r <= n - 1 else 0)
        self.binom = torch.tensor(B, dtype=torch.long, device=device)
        self._cols5 = torch.arange(1, 6, device=device)

    def combo_idx(self, n_hole, n_board):
        key = (n_hole, n_board)
        if key not in self._combo_idx:
            hu = self.v.hole_used
            if hu is None:
                c = list(itertools.combinations(range(n_hole + n_board), 5))
            else:
                c = [h + tuple(n_hole + b for b in bc)
                     for h in itertools.combinations(range(n_hole), hu)
                     for bc in itertools.combinations(range(n_board), 5 - hu)]
            self._combo_idx[key] = torch.tensor(c, dtype=torch.long, device=self.dev)
        return self._combo_idx[key]

    def eval5(self, c):
        """c: (..., 5) long card ids -> (...,) long values (matches runtime.hand_value_5)."""
        S, R = self.v.suits, self.v.R
        r = torch.div(c, S, rounding_mode="floor")
        s = c - r * S
        cnt = (r.unsqueeze(-1) == r.unsqueeze(-2)).sum(-1)
        ks, _ = (cnt * 16 + r).sort(dim=-1, descending=True)
        ro = ks % 16
        top = torch.div(ks[..., 0], 16, rounding_mode="floor")
        distinct = torch.div((60 // cnt).sum(-1), 60, rounding_mode="floor")
        flush = (s == s[..., :1]).all(-1)
        rs, _ = r.sort(dim=-1)
        five = distinct == 5
        normal = five & (rs[..., 4] - rs[..., 0] == 4)
        shi = torch.where(normal, rs[..., 4], torch.full_like(rs[..., 4], -1))
        if self.wheel is not None:
            wh = five & (rs == self.wheel).all(-1) & ~normal
            shi = torch.where(wh, torch.full_like(shi, 3), shi)
        is_st = shi >= 0
        cat = torch.full_like(top, HIGH)
        cat = torch.where((top == 2) & (distinct == 4), torch.full_like(cat, PAIR), cat)
        cat = torch.where((top == 2) & (distinct == 3), torch.full_like(cat, TWO_PAIR), cat)
        cat = torch.where((top == 3) & (distinct == 3), torch.full_like(cat, TRIPS), cat)
        cat = torch.where(is_st, torch.full_like(cat, STRAIGHT), cat)
        cat = torch.where(flush, torch.full_like(cat, FLUSH), cat)
        cat = torch.where((top == 3) & (distinct == 2), torch.full_like(cat, FULL_HOUSE), cat)
        cat = torch.where(top == 4, torch.full_like(cat, QUADS), cat)
        cat = torch.where(is_st & flush, torch.full_like(cat, STRAIGHT_FLUSH), cat)
        cat = torch.where(top == 5, torch.full_like(cat, FIVE_KIND), cat)
        tb = (ro[..., 0] << 16) | (ro[..., 1] << 12) | (ro[..., 2] << 8) | (ro[..., 3] << 4) | ro[..., 4]
        tb = torch.where(is_st, shi.clamp(min=0) << 16, tb)
        return (self.strength[cat] << 20) | tb

    def best(self, hole, board):
        """hole (N, h), board (N, b) -> (N,) best value; -1 where no legal hand."""
        idx = self.combo_idx(hole.shape[1], board.shape[1])
        if idx.numel() == 0:
            return torch.full((hole.shape[0],), -1, dtype=torch.long, device=self.dev)
        cards = torch.cat([hole, board], dim=1)
        presorted = self.use_lut and self.v.hole_used is None
        if presorted:
            # Any 5 of the cards may be used, so order is free: sort once and every
            # (increasing) combo_idx subset comes out sorted, ready for the table lookup.
            cards, _ = cards.sort(dim=1)
        N = cards.shape[0]
        rows = max(1, self.eval_batch // idx.shape[0])     # bound the working set per batch
        out = None if N <= rows else torch.empty(N, dtype=torch.long, device=self.dev)
        for s0 in range(0, N, rows):
            sub = cards[s0:s0 + rows][:, idx]
            if self.use_lut:
                if not presorted:
                    sub, _ = sub.sort(dim=-1)
                val = self.lookup5(sub)
            else:
                val = self.eval5(sub)
            val = val.max(dim=1).values
            if out is None:
                return val
            out[s0:s0 + rows] = val
        return out

    def lookup5(self, c):
        """c: (..., 5) long card ids sorted ascending -> eval5(c), via the C(D, 5) table."""
        if self._lut is None:
            combos = torch.combinations(torch.arange(self.v.D, device=self.dev), 5)
            lut = torch.empty(combos.shape[0], dtype=torch.long, device=self.dev)
            for s0 in range(0, combos.shape[0], self.eval_batch):
                part = combos[s0:s0 + self.eval_batch]
                lut[self._colex5(part)] = self.eval5(part)
            self._lut = lut
        key = self._colex5(c)
        dup = (c[..., 1:] == c[..., :-1]).any(-1)       # not a real hand (masked-out villains)
        val = self._lut[key.clamp(max=self._lut.shape[0] - 1)]
        if bool(dup.any()):
            val[dup] = self.eval5(c[dup])
        return val

    def _colex5(self, c):
        return self.binom[c, self._cols5].sum(-1)

    def category(self, val):
        return self.cat_of_strength[val >> 20]

    def combo_index(self, cards):
        cs, _ = cards.sort(dim=1)
        cols = torch.arange(1, cs.shape[1] + 1, device=self.dev).expand_as(cs)
        return self.binom[cs, cols].sum(1)

    def features(self, hole, board):
        """(N, feature_dim) float32 matching runtime.postflop_features."""
        v = self.v
        R, S = v.R, v.suits
        N = hole.shape[0]
        rh = torch.div(hole, S, rounding_mode="floor")
        rb = torch.div(board, S, rounding_mode="floor")
        hh = torch.nn.functional.one_hot(rh, R).sum(1).float()
        bh = torch.nn.functional.one_hot(rb, R).sum(1).float()
        hsc = torch.nn.functional.one_hot(hole - rh * S, S).sum(1)
        bsc = torch.nn.functional.one_hot(board - rb * S, S).sum(1)
        order = ((hsc + bsc) * 8 + hsc).argsort(dim=1, descending=True)
        suits = torch.stack([hsc.gather(1, order), bsc.gather(1, order)], dim=2).reshape(N, 2 * S).float() * 0.25
        cat = self.category(self.best(hole, board))
        cat1h = torch.nn.functional.one_hot(cat, N_CATEGORIES).float()
        street = torch.zeros(N, len(v.streets), device=self.dev)
        cum = 0
        for k, n in enumerate(v.streets):
            cum += n
            if cum == board.shape[1]:
                street[:, k] = 1.0
        if self.windows is not None:
            pc = ((hh + bh) > 0).float()
            ph = (hh > 0).float()
            cnt = pc @ self.windows.T
            uses = (ph @ self.windows.T) > 0
            best_all = cnt.max(1).values
            best_hole = torch.where(uses, cnt, torch.zeros_like(cnt)).max(1).values
        else:
            best_all = best_hole = torch.zeros(N, device=self.dev)
        f = torch.cat([hh * 0.5, bh * 0.5, suits, cat1h, street,
                       (best_all / 5.0)[:, None], (best_hole / 5.0)[:, None]], dim=1)
        assert f.shape[1] == feature_dim(v)
        return f

    def draw(self, known, n_draw, gen=None):
        """Uniformly draw n_draw unseen cards per row. known: (N, m) long."""
        N = known.shape[0]
        keys = torch.rand(N, self.v.D, device=self.dev, generator=gen)
        if known.shape[1]:
            keys.scatter_(1, known, 2.0)
        return keys.topk(n_draw, dim=1, largest=False).indices

    def shares(self, hero, board, opp_holes):
        """Pot share of hero vs the first k opponents, for k = 1..K. Returns (N, K)."""
        hv = self.best(hero, board)
        K = len(opp_holes)
        out = []
        m = None
        ties = None
        for k in range(K):
            ov = self.best(opp_holes[k], board)
            m = ov if m is None else torch.maximum(m, ov)
            t = (ov == hv).float()
            ties = t if ties is None else ties + t
            out.append(torch.where(hv > m, torch.ones_like(t),
                                   torch.where(hv == m, 1.0 / (1.0 + ties), torch.zeros_like(t))))
        return torch.stack(out, dim=1)

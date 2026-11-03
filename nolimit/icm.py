"""Malmuth-Harville ICM via dynamic programming over subsets (fine for <= 10 players)."""
from functools import lru_cache


def icm(stacks, payouts):
    """Expected payout per player. payouts[i] is the prize for place i+1."""
    n = len(stacks)
    pay = list(payouts[:n]) + [0.0] * max(0, n - len(payouts))
    st = [float(x) for x in stacks]

    @lru_cache(maxsize=None)
    def rec(mask):
        # Expected payouts for players in `mask`, competing for places starting at `place`.
        members = [i for i in range(n) if mask >> i & 1]
        place = n - len(members)
        out = [0.0] * n
        if not members:
            return tuple(out)
        total = sum(st[i] for i in members)
        if total <= 0:
            share = sum(pay[place:place + len(members)]) / len(members)
            for i in members:
                out[i] = share
            return tuple(out)
        for k in members:
            pk = st[k] / total
            if pk == 0:
                continue
            out[k] += pk * pay[place]
            sub = rec(mask & ~(1 << k))
            for i in members:
                if i != k:
                    out[i] += pk * sub[i]
        return tuple(out)

    return list(rec((1 << n) - 1))

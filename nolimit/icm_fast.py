"""Exact single-player Malmuth-Harville ICM, without computing other payouts.

For at most ten players, subset DP sums over the opponents who finish before the
hero. It has O(n * 2**(n-1)) time and O(2**(n-1)) storage. This is the same ICM
objective as ``nolimit.icm.icm``, not an exact model of future poker play.

This standalone research module is deliberately not imported by the bot runtime.
"""
import math
import operator


def hero_rank_probabilities(stacks, hero=0):
    """Return probabilities of hero finishing first through last.

    Nonnegative finite stacks and 1--10 players are supported. Zero stacks finish
    after all positive stacks and divide the remaining places uniformly, matching
    the reference ICM routine's equal-payout convention for a zero-total tail.
    """
    st = [float(x) for x in stacks]
    n = len(st)
    if not 1 <= n <= 10:
        raise ValueError("Expected between one and ten players")
    try:
        hero = operator.index(hero)
    except TypeError as exc:
        raise ValueError("hero must be an integer seat index") from exc
    if not 0 <= hero < n:
        raise ValueError("hero seat is outside the table")
    if any(not math.isfinite(x) or x < 0 for x in st):
        raise ValueError("Stacks must be finite and nonnegative")

    ranks = [0.0] * n
    if st[hero] == 0:
        positive = sum(x > 0 for x in st)
        share = 1.0 / (n - positive)
        for r in range(positive, n):
            ranks[r] = share
        return ranks

    # Scale before summing, avoiding overflow without changing ICM probabilities.
    scale = max(st)
    h = st[hero] / scale
    opponents = [x / scale for i, x in enumerate(st) if i != hero and x > 0]
    if h == 0 or any(x == 0 for x in opponents):
        # Unrealistic chip ratios can underflow when scaled. Keep the positive
        # tail distinct instead of treating its players as tied zero stacks.
        from decimal import Decimal, localcontext
        with localcontext() as context:
            context.prec = 50
            return _positive_ranks(Decimal(st[hero]),
                                   [Decimal(x) for i, x in enumerate(st) if i != hero and x > 0], n)
    return _positive_ranks(h, opponents, n)


def _positive_ranks(h, opponents, n):
    """Subset recurrence; float normally, Decimal only for scaling underflow."""
    zero, one = h * 0, h / h
    ranks = [zero] * n
    m = len(opponents)
    size = 1 << m
    full = size - 1
    sums = [zero] * size
    counts = [0] * size
    bit_value = {1 << j: x for j, x in enumerate(opponents)}
    for mask in range(1, size):
        bit = mask & -mask
        previous = mask ^ bit
        sums[mask] = sums[previous] + bit_value[bit]
        counts[mask] = counts[previous] + 1

    dp = [zero] * size
    dp[0] = one
    for mask, probability in enumerate(dp):
        if probability == 0:
            continue
        remaining = full ^ mask
        # Sum remaining stacks directly instead of total - removed: subtraction
        # can erase a very small hero stack in a highly unbalanced configuration.
        denominator = h + sums[remaining]
        ranks[counts[mask]] += probability * (h / denominator)
        while remaining:
            bit = remaining & -remaining
            dp[mask | bit] += probability * (bit_value[bit] / denominator)
            remaining ^= bit
    return [float(p) for p in ranks]


def hero_icm(stacks, payouts, hero=0):
    """Return hero's expected payout; missing prizes are zero, extras ignored."""
    ranks = hero_rank_probabilities(stacks, hero)
    pay = [float(x) for x in payouts][:len(ranks)]
    if any(not math.isfinite(x) for x in pay):
        raise ValueError("Payouts must be finite")
    return math.fsum(p * prize for p, prize in zip(ranks, pay))

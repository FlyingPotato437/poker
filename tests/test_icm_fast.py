"""Independent payout/rank identities for single-hero exact ICM."""
import itertools
import math
import random

import pytest

from nolimit.icm import icm
from nolimit.icm_fast import hero_icm, hero_rank_probabilities


def test_random_eight_player_against_reference():
    rng = random.Random(8675309)
    for _ in range(30):
        stacks = [rng.randint(0, 20000) for _ in range(8)]
        payouts = sorted([rng.uniform(0, 100) for _ in range(8)], reverse=True)
        expected = icm(stacks, payouts)
        for hero in range(8):
            assert hero_icm(stacks, payouts, hero) == pytest.approx(expected[hero], abs=1e-10)
            ranks = hero_rank_probabilities(stacks, hero)
            assert math.fsum(ranks) == pytest.approx(1.0, abs=1e-12)
            assert all(0 <= p <= 1.0 + 1e-12 for p in ranks)


@pytest.mark.parametrize("n", range(1, 11))
def test_all_supported_table_sizes(n):
    stacks = [100 + i * i * 17 for i in range(n)]
    payouts = [100, 65, 45, 30, 20, 12, 6, 0, 0, 0][:n]
    expected = icm(stacks, payouts)
    for hero in range(n):
        ranks = hero_rank_probabilities(stacks, hero)
        assert ranks[0] == pytest.approx(stacks[hero] / sum(stacks))
        assert hero_icm(stacks, payouts, hero) == pytest.approx(expected[hero], abs=1e-10)


@pytest.mark.parametrize("stacks", [[0], [0, 0, 0], [5, 0, 0], [0, 10, 20, 0],
                                    [1, 1, 1, 1], [30, 0, 39, 1]])
def test_zero_stacks_equal_stacks_and_payout_lengths(stacks):
    for payouts in ([50], [50, 30, 20, 0], list(range(20, 0, -1))):
        expected = icm(stacks, payouts)
        for hero in range(len(stacks)):
            assert hero_icm(stacks, payouts, hero) == pytest.approx(expected[hero], abs=1e-12)
    if not any(stacks) or len(set(stacks)) == 1:
        assert hero_rank_probabilities(stacks) == pytest.approx([1 / len(stacks)] * len(stacks))


def test_explicit_zero_tail_rank_distribution():
    assert hero_rank_probabilities([0, 20, 10, 0]) == [0, 0, 0.5, 0.5]
    assert hero_rank_probabilities([20, 0, 0]) == [1, 0, 0]
    assert hero_rank_probabilities([20, 0, 0], 1) == [0, 0.5, 0.5]


def test_rank_probabilities_against_independent_permutation_enumeration():
    stacks = [2.0, 5.0, 11.0, 17.0]
    expected = [0.0] * 4
    for ordering in itertools.permutations(range(4)):
        remaining = sum(stacks)
        probability = 1.0
        for seat in ordering:
            probability *= stacks[seat] / remaining
            remaining -= stacks[seat]
        expected[ordering.index(0)] += probability
    assert hero_rank_probabilities(stacks) == pytest.approx(expected, abs=1e-12)


def test_scaling_and_seat_permutation():
    stacks = [0, 15, 2, 70, 13, 0, 25, 6]
    payouts = [100, 65, 45, 30, 20, 12, 6, 0]
    hero = 4
    baseline = hero_icm(stacks, payouts, hero)
    for scale in (1e-12, 0.25, 1, 1e12):
        assert hero_icm([s * scale for s in stacks], payouts, hero) == pytest.approx(baseline)
    permutation = [7, 5, 3, 1, 6, 4, 2, 0]
    assert hero_icm([stacks[i] for i in permutation], payouts, permutation.index(hero)) == pytest.approx(baseline)


def test_extreme_stack_ratio_keeps_probability_mass():
    for stacks in ([1e-9, 1e9, 1e9], [1e308, 1e308, 1.0], [1e-308, 1e308, 1.0]):
        ranks = hero_rank_probabilities(stacks)
        assert math.fsum(ranks) == pytest.approx(1.0, abs=1e-12)
        assert all(math.isfinite(p) for p in ranks)
    # Two equally tiny but positive players still divide the tail equally.
    assert hero_rank_probabilities([1e-308, 1e308, 1e-308]) == pytest.approx([0, 0.5, 0.5])


def test_actual_bystander_stacks_change_optimal_icm_choice():
    payouts = [50, 30, 20, 0]
    thresholds = []
    advantages = []
    for other in ([20, 20], [39, 1]):
        decline = hero_icm([30, 30] + other, payouts)
        win = hero_icm([60, 0] + other, payouts)
        lose = hero_icm([0, 60] + other, payouts)
        thresholds.append((decline - lose) / (win - lose))
        advantages.append(0.7 * win + 0.3 * lose - decline)
    assert thresholds == pytest.approx([0.6881533101045296, 0.7594025859224163])
    assert advantages[0] > 0 > advantages[1]


@pytest.mark.parametrize("stacks,hero", [([], 0), ([1] * 11, 0), ([1, -1], 0),
                                         ([1, math.nan], 0), ([1, math.inf], 0),
                                         ([1, 2], -1), ([1, 2], 2), ([1, 2], 0.5)])
def test_invalid_inputs(stacks, hero):
    with pytest.raises(ValueError):
        hero_rank_probabilities(stacks, hero)


def test_invalid_payout():
    with pytest.raises(ValueError):
        hero_icm([1, 1], [math.nan, 0])

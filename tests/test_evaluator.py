import random

import pytest

from nolimit.runtime import PRESETS, Evaluator, parse_cards, postflop_features, straight_windows


def best(vname, hole, board):
    v = PRESETS[vname]
    return Evaluator(v).best(parse_cards(v, hole), parse_cards(v, board))


def test_nlhe_category_order():
    board = "2c7d9hJs3c"
    hands = [
        best("nlhe", "AhKh", "QhJhTh2c3d"),   # royal flush
        best("nlhe", "9h8h", "7h6h5h2c3d"),   # straight flush
        best("nlhe", "AhAd", "AcAs2c3d4h"),   # quads
        best("nlhe", "AhAd", "AcKsKc3d4h"),   # full house
        best("nlhe", "Ah2h", "9h7h4hKsQd"),   # flush
        best("nlhe", "Th9d", "8c7s6hKsQd"),   # straight
        best("nlhe", "QhQd", "Qc" + board[2:10]),  # trips
        best("nlhe", "JhJd", "9c9s2h4d6c"),   # two pair
        best("nlhe", "AhAd", board),          # pair
        best("nlhe", "AhKd", board),          # high card
    ]
    assert hands == sorted(hands, reverse=True)


def test_wheel_is_lowest_straight():
    wheel = best("nlhe", "Ah2d", "3c4s5hKdQc")
    six = best("nlhe", "6h2d", "3c4s5hKdQc")
    broadway = best("nlhe", "AhKd", "QcJsTh2d3c")
    assert wheel < six < broadway


def test_short_deck_flush_beats_full_house():
    flush = best("shortdeck", "Ah9h", "7h6hJhKsQd")
    boat = best("shortdeck", "AhAd", "AcKsKc7d8h")
    assert flush > boat
    low_straight = best("shortdeck", "Ah6d", "7c8s9hKdQc")   # A6789 plays low
    ten_straight = best("shortdeck", "Th6d", "7c8s9hKdQc")
    trips = best("shortdeck", "QhQd", "Qc7s9h6dKc")
    assert trips < low_straight < ten_straight
    assert best("shortdeck_triton", "QhQd", "Qc7s9h6dKc") > best("shortdeck_triton", "Ah6d", "7c8s9hKdQc")


def test_omaha_must_use_two_hole_cards():
    one_heart = best("plo4", "AhKcQd2s", "3h5h7h9hJc")
    two_hearts = best("plo4", "AhKhQd2s", "3h5h7h9hJc")
    assert two_hearts > one_heart
    # Board quads cannot be played with three board cards only... but board AAAA + KK in hand = full house of A's
    hole_pair = best("plo4", "KhKd2c3c", "AhAdAcAs9d")
    assert hole_pair >> 20 == PRESETS["plo4"].category_order.index(6)   # full house, not quads


@pytest.mark.parametrize("vname", sorted(PRESETS))
def test_torch_parity(vname):
    torch = pytest.importorskip("torch")
    from gpu.tensor_eval import TorchEval
    v = PRESETS[vname]
    ev = Evaluator(v)
    te = TorchEval(v, torch.device("cpu"))
    rng = random.Random(7)
    W = straight_windows(v)
    for nb in (3, 4, 5):
        rows = [rng.sample(range(v.D), v.n_hole + nb) for _ in range(1500)]
        hole = torch.tensor([r[:v.n_hole] for r in rows])
        board = torch.tensor([r[v.n_hole:] for r in rows])
        assert te.best(hole, board).tolist() == [ev.best(r[:v.n_hole], r[v.n_hole:]) for r in rows]
        if ev.combos(v.n_hole, nb):
            tf = te.features(hole, board)
            pf = torch.tensor([postflop_features(v, ev, W, r[:v.n_hole], r[v.n_hole:]) for r in rows])
            assert torch.allclose(tf, pf)

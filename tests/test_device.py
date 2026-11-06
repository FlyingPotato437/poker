"""Device choice, bounded eval5 batches and the out-of-memory fallback in gpu/tensor_eval."""
import pytest

torch = pytest.importorskip("torch")

from gpu import tensor_eval  # noqa: E402
from gpu.tensor_eval import TorchEval, is_oom, pick_device, run_with_fallback  # noqa: E402
from nolimit.runtime import PRESETS  # noqa: E402


def test_pick_device(monkeypatch):
    monkeypatch.delenv(tensor_eval.DEVICE_ENV, raising=False)
    auto = pick_device("auto")
    assert auto.type == ("cuda" if torch.cuda.is_available() else "cpu")   # never MPS unasked
    monkeypatch.setenv(tensor_eval.DEVICE_ENV, "cpu")
    assert pick_device("auto").type == "cpu"
    assert pick_device(None).type == "cpu"
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: False)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    monkeypatch.setenv(tensor_eval.DEVICE_ENV, "mps")
    assert pick_device("auto", log=lambda m: None).type == "cpu"           # asked but missing
    assert pick_device("cuda", log=lambda m: None).type == "cpu"
    assert pick_device("cpu").type == "cpu"                                 # flag beats env


@pytest.mark.parametrize("variant", ["nlhe", "plo4", "shortdeck", "royal"])
def test_lookup_table_matches_eval5(variant):
    v = PRESETS[variant]
    cpu = torch.device("cpu")
    lut, direct = TorchEval(v, cpu, use_lut=True), TorchEval(v, cpu, use_lut=False)
    assert lut.use_lut and not direct.use_lut
    g = torch.Generator().manual_seed(2)
    h = v.n_hole
    cards = lut.draw(torch.empty(3000, 0, dtype=torch.long), h + v.n_board, gen=g)
    for nb in range(3, v.n_board + 1):
        assert torch.equal(lut.best(cards[:, :h], cards[:, h:h + nb]),
                           direct.best(cards[:, :h], cards[:, h:h + nb]))
    # Duplicate cards (range_eq scores villains that collide with known cards, then masks them).
    dup = cards.clone()
    dup[:, 0] = dup[:, h]
    assert torch.equal(lut.best(dup[:, :h], dup[:, h:]), direct.best(dup[:, :h], dup[:, h:]))


@pytest.mark.parametrize("variant", ["nlhe", "plo4"])
def test_batched_best_matches_unbatched(variant):
    v = PRESETS[variant]
    cpu = torch.device("cpu")
    big, small = TorchEval(v, cpu), TorchEval(v, cpu, eval_batch=97)   # odd size: ragged last batch
    g = torch.Generator().manual_seed(1)
    cards = big.draw(torch.empty(1000, 0, dtype=torch.long), v.n_hole + v.n_board, gen=g)
    hole, board = cards[:, :v.n_hole], cards[:, v.n_hole:]
    assert torch.equal(big.best(hole, board), small.best(hole, board))
    opps = [big.draw(cards, v.n_hole, gen=g)]
    assert torch.equal(big.shares(hole, board, opps), small.shares(hole, board, opps))
    assert torch.equal(big.features(hole, board), small.features(hole, board))


def test_eval_batch_env(monkeypatch):
    monkeypatch.setenv(tensor_eval.EVAL_BATCH_ENV, "1234")
    assert TorchEval(PRESETS["nlhe"], torch.device("cpu")).eval_batch == 1234


def test_oom_falls_back_to_cpu():
    seen, logs = [], []

    def fn(dev):
        seen.append(dev.type)
        if dev.type != "cpu":
            raise RuntimeError("MPS backend out of memory (MPS allocated: 3.32 GiB)")
        return "ok"

    fake = torch.device("meta")                     # any non-CPU device; fn never touches it
    assert run_with_fallback(fn, fake, log=logs.append) == "ok"
    assert seen == ["meta", "cpu"] and "out of memory" in logs[0]


def test_other_errors_are_not_swallowed():
    def fn(dev):
        raise RuntimeError("shape mismatch")
    with pytest.raises(RuntimeError, match="shape mismatch"):
        run_with_fallback(fn, torch.device("meta"), log=lambda m: None)
    assert is_oom(RuntimeError("CUDA out of memory. Tried to allocate"))
    assert not is_oom(ValueError("out of range"))

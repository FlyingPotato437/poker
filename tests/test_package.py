"""Package a heuristic bot with the mock-kit adapter and play it through the mock kit."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_package_and_mock_kit(tmp_path):
    out = tmp_path / "bot.py"
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "package_bot.py"), "--variant", "nlhe",
                    "--adapter", os.path.join(ROOT, "examples", "adapter_mock_solution.py"),
                    "--out", str(out)], check=True, capture_output=True, text=True)
    res = subprocess.run([sys.executable, os.path.join(ROOT, "examples", "mock_kit.py"), str(out), "6"],
                         check=True, capture_output=True, text=True)
    assert "via mock kit" in res.stdout


def test_adapter_swap_keeps_everything_else(tmp_path):
    """freeze.with_adapter() must give the same bytes as packaging with that adapter."""
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from freeze import split_package, with_adapter

    built = {}
    for name, adapter in (("tmpl", "adapter_template.py"), ("mock", "examples/adapter_mock_solution.py")):
        built[name] = tmp_path / f"{name}.py"
        subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "package_bot.py"), "--variant", "plo4",
                        "--params", os.path.join(ROOT, "params", "ev_t3.json"), "--no-smoke",
                        "--adapter", os.path.join(ROOT, adapter), "--out", str(built[name])],
                       check=True, capture_output=True, text=True)
    swapped = with_adapter(str(built["tmpl"]), os.path.join(ROOT, "examples", "adapter_mock_solution.py"))
    assert swapped == built["mock"].read_text()
    assert split_package(swapped)[:2] == split_package(built["tmpl"].read_text())[:2]

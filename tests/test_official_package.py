import importlib.util
from pathlib import Path
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from official import AGENT_LIMIT, check_files, check_zip, zip_files


def test_archive_reproducible_and_root_agent(tmp_path):
    files = {"agent.py": b"x = 1\n", "data.bin": b"abcd" * 3000}
    a, b = tmp_path / "a.zip", tmp_path / "b.zip"
    zip_files(a, files)
    zip_files(b, files)
    assert a.read_bytes() == b.read_bytes()
    assert check_zip(a)["agent_bytes"] == 6
    with pytest.raises(ValueError, match="root"):
        check_files({"nested/agent.py": b""})


@pytest.mark.parametrize("name,content", [("unused.py", b"import pokerkit.state\n"),
                                           ("unused.py", b"from poker_engine import X\n"),
                                           ("../file", b""), ("lib.so", b"native")])
def test_reject_unsafe_entries_even_unused(name, content):
    with pytest.raises(ValueError):
        check_files({"agent.py": b"", name: content})


def test_agent_limit_is_separate_from_model_limit():
    with pytest.raises(ValueError, match="1 MB"):
        check_files({"agent.py": b"#" * (AGENT_LIMIT + 1)})
    check_files({"agent.py": b"", "model.bin": b"x" * (AGENT_LIMIT + 1)})


def test_duplicate_archive_entry_rejected(tmp_path):
    path = tmp_path / "bad.zip"
    with pytest.warns(UserWarning):
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("agent.py", b"x=1")
            z.writestr("agent.py", b"x=2")
    with pytest.raises(ValueError, match="duplicate"):
        check_zip(path)

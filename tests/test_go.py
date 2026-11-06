"""scripts/go.py: announcement validation, preset matching, params mapping, ante choice."""
import copy
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import go  # noqa: E402


def load(name):
    with open(os.path.join(ROOT, "variants", name)) as fh:
        return json.load(fh)


def ok(raw):
    spec, errors, warnings, plans = go.validate(raw)
    assert errors == [], errors
    return spec, warnings, plans


@pytest.mark.parametrize("name,preset,params", [
    ("examples/nlhe_points_ante.json", "nlhe", "params/cand_nlhe.json"),
    ("examples/plo4.json", "plo4", "params/ev_t3.json"),
    ("examples/kit2_tahoe.json", None, "params/ev_t3.json"),
    ("examples/custom_7plus_flush.json", None, "params/ev_t4.json"),
])
def test_examples_resolve(name, preset, params):
    spec, _, _ = ok(load(name))
    hits = go.match_preset(spec["variant"])
    assert (hits[0] if hits else None) == preset
    got, _ = go.pick_params(preset, spec["variant"], go.load_params_map())
    assert got == params


def test_params_map_files_exist():
    pmap = go.load_params_map()
    paths = [pmap["heuristic_v0"], *pmap["preset"].values(), *pmap["new_variant"].values()]
    for p in paths:
        assert os.path.exists(os.path.join(ROOT, p)), p
    for preset in pmap["preset"]:
        assert preset in go.PRESETS


def test_template_needs_points_only():
    _, errors, _, _ = go.validate(load("ANNOUNCE.json"))
    assert len(errors) == 1 and errors[0].startswith("points")
    raw = load("ANNOUNCE.json")
    raw["points"] = "100,65,45,30,20,12,6,0"
    spec, _, _ = ok(raw)
    assert go.match_preset(spec["variant"])[0] == "nlhe"
    assert spec["ante_bb"] == 0.0


def test_kit2_matches_its_variant_json_and_ante():
    spec, _, _ = ok(load("examples/kit2_tahoe.json"))
    with open(os.path.join(ROOT, "bench", "dayof", "kit2_day.json")) as fh:
        ref = json.load(fh)
    assert go.same_rules(spec["variant"], ref)
    # 1500 chips: first level with <= 25 bb is 40/80, ante 5 -> 0.0625
    assert spec["ante_bb"] == pytest.approx(0.0625)


def test_flush_over_full_house_is_not_shortdeck():
    raw = load("examples/custom_7plus_flush.json")
    spec, _, _ = ok(raw)
    assert spec["variant"]["category_order"].index(5) > spec["variant"]["category_order"].index(6)
    raw["variant"]["ranks"] = "6789TJQKA"     # now identical to the shortdeck preset
    spec, _, _ = ok(raw)
    assert go.match_preset(spec["variant"]) == ["shortdeck"]


def test_preset_overrides_and_holdem3_alias():
    raw = load("examples/plo4.json")
    raw["variant"] = {"preset": None, "n_hole": 3}
    spec, _, _ = ok(raw)
    # holdem3 and pineapple_nodiscard have identical rules; the one with a bundle comes first
    hits = go.match_preset(spec["variant"])
    assert set(hits) == {"holdem3", "pineapple_nodiscard"}
    if os.path.exists(go.bundle_path("holdem3")):
        assert hits[0] == "holdem3"
    raw["variant"] = {"preset": "plo4", "n_hole": 5}
    spec, _, _ = ok(raw)
    assert go.match_preset(spec["variant"]) == ["plo5"]
    raw["variant"] = "royal"
    spec, _, _ = ok(raw)
    assert go.match_preset(spec["variant"]) == ["royal"]


@pytest.mark.parametrize("patch,needle", [
    ({"variant": {"preset": "omaha8"}}, "unknown preset"),
    ({"variant": {"preset": None, "category_order": ["high", "pair"]}}, "permutation"),
    ({"variant": {"preset": None, "suits": 9}}, "suits"),
    ({"variant": {"preset": None, "ranks": "AAKQJ"}}, "repeats"),
    ({"variant": {"preset": None, "n_hole": 2, "hole_used": 3}}, "hole_used"),
    ({"points": [10, 5]}, None),                        # padded: a warning, not an error
    ({"points": [9, 8, 7, 6, 5, 4, 3, 2, 1]}, "9 points for 8 players"),
    ({"points": [0] * 8}, "all zero"),
    ({"players": 12}, "players"),
    ({"betting": {"type": "spread-limit"}}, "betting.type"),
    ({"game_type": "razz"}, "game_type"),
    ({"ante": {"type": "every-player", "chips": 0}}, "no ante.chips"),
    ({"special_rules": {"double_board": True}}, "unknown keys"),
    ({"blinds": "10/20/5/1"}, "sb/bb"),
])
def test_validation_errors(patch, needle):
    raw = load("examples/nlhe_points_ante.json")
    for k, v in patch.items():
        raw[k] = copy.deepcopy(v)
    _, errors, warnings, _ = go.validate(raw)
    if needle is None:
        assert errors == [] and any("padding" in w for w in warnings)
    else:
        assert any(needle in e for e in errors), errors


def test_unsupported_rules_get_plans():
    raw = load("examples/nlhe_points_ante.json")
    raw["betting"] = {"type": "pot-limit", "raise_cap": 4}
    raw["game_type"] = "hi-lo"
    raw["special_rules"] = {"straddle": True, "bounty": True, "other": "dealer's choice"}
    raw["time_limit_ms"] = 0.4
    _, warnings, plans = ok(raw)
    text = " ".join(plans)
    for word in ("Pot-limit", "Raise cap", "Hi-lo", "Straddle", "Bounties", "raise-BY", "0.5 ms"):
        assert word in text, word
    assert any("dealer's choice" in w for w in warnings)


def test_ante_choice():
    raw = load("examples/nlhe_points_ante.json")
    spec, _, _ = ok(raw)
    assert spec["ante_bb"] == pytest.approx(0.05)    # 2000 chips: 50/100 is the first level <= 25 bb
    raw["ante"] = {"type": "bb-ante"}
    spec, _, _ = ok(raw)
    assert spec["ante_bb"] == pytest.approx(1 / 8, abs=1e-4)
    raw["ante"] = {"type": "every-player"}
    raw["blinds"] = "10/20/0,25/50/5,50/100/10,100/200/25"
    spec, _, _ = ok(raw)
    assert spec["ante_bb"] == pytest.approx(0.1)
    raw["ante"] = {"type": "every-player", "chips": 5, "ante_bb_override": 0.25}
    spec, _, _ = ok(raw)
    assert spec["ante_bb"] == 0.25


def test_adapter_checks(tmp_path):
    spec, _, _ = ok(load("examples/kit2_tahoe.json"))
    errs, _ = go.check_adapter(os.path.join(ROOT, "adapter_template.py"), spec)
    assert errs and "template" in errs[0]
    errs, warns = go.check_adapter(os.path.join(ROOT, "examples", "answers", "kit2_adapter.py"), spec)
    assert errs == [] and warns == []
    errs, warns = go.check_adapter(os.path.join(ROOT, "examples", "adapter_mock_solution.py"), spec)
    assert errs == [] and any("PokerBot" in w for w in warns)


def test_deadline_adapter(tmp_path, monkeypatch):
    monkeypatch.setattr(go, "ROOT", str(tmp_path))
    spec, _, _ = ok(load("examples/kit2_tahoe.json"))
    src = os.path.join(ROOT, "examples", "answers", "kit2_adapter.py")
    assert go.deadline_adapter(src, spec, "t") == src         # 1 ms: unchanged
    spec["time_limit_ms"] = 2.0
    out = go.deadline_adapter(src, spec, "t")
    assert out != src and open(out).read().rstrip().splitlines()[-1].startswith("PrepBot.deadline = 0.001200")


def test_eta_and_combos():
    spec, _, _ = ok(load("examples/kit2_tahoe.json"))
    assert go.combos_per_showdown(spec["variant"]) == 30
    assert go.combos_per_showdown(go.PRESETS["nlhe"].to_dict()) == 21
    assert go.combos_per_showdown(go.PRESETS["plo4"].to_dict()) == 60
    fast, lap = go.eta_minutes(spec["variant"], "fast"), go.eta_minutes(spec["variant"], "laptop")
    assert fast[0] < fast[1] < lap[1]


def test_check_mode_builds_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(go, "LOGDIR", str(tmp_path))
    for name in ("nlhe_points_ante", "plo4", "kit2_tahoe", "custom_7plus_flush"):
        rc = go.main([os.path.join(ROOT, "variants", "examples", name + ".json"), "--check", "--tag", "pytest",
                      "--variant-out", str(tmp_path / "day.json")])
        assert rc == 0
    assert not (tmp_path / "day.json").exists()
    log = (tmp_path / "go_pytest.log").read_text()
    assert "preset nlhe" in log and "NEW variant" in log
    rc = go.main([os.path.join(ROOT, "variants", "ANNOUNCE.json"), "--check", "--tag", "pytest"])
    assert rc == 2


def test_tags_checked_before_building(tmp_path, monkeypatch):
    monkeypatch.setattr(go, "LOGDIR", str(tmp_path))
    monkeypatch.setattr(go, "ROOT", str(tmp_path))
    (tmp_path / "frozen" / "x_v2").mkdir(parents=True)
    rc = go.main([os.path.join(ROOT, "variants", "examples", "kit2_tahoe.json"), "--tag", "x",
                  "--adapter", os.path.join(ROOT, "examples", "answers", "kit2_adapter.py")])
    assert rc == 2 and "frozen/x_v2 exists" in (tmp_path / "go_x.log").read_text()


def test_table_script_chain():
    spec, _, _ = ok(load("examples/kit2_tahoe.json"))
    text, v1, v2 = go.table_script("tt", "variants/day.json", spec, "params/ev_t3.json", "a.py", "k {bot}",
                                   "fast", 10, 3, "cpu")
    assert "gpu.build_tables" in text and "gpu.range_eq" in text and "--skip pushfold" in text
    assert "--device cpu" in text and "NOLIMIT_DEVICE=cpu" in text
    assert (text.index("gpu.build_tables") < text.index("day.py build tt_v1") < text.index("gpu.range_eq")
            < text.index("day.py build tt_v2"))
    for cmd in (v1, v2):
        assert "--points 10,6,4,3,2,1,0,0" in " ".join(cmd) and "--ante-bb 0.0625" in " ".join(cmd)
    assert v1[v1.index("--bundle") + 1].endswith("tt_base.nlb")
    assert v2[v2.index("--bundle") + 1].endswith("tt_base_rng.nlb")


def test_tables_only_then_full_run(tmp_path, monkeypatch):
    """--tables-only starts the chain without an adapter; the later full run doesn't restart it."""
    for d in ("variants", "bench/dayof", "frozen"):
        (tmp_path / d).mkdir(parents=True)
    monkeypatch.setattr(go, "LOGDIR", str(tmp_path))
    monkeypatch.setattr(go, "ROOT", str(tmp_path))
    started = []

    class FakePopen:
        pid = 1

        def __init__(self, cmd, **kw):
            started.append(cmd)

    monkeypatch.setattr(go.subprocess, "Popen", FakePopen)
    runs = []
    monkeypatch.setattr(go.Log, "run", lambda self, cmd, env=None: runs.append(cmd) or 0)
    ann = os.path.join(ROOT, "variants", "examples", "custom_7plus_flush.json")
    assert go.main([ann, "--tag", "q", "--tables-only"]) == 0
    script = (tmp_path / "bench" / "dayof" / "go_q_tables.sh").read_text()
    assert "gpu.build_tables" in script and "day.py build" not in script
    assert len(started) == 1 and (tmp_path / "bench" / "dayof" / "go_q_tables.only").exists()
    assert go.main([ann, "--tag", "q", "--adapter", os.path.join(ROOT, "examples", "adapter_mock_solution.py")]) == 0
    assert len(started) == 1                                   # not restarted
    assert [c[3] for c in runs if "day.py" in " ".join(c)] == ["q_v0"]    # tables not finished yet

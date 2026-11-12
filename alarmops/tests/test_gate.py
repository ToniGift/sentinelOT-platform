from pathlib import Path

import pytest
import yaml
from conftest import BASELINE_RULES, ROOT

from alarmops.gate import GateError, evaluate, load_gate, render_markdown, MARKER
from alarmops.replay import replay_files
from alarmops.rules import parse_rules



def _head(**tank):
    cfg = yaml.safe_load(BASELINE_RULES.read_text())
    cfg["tags"]["tank_level"].update(tank)
    return replay_files("x", rules=parse_rules(cfg))


@pytest.fixture(scope="module")
def base():
    return replay_files(BASELINE_RULES)


@pytest.fixture(scope="module")
def gate():
    return load_gate(ROOT / "gate.yaml")


def test_identical_rules_pass(base, gate):
    res = evaluate(base, base, gate)
    assert res.passed and res.violations == [] and res.newly_missed == []


def test_widened_limit_is_blocked_and_names_missed_faults(base, gate):
    res = evaluate(base, _head(high=88, high_high=95), gate)
    assert not res.passed
    assert res.detection_delta < 0
    assert res.newly_missed and all(f["tag"] == "tank_level" for f in res.newly_missed)


def test_nuisance_alarms_are_blocked(base, gate):
    res = evaluate(base, _head(high=56), gate)
    assert not res.passed
    assert any("false alarms" in v for v in res.violations)


def test_safe_tightening_passes(base, gate):
    assert evaluate(base, _head(high=75, high_high=88), gate).passed


def test_markdown_has_marker_and_status(base, gate):
    head = _head(high=88, high_high=95)
    md = render_markdown(base, head, evaluate(base, head, gate), gate)
    assert md.startswith(MARKER) and "FAIL" in md and "Blocked because" in md


def test_gate_file_validation(tmp_path):
    p = tmp_path / "g.yaml"
    p.write_text("min_detection_rate: 0.9\n")
    with pytest.raises(GateError):
        load_gate(p)

import json
from pathlib import Path

import pytest
import yaml
from conftest import BASELINE_REPORT, BASELINE_RULES, ROOT

from alarmops.replay import Fault, replay_files, run_replay, main
from alarmops.rules import RulesError, TagRules, load_rules



def test_harness_scores_synthetic_case():
    r = {"x": TagRules("x", 10, 20, 80, 90, 0, 1)}
    times = list(range(100))
    vals = [50.0] * 100
    for t in range(30, 36):
        vals[t] = 85.0           # injected spike, labelled
    for t in range(90, 93):
        vals[t] = 85.0           # unlabelled excursion -> false alarm
    faults = [Fault("F1", "x", "spike", 30, 35), Fault("F2", "x", "spike", 50, 55)]
    rep = run_replay(r, times, {"x": vals}, faults)
    assert rep["faults_total"] == 2 and rep["faults_detected"] == 1
    assert rep["detection_rate"] == 0.5
    assert rep["false_alarm_count"] == 1
    assert rep["per_tag"]["x"]["alarms"] == 2


def test_missing_rules_for_tag_is_error():
    r = {"x": TagRules("x", 10, 20, 80, 90)}
    with pytest.raises(RulesError):
        run_replay(r, [0, 1], {"x": [1.0, 1.0], "y": [1.0, 1.0]}, [])


def test_baseline_report_matches_fresh_measurement():
    fresh = replay_files(BASELINE_RULES)
    saved = json.loads(BASELINE_REPORT.read_text())
    for k in ("detection_rate", "false_alarm_count", "faults_detected", "alarm_count"):
        assert fresh[k] == saved[k]


def test_baseline_is_healthy():
    rep = replay_files(BASELINE_RULES)
    assert rep["detection_rate"] >= 0.9
    assert rep["false_alarm_count"] <= 3


def test_widening_a_limit_reduces_detection(tmp_path):
    cfg = yaml.safe_load(BASELINE_RULES.read_text())
    cfg["tags"]["tank_level"]["high"] = 89
    cfg["tags"]["tank_level"]["high_high"] = 95
    p = tmp_path / "wide.yaml"
    p.write_text(yaml.safe_dump(cfg))
    base = replay_files(BASELINE_RULES)
    wide = replay_files(p)
    assert wide["detection_rate"] < base["detection_rate"]


def test_cli_writes_report(tmp_path):
    out = tmp_path / "r.json"
    assert main(["--rules", str(BASELINE_RULES), "--out", str(out)]) == 0
    assert json.loads(out.read_text())["faults_total"] == 21


def test_cli_bad_rules_returns_2(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("tags:\n  tank_level: {low_low: 1}\n")
    assert main(["--rules", str(bad)]) == 2

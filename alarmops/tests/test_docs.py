"""Keep the documentation honest: numbers must match a fresh measurement."""
import re

import yaml
from conftest import BASELINE_RULES, ROOT

from alarmops.replay import replay_files
from alarmops.rules import parse_rules

README = (ROOT / "README.md").read_text(encoding="utf-8")


def _widened_tank():
    cfg = yaml.safe_load(BASELINE_RULES.read_text())
    cfg["tags"]["tank_level"].update(high=88, high_high=95)      # what demo-change-a does
    return replay_files("x", rules=parse_rules(cfg))


def test_readme_baseline_numbers_match_measurement():
    base = replay_files(BASELINE_RULES)
    assert (base["faults_detected"], base["faults_total"], base["false_alarm_count"]) == (21, 21, 0)
    assert "21/21 faults detected, 0 false alarms" in README


def test_readme_demo_a_numbers_match_measurement():
    wide = _widened_tank()
    assert (wide["faults_detected"], wide["faults_total"]) == (17, 21)
    assert f"{wide['detection_rate']:.1%}" == "81.0%"
    assert "81.0% (17/21)" in README


def test_documents_referenced_by_readme_exist():
    for rel in ("docs/duo-agents.md", "SUBMISSION.md", "LICENSE",
                ".gitlab/duo/agent-config.yml", "gate.yaml", "alarms.yaml"):
        assert (ROOT / rel).exists(), rel
        assert rel in README or rel in ("LICENSE", "alarms.yaml", "gate.yaml")


def test_docs_do_not_overclaim():
    duo = (ROOT / "docs" / "duo-agents.md").read_text(encoding="utf-8")
    assert "not guessed" in duo or "deliberately not guessed" in duo
    assert "reference mapping, not a" in README.replace("\n", " ").lower().replace("**", "")
    assert "simulation" in README.lower()
    assert not re.search(r"(?i)\bcertified\b(?! )", README.replace("not a certification", ""))

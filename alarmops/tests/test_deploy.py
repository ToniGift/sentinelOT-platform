import json

import pytest
import yaml
from conftest import BASELINE_RULES, ROOT

from alarmops.deploy import promote_release, stage_release, verify_release

GATE = ROOT / "gate.yaml"


def test_stage_then_verify_passes(tmp_path):
    m = stage_release(BASELINE_RULES, tmp_path / "staging", "staging")
    assert m["simulation"] is True and m["replay"]["detection_rate"] == 1.0
    res = verify_release(tmp_path / "staging", GATE)
    assert res["ok"], res
    names = {c["name"] for c in res["checks"]}
    assert {"rules_hash_matches_manifest", "replay_matches_manifest",
            "service_smoke_test", "gate_floors_met"} <= names


def test_tampered_rules_fail_verification(tmp_path):
    stage_release(BASELINE_RULES, tmp_path / "s", "staging")
    p = tmp_path / "s" / "alarms.yaml"
    cfg = yaml.safe_load(p.read_text())
    cfg["tags"]["tank_level"]["high"] = 85
    p.write_text(yaml.safe_dump(cfg))
    res = verify_release(tmp_path / "s", GATE)
    assert not res["ok"]
    assert not next(c for c in res["checks"] if c["name"] == "rules_hash_matches_manifest")["ok"]


def test_missing_release_fails(tmp_path):
    assert verify_release(tmp_path / "nope")["ok"] is False


def test_promote_records_approver(tmp_path):
    stage_release(BASELINE_RULES, tmp_path / "s", "staging")
    m = promote_release(tmp_path / "s", tmp_path / "p", "anthony", GATE)
    assert m["environment"] == "production" and m["approval"]["approved_by"] == "anthony"
    assert json.loads((tmp_path / "p" / "manifest.json").read_text())["promoted_from"] == "staging"


def test_promote_refuses_unverified_release(tmp_path):
    stage_release(BASELINE_RULES, tmp_path / "s", "staging")
    (tmp_path / "s" / "alarms.yaml").write_text("tags: {}\n")
    with pytest.raises(RuntimeError):
        promote_release(tmp_path / "s", tmp_path / "p", "anthony", GATE)
    assert not (tmp_path / "p").exists()

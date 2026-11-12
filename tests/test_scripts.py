import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from conftest import BASELINE_RULES, ROOT



def run(script, *args, env=None):
    import os
    e = {k: v for k, v in os.environ.items()
         if not k.startswith(("CI_", "GITLAB_"))}
    e.update(env or {})
    return subprocess.run([sys.executable, str(ROOT / "scripts" / script), *args],
                          capture_output=True, text=True, cwd=ROOT, env=e)


@pytest.fixture()
def wide(tmp_path):
    cfg = yaml.safe_load(BASELINE_RULES.read_text())
    cfg["tags"]["tank_level"].update(high=88, high_high=95)
    p = tmp_path / "wide.yaml"
    p.write_text(yaml.safe_dump(cfg))
    return p


def test_compare_exit_codes(tmp_path, wide):
    out = ["--summary", str(tmp_path / "s.md"), "--json", str(tmp_path / "c.json")]
    ok = run("compare_replay.py", "--base-rules", str(BASELINE_RULES), "--head-rules", str(BASELINE_RULES), *out)
    assert ok.returncode == 0, ok.stderr
    bad = run("compare_replay.py", "--base-rules", str(BASELINE_RULES), "--head-rules", str(wide), *out)
    assert bad.returncode == 1 and "GATE: FAIL" in bad.stdout
    err = run("compare_replay.py", "--base-rules", str(BASELINE_RULES), "--head-rules", "nope.yaml", *out)
    assert err.returncode == 2
    data = json.loads((tmp_path / "c.json").read_text())
    assert set(data) == {"base", "head", "gate", "result"}


def test_post_mr_comment_skips_without_env(tmp_path):
    s = tmp_path / "s.md"
    s.write_text("x")
    r = run("post_mr_comment.py", "--summary", str(s))
    assert r.returncode == 0 and "skipping" in r.stdout


def test_change_record_lists_changes_and_disclaimer(tmp_path, wide):
    cj, out = tmp_path / "c.json", tmp_path / "cr.md"
    run("compare_replay.py", "--base-rules", str(BASELINE_RULES), "--head-rules", str(wide),
        "--summary", str(tmp_path / "s.md"), "--json", str(cj))
    r = run("change_record.py", "--base-rules", str(BASELINE_RULES), "--head-rules", str(wide),
            "--compare-json", str(cj), "--out", str(out), "--reason", "test")
    assert r.returncode == 0, r.stderr
    text = out.read_text()
    assert "| tank_level | high | 80.0 | 88.0 |" in text
    assert "not a certification" in text.lower()


def test_monitor_detects_drift_and_healthy(tmp_path):
    out = tmp_path / "d.md"
    healthy = run("monitor.py", "--log", "data/post_deploy_alarm_log_healthy.csv", "--out", str(out))
    assert healthy.returncode == 0 and "no drift" in healthy.stdout and not out.exists()
    drift = run("monitor.py", "--log", "data/post_deploy_alarm_log_drift.csv", "--out", str(out))
    assert drift.returncode == 0 and "DRIFT DETECTED" in drift.stdout
    assert "pump_pressure" in out.read_text()
    failing = run("monitor.py", "--log", "data/post_deploy_alarm_log_drift.csv",
                  "--out", str(out), "--fail-on-drift")
    assert failing.returncode == 3

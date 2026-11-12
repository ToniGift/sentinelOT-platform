"""Simulated staging/production release handling.

A "release" is a directory holding the deployed alarms.yaml and a manifest.json
(rules hash, measured replay metrics, CI context, approval record). Nothing here
touches real equipment: deployment is simulated by staging files + verifying them.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .gate import load_gate
from .replay import DEFAULT_DATA, DEFAULT_FAULTS, replay_files
from .rules import RulesError, load_rules
from .service import run as run_service


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ci_context() -> dict[str, Any]:
    e = os.environ
    return {
        "commit": e.get("CI_COMMIT_SHA", "local"),
        "pipeline_url": e.get("CI_PIPELINE_URL", "local"),
        "triggered_by": e.get("GITLAB_USER_LOGIN", "local"),
    }


def stage_release(rules_path: str | Path, dest: str | Path, environment: str,
                  data: str | Path = DEFAULT_DATA,
                  faults: str | Path = DEFAULT_FAULTS) -> dict[str, Any]:
    load_rules(rules_path)  # raises RulesError if invalid
    report = replay_files(rules_path, data, faults)
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(rules_path, dest / "alarms.yaml")
    manifest = {
        "environment": environment,
        "deployed_at": _now(),
        "rules_sha256": sha256_file(dest / "alarms.yaml"),
        "replay": {k: report[k] for k in
                   ("detection_rate", "false_alarm_count", "faults_detected",
                    "faults_total", "alarm_count")},
        "ci": _ci_context(),
        "simulation": True,
    }
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def verify_release(release_dir: str | Path, gate_path: str | Path | None = None,
                   data: str | Path = DEFAULT_DATA,
                   faults: str | Path = DEFAULT_FAULTS) -> dict[str, Any]:
    d = Path(release_dir)
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    manifest_path, rules_path = d / "manifest.json", d / "alarms.yaml"
    if not manifest_path.exists() or not rules_path.exists():
        add("release_files_present", False, f"missing manifest.json or alarms.yaml in {d}")
        return {"ok": False, "checks": checks}
    add("release_files_present", True, "manifest.json and alarms.yaml found")
    manifest = json.loads(manifest_path.read_text())

    actual = sha256_file(rules_path)
    add("rules_hash_matches_manifest", actual == manifest.get("rules_sha256"),
        f"sha256 {actual[:12]}... vs manifest {str(manifest.get('rules_sha256'))[:12]}...")

    try:
        load_rules(rules_path)
        add("rules_valid", True, "alarms.yaml parses and limits are ordered")
    except RulesError as exc:
        add("rules_valid", False, str(exc))
        return {"ok": False, "checks": checks}

    report = replay_files(rules_path, data, faults)
    m = manifest.get("replay", {})
    same = (report["detection_rate"] == m.get("detection_rate")
            and report["false_alarm_count"] == m.get("false_alarm_count"))
    add("replay_matches_manifest", same,
        f"detection {report['detection_rate']:.1%}, false alarms {report['false_alarm_count']}")

    served = sum(1 for _ in run_service(str(rules_path), str(data)))
    add("service_smoke_test", served == report["alarm_count"],
        f"service raised {served} alarms; replay expected {report['alarm_count']}")

    if gate_path:
        gate = load_gate(gate_path)
        add("gate_floors_met",
            report["detection_rate"] >= gate["min_detection_rate"]
            and report["false_alarm_count"] <= gate["max_false_alarms"],
            f"min detection {gate['min_detection_rate']:.0%}, max false alarms {int(gate['max_false_alarms'])}")

    return {"ok": all(c["ok"] for c in checks), "checks": checks,
            "measured": {k: report[k] for k in ("detection_rate", "false_alarm_count")}}


def promote_release(source: str | Path, dest: str | Path, approver: str,
                    gate_path: str | Path | None = None) -> dict[str, Any]:
    """Promote a verified staging release to production (the human-approved step)."""
    result = verify_release(source, gate_path)
    if not result["ok"]:
        failed = [c["name"] for c in result["checks"] if not c["ok"]]
        raise RuntimeError(f"refusing to promote: failed checks {failed}")
    source, dest = Path(source), Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source / "alarms.yaml", dest / "alarms.yaml")
    manifest = json.loads((source / "manifest.json").read_text())
    manifest.update({
        "environment": "production",
        "promoted_from": "staging",
        "approval": {"approved_by": approver, "approved_at": _now()},
        "ci": _ci_context(),
    })
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest

#!/usr/bin/env python3
"""Run the AlarmOps pipeline locally, stage by stage, in the same order as .gitlab-ci.yml.

Nothing here needs GitLab. It lets you check a change before pushing it.
Exit code: 0 = every job passed (or is waiting for approval), 1 = a job failed.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import _common  # noqa: F401
from _common import ROOT

PY = sys.executable
OUT = ROOT / "out"
LOG_DIR = OUT / "local"
SCRIPTS = ROOT / "scripts"
MARKERS = ("GATE: FAIL", "  - ", "BLOCKED", "INVALID", "promotion blocked",
           "VALIDATION: FAIL", "[FAIL]", "error:", "FAILED", "failed", "(value not printed)")
SUMMARY_PREFIXES = ("GATE:", "VALIDATION:", "MONITOR:", "OK:", "staged", "secret_guard:", "wrote")


@dataclass
class Job:
    stage: str
    name: str
    status: str            # passed | failed | skipped | waiting
    note: str = ""


@dataclass
class PipelineResult:
    base_ref: str
    jobs: list[Job] = field(default_factory=list)
    stopped_at: str | None = None

    @property
    def failed(self) -> list[Job]:
        return [j for j in self.jobs if j.status == "failed"]

    @property
    def waiting(self) -> bool:
        return any(j.status == "waiting" for j in self.jobs)


def sh(args: list[str], env: dict | None = None) -> tuple[int, str]:
    p = subprocess.run(args, cwd=ROOT, capture_output=True, text=True,
                       env={**os.environ, **(env or {})})
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def default_base_ref() -> str:
    for cand in ("main", "master"):
        if sh(["git", "rev-parse", "--verify", "-q", cand])[0] == 0:
            return cand
    return "HEAD"


def _highlights(text: str, failed: bool) -> str:
    lines = [l.rstrip() for l in text.splitlines() if l.strip()]
    if not lines:
        return "done"
    if failed:
        picked = [l.strip() for l in lines if any(m in l for m in MARKERS)]
        return " | ".join(dict.fromkeys(picked[:4])) or lines[-1].strip()
    for l in lines:
        if l.strip().startswith(SUMMARY_PREFIXES) or "passed" in l:
            return l.strip()
    return lines[-1].strip()


def _job(res: PipelineResult, stage: str, name: str, args: list[str],
         env: dict | None = None) -> None:
    rc, out = sh(args, env)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    (LOG_DIR / f"{name}.log").write_text(out, encoding="utf-8")
    res.jobs.append(Job(stage, name, "passed" if rc == 0 else "failed", _highlights(out, rc != 0)))


def _skip(res, stage, name, why):
    res.jobs.append(Job(stage, name, "skipped", why))


def _approver() -> str:
    return (os.environ.get("GITLAB_USER_LOGIN")
            or sh(["git", "config", "user.name"])[1].strip() or "local-user")


def pipeline(base_ref: str, approve: str = "no") -> PipelineResult:
    shutil.rmtree(OUT, ignore_errors=True)
    shutil.rmtree(ROOT / "deploy", ignore_errors=True)
    OUT.mkdir(parents=True)
    res = PipelineResult(base_ref)

    def stage_ok(stage: str) -> bool:
        if any(j.stage == stage and j.status == "failed" for j in res.jobs):
            res.stopped_at = stage
            return False
        return True

    # plan
    _job(res, "plan", "validate_rules", [PY, str(SCRIPTS / "validate_rules.py")])
    if not stage_ok("plan"):
        return res

    # review: replay target-branch rules vs this change, apply the gate
    rc, base_text = sh(["git", "show", f"{base_ref}:alarms.yaml"])
    if rc != 0:
        res.jobs.append(Job("review", "replay_review", "failed", f"cannot read alarms.yaml at {base_ref}"))
    else:
        (OUT / "base_alarms.yaml").write_text(base_text, encoding="utf-8")
        _job(res, "review", "replay_review",
             [PY, str(SCRIPTS / "compare_replay.py"), "--base-rules", str(OUT / "base_alarms.yaml"),
              "--head-rules", "alarms.yaml"])
    if not stage_ok("review"):
        return res

    # test
    rc_pytest = sh([PY, "-c", "import pytest"])[0]
    if rc_pytest == 0:
        _job(res, "test", "unit_tests", [PY, "-m", "pytest", "-q"])
    else:
        _skip(res, "test", "unit_tests", "pytest not installed (pip install -r requirements-dev.txt)")
    _job(res, "test", "replay_test",
         [PY, str(SCRIPTS / "compare_replay.py"), "--base-rules", "alarms.yaml", "--head-rules", "alarms.yaml",
          "--summary", str(OUT / "floor_summary.md"), "--json", str(OUT / "floor.json")])
    if not stage_ok("test"):
        return res

    # security
    _job(res, "security", "secret_guard", [PY, str(SCRIPTS / "secret_guard.py")])
    _skip(res, "security", "secret_detection", "GitLab-only job; runs after you push")
    if not stage_ok("security"):
        return res

    # compliance
    _job(res, "compliance", "change_record",
         [PY, str(SCRIPTS / "change_record.py"), "--base-rules", str(OUT / "base_alarms.yaml"),
          "--head-rules", "alarms.yaml", "--compare-json", str(OUT / "compare.json"),
          "--scan-status", "secret_guard passed locally (GitLab Secret Detection runs in CI)",
          "--out", str(OUT / "change_record.md")])
    if shutil.which("cyclonedx-py"):
        _job(res, "compliance", "sbom",
             ["cyclonedx-py", "environment", "--of", "JSON", "-o", str(OUT / "sbom.cdx.json"), PY])
    else:
        _skip(res, "compliance", "sbom", "cyclonedx-py not installed (pip install cyclonedx-bom)")
    if not stage_ok("compliance"):
        return res

    # deploy_staging + validate
    _job(res, "deploy_staging", "deploy_staging", [PY, str(SCRIPTS / "deploy_staging.py")])
    if not stage_ok("deploy_staging"):
        return res
    _job(res, "validate", "validate_staging", [PY, str(SCRIPTS / "validate_staging.py")])
    if not stage_ok("validate"):
        return res

    # approve: the single human gate
    if approve == "ask":
        if sys.stdin.isatty():
            approve = "yes" if input("Approve deployment to PRODUCTION? [y/N] ").strip().lower() == "y" else "no"
        else:
            approve = "no"
    if approve == "yes":
        _job(res, "approve", "deploy_production",
             [PY, str(SCRIPTS / "deploy_production.py"), "--approver", _approver()])
        if not stage_ok("approve"):
            return res
    else:
        res.jobs.append(Job("approve", "deploy_production", "waiting",
                            "waiting for human approval (Supervised gate; manual job on the default branch in GitLab)"))

    # monitor (scheduled / manual in GitLab; run here so you can see it)
    _job(res, "monitor", "monitor_alarm_rate",
         [PY, str(SCRIPTS / "monitor.py"), "--log", "data/post_deploy_alarm_log_drift.csv",
          "--out", str(OUT / "monitor_diagnosis.md")])
    return res


def measured() -> dict | None:
    p = OUT / "compare.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text())
    return {"base_rate": d["base"]["detection_rate"], "head_rate": d["head"]["detection_rate"],
            "base_fa": d["base"]["false_alarm_count"], "head_fa": d["head"]["false_alarm_count"],
            "head_detected": d["head"]["faults_detected"], "faults_total": d["head"]["faults_total"]}


ICON = {"passed": "[PASS]", "failed": "[FAIL]", "skipped": "[SKIP]", "waiting": "[WAIT]"}


def print_result(res: PipelineResult) -> None:
    print(f"\nAlarmOps local pipeline (comparing against '{res.base_ref}')\n" + "-" * 64)
    for j in res.jobs:
        print(f"{ICON[j.status]} {j.stage:<15} {j.name:<20} {j.note}")
    print("-" * 64)
    if res.failed:
        print(f"PIPELINE FAILED at stage '{res.stopped_at}'. Logs: out/local/")
    elif res.waiting:
        print("PIPELINE PASSED every automated check; waiting for human approval.")
    else:
        print("PIPELINE PASSED.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-ref", default=None, help="branch holding the current rules (default: main/master)")
    ap.add_argument("--approve", choices=["ask", "yes", "no"], default="ask",
                    help="what to do at the human approval gate (default: ask)")
    a = ap.parse_args()
    res = pipeline(a.base_ref or default_base_ref(), a.approve)
    print_result(res)
    return 1 if res.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

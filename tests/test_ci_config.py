"""Structural checks on .gitlab-ci.yml (GitLab's own linter needs a GitLab instance)."""
import re

import yaml
from conftest import ROOT

CI = yaml.safe_load((ROOT / ".gitlab-ci.yml").read_text())
RESERVED = {"workflow", "stages", "default", "variables", "cache", "include"}
JOBS = {k: v for k, v in CI.items() if k not in RESERVED and not k.startswith(".")}
EXPECTED_STAGES = ["plan", "review", "test", "security", "compliance",
                   "deploy_staging", "validate", "approve", "monitor"]


def test_stage_order_matches_brief():
    assert CI["stages"] == EXPECTED_STAGES


def test_every_job_uses_a_declared_stage():
    # secret_detection is defined by the included template but re-staged here.
    for name, job in JOBS.items():
        assert job.get("stage") in EXPECTED_STAGES, name


def test_dependencies_point_at_real_jobs():
    for name, job in JOBS.items():
        for dep in job.get("dependencies", []):
            assert dep in JOBS, f"{name} depends on unknown job {dep}"


def test_every_stage_has_a_job():
    used = {j["stage"] for j in JOBS.values()}
    assert used == set(EXPECTED_STAGES)


def test_production_is_a_manual_default_branch_only_gate():
    job = JOBS["deploy_production"]
    assert job["allow_failure"] is False
    rules = job["rules"]
    assert all(r.get("when") == "manual" for r in rules)
    assert all("CI_DEFAULT_BRANCH" in r["if"] for r in rules)
    assert job["environment"]["name"] == "production"


def test_secret_detection_template_included_and_not_allowed_to_fail():
    assert {"template": "Security/Secret-Detection.gitlab-ci.yml"} in CI["include"]
    assert JOBS["secret_detection"]["allow_failure"] is False


def test_referenced_scripts_exist():
    text = (ROOT / ".gitlab-ci.yml").read_text()
    for rel in set(re.findall(r"scripts/[\w./-]+\.(?:py|sh)", text)):
        assert (ROOT / rel).exists(), rel


def test_no_secrets_or_tokens_in_pipeline_file():
    text = (ROOT / ".gitlab-ci.yml").read_text()
    assert "glpat-" not in text


def test_artifacts_outlive_judging():
    """Judging ends 14 Nov 2026 and winners are announced ~16 Nov; keep artifacts >= 6 weeks."""
    text = (ROOT / ".gitlab-ci.yml").read_text()
    values = re.findall(r"expire_in:\s*(\d+)\s*(week|month)s?", text)
    assert values, "no expire_in found"
    for n, unit in values:
        weeks = int(n) * (1 if unit == "week" else 4)
        assert weeks >= 6, f"expire_in {n} {unit}(s) is too short for the judging window"

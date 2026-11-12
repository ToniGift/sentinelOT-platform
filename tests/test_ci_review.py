"""Run scripts/ci_review.sh in a throwaway git repo, the way the CI job does."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import BASELINE_RULES, ROOT

SH = shutil.which("sh")

# ci_review.sh runs on GitLab's Linux runners. Windows has no POSIX sh by default;
# scripts/local_pipeline.py covers the same logic there.
pytestmark = pytest.mark.skipif(SH is None, reason="needs a POSIX sh (not available on this machine)")


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture()
def repo(tmp_path):
    for item in ("scripts", "src", "data", "gate.yaml"):
        src = ROOT / item
        dst = tmp_path / item
        shutil.copytree(src, dst) if src.is_dir() else shutil.copy(src, dst)
    shutil.copy(BASELINE_RULES, tmp_path / "alarms.yaml")   # frozen baseline, not the live file
    shim = tmp_path / "bin"
    shim.mkdir()
    # A wrapper script, not a symlink: creating symlinks needs admin rights on Windows.
    wrapper = shim / "python"
    exe = Path(sys.executable).as_posix()
    wrapper.write_text(f'#!/bin/sh\nexec "{exe}" "$@"\n', newline="\n")
    wrapper.chmod(0o755)
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.name", "t")
    _git(tmp_path, "config", "user.email", "t@example.invalid")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "base")
    return tmp_path


def _review(repo):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CI_", "GITLAB_"))}
    env["PATH"] = f"{repo / 'bin'}{os.pathsep}{env['PATH']}"
    env["PYTHONPATH"] = str(repo / "src")
    return subprocess.run([SH, "scripts/ci_review.sh"], cwd=repo, env=env,
                          capture_output=True, text=True)


def _edit(repo, old, new):
    p = repo / "alarms.yaml"
    p.write_text(p.read_text().replace(old, new, 1))
    _git(repo, "commit", "-qam", "change")


def test_safe_change_passes(repo):
    _edit(repo, "high: 80", "high: 75")
    r = _review(repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "GATE: PASS" in r.stdout and (repo / "out" / "base_alarms.yaml").exists()


def test_widened_limit_blocks_the_pipeline(repo):
    _edit(repo, "high: 80", "high: 88")
    r = _review(repo)
    assert r.returncode == 1 and "GATE: FAIL" in r.stdout
    assert (repo / "out" / "replay_summary.md").exists()

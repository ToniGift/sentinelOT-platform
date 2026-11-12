"""End-to-end: build the three demo branches in a throwaway repo and run the local demo."""
import os
import re
import shutil
import subprocess
import sys

from conftest import BASELINE_RULES, ROOT


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def test_demo_branches_behave_as_designed(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    for item in ("scripts", "src", "data", "tests", "gate.yaml", "pyproject.toml",
                 "requirements.txt", "requirements-dev.txt", ".gitignore", ".gitlab-ci.yml", "cloud"):
        src = ROOT / item
        if src.is_dir():
            shutil.copytree(src, repo / item, ignore=shutil.ignore_patterns(
                "__pycache__", "test_local_pipeline.py",   # avoid recursion
                "test_ci_review.py",                       # needs POSIX sh; covered separately
                "test_docs.py"))                           # checks the real README, not the copy
        else:
            shutil.copy(src, repo / item)
    shutil.copy(BASELINE_RULES, repo / "alarms.yaml")
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "base")

    env = {k: v for k, v in os.environ.items() if not k.startswith(("CI_", "GITLAB_"))}
    run = lambda script: subprocess.run([sys.executable, f"scripts/{script}"], cwd=repo, env=env,
                                        capture_output=True, text=True)
    made = run("make_demo_branches.py")
    assert made.returncode == 0, made.stderr
    demo = run("local_demo.py")
    assert demo.returncode == 0, demo.stdout + demo.stderr

    summary = demo.stdout.split("DEMO SUMMARY")[1]
    full = demo.stdout       # shown by pytest when an assertion below fails
    line = lambda b: next(l for l in summary.splitlines() if l.startswith(b))
    assert "BLOCKED" in line("demo-change-a") and "stage: review" in line("demo-change-a"), full
    assert "BLOCKED" in line("demo-change-b") and "stage: security" in line("demo-change-b"), full
    assert "WAITING FOR APPROVAL" in line("demo-change-c"), full
    assert re.search(r"detection 100\.0% -> 8\d\.\d%", summary)      # change A measured drop
    assert _git(repo, "branch", "--show-current").strip() == "main"  # always returns you home

#!/usr/bin/env python3
"""Fast local guard that fails on obvious hard-coded credentials.

Complements GitLab Secret Detection (the real scanner); it exists so the demo
block is deterministic. Scans git-tracked text files. Add `alarmops: allow-secret`
on a line to allow it. Exit 1 if anything is found.
"""
import subprocess
import sys
from pathlib import Path

import _common  # noqa: F401
from _common import ROOT

from alarmops.secretscan import ALLOW, PATTERNS  # noqa: F401

SKIP_DIRS = ("tests/", "data/")


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files"],
                         capture_output=True, text=True, cwd=ROOT)
    return out.stdout.split() if out.returncode == 0 else []


def scan(paths) -> list[tuple[str, int, str]]:
    findings = []
    for rel in paths:
        if rel.startswith(SKIP_DIRS) or rel == "scripts/secret_guard.py":
            continue
        p = ROOT / rel
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if ALLOW in line:
                continue
            for name, rx in PATTERNS.items():
                if rx.search(line):
                    findings.append((rel, n, name))
    return findings


def main() -> int:
    found = scan(tracked_files())
    if not found:
        print("secret_guard: no hard-coded credentials found")
        return 0
    print("secret_guard: BLOCKED, possible hard-coded credentials:", file=sys.stderr)
    for rel, n, name in found:
        print(f"  {rel}:{n}  {name}  (value not printed)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

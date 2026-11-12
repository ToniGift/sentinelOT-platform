"""Obvious-credential patterns shared by scripts/secret_guard.py and the web lab.

This is a small backstop, not a replacement for GitLab Secret Detection. Findings never
include the matched value.
"""
from __future__ import annotations

import re

PATTERNS = {
    "AWS access key id": re.compile(r"AKIA[0-9A-Z]{16}"),
    "private key block": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "GitLab personal access token": re.compile(r"glpat-[0-9A-Za-z_\-]{20,}"),
    "hard-coded credential": re.compile(
        r"""(?i)\b(password|passwd|secret|api[_-]?key|token)\b\s*[:=]\s*["'][^"'\s]{8,}["']"""),
}
ALLOW = "alarmops: allow-secret"


def scan_text(text: str) -> list[tuple[int, str]]:
    """Return (line number, pattern name) for every line that looks like a credential."""
    findings = []
    for n, line in enumerate(text.splitlines(), 1):
        if ALLOW in line:
            continue
        for name, rx in PATTERNS.items():
            if rx.search(line):
                findings.append((n, name))
    return findings

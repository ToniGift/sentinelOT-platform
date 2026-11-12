#!/usr/bin/env python3
"""Run the local pipeline on each demo branch and print a results table.

Use this for rehearsing the demo video. It always returns you to your starting branch.
"""
import argparse
import subprocess
import sys

import _common  # noqa: F401
from _common import ROOT

import local_pipeline as lp

CASES = [
    ("demo-change-a", "Widen a limit"),
    ("demo-change-b", "Hard-coded credential"),
    ("demo-change-c", "Valid tightening"),
]


def git(*args):
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if p.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed: {p.stderr.strip()}")
    return p.stdout.strip()


def outcome(res):
    if res.failed:
        return "BLOCKED", res.stopped_at
    return ("WAITING FOR APPROVAL" if res.waiting else "PASSED"), "approve" if res.waiting else "-"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", default=None)
    a = ap.parse_args()
    base = a.base or lp.default_base_ref()
    start = git("branch", "--show-current")
    if git("status", "--porcelain"):
        sys.exit("working tree is not clean; commit or stash first")
    missing = [b for b, _ in CASES if subprocess.run(
        ["git", "rev-parse", "--verify", "-q", b], cwd=ROOT, capture_output=True).returncode != 0]
    if missing:
        sys.exit(f"missing branches {missing}; run: python scripts/make_demo_branches.py")

    rows = []
    try:
        for branch, label in CASES:
            git("checkout", branch)
            res = lp.pipeline(base, approve="no")
            lp.print_result(res)
            m = lp.measured()
            verdict, stage = outcome(res)
            blockers = "; ".join(f"{j.name}: {j.note}" for j in res.failed)
            rows.append((branch, label, verdict, stage, m, blockers))
    finally:
        git("checkout", start or base)

    print("\n" + "=" * 78 + "\nDEMO SUMMARY\n" + "=" * 78)
    for branch, label, verdict, stage, m, blockers in rows:
        nums = ""
        if m:
            nums = (f"detection {m['base_rate']:.1%} -> {m['head_rate']:.1%} "
                    f"({m['head_detected']}/{m['faults_total']}), false alarms {m['base_fa']} -> {m['head_fa']}")
        print(f"{branch:<14} {label:<22} {verdict:<22} stage: {stage}")
        if nums:
            print(f"{'':<14} measured: {nums}")
        if blockers:
            print(f"{'':<14} reason:   {blockers}")
    print(f"\nBack on '{start or base}'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

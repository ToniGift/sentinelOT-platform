#!/usr/bin/env python3
"""Replay the target-branch rules and the merge-request rules, then apply the gate.

Exit codes: 0 = gate passed, 1 = gate failed (change blocked), 2 = error.
"""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

import _common  # noqa: F401  (adds src/ to sys.path)
from _common import ROOT, git_show

from alarmops.gate import GateError, evaluate, load_gate, render_markdown
from alarmops.replay import DEFAULT_DATA, DEFAULT_FAULTS, replay_files
from alarmops.rules import RulesError, load_rules_text


def default_base_ref() -> str | None:
    target = os.environ.get("CI_MERGE_REQUEST_TARGET_BRANCH_NAME")
    return f"origin/{target}" if target else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--head-rules", default="alarms.yaml", help="rules under review")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--base-rules", help="path to the target-branch rules file")
    g.add_argument("--base-ref", help="git ref holding the target rules (e.g. origin/main)")
    ap.add_argument("--rules-path-in-repo", default="alarms.yaml")
    ap.add_argument("--gate", default=str(ROOT / "gate.yaml"))
    ap.add_argument("--data", default=str(DEFAULT_DATA))
    ap.add_argument("--faults", default=str(DEFAULT_FAULTS))
    ap.add_argument("--summary", default="out/replay_summary.md")
    ap.add_argument("--json", dest="json_out", default="out/compare.json")
    a = ap.parse_args()

    try:
        gate = load_gate(a.gate)
        head = replay_files(a.head_rules, a.data, a.faults)
        if a.base_rules:
            base = replay_files(a.base_rules, a.data, a.faults)
        else:
            ref = a.base_ref or default_base_ref() or "main"
            text = git_show(ref, a.rules_path_in_repo)
            base = replay_files(f"{ref}:{a.rules_path_in_repo}", a.data, a.faults,
                                rules=load_rules_text(text))
    except (GateError, RulesError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    res = evaluate(base, head, gate)
    md = render_markdown(base, head, res, gate)
    for p in (a.summary, a.json_out):
        Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(a.summary).write_text(md, encoding="utf-8")
    Path(a.json_out).write_text(json.dumps(
        {"base": base, "head": head, "gate": gate, "result": res.as_dict()}, indent=2) + "\n")

    print(f"base : detection={base['detection_rate']:.1%} false_alarms={base['false_alarm_count']}")
    print(f"head : detection={head['detection_rate']:.1%} false_alarms={head['false_alarm_count']}")
    if res.passed:
        print("GATE: PASS")
        return 0
    print("GATE: FAIL")
    for v in res.violations:
        print(f"  - {v}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

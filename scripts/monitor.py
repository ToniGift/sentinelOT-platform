#!/usr/bin/env python3
"""Watch the simulated post-deploy alarm rate; on drift, write a diagnosis and open a GitLab issue.

Log format: CSV with an 'hour' column and one alarm-count column per tag.
Exit codes: 0 = ok (or drift reported), 3 = drift detected and --fail-on-drift set, 2 = error.
"""
import argparse
import os
import sys
from pathlib import Path

import _common  # noqa: F401

from alarmops import gitlab_api
from alarmops.monitoring import analyse, diagnosis, load_log  # noqa: F401

ISSUE_TITLE = "AlarmOps monitor: alarm-rate drift after deployment"


def open_issue(body):
    missing = gitlab_api.missing_env()
    if missing:
        print(f"\n[not opening a GitLab issue: missing env vars {missing}]")
        return
    try:
        existing = gitlab_api.request("GET", "/issues", query={
            "state": "opened", "labels": "alarmops-monitor", "search": ISSUE_TITLE, "in": "title"})
        if existing:
            print(f"open monitoring issue already exists (#{existing[0]['iid']}); not duplicating")
            return
        issue = gitlab_api.request("POST", "/issues", body={
            "title": ISSUE_TITLE, "description": body, "labels": "alarmops-monitor,monitoring"})
        print(f"opened issue #{issue['iid']}")
    except RuntimeError as exc:
        print(f"warning: could not open issue: {exc}", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--log", default="data/post_deploy_alarm_log_drift.csv")
    ap.add_argument("--baseline-hours", type=int, default=24)
    ap.add_argument("--recent-hours", type=int, default=6)
    ap.add_argument("--factor", type=float, default=2.0)
    ap.add_argument("--min-increase", type=float, default=2.0)
    ap.add_argument("--out", default="out/monitor_diagnosis.md")
    ap.add_argument("--fail-on-drift", action="store_true")
    a = ap.parse_args()
    try:
        tags, rows = load_log(a.log)
        res = analyse(tags, rows, a.baseline_hours, a.recent_hours, a.factor, a.min_increase)
    except (OSError, ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"baseline={res['baseline_per_hour']:.2f}/h recent={res['recent_per_hour']:.2f}/h "
          f"threshold={res['threshold']:.2f}/h")
    if not res["drift"]:
        print("MONITOR: OK, no drift")
        return 0
    body = diagnosis(res, a.log, a.baseline_hours, a.recent_hours)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(body + "\n", encoding="utf-8")
    print("MONITOR: DRIFT DETECTED\n")
    print(body)
    open_issue(body)
    return 3 if a.fail_on_drift else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Promote the validated staging release to (simulated) production.

Runs as a MANUAL pipeline job: the person who clicks it is the human approver.
"""
import argparse
import os
import sys

import _common  # noqa: F401
from _common import ROOT

from alarmops.deploy import promote_release


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", default="deploy/staging")
    ap.add_argument("--dest", default="deploy/production")
    ap.add_argument("--gate", default=str(ROOT / "gate.yaml"))
    ap.add_argument("--approver", default=os.environ.get("GITLAB_USER_LOGIN", "local"))
    a = ap.parse_args()
    try:
        m = promote_release(a.source, a.dest, a.approver, a.gate)
    except (RuntimeError, FileNotFoundError) as exc:
        print(f"promotion blocked: {exc}", file=sys.stderr)
        return 1
    print(f"promoted to {a.dest}; approved by {m['approval']['approved_by']} at {m['approval']['approved_at']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

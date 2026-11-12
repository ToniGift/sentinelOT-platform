#!/usr/bin/env python3
"""Deploy the alarm rules to the (simulated) staging environment."""
import argparse
import sys

import _common  # noqa: F401

from alarmops.deploy import stage_release
from alarmops.rules import RulesError


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rules", default="alarms.yaml")
    ap.add_argument("--dest", default="deploy/staging")
    a = ap.parse_args()
    try:
        m = stage_release(a.rules, a.dest, "staging")
    except (RulesError, FileNotFoundError) as exc:
        print(f"deploy failed: {exc}", file=sys.stderr)
        return 2
    print(f"staged to {a.dest} (rules {m['rules_sha256'][:12]}..., "
          f"detection {m['replay']['detection_rate']:.1%}, "
          f"false alarms {m['replay']['false_alarm_count']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

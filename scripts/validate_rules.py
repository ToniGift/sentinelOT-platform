#!/usr/bin/env python3
"""Plan-stage check: is alarms.yaml well-formed and physically consistent?"""
import argparse
import sys

import _common  # noqa: F401

from alarmops.rules import RulesError, load_rules


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rules", default="alarms.yaml")
    a = ap.parse_args()
    try:
        rules = load_rules(a.rules)
    except (RulesError, FileNotFoundError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 2
    for tag, r in rules.items():
        print(f"{tag}: {r.low_low} < {r.low} < {r.high} < {r.high_high} {r.unit} "
              f"(deadband {r.deadband}, delay {r.delay_samples})")
    print(f"OK: {len(rules)} tags valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

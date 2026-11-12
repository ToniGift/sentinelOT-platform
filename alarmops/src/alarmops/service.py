"""AlarmOps service: reads simulated sensor values and raises alarms from alarms.yaml.

SIMULATION ONLY. Reads a CSV replay stream; never talks to real equipment.
"""
from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict

from .engine import TagAlarmState
from .rules import load_rules


def run(rules_path: str, data_path: str):
    rules = load_rules(rules_path)
    states = {tag: TagAlarmState(r) for tag, r in rules.items()}
    with open(data_path, newline="") as fh:
        for row in csv.DictReader(fh):
            t = int(row["t"])
            for tag, st in states.items():
                if tag in row:
                    ev = st.update(t, float(row[tag]))
                    if ev:
                        yield ev


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Run the AlarmOps simulated alarm service")
    ap.add_argument("--rules", default="alarms.yaml")
    ap.add_argument("--data", default="data/replay.csv")
    ap.add_argument("--limit", type=int, default=0, help="stop after N alarms (0 = all)")
    a = ap.parse_args(argv)
    n = 0
    for ev in run(a.rules, a.data):
        print(json.dumps(asdict(ev)))
        n += 1
        if a.limit and n >= a.limit:
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

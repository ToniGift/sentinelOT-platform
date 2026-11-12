#!/usr/bin/env python3
"""Post-deploy validation of the staged release. Exit 1 if any check fails."""
import argparse
import json
from pathlib import Path

import _common  # noqa: F401
from _common import ROOT

from alarmops.deploy import verify_release


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", default="deploy/staging")
    ap.add_argument("--gate", default=str(ROOT / "gate.yaml"))
    ap.add_argument("--out", default="out/validation.json")
    a = ap.parse_args()
    res = verify_release(a.dir, a.gate)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, indent=2) + "\n")
    for c in res["checks"]:
        print(f"[{'PASS' if c['ok'] else 'FAIL'}] {c['name']}: {c['detail']}")
    print("VALIDATION:", "PASS" if res["ok"] else "FAIL")
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Regenerate docs/explainer.html from a fresh replay (all figures are measured)."""
import argparse
from pathlib import Path

import _common  # noqa: F401
from _common import ROOT

from alarmops.explainer import render_explainer
from alarmops.scenarios import build_report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(ROOT / "docs" / "explainer.html"))
    a = ap.parse_args()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_explainer(build_report()), encoding="utf-8", newline="\n")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

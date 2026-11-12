#!/usr/bin/env python3
"""Refresh the saved results embedded in static/sentinelot.html.

The showcase page shows these, labelled "Recorded", when it is opened without
the platform server. Run this after changing plant/alarms.yaml or regenerating
the dataset, from the repo root:
    python plant/save_page_copy.py
tests/test_alarm_limits.py fails if the saved copy no longer matches the API.
"""
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PAGE = REPO / "static" / "sentinelot.html"
MARK = "var LIM_RECORDED="
PRESET = {"tag": "sealer_temperature", "high": "250", "high_high": "265"}


def main():
    os.chdir(REPO)
    sys.path.insert(0, str(REPO / "triage"))
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import alarm_limits
    app = FastAPI()
    app.include_router(alarm_limits.router)
    c = TestClient(app)
    saved = {"baseline": c.get("/api/alarmops/baseline").json(),
             "preset": c.get("/api/alarmops/compare", params=PRESET).json()}
    text = PAGE.read_text(encoding="utf-8")
    start = text.index(MARK) + len(MARK)
    end = text.index(";\n", start)
    body = json.dumps(saved, ensure_ascii=False, separators=(",", ":"))
    PAGE.write_text(text[:start] + body + text[end:], encoding="utf-8",
                    newline="\n")
    print(f"saved baseline and preset result into {PAGE.relative_to(REPO)}")


if __name__ == "__main__":
    main()

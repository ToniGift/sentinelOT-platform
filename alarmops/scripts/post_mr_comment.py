#!/usr/bin/env python3
"""Post (or update) the replay summary as a merge request comment.

Needs GITLAB_API_TOKEN, CI_API_V4_URL, CI_PROJECT_ID, CI_MERGE_REQUEST_IID.
If any are missing it prints a message and exits 0 (so local runs never fail).
"""
import argparse
import os
import sys
from pathlib import Path

import _common  # noqa: F401

from alarmops import gitlab_api
from alarmops.gate import MARKER


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--summary", default="out/replay_summary.md")
    a = ap.parse_args()

    missing = gitlab_api.missing_env(("CI_MERGE_REQUEST_IID",))
    if missing:
        print(f"skipping MR comment: missing env vars {missing} (expected outside CI)")
        return 0
    path = Path(a.summary)
    if not path.exists():
        print(f"error: {path} not found; run compare_replay.py first", file=sys.stderr)
        return 2
    body = path.read_text(encoding="utf-8")
    iid = os.environ["CI_MERGE_REQUEST_IID"]
    try:
        notes = gitlab_api.request("GET", f"/merge_requests/{iid}/notes",
                                   query={"per_page": 100, "sort": "desc"})
        existing = next((n for n in notes or [] if MARKER in n.get("body", "")), None)
        if existing:
            gitlab_api.request("PUT", f"/merge_requests/{iid}/notes/{existing['id']}",
                               body={"body": body})
            print(f"updated MR !{iid} comment {existing['id']}")
        else:
            gitlab_api.request("POST", f"/merge_requests/{iid}/notes", body={"body": body})
            print(f"posted new comment on MR !{iid}")
    except RuntimeError as exc:
        # Never let a comment failure hide the real gate result.
        print(f"warning: {exc}", file=sys.stderr)
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

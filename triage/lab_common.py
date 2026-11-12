"""Shared pieces for the Labshock lab feeds (lab_elk.py and lab_sniffer.py).

Read-only towards the lab: nothing here sends a packet to a control
network. The only outbound call is the POST to SentinelOT's own
/api/triage endpoint.
"""
import json
import os

import httpx

from schemas import Alert


def csv_set(value):
    return {x.strip() for x in (value or "").split(",") if x.strip()}


def post_alert(alert: Alert, url=None, token=None, dry_run=False, out=None):
    """Send one alert to SentinelOT. Returns the job id, or None on dry run.

    out: optional path of a .jsonl file that records every alert sent and
    the job id it got, so lab results can be matched to expected labels.
    """
    body = alert.model_dump()
    job_id = None
    if dry_run:
        print(json.dumps(body, indent=2))
    else:
        url = (url or os.getenv("SENTINELOT_URL", "http://127.0.0.1:8000"))
        token = token or os.getenv("APP_ADMIN_TOKEN", "")
        if not token:
            raise SystemExit("Set APP_ADMIN_TOKEN (same value the SentinelOT "
                             "server uses) or pass --dry-run.")
        r = httpx.post(url.rstrip("/") + "/api/triage", json=body,
                       headers={"x-admin-token": token}, timeout=30)
        r.raise_for_status()
        job_id = r.json()["job_id"]
        print(f"sent {alert.alert_id}: {alert.title} -> job {job_id}")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(json.dumps({"job_id": job_id, "alert": body}) + "\n")
    return job_id

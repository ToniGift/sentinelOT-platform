"""Labshock ELK adapter: reads alert documents from the lab's Elasticsearch
and posts each one to SentinelOT as an Alert with source="labshock-elk".

It only reads from Elasticsearch. It never talks to the control network.

Field names are tried in order, so both Elastic Common Schema documents
and Suricata EVE documents map without extra configuration. Check the
mapping against real lab documents with --dry-run before trusting it.

Run from the repo root:
  python triage/lab_elk.py --dry-run --once
  python triage/lab_elk.py --index "suricata-*" --query "event_type:alert"
"""
import argparse
import os
import time

import httpx

from lab_common import post_alert
from schemas import Alert

SRC = ("source.ip", "src_ip", "source.address")
DST = ("destination.ip", "dest_ip", "destination.address")
TITLE = ("kibana.alert.rule.name", "rule.name", "alert.signature",
         "signal.rule.name", "event.action")
DESC = ("kibana.alert.reason", "rule.description", "message",
        "alert.category", "event.original")
SEV = ("kibana.alert.severity", "event.severity_label", "alert.severity",
       "event.severity", "log.level")
PROTO = ("network.protocol", "app_proto", "network.transport", "proto")
PORT = ("destination.port", "dest_port")
PORT_PROTO = {502: "modbus", 4840: "opcua", 44818: "enip", 20000: "dnp3"}
KNOWN = {"modbus", "opcua", "enip", "dnp3", "profinet"}


def pick(doc, paths):
    """First non-empty value among dotted paths (nested or flattened keys)."""
    for p in paths:
        cur = doc.get(p)
        if cur in (None, ""):
            cur = doc
            for part in p.split("."):
                cur = cur.get(part) if isinstance(cur, dict) else None
        if isinstance(cur, list):
            cur = cur[0] if cur else None
        if cur not in (None, ""):
            return cur
    return None


def to_alert(hit) -> Alert:
    doc = hit.get("_source", {})
    src, dst = pick(doc, SRC), pick(doc, DST)
    port = pick(doc, PORT)
    proto = str(pick(doc, PROTO) or "").lower()
    if proto not in KNOWN:
        try:
            proto = PORT_PROTO.get(int(port), proto)
        except (TypeError, ValueError):
            pass
    title = str(pick(doc, TITLE) or "Lab alert without a rule name")
    desc = str(pick(doc, DESC) or title)
    facts = [f"{k} {v}" for k, v in (("Source", src), ("destination", dst),
                                     ("destination port", port)) if v]
    if facts:
        desc = f"{desc} ({', '.join(facts)}.)"
    sev = pick(doc, SEV)
    return Alert(alert_id="lab-elk-" + str(hit.get("_id", ""))[:20],
                 timestamp=str(pick(doc, ("@timestamp", "timestamp")) or ""),
                 source="labshock-elk", title=title[:200],
                 description=desc[:1500],
                 severity_src=None if sev is None else str(sev),
                 protocol=proto or None,
                 src_ip=None if src is None else str(src),
                 dst_ip=None if dst is None else str(dst),
                 raw={"detector": "lab_elk", "index": hit.get("_index"),
                      "id": hit.get("_id")})


def search(client, index, since, query, size):
    flt = [{"range": {"@timestamp": {"gte": since}}}]
    if query:
        flt.append({"query_string": {"query": query}})
    r = client.post(f"/{index}/_search", json={
        "size": size, "sort": [{"@timestamp": "asc"}],
        "query": {"bool": {"filter": flt}}})
    r.raise_for_status()
    return r.json()["hits"]["hits"]


def main():
    from dotenv import load_dotenv
    load_dotenv()
    env = os.getenv
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--es", default=env("LAB_ES_URL", "http://127.0.0.1:9200"))
    p.add_argument("--index", default=env("LAB_ES_INDEX",
                                          ".alerts-security.alerts-*"))
    p.add_argument("--query", default=env("LAB_ES_QUERY"),
                   help="extra Lucene filter, e.g. event_type:alert")
    p.add_argument("--since", default="now-5m",
                   help="where to start (Elasticsearch date maths)")
    p.add_argument("--interval", type=float, default=15)
    p.add_argument("--max-per-poll", type=int, default=10,
                   help="cap on alerts per poll; each one costs a full run")
    p.add_argument("--once", action="store_true")
    p.add_argument("--insecure", action="store_true",
                   help="skip TLS verification (lab self-signed cert)")
    p.add_argument("--dry-run", action="store_true",
                   help="print alerts, do not post them")
    p.add_argument("--out", help="append alerts and job ids to this .jsonl")
    a = p.parse_args()

    headers, auth = {}, None
    if env("LAB_ES_API_KEY"):
        headers["Authorization"] = "ApiKey " + env("LAB_ES_API_KEY")
    elif env("LAB_ES_USER"):
        auth = (env("LAB_ES_USER"), env("LAB_ES_PASSWORD", ""))
    client = httpx.Client(base_url=a.es, headers=headers, auth=auth,
                          verify=not a.insecure, timeout=30)
    since, seen = a.since, set()
    while True:
        sent = 0
        for hit in search(client, a.index, since, a.query,
                          a.max_per_poll + 100):
            if hit["_id"] in seen:
                continue
            if sent >= a.max_per_poll:
                break
            sent += 1
            seen.add(hit["_id"])
            alert = to_alert(hit)
            since = alert.timestamp or since
            post_alert(alert, dry_run=a.dry_run, out=a.out)
        if a.once:
            break
        time.sleep(a.interval)


if __name__ == "__main__":
    main()

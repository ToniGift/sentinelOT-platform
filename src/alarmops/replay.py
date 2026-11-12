"""Replay harness: run ANY rules file against the labelled dataset and score it.

Detection: a labelled fault counts as detected if an alarm event for the same
tag is raised in [start, end + window]. False alarm: an alarm event for a tag
that falls inside no fault window of that tag.
All numbers are computed here from the dataset; nothing is hard-coded.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .engine import AlarmEvent, evaluate_series
from .rules import RulesError, TagRules, load_rules

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA = ROOT / "data" / "replay.csv"
DEFAULT_FAULTS = ROOT / "data" / "faults.csv"
DETECTION_WINDOW = 20  # samples allowed after fault end


@dataclass(frozen=True)
class Fault:
    fault_id: str
    tag: str
    type: str
    start: int
    end: int


def load_dataset(path: str | Path) -> tuple[list[int], dict[str, list[float]]]:
    times: list[int] = []
    cols: dict[str, list[float]] = {}
    with open(path, newline="") as fh:
        reader = csv.DictReader(fh)
        tags = [c for c in (reader.fieldnames or []) if c != "t"]
        cols = {c: [] for c in tags}
        for row in reader:
            times.append(int(row["t"]))
            for c in tags:
                cols[c].append(float(row[c]))
    return times, cols


def load_faults(path: str | Path) -> list[Fault]:
    with open(path, newline="") as fh:
        return [Fault(r["fault_id"], r["tag"], r["type"], int(r["start"]), int(r["end"]))
                for r in csv.DictReader(fh)]


def _sha256(path: str | Path) -> str:
    """Short content hash that ignores CRLF vs LF, so it is the same on every OS."""
    data = Path(path).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()[:16]


def run_replay(
    rules: dict[str, TagRules],
    times: list[int],
    cols: dict[str, list[float]],
    faults: list[Fault],
    window: int = DETECTION_WINDOW,
) -> dict[str, Any]:
    missing = [t for t in cols if t not in rules]
    if missing:
        raise RulesError(f"rules file has no entry for dataset tags: {missing}")

    events: dict[str, list[AlarmEvent]] = {
        tag: evaluate_series(rules[tag], times, vals) for tag, vals in cols.items()
    }

    fault_rows: list[dict[str, Any]] = []
    for f in faults:
        hit = next((e for e in events.get(f.tag, []) if f.start <= e.t <= f.end + window), None)
        fault_rows.append({
            "fault_id": f.fault_id, "tag": f.tag, "type": f.type,
            "start": f.start, "end": f.end,
            "detected": hit is not None,
            "latency_samples": (hit.t - f.start) if hit else None,
            "level": hit.level if hit else None,
        })

    per_tag: dict[str, dict[str, Any]] = {}
    total_false = 0
    for tag in cols:
        tag_faults = [f for f in faults if f.tag == tag]
        false_alarms = [
            e for e in events[tag]
            if not any(f.start <= e.t <= f.end + window for f in tag_faults)
        ]
        det = [r for r in fault_rows if r["tag"] == tag and r["detected"]]
        n_f = len(tag_faults)
        per_tag[tag] = {
            "faults_total": n_f, "faults_detected": len(det),
            "detection_rate": round(len(det) / n_f, 4) if n_f else None,
            "alarms": len(events[tag]), "false_alarms": len(false_alarms),
        }
        total_false += len(false_alarms)

    per_type: dict[str, dict[str, Any]] = {}
    for ftype in sorted({f.type for f in faults}):
        rows = [r for r in fault_rows if r["type"] == ftype]
        d = sum(1 for r in rows if r["detected"])
        per_type[ftype] = {"faults_total": len(rows), "faults_detected": d,
                           "detection_rate": round(d / len(rows), 4)}

    detected = [r for r in fault_rows if r["detected"]]
    lat = [r["latency_samples"] for r in detected]
    return {
        "detection_rate": round(len(detected) / len(faults), 4) if faults else None,
        "faults_total": len(faults),
        "faults_detected": len(detected),
        "false_alarm_count": total_false,
        "alarm_count": sum(len(v) for v in events.values()),
        "mean_detection_latency_samples": round(sum(lat) / len(lat), 2) if lat else None,
        "per_tag": per_tag,
        "per_fault_type": per_type,
        "faults": fault_rows,
        "meta": {"samples": len(times), "detection_window_samples": window},
    }


def replay_files(rules_path: str | Path, data: str | Path = DEFAULT_DATA,
                 faults: str | Path = DEFAULT_FAULTS, rules: dict | None = None) -> dict[str, Any]:
    rules = rules if rules is not None else load_rules(rules_path)
    times, cols = load_dataset(data)
    report = run_replay(rules, times, cols, load_faults(faults))
    report["meta"].update({
        "rules_file": str(rules_path),
        "dataset_sha256_16": _sha256(data),
        "faults_sha256_16": _sha256(faults),
    })
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Replay a rules file against the simulated dataset")
    ap.add_argument("--rules", default="alarms.yaml")
    ap.add_argument("--data", default=str(DEFAULT_DATA))
    ap.add_argument("--faults", default=str(DEFAULT_FAULTS))
    ap.add_argument("--out", default=None, help="write JSON report here (default: stdout)")
    args = ap.parse_args(argv)
    try:
        report = replay_files(args.rules, args.data, args.faults)
    except (RulesError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(report, indent=2)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n")
        print(f"detection_rate={report['detection_rate']} "
              f"false_alarms={report['false_alarm_count']} -> {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

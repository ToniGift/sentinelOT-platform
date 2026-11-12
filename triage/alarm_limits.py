"""Read-only alarm-limit routes, backed by the AlarmOps library.

SIMULATION ONLY. Every number here comes from replaying a generated,
fault-labelled sensor dataset. Nothing is read from, or written to, a
control network, and nothing is stored: a "change" exists only in the reply.

This is the only module that imports alarmops. The library is used from
alarmops/src as imported (see NOTICE.md); it is not modified.
"""
import json
import math
import os
import sys
import threading
from dataclasses import replace
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

REPO = Path(__file__).resolve().parents[1]
ALARMOPS = REPO / "alarmops"
if str(ALARMOPS / "src") not in sys.path:
    sys.path.insert(0, str(ALARMOPS / "src"))

from alarmops.gate import evaluate, load_gate              # noqa: E402
from alarmops.monitoring import analyse, load_log          # noqa: E402
from alarmops.replay import load_dataset, load_faults, run_replay  # noqa: E402
from alarmops.rules import LIMIT_KEYS, load_rules          # noqa: E402

MONITOR_LOGS = ("healthy", "drift")
HEAD_KEYS = ("detection_rate", "faults_detected", "faults_total",
             "false_alarm_count")

router = APIRouter(prefix="/api/alarmops")
_lock = threading.Lock()
_slots = threading.BoundedSemaphore(4)     # replays running at once
_plant = None


def _root():
    """Folder holding alarms.yaml, gate.yaml and data/. Read at first use.

    Default is plant/: the AlarmOps tags and dataset, unchanged, plus the
    sealer and conveyor tags of the showcase plant. Set ALARM_LIMITS_ROOT to
    alarmops to replay the original AlarmOps files instead.
    """
    p = Path(os.getenv("ALARM_LIMITS_ROOT", "plant"))
    return p if p.is_absolute() else REPO / p


class Plant:
    def __init__(self, root: Path):
        self.root = root
        self.rules = load_rules(root / "alarms.yaml")
        self.times, self.cols = load_dataset(root / "data" / "replay.csv")
        self.faults = load_faults(root / "data" / "faults.csv")
        self.gate = load_gate(root / "gate.yaml")
        self.base = run_replay(self.rules, self.times, self.cols, self.faults)
        self.logs = {}
        for n in MONITOR_LOGS:
            name = f"post_deploy_alarm_log_{n}.csv"
            p = root / "data" / name
            self.logs[n] = load_log(p if p.exists()
                                    else ALARMOPS / "data" / name)
        # tag -> [asset it is measured at, controller that reads it]
        m = root / "tag_assets.json"
        self.assets = json.loads(m.read_text(encoding="utf-8")) \
            if m.exists() else {}
        self.cache = {}

    def dataset(self):
        return {"samples": len(self.times), "faults": len(self.faults),
                "source": self.root.relative_to(REPO).as_posix()
                if self.root.is_relative_to(REPO) else self.root.name}


def plant() -> Plant:
    global _plant
    with _lock:
        if _plant is None or _plant.root != _root():
            _plant = Plant(_root())
        return _plant


def _head(rep):
    return {k: rep[k] for k in HEAD_KEYS}


def _fault(f):
    return {k: f[k] for k in ("fault_id", "tag", "type", "start", "end")}


@router.get("/baseline")
def baseline():
    """Replay the current limits. Lists every tag with its limits and score."""
    p = plant()
    tags = {}
    for tag, r in p.rules.items():
        if tag not in p.cols:
            continue
        s = p.base["per_tag"][tag]
        tags[tag] = {"unit": r.unit, **{k: getattr(r, k) for k in LIMIT_KEYS},
                     "deadband": r.deadband, "delay_samples": r.delay_samples,
                     "faults_total": s["faults_total"],
                     "faults_detected": s["faults_detected"],
                     "false_alarms": s["false_alarms"],
                     "assets": p.assets.get(tag, [])}
    return {"simulated": True, "dataset": p.dataset(), "gate": p.gate,
            "baseline": _head(p.base), "tags": tags}


@router.get("/compare")
def compare(request: Request, tag: str = "tank_level"):
    """Replay edited limits for one tag and apply the change gate.

    Limits come as query numbers: low_low, low, high, high_high. A limit
    that is left out keeps its current value.
    """
    p = plant()
    if tag not in p.rules or tag not in p.cols:
        raise HTTPException(404, f"unknown tag: {tag}")
    cur = p.rules[tag]
    vals = {}
    for k in LIMIT_KEYS:
        raw = request.query_params.get(k)
        if raw in (None, ""):
            vals[k] = getattr(cur, k)
            continue
        try:
            v = float(raw)
        except ValueError:
            raise HTTPException(400, f"{k} must be a number") from None
        if not math.isfinite(v) or abs(v) > 1e6:
            raise HTTPException(400, f"{k} is out of range")
        vals[k] = v
    if not vals["low_low"] < vals["low"] < vals["high"] < vals["high_high"]:
        raise HTTPException(
            400, "limits must satisfy low_low < low < high < high_high")

    key = (tag,) + tuple(vals[k] for k in LIMIT_KEYS)
    if key in p.cache:
        return p.cache[key]
    if not _slots.acquire(blocking=False):
        raise HTTPException(503, "busy, try again in a moment")
    try:
        rules = dict(p.rules)
        rules[tag] = replace(cur, **vals)
        head = run_replay(rules, p.times, p.cols, p.faults)
    finally:
        _slots.release()
    res = evaluate(p.base, head, p.gate)
    out = {"simulated": True, "dataset": p.dataset(), "tag": tag,
           "assets": p.assets.get(tag, []),
           "unit": cur.unit, "limits": vals,
           "current": {k: getattr(cur, k) for k in LIMIT_KEYS},
           "base": _head(p.base), "head": _head(head),
           "passed": res.passed, "violations": res.violations,
           "newly_missed": [_fault(f) for f in res.newly_missed],
           "newly_detected": [_fault(f) for f in res.newly_detected]}
    if len(p.cache) < 512:
        p.cache[key] = out
    return out


@router.get("/monitor")
def monitor(log: str = "healthy"):
    """Drift check on a bundled, simulated post-deploy alarm log."""
    p = plant()
    if log not in p.logs:
        raise HTTPException(
            400, f"log must be one of {', '.join(MONITOR_LOGS)}")
    tags, rows = p.logs[log]
    res = analyse(tags, rows, 24, 6, 2.0, 2.0)
    return {"simulated": True, "log": log, "drift": res["drift"],
            "baseline_per_hour": res["baseline_per_hour"],
            "recent_per_hour": res["recent_per_hour"],
            "threshold": res["threshold"]}

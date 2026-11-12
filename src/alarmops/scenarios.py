"""The three demo changes, measured. Shared by the demo branch tooling and the web page.

Every number returned here comes from replaying the labelled dataset; nothing is typed in.
Change B (a hard-coded credential) is not a limit change, so it has no replay figures.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from .gate import evaluate, load_gate
from .monitoring import analyse, load_log
from .replay import load_dataset, load_faults, run_replay
from .rules import load_rules_text

# ALARMOPS_ROOT lets an installed copy (e.g. the container) find alarms.yaml, gate.yaml and data/
ROOT = Path(os.environ.get("ALARMOPS_ROOT") or Path(__file__).resolve().parents[2])

# tank_level (high, high_high) after each demo change
CHANGE_A = (88, 95)   # widened: faults between 80 and 88 are no longer caught
CHANGE_C = (75, 88)   # tightened: still catches every labelled fault


def set_tank_limits_text(text: str, high: float, high_high: float) -> str:
    """Edit the FIRST tag's (tank_level) high and high_high limits in an alarms.yaml text."""
    for key, val in (("high_high", high_high), ("high", high)):
        text, n = re.subn(rf"(?m)^([ \t]+){key}: [\d.]+[ \t]*$", rf"\g<1>{key}: {val}", text, count=1)
        if n != 1:
            raise ValueError(f"could not find '{key}' in the rules text")
    return text


def _headline(rep: dict) -> dict[str, Any]:
    return {k: rep[k] for k in ("detection_rate", "faults_detected", "faults_total", "false_alarm_count")}


def build_report(root: Path = ROOT) -> dict[str, Any]:
    root = Path(root)
    base_text = (root / "alarms.yaml").read_text(encoding="utf-8")
    times, cols = load_dataset(root / "data" / "replay.csv")
    faults = load_faults(root / "data" / "faults.csv")
    gate = load_gate(root / "gate.yaml")

    def replay(text: str) -> dict:
        return run_replay(load_rules_text(text), times, cols, faults)

    base = replay(base_text)
    out: dict[str, Any] = {"baseline": _headline(base), "per_tag": base["per_tag"], "scenarios": {}}
    tank = load_rules_text(base_text)["tank_level"]
    out["tank"] = {"low_low": tank.low_low, "low": tank.low, "high": tank.high, "high_high": tank.high_high,
                   "deadband": tank.deadband, "delay_samples": tank.delay_samples, "unit": tank.unit}
    out["gate"] = gate

    for key, (hi, hh) in (("a", CHANGE_A), ("c", CHANGE_C)):
        rep = replay(set_tank_limits_text(base_text, hi, hh))
        res = evaluate(base, rep, gate)
        out["scenarios"][key] = {
            **_headline(rep), "high": hi, "high_high": hh,
            "blocked": not res.passed, "violations": res.violations,
            "newly_missed": [{k: f[k] for k in ("fault_id", "tag", "type", "start", "end")}
                             for f in res.newly_missed],
        }

    # data for the chart on the page: the tank level series and its labelled faults
    out["series"] = {"t": times, "tank_level": cols["tank_level"]}
    out["tank_faults"] = [
        {"fault_id": f["fault_id"], "type": f["type"], "start": f["start"], "end": f["end"],
         "detected": f["detected"]}
        for f in base["faults"] if f["tag"] == "tank_level"
    ]
    # hourly alarm totals of the two simulated post-deploy logs, for the alarm-rate graphs
    out["monitor"] = {}
    for name in ("healthy", "drift"):
        tags, rows = load_log(root / "data" / f"post_deploy_alarm_log_{name}.csv")
        res = analyse(tags, rows, 24, 6, 2.0, 2.0)
        out["monitor"][name] = {
            "hourly": [sum(r.values()) for r in rows], "baseline_hours": 24, "recent_hours": 6,
            "baseline_per_hour": res["baseline_per_hour"], "recent_per_hour": res["recent_per_hour"],
            "threshold": res["threshold"], "drift": res["drift"],
        }
    out["meta"] = {**base["meta"], "simulation": True}
    return out

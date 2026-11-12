"""The website's "lab": a fixed set of SAFE commands that run the real AlarmOps logic.

Nothing here runs a shell or touches the filesystem beyond reading the bundled data.
Inputs are numbers (range-checked) or a short text to scan. Results are text a CLI would
print, plus structured fields for the page. Secret values are never echoed back.
"""
from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

from .gate import evaluate
from .gate import load_gate
from .monitoring import analyse, diagnosis, load_log
from .replay import load_dataset, load_faults, run_replay
from .rules import load_rules_text
from .scenarios import ROOT
from .secretscan import scan_text

MAX_TEXT = 4000
LIMIT_KEYS = ("tank_low_low", "tank_low", "tank_high", "tank_high_high")
MONITOR_LOGS = ("healthy", "drift")


class LabError(ValueError):
    """Bad input from the page (reported as HTTP 400)."""


def _num(raw: str | None, name: str, default: float, lo: float, hi: float, integer: bool = False) -> float:
    if raw is None or raw == "":
        return default
    try:
        v = float(raw)
    except ValueError:
        raise LabError(f"{name} must be a number") from None
    if not math.isfinite(v) or not lo <= v <= hi:
        raise LabError(f"{name} must be between {lo:g} and {hi:g}")
    if integer and v != int(v):
        raise LabError(f"{name} must be a whole number")
    return int(v) if integer else v


def _headline(rep: dict) -> dict:
    return {k: rep[k] for k in ("detection_rate", "faults_detected", "faults_total", "false_alarm_count")}


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


class Lab:
    def __init__(self, root: Path = ROOT):
        root = Path(root)
        self.rules = load_rules_text((root / "alarms.yaml").read_text(encoding="utf-8"))
        self.times, self.cols = load_dataset(root / "data" / "replay.csv")
        self.faults = load_faults(root / "data" / "faults.csv")
        self.gate = load_gate(root / "gate.yaml")
        self.base = run_replay(self.rules, self.times, self.cols, self.faults)
        self.logs = {n: load_log(root / "data" / f"post_deploy_alarm_log_{n}.csv") for n in MONITOR_LOGS}
        self._cache: dict[tuple, dict] = {}

    # ---------------------------------------------------------------- replay
    def baseline(self) -> dict:
        b = self.base
        lines = [
            "$ python -m alarmops.replay --rules alarms.yaml",
            f"detection={_pct(b['detection_rate'])} ({b['faults_detected']}/{b['faults_total']} faults)"
            f"  false_alarms={b['false_alarm_count']}",
            "",
            f"{'tag':<15}{'detected':>10}{'false alarms':>14}",
        ]
        for tag, v in b["per_tag"].items():
            lines.append(f"{tag:<15}{str(v['faults_detected']) + '/' + str(v['faults_total']):>10}{v['false_alarms']:>14}")
        lines += ["", "by fault type: " + ", ".join(
            f"{t} {v['faults_detected']}/{v['faults_total']}" for t, v in b["per_fault_type"].items())]
        return {"command": lines[0][2:], "output": "\n".join(lines), "baseline": _headline(b)}

    # --------------------------------------------------------------- compare
    def parse_limits(self, q: dict[str, str]) -> dict:
        t = self.rules["tank_level"]
        vals = {
            "low_low": _num(q.get("tank_low_low"), "tank_low_low", t.low_low, 0, 200),
            "low": _num(q.get("tank_low"), "tank_low", t.low, 0, 200),
            "high": _num(q.get("tank_high"), "tank_high", t.high, 0, 200),
            "high_high": _num(q.get("tank_high_high"), "tank_high_high", t.high_high, 0, 200),
            "deadband": _num(q.get("deadband"), "deadband", t.deadband, 0, 50),
            "delay_samples": _num(q.get("delay_samples"), "delay_samples", t.delay_samples, 1, 50, integer=True),
        }
        if not vals["low_low"] < vals["low"] < vals["high"] < vals["high_high"]:
            raise LabError("limits must satisfy low_low < low < high < high_high")
        return vals

    def compare(self, q: dict[str, str]) -> dict:
        vals = self.parse_limits(q)
        key = tuple(sorted(vals.items()))
        if key in self._cache:
            return self._cache[key]
        rules = dict(self.rules)
        rules["tank_level"] = replace(rules["tank_level"], **vals)
        head = run_replay(rules, self.times, self.cols, self.faults)
        res = evaluate(self.base, head, self.gate)
        floor = evaluate(head, head, self.gate)
        yaml_text = (f"tank_level:\n  low_low: {vals['low_low']:g}\n  low: {vals['low']:g}\n"
                     f"  high: {vals['high']:g}\n  high_high: {vals['high_high']:g}\n")
        secrets = scan_text(yaml_text)

        out = [
            "$ python scripts/compare_replay.py --base-rules alarms.yaml --head-rules your_limits.yaml",
            f"tank_level (yours): {vals['low_low']:g} < {vals['low']:g} < {vals['high']:g} < {vals['high_high']:g}"
            f"  (deadband {vals['deadband']:g}, delay {vals['delay_samples']})",
            f"base : detection={_pct(self.base['detection_rate'])} false_alarms={self.base['false_alarm_count']}",
            f"head : detection={_pct(head['detection_rate'])} false_alarms={head['false_alarm_count']}",
            "GATE: PASS" if res.passed else "GATE: FAIL",
        ]
        out += [f"  - {v}" for v in res.violations]
        if res.newly_missed:
            out.append("faults this change no longer detects: " + ", ".join(
                f"{f['fault_id']} ({f['type']}, {f['tag']})" for f in res.newly_missed))
        if res.newly_detected:
            out.append("faults newly detected: " + ", ".join(f["fault_id"] for f in res.newly_detected))

        later = "ok" if res.passed and floor.passed else "skipped"
        stages = [
            {"stage": "plan", "job": "validate_rules", "status": "pass", "detail": "limits are in a valid order"},
            {"stage": "review", "job": "replay_review", "status": "pass" if res.passed else "fail",
             "detail": "; ".join(res.violations) or "no detection lost beyond the allowed drop"},
            {"stage": "test", "job": "replay_test", "status": "pass" if floor.passed else "fail",
             "detail": "; ".join(floor.violations) or "meets the absolute detection and false-alarm floors"}
            if res.passed else
            {"stage": "test", "job": "replay_test", "status": "skipped", "detail": "an earlier stage failed"},
            {"stage": "security", "job": "secret_guard",
             "status": "skipped" if later == "skipped" else ("fail" if secrets else "pass"),
             "detail": "an earlier stage failed" if later == "skipped" else "no credentials in the change"},
        ]
        for stage, job in (("compliance", "change_record, sbom"), ("deploy_staging", "deploy_staging"),
                           ("validate", "validate_staging")):
            stages.append({"stage": stage, "job": job,
                           "status": "skipped" if later == "skipped" else "gitlab",
                           "detail": "an earlier stage failed" if later == "skipped"
                           else "runs in the GitLab pipeline, not on this website"})
        stages.append({"stage": "approve", "job": "deploy_production",
                       "status": "skipped" if later == "skipped" else "manual",
                       "detail": "an earlier stage failed" if later == "skipped" else "waits for a person to approve"})
        stages.append({"stage": "monitor", "job": "monitor_alarm_rate", "status": "gitlab",
                       "detail": "runs on a schedule after release"})

        result = {
            "command": out[0][2:], "output": "\n".join(out), "limits": vals,
            "base": _headline(self.base), "head": _headline(head),
            "passed": res.passed, "violations": res.violations,
            "newly_missed": [{k: f[k] for k in ("fault_id", "tag", "type", "start", "end")}
                             for f in res.newly_missed],
            "stages": stages,
            # per tank fault: is it detected with these limits? (the page's chart uses this)
            "tank_detected": {f["fault_id"]: f["detected"] for f in head["faults"] if f["tag"] == "tank_level"},
        }
        if len(self._cache) < 512:
            self._cache[key] = result
        return result

    # ------------------------------------------------------------------ scan
    def scan(self, text: str) -> dict:
        if not isinstance(text, str):
            raise LabError("text must be a string")
        if len(text) > MAX_TEXT:
            raise LabError(f"text is limited to {MAX_TEXT} characters")
        found = scan_text(text)
        out = ["$ python scripts/secret_guard.py   (on the text you pasted)"]
        if not found:
            out.append("secret_guard: no hard-coded credentials found")
        else:
            out.append("secret_guard: BLOCKED, possible hard-coded credentials:")
            out += [f"  line {n}: {name}  (value not printed)" for n, name in found]
        return {"command": out[0][2:], "output": "\n".join(out), "blocked": bool(found),
                "findings": [{"line": n, "pattern": name} for n, name in found]}

    # --------------------------------------------------------------- monitor
    def monitor(self, name: str) -> dict:
        if name not in self.logs:
            raise LabError(f"log must be one of {', '.join(MONITOR_LOGS)}")
        tags, rows = self.logs[name]
        res = analyse(tags, rows, 24, 6, 2.0, 2.0)
        out = [f"$ python scripts/monitor.py --log data/post_deploy_alarm_log_{name}.csv",
               f"baseline={res['baseline_per_hour']:.2f}/h recent={res['recent_per_hour']:.2f}/h "
               f"threshold={res['threshold']:.2f}/h"]
        if res["drift"]:
            out += ["MONITOR: DRIFT DETECTED", "", diagnosis(res, f"{name} log", 24, 6), "",
                    "[in GitLab, this opens an issue; the website does not]"]
        else:
            out.append("MONITOR: OK, no drift")
        return {"command": out[0][2:], "output": "\n".join(out), "drift": res["drift"],
                "baseline_per_hour": res["baseline_per_hour"], "recent_per_hour": res["recent_per_hour"],
                "threshold": res["threshold"]}

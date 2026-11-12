"""Change gate: compare base vs head replay reports against gate.yaml."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

MARKER = "<!-- alarmops-replay-summary -->"
GATE_KEYS = ("min_detection_rate", "max_detection_rate_drop",
             "max_false_alarms", "max_false_alarm_increase")


class GateError(ValueError):
    pass


def load_gate(path: str | Path) -> dict[str, float]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    missing = [k for k in GATE_KEYS if k not in data]
    if missing:
        raise GateError(f"gate file missing keys: {missing}")
    return {k: float(data[k]) for k in GATE_KEYS}


@dataclass
class GateResult:
    passed: bool
    violations: list[str] = field(default_factory=list)
    detection_delta: float = 0.0
    false_alarm_delta: int = 0
    newly_missed: list[dict[str, Any]] = field(default_factory=list)
    newly_detected: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def evaluate(base: dict, head: dict, gate: dict[str, float]) -> GateResult:
    d_rate = round(head["detection_rate"] - base["detection_rate"], 4)
    d_fa = head["false_alarm_count"] - base["false_alarm_count"]
    v: list[str] = []
    if head["detection_rate"] < gate["min_detection_rate"]:
        v.append(f"detection rate {head['detection_rate']:.1%} is below the minimum "
                 f"{gate['min_detection_rate']:.1%}")
    if -d_rate > gate["max_detection_rate_drop"] + 1e-9:
        v.append(f"detection rate fell by {-d_rate:.1%}, more than the allowed "
                 f"{gate['max_detection_rate_drop']:.1%}")
    if head["false_alarm_count"] > gate["max_false_alarms"]:
        v.append(f"{head['false_alarm_count']} false alarms exceeds the maximum "
                 f"{int(gate['max_false_alarms'])}")
    if d_fa > gate["max_false_alarm_increase"]:
        v.append(f"false alarms rose by {d_fa}, more than the allowed "
                 f"{int(gate['max_false_alarm_increase'])}")
    bf = {f["fault_id"]: f for f in base["faults"]}
    hf = {f["fault_id"]: f for f in head["faults"]}
    missed = [hf[i] for i in hf if bf.get(i, {}).get("detected") and not hf[i]["detected"]]
    found = [hf[i] for i in hf if not bf.get(i, {}).get("detected") and hf[i]["detected"]]
    return GateResult(not v, v, d_rate, d_fa, missed, found)


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.1%}"


def render_markdown(base: dict, head: dict, res: GateResult, gate: dict[str, float]) -> str:
    status = "PASS" if res.passed else "FAIL"
    icon = "✅" if res.passed else "❌"
    lines = [
        MARKER,
        f"## {icon} AlarmOps replay gate: {status}",
        "",
        "Every figure below was measured by replaying the simulated, fault-labelled "
        "dataset against each rules file. (Simulation only; no real plant data.)",
        "",
        "| Metric | Target branch | This change | Delta |",
        "|---|---|---|---|",
        f"| Fault detection rate | {_pct(base['detection_rate'])} "
        f"({base['faults_detected']}/{base['faults_total']}) | {_pct(head['detection_rate'])} "
        f"({head['faults_detected']}/{head['faults_total']}) | {res.detection_delta:+.1%} "
        f"({head['faults_detected'] - base['faults_detected']:+d} faults) |",
        f"| False alarms | {base['false_alarm_count']} | {head['false_alarm_count']} "
        f"| {res.false_alarm_delta:+d} |",
        f"| Total alarms raised | {base['alarm_count']} | {head['alarm_count']} "
        f"| {head['alarm_count'] - base['alarm_count']:+d} |",
        "",
        "**Per tag (this change)**",
        "",
        "| Tag | Detected | False alarms | Alarms |",
        "|---|---|---|---|",
    ]
    for tag, t in head["per_tag"].items():
        bt = base["per_tag"].get(tag, {})
        lines.append(f"| {tag} | {t['faults_detected']}/{t['faults_total']} "
                     f"(was {bt.get('faults_detected', '?')}) | {t['false_alarms']} | {t['alarms']} |")
    if res.newly_missed:
        lines += ["", "**Faults this change no longer detects**", "",
                  "| Fault | Tag | Type |", "|---|---|---|"]
        lines += [f"| {f['fault_id']} | {f['tag']} | {f['type']} |" for f in res.newly_missed]
    if res.newly_detected:
        lines += ["", f"Faults newly detected: {', '.join(f['fault_id'] for f in res.newly_detected)}"]
    lines += ["", "**Gate thresholds** (`gate.yaml`)", "",
              f"- min detection rate: {gate['min_detection_rate']:.0%}",
              f"- max detection-rate drop vs target: {gate['max_detection_rate_drop']:.0%}",
              f"- max false alarms: {int(gate['max_false_alarms'])}",
              f"- max false-alarm increase vs target: {int(gate['max_false_alarm_increase'])}"]
    if res.violations:
        lines += ["", "**Blocked because:**", ""] + [f"- {x}" for x in res.violations]
    else:
        lines += ["", "No gate thresholds were breached."]
    lines += ["", f"_dataset `{head['meta'].get('dataset_sha256_16')}` · "
                  f"detection window {head['meta']['detection_window_samples']} samples_"]
    return "\n".join(lines) + "\n"

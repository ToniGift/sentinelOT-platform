"""Post-deploy alarm-rate drift detection (used by scripts/monitor.py and the web lab)."""
from __future__ import annotations

import csv


def load_log(path):
    with open(path, newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise ValueError("alarm log is empty")
    tags = [c for c in rows[0] if c != "hour"]
    return tags, [{t: int(r[t]) for t in tags} for r in rows]


def analyse(tags, rows, baseline_hours, recent_hours, factor, min_increase):
    if len(rows) < baseline_hours + recent_hours:
        raise ValueError(f"need at least {baseline_hours + recent_hours} hours of log, got {len(rows)}")
    base, recent = rows[:baseline_hours], rows[-recent_hours:]
    mean = lambda rs, t: sum(r[t] for r in rs) / len(rs)
    per_tag = {t: {"baseline": mean(base, t), "recent": mean(recent, t)} for t in tags}
    b_total = sum(v["baseline"] for v in per_tag.values())
    r_total = sum(v["recent"] for v in per_tag.values())
    threshold = max(b_total * factor, b_total + min_increase)
    return {"baseline_per_hour": b_total, "recent_per_hour": r_total, "threshold": threshold,
            "drift": r_total > threshold, "per_tag": per_tag}


def diagnosis(res, log_name, baseline_hours, recent_hours):
    top = max(res["per_tag"].items(), key=lambda kv: kv[1]["recent"] - kv[1]["baseline"])
    lines = [
        f"Alarm rate drifted after deployment (simulated log `{log_name}`).",
        "",
        f"- Baseline (first {baseline_hours} h): {res['baseline_per_hour']:.2f} alarms/hour",
        f"- Recent (last {recent_hours} h): {res['recent_per_hour']:.2f} alarms/hour",
        f"- Drift threshold: {res['threshold']:.2f} alarms/hour",
        "",
        "| Tag | Baseline /h | Recent /h |", "|---|---|---|",
    ]
    lines += [f"| {t} | {v['baseline']:.2f} | {v['recent']:.2f} |" for t, v in res["per_tag"].items()]
    lines += [
        "",
        f"**Largest contributor:** `{top[0]}` "
        f"({top[1]['baseline']:.2f} -> {top[1]['recent']:.2f} alarms/hour).",
        "",
        "Things to check (hypotheses, not conclusions):",
        f"- Was a limit, deadband or delay for `{top[0]}` tightened in a recent change record?",
        "- Is the signal itself drifting, or is the sensor chattering near a limit?",
        "- Consider a rollback of the latest alarm-limit change and re-run the replay gate.",
    ]
    return "\n".join(lines)

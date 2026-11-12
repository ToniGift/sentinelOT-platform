#!/usr/bin/env python3
"""Seeded generator for the simulated AlarmOps replay dataset.

Writes (next to this script):
  replay.csv                      t,tank_level,pump_pressure,flow_rate
  faults.csv                      labelled injected faults (ground truth)
  post_deploy_alarm_log_healthy.csv / post_deploy_alarm_log_drift.csv
                                  hourly alarm counts used by scripts/monitor.py

Everything is simulated. Stdlib only; fully deterministic for a given seed.
"""
from __future__ import annotations

import argparse
import csv
import math
import random
from pathlib import Path

SEED = 20261020
N_SAMPLES = 6000

# Process model per tag. Limits here are only used to place faults between
# 'high' and 'high_high' (or 'low' and 'low_low'); the rules under test live
# in alarms.yaml.
TAGS = {
    "tank_level":    dict(base=50.0, amp=6.0,  period=1500, noise=1.2,  ll=10.0, l=20.0, h=80.0,  hh=90.0,  nd=2),
    "pump_pressure": dict(base=5.0,  amp=0.3,  period=1100, noise=0.08, ll=2.0,  l=3.0,  h=7.0,   hh=8.0,   nd=1),
    "flow_rate":     dict(base=120.0, amp=8.0, period=900,  noise=2.5,  ll=60.0, l=80.0, h=160.0, hh=180.0, nd=1),
}
FAULT_TYPES = ["spike", "spike", "spike", "drift", "drift", "stuck", "stuck"]
SPIKE_LEN, DRIFT_RAMP, DRIFT_HOLD, STUCK_LEN = 6, 100, 10, 40


def signal(cfg, t, phase):
    return cfg["base"] + cfg["amp"] * math.sin(2 * math.pi * (t + phase) / cfg["period"])


def poisson(rng: random.Random, lam: float) -> int:
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def build(out_dir: Path, seed: int = SEED, n: int = N_SAMPLES) -> None:
    rng = random.Random(seed)
    series: dict[str, list[float]] = {}
    faults: list[dict] = []
    fid = 0
    for ti, (tag, cfg) in enumerate(TAGS.items()):
        phase = rng.uniform(0, cfg["period"])
        vals = [signal(cfg, t, phase) + rng.gauss(0, cfg["noise"]) for t in range(n)]
        types = FAULT_TYPES[:]
        rng.shuffle(types)
        for i, ftype in enumerate(types):
            start = 500 + ti * 120 + i * 800 + rng.randint(-80, 80)
            down = rng.random() < 0.25
            if down:
                target = cfg["l"] - rng.uniform(0.25, 0.75) * (cfg["l"] - cfg["ll"])
            else:
                target = cfg["h"] + rng.uniform(0.25, 0.75) * (cfg["hh"] - cfg["h"])
            if ftype == "spike":
                end = start + SPIKE_LEN - 1
                for t in range(start, end + 1):
                    vals[t] = target + rng.gauss(0, cfg["noise"] * 0.3)
            elif ftype == "drift":
                end = start + DRIFT_RAMP + DRIFT_HOLD - 1
                for t in range(start, end + 1):
                    p = min(1.0, (t - start + 1) / DRIFT_RAMP)
                    vals[t] = vals[t] + (target - vals[t]) * p
            else:  # stuck: reading frozen at an abnormal value
                end = start + STUCK_LEN - 1
                for t in range(start, end + 1):
                    vals[t] = target
            fid += 1
            faults.append(dict(fault_id=f"F{fid:02d}", tag=tag, type=ftype,
                               direction="low" if down else "high", start=start, end=end))
        series[tag] = vals

    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "replay.csv", "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["t", *TAGS])
        for t in range(n):
            w.writerow([t, *(f"{series[tag][t]:.4f}" for tag in TAGS)])
    with open(out_dir / "faults.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["fault_id", "tag", "type", "direction", "start", "end"], lineterminator="\n")
        w.writeheader()
        w.writerows(sorted(faults, key=lambda f: (f["start"], f["tag"])))

    # Simulated post-deploy hourly alarm counts (for the monitor job).
    hours = 72
    for name, drifting in (("healthy", False), ("drift", True)):
        r = random.Random(seed + (1 if drifting else 0))
        with open(out_dir / f"post_deploy_alarm_log_{name}.csv", "w", newline="") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(["hour", *TAGS])
            for h in range(hours):
                row = []
                for tag in TAGS:
                    lam = 1.0
                    if drifting and tag == "pump_pressure" and h >= 40:
                        lam = 1.0 + 0.45 * (h - 40)  # simulated post-change nuisance alarms
                    row.append(poisson(r, lam))
                w.writerow([h, *row])


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", default=str(Path(__file__).parent))
    ap.add_argument("--seed", type=int, default=SEED)
    a = ap.parse_args()
    build(Path(a.out_dir), a.seed)
    print(f"wrote dataset to {a.out_dir} (seed={a.seed})")

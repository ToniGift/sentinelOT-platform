#!/usr/bin/env python3
"""Generate the simulated replay dataset for the platform's demo plant.

This runs the AlarmOps generator (alarmops/data/generate_dataset.py), unchanged,
with two extra tags added after its own three: sealer_temperature and
conveyor_speed. The generator draws from one seeded random stream tag by tag,
so the tank, pump and flow series and their 21 faults are identical to the
AlarmOps dataset, and the new tags add 7 labelled faults each (F22 to F35).

Everything is simulated. Run from the repo root:
    python plant/generate_dataset.py
"""
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
GEN = HERE.parent / "alarmops" / "data" / "generate_dataset.py"

# Process model for the extra tags (same fields the AlarmOps generator uses).
# The limits only place the injected faults; the rules under test are in
# plant/alarms.yaml.
EXTRA_TAGS = {
    "sealer_temperature": dict(base=160.0, amp=2.0, period=1300, noise=0.8,
                               ll=100.0, l=120.0, h=190.0, hh=205.0, nd=1),
    "conveyor_speed": dict(base=1200.0, amp=8.0, period=700, noise=4.0,
                           ll=600.0, l=900.0, h=1500.0, hh=1650.0, nd=0),
}


def main():
    spec = importlib.util.spec_from_file_location("alarmops_generate", GEN)
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    gen.TAGS = {**gen.TAGS, **EXTRA_TAGS}
    gen.build(HERE / "data", gen.SEED, gen.N_SAMPLES)
    print(f"wrote plant dataset to {HERE / 'data'} (seed={gen.SEED}, "
          f"tags={', '.join(gen.TAGS)})")


if __name__ == "__main__":
    main()

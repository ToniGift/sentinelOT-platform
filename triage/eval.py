"""Run scenarios through the full pipeline, optionally several times.
Usage:
  python eval.py dev [runs]        12 development scenarios
  python eval.py heldout [runs]    first held-out set (h01-h10, now used)
  python eval.py heldout2 [runs]   fresh held-out set (x01-x10)
Example: python eval.py dev 3
"""
import csv
import sys
import time
from collections import defaultdict

from orchestrator import run_triage
from scenarios import technique_match

which = sys.argv[1] if len(sys.argv) > 1 else "dev"
runs = int(sys.argv[2]) if len(sys.argv) > 2 else 1
if which == "heldout":
    from scenarios_heldout import SCENARIOS, EXPECTED, tech_ok
elif which == "heldout2":
    from scenarios_heldout2 import SCENARIOS, EXPECTED, tech_ok
else:
    from scenarios import SCENARIOS, EXPECTED

    def tech_ok(got, exp):
        want = exp["techniques"]
        return technique_match(got, want) if want else not got

rows, stab, per_run = [], defaultdict(lambda: [0, 0]), []
for run in range(1, runs + 1):
    v_ok = t_ok = 0
    print(f"\n--- run {run} of {runs} ---")
    for sid, alert in SCENARIOS.items():
        try:
            r = run_triage(alert)
        except Exception as e:
            print(sid, "FAILED:", e)
            rows.append({"run": run, "scenario": sid, "verdict": "FAILED"})
            continue
        exp = EXPECTED[sid]
        got = [t["id"] for t in r["attack"]["techniques"]]
        vok = r["triage"]["verdict"] == exp["verdict"]
        tok = tech_ok(got, exp)
        v_ok += vok
        t_ok += tok
        stab[sid][0] += vok
        stab[sid][1] += tok
        rows.append({
            "run": run, "scenario": sid,
            "verdict": r["triage"]["verdict"],
            "expected_verdict": exp["verdict"], "verdict_ok": vok,
            "priority": r["triage"]["priority"],
            "techniques": " ".join(got),
            "expected_techniques": " ".join(exp["techniques"]),
            "technique_ok": tok,
            "injection_flag": r["security_flags"]["embedded_instructions"],
            "notes": " | ".join(r["notes"]),
            "intel_items": len(r["intel"]["items"]),
            "intel_dropped": r["intel"]["dropped_unverified"],
            "step_failures": len(r["errors"]),
            "seconds": r["total_seconds"],
            "prompt_tokens": sum(x["prompt_tokens"] or 0 for x in r["trace"]),
            "completion_tokens": sum(x["completion_tokens"] or 0
                                     for x in r["trace"]),
        })
        print(f"{sid}: {r['triage']['verdict']:<14} {r['triage']['priority']}"
              f"  verdict_ok={vok} technique_ok={tok}"
              f"  {r['total_seconds']}s")
    per_run.append((v_ok, t_ok))
    print(f"run {run}: verdicts {v_ok}/{len(SCENARIOS)}, "
          f"techniques {t_ok}/{len(SCENARIOS)}")

good = [r for r in rows if "verdict_ok" in r]
name = f"eval_{which}_{time.strftime('%Y%m%d_%H%M%S')}.csv"
if good:
    fields = list(good[0].keys())
    with open(name, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

n = len(SCENARIOS)
vs, ts = [p[0] for p in per_run], [p[1] for p in per_run]
print(f"\n=== {which}: {runs} run(s) ===")
print(f"Verdicts correct:   {min(vs)}-{max(vs)} of {n} per run")
print(f"Techniques correct: {min(ts)}-{max(ts)} of {n} per run")
print("Per scenario (verdict ok / technique ok, out of runs):")
for sid, (a, b) in stab.items():
    flag = "" if a == runs else "   <-- verdict not stable"
    print(f"  {sid}  {a}/{runs}  {b}/{runs}{flag}")
print(f"Saved {name}")

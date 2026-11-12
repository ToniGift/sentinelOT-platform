"""Run the full five-agent pipeline on one scenario.
Usage: python run_pipeline.py s01
"""
import sys

from orchestrator import run_triage
from scenarios import SCENARIOS, EXPECTED

sid = sys.argv[1] if len(sys.argv) > 1 else "s01"
r = run_triage(SCENARIOS[sid])
t = r["triage"]

print(f"\n=== {sid}: {r['alert']['title']} ===")
print(f"VERDICT  {t['verdict']} (expected {EXPECTED[sid]['verdict']})  "
      f"{t['priority']}  confidence {t['confidence']}")
print("IMPACT  ", t["process_impact"])
print("REASON  ", t["reasoning"])
print("\nATT&CK for ICS:")
for x in r["attack"]["techniques"] or [{"id": "-", "name": "none",
                                         "rationale": ""}]:
    print(f"  {x['id']}  {x['name']}  - {x['rationale']}")
print("  expected:", EXPECTED[sid]["techniques"] or "none",
      f"| dropped invalid IDs: {r['attack']['dropped_invalid']}")
print("\nThreat intel:", r["intel"]["summary"])
for i in r["intel"]["items"]:
    tag = "" if i["trusted"] else "  [UNVERIFIED SOURCE]"
    print(f"  - {i['finding']}\n    {i['url']}{tag}")
print(f"  dropped (URL not retrieved): {r['intel']['dropped_unverified']}")
print("\nRecommended actions:")
for a in r["advice"]["actions"]:
    print(f"  [{a['type']}] {a['action']}")
print("\nTrace:")
print(f"  {'step':<9}{'model':<36}{'sec':<7}{'in':<7}{'out':<7}status")
for x in r["trace"]:
    print(f"  {x['step']:<9}{x['model']:<36}{x['seconds']:<7}"
          f"{str(x['prompt_tokens'] or '-'):<7}"
          f"{str(x['completion_tokens'] or '-'):<7}{x['status']}")
print(f"  total {r['total_seconds']}s (wall clock; steps added up: "
      f"{r['sum_step_seconds']}s)")
if r["errors"]:
    print("\nERRORS:", *r["errors"], sep="\n  ")

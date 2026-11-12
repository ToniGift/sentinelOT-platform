"""Phase 1 baseline: Triage step only (no intel, no mapping).
Usage:
  python run_baseline.py s01      # one scenario, full output
  python run_baseline.py          # all 12 scenarios, summary table
"""
import json
import sys
import time

from assets import lookup_asset
from config import MODELS
from llm import call_json
from prompts import TRIAGE_SYS
from scenarios import SCENARIOS, EXPECTED
from schemas import TriageResult


def run(alert):
    ctx = {"src": lookup_asset(alert.src_asset or alert.src_ip),
           "dst": lookup_asset(alert.dst_asset or alert.dst_ip)}
    payload = {"alert": alert.model_dump(), "assets": ctx}
    t0 = time.time()
    out, usage = call_json(MODELS["triage"], TRIAGE_SYS,
                           json.dumps(payload), TriageResult)
    return out, usage, round(time.time() - t0, 1)


ids = sys.argv[1:] or list(SCENARIOS)
rows = []
for sid in ids:
    try:
        res, u, secs = run(SCENARIOS[sid])
    except Exception as e:
        print(sid, "FAILED:", e)
        rows.append((sid, "FAILED", "-", "-", "-", "-"))
        continue
    exp = EXPECTED[sid]["verdict"]
    rows.append((sid, res.verdict, exp, res.priority,
                 f"{res.confidence:.2f}", f"{secs}s"))
    if len(ids) == 1:
        print(json.dumps(res.model_dump(), indent=2))
        print("usage:", u.prompt_tokens, "in /", u.completion_tokens, "out")

print()
print(f"{'id':<5}{'got':<15}{'expected':<15}{'prio':<6}{'conf':<6}time")
for r in rows:
    mark = "" if r[1] == r[2] else ("  <-- differs" if r[1] != "FAILED" else "")
    print(f"{r[0]:<5}{r[1]:<15}{r[2]:<15}{r[3]:<6}{r[4]:<6}{r[5]}{mark}")
ok = sum(1 for r in rows if r[1] == r[2])
print(f"\n{ok}/{len(rows)} verdicts match expected labels")

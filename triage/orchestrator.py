import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

from assets import lookup_asset
from attack_ics import catalogue, load_ics
from config import MODELS
from guards import (check_evidence, clamp_priority, consistent,
                    detect_injection)
from intel import canon, is_trusted, search
from llm import call_json
from prompts import (ADVISOR_SYS, INTAKE_SYS, INTEL_SYS, MAPPER_SYS,
                     TRIAGE_SYS)
from schemas import (AdvisorResult, Indicators, IntakeResult, IntelResult,
                     MapperResult, TriageResult)

TECHS = load_ics()
CATALOGUE = catalogue(TECHS)
NAMES = {c["id"]: c["name"] for c in CATALOGUE}
RUN_BUDGET_S = float(os.getenv("RUN_BUDGET_S", "200"))
ORDER = {"intake": 0, "search": 1, "intel": 2, "mapper": 3,
         "triage": 4, "triage_review": 4.5, "advisor": 5}


def step(trace, errors, name, system, payload, schema, required=False,
         model_key=None):
    """Run one LLM agent. Records a trace row. Optional agents degrade
    gracefully (return None); required agents re-raise."""
    t0 = time.time()
    model = MODELS[model_key or name]
    row = {"step": name, "model": model, "prompt_tokens": None,
           "completion_tokens": None}
    try:
        out, u = call_json(model, system,
                           json.dumps(payload, ensure_ascii=False), schema)
        row.update(status="ok",
                   prompt_tokens=getattr(u, "prompt_tokens", None),
                   completion_tokens=getattr(u, "completion_tokens", None))
        return out
    except Exception as e:
        row["status"] = "failed"
        errors.append(f"{name} failed: {e}")
        if required:
            raise
        return None
    finally:
        row["seconds"] = round(time.time() - t0, 2)
        trace.append(row)


def _search_all(queries, errors):
    """Run the (up to 3) searches in parallel, de-duplicate by URL."""
    def one(q):
        try:
            return search(q)
        except Exception as e:
            errors.append(f"search failed for '{q}': {e}")
            return []

    with ThreadPoolExecutor(max_workers=3) as ex:
        results = list(ex.map(one, queries))
    hits, seen = [], set()
    for res in results:
        for h in res:
            key = canon(h.get("url"))
            if h.get("url") and key not in seen:
                seen.add(key)
                hits.append(h)
    return hits


def _intel_branch(alert, intake, trace, errors):
    t0 = time.time()
    hits = _search_all(intake.search_queries[:3], errors)
    trace.append({"step": "search", "model": "tavily", "status": "ok",
                  "seconds": round(time.time() - t0, 2),
                  "prompt_tokens": None, "completion_tokens": None,
                  "hits": len(hits)})
    trust = {h["url"]: is_trusted(h["url"]) for h in hits}
    intel = None
    if hits:
        intel = step(trace, errors, "intel", INTEL_SYS,
                     {"alert": {"title": alert.title,
                                "description": alert.description},
                      "results": [{"title": h["title"], "url": h["url"],
                                   "content": h["content"]} for h in hits]},
                     IntelResult)
    if intel is None:
        intel = IntelResult(summary="No threat intelligence retrieved.",
                            items=[])
    kept = [i for i in intel.items if i.url in trust]          # validator
    return {"summary": intel.summary,
            "items": [{**i.model_dump(), "trusted": trust[i.url]}
                      for i in kept],
            "dropped_unverified": len(intel.items) - len(kept)}


def _mapper_branch(alert, intake, ctx, trace, errors):
    text = " ".join([alert.title, alert.description,
                     alert.protocol or "", intake.summary])
    mapped = step(trace, errors, "mapper", MAPPER_SYS,
                  {"alert": text, "assets": ctx, "catalogue": CATALOGUE},
                  MapperResult)
    techniques, ids, dropped = [], set(), 0
    for t in (mapped.techniques if mapped else []):                # validator
        if t.id in NAMES and t.id not in ids:
            ids.add(t.id)
            techniques.append({"id": t.id, "name": NAMES[t.id],
                               "rationale": t.rationale})
        elif t.id not in NAMES:
            dropped += 1
    return {"techniques": techniques, "dropped_invalid": dropped}


def run_triage(alert, trace_sink=None) -> dict:
    """trace_sink: optional list that receives trace rows as steps finish
    (used by the web app to show live progress)."""
    t_start = time.time()
    trace = trace_sink if trace_sink is not None else []
    errors, notes = [], []
    ctx = {"src": lookup_asset(alert.src_asset or alert.src_ip),
           "dst": lookup_asset(alert.dst_asset or alert.dst_ip)}

    # code-level prompt-injection check on every alert text field
    code_hits = detect_injection(alert.title, alert.description,
                                 *[str(v) for v in alert.raw.values()])

    # 1 Intake
    intake = step(trace, errors, "intake", INTAKE_SYS,
                  {"alert": alert.model_dump(), "assets": ctx}, IntakeResult)
    if intake is None:
        intake = IntakeResult(summary=alert.title, indicators=Indicators(),
                              search_queries=[alert.title])
    inj = bool(code_hits) or intake.embedded_instructions
    flags = {"embedded_instructions": inj,
             "note": ((intake.embedded_instructions_note
                       or "matched: " + "; ".join(code_hits[:3]))
                      if inj else "")}
    intake_out = intake.model_dump()
    intake_out["embedded_instructions"] = inj

    # 2 + 3 run side by side: (search -> intel) and mapper
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_intel = ex.submit(_intel_branch, alert, intake, trace, errors)
        f_map = ex.submit(_mapper_branch, alert, intake, ctx, trace, errors)
        intel_out, attack_out = f_intel.result(), f_map.result()

    # 4 Triage (required)
    triage_payload = {"alert": alert.model_dump(), "assets": ctx,
                      "intake": intake_out, "intel": intel_out,
                      "attack": attack_out}
    triage = step(trace, errors, "triage", TRIAGE_SYS, triage_payload,
                  TriageResult, required=True)

    # verdict and priority must agree: one re-check, then a code fallback
    if not consistent(triage.verdict, triage.priority):
        pair = f"{triage.verdict}/{triage.priority}"
        review = step(trace, errors, "triage_review", TRIAGE_SYS,
                      {**triage_payload, "review": {
                          "previous_answer": triage.model_dump(),
                          "problem": "verdict and priority disagree. Allowed "
                          "pairs: escalate=P1/P2, investigate=P2/P3, "
                          "likely_benign=P3/P4. Decide which is right from "
                          "the evidence and return a corrected answer."}},
                      TriageResult, model_key="triage")
        if review and consistent(review.verdict, review.priority):
            triage = review
            notes.append(f"Verdict and priority disagreed ({pair}); the "
                         "triage step was re-checked once.")
        else:
            old = triage.priority
            triage.priority = clamp_priority(triage.verdict, old)
            notes.append(f"Priority adjusted from {old} to {triage.priority} "
                         f"to agree with the verdict ({triage.verdict}).")

    # evidence must cite data that exists
    kept, dropped = check_evidence(triage.evidence, triage_payload)
    triage.evidence = kept
    if dropped:
        notes.append(f"{len(dropped)} evidence item(s) removed because they "
                     "cited data that does not exist.")

    # 5 Advisor (optional; skipped if the run is already very slow)
    if time.time() - t_start > RUN_BUDGET_S:
        advice = None
        notes.append(f"Recommended actions were skipped because the run took "
                     f"more than {int(RUN_BUDGET_S)} seconds (the model "
                     "service was slow).")
    else:
        advice = step(trace, errors, "advisor", ADVISOR_SYS,
                      {"triage": triage.model_dump(), "assets": ctx,
                       "attack": attack_out}, AdvisorResult)
    advice_out = (advice.model_dump() if advice else
                  {"summary": "Advisor unavailable.", "actions": []})

    trace.sort(key=lambda r: ORDER[r["step"]])
    return {"alert": alert.model_dump(), "intake": intake_out,
            "intel": intel_out, "attack": attack_out,
            "triage": triage.model_dump(), "advice": advice_out,
            "security_flags": flags, "notes": notes,
            "evidence_dropped": len(dropped),
            "trace": trace, "errors": errors,
            "total_seconds": round(time.time() - t_start, 2),   # wall clock
            "sum_step_seconds": round(sum(r["seconds"] for r in trace), 2)}

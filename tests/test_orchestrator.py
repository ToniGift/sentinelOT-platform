"""Offline test of the pipeline logic with fake LLM and search."""
import orchestrator as o
from schemas import (AdvisorResult, Action, Indicators, IntakeResult,
                     IntelItem, IntelResult, MapperResult, Technique,
                     TriageResult)
from scenarios import SCENARIOS


class U:
    prompt_tokens, completion_tokens = 10, 5


def fake_call_json(model, system, user, schema, **kw):
    if schema is IntakeResult:
        return IntakeResult(summary="s", indicators=Indicators(),
                            search_queries=["a", "b", "c", "d"]), U()
    if schema is IntelResult:
        return IntelResult(summary="x", items=[
            IntelItem(title="real", url="https://cisa.gov/x", finding="f"),
            IntelItem(title="made up", url="https://evil.test/y",
                      finding="f")]), U()
    if schema is MapperResult:
        return MapperResult(techniques=[
            Technique(id="T1692.001", name="WRONG NAME", rationale="r"),
            Technique(id="T0855", name="revoked id", rationale="r"),
            Technique(id="T9999", name="invented", rationale="r")]), U()
    if schema is TriageResult:
        return TriageResult(verdict="escalate", priority="P1",
                            confidence=0.9, process_impact="i",
                            reasoning="r", evidence=["e"]), U()
    return AdvisorResult(summary="s", actions=[
        Action(action="check logs", type="read_only")]), U()


def test_pipeline_validators(monkeypatch):
    searched = []

    def fake_search(q):
        searched.append(q)
        return [{"title": "real", "url": "https://cisa.gov/x",
                 "content": "c", "trusted": True}]

    monkeypatch.setattr(o, "call_json", fake_call_json)
    monkeypatch.setattr(o, "search", fake_search)
    r = o.run_triage(SCENARIOS["s01"])

    assert len(searched) == 3                      # queries capped at 3
    assert [i["url"] for i in r["intel"]["items"]] == ["https://cisa.gov/x"]
    assert r["intel"]["dropped_unverified"] == 1   # invented URL dropped
    ids = [t["id"] for t in r["attack"]["techniques"]]
    assert ids == ["T1692.001"]                    # revoked + invented gone
    assert r["attack"]["techniques"][0]["name"] == o.NAMES["T1692.001"]
    assert r["attack"]["dropped_invalid"] == 2
    assert [x["step"] for x in r["trace"]] == [
        "intake", "search", "intel", "mapper", "triage", "advisor"]


def test_optional_agent_failure_degrades(monkeypatch):
    def flaky(model, system, user, schema, **kw):
        if schema is AdvisorResult:
            raise RuntimeError("boom")
        return fake_call_json(model, system, user, schema)

    monkeypatch.setattr(o, "call_json", flaky)
    monkeypatch.setattr(o, "search", lambda q: [])
    r = o.run_triage(SCENARIOS["s02"])
    assert r["triage"]["verdict"] == "escalate"
    assert r["advice"]["actions"] == []
    assert any("advisor failed" in e for e in r["errors"])


def test_canon_and_catalogue_names():
    from intel import canon
    from attack_ics import catalogue, load_ics
    assert canon("https://us-cert.cisa.gov/a/b/") == canon(
        "https://www.cisa.gov/a/b")
    names = {c["id"]: c["name"] for c in catalogue(load_ics())}
    assert names["T1692.001"] == "Unauthorized Message: Command Message"
    assert names["T1691.001"] == "Block Operational Technology Message: Command Message"


def test_trust_by_domain_and_case_insensitive_canon():
    from intel import canon, is_trusted
    assert is_trusted("https://nvd.nist.gov/vuln/detail/cve-1")
    assert is_trusted("https://sec.cloudapps.cisco.com/security/x")
    assert is_trusted("https://www.cisa.gov/a")
    assert not is_trusted("https://thehackerwire.com/x")
    assert not is_trusted("https://notcisa.gov/x")
    assert not is_trusted("https://cisa.gov.evil.example.com/x")
    assert canon("https://nvd.nist.gov/vuln/detail/CVE-1") == canon(
        "https://nvd.nist.gov/vuln/detail/cve-1")


def test_catalogue_has_clean_descriptions():
    from attack_ics import catalogue, load_ics
    cat = catalogue(load_ics())
    assert all(c["what"] for c in cat)
    assert not any("Citation" in c["what"] or "](" in c["what"] for c in cat)
    assert max(len(c["what"]) for c in cat) <= 220


def test_inconsistent_triage_gets_one_review(monkeypatch):
    calls = {"n": 0}

    def inconsistent_then_fixed(model, system, user, schema, **kw):
        if schema is TriageResult:
            calls["n"] += 1
            pr = "P1" if calls["n"] == 1 else "P3"
            return TriageResult(verdict="investigate", priority=pr,
                                confidence=0.7, process_impact="i",
                                reasoning="r",
                                evidence=["alert.title: x",
                                          "alert.raw: invented"]), U()
        return fake_call_json(model, system, user, schema)

    monkeypatch.setattr(o, "call_json", inconsistent_then_fixed)
    monkeypatch.setattr(o, "search", lambda q: [])
    r = o.run_triage(SCENARIOS["s02"])
    assert calls["n"] == 2
    assert r["triage"]["priority"] == "P3"
    assert [x["step"] for x in r["trace"]].count("triage_review") == 1
    assert r["evidence_dropped"] == 1
    assert r["triage"]["evidence"] == ["alert.title: x"]
    assert any("re-checked" in n for n in r["notes"])


def test_injection_flag_is_set_by_code(monkeypatch):
    from scenarios_heldout import SCENARIOS as H1
    monkeypatch.setattr(o, "call_json", fake_call_json)
    monkeypatch.setattr(o, "search", lambda q: [])
    r = o.run_triage(H1["h06"])
    assert r["security_flags"]["embedded_instructions"] is True
    r2 = o.run_triage(SCENARIOS["s01"])
    assert r2["security_flags"]["embedded_instructions"] is False


def test_advisor_skipped_when_run_budget_exceeded(monkeypatch):
    monkeypatch.setattr(o, "call_json", fake_call_json)
    monkeypatch.setattr(o, "search", lambda q: [])
    monkeypatch.setattr(o, "RUN_BUDGET_S", -1)
    r = o.run_triage(SCENARIOS["s02"])
    assert r["advice"]["actions"] == []
    assert "advisor" not in [x["step"] for x in r["trace"]]
    assert any("skipped" in n for n in r["notes"])

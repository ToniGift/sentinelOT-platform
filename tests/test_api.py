import time

import pytest
from fastapi.testclient import TestClient

import main
import store


def fake_run(alert, trace_sink=None):
    row = {"step": "intake", "model": "m", "seconds": 0.1, "status": "ok",
           "prompt_tokens": 1, "completion_tokens": 1}
    if trace_sink is not None:
        trace_sink.append(row)
    return {"alert": alert.model_dump(), "intake": {}, "intel": {
        "summary": "s", "items": [], "dropped_unverified": 0},
        "attack": {"techniques": [], "dropped_invalid": 0},
        "triage": {"verdict": "escalate", "priority": "P1",
                   "confidence": 0.9, "process_impact": "i",
                   "reasoning": "r", "evidence": ["e"]},
        "advice": {"summary": "s", "actions": []},
        "trace": [row], "errors": [], "total_seconds": 0.1,
        "sum_step_seconds": 0.1}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB", str(tmp_path / "t.sqlite"))
    monkeypatch.setattr(main, "run_triage", fake_run)
    monkeypatch.setenv("APP_ADMIN_TOKEN", "secret-token")
    main._ip_hits.clear()
    main._day.update(n=0)
    return TestClient(main.app)


def wait_done(c, job_id):
    for _ in range(50):
        j = c.get(f"/api/jobs/{job_id}").json()
        if j["status"] != "running":
            return j
        time.sleep(0.05)
    raise AssertionError("job did not finish")


def test_scenarios_and_static_page(client):
    s = client.get("/api/scenarios").json()
    assert len(s) == 32
    assert {x["group"] for x in s} == {"development", "held-out", "held-out-2"}
    assert "SentinelOT" in client.get("/").text


def test_demo_flow_and_saved_result(client):
    assert client.get("/api/saved/s01").status_code == 404
    jid = client.post("/api/demo/s01").json()["job_id"]
    j = wait_done(client, jid)
    assert j["status"] == "done" and j["result"]["triage"]["verdict"] == "escalate"
    assert client.get("/api/saved/s01").json()["triage"]["priority"] == "P1"
    assert client.post("/api/demo/nope").status_code == 404


def test_rate_limit(client, monkeypatch):
    monkeypatch.setattr(main, "PER_IP", 2)
    assert client.post("/api/demo/s01").status_code == 200
    assert client.post("/api/demo/s02").status_code == 200
    assert client.post("/api/demo/s03").status_code == 429


def test_free_form_needs_admin_token(client):
    body = main.DEV["s01"].model_dump()
    assert client.post("/api/triage", json=body).status_code == 401
    r = client.post("/api/triage", json=body,
                    headers={"x-admin-token": "wrong"})
    assert r.status_code == 401
    r = client.post("/api/triage", json=body,
                    headers={"x-admin-token": "secret-token"})
    assert r.status_code == 200

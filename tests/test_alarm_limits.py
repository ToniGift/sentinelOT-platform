import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture(scope="module")
def c():
    return TestClient(main.app)


def test_baseline_lists_tags_and_is_labelled_simulated(c):
    b = c.get("/api/alarmops/baseline").json()
    assert b["simulated"] is True
    assert b["baseline"]["faults_detected"] == b["baseline"]["faults_total"]
    assert b["baseline"]["false_alarm_count"] == 0
    t = b["tags"]["tank_level"]
    assert (t["low_low"], t["low"], t["high"], t["high_high"]) == (10, 20, 80, 90)
    assert sum(x["faults_total"] for x in b["tags"].values()) == \
        b["baseline"]["faults_total"] == b["dataset"]["faults"]


def test_widened_tank_limits_are_blocked(c):
    r = c.get("/api/alarmops/compare",
              params={"tag": "tank_level", "high": 88, "high_high": 95}).json()
    assert r["simulated"] is True and r["passed"] is False
    assert r["violations"]
    assert len(r["newly_missed"]) == 4
    assert {f["tag"] for f in r["newly_missed"]} == {"tank_level"}
    assert r["head"]["faults_detected"] == r["base"]["faults_detected"] - 4
    assert r["limits"]["low"] == 20          # left out, so unchanged


def test_tightened_tank_limits_pass(c):
    r = c.get("/api/alarmops/compare",
              params={"tag": "tank_level", "high": 75, "high_high": 88}).json()
    assert r["passed"] is True and r["newly_missed"] == []


def test_compare_rejects_bad_input(c):
    get = lambda **p: c.get("/api/alarmops/compare", params=p).status_code
    assert get(tag="tank_level", high=95, high_high=90) == 400
    assert get(tag="tank_level", high="abc") == 400
    assert get(tag="tank_level", high="inf") == 400
    assert get(tag="no_such_tag") == 404


def test_monitor(c):
    assert c.get("/api/alarmops/monitor",
                 params={"log": "healthy"}).json()["drift"] is False
    d = c.get("/api/alarmops/monitor", params={"log": "drift"}).json()
    assert d["drift"] is True and d["recent_per_hour"] > d["threshold"]
    assert c.get("/api/alarmops/monitor",
                 params={"log": "../x"}).status_code == 400


def test_routes_are_read_only(c):
    for path in ("baseline", "compare", "monitor"):
        assert c.post(f"/api/alarmops/{path}").status_code == 405

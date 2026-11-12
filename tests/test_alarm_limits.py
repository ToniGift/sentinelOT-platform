import csv
import json

import pytest
from fastapi.testclient import TestClient

import alarm_limits
import main


@pytest.fixture(scope="module")
def c():
    return TestClient(main.app)


def compare(c, **p):
    return c.get("/api/alarmops/compare", params=p)


def test_baseline_lists_tags_and_is_labelled_simulated(c):
    b = c.get("/api/alarmops/baseline").json()
    assert b["simulated"] is True and b["dataset"]["source"] == "plant"
    assert set(b["tags"]) == {"tank_level", "pump_pressure", "flow_rate",
                              "sealer_temperature", "conveyor_speed"}
    assert b["baseline"] == {"detection_rate": 1.0, "faults_detected": 35,
                             "faults_total": 35, "false_alarm_count": 0}
    assert all(t["faults_total"] == 7 for t in b["tags"].values())
    t = b["tags"]["tank_level"]
    assert (t["low_low"], t["low"], t["high"], t["high_high"]) == (10, 20, 80, 90)
    s = b["tags"]["sealer_temperature"]
    assert (s["low_low"], s["low"], s["high"], s["high_high"]) == (100, 120, 190, 205)
    assert s["assets"] == ["SENSOR-GW-1", "PLC-Line1"]
    assert b["tags"]["conveyor_speed"]["assets"][0] == "VFD-Conveyor-1"
    assert t["assets"] == ["TANK-Utility-1", "DCS-CTRL-01"]


def test_widened_tank_limits_are_blocked(c):
    r = compare(c, tag="tank_level", high=88, high_high=95).json()
    assert r["simulated"] is True and r["passed"] is False
    assert r["violations"]
    assert len(r["newly_missed"]) == 4
    assert {f["tag"] for f in r["newly_missed"]} == {"tank_level"}
    assert (r["head"]["faults_detected"], r["head"]["faults_total"]) == (31, 35)
    assert r["limits"]["low"] == 20          # left out, so unchanged


def test_tightened_tank_limits_pass(c):
    r = compare(c, tag="tank_level", high=75, high_high=88).json()
    assert r["passed"] is True and r["newly_missed"] == []


def test_widened_sealer_high_limit_is_blocked_by_the_gate(c):
    """The preset on the showcase page: sealer high 190 -> 250 (high-high 265)."""
    r = compare(c, tag="sealer_temperature", high=250, high_high=265).json()
    assert r["passed"] is False
    assert r["current"]["high"] == 190 and r["limits"]["high"] == 250
    missed = r["newly_missed"]
    assert len(missed) == 5
    assert {f["tag"] for f in missed} == {"sealer_temperature"}
    assert (r["head"]["faults_detected"], r["head"]["faults_total"]) == (30, 35)
    assert any("below the minimum" in v for v in r["violations"])
    assert r["assets"] == ["SENSOR-GW-1", "PLC-Line1"]
    # every missed fault is a high-side fault: the widened limit no longer sees it
    high = {f["fault_id"] for f in csv.DictReader(open("plant/data/faults.csv"))
            if f["tag"] == "sealer_temperature" and f["direction"] == "high"}
    assert {f["fault_id"] for f in missed} == high


def test_sealer_high_alone_cannot_pass_high_high(c):
    assert compare(c, tag="sealer_temperature", high=250).status_code == 400


def test_compare_rejects_bad_input(c):
    assert compare(c, tag="tank_level", high=95, high_high=90).status_code == 400
    assert compare(c, tag="tank_level", high="abc").status_code == 400
    assert compare(c, tag="tank_level", high="inf").status_code == 400
    assert compare(c, tag="no_such_tag").status_code == 404


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


def test_plant_keeps_the_alarmops_tags_and_data_unchanged():
    """plant/ adds tags; it must not alter the AlarmOps series or faults."""
    a = [r[:4] for r in csv.reader(open("alarmops/data/replay.csv"))]
    b = [r[:4] for r in csv.reader(open("plant/data/replay.csv"))]
    assert a == b
    fa = {r["fault_id"]: r for r in csv.DictReader(open("alarmops/data/faults.csv"))}
    fb = {r["fault_id"]: r for r in csv.DictReader(open("plant/data/faults.csv"))}
    assert len(fa) == 21 and all(fb[k] == v for k, v in fa.items())


def test_original_alarmops_files_still_replay(monkeypatch):
    monkeypatch.setenv("ALARM_LIMITS_ROOT", "alarmops")
    try:
        b = alarm_limits.baseline()
        assert b["dataset"] == {"samples": 6000, "faults": 21,
                                "source": "alarmops"}
    finally:
        monkeypatch.delenv("ALARM_LIMITS_ROOT")
        alarm_limits.plant()


def test_page_recorded_copy_matches_the_api(c):
    """The page embeds a saved baseline and preset result for use without the server."""
    page = open("static/sentinelot.html", encoding="utf-8").read()
    start = page.index("var LIM_RECORDED=") + len("var LIM_RECORDED=")
    saved = json.loads(page[start:page.index(";\n", start)])
    assert saved["baseline"] == c.get("/api/alarmops/baseline").json()
    assert saved["preset"] == compare(
        c, tag="sealer_temperature", high=250, high_high=265).json()

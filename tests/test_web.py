import json
import shutil
import threading
import urllib.error
import urllib.request

import pytest
from conftest import BASELINE_RULES, ROOT

from alarmops.explainer import render_explainer
from alarmops.scenarios import build_report, set_tank_limits_text
from alarmops.lab import Lab
from alarmops.web import make_handler
from http.server import ThreadingHTTPServer

BASE_TEXT = "tags:\n  tank_level:\n    high: 80\n    high_high: 90\n  other:\n    high: 1\n    high_high: 2\n"


def test_set_tank_limits_only_edits_first_tag():
    out = set_tank_limits_text(BASE_TEXT, 88, 95)
    assert "high: 88" in out and "high_high: 95" in out and "high: 1\n" in out


def test_set_tank_limits_missing_key():
    with pytest.raises(ValueError):
        set_tank_limits_text("tags: {}", 1, 2)


@pytest.fixture(scope="module")
def root(tmp_path_factory):
    # frozen baseline rules, not the live alarms.yaml (which changes with every limit change)
    root = tmp_path_factory.mktemp("root")
    shutil.copy(BASELINE_RULES, root / "alarms.yaml")
    shutil.copy(ROOT / "gate.yaml", root / "gate.yaml")
    shutil.copytree(ROOT / "data", root / "data")
    return root


@pytest.fixture(scope="module")
def report(root):
    return build_report(root)


def test_report_measures_the_three_changes(report):
    a, c = report["scenarios"]["a"], report["scenarios"]["c"]
    assert a["blocked"] and a["faults_detected"] < report["baseline"]["faults_detected"]
    assert not c["blocked"] and c["faults_detected"] == report["baseline"]["faults_detected"]
    assert len(a["newly_missed"]) == report["baseline"]["faults_detected"] - a["faults_detected"]


def test_page_uses_measured_numbers_and_says_simulation(report):
    html = render_explainer(report)
    a = report["scenarios"]["a"]
    assert "simulation" in html.lower()
    assert f"{a['faults_detected']} of {a['faults_total']}" in html
    assert "<script" not in html


@pytest.fixture()
def server(report, root):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(report, Lab(root)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def get(url, method="GET", data=None):
    req = urllib.request.Request(url, method=method, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


def test_endpoints(server, report):
    code, hdr, body = get(server + "/healthz")
    assert code == 200 and json.loads(body)["status"] == "ok"
    code, hdr, body = get(server + "/")
    assert code == 200 and b"AlarmOps" in body and hdr["X-Content-Type-Options"] == "nosniff"
    code, _, body = get(server + "/api/replay")
    data = json.loads(body)
    assert code == 200 and data["scenarios"]["a"]["blocked"] and "series" not in data
    assert get(server + "/nope")[0] == 404
    assert get(server + "/", "POST")[0] == 405
    assert get(server + "/", "HEAD")[0] == 200


def test_cloud_run_deploy_is_optional_manual_and_secret_free():
    import yaml
    from conftest import ROOT

    ci = yaml.safe_load((ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8"))
    job = ci["deploy_cloud_run"]
    assert job["allow_failure"] is True and "deploy_production" in job["needs"]
    assert all(r.get("when") == "manual" and "CI_DEFAULT_BRANCH" in r["if"] for r in job["rules"])
    script = (ROOT / "cloud" / "cloudrun_deploy.sh").read_text(encoding="utf-8")
    assert "GCP_PROJECT_ID" in script and "--allow-unauthenticated" in script
    assert "BEGIN PRIVATE KEY" not in script and "private_key" not in script


def lab_get(server, path):
    code, _, body = get(server + path)
    return code, json.loads(body)


def test_lab_compare_blocks_a_loosened_limit_and_passes_a_tightened_one(server, report):
    a = report["scenarios"]["a"]
    code, r = lab_get(server, f"/api/lab/compare?tank_high={a['high']}&tank_high_high={a['high_high']}")
    assert code == 200 and not r["passed"] and r["output"].splitlines()[4] == "GATE: FAIL"
    assert r["head"]["faults_detected"] == a["faults_detected"]      # same numbers as the report
    assert [s["status"] for s in r["stages"] if s["stage"] == "review"] == ["fail"]
    assert all(s["status"] == "skipped" for s in r["stages"] if s["stage"] in ("deploy_staging", "approve"))
    c = report["scenarios"]["c"]
    code, r = lab_get(server, f"/api/lab/compare?tank_high={c['high']}&tank_high_high={c['high_high']}")
    assert code == 200 and r["passed"]
    assert [s["status"] for s in r["stages"] if s["stage"] == "approve"] == ["manual"]


def test_lab_compare_defaults_to_current_limits(server):
    code, r = lab_get(server, "/api/lab/compare")
    assert code == 200 and r["passed"] and r["head"] == r["base"]


@pytest.mark.parametrize("qs", [
    "tank_high=abc", "tank_high=nan", "tank_high=inf", "tank_high=-5", "tank_high=1e9",
    "tank_high=10", "delay_samples=2.5", "delay_samples=0", "deadband=-1",
])
def test_lab_compare_rejects_bad_input(server, qs):
    code, r = lab_get(server, "/api/lab/compare?" + qs)
    assert code == 400 and "error" in r


def test_lab_baseline_and_monitor(server):
    assert "detection=" in lab_get(server, "/api/lab/baseline")[1]["output"]
    assert lab_get(server, "/api/lab/monitor?log=drift")[1]["drift"] is True
    assert lab_get(server, "/api/lab/monitor?log=healthy")[1]["drift"] is False
    assert lab_get(server, "/api/lab/monitor?log=../../etc/passwd")[0] == 400


def post(server, body):
    return get(server + "/api/lab/scan", "POST", body)


def test_lab_scan_finds_fake_key_and_never_echoes_it(server):
    fake = "AKIA" + "ABCDEFGHIJKLMNOP"
    code, _, body = post(server, json.dumps({"text": f"x=1\naws_access_key_id={fake}\n"}).encode())
    data = json.loads(body)
    assert code == 200 and data["blocked"] and data["findings"][0]["line"] == 2
    assert fake not in body.decode()
    code, _, body = post(server, json.dumps({"text": "region=eu-west-1"}).encode())
    assert code == 200 and not json.loads(body)["blocked"]


def test_lab_scan_limits(server):
    assert post(server, json.dumps({"text": "a" * 5000}).encode())[0] == 400
    assert post(server, b"not json")[0] == 400
    assert post(server, b"")[0] == 400
    # an oversized body is rejected before it is read; depending on timing the client sees the
    # 400 or the connection being reset, and both mean "rejected"
    try:
        assert post(server, b"x" * 50_000)[0] == 400
    except (ConnectionError, urllib.error.URLError):
        pass
    assert get(server + "/api/lab/scan", "POST", None)[0] == 400
    assert get(server + "/api/lab/compare", "POST", b"{}")[0] == 405
    assert get(server + "/api/lab/compare", "HEAD")[0] == 404


def test_page_is_interactive_but_csp_blocks_inline_script(server):
    code, hdr, body = get(server + "/")
    assert b'id="run-compare"' in body and b'src="/lab.js"' in body
    csp = hdr["Content-Security-Policy"]
    assert "script-src 'self'" in csp and "unsafe-inline" not in csp.split("script-src")[1].split(";")[0]
    code, hdr, js = get(server + "/lab.js")
    assert code == 200 and b"textContent" in js and b"innerHTML" not in js
    assert b"AKIAABCDEFGHIJKLMNOP" not in js           # the fake key is assembled at run time
    assert b"function showError" in js and b"Cannot run this" in js   # errors appear beside the buttons
    assert b"validity.badInput" in js                  # text in a number box is reported, not ignored


def test_static_explainer_has_no_lab(report):
    assert 'id="lab"' not in render_explainer(report)


def test_rejected_requests_with_a_body_still_get_their_response(server):
    """Regression: a 405 sent without reading the body could surface as a reset connection."""
    for _ in range(40):
        assert get(server + "/api/lab/compare", "POST", b'{"x": 1}')[0] == 405
        assert get(server + "/", "PUT", b"data")[0] == 405
        assert get(server + "/api/lab/scan", "POST", b"not json")[0] == 400


def test_monitor_screen_interactive_and_static(report, server):
    code, hdr, body = get(server + "/")
    page = body.decode()
    assert 'id="monitor"' in page and 'href="#monitor"' in page
    assert 'id="mon-run-healthy"' in page and 'id="mon-run-drift"' in page and 'id="mon-diag"' in page
    assert "NOT CHECKED" in page                       # nothing is claimed until the monitor is run
    static = render_explainer(report)
    assert 'id="monitor"' in static and "mon-run-" not in static
    m = report["monitor"]
    assert f"{m['drift']['recent_per_hour']:.2f} /h" in static and "DRIFT DETECTED" in static and "NORMAL" in static


def test_monitor_api_returns_the_numbers_the_screen_shows(server, report):
    for name in ("healthy", "drift"):
        code, r = lab_get(server, f"/api/lab/monitor?log={name}")
        m = report["monitor"][name]
        assert code == 200 and r["drift"] == m["drift"]
        assert round(r["recent_per_hour"], 2) == round(m["recent_per_hour"], 2)
        assert round(r["threshold"], 2) == round(m["threshold"], 2)
    assert b"mon-run-" in get(server + "/lab.js")[2]


def test_lab_shows_false_alarms_prominently(server):
    code, hdr, js = get(server + "/lab.js")
    assert b'ro-false' in js and b"false_alarm_count" in js
    page = get(server + "/")[2].decode()
    assert 'id="lab-readouts"' in page and "A false alarm is an alarm that sounds when no hidden fault" in page
    # a limit set far too tight is noticed as false alarms, not as lost detection
    code, r = lab_get(server, "/api/lab/compare?tank_high=56&tank_high_high=88&deadband=0&delay_samples=1")
    assert code == 200 and not r["passed"]
    assert r["head"]["false_alarm_count"] > r["base"]["false_alarm_count"] and r["head"]["faults_detected"] == r["base"]["faults_detected"]

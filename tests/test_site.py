"""The static showcase in site/, and how the page behaves with no API behind it.

WHAT THIS CHECKS. site/index.html is the file Render publishes. It must be an exact copy of
static/sentinelot.html, and on a plain static server (no platform server, so every /api/... path
is a 404 HTML page) the page must still work: attacks, firewall switches, Segmentation, What-if,
Limits and Show trace, with no errors in the console and no request to /api/ at all. This checks
the page's code against the demo's own behaviour, not against a real plant or a real host.

The browser tests need Playwright and an installed Microsoft Edge (or Chrome). Without them they
are SKIPPED, and pytest.ini turns on the summary that lists each skip with its reason.
"""
import json
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static" / "sentinelot.html"
SITE = ROOT / "site"


# ---------------------------------------------------------------- no browser needed

def test_site_index_is_an_exact_copy_of_the_showcase_page():
    """Fails if a page change was not followed by `python scripts/build_site.py`."""
    assert (SITE / "index.html").read_bytes() == STATIC.read_bytes(), \
        "site/index.html is out of date: run python scripts/build_site.py and commit it"


def test_site_holds_only_the_showcase_page_never_the_triage_interface():
    assert sorted(p.name for p in SITE.iterdir()) == ["index.html"]
    html = (SITE / "index.html").read_text(encoding="utf-8")
    assert "SentinelOT: OT security demo, simulated plant" in html
    triage = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    assert html != triage


def test_the_page_has_title_description_and_open_graph_tags_but_no_og_image():
    html = STATIC.read_text(encoding="utf-8")
    head = html[:html.index("</head>")]
    assert re.search(r"<title>[^<]+</title>", head)
    assert re.search(r'<meta name="description" content="[^"]{40,}"', head)
    for prop in ("og:title", "og:description", "og:type"):
        assert f'<meta property="{prop}"' in head, prop
    assert "og:image" not in html


def test_build_site_is_repeatable():
    import importlib.util
    spec = importlib.util.spec_from_file_location("build_site", ROOT / "scripts" / "build_site.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    before = (SITE / "index.html").read_bytes()
    mod.build()
    assert (SITE / "index.html").read_bytes() == before == STATIC.read_bytes()


def test_the_platform_server_marks_every_response_so_the_page_can_tell_it_is_there():
    from fastapi.testclient import TestClient
    import main
    c = TestClient(main.app)
    for path in ("/sentinelot.html", "/api/alarmops/baseline"):
        assert c.get(path).headers.get("X-SentinelOT-API") == "1", path
    assert c.head("/sentinelot.html").headers.get("X-SentinelOT-API") == "1"


# ---------------------------------------------------------------- in a browser

sync_api = pytest.importorskip(
    "playwright.sync_api",
    reason="Playwright is not installed: static-host tests NOT RUN "
           "(pip install -r requirements-dev.txt)")


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as pw:
        b, errors = None, []
        for channel in ("msedge", "chrome"):
            try:
                b = pw.chromium.launch(channel=channel)
                break
            except Exception as exc:                  # browser not installed
                errors.append(f"{channel}: {str(exc).splitlines()[0]}")
        if b is None:
            pytest.skip("No installed Edge or Chrome could be launched: static-host tests "
                        "NOT RUN (" + "; ".join(errors) + ")")
        yield b
        b.close()


@pytest.fixture(scope="module")
def static_host():
    """site/ served by `python -m http.server`: no API, so /api/... is a 404 HTML page."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen([sys.executable, "-m", "http.server", str(port),
                             "--bind", "127.0.0.1", "--directory", str(SITE)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
                break
            except OSError:
                time.sleep(0.1)
        else:
            pytest.fail("the static test server did not start")
        yield f"http://127.0.0.1:{port}/"
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def watch(page, origin):
    """Collect page errors, same-origin console errors and every request to /api/."""
    log = {"errors": [], "console": [], "api": []}
    page.on("pageerror", lambda e: log["errors"].append(str(e)))

    def on_console(m):
        if m.type == "error" and m.location.get("url", "").startswith(origin):
            log["console"].append(m.text)
    page.on("console", on_console)
    page.on("request", lambda r: log["api"].append(r.url) if "/api/" in r.url else None)
    return log


def open_static(browser, host, width=1280, height=900):
    page = browser.new_page(viewport={"width": width, "height": height})
    log = watch(page, host)
    page.goto(host, wait_until="domcontentloaded")
    page.wait_for_function("() => window.ProcessModel && window.__sentinelot")
    page.wait_for_function("() => document.querySelector('#lim-tag').options.length === 5")
    return page, log


def test_the_showcase_works_on_a_plain_static_server(browser, static_host):
    page, log = open_static(browser, static_host)

    # Limits: the recorded copy, labelled, with Check change off
    page.click("#tab-lim")
    assert page.is_disabled("#lim-check")
    out = page.text_content("#lim-out")
    assert "Recorded" in out
    assert "Check change needs the platform server, which isn’t running in this view" in out
    page.click("#lim-preset")
    page.wait_for_timeout(300)
    assert "Blocked" in page.text_content("#lim-out") and "(recorded)" in page.text_content("#lim-out")

    # attacks, and the analyst note is the pre-written one, labelled as such
    page.click("#tab-live")
    page.click('[data-atk="setpoint"]')
    page.wait_for_selector("#alarm.crit", timeout=20000)
    page.wait_for_timeout(600)
    assert "pre-written" in page.text_content("#ai-who")
    page.click("#an-ack")
    # firewall switches, and the Segmentation tab follows them
    page.click('#rules .swt[data-fw="FW-302"]')
    page.click("#tab-seg")
    page.wait_for_timeout(300)
    assert page.evaluate("() => window.__sentinelot.segv().reach.now") == 2
    page.click("#mode-flat")
    page.click("#zones-btn")
    # What-if
    page.click("#tab-sim")
    page.wait_for_timeout(500)
    page.click("#sim-preset")
    assert page.evaluate("() => window.__sentinelot.sim().proposed.sealer_temperature.high") == 250
    page.click("#tab-live")
    page.wait_for_timeout(300)

    assert log["errors"] == [], log["errors"]
    assert log["console"] == [], log["console"]
    assert log["api"] == [], log["api"]             # a static host is never asked for /api/...
    page.close()


def test_show_trace_works_on_a_phone_on_a_static_server(browser, static_host):
    page, log = open_static(browser, static_host, width=390, height=844)
    page.evaluate("() => document.querySelector('[data-atk=\"setpoint\"]')"
                  ".scrollIntoView({block: 'center'})")
    page.wait_for_timeout(600)
    page.click('[data-atk="setpoint"]')
    page.wait_for_selector("#alarm.crit", timeout=20000)
    page.evaluate("() => document.querySelector('#alarm').scrollIntoView({block: 'center'})")
    page.wait_for_timeout(900)
    assert page.evaluate("() => !document.querySelector('#showtrace').hidden")
    page.click("#showtrace")
    page.wait_for_timeout(1200)
    visible = page.evaluate("""() => { const s = document.querySelector('#stage').getBoundingClientRect();
        return Math.max(0, Math.min(innerHeight, s.bottom) - Math.max(0, s.top)) }""")
    assert visible > 300
    assert log["errors"] == [] and log["console"] == [] and log["api"] == []
    page.close()


# -- a host that answers /api/... with HTML, or with a server that goes missing --------------

def server_marked(route):
    """Answer the page's HEAD probe as if the platform server were there."""
    if route.request.method == "HEAD":
        route.fulfill(status=200, headers={"X-SentinelOT-API": "1"}, body="")
    else:
        route.continue_()


HTML_404 = "<!doctype html><html><body><h1>Error response</h1><p>404 Not Found</p></body></html>"


def recorded_baseline():
    html = STATIC.read_text(encoding="utf-8")
    start = html.index("var LIM_RECORDED=") + len("var LIM_RECORDED=")
    return json.loads(html[start:html.index(";\n", start)])["baseline"]


@pytest.mark.parametrize("reply", [
    dict(status=404, content_type="text/html", body=HTML_404),            # a 404 page
    dict(status=200, content_type="text/html", body=HTML_404),            # a fallback page, 200
    dict(status=200, content_type="application/json", body="{not json"),  # a JSON parse failure
    dict(status=500, content_type="text/plain", body="boom"),             # any non-OK, no JSON
], ids=["404-html", "200-html", "bad-json", "500-text"])
def test_any_bad_baseline_answer_means_the_server_is_missing(browser, static_host, reply):
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    log = watch(page, static_host)
    page.route(static_host, server_marked)
    page.route("**/api/alarmops/baseline", lambda r: r.fulfill(**reply))
    page.goto(static_host, wait_until="domcontentloaded")
    page.wait_for_function("() => document.querySelector('#lim-tag').options.length === 5")
    page.click("#tab-lim")
    assert page.is_disabled("#lim-check")
    assert "Recorded" in page.text_content("#lim-out")
    assert log["errors"] == []
    page.close()


@pytest.mark.parametrize("reply", [
    dict(status=404, content_type="text/html", body=HTML_404),
    dict(status=200, content_type="text/html", body=HTML_404),
    dict(status=200, content_type="application/json", body="{not json"),
], ids=["404-html", "200-html", "bad-json"])
def test_a_server_that_goes_missing_after_the_baseline_puts_the_tab_back_to_recorded(
        browser, static_host, reply):
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    log = watch(page, static_host)
    page.route(static_host, server_marked)
    page.route("**/api/alarmops/baseline",
               lambda r: r.fulfill(status=200, content_type="application/json",
                                   body=json.dumps(recorded_baseline())))
    page.route("**/api/alarmops/compare**", lambda r: r.fulfill(**reply))
    page.goto(static_host, wait_until="domcontentloaded")
    page.wait_for_function("() => document.querySelector('#lim-tag').options.length === 5")
    page.click("#tab-lim")
    assert page.is_enabled("#lim-check")                    # the server looked present
    assert "Current limits" in page.text_content("#lim-out")
    page.click("#lim-preset")                               # asks the server, which is missing
    page.wait_for_function("() => document.querySelector('#lim-out').textContent.includes('Recorded')")
    assert page.is_disabled("#lim-check")                  # and it stays off, not only while waiting
    assert log["errors"] == []
    page.close()


def test_a_real_validation_answer_from_the_server_is_not_mistaken_for_a_missing_server(
        browser, static_host):
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.route(static_host, server_marked)
    page.route("**/api/alarmops/baseline",
               lambda r: r.fulfill(status=200, content_type="application/json",
                                   body=json.dumps(recorded_baseline())))
    page.route("**/api/alarmops/compare**",
               lambda r: r.fulfill(status=422, content_type="application/json",
                                   body=json.dumps({"detail": "high must stay below high high"})))
    page.goto(static_host, wait_until="domcontentloaded")
    page.wait_for_function("() => document.querySelector('#lim-tag').options.length === 5")
    page.click("#tab-lim")
    page.click("#lim-check")
    page.wait_for_function("() => document.querySelector('#lim-out').textContent.includes('Not checked')")
    assert page.is_enabled("#lim-check")                    # still live: the server answered
    page.close()

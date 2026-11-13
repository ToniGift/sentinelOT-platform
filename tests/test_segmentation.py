"""The firewall rule editor: zones, conduits, flows and canPass().

WHAT THIS CHECKS. These tests check the page's code against the model written down in the
proposal: given these zones, these conduits and these flows, canPass() must answer this way.
They do NOT check the model against a real plant. The zones, the four firewalls, the flows and
the rules are invented for the demo, and the page says so wherever they appear. A test passing
here means the code agrees with the demo's own rules, nothing more.

The expected answers come from `expected_stop()` below, a small reimplementation written from
the table in the proposal rather than translated from the JavaScript, so the two are independent
and an identical mistake in both is unlikely.

They run the page's JavaScript in an installed Microsoft Edge (or Chrome) through Playwright.
Without one every test here is SKIPPED, and pytest.ini turns on the summary that says so.
"""
import itertools
from pathlib import Path

import pytest

sync_api = pytest.importorskip(
    "playwright.sync_api",
    reason="Playwright is not installed: segmentation tests NOT RUN "
           "(pip install -r requirements-dev.txt)")

PAGE = (Path(__file__).resolve().parents[1] / "static" / "sentinelot.html").as_uri()
FIREWALLS = ["FW-301", "FW-302", "FW-303", "FW-304"]

# ---------------------------------------------------------------------------
# The model, written out again from the proposal's table.
#
# Zones, lowest first. A path crosses the firewalls that sit between its two ends.
ZONES = ["L0", "L1", "L2", "L3", "L3.5", "L4", "L5"]
# the firewall on the conduit between ZONES[n] and ZONES[n+1], or None
ON_CONDUIT = [None, "FW-304", None, "FW-303", "FW-302", "FW-301"]
# the ports each switch's rule covers; None means every port
RULE_PORTS = {"FW-301": None, "FW-302": None, "FW-303": None, "FW-304": {502, 20000}}

# every path the page can draw: (name, from zone, to zone, port, approved)
PATHS = [
    # the three live attacks, all from the enterprise level down to the line 1 controller
    ("attack:setpoint", "L4", "L1", 502, False),
    ("attack:robot", "L4", "L1", 502, False),
    ("attack:scan", "L4", "L1", 502, False),
    # the eight recorded alerts
    ("rec:1 office PC writes a coil", "L4", "L1", 502, False),
    ("rec:2 PLC program download", "L3", "L1", 502, True),
    ("rec:3 setpoint out of range", "L2", "L1", 502, True),
    ("rec:4 VPN pool to the HMI", "L5", "L2", 3389, False),
    ("rec:5 unit ID and port sweep", "L4", "L1", 502, False),
    ("rec:6 DNP3 from an unknown outstation", "L1", "L2", 20000, False),
    ("rec:7 failed OPC UA logins", "L4", "L2", 4840, False),
    ("rec:8 workstation reads registers", "L3", "L1", 502, True),
    # normal polling, which must keep running whatever the switches say
    ("poll:HMI-Line1 to PLC-101", "L2", "L1", 502, True),
    ("poll:HIST-01 to PLC-101", "L3", "L1", 502, True),
]
APPROVED_PATHS = [p[0] for p in PATHS if p[4]]


def expected_stop(frm, to, port, approved, denied):
    """Where this path stops, or None if it gets through. Written from the proposal's table."""
    if approved:
        return None                      # a fixed approved rule; no switch touches it
    i, j = ZONES.index(frm), ZONES.index(to)
    step = 1 if j > i else -1
    for k in range(i, j, step):
        fw = ON_CONDUIT[min(k, k + step)]
        if fw is None or fw not in denied:
            continue
        ports = RULE_PORTS[fw]
        if ports is None or port in ports:
            return fw
    return None


COMBOS = [set(c) for n in range(5) for c in itertools.combinations(FIREWALLS, n)]
CASES = [(p, d) for p in PATHS for d in COMBOS]


def case_id(path, denied):
    return path[0] + " | deny " + (",".join(sorted(denied)) if denied else "nothing")


# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def page():
    with sync_api.sync_playwright() as pw:
        b, errors = None, []
        for channel in ("msedge", "chrome"):
            try:
                b = pw.chromium.launch(channel=channel)
                break
            except Exception as exc:
                errors.append(f"{channel}: {str(exc).splitlines()[0]}")
        if b is None:
            pytest.skip("No installed Edge or Chrome could be launched: segmentation "
                        "tests NOT RUN (" + "; ".join(errors) + ")")
        p = b.new_page()
        p.goto(PAGE, wait_until="domcontentloaded")
        p.wait_for_function("() => window.NetworkModel")
        yield p
        p.close()
        b.close()


def ask(page, path, denied):
    rules = {fw: ("deny" if fw in denied else "allow") for fw in FIREWALLS}
    return page.evaluate("([p, r]) => window.NetworkModel.canPass(p, r)",
                         [{"from": path[1], "to": path[2], "port": path[3],
                           "approved": path[4]}, rules])


@pytest.mark.parametrize("path,denied", CASES,
                         ids=[case_id(*c) for c in CASES])
def test_every_path_against_every_combination_of_switches(page, path, denied):
    """All 13 paths x 16 switch combinations (208 cases), against the independent table above."""
    got = ask(page, path, denied)
    want = expected_stop(path[1], path[2], path[3], path[4], denied)
    assert got["stoppedAt"] == want
    assert got["passed"] is (want is None)


# --------------------------------------------------- the rows worth stating outright
def test_the_live_attacks_are_stopped_by_any_one_of_302_303_or_304(page):
    for kind in ("setpoint", "robot", "scan"):
        path = next(p for p in PATHS if p[0] == "attack:" + kind)
        for fw in ("FW-302", "FW-303", "FW-304"):
            assert ask(page, path, {fw})["stoppedAt"] == fw
        assert ask(page, path, {"FW-301"})["passed"] is True   # above the source
        assert ask(page, path, set())["passed"] is True


def test_alert_4_is_stopped_by_any_one_of_301_302_or_303(page):
    path = next(p for p in PATHS if p[0].startswith("rec:4"))
    for fw in ("FW-301", "FW-302", "FW-303"):
        assert ask(page, path, {fw})["stoppedAt"] == fw
    assert ask(page, path, {"FW-304"})["passed"] is True


def test_alert_7_is_stopped_by_302_or_303_only(page):
    path = next(p for p in PATHS if p[0].startswith("rec:7"))
    assert ask(page, path, {"FW-302"})["stoppedAt"] == "FW-302"
    assert ask(page, path, {"FW-303"})["stoppedAt"] == "FW-303"
    assert ask(page, path, {"FW-301"})["passed"] is True
    assert ask(page, path, {"FW-304"})["passed"] is True


def test_alert_6_is_stopped_by_304_only(page):
    path = next(p for p in PATHS if p[0].startswith("rec:6"))
    assert ask(page, path, {"FW-304"})["stoppedAt"] == "FW-304"
    for fw in ("FW-301", "FW-302", "FW-303"):
        assert ask(page, path, {fw})["passed"] is True


@pytest.mark.parametrize("name", APPROVED_PATHS)
def test_approved_flows_are_never_stopped_by_any_combination(page, name):
    """Alerts 2, 3 and 8 and the normal polling come from approved hosts, so no switch touches them."""
    path = next(p for p in PATHS if p[0] == name)
    for denied in COMBOS:
        r = ask(page, path, denied)
        assert r["passed"] is True, (name, sorted(denied))
        assert r["stoppedAt"] is None


def test_all_deny_stops_every_non_approved_path(page):
    everything = set(FIREWALLS)
    for path in PATHS:
        r = ask(page, path, everything)
        assert r["passed"] is path[4], path[0]


def test_the_first_deny_on_the_route_is_the_one_that_stops_it(page):
    """With several set to DENY, the answer is the firewall nearest the source, not just any on the path."""
    path = next(p for p in PATHS if p[0] == "attack:setpoint")        # L4 down to L1
    assert ask(page, path, {"FW-302", "FW-303", "FW-304"})["stoppedAt"] == "FW-302"
    assert ask(page, path, {"FW-303", "FW-304"})["stoppedAt"] == "FW-303"
    assert ask(page, path, {"FW-304"})["stoppedAt"] == "FW-304"
    up = next(p for p in PATHS if p[0].startswith("rec:4"))           # L5 down to L2
    assert ask(page, up, {"FW-301", "FW-303"})["stoppedAt"] == "FW-301"


def test_a_stopped_path_says_how_far_it_got(page):
    path = next(p for p in PATHS if p[0] == "attack:setpoint")
    assert ask(page, path, {"FW-302"})["reached"] == "L4"             # never left the office
    assert ask(page, path, {"FW-303"})["reached"] == "L3.5"           # as far as the DMZ
    assert ask(page, path, {"FW-304"})["reached"] == "L2"             # as far as supervisory
    assert ask(page, path, set())["reached"] == "L1"


def test_the_unfiltered_conduits_are_in_the_model(page):
    """L2-L3 and L0-L1 have no firewall. The model names them rather than leaving them out."""
    conduits = page.evaluate("() => window.NetworkModel.CONDUITS")
    no_fw = [c["id"] for c in conduits if c["firewall"] is None]
    assert sorted(no_fw) == ["C-0-1", "C-2-3"]
    path = next(p for p in PATHS if p[0] == "attack:setpoint")
    assert ask(page, path, set())["unfiltered"] == ["C-2-3"]


def test_canPass_changes_neither_its_path_nor_its_rules(page):
    out = page.evaluate("""() => { const N = window.NetworkModel;
        const p = {from: 'L4', to: 'L1', port: 502, approved: false};
        const r = {'FW-303': 'deny'};
        const before = JSON.stringify([p, r]);
        N.canPass(p, r);
        return JSON.stringify([p, r]) === before }""")
    assert out is True


def test_every_switch_names_a_real_conduit_and_firewall(page):
    m = page.evaluate("""() => ({switches: window.NetworkModel.switches(),
                                conduits: window.NetworkModel.CONDUITS,
                                flows: window.NetworkModel.FLOWS})""")
    by_id = {c["id"]: c for c in m["conduits"]}
    assert [r["firewall"] for r in m["switches"]] == ["FW-301", "FW-302", "FW-303", "FW-304"]
    for r in m["switches"]:
        assert by_id[r["conduit"]]["firewall"] == r["firewall"]
        assert by_id[r["conduit"]]["rule"] == r["id"]
        assert r["approved"] is False
    # every flow carries the four fields the segmentation view will read
    for f in m["flows"]:
        assert set(("from", "to", "protocol", "port", "approved")) <= set(f)
    approved = [f for f in m["flows"] if f["approved"]]
    assert {f["from"] for f in approved} == {"HMI-Line1", "HIST-01", "ENG-WS-01", "RTU-Outstation-3"}

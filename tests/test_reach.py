"""The segmentation view's model: zoneNets, reachableFrom and hops.

WHAT THIS CHECKS. These tests check the page's code against the model written down in the
proposal: given these zones, these hosts, these conduits and these flows, reachableFrom() and
hops() must answer this way. They do NOT check the model against a real plant. The zones, the
addresses, the subnets, the VLAN numbers and the rules are invented for the demo, and the page
says so wherever they appear. A test passing here means the code agrees with the demo's own
rules, nothing more.

The expected answers come from the small reimplementation below, written from the tables in
the proposal rather than translated from the JavaScript, so the two are independent and an
identical mistake in both is unlikely.

They run the page's JavaScript in an installed Microsoft Edge (or Chrome) through Playwright.
Without one every test here is SKIPPED, and pytest.ini turns on the summary that says so.
"""
import itertools
from pathlib import Path

import pytest

sync_api = pytest.importorskip(
    "playwright.sync_api",
    reason="Playwright is not installed: reachability tests NOT RUN "
           "(pip install -r requirements-dev.txt)")

PAGE = (Path(__file__).resolve().parents[1] / "static" / "sentinelot.html").as_uri()
FIREWALLS = ["FW-301", "FW-302", "FW-303", "FW-304"]

# ---------------------------------------------------------------------------
# The model, written out again from the proposal's tables.
#
# Zones, lowest first; the firewall on each conduit; the ports each rule covers.
ZONES = ["L0", "L1", "L2", "L3", "L3.5", "L4", "L5"]
ON_CONDUIT = [None, "FW-304", None, "FW-303", "FW-302", "FW-301"]
CONDUIT_IDS = ["C-0-1", "C-1-2", "C-2-3", "C-3-3.5", "C-3.5-4", "C-4-5"]
RULE_PORTS = {"FW-301": None, "FW-302": None, "FW-303": None, "FW-304": {502, 20000}}

ZONE_OF_LEVEL = {"0": "L0", "1": "L1", "2": "L2", "3": "L3",
                 "3.5": "L3.5", "4": "L4", "5": "L5"}

# One demo subnet and VLAN per zone, from the third octet of the demo addresses.
NETS = {"L0": ("10.10.10.0/24", 10), "L1": ("10.10.20.0/24", 20),
        "L2": ("10.10.30.0/24", 30), "L3": ("10.10.40.0/24", 40),
        "L3.5": ("10.10.45.0/24", 45), "L4": ("10.10.50.0/24", 50),
        "L5": ("10.10.90.0/24", 90)}

# Every addressed host: name -> (level, address invented for a demo-only asset?).
# The field devices, the drawn internet and the firewalls have no address and are not here.
HOSTS = {
    "VPN-GW-01": ("5", True),
    "OFFICE-PC-14": ("4", False),
    "ERP-SRV-01": ("4", True),
    "JUMP-SRV-01": ("3.5", False),
    "PATCH-SRV-01": ("3.5", False),
    "HIST-DMZ-01": ("3.5", False),
    "ENG-WS-01": ("3", False),
    "HIST-01": ("3", False),
    "MES-SRV-01": ("3", True),
    "AD-OT-01": ("3", True),
    "HMI-Line1": ("2", False),
    "SCADA-SRV-01": ("2", False),
    "DCS-OPS-01": ("2", True),
    "DCS-SRV-01": ("2", True),
    "DCS-CTRL-01": ("1", True),
    "PLC-Line1": ("1", False),
    "PLC-Line2": ("1", False),
    "RTU-Outstation-3": ("1", False),
    "VFD-Conveyor-1": ("0", False),
    "ROBOT-Pick-1": ("0", True),
    "IO-Module-Line2": ("0", False),
    "SENSOR-GW-1": ("0", False),
}

# The approved flows: fixed rules no switch touches.
APPROVED = {
    ("HMI-Line1", "PLC-Line1", 502),
    ("HIST-01", "PLC-Line1", 502),
    ("HIST-01", "PLC-Line2", 502),
    ("ENG-WS-01", "PLC-Line1", 502),
    ("ENG-WS-01", "PLC-Line2", 502),
    ("RTU-Outstation-3", "SCADA-SRV-01", 20000),
}

PORTS = [502, 20000, 4840, 3389]
COMBOS = [frozenset(c) for n in range(5) for c in itertools.combinations(FIREWALLS, n)]


def expected_stop(frm, to, port, approved, denied):
    """Where this path stops, or None if it gets through. Written from the proposal's table."""
    if approved:
        return None
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


def expected_reachable(src, denied, mode, port):
    """The hosts src can reach, by name, sorted. Written from the tables above."""
    frm = ZONE_OF_LEVEL[HOSTS[src][0]]
    out = []
    for name, (level, _demo) in HOSTS.items():
        if name == src:
            continue
        if mode == "flat":
            out.append(name)
            continue
        approved = (src, name, port) in APPROVED
        if expected_stop(frm, ZONE_OF_LEVEL[level], port, approved, denied) is None:
            out.append(name)
    return sorted(out)


def expected_route(frm, to):
    """The conduit ids between two zones, nearest the source first."""
    i, j = ZONES.index(frm), ZONES.index(to)
    step = 1 if j > i else -1
    return [CONDUIT_IDS[min(k, k + step)] for k in range(i, j, step)]


# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def page():
    with sync_api.sync_playwright() as pw:
        b, errors = None, []
        for channel in ("msedge", "chrome"):
            try:
                b = pw.chromium.launch(channel=channel)
                break
            except Exception as exc:                  # browser not installed
                errors.append(f"{channel}: {str(exc).splitlines()[0]}")
        if b is None:
            pytest.skip("No installed Edge or Chrome could be launched: reachability "
                        "tests NOT RUN (" + "; ".join(errors) + ")")
        p = b.new_page()
        p.goto(PAGE, wait_until="domcontentloaded")
        p.wait_for_function("() => window.NetworkModel && window.NetworkModel.hosts().length")
        yield p
        b.close()


def reach(page, src, denied, mode, port):
    return page.evaluate(
        """([src, denied, mode, port]) => {
             const rules = {}; denied.forEach(f => rules[f] = 'deny');
             const r = window.NetworkModel.reachableFrom(src, rules, mode, port);
             return {count: r.count, total: r.total, reached: r.reached.slice().sort(),
                     blocked: r.blocked.map(b => b.stoppedAt)} }""",
        [src, sorted(denied), mode, port])


def test_the_registered_hosts_match_the_table(page):
    got = page.evaluate("""() => window.NetworkModel.hosts()
        .map(h => ({name: h.name, level: h.level, demo: !!h.demo}))""")
    assert {h["name"]: (h["level"], h["demo"]) for h in got} == HOSTS
    assert len(got) == 22


def test_zone_nets_match_the_table(page):
    got = page.evaluate(
        "() => window.NetworkModel.zoneNets(window.NetworkModel.hosts())")
    assert {z: (n["subnet"], n["vlan"]) for z, n in got.items()} == NETS
    # every host's address sits in its own zone's subnet
    hosts = page.evaluate("() => window.NetworkModel.hosts().map(h => [h.name, h.ip, h.level])")
    for name, ip, level in hosts:
        prefix = NETS[ZONE_OF_LEVEL[level]][0].rsplit(".", 1)[0]
        assert ip.startswith(prefix + "."), (name, ip, prefix)


@pytest.mark.parametrize("denied", COMBOS, ids=lambda c: "+".join(sorted(c)) or "none")
def test_office_pc_reach_matches_under_every_combination(page, denied):
    for mode in ("segmented", "flat"):
        got = reach(page, "OFFICE-PC-14", denied, mode, 502)
        want = expected_reachable("OFFICE-PC-14", denied, mode, 502)
        assert got["reached"] == want, (mode, sorted(denied))
        assert got["count"] == len(want) and got["total"] == 21


def test_every_host_as_found_and_under_all_deny(page):
    for src in HOSTS:
        for denied in (frozenset(), frozenset(FIREWALLS)):
            for port in (502, 20000):
                got = reach(page, src, denied, "segmented", port)
                assert got["reached"] == expected_reachable(src, denied, "segmented", port), \
                    (src, sorted(denied), port)


def test_the_counter_states_are_these_measured_numbers(page):
    """Flat and as-found reach everything, all-DENY leaves only the same-zone neighbour.
    The page's counter shows the same three figures, measured, which the page tests check."""
    assert len(expected_reachable("OFFICE-PC-14", frozenset(), "flat", 502)) == 21
    assert len(expected_reachable("OFFICE-PC-14", frozenset(), "segmented", 502)) == 21
    assert expected_reachable("OFFICE-PC-14", frozenset(FIREWALLS), "segmented", 502) == ["ERP-SRV-01"]
    got = reach(page, "OFFICE-PC-14", frozenset(FIREWALLS), "segmented", 502)
    assert got["reached"] == ["ERP-SRV-01"] and got["count"] == 1


def test_approved_flows_are_reached_under_all_deny(page):
    for src, dst, port in APPROVED:
        got = reach(page, src, frozenset(FIREWALLS), "segmented", port)
        assert dst in got["reached"], (src, dst, port)


def test_flat_mode_ignores_every_switch(page):
    everything = sorted(n for n in HOSTS if n != "OFFICE-PC-14")
    for denied in COMBOS:
        assert reach(page, "OFFICE-PC-14", denied, "flat", 502)["reached"] == everything


@pytest.mark.parametrize("denied", COMBOS, ids=lambda c: "+".join(sorted(c)) or "none")
def test_hops_agrees_with_canpass_and_lists_the_gaps(page, denied):
    pairs = [(a, b) for a in ZONES for b in ZONES if a != b]
    got = page.evaluate(
        """([pairs, denied, ports]) => {
             const NM = window.NetworkModel, rules = {};
             denied.forEach(f => rules[f] = 'deny');
             return pairs.map(([a, b]) => ports.map(port => {
               const h = NM.hops(a, b, port, false, rules);
               const c = NM.canPass({from: a, to: b, approved: false, port: port}, rules);
               return {stop: h.stoppedAt, cstop: c.stoppedAt, passed: h.passed,
                       order: h.hops.map(x => x.conduit),
                       verdicts: h.hops.map(x => x.verdict),
                       gaps: h.hops.filter(x => x.gap).map(x => x.conduit)} })) }""",
        [pairs, sorted(denied), PORTS])
    for (a, b), per_port in zip(pairs, got):
        for port, r in zip(PORTS, per_port):
            want = expected_stop(a, b, port, False, denied)
            assert r["stop"] == want == r["cstop"], (a, b, port, sorted(denied))
            assert r["passed"] == (want is None)
            assert r["order"] == expected_route(a, b), (a, b)
            assert set(r["gaps"]) <= {"C-0-1", "C-2-3"}
            if want is not None:                      # nothing past the first DENY is reached
                stop_i = r["verdicts"].index("deny")
                assert all(v == "unreached" for v in r["verdicts"][stop_i + 1:])


def test_an_approved_path_passes_every_firewall_in_hops(page):
    got = page.evaluate(
        """() => window.NetworkModel.hops('L3', 'L1', 502, true,
                 {'FW-301':'deny','FW-302':'deny','FW-303':'deny','FW-304':'deny'})""")
    assert got["passed"] and got["stoppedAt"] is None
    assert [h["verdict"] for h in got["hops"]] == ["gap", "approved"]


def test_the_dnp3_alert_s_upward_path_is_stopped_by_304_only(page):
    """Recorded alert 6: DNP3 from level 1 up to level 2. Only FW-304's rule covers 20000;
    RDP 3389 is outside that rule, so even a DENY on FW-304 does not stop it."""
    for denied, stop in [(frozenset(), None), (frozenset(["FW-304"]), "FW-304"),
                         (frozenset(["FW-301", "FW-302", "FW-303"]), None)]:
        got = page.evaluate(
            """(denied) => { const rules = {}; denied.forEach(f => rules[f] = 'deny');
                 return window.NetworkModel.hops('L1', 'L2', 20000, false, rules).stoppedAt }""",
            sorted(denied))
        assert got == stop == expected_stop("L1", "L2", 20000, False, denied)
    assert page.evaluate(
        """() => window.NetworkModel.hops('L1', 'L2', 3389, false,
                 {'FW-304': 'deny'}).stoppedAt""") is None


def test_reachable_from_and_hops_change_nothing(page):
    assert page.evaluate(
        """() => { const NM = window.NetworkModel;
             const rules = {'FW-302': 'deny'}, before = JSON.stringify(rules);
             const n = NM.hosts().length;
             NM.reachableFrom('OFFICE-PC-14', rules, 'segmented', 502);
             NM.reachableFrom('OFFICE-PC-14', rules, 'flat', 502);
             NM.hops('L4', 'L0', 502, false, rules);
             return JSON.stringify(rules) === before && NM.hosts().length === n }""")


def test_an_unknown_host_returns_null(page):
    assert page.evaluate(
        "() => window.NetworkModel.reachableFrom('NO-SUCH-HOST', {}, 'segmented', 502)") is None

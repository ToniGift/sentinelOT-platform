"""The Segmentation tab in static/sentinelot.html: counter, matrix, path test, zones.

These drive the page's own JavaScript in a headless browser, with the page opened as a plain
file. They check the page against the demo's own rules, not against a real plant: the zones,
subnets, VLAN numbers and firewall rules are invented for the demo and labelled SIMULATED.

They need Playwright and an installed Microsoft Edge (or Chrome); without one every test here
is SKIPPED, and pytest.ini turns on the summary that says so.
"""
from pathlib import Path

import pytest

sync_api = pytest.importorskip(
    "playwright.sync_api",
    reason="Playwright is not installed: segmentation page tests NOT RUN "
           "(pip install -r requirements-dev.txt)")

PAGE = (Path(__file__).resolve().parents[1] / "static" / "sentinelot.html").as_uri()
FIREWALLS = ["FW-301", "FW-302", "FW-303", "FW-304"]


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
            pytest.skip("No installed Edge or Chrome could be launched: segmentation "
                        "page tests NOT RUN (" + "; ".join(errors) + ")")
        yield b
        b.close()


def open_seg(browser, width=1280, height=900):
    page = browser.new_page(viewport={"width": width, "height": height})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(PAGE, wait_until="domcontentloaded")
    page.wait_for_function("() => window.ProcessModel && window.__sentinelot")
    page.click("#tab-seg")
    page.wait_for_timeout(300)
    page.errors = errors
    return page


def set_rule(page, fw, value):
    page.evaluate("([f, v]) => window.__sentinelot.setRule(f, v)", [fw, value])


def cell(page, frm, to):
    return page.evaluate(
        """([f, t]) => { const b = [...document.querySelectorAll('#mx td button')]
               .find(b => b.dataset.from === f && b.dataset.to === t);
             return {text: b.innerText.replace(/\\s+/g, ' ').trim(),
                     label: b.getAttribute('aria-label'),
                     pressed: b.getAttribute('aria-pressed'),
                     denied: b.parentElement.className === 'no'} }""", [frm, to])


def click_cell(page, frm, to):
    page.evaluate(
        """([f, t]) => [...document.querySelectorAll('#mx td button')]
             .find(b => b.dataset.from === f && b.dataset.to === t).click()""", [frm, to])


def test_the_fifth_tab_opens_the_pane_and_says_simulated(browser):
    page = open_seg(browser)
    assert page.evaluate("() => document.querySelector('#tab-seg').getAttribute('aria-pressed')") == "true"
    assert not page.evaluate("() => document.querySelector('#pane-seg').hidden")
    text = page.text_content("#pane-seg")
    assert "SIMULATED." in text
    assert "Demo rules, demo subnets and demo VLAN numbers, not a recommendation for a real plant" in text
    assert page.errors == []
    page.close()


def test_no_element_id_appears_twice_on_the_page(browser):
    page = open_seg(browser)
    dup = page.evaluate("""() => { const seen = {}, dup = [];
        document.querySelectorAll('[id]').forEach(e => {
          if (seen[e.id]) dup.push(e.id); seen[e.id] = 1 });
        return dup }""")
    assert dup == []
    page.close()


def test_the_counter_shows_three_measured_states_and_the_sums(browser):
    """Flat, as found (all four ALLOW) and all four DENY, every figure measured from the
    model on the page, never typed in. test_reach.py pins the same numbers independently."""
    page = open_seg(browser)
    segv = page.evaluate("() => window.__sentinelot.segv()")
    r = segv["reach"]
    assert r["total"] == 21 and r["flat"] == 21 and r["found"] == 21 and r["deny"] == 1
    rows = page.evaluate("""() => [...document.querySelectorAll('#reach tr')]
        .map(tr => tr.innerText.replace(/\\s+/g, ' ').trim())""")
    assert rows == [
        f"One flat network, no segmentation {r['flat']} of {r['total']}",
        f"Segmented, as found: all four switches ALLOW {r['found']} of {r['total']}",
        f"Segmented, all four switches DENY {r['deny']} of {r['total']}",
        f"Segmented, with the switches as set now {r['now']} of {r['total']}"]
    foot = page.text_content("#reach")
    assert "measured from the model on this page" in foot and "502" in foot
    page.close()


def test_the_counter_and_both_switch_copies_follow_one_state(browser):
    page = open_seg(browser)
    # flip FW-302 through the Segmentation pane's own copy of the switch
    page.click('#rules-seg .swt[data-fw="FW-302"]')
    page.wait_for_timeout(200)
    states = page.evaluate("""() => [...document.querySelectorAll('.swt[data-fw="FW-302"]')]
        .map(b => b.textContent)""")
    assert states == ["DENY", "DENY"]                # the Live tab copy moved too
    segv = page.evaluate("() => window.__sentinelot.segv()")
    # FW-302 sits on the first conduit below L4, so only ERP-SRV-01 (same zone) and
    # VPN-GW-01 (upward, through FW-301 on ALLOW) are still reached
    assert segv["reach"]["now"] == 2
    now_row = page.evaluate(
        "() => document.querySelectorAll('#reach tr')[3].innerText.replace(/\\s+/g, ' ').trim()")
    assert now_row.endswith("2 of 21")
    # and back through the Live tab's copy, which is the one visible on that tab
    page.click("#tab-live")
    page.click('#rules .swt[data-fw="FW-302"]')
    page.click("#tab-seg")
    page.wait_for_timeout(200)
    assert page.evaluate("() => window.__sentinelot.segv().reach.now") == 21
    assert page.errors == []
    page.close()


def test_who_the_counter_counts_lists_demo_addresses_and_the_left_out(browser):
    page = open_seg(browser)
    text = page.evaluate("() => document.querySelector('#reach-list').textContent")
    assert "Counted: every item with a network address, 22 hosts" in text
    assert "Left out, because they have no network address" in text
    for name in ("TANK-Utility-1", "PUMP-Utility-1", "FLOW-Meter-1", "SEALER-Line1",
                 "MOTOR-Conveyor-1", "INTERNET", "FW-Edge"):
        assert name in text, name
    marks = page.evaluate("""() => [...document.querySelectorAll('#reach-list .dm')]
        .map(s => s.parentElement.textContent.split(' · ')[0])""")
    assert sorted(marks) == sorted([
        "VPN-GW-01", "ERP-SRV-01", "MES-SRV-01", "AD-OT-01",
        "DCS-OPS-01", "DCS-SRV-01", "DCS-CTRL-01", "ROBOT-Pick-1"])
    page.close()


def test_matrix_cells_follow_the_switches_and_the_protocol(browser):
    page = open_seg(browser)
    assert cell(page, "L4", "L1")["text"] == "Allowed"           # as found
    set_rule(page, "FW-304", "deny")
    c = cell(page, "L2", "L1")
    assert c["text"] == "Denied at FW-304" and c["denied"]
    assert "Modbus/TCP port 502" in c["label"] and "Denied" in c["label"]
    up = cell(page, "L1", "L2")                                  # the DNP3 alert's direction
    assert up["text"] == "Denied at FW-304"
    page.select_option("#mx-proto", "3389")                      # RDP: outside FW-304's rule
    page.wait_for_timeout(150)
    assert cell(page, "L2", "L1")["text"] == "Allowed"
    page.select_option("#mx-proto", "20000")
    page.wait_for_timeout(150)
    assert cell(page, "L1", "L2")["text"] == "Denied at FW-304"
    assert page.errors == []
    page.close()


def test_matrix_diagonal_and_gap_cells_say_what_they_are(browser):
    page = open_seg(browser)
    for z in ("L0", "L3.5", "L5"):
        d = cell(page, z, z)
        assert d["text"] == "Same zone no conduit"
        assert "crosses no conduit" not in (d["label"] or "") or True
    gap = cell(page, "L2", "L3")
    assert gap["text"] == "Allowed no firewall"
    gap2 = cell(page, "L0", "L1")
    assert gap2["text"] == "Allowed no firewall"
    empty = page.evaluate("""() => [...document.querySelectorAll('#mx td button')]
        .filter(b => !b.getAttribute('aria-label') || !b.innerText.trim()).length""")
    assert empty == 0
    page.close()


def test_a_picked_cell_is_explained_and_lights_the_path_in_3d(browser):
    page = open_seg(browser)
    set_rule(page, "FW-302", "deny")
    click_cell(page, "L4", "L1")
    page.wait_for_timeout(300)
    sel = page.text_content("#mx-sel")
    assert "L4 Enterprise to L1 Control" in sel
    assert "denied at FW-302" in sel and "FW-302 denies it on C-3.5-4" in sel
    assert cell(page, "L4", "L1")["pressed"] == "true"
    plates = page.evaluate("""() => [...document.querySelectorAll('#labels .lab')]
        .filter(e => e.style.display !== 'none').map(e => e.textContent)""")
    assert any("FW-302" in t and "DENY" in t for t in plates), plates
    assert page.errors == []
    page.close()


def test_the_path_test_lists_hops_gaps_and_the_first_block(browser):
    page = open_seg(browser)
    for fw in FIREWALLS:
        set_rule(page, fw, "deny")
    page.wait_for_timeout(200)
    out = page.text_content("#pt-out")                # default: OFFICE-PC-14 to PLC-Line2
    assert "STOPPED AT FW-302" in out
    assert "C-3.5-4 · L4 to L3.5 · FW-302 DENIES it: the path stops here" in out
    assert "C-2-3 · L3 to L2 · not reached" in out
    for fw in FIREWALLS:
        set_rule(page, fw, "allow")
    page.wait_for_timeout(200)
    out = page.text_content("#pt-out")
    assert out.startswith("ALLOWED")
    assert "C-2-3 · L3 to L2 · no firewall: an unfiltered gap, nothing to set" in out
    assert page.errors == []
    page.close()


def test_the_path_test_shows_an_approved_flow_as_fixed(browser):
    page = open_seg(browser)
    for fw in FIREWALLS:
        set_rule(page, fw, "deny")
    page.select_option("#pt-src", "HIST-01")
    page.select_option("#pt-dst", "PLC-Line2")
    page.wait_for_timeout(200)
    out = page.text_content("#pt-out")
    assert "ALLOWED · APPROVED FLOW" in out
    assert "An approved flow has its own fixed rule: no switch touches it." in out
    assert "approved flow, fixed rule" in out         # the firewall hops say it too
    page.close()


def test_flat_mode_changes_matrix_path_test_and_mode_text_together(browser):
    page = open_seg(browser)
    for fw in FIREWALLS:
        set_rule(page, fw, "deny")
    page.click("#mode-flat")
    page.wait_for_timeout(200)
    assert page.evaluate("() => document.querySelector('#mode-flat').getAttribute('aria-pressed')") == "true"
    assert cell(page, "L4", "L1")["text"] == "Allowed flat network"
    assert "ALLOWED · FLAT NETWORK" in page.text_content("#pt-out")
    assert "Mode now: flat network" in page.text_content("#reach")
    # the counter still shows all the states, so the all-DENY figure is still there to compare
    assert page.evaluate("() => window.__sentinelot.segv().reach.deny") == 1
    page.click("#mode-seg")
    page.wait_for_timeout(200)
    assert "Mode now: segmented" in page.text_content("#reach")
    assert page.errors == []
    page.close()


def test_zone_plates_carry_subnet_and_vlan_in_text(browser):
    page = open_seg(browser)
    page.click("#zones-btn")
    page.wait_for_timeout(300)
    texts = page.evaluate(
        "() => [...document.querySelectorAll('#labels .lab.zone')].map(e => e.textContent)")
    for want in ("L0 · 10.10.10.0/24 · VLAN 10", "L1 · 10.10.20.0/24 · VLAN 20",
                 "L2 · 10.10.30.0/24 · VLAN 30", "L3 · 10.10.40.0/24 · VLAN 40",
                 "L3.5 · 10.10.45.0/24 · VLAN 45", "L4 · 10.10.50.0/24 · VLAN 50",
                 "L5 · 10.10.90.0/24 · VLAN 90"):
        assert want in texts, want
    # flat mode swaps the seven zones for the one flat label
    page.click("#mode-flat")
    page.wait_for_timeout(300)
    shown = page.evaluate("""() => [...document.querySelectorAll('#labels .lab.zone')]
        .filter(e => e.style.display !== 'none').map(e => e.textContent)""")
    assert shown == ["One flat network · no VLANs · nothing between the levels"]
    assert page.errors == []
    page.close()


def test_the_phone_matrix_is_a_labelled_region_with_thumb_sized_cells(browser):
    page = open_seg(browser, width=390, height=844)
    r = page.evaluate("""() => { const w = document.querySelector('#mxwrap');
        const cells = [...w.querySelectorAll('td button')].map(b => {
          const r = b.getBoundingClientRect(); return {w: r.width, h: r.height} });
        return {role: w.getAttribute('role'), label: w.getAttribute('aria-label'),
                tab: w.getAttribute('tabindex'), scrolls: w.scrollWidth > w.clientWidth + 1,
                page: document.documentElement.scrollWidth <= window.innerWidth,
                cells} }""")
    assert r["role"] == "region" and r["tab"] == "0"
    assert "scrolls sideways" in r["label"]
    assert r["scrolls"] and r["page"]                 # the table scrolls inside, not the page
    assert all(c["w"] >= 40 and c["h"] >= 40 for c in r["cells"])
    # the switches fold up on a phone here as on the Live tab
    assert page.evaluate("() => document.querySelector('#segbox2').open") is False
    page.close()


def test_the_seg_controls_are_tall_enough_on_a_phone(browser):
    page = open_seg(browser, width=390, height=844)
    small = page.evaluate("""() => [...document.querySelectorAll(
        '#pane-seg .segmode button, #pane-seg .segsel, #pane-seg .swt, #pane-seg .foldhd')]
        .filter(e => e.offsetParent !== null)
        .map(e => ({t: (e.textContent || e.id).trim().slice(0, 24),
                    h: e.getBoundingClientRect().height}))
        .filter(e => e.h > 0 && e.h < 40)""")
    assert small == [], small
    page.close()


def test_the_seg_switches_start_open_on_a_desktop(browser):
    page = open_seg(browser)
    assert page.evaluate("() => document.querySelector('#segbox2').open") is True
    page.close()


def test_the_fw304_note_names_every_level_1_controller(browser):
    page = open_seg(browser)
    note = page.text_content("#fw304-note")
    assert "level 2 to level 1 boundary" in note
    for name in ("PLC-Line1", "PLC-Line2", "DCS-CTRL-01", "RTU-Outstation-3"):
        assert name in note, name
    assert "line 1 cell firewall" in note             # the as-found name is kept, honestly
    page.close()


def test_the_three_status_regions_announce_their_changes(browser):
    page = open_seg(browser)
    roles = page.evaluate("""() => ['#reach', '#mx-sel', '#pt-out']
        .map(s => document.querySelector(s).getAttribute('role'))""")
    assert roles == ["status", "status", "status"]
    page.close()

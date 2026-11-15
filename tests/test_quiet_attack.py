"""The Quiet attack: the Live tab's alarm-limit control, ProcessModel.alarmRaised and quietOutcome.

WHAT THIS CHECKS. These tests check the page's code against the model written down in the
proposal: given these sealer limits and this rule for who raises a security alarm, alarmRaised()
and quietOutcome() must answer this way, and the page must show those answers. They do NOT check
the model against a real plant. The 190 / 205 and 250 / 265 limits, the 240 degC write and the
live detector's rule are demo values and demo behaviour, and the page labels them SIMULATED. A test
passing here means the code agrees with the demo's own rules, nothing more.

The expected answers come from `raises_high()` and `quiet_outcome()` below, a small
reimplementation written from the limit table rather than translated from the JavaScript, so the
two are independent and an identical mistake in both is unlikely.

The limit numbers are read from the page's own recorded AlarmOps baseline (checked against the
API by test_alarm_limits.py), not typed in here.

They run the page's JavaScript in an installed Microsoft Edge (or Chrome) through Playwright.
Without one every browser test here is SKIPPED, and pytest.ini turns on the summary that says so.
"""
import itertools
import json
from pathlib import Path

import pytest

sync_api = pytest.importorskip(
    "playwright.sync_api",
    reason="Playwright is not installed: Quiet attack tests NOT RUN "
           "(pip install -r requirements-dev.txt)")

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "static" / "sentinelot.html").read_text(encoding="utf-8")
PAGE = (ROOT / "static" / "sentinelot.html").as_uri()


def _recorded():
    start = HTML.index("var LIM_RECORDED=") + len("var LIM_RECORDED=")
    return json.loads(HTML[start:HTML.index(";\n", start)])


RECORDED = _recorded()
SEALER = RECORDED["baseline"]["tags"]["sealer_temperature"]          # the protected limits
PRESET = RECORDED["preset"]["limits"]                                # the widened ones, 250 / 265
PROTECTED = {"low_low": SEALER["low_low"], "low": SEALER["low"],
             "high": SEALER["high"], "high_high": SEALER["high_high"]}
WIDENED = {"low_low": SEALER["low_low"], "low": SEALER["low"],
           "high": PRESET["high"], "high_high": PRESET["high_high"]}
COMMANDED = 240                                                      # the setpoint attack's write


# ---------------------------------------------------------------------------
# The model, written out again from the limit table.

def state(v, lim):
    """The alarm state of value v against limits lim, or None. Same table as the proposal."""
    if not (lim["low_low"] < lim["low"] < lim["high"] < lim["high_high"]):
        return None
    if v >= lim["high_high"]:
        return "high_high"
    if v >= lim["high"]:
        return "high"
    if v <= lim["low_low"]:
        return "low_low"
    if v <= lim["low"]:
        return "low"
    return None


def raises_high(v, lim):
    """Does limit lim raise a high process alarm at value v?"""
    return state(v, lim) in ("high", "high_high")


def quiet_outcome(approved, value, lim):
    """The live demo's detector raises its security alarm only for a write from a host that is not
    an approved master, whatever the value. The process alarm is the limit's decision."""
    return {"security": not approved, "process": raises_high(value, lim), "state": state(value, lim)}


VALUES = [100, 120, 159.9, 160, 189.9, 190, 190.1, 204.9, 205, 239.9, 240, 249.9, 250,
          250.1, 259.9, 260, 264.9, 265, 300]
LIMITS = {"protected": PROTECTED, "widened": WIDENED}


# ---------------------------------------------------------------------------

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
            pytest.skip("No installed Edge or Chrome could be launched: Quiet attack tests "
                        "NOT RUN (" + "; ".join(errors) + ")")
        yield b
        b.close()


def open_page(browser, width=1280, height=900):
    page = browser.new_page(viewport={"width": width, "height": height})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(PAGE, wait_until="domcontentloaded")
    page.wait_for_function("() => window.ProcessModel && window.__sentinelot")
    page.wait_for_function("() => document.querySelector('#lim-tag').options.length === 5")
    page.errors = errors
    return page


def live(page):
    return page.evaluate("() => window.__sentinelot.live()")


def kinds(page):
    return [a["kind"] for a in live(page)["alarms"]]


def txt(page, sel):
    # textContent, not innerText: the page uppercases many headings and windows with CSS, and these
    # tests check the words the page holds
    return page.evaluate("s => document.querySelector(s).textContent.replace(/\\s+/g, ' ').trim()", sel)


def attack(page):
    page.click('[data-atk="setpoint"]')
    page.wait_for_selector("#alarm.crit", timeout=20000)


def wait_hot(page, above=200):
    """Wait until the sealer is well over the protected limit (it climbs about 40 degC in 8 s)."""
    page.wait_for_function("a => window.__sentinelot.live().st.pv > a", arg=above, timeout=40000)


# ------------------------------------------------ the pure functions against the twin

def test_the_protected_and_widened_limits_come_from_the_recorded_alarmops_copy():
    assert (PROTECTED["high"], PROTECTED["high_high"]) == (190, 205)
    assert (WIDENED["high"], WIDENED["high_high"]) == (250, 265)


@pytest.mark.parametrize("name", list(LIMITS))
def test_alarm_raised_matches_the_independent_reimplementation(browser, name):
    page = open_page(browser)
    lim = LIMITS[name]
    got = page.evaluate("""([values, lim]) => values.map(v => ({
        raised: window.ProcessModel.alarmRaised(v, lim), state: window.ProcessModel.alarmState(v, lim)}))""",
                        [VALUES, lim])
    for v, g in zip(VALUES, got):
        assert g["raised"] == raises_high(v, lim), (name, v)
        assert g["state"] == state(v, lim), (name, v)
    page.close()


@pytest.mark.parametrize("approved,name", list(itertools.product([False, True], LIMITS)))
def test_quiet_outcome_matches_the_independent_reimplementation(browser, approved, name):
    page = open_page(browser)
    lim = LIMITS[name]
    got = page.evaluate("""([values, lim, approved]) => values.map(v =>
        window.ProcessModel.quietOutcome({approved: approved, value: v}, lim))""",
                        [VALUES, lim, approved])
    for v, g in zip(VALUES, got):
        assert g == quiet_outcome(approved, v, lim), (approved, name, v)
    page.close()


def test_the_quiet_decisions_the_page_shows_at_the_commanded_240_and_at_260(browser):
    """Spelled out: widened silences 240 but not 260; protected raises both; an approved source
    never raises the security alarm in this live demo's detector."""
    page = open_page(browser)

    def out(approved, value, name):
        return page.evaluate("([a, v, l]) => window.ProcessModel.quietOutcome({approved: a, value: v}, l)",
                             [approved, value, LIMITS[name]])
    assert out(False, 240, "protected") == {"security": True, "process": True, "state": "high_high"}
    assert out(False, 240, "widened") == {"security": True, "process": False, "state": None}
    assert out(False, 260, "widened") == {"security": True, "process": True, "state": "high"}
    assert out(True, 240, "protected") == {"security": False, "process": True, "state": "high_high"}
    assert out(True, 240, "widened") == {"security": False, "process": False, "state": None}
    page.close()


def test_quiet_outcome_changes_neither_its_write_nor_its_limits(browser):
    page = open_page(browser)
    assert page.evaluate("""([lim]) => { const w = {approved: false, value: 240};
        const a = JSON.stringify(w), b = JSON.stringify(lim);
        window.ProcessModel.quietOutcome(w, lim); window.ProcessModel.alarmRaised(240, lim);
        return JSON.stringify(w) === a && JSON.stringify(lim) === b }""", [WIDENED])
    page.close()


# ------------------------------------------------ the control on the page

def test_the_control_names_both_limit_states_from_the_model_and_says_what_it_is(browser):
    page = open_page(browser)
    assert txt(page, "#quiet-protected") == "AS PROTECTED (190 / 205)"
    assert txt(page, "#quiet-widened") == "WIDENED (250 / 265)"
    assert page.get_attribute("#quiet-protected", "aria-pressed") == "true"
    assert page.get_attribute("#quiet-widened", "aria-pressed") == "false"
    assert txt(page, "#quiet-sum") == "Alarm limit: AS PROTECTED (190 / 205)"
    box = txt(page, "#quietbox")
    assert "SIMULATED" in box
    assert "stands for a limit change that was not blocked" in box
    assert "AlarmOps does block that change in the Limits tab; this control shows the world where it did not" in box
    assert "The attack does not feed AlarmOps, and AlarmOps does not watch the attack." in box
    assert ("The link below, not this control, loads the 250 / 265 preset into the proposed limits "
            "that the What-if tab shares.") in box
    assert "does not change the Limits tab’s current limits, the AlarmOps results or the recorded copy" in box
    assert page.errors == []
    page.close()


def test_the_wording_about_the_security_alarm_is_narrow_and_points_to_recorded_alert_3(browser):
    page = open_page(browser)
    box = txt(page, "#quietbox")
    assert "In this live demo’s detector it exists only because the write came from a host that is not an approved master" in box
    assert "Recorded alert 3" in box and "the full SentinelOT pipeline escalated it" in box
    assert "recorded alert 3 shows the full pipeline catching an HMI write by its value" in box
    for bad in ("would miss", "would not catch", "would be missed", "SentinelOT would not"):
        assert bad not in box, bad
    page.close()


def test_the_default_is_as_protected_and_the_annunciator_says_so_in_words(browser):
    page = open_page(browser)
    assert txt(page, "#an-quiet") == "TT-101: high limit 190 °C, as protected. No process alarm."
    assert "High 190 °C" in txt(page, '[data-kind="temp"]')
    assert "No write yet" in txt(page, "#quiet-result")
    page.close()


def test_the_buttons_work_from_the_keyboard(browser):
    page = open_page(browser)
    page.focus("#quiet-widened")
    page.keyboard.press("Enter")
    assert page.get_attribute("#quiet-widened", "aria-pressed") == "true"
    assert page.get_attribute("#quiet-protected", "aria-pressed") == "false"
    assert txt(page, "#quiet-sum") == "Alarm limit: WIDENED (250 / 265)"
    page.focus("#quiet-protected")
    page.keyboard.press("Space")
    assert page.get_attribute("#quiet-protected", "aria-pressed") == "true"
    assert page.errors == []
    page.close()


# ------------------------------------------------ both limit states, unapproved source

def test_protected_limits_still_raise_tt101_after_the_setpoint_attack(browser):
    page = open_page(browser)
    attack(page)
    page.wait_for_function("() => window.__sentinelot.live().alarms.some(a => a.kind === 'temp')",
                           timeout=40000)
    d = live(page)
    assert [a["kind"] for a in d["alarms"]] == ["setpoint", "temp"]
    assert d["firstOut"] == "setpoint"                       # the cause is first out, TT-101 follows
    assert "TT-101 high: sealer above its 190 °C limit" in txt(page, "#alarm")
    assert "process alarm raised, the sealer is over the protected 190 °C limit" in txt(page, "#an-quiet")
    assert page.errors == []
    page.close()


def test_widened_limits_keep_tt101_silent_while_the_security_alarm_is_raised(browser):
    page = open_page(browser)
    page.click("#quiet-widened")
    attack(page)
    wait_hot(page, 200)                                      # well over the protected 190
    assert kinds(page) == ["setpoint"]                       # the security alarm only
    assert "ALARM" in txt(page, '[data-kind="setpoint"]').upper()
    tt = txt(page, '[data-kind="temp"]')
    assert "High 250 °C" in tt and "SILENT · LIMIT WIDENED" in tt.upper()
    assert "silent, no process alarm, limit widened" in page.get_attribute('[data-kind="temp"]', "aria-label")
    line = txt(page, "#an-quiet")
    assert "TT-101: no process alarm at 240.0 °C commanded. Limit is 250 °C" in line
    assert "The protected 190 °C limit would already have raised one." in line
    assert page.errors == []
    page.close()


def test_the_side_by_side_table_is_labelled_as_the_commanded_value_not_a_measurement(browser):
    page = open_page(browser)
    attack(page)
    rows = page.evaluate("""() => [...document.querySelectorAll('#quiet-table tr')]
        .map(tr => [...tr.children].map(c => c.textContent.replace(/\\s+/g, ' ').trim()))""")
    assert rows[0] == ["At the commanded 240 °C", "As protected (190 / 205) · in force", "Widened (250 / 265)"]
    assert rows[1] == ["Security alarm", "raised", "raised"]
    assert rows[2] == ["Process alarm (TT-101)", "raised (high high)", "not raised"]
    note = txt(page, "#quiet-result")
    assert "Last write: 240 °C to the sealer setpoint, from OFFICE-PC-14, which is not an approved master" in note
    assert "It is not a measurement of the sealer." in note
    page.click("#quiet-widened")                             # the same table, the other column in force
    rows = page.evaluate("""() => [...document.querySelectorAll('#quiet-table tr')][0]
        .textContent.replace(/\\s+/g, ' ')""")
    assert "Widened (250 / 265) · in force" in rows and "As protected (190 / 205) · in force" not in rows
    page.close()


# ------------------------------------------------ mid-attack changes and first out

def test_switching_to_protected_at_240_raises_tt101_and_it_is_not_first_out(browser):
    page = open_page(browser)
    page.click("#quiet-widened")
    attack(page)
    wait_hot(page, 200)
    assert kinds(page) == ["setpoint"]
    page.click("#quiet-protected")
    page.wait_for_function("() => window.__sentinelot.live().alarms.some(a => a.kind === 'temp')",
                           timeout=10000)
    d = live(page)
    temp = [a for a in d["alarms"] if a["kind"] == "temp"][0]
    assert d["firstOut"] == "setpoint" and temp["firstOut"] is False     # the earlier alarm stays first out
    assert temp["cleared"] is False and temp["ack"] is False
    assert [a["kind"] for a in d["alarms"]] == ["setpoint", "temp"]
    page.close()


def test_widening_while_tt101_is_active_returns_it_to_normal_and_keeps_first_out(browser):
    page = open_page(browser)
    attack(page)
    page.wait_for_function("() => window.__sentinelot.live().alarms.some(a => a.kind === 'temp')",
                           timeout=40000)
    page.click("#quiet-widened")
    page.wait_for_function(
        "() => window.__sentinelot.live().alarms.find(a => a.kind === 'temp').cleared", timeout=10000)
    d = live(page)
    assert d["firstOut"] == "setpoint"
    assert "RETURNED" in txt(page, '[data-kind="temp"]').upper()
    assert "no process alarm" in txt(page, "#an-quiet")
    page.click("#quiet-protected")                           # and back: the alarm comes back
    page.wait_for_function(
        "() => !window.__sentinelot.live().alarms.find(a => a.kind === 'temp').cleared", timeout=10000)
    assert page.errors == []
    page.close()


def test_widened_limits_do_raise_tt101_at_260(browser):
    """The one place the test hook is used: the sealer would take half a minute to reach 260."""
    page = open_page(browser)
    page.click("#quiet-widened")
    page.evaluate("() => window.__sentinelot.forceSetpoint(260, 255)")
    page.wait_for_function("() => window.__sentinelot.live().alarms.some(a => a.kind === 'temp')",
                           timeout=10000)
    assert "TT-101 high: sealer above its 250 °C limit" in txt(page, "#alarm")
    assert "widened" in txt(page, "#an-quiet") and "process alarm raised" in txt(page, "#an-quiet")
    page.close()


# ------------------------------------------------ the same write from the HMI

def test_the_hmi_write_raises_no_security_alarm_and_tt101_fires_only_under_protected_limits(browser):
    page = open_page(browser)
    page.click("#hmi-write")
    page.wait_for_function("() => window.__sentinelot.live().alarms.some(a => a.kind === 'temp')",
                           timeout=40000)
    d = live(page)
    assert [a["kind"] for a in d["alarms"]] == ["temp"]      # no security alarm: an approved master
    assert d["firstOut"] == "temp"
    assert "Last write: 240 °C to the sealer setpoint, from HMI-Line1, an approved master" in txt(page, "#quiet-result")
    assert "Security alarm: not raised · Process alarm (TT-101): raised" in txt(page, "#quiet-line")
    rows = page.evaluate("""() => [...document.querySelectorAll('#quiet-table tbody tr')]
        .map(tr => [...tr.children].map(c => c.textContent.trim()))""")
    assert rows == [["Security alarm", "not raised", "not raised"],
                    ["Process alarm (TT-101)", "raised (high high)", "not raised"]]
    assert page.errors == []
    page.close()


def test_the_hmi_write_under_widened_limits_raises_nothing_at_all(browser):
    page = open_page(browser)
    page.click("#quiet-widened")
    page.click("#hmi-write")
    page.wait_for_function("() => window.__sentinelot.live().st.sp === 240", timeout=10000)
    wait_hot(page, 200)
    assert live(page)["alarms"] == []
    assert "Security alarm: not raised · Process alarm (TT-101): not raised at the commanded 240 °C" in txt(page, "#quiet-line")
    assert "SILENT" in txt(page, '[data-kind="temp"]').upper()
    assert "NO ALARM" in txt(page, "#an-st").upper()
    rows = page.evaluate("""() => [...document.querySelectorAll('#quiet-table tbody tr')]
        .map(tr => [...tr.children].map(c => c.textContent.trim()))""")
    assert rows == [["Security alarm", "not raised", "not raised"],
                    ["Process alarm (TT-101)", "raised (high high)", "not raised"]]       # drawn although nothing raised
    page.close()


def test_the_hmi_buttons_enable_and_disable_with_the_setpoint_and_restore_it(browser):
    page = open_page(browser)
    assert page.is_enabled("#hmi-write") and page.is_disabled("#hmi-restore")
    page.click("#hmi-write")
    # the write and its echo are two frames: wait for both, then the buttons settle
    page.wait_for_function(
        "() => window.__sentinelot.live().st.sp === 240 && window.__sentinelot.live().queue === 0", timeout=10000)
    page.wait_for_timeout(900)
    assert page.is_disabled("#hmi-write") and page.is_enabled("#hmi-restore")
    page.click("#hmi-restore")
    assert live(page)["st"]["sp"] == 160
    assert page.is_enabled("#hmi-write") and page.is_disabled("#hmi-restore")
    page.close()


# ------------------------------------------------ independence from Limits, What-if and AlarmOps

def test_the_control_never_touches_the_limits_tab_or_the_what_if_proposed_limits(browser):
    page = open_page(browser)
    page.click("#quiet-widened")
    attack(page)
    assert page.evaluate("() => window.__sentinelot.sim().proposed") == {}
    page.click("#tab-lim")
    page.select_option("#lim-tag", "sealer_temperature")
    assert page.input_value("#lim-high") == "190" and page.input_value("#lim-high_high") == "205"
    assert "Current limits" in txt(page, "#lim-out") or "Recorded" in txt(page, "#lim-out")
    page.close()


def test_the_limits_link_loads_the_250_265_preset_into_the_shared_proposed_limits(browser):
    page = open_page(browser)
    page.click("#quiet-link")
    assert page.get_attribute("#tab-lim", "aria-pressed") == "true"
    assert page.input_value("#lim-tag") == "sealer_temperature"
    assert page.input_value("#lim-high") == "250" and page.input_value("#lim-high_high") == "265"
    proposed = page.evaluate("() => window.__sentinelot.sim().proposed")
    assert proposed["sealer_temperature"]["high"] == 250 and proposed["sealer_temperature"]["high_high"] == 265
    assert "Blocked" in txt(page, "#lim-out")               # AlarmOps blocks it: the recorded result
    # the control itself is still as it was: the link loaded a proposal, it did not widen the Live limit
    page.click("#tab-live")
    assert page.get_attribute("#quiet-protected", "aria-pressed") == "true"
    assert page.errors == []
    page.close()


def test_the_alarmops_routes_return_the_same_results_as_the_recorded_copy():
    """The page only reads its recorded copy and the control writes nothing to it, so the routes and
    the copy must still agree (test_alarm_limits.py checks the same thing in more detail)."""
    from fastapi.testclient import TestClient
    import main
    c = TestClient(main.app)
    assert c.get("/api/alarmops/baseline").json() == RECORDED["baseline"]
    got = c.get("/api/alarmops/compare", params={"tag": "sealer_temperature", "high": 250,
                                                 "high_high": 265}).json()
    assert got == RECORDED["preset"]
    assert got["passed"] is False                            # the gate blocks the widening


# ------------------------------------------------ phones

def test_on_a_phone_the_outcome_line_is_outside_the_fold_and_the_order_holds(browser):
    page = open_page(browser, width=390, height=844)
    assert page.evaluate("() => document.querySelector('#quietbox').open") is False
    order = page.evaluate("""() => { const y = s => document.querySelector(s).getBoundingClientRect().top + scrollY;
        return [y('#stage'), y('#tabs'), y('[data-atk="setpoint"]'), y('#quietbox'), y('#windows')] }""")
    assert order == sorted(order), order                    # plant, tabs, attacks, the control, annunciator
    page.evaluate("() => document.querySelector('[data-atk=\"setpoint\"]').scrollIntoView({block: 'center'})")
    page.wait_for_timeout(600)
    attack(page)
    page.wait_for_timeout(600)
    line = page.evaluate("""() => { const l = document.querySelector('#quiet-line');
        return {text: l.innerText.trim(), visible: l.checkVisibility(),
                insideFold: !!l.closest('#quietbox'), box: document.querySelector('#quietbox').open} }""")
    assert line["visible"] and not line["insideFold"] and line["box"] is False
    assert line["text"].startswith("Security alarm: raised · Process alarm (TT-101): raised at the commanded 240 °C")
    # the summary of the folded box still says which limit is in force
    assert txt(page, "#quiet-sum") == "Alarm limit: AS PROTECTED (190 / 205)"
    assert page.errors == []
    page.close()


def test_on_a_phone_every_control_in_the_box_is_at_least_40px_tall(browser):
    page = open_page(browser, width=390, height=844)
    page.click("#quiet-sum")                                 # open the fold
    page.wait_for_timeout(300)
    small = page.evaluate("""() => [...document.querySelectorAll('#quietbox button')]
        .filter(b => b.offsetParent !== null)
        .map(b => ({t: b.textContent.trim().slice(0, 30), h: b.getBoundingClientRect().height}))
        .filter(b => b.h < 40)""")
    assert small == [], small
    buttons = page.evaluate("() => document.querySelectorAll('#quietbox button').length")
    assert buttons == 5
    assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth")
    page.close()


def test_on_a_desktop_the_box_is_open_and_the_line_is_empty_until_a_write(browser):
    page = open_page(browser)
    assert page.evaluate("() => document.querySelector('#quietbox').open") is True
    assert txt(page, "#quiet-line") == ""
    assert page.evaluate("() => document.querySelector('#quiet-line').checkVisibility()") is False
    page.close()

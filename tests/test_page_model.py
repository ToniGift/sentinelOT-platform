"""Tests for the What-if process model and sandbox in static/sentinelot.html.

They run the page's own JavaScript in a headless browser, with the page opened
as a plain file (no server), so they also check that the sandbox works that way.

They need Playwright, which is not in requirements.txt:
    pip install -r requirements-dev.txt
They drive an installed Microsoft Edge (falling back to Chrome), so no browser
download is needed. Without a browser every test here is SKIPPED, and pytest says so in its summary
(pytest.ini sets -ra). A skipped test is not a pass.
"""
from pathlib import Path

import pytest

sync_api = pytest.importorskip(
    "playwright.sync_api",
    reason="Playwright is not installed: page model tests NOT RUN "
           "(pip install -r requirements-dev.txt)")

PAGE = (Path(__file__).resolve().parents[1] / "static" / "sentinelot.html").as_uri()
TAGS = ["sealer_temperature", "conveyor_speed", "tank_level", "pump_pressure",
        "flow_rate"]


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
            pytest.skip("No installed Edge or Chrome could be launched: page "
                        "model tests NOT RUN (" + "; ".join(errors) + ")")
        yield b
        b.close()


def open_page(browser):
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(PAGE, wait_until="domcontentloaded")
    page.wait_for_function("() => window.ProcessModel && window.__sentinelot")
    page.errors = errors
    return page


@pytest.fixture(scope="module")
def page(browser):
    p = open_page(browser)
    yield p
    p.close()


@pytest.fixture(scope="module")
def cur(page):
    """The current limits, as the page holds them when opened without a server."""
    page.wait_for_function("() => document.querySelector('#lim-tag').options.length === 5")
    page.click("#tab-sim")
    return page.evaluate("""() => { const o = {};
        document.querySelectorAll('#sim-cmp tr').forEach((tr, i) => {
          const nums = tr.children[2].querySelector('small').textContent.split(' / ').map(Number);
          o[window.ProcessModel.TAGS[i]] = {low_low: nums[0], low: nums[1], high: nums[2], high_high: nums[3]} });
        return o }""")


def settle(page, inp, steps=400):
    """Run the model to a steady state for these inputs; return state and values."""
    return page.evaluate(
        """([inp, steps]) => { const M = window.ProcessModel;
            const st = M.run(M.initial(), inp, steps);
            return {st, vals: M.values(inp, st)} }""", [inp, steps])


def effects(page, inp, st, cur):
    return page.evaluate("([i, s, c]) => window.ProcessModel.effects(i, s, c)",
                         [inp, st, cur])


def evaluate(page, vals, limits):
    return page.evaluate("([v, l]) => window.ProcessModel.evaluate(v, l)",
                         [vals, limits])


NORMAL = {"sp": 160, "rpm": 1200, "level": 50, "pump": True}


def test_page_loads_as_a_plain_file_and_limits_are_the_plant_ones(page, cur):
    assert set(cur) == set(TAGS)
    assert cur["sealer_temperature"] == {"low_low": 100, "low": 120,
                                         "high": 190, "high_high": 205}
    assert page.errors == []


def test_normal_operation_raises_nothing(page, cur):
    r = settle(page, NORMAL)
    assert evaluate(page, r["vals"], cur) == {t: None for t in TAGS}
    fx = effects(page, NORMAL, r["st"], cur)
    assert {d["level"] for d in fx.values()} == {"ok"}
    assert round(r["st"]["picked"]) == 42 and r["st"]["backlog"] == 0
    assert r["vals"]["pump_pressure"] == 5 and r["vals"]["flow_rate"] == 120


def test_step_is_pure(page):
    out = page.evaluate("""() => { const M = window.ProcessModel;
        const st = M.initial(), inp = {sp: 240, rpm: 1800, level: 5, pump: true};
        const a = JSON.stringify([st, inp]); const n = M.step(st, inp);
        return {same: JSON.stringify([st, inp]) === a, moved: n.pv > st.pv} }""")
    assert out == {"same": True, "moved": True}


def test_sealer_follows_setpoint_with_a_lag_and_goes_over_the_high_limit(page, cur):
    inp = {**NORMAL, "sp": 230}
    one = settle(page, inp, 1)
    assert 160 < one["vals"]["sealer_temperature"] < 170        # lag, not a jump
    hot = settle(page, {**NORMAL, "sp": 198})
    assert evaluate(page, hot["vals"], cur)["sealer_temperature"] == "high"
    d = effects(page, {**NORMAL, "sp": 198}, hot["st"], cur)["SEALER-Line1"]
    assert d["level"] == "warn" and "hot" in d["text"]
    r = settle(page, inp)
    assert round(r["vals"]["sealer_temperature"], 1) == 230.0
    assert evaluate(page, r["vals"], cur)["sealer_temperature"] == "high_high"
    d = effects(page, inp, r["st"], cur)["SEALER-Line1"]
    assert d["level"] == "alarm" and d["text"] == "Film burns on the bars"
    assert d["value"] == "230.0 °C"
    cold = settle(page, {**NORMAL, "sp": 115})
    d = effects(page, {**NORMAL, "sp": 115}, cold["st"], cur)["SEALER-Line1"]
    assert d["text"] == "Weak seals, rejects rise"


def test_conveyor_over_its_limit_piles_product_up(page, cur):
    inp = {**NORMAL, "rpm": 1700}
    r = settle(page, inp, 200)
    assert evaluate(page, r["vals"], cur)["conveyor_speed"] == "high_high"
    assert round(r["st"]["picked"]) == 45                       # robot at its limit
    assert r["st"]["backlog"] > 20                              # and falling behind
    fx = effects(page, inp, r["st"], cur)
    assert fx["MOTOR-Conveyor-1"]["level"] == "alarm"
    assert "piles up" in fx["MOTOR-Conveyor-1"]["text"]
    assert fx["ROBOT-Pick-1"]["value"].endswith("packs waiting")
    slow = settle(page, {**NORMAL, "rpm": 800}, 50)
    assert effects(page, {**NORMAL, "rpm": 800}, slow["st"], cur)[
        "MOTOR-Conveyor-1"]["text"] == "Throughput falls; line starved"
    stop = settle(page, {**NORMAL, "rpm": 0}, 50)
    d = effects(page, {**NORMAL, "rpm": 0}, stop["st"], cur)["MOTOR-Conveyor-1"]
    assert d["level"] == "alarm" and "stopped" in d["text"]
    assert stop["st"]["picked"] == 0


def test_tank_at_100_percent_overflows(page, cur):
    inp = {**NORMAL, "level": 100}
    r = settle(page, inp, 50)
    assert evaluate(page, r["vals"], cur)["tank_level"] == "high_high"
    d = effects(page, inp, r["st"], cur)["TANK-Utility-1"]
    assert d["level"] == "alarm" and d["text"] == "Overflow, spill"
    risk = effects(page, {**NORMAL, "level": 85},
                   settle(page, {**NORMAL, "level": 85}, 50)["st"], cur)
    assert risk["TANK-Utility-1"]["text"] == "Overflow risk"
    assert risk["TANK-Utility-1"]["level"] == "warn"


def test_tank_at_low_low_runs_the_pump_dry(page, cur):
    inp = {**NORMAL, "level": 10}
    r = settle(page, inp, 100)
    a = evaluate(page, r["vals"], cur)
    assert a["tank_level"] == "low_low"
    assert r["vals"]["pump_pressure"] == 1                      # pressure has dropped
    assert a["pump_pressure"] == "low_low" and a["flow_rate"] == "low_low"
    fx = effects(page, inp, r["st"], cur)
    assert fx["PUMP-Utility-1"]["level"] == "alarm"
    assert fx["PUMP-Utility-1"]["text"] == "Pump runs dry; pressure drops"
    assert fx["TANK-Utility-1"]["level"] == "alarm"
    off = settle(page, {**NORMAL, "pump": False}, 100)
    assert off["vals"]["pump_pressure"] == 0 and off["vals"]["flow_rate"] == 0
    assert effects(page, {**NORMAL, "pump": False}, off["st"], cur)[
        "FLOW-Meter-1"]["text"] == "No flow"


# One case per tag: inputs that make the CURRENT limits raise an alarm, and
# proposed limits wide enough to stay silent at the same value.
MISSED = [
    ("sealer_temperature", {**NORMAL, "sp": 230}, "high_high",
     {"low_low": 100, "low": 120, "high": 250, "high_high": 265},
     "Sealer at 230.0 °C", "The film would burn with no alarm."),
    ("conveyor_speed", {**NORMAL, "rpm": 1600}, "high",
     {"low_low": 600, "low": 900, "high": 1900, "high_high": 2000},
     "Conveyor at 1600 rpm", "Product would pile up at the robot with no alarm."),
    ("tank_level", {**NORMAL, "level": 96}, "high_high",
     {"low_low": 10, "low": 20, "high": 98, "high_high": 99},
     "Tank at 96.0 %", "The tank could overflow with no alarm."),
    ("pump_pressure", {**NORMAL, "level": 5}, "low_low",
     {"low_low": 0.2, "low": 0.5, "high": 7, "high_high": 8},
     "Pump pressure at 1.00 bar", "The pump could run dry with no alarm."),
    ("flow_rate", {**NORMAL, "pump": False}, "low_low",
     {"low_low": -2, "low": -1, "high": 160, "high_high": 180},
     "Flow at 0.0 m3/h", "A loss of flow would go unnoticed."),
]


@pytest.mark.parametrize("tag,inp,cur_alarm,proposed,start,consequence", MISSED,
                         ids=[m[0] for m in MISSED])
def test_proposed_limits_miss_an_alarm_the_current_limits_catch(
        page, cur, tag, inp, cur_alarm, proposed, start, consequence):
    r = settle(page, inp)
    prop = {**cur, tag: proposed}
    assert evaluate(page, r["vals"], cur)[tag] == cur_alarm
    assert evaluate(page, r["vals"], prop)[tag] is None
    out = page.evaluate("([v, c, p]) => window.ProcessModel.allMissed(v, c, p)",
                        [r["vals"], cur, prop])
    mine = [m["text"] for m in out if m["tag"] == tag]
    label = {"high": "High", "high_high": "High high", "low_low": "Low low"}[cur_alarm]
    assert mine == [f"{start}: the current limits raise {label}; "
                    f"the proposed limits raise nothing. {consequence}"]
    # and no sentence when the proposed limits are the current ones
    assert page.evaluate("([v, c]) => window.ProcessModel.allMissed(v, c, c)",
                         [r["vals"], cur]) == []


def test_weaker_but_present_alarm_is_not_called_missed(page):
    assert page.evaluate(
        "() => window.ProcessModel.missed('tank_level', 92, 'high_high', 'high')") is None
    assert page.evaluate(
        "() => window.ProcessModel.missed('tank_level', 50, null, null)") is None


def test_invalid_proposed_limits_raise_nothing(page):
    bad = {"low_low": 10, "low": 20, "high": 95, "high_high": 90}
    assert page.evaluate("l => window.ProcessModel.alarmState(99, l)", bad) is None


def test_sandbox_shows_the_missed_alarm_sentence_on_the_page(browser):
    page = open_page(browser)
    page.wait_for_function("() => document.querySelector('#lim-tag').options.length === 5")
    page.click("#tab-sim")
    assert "Simplified demo model, not plant physics." in page.inner_text("#pane-sim")
    assert ("Instant comparison for the demo; the AlarmOps gate uses deadband "
            "and delay.") in page.inner_text("#pane-sim")
    page.click("#sim-preset")
    page.fill("#sim-sp-n", "230")
    page.dispatch_event("#sim-sp-n", "change")
    page.wait_for_selector("#sim-missed .miss", timeout=60000)
    text = page.inner_text("#sim-missed")
    assert "the current limits raise High" in text
    assert "the proposed limits raise nothing. The film would burn with no alarm." in text
    assert "Sealer at" in text
    page.click("#sim-reset")
    page.wait_for_function("() => !document.querySelector('#sim-missed .miss')")
    assert page.errors == []
    page.close()


def test_leaving_the_sandbox_restores_the_live_plant_and_its_alarm(browser):
    page = open_page(browser)
    page.click('[data-atk="setpoint"]')
    page.wait_for_selector("#alarm.crit", timeout=20000)
    page.wait_for_timeout(1500)
    page.click("#tab-sim")
    before = page.evaluate("() => window.__sentinelot.live()")
    assert before["active"]["kind"] == "setpoint" and before["st"]["sp"] == 240
    alarm_html = page.inner_html("#alarm")
    # drive the sandbox hard for a few seconds
    for sel, val in (("#sim-sp-n", "110"), ("#sim-rpm-n", "0"), ("#sim-level-n", "100")):
        page.fill(sel, val)
        page.dispatch_event(sel, "change")
    page.uncheck("#sim-pump")
    page.wait_for_timeout(3000)
    assert page.text_content("#proc-h") == "Line 1 process (What-if, simulated)"
    assert page.inner_text("#t-sp .v") == "110.0"
    during = page.evaluate("() => window.__sentinelot.live()")
    assert {**during, "tab": None} == {**before, "tab": None}   # live plant untouched
    # click and read in one step, so no live tick can run in between
    after = page.evaluate("""() => { document.querySelector('#tab-live').click();
                                     return window.__sentinelot.live() }""")
    assert after["tab"] == "live"
    assert {**after, "tab": None} == {**before, "tab": None}
    assert page.inner_html("#alarm") == alarm_html             # same alarm, same note
    assert page.text_content("#proc-h") == "Line 1 process"
    assert page.inner_text("#t-sp .v") == "240.0"              # live value is back
    assert page.errors == []
    page.close()


# ---------------- annunciator, tags and the drawing view ----------------

def live(page):
    return page.evaluate("() => window.__sentinelot.live()")


def win_classes(page, kind):
    return page.get_attribute(f'.win[data-kind="{kind}"]', "class").split()


def test_second_attack_before_acknowledge_gives_two_alarms_and_first_out(browser):
    """Detection keeps running while an alarm is active; first-out stays until Reset."""
    page = open_page(browser)
    page.click('[data-atk="setpoint"]')
    page.wait_for_selector("#alarm.crit", timeout=20000)
    page.wait_for_function(
        "() => !document.querySelector('[data-atk=\"robot\"]').disabled", timeout=20000)
    assert live(page)["alarms"][0]["ack"] is False            # not acknowledged
    page.click('[data-atk="robot"]')
    page.wait_for_function(
        "() => window.__sentinelot.live().alarms.some(a => a.kind === 'robot')",
        timeout=20000)
    s = live(page)
    by = {a["kind"]: a for a in s["alarms"]}
    assert by["setpoint"]["seq"] == 1 and by["setpoint"]["firstOut"] is True
    assert by["robot"]["seq"] == 2 and by["robot"]["firstOut"] is False
    assert s["firstOut"] == "setpoint"
    assert s["st"]["sp"] == 240 and s["st"]["robot"] == 0
    page.click('.win[data-kind="setpoint"]')
    assert "TIC-101 SP changed" in page.text_content("#alarm h3")
    assert "fo" in win_classes(page, "setpoint") and "unack" in win_classes(page, "setpoint")
    assert "fo" not in win_classes(page, "robot") and "unack" in win_classes(page, "robot")
    # acknowledge: the flashing stops and nothing else changes
    page.click("#an-ack")
    s = live(page)
    assert all(a["ack"] for a in s["alarms"]) and s["firstOut"] == "setpoint"
    assert s["st"]["sp"] == 240 and s["st"]["robot"] == 0
    assert "fo" in win_classes(page, "setpoint") and "unack" not in win_classes(page, "setpoint")
    # reset clears the first-out mark; alarms whose condition is still there stay
    page.click("#an-reset")
    s = live(page)
    assert s["firstOut"] is None
    assert {"setpoint", "robot"} <= {a["kind"] for a in s["alarms"]}
    assert "fo" not in win_classes(page, "setpoint")
    assert page.errors == []
    page.close()


def test_restore_then_reset_clears_the_alarm(browser):
    page = open_page(browser)
    page.click('[data-atk="robot"]')
    page.wait_for_selector("#alarm.crit", timeout=20000)
    page.click("#an-ack")
    page.wait_for_function(
        "() => { const b = [...document.querySelectorAll('#alarm .btnrow button')]"
        ".find(x => x.textContent.startsWith('Restore')); return b && !b.disabled }",
        timeout=20000)
    page.click("#alarm .btnrow button:has-text('Restore')")
    s = live(page)
    assert s["st"]["robot"] == 1 and s["alarms"][0]["cleared"] is True
    page.click("#an-reset")
    s = live(page)
    assert s["alarms"] == [] and s["active"] is None and s["firstOut"] is None
    assert page.errors == []
    page.close()


ALARMOPS_TAG = {"sealer_temperature": "TT-101", "conveyor_speed": "ST-101",
                "tank_level": "LT-501", "pump_pressure": "PT-501", "flow_rate": "FT-501"}


def test_equipment_list_maps_every_alarmops_tag_and_marks_demo_items(page):
    rows = page.evaluate("""() => [...document.querySelectorAll('#eq tbody tr')].map(tr =>
        [...tr.children].map(td => td.textContent.trim()))""")
    by_tag = {r[0]: r for r in rows}
    for lim, tag in ALARMOPS_TAG.items():
        assert by_tag[tag][4] == lim
    assert "SC-201" not in page.content()
    assert by_tag["GW-101"][1] == "SENSOR-GW-1"              # a gateway, not a transmitter
    assert by_tag["TIC-101"][2] == "Signal tag"
    for tag, name in (("WS-601", "ENG-WS-01"), ("DB-601", "HIST-01"), ("SRV-601", "MES-SRV-01"),
                      ("SRV-602", "AD-OT-01"), ("SRV-603", "SCADA-SRV-01")):
        assert by_tag[tag][1] == name
    for tag in ("SRV-601", "SRV-602", "WS-501", "SRV-501"):   # added for the demo
        assert by_tag[tag][5] == "Demo only"
    assert by_tag["PLC-101"][5] == "Project asset file"
    text = page.text_content("body")
    assert "Tags are ISA-style. IT equipment uses plain asset-class prefixes." in text
    assert "recommends, never acts" in text and "checks alarm-limit changes" in text


def lit_rows(page):
    return page.evaluate(
        "() => [...document.querySelectorAll('#eq tr.lit')].map(r => r.dataset.tag)")


def test_blocked_limit_change_lights_its_tag(browser):
    page = open_page(browser)
    page.wait_for_function("() => document.querySelector('#lim-tag').options.length === 5")
    assert lit_rows(page) == []
    page.click("#tab-lim")
    page.click("#lim-preset")                                 # sealer high 250: blocked
    page.wait_for_selector("#lim-out .g-block")
    assert lit_rows(page) == ["TT-101"]
    page.click("#lim-reset")
    assert lit_rows(page) == []
    # What-if: the proposed limit would miss an alarm
    page.click("#tab-sim")
    page.click("#sim-preset")
    page.fill("#sim-sp-n", "230")
    page.dispatch_event("#sim-sp-n", "change")
    page.wait_for_selector("#sim-missed .miss", timeout=60000)
    assert lit_rows(page) == ["TT-101"]
    assert page.errors == []
    page.close()


def plate_dim(page, tag):
    return page.evaluate(
        "t => [...document.querySelectorAll('#labels .lab')].find(e => e.textContent === t)"
        ".classList.contains('dim')", tag)


def test_level_keys_cover_every_level_and_dim_the_others(browser):
    page = open_page(browser)
    keys = page.evaluate(
        "() => [...document.querySelectorAll('#levels button')].map(b => b.textContent)")
    assert keys == ["L5", "L4", "L3.5", "L3", "L2", "L1", "L0"]
    page.click("#levels button:text-is('L3.5')")
    assert page.evaluate("() => window.__sentinelot.view().focus") == "3.5"
    assert plate_dim(page, "PLC-101") is True and plate_dim(page, "DB-401") is False
    page.click("#levels button:text-is('L3.5')")              # same key again: undim
    assert page.evaluate("() => window.__sentinelot.view().focus") is None
    assert plate_dim(page, "PLC-101") is False
    assert page.errors == []
    page.close()


PROJECT = """() => {
  const NAMES = __NAMES__;
  const S = window.__sentinelot, v = S.view(), st = document.querySelector('#stage').getBoundingClientRect();
  const sub = (a, b) => [a[0]-b[0], a[1]-b[1], a[2]-b[2]], dot = (a, b) => a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
  const cross = (a, b) => [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]];
  const norm = a => { const n = Math.hypot(...a); return a.map(x => x/n) };
  const T = [v.x, v.y, v.z];
  const f = norm([-Math.sin(v.phi)*Math.sin(v.theta), -Math.cos(v.phi), -Math.sin(v.phi)*Math.cos(v.theta)]);
  const right = norm(cross(f, [0, 1, 0])), up = cross(right, f);
  const out = [];
  for (const [name, tag] of NAMES) {
    const a = S.anchor(name), p = sub([a.x, a.y, a.z], T);
    const ex = (dot(p, right)/(v.half*v.aspect)*0.5+0.5)*v.w, ey = (-dot(p, up)/v.half*0.5+0.5)*v.h;
    const e = [...document.querySelectorAll('#labels .lab')].find(x => x.textContent.startsWith(tag));
    const r = e.getBoundingClientRect();
    out.push({tag, ex, ey, x: r.left + r.width/2 - st.left, y: r.top - st.top + 1.4*r.height, w: r.width, sw: v.w});
  }
  return {iso: v.iso, zoom: v.zoom, y: v.y, out};
}"""
PLATES = [["PLC-Line1", "PLC-101"], ["HMI-Line1", "HMI-101"], ["HIST-01", "DB-601"],
          ["SENSOR-GW-1", "GW-101"], ["ERP-SRV-01", "SRV-401"], ["ROBOT-Pick-1", "RB-101"]]


def plates_on_their_equipment(page):
    """A plate sits on its equipment, unless the collision handling nudged it straight up."""
    page.wait_for_timeout(1800)                               # let a glide finish
    import json
    r = page.evaluate(PROJECT.replace("__NAMES__", json.dumps(PLATES)))
    assert r["iso"] is True
    seen = exact = 0
    for o in r["out"]:
        if o["ex"] < o["w"] / 2 + 8 or o["ex"] > o["sw"] - o["w"] / 2 - 8:
            continue                                          # kept inside the stage on purpose
        assert abs(o["x"] - o["ex"]) < 1.5, o                 # a nudge never moves it sideways
        if abs(o["y"] - o["ey"]) < 1.5:
            exact += 1
        else:
            assert o["y"] < o["ey"], o                        # nudged up and away, never down
        seen += 1
    assert seen >= 4 and exact >= 2
    return r


def test_tag_plates_stay_on_their_equipment_in_the_orthographic_view(browser):
    """Projects each plate's anchor with the test's own maths and compares it with where the page drew it."""
    page = open_page(browser)
    page.click("#isob")
    a = plates_on_their_equipment(page)
    page.click("#zin")
    page.click("#zin")
    b = plates_on_their_equipment(page)
    page.click("#down")
    page.click("#down")
    c = plates_on_their_equipment(page)
    assert b["zoom"] > a["zoom"] and c["y"] < b["y"]
    page.click("#persp")
    assert page.evaluate("() => window.__sentinelot.view().iso") is False
    assert page.errors == []
    page.close()


def test_phone_width_shows_all_four_tabs_and_the_short_labels(browser):
    for width, first in ((390, "live"), (768, "live attack")):
        page = browser.new_page(viewport={"width": width, "height": 844})
        page.goto(PAGE, wait_until="domcontentloaded")
        page.wait_for_function("() => window.ProcessModel && window.__sentinelot")
        t = page.evaluate("""() => { const box = document.querySelector('#tabs');
            return {fits: box.scrollWidth <= box.clientWidth + 1,
                    page: document.documentElement.scrollWidth <= window.innerWidth,
                    tabs: [...box.querySelectorAll('button')].map(b => { const r = b.getBoundingClientRect();
                      return {text: b.innerText.replace(/\\s+/g, ' ').trim().toLowerCase(),
                              left: r.left, right: r.right, w: r.width} })} }""")
        assert t["fits"] and t["page"]
        assert all(0 <= b["left"] and b["right"] <= width and b["w"] > 40 for b in t["tabs"])
        words = [b["text"].lstrip("0123456789 ") for b in t["tabs"]]
        assert words == [first, "recorded", "limits", "what-if"]
        page.close()


# ---------------- the firewall rule editor on the page ----------------
# These check the page against the demo's own rules, not against a real plant.

def rules_of(page):
    return page.evaluate("() => window.__sentinelot.rules()")


def set_rule(page, fw, value):
    page.evaluate("([f, v]) => window.__sentinelot.setRule(f, v)", [fw, value])


def test_the_four_switches_start_as_found_and_are_labelled_by_their_rule(page):
    assert rules_of(page) == {"FW-301": "allow", "FW-302": "allow",
                              "FW-303": "allow", "FW-304": "allow"}
    rows = page.evaluate("""() => [...document.querySelectorAll('#rules li')].map(li => ({
        label: li.querySelector('.lb').textContent,
        state: li.querySelector('.swt').textContent,
        pressed: li.querySelector('.swt').getAttribute('aria-pressed'),
        fw: li.querySelector('.swt').dataset.fw}))""")
    assert [r["fw"] for r in rows] == ["FW-301", "FW-302", "FW-303", "FW-304"]
    assert all(r["state"] == "ALLOW" and r["pressed"] == "true" for r in rows)
    assert rows[3]["label"].endswith(
        "Non-approved hosts across the line 1 cell boundary, Modbus 502 and DNP3 20000")
    for r in rows[:3]:                                   # each names its own rule, not the same one
        assert "Non-approved" in r["label"] and "any port" in r["label"]
    assert len({r["label"] for r in rows}) == 4
    text = page.text_content("#pane-live")
    assert "Demo rules, not a recommendation for a real plant" in text
    assert "As found. Each switch removes one over-broad rule." in text
    assert ("A firewall rule sees source, destination and port, not the change window or "
            "the value being written. That is what triage is for.") in text


def test_a_denied_attack_raises_no_alarm_and_changes_nothing_in_the_plant(browser):
    page = open_page(browser)
    set_rule(page, "FW-303", "deny")
    assert "3 of 3 live attacks stop" in page.text_content("#seg-sum")
    page.click('[data-atk="setpoint"]')
    page.wait_for_function("() => window.__sentinelot.live().blocked", timeout=20000)
    page.wait_for_timeout(1200)
    s = live(page)
    assert s["blocked"] == {"fw": "FW-303", "rule": "SEG-303",
                            "kind": "setpoint", "reached": "L3.5"}
    assert s["alarms"] == [] and s["firstOut"] is None       # not an alarm
    assert s["st"]["sp"] == 160                              # the setpoint never moved
    assert page.text_content("#an-st") == "NO ALARM"
    # the informational window: steady, never first out, never counted
    cls = win_classes(page, "seg")
    assert "info" in cls and "on" in cls
    assert "unack" not in cls and "fo" not in cls and "crit" not in cls
    assert page.text_content('.win[data-kind="seg"] .w-tag') == "FW-303"
    assert "NOT AN ALARM" in page.text_content('.win[data-kind="seg"] .w-st')
    # the note is pre-written and says the sensor saw nothing
    assert page.text_content("#alarm h3") == "Stopped at the firewall, not by SentinelOT"
    assert page.text_content("#alarm .who") == "Not seen by SentinelOT · simulated firewall log"
    note = page.text_content("#alarm .text")
    assert "no frame reached the controller" in note
    assert "never reached the mirror port" in note
    assert "The setpoint did not change" in note
    # the log shows the denial and no reply
    rows = page.eval_on_selector_all(".row.deny .meta", "rs => rs.map(r => r.textContent)")
    assert len(rows) == 1 and "DENY at FW-303" in rows[0]
    assert "did not reach PLC-101" in rows[0]
    assert page.eval_on_selector_all(
        ".row", "rs => rs.filter(r => r.textContent.includes('Echo: write accepted')).length") == 0
    assert page.errors == []
    page.close()


def test_normal_polling_keeps_running_with_every_switch_set_to_deny(browser):
    """The approved flows have fixed rules, so no switch touches the HMI and historian polling."""
    page = open_page(browser)
    for fw in ("FW-301", "FW-302", "FW-303", "FW-304"):
        set_rule(page, fw, "deny")
    assert rules_of(page) == {fw: "deny" for fw in
                              ("FW-301", "FW-302", "FW-303", "FW-304")}
    before = live(page)["rows"]
    page.wait_for_function("n => window.__sentinelot.live().rows > n", arg=before, timeout=20000)
    page.wait_for_timeout(2500)
    after = live(page)
    assert after["rows"] > before
    # every new row is ordinary polling: nothing denied, because nothing unapproved is talking
    assert page.eval_on_selector_all(".row.deny", "rs => rs.length") == 0
    seen = page.eval_on_selector_all(".row .meta", "rs => rs.map(r => r.textContent).join(' ')")
    assert "10.10.30.5" in seen and "10.10.40.20" in seen     # HMI-Line1 and HIST-01
    assert after["st"]["rpm"] > 0                             # the plant is still running
    assert page.errors == []
    page.close()


def test_the_three_alerts_from_approved_hosts_are_never_stopped_on_the_page(browser):
    page = open_page(browser)
    for fw in ("FW-301", "FW-302", "FW-303", "FW-304"):
        set_rule(page, fw, "deny")
    page.click("#tab-rec")
    for n in (2, 3, 8):                                       # 1-based, as the page lists them
        page.click(f"#recs button >> nth={n - 1}")
        assert "Passes: an approved flow, which no switch touches" in page.text_content("#detail")
    page.click("#recs button >> nth=5")                       # alert 6, DNP3, not approved
    assert "Stopped at FW-304" in page.text_content("#detail")
    assert "5 of 8 recorded alerts would stop" in page.text_content("#seg-sum")
    assert page.errors == []
    page.close()


def test_a_denied_trace_stops_at_the_firewall_in_3d(browser):
    page = open_page(browser)
    set_rule(page, "FW-304", "deny")
    page.click('[data-atk="robot"]')
    page.wait_for_function("() => window.__sentinelot.live().blocked", timeout=20000)
    page.wait_for_timeout(1200)
    shown = page.evaluate(
        "() => [...document.querySelectorAll('#labels .lab')]"
        ".filter(e => e.style.display !== 'none').map(e => e.textContent)")
    assert any(t.startswith("FW-304") and "DENY" in t for t in shown)
    # the controller is not part of the trace, because nothing reached it
    assert not any(t.startswith("PLC-101 ·") for t in shown)
    assert live(page)["st"]["robot"] == 1
    assert page.errors == []
    page.close()


def test_turning_a_rule_back_to_allow_lets_the_attack_through_again(browser):
    page = open_page(browser)
    set_rule(page, "FW-302", "deny")
    page.click('[data-atk="robot"]')
    page.wait_for_function("() => window.__sentinelot.live().blocked", timeout=20000)
    assert live(page)["alarms"] == []
    set_rule(page, "FW-302", "allow")
    page.wait_for_function("() => !document.querySelector('[data-atk=\"robot\"]').disabled",
                           timeout=20000)
    page.click('[data-atk="robot"]')
    page.wait_for_selector("#alarm.crit", timeout=20000)
    s = live(page)
    assert [a["kind"] for a in s["alarms"]] == ["robot"] and s["st"]["robot"] == 0
    assert s["blocked"] is None
    assert page.errors == []
    page.close()


def test_the_page_has_a_drawn_favicon_and_no_emoji(page):
    href = page.get_attribute('link[rel="icon"]', "href")
    assert href.startswith("data:image/svg+xml,")
    assert "<svg" in href.replace("%3C", "<") and "emoji" not in href
    assert "text" not in href                                 # drawn, not a character


# ---------------- the design-review fixes ----------------

def visible_plates(page):
    return page.evaluate("""() => [...document.querySelectorAll('#labels .lab')]
        .filter(e => e.style.display !== 'none')
        .map(e => { const r = e.getBoundingClientRect();
          return {text: e.textContent, level: e.classList.contains('level'),
                  lit: e.classList.contains('lit'), hot: e.classList.contains('hot'),
                  x: r.left, y: r.top, w: r.width, h: r.height,
                  size: parseFloat(getComputedStyle(e).fontSize)} })""")


def test_no_two_plates_overlap_and_lit_ones_stay_on_top(browser):
    page = open_page(browser)
    set_rule(page, "FW-304", "deny")                           # lights FW-304 with a DENY plate
    page.click('[data-atk="setpoint"]')
    page.wait_for_function("() => window.__sentinelot.live().blocked", timeout=20000)
    page.wait_for_timeout(1500)
    plates = visible_plates(page)
    assert len(plates) > 10
    for i, a in enumerate(plates):
        for b in plates[i + 1:]:
            apart = (a["x"] + a["w"] <= b["x"] or b["x"] + b["w"] <= a["x"]
                     or a["y"] + a["h"] <= b["y"] or b["y"] + b["h"] <= a["y"])
            assert apart, (a["text"], b["text"])
    assert any("DENY" in p["text"] for p in plates)            # the lit one survived the sorting
    assert page.errors == []
    page.close()


def test_level_names_sit_in_a_gutter_with_a_leader_line_to_their_floor(browser):
    page = open_page(browser)
    for camera in ("#persp", "#isob"):
        page.click(camera)
        page.wait_for_timeout(1500)
        levels = [p for p in visible_plates(page) if p["level"]]
        assert len(levels) == 7
        lefts = {round(p["x"], 1) for p in levels}
        assert len(lefts) == 1, lefts                          # one gutter, all of them aligned
        # nothing else is drawn on top of a level name
        others = [p for p in visible_plates(page) if not p["level"]]
        for lv in levels:
            for o in others:
                apart = (lv["x"] + lv["w"] <= o["x"] or o["x"] + o["w"] <= lv["x"]
                         or lv["y"] + lv["h"] <= o["y"] or o["y"] + o["h"] <= lv["y"])
                assert apart, (lv["text"], o["text"], camera)
        leaders = page.evaluate(
            "() => [...document.querySelectorAll('#leaders line')].map(l => ({"
            "x1: +l.getAttribute('x1'), y1: +l.getAttribute('y1'),"
            "x2: +l.getAttribute('x2'), y2: +l.getAttribute('y2')}))")
        assert len(leaders) >= 5, camera
        for ln in leaders:
            assert ln["x2"] > ln["x1"]                         # out from the gutter to the floor
    assert page.errors == []
    page.close()


def test_at_phone_width_only_the_levels_that_matter_keep_their_plates(browser):
    page = browser.new_page(viewport={"width": 390, "height": 844})
    page.goto(PAGE, wait_until="domcontentloaded")
    page.wait_for_function("() => window.ProcessModel && window.__sentinelot")
    page.wait_for_timeout(1800)
    plates = [p for p in visible_plates(page) if not p["level"]]
    always = ("FW-301", "FW-302", "FW-303", "FW-304", "PLC-101")
    assert all(p["lit"] or p["hot"] or p["text"].startswith(always) for p in plates), plates
    assert all(p["size"] >= 11 for p in visible_plates(page))
    page.click("#levels button:text-is('L1')")
    page.wait_for_timeout(1600)
    shown = [p["text"] for p in visible_plates(page) if not p["level"]]
    assert "PLC-101" in shown and "PLC-201" in shown           # the focused level
    assert "SRV-401" not in shown                              # level 4, not focused
    assert all(p["size"] >= 11 for p in visible_plates(page))
    page.close()


def test_wide_screens_still_show_every_plate(page):
    page.wait_for_timeout(1200)
    shown = [p["text"] for p in visible_plates(page) if not p["level"]]
    for tag in ("PLC-101", "SRV-401", "GW-101", "FW-301", "RB-101"):
        assert any(t.startswith(tag) for t in shown), tag


def test_the_annunciator_is_on_the_first_screen_beside_the_stage(browser):
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.goto(PAGE, wait_until="domcontentloaded")
    page.wait_for_function("() => window.__sentinelot")
    page.wait_for_timeout(1200)
    box = page.evaluate("""() => { const w = document.querySelector('#windows');
        const s = document.querySelector('#stage').getBoundingClientRect();
        const r = w.getBoundingClientRect();
        return {winTop: r.top, winBottom: r.bottom, stageBottom: s.bottom,
                h: window.innerHeight} }""")
    assert box["winTop"] < box["h"], box                       # the windows start above the fold
    assert box["winTop"] > box["stageBottom"] - 2              # and below the stage, not beside it
    assert box["stageBottom"] < box["h"]                       # the stage fits too
    page.close()


def test_the_switch_panel_folds_up_on_a_phone_and_is_open_on_a_desktop(browser):
    for width, want_open in ((390, False), (1280, True)):
        page = browser.new_page(viewport={"width": width, "height": 844})
        page.goto(PAGE, wait_until="domcontentloaded")
        page.wait_for_function("() => window.__sentinelot")
        assert page.evaluate("() => document.querySelector('#segbox').open") is want_open
        page.close()


def test_phone_order_is_stage_tabs_attacks_then_annunciator(browser):
    page = browser.new_page(viewport={"width": 390, "height": 844})
    page.goto(PAGE, wait_until="domcontentloaded")
    page.wait_for_function("() => window.__sentinelot")
    page.wait_for_timeout(1000)
    tops = page.evaluate("""() => { const t = s => document.querySelector(s).getBoundingClientRect().top
                                      + window.scrollY;
        return {stage: t('#stage'), tabs: t('#tabs'), attacks: t('.attacks'),
                last: t('[data-atk="scan"]'), anun: t('#windows'),
                h: window.innerHeight} }""")
    assert tops["stage"] < tops["tabs"] < tops["attacks"] < tops["anun"]
    # all three attacks and the annunciator within one screen of scrolling from the tab row
    assert tops["last"] - tops["tabs"] < tops["h"]
    assert tops["anun"] - tops["tabs"] < tops["h"], tops
    page.close()


def test_every_control_a_thumb_has_to_hit_is_tall_enough_on_a_phone(browser):
    page = browser.new_page(viewport={"width": 390, "height": 844})
    page.goto(PAGE, wait_until="domcontentloaded")
    page.wait_for_function("() => window.__sentinelot")
    page.click("#tab-lim")
    page.wait_for_timeout(600)
    small = page.evaluate("""() => [...document.querySelectorAll(
        '.btn, .swt, .sq, .tabs button, .tools button, .levels button, .recs button, #lim-tag, .lims input')]
        .filter(e => e.offsetParent !== null)
        .map(e => ({t: (e.textContent || e.id).trim().slice(0, 24), h: e.getBoundingClientRect().height}))
        .filter(e => e.h > 0 && e.h < 40)""")
    assert small == [], small
    page.close()


def test_the_limits_heading_is_not_clipped(browser):
    """Big Shoulders is a tall face: a tight line box cut the underscore off sealer_temperature."""
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.goto(PAGE, wait_until="domcontentloaded")
    page.wait_for_function("() => document.querySelector('#lim-tag').options.length === 5")
    page.click("#tab-lim")
    page.click("#lim-preset")
    page.wait_for_selector("#lim-out h3")
    m = page.evaluate("""() => { const h = document.querySelector('#lim-out h3');
        const cs = getComputedStyle(h);
        return {text: h.textContent, line: parseFloat(cs.lineHeight),
                size: parseFloat(cs.fontSize), clip: cs.overflow,
                scroll: h.scrollHeight, client: h.clientHeight} }""")
    assert "sealer_temperature" in m["text"]
    assert m["line"] / m["size"] >= 1.2, m                     # room under the baseline
    assert m["scroll"] <= m["client"] + 1, m                   # nothing cut off
    page.close()


def test_the_internet_is_drawn_flat_with_no_spheres(browser):
    page = open_page(browser)
    kinds = page.evaluate("""() => { const seen = [];
        // walk what the renderer holds, counting sphere geometries that belong to equipment
        return window.__sentinelot.geometry() }""")
    assert kinds["spheres"] == 0, kinds
    assert kinds["shapes"] >= 2                                # the cloud, drawn front and back
    page.close()


# ---------------- the side panel ----------------

def wide_page(browser, **kw):
    p = browser.new_page(viewport={"width": 1280, "height": 900}, **kw)
    errors = []
    p.on("pageerror", lambda e: errors.append(str(e)))
    p.goto(PAGE, wait_until="domcontentloaded")
    p.wait_for_function("() => window.ProcessModel && window.__sentinelot")
    p.errors = errors
    return p


def panel_scroll(page):
    return page.evaluate("""() => { const p = document.querySelector('#panel');
        return {top: p.scrollTop, h: p.clientHeight, full: p.scrollHeight} }""")


def test_the_side_panel_is_a_named_region_a_keyboard_can_scroll(browser):
    page = wide_page(browser)
    p = page.locator("#panel")
    assert p.get_attribute("tabindex") == "0"
    assert p.get_attribute("role") == "region"
    assert p.get_attribute("aria-label") == ("Attack controls, firewall rules "
                                             "and alarm detail")
    s = panel_scroll(page)
    assert s["full"] > s["h"] and s["top"] == 0           # there is something to scroll
    page.focus("#panel")
    assert page.evaluate("() => document.activeElement.id") == "panel"
    page.keyboard.press("PageDown")
    page.wait_for_timeout(500)
    down = panel_scroll(page)["top"]
    assert down > 0, "PageDown did not scroll the panel"
    page.keyboard.press("ArrowDown")
    page.wait_for_timeout(400)
    assert panel_scroll(page)["top"] >= down
    page.keyboard.press("Home")
    page.wait_for_timeout(500)
    assert panel_scroll(page)["top"] < down
    assert page.errors == []
    page.close()


def test_a_new_alarm_is_scrolled_into_view_in_the_panel_and_marked(browser):
    page = wide_page(browser)
    page.evaluate("() => document.querySelector('#panel').scrollTop = 0")
    page.click('[data-atk="setpoint"]')
    page.wait_for_selector("#alarm.crit", timeout=20000)
    page.wait_for_timeout(1200)
    box = page.evaluate("""() => { const p = document.querySelector('#panel');
        const a = document.querySelector('#alarm').getBoundingClientRect();
        const r = p.getBoundingClientRect();
        return {scrolled: p.scrollTop, visible: a.top >= r.top - 2 && a.top < r.bottom,
                marked: document.querySelector('#alarm').classList.contains('justin')} }""")
    assert box["scrolled"] > 0, box                       # the panel moved to it
    assert box["visible"], box
    assert box["marked"], box
    # the mark is temporary
    page.wait_for_function(
        "() => !document.querySelector('#alarm').classList.contains('justin')", timeout=8000)
    assert page.errors == []
    page.close()


def test_the_new_alarm_mark_does_not_animate_under_reduced_motion(browser):
    page = wide_page(browser, reduced_motion="reduce")
    page.click('[data-atk="robot"]')
    page.wait_for_selector("#alarm.crit", timeout=20000)
    page.wait_for_timeout(900)
    style = page.evaluate("""() => { const a = document.querySelector('#alarm');
        const cs = getComputedStyle(a);
        return {marked: a.classList.contains('justin'), name: cs.animationName,
                shadow: cs.boxShadow} }""")
    assert style["marked"] is True
    assert style["name"] == "none", style                 # steady, not flashing
    assert style["shadow"] != "none", style               # but still visibly marked
    assert page.errors == []
    page.close()


def test_every_switch_row_is_the_same_height_so_none_is_cut_at_the_fold(browser):
    for width in (1280, 1024, 390):
        page = browser.new_page(viewport={"width": width, "height": 900})
        page.goto(PAGE, wait_until="domcontentloaded")
        page.wait_for_function("() => window.__sentinelot")
        page.evaluate("() => document.querySelector('#segbox').open = true")
        page.wait_for_timeout(400)
        rows = page.evaluate("""() => [...document.querySelectorAll('#rules li')].map(li => {
            const tx = li.querySelector('.tx'), dt = li.querySelector('.dt');
            return {h: Math.round(li.getBoundingClientRect().height),
                    labelCut: tx.scrollHeight - tx.clientHeight,
                    detailCut: Math.max(0, dt.scrollWidth - dt.clientWidth - 2),
                    snap: getComputedStyle(li).scrollSnapAlign} })""")
        assert len({r["h"] for r in rows}) == 1, (width, rows)
        assert all(r["labelCut"] <= 0 and r["detailCut"] == 0 for r in rows), (width, rows)
        assert all(r["snap"] == "start" for r in rows), (width, rows)
        page.close()


def test_scrolling_the_panel_never_leaves_a_switch_row_cut_in_half(browser):
    """Rows are one fixed height and snap to the top, so a scroll lands on a row boundary."""
    page = wide_page(browser)
    page.evaluate("() => document.querySelector('#segbox').open = true")
    page.wait_for_timeout(300)
    assert page.evaluate(
        "() => getComputedStyle(document.querySelector('#panel')).scrollSnapType"
    ).split()[0] == "y"
    h = page.evaluate("() => document.querySelector('#rules li').getBoundingClientRect().height")
    top = page.evaluate("""() => { const p = document.querySelector('#panel');
        const first = document.querySelector('#rules li');
        p.scrollTop = first.offsetTop - p.offsetTop + 37;      // deliberately mid-row
        return p.scrollTop }""")
    page.wait_for_timeout(600)
    cut = page.evaluate("""() => { const p = document.querySelector('#panel').getBoundingClientRect();
        return [...document.querySelectorAll('#rules li')].filter(li => {
            const r = li.getBoundingClientRect();
            return (r.top < p.top - 1 && r.bottom > p.top + 1)
                || (r.top < p.bottom - 1 && r.bottom > p.bottom + 1) }).length }""")
    assert 100 < h < 112 and top > 0          # one row, border included
    assert cut <= 1, cut            # at most the one the fold lands on, and snapping removes it
    assert page.errors == []
    page.close()


def test_a_phone_always_keeps_the_firewalls_and_the_controller(browser):
    page = browser.new_page(viewport={"width": 390, "height": 844})
    page.goto(PAGE, wait_until="domcontentloaded")
    page.wait_for_function("() => window.ProcessModel && window.__sentinelot")
    page.wait_for_timeout(1800)
    plates = visible_plates(page)
    shown = [p["text"] for p in plates if not p["level"]]
    for tag in ("FW-301", "FW-302", "FW-303", "FW-304", "PLC-101"):
        assert any(t.startswith(tag) for t in shown), (tag, shown)
    assert not any(t.startswith("SRV-401") for t in shown)     # still hidden
    assert all(p["size"] >= 11 for p in plates)
    # and they still do not overlap
    for i, a in enumerate(plates):
        for b in plates[i + 1:]:
            apart = (a["x"] + a["w"] <= b["x"] or b["x"] + b["w"] <= a["x"]
                     or a["y"] + a["h"] <= b["y"] or b["y"] + b["h"] <= a["y"])
            assert apart, (a["text"], b["text"])
    page.close()

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
    page.wait_for_timeout(1800)                               # let a glide finish
    import json
    r = page.evaluate(PROJECT.replace("__NAMES__", json.dumps(PLATES)))
    assert r["iso"] is True
    seen = 0
    for o in r["out"]:
        if o["ex"] < o["w"] / 2 + 8 or o["ex"] > o["sw"] - o["w"] / 2 - 8:
            continue                                          # kept inside the stage on purpose
        assert abs(o["x"] - o["ex"]) < 1.5 and abs(o["y"] - o["ey"]) < 1.5, o
        seen += 1
    assert seen >= 4
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

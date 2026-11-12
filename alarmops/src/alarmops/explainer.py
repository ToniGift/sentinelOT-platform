"""Render the AlarmOps page from measured results (see scenarios.build_report).

interactive=False gives a static page (docs/explainer.html, no scripts).
interactive=True adds the lab and the live chart (served by web.py).
"""
from __future__ import annotations

from html import escape
from typing import Any

from .labpage import render_lab
from .theme import CSS

STEPS = [
    ("Plan", "Check the change is well-formed."),
    ("Review", "Replay hidden faults on the old and new limits. Compare."),
    ("Test", "Run the automatic tests."),
    ("Security", "Scan for passwords and keys saved in the code."),
    ("Compliance", "Write the change record and a parts list."),
    ("Staging", "Release to a practice environment."),
    ("Validate", "Check the practice release works."),
    ("Approval", "The one manual step. A named person says yes."),
    ("Monitor", "Watch alarm counts after release. Open an issue if they drift."),
]

WORDS = [
    ("Alarm limit", "The number at which the control system warns an operator, such as a tank being 80% full."),
    ("Fault", "Something going wrong in the process: a sudden spike, a slow drift, or a sensor stuck on one value."),
    ("Detection rate", "Of the faults we hid in the data, how many the alarms noticed."),
    ("False alarm", "An alarm that sounds when nothing is wrong. Too many and operators stop listening."),
    ("Deadband and delay", "Two settings that stop alarms from flickering: how far the value must recover, and how many readings in a row must break the limit."),
    ("Gate", "The pass or fail rule. A change that loses too much detection is blocked."),
]


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def chart_svg(rep: dict[str, Any]) -> str:
    """Tank level over time with the hidden faults. Faults the loosened limit (change A) would
    miss are hatched red; the lab redraws this live."""
    t, y = rep["series"]["t"], rep["series"]["tank_level"]
    n = max(t) or 1
    w, h, left, right, top, bottom = 960, 330, 52, 16, 16, 36
    ymax = 100.0
    sx = lambda v: left + (w - left - right) * v / n
    sy = lambda v: top + (h - top - bottom) * (1 - v / ymax)
    grid = "".join(
        f'<line class="gridline" x1="{left}" x2="{w - right}" y1="{sy(v):.1f}" y2="{sy(v):.1f}"/>'
        f'<text x="{left - 8}" y="{sy(v) + 4:.1f}" text-anchor="end">{v}%</text>' for v in range(0, 101, 20))
    xticks = "".join(
        f'<text x="{sx(v):.1f}" y="{h - 12}" text-anchor="middle">{v}</text>' for v in range(0, n + 1, 1000))
    pts = " ".join(f"{sx(t[i]):.1f},{sy(min(y[i], ymax)):.1f}" for i in range(0, len(t), 4))
    cur, a = rep["tank"]["high"], rep["scenarios"]["a"]
    missed = {m["fault_id"] for m in a["newly_missed"]}
    bands = "".join(
        f'<rect id="band-{escape(f["fault_id"])}" class="band {"missed" if f["fault_id"] in missed else "ok"}" '
        f'x="{sx(f["start"]):.1f}" y="{top}" width="{max(sx(f["end"]) - sx(f["start"]), 4):.1f}" '
        f'height="{h - top - bottom}"><title>{escape(f["type"])} fault {escape(f["fault_id"])}</title></rect>'
        for f in rep["tank_faults"])
    ya = sy(a["high"])
    return f"""<svg id="chart" class="chart" viewBox="0 0 {w} {h}" role="img"
 aria-label="Tank level over time. Shaded bands are hidden faults. Hatched red bands would be missed by a loosened limit."
 data-y-top="{top}" data-y-bottom="{h - bottom}" data-ymax="{ymax:g}">
<defs><pattern id="hatch" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
<line x1="0" y1="0" x2="0" y2="7" style="stroke:var(--red)" stroke-width="3"/></pattern></defs>
{grid}{xticks}{bands}
<polyline class="trace" points="{pts}"/>
<line class="lim-now" x1="{left}" x2="{w - right}" y1="{sy(cur):.1f}" y2="{sy(cur):.1f}"/>
<text class="lbl-now" x="{w - right - 6}" y="{sy(cur) + 16:.1f}" text-anchor="end">current high limit ({cur:g})</text>
<line id="limit-user" class="lim-user" x1="{left}" x2="{w - right}" y1="{ya:.1f}" y2="{ya:.1f}"/>
<text id="limit-user-label" class="lbl-user" x="{w - right - 6}" y="{ya - 6:.1f}" text-anchor="end">loosened limit, change A ({a['high']:g})</text>
<text x="{w - right}" y="{h - 12}" text-anchor="end" style="font-size:10px">time, in simulated readings</text>
</svg>"""


def sparkline(m: dict[str, Any], name: str) -> str:
    """Alarms per hour over the logged hours, the drift limit, and the recent window the monitor checks."""
    w, h, left, right, top, bottom = 560, 220, 40, 12, 14, 28
    vals = m["hourly"]
    ymax = max(max(vals), m["threshold"]) * 1.15 or 1
    sx = lambda i: left + (w - left - right) * i / (len(vals) - 1)
    sy = lambda v: h - bottom - (h - bottom - top) * v / ymax
    pts = " ".join(f"{sx(i):.1f},{sy(v):.1f}" for i, v in enumerate(vals))
    x0 = sx(len(vals) - m["recent_hours"])
    th = sy(m["threshold"])
    cls = "s drift" if m["drift"] else "s"
    ticks = "".join(
        f'<line class="gridline" x1="{left}" x2="{w - right}" y1="{sy(v):.1f}" y2="{sy(v):.1f}"/>'
        f'<text x="{left - 6}" y="{sy(v) + 3:.1f}" text-anchor="end">{v:g}</text>'
        for v in sorted({0, round(ymax / 2), round(ymax * 0.87)}) if v <= ymax)
    return f"""<svg class="spark" viewBox="0 0 {w} {h}" role="img" aria-label="Alarms per hour over {len(vals)} hours, {name} log">
{ticks}
<rect class="rc" x="{x0:.1f}" y="{top}" width="{w - right - x0:.1f}" height="{h - bottom - top}"/>
<line class="th" x1="{left}" x2="{w - right}" y1="{th:.1f}" y2="{th:.1f}"/>
<polyline class="{cls}" points="{pts}"/>
<text x="{left}" y="{h - 8}">0 h</text><text x="{w - right}" y="{h - 8}" text-anchor="end">{len(vals)} h</text>
<text x="{left + 6}" y="{th - 5:.1f}">drift limit {m['threshold']:.1f}/h</text></svg>"""


def monitor_panel(name: str, title: str, m: dict[str, Any], interactive: bool) -> str:
    """One log on the monitor screen. Interactive: starts unchecked and a button runs the monitor.
    Static: pre-filled with the measured values."""
    if interactive:
        cls, status, base, recent, limit = "monpanel", "NOT CHECKED", "-", "-", "-"
        button = f'<button class="chip" id="mon-run-{name}" type="button">Run the monitor</button>'
    else:
        cls = "monpanel " + ("bad" if m["drift"] else "good")
        status = "DRIFT DETECTED" if m["drift"] else "NORMAL"
        base, recent, limit = (f"{m['baseline_per_hour']:.2f} /h", f"{m['recent_per_hour']:.2f} /h",
                               f"{m['threshold']:.2f} /h")
        button = ""
    return f"""<div class="{cls}" id="mon-{name}">
<div class="monhead"><span class="lamp"></span><div><b>{escape(title)}</b><span class="monstatus" id="mon-{name}-status">{status}</span></div>{button}</div>
{sparkline(m, name)}
<dl class="readouts"><div><dt>Before release</dt><dd id="mon-{name}-base">{base}</dd></div>
<div><dt>Recent</dt><dd id="mon-{name}-recent">{recent}</dd></div>
<div><dt>Drift limit</dt><dd id="mon-{name}-limit">{limit}</dd></div></dl>
</div>"""


def _tile(kind: str, label: str, title: str, detail: str, href: str, load: str) -> str:
    return (f'<a class="tile {kind}" href="{href}" data-load="{load}"><span class="lamp"></span>'
            f'<span class="t1">{escape(label)}</span><span class="t2">{escape(title)}</span>'
            f'<span class="t3">{escape(detail)}</span></a>')


def render_explainer(rep: dict[str, Any], interactive: bool = False) -> str:
    base, gate = rep["baseline"], rep["gate"]
    a, c = rep["scenarios"]["a"], rep["scenarios"]["c"]
    try_href = "#try" if interactive else "#results"
    n_mon, n_res, n_lim = (4, 5, 6) if interactive else (3, 4, 5)

    tiles = (
        _tile("bad" if a["blocked"] else "good", "Change A / loosen a limit", "Blocked" if a["blocked"] else "Allowed",
              f"notices {a['faults_detected']} of {a['faults_total']} faults, was {base['faults_detected']}", try_href, "a")
        + _tile("bad", "Change B / password in code", "Blocked", "the secret scan stops it", try_href, "b")
        + _tile("bad" if c["blocked"] else "good", "Change C / safe tightening",
                "Blocked" if c["blocked"] else "Ready",
                f"notices {c['faults_detected']} of {c['faults_total']}; waits for a person", try_href, "c"))

    steps = "".join(
        f'<li class="{"human" if name == "Approval" else ""}"><b>{escape(name)}</b><span>{escape(text)}</span></li>'
        for name, text in STEPS)
    words = "".join(f"<div><dt>{escape(k)}</dt><dd>{escape(v)}</dd></div>" for k, v in WORDS)
    tag_rows = "".join(
        f"<tr><td>{escape(tag)}</td><td>{v['faults_detected']} / {v['faults_total']}</td><td>{v['false_alarms']}</td></tr>"
        for tag, v in rep["per_tag"].items())

    def result_cell(code: str, title: str, body: str, readout: str, small: str, stamp: str, kind: str) -> str:
        return (f'<div class="cell"><span class="id">CHANGE {code}</span><h3>{escape(title)}</h3><p class="small mute">{body}</p>'
                f'<div class="readout">{readout}<br><small>{small}</small></div>'
                f'<span class="stamp {kind}">{escape(stamp)}</span></div>')

    cells = (
        result_cell("A", "Loosen a limit",
                    f"The tank's \"too full\" alarm moves from {rep['tank']['high']:g}% up to {a['high']:g}%.",
                    f"{a['faults_detected']} of {a['faults_total']}",
                    f"faults noticed (before: {base['faults_detected']} of {base['faults_total']})",
                    "Blocked" if a["blocked"] else "Allowed", "bad" if a["blocked"] else "good")
        + result_cell("B", "A password in the code",
                      "Someone commits a key that unlocks a cloud account. The key in the demo is fake.",
                      "Not a limit change", "so there is no detection figure",
                      "Blocked by the secret scan", "bad")
        + result_cell("C", "A safe tightening",
                      f"The alarm moves from {rep['tank']['high']:g}% down to {c['high']:g}%, so it speaks up earlier.",
                      f"{c['faults_detected']} of {c['faults_total']}",
                      f"faults noticed, {c['false_alarm_count']} false alarms",
                      "Ready for a person" if not c["blocked"] else "Blocked", "good" if not c["blocked"] else "bad"))

    mon = rep["monitor"]
    nav_try = '<a href="#try">Try it</a>' if interactive else ""
    lab = render_lab(rep) if interactive else ""
    chart_note = ('<p class="hint" id="chart-note">Showing change A: the loosened limit would leave '
                  f'{len(a["newly_missed"])} tank faults unnoticed (hatched red). Run the lab below to try your own.</p>'
                  if interactive else
                  f'<p class="hint">Showing change A: the loosened limit would leave {len(a["newly_missed"])} tank faults unnoticed (hatched red).</p>')
    mon_diag = ('<pre class="term" id="mon-diag" aria-live="polite">Press a button on a log to run the monitor on it.</pre>'
                if interactive else "")
    cta_try = ('<a class="btn" href="#try">Try it yourself</a>' if interactive
               else '<a class="btn" href="#results">See the results</a>')

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AlarmOps: measure every alarm-limit change</title>
<meta name="description" content="A simulation that measures what a change to an industrial alarm limit would do before it ships.">
<style>{CSS}</style></head><body id="top">
<div class="stripe"></div>
<header class="nav"><div class="wrap">
<a class="brand" href="#top"><span class="glyph"><i></i><i></i><i></i><i></i></span>ALARMOPS</a>
<nav class="links" aria-label="Sections"><a href="#problem">Problem</a><a href="#how">How it works</a>{nav_try}<a href="#monitor">Monitor</a><a href="#results">Results</a><a href="#limits">Limits</a></nav>
<span class="simtag">SIMULATION</span>
</div></header>

<main>
<div class="herobg"><div class="wrap hero">
<div>
<p class="kicker">Alarm-limit change control</p>
<h1>Measure the change before it ships.</h1>
<p class="lead">AlarmOps checks every edit to a plant's alarm settings. It replays known faults against the new settings, shows what would be missed, and leaves the final yes to a person.</p>
<div class="cta">{cta_try}<a class="btn ghost" href="#how">How it works</a></div>
<p class="small mute">Everything here is simulated. No real plant is connected.</p>
</div>
<div class="panel" aria-label="Status of the three demo changes">
<div class="panelhead">Change status panel{" / click a tile" if interactive else ""}</div>
{tiles}
</div>
</div></div>

<section id="problem"><div class="wrap">
<div class="sectionhead"><p class="kicker">01 / The problem</p><h2>A loosened limit fails silently</h2></div>
<div class="two">
<div>
<p>In a factory, an <b>alarm limit</b> is the number at which the control system warns an operator. Over the years people edit these numbers.</p>
<p>Loosen a limit by mistake and a real problem can happen with <b>no warning at all</b>. Tighten it too far and operators drown in false alarms and start ignoring them.</p>
<div class="callout">Today these edits are mostly checked by eye. Nobody measures what they really do, and nobody watches the alarm rate afterwards.</div>
</div>
<div><p class="kicker" style="margin-bottom:0">Words used on this page</p><dl class="words">{words}</dl></div>
</div>
<figure style="margin-top:34px">
{chart_svg(rep)}
<figcaption class="legend"><span class="k-now">current high limit</span><span class="k-user">a limit that was loosened</span><span class="k-ok">hidden fault, noticed</span><span class="k-miss">hidden fault, missed</span></figcaption>
{chart_note}
</figure>
<p class="small mute">What you are looking at: a simulated tank level over time. We hid {base['faults_total']} faults in the data (this chart shows the tank's). The grey trace is the level, the bands are the faults. A limit set too high lets some faults pass unnoticed.</p>
</div></section>

<section id="how"><div class="wrap">
<div class="sectionhead"><p class="kicker">02 / How it works</p><h2>Nine automatic steps, one human</h2>
<p class="mute">Every proposed change runs this line. It stops at the first step that fails. Only the approval is manual.</p></div>
<ol class="rail">{steps}</ol>
</div></section>

{lab}

<section id="monitor"><div class="wrap">
<div class="sectionhead"><p class="kicker">0{n_mon} / After release</p><h2>The monitor screen</h2>
<p class="mute">Releasing a change is not the end. The monitor counts alarms per hour after the release and compares the recent hours with the quiet period before. If the rate climbs past the drift limit, it raises an issue with a diagnosis.</p></div>
<div class="two">
{monitor_panel('healthy', 'Healthy log', mon['healthy'], interactive)}
{monitor_panel('drift', 'Drifting log', mon['drift'], interactive)}
</div>
{mon_diag}
<p class="small mute">What you are looking at: alarms per hour over 72 simulated hours. The dashed line is the drift limit and the shaded strip is the recent window the monitor checks. A healthy line stays under the limit; a drifting one climbs through it.</p>
</div></section>

<section id="results"><div class="wrap">
<div class="sectionhead"><p class="kicker">0{n_res} / Results</p><h2>Measured, not claimed</h2>
<p class="mute">The figures come from replaying the simulated data on each version of the rules, every time this page is built. None are typed in by hand.</p></div>
<div class="grid3">{cells}</div>

<div style="margin-top:36px;max-width:760px"><h3>Baseline by tag</h3><table><tr><th>Tag</th><th>Faults noticed</th><th>False alarms</th></tr>{tag_rows}</table>
<p class="small mute">Baseline overall: {base['faults_detected']} of {base['faults_total']} noticed, {base['false_alarm_count']} false alarms.</p></div>

<details><summary>How the pass or fail is decided</summary>
<p>A change passes if it keeps at least {_pct(gate['min_detection_rate'])} detection, loses no more than {_pct(gate['max_detection_rate_drop'])} compared with the current rules,
causes at most {int(gate['max_false_alarms'])} false alarms, and adds at most {int(gate['max_false_alarm_increase'])}.
A fault counts as noticed when an alarm for its tag starts between the fault's start and {rep['meta']['detection_window_samples']} readings after its end.
These thresholds are choices for this demo, not an industry standard. Raw numbers: <a href="/api/replay"><code>/api/replay</code></a>.</p></details>
</div></section>

<section id="limits"><div class="wrap">
<div class="sectionhead"><p class="kicker">0{n_lim} / What this is not</p><h2>Honest limits</h2></div>
<div class="limits">
<div><b>A simulation</b>The sensor data is made up and the deployment is simulated. It is not connected to any real plant or equipment.</div>
<div><b>Not a certification</b>The mapping to ISA-18.2 and IEC 62443 in each change record is a reference mapping. It is not a certificate or a compliance claim.</div>
<div><b>Demo thresholds</b>The pass and fail numbers are policy choices made for this demo, not an industry standard.</div>
</div>
</div></section>
</main>

<footer><div class="wrap"><span>AlarmOps / MIT licence / (c) 2026 Anthony Afonughe</span><span>Simulation only. Built for the GitLab Transcend hackathon.</span></div></footer>
</body></html>
"""

"""HTML and JavaScript for the interactive lab section (served by web.py only)."""
from __future__ import annotations

from html import escape

HELP = {
    "tank_low_low": "Very low: the level is dangerously low (percent).",
    "tank_low": "Low: the level is getting low (percent).",
    "tank_high": "High: the level is getting too full (percent).",
    "tank_high_high": "Very high: the level is dangerously full (percent).",
    "deadband": "How far the level must come back before the alarm clears, so it does not flicker.",
    "delay_samples": "How many readings in a row must be past the limit before the alarm sounds.",
}


def render_lab(rep: dict) -> str:
    t, a, c = rep["tank"], rep["scenarios"]["a"], rep["scenarios"]["c"]

    def field(fid: str, label: str, value) -> str:
        v = escape(format(value, "g"))
        return (f'<label title="{escape(HELP[fid])}">{escape(label)}'
                f'<input id="{fid}" type="number" step="any" value="{v}" data-default="{v}"></label>')

    return f"""<section id="try">
<div class="wrap">
<div class="sectionhead"><p class="kicker">03 / Try it yourself</p><h2>Break an alarm limit. Watch it get caught.</h2>
<p class="mute">These buttons run the real AlarmOps code on the server, on the same simulated data. The black panel prints what the command line would print. The site runs only this fixed set of checks and stores nothing you type.</p></div>
<div class="lab" id="lab" data-a-high="{a['high']:g}" data-a-hh="{a['high_high']:g}" data-c-high="{c['high']:g}" data-c-hh="{c['high_high']:g}">
<div class="labsteps">
<div><b>STEP 1</b>Pick a ready-made change, or type your own limits for the tank.</div>
<div><b>STEP 2</b>Press <i>Run the checks</i>. The server replays the hidden faults on your limits.</div>
<div><b>STEP 3</b>Read the verdict and the pipeline lights. The chart above also updates.</div>
</div>
<div class="labbody">
<div class="labcol">
<div class="group">
<h3>Tank alarm limits</h3>
<div class="chips" role="group" aria-label="Ready-made changes">
<button class="chip" id="preset-a" type="button">Load change A: loosen</button>
<button class="chip" id="preset-c" type="button">Load change C: tighten</button>
<button class="chip" id="preset-reset" type="button">Reset</button>
</div>
<div class="fields">
{field('tank_low_low', 'very low', t['low_low'])}{field('tank_low', 'low', t['low'])}
{field('tank_high', 'high', t['high'])}{field('tank_high_high', 'very high', t['high_high'])}
{field('deadband', 'deadband', t['deadband'])}{field('delay_samples', 'delay (readings)', t['delay_samples'])}
</div>
<p class="hint">Limits go in order: very low, then low, then high, then very high. Hover a box for what it means.</p>
<div class="cta"><button class="btn" id="run-compare" type="button">Run the checks</button>
<button class="btn ghost" id="run-baseline" type="button">Replay the current limits</button></div>
<div class="verdict" id="verdict"><span class="lamp"></span><div id="banner" aria-live="polite">Waiting for a run.</div></div>
<dl class="readouts" id="lab-readouts" hidden>
<div><dt>Faults noticed</dt><dd id="ro-detect">-</dd></div>
<div><dt>False alarms</dt><dd id="ro-false">-</dd></div>
</dl>
<p class="hint" id="ro-help" hidden>A false alarm is an alarm that sounds when no hidden fault is happening. The numbers read: current limits, then your limits.</p>
<div class="pills" id="pills" aria-label="Pipeline stages"></div>
</div>

<div class="group">
<h3>Scan text for passwords and keys</h3>
<p class="small mute">This is change B. Paste a config snippet, or use the fake example key.</p>
<textarea id="scan-text" maxlength="4000" aria-label="Text to scan" placeholder="Paste text here. Nothing is stored or shown back."></textarea>
<div class="chips"><button class="chip" id="scan-example" type="button">Insert a fake example key</button>
<button class="btn" id="run-scan" type="button">Run the secret scan</button></div>
</div>
</div>

<div class="labout"><h3>What the command line would print</h3>
<pre class="term" id="term" aria-live="polite">Pick something above. Results appear here.</pre>
<p class="hint">Stages marked "GitLab only" are not run by this website; they run in the real pipeline.</p></div>
</div>
</div>
</div>
</section>
<script src="/lab.js" defer></script>
"""


LAB_JS = r"""
(function () {
  var $ = function (id) { return document.getElementById(id); };
  var lab = $("lab");
  if (!lab) { return; }
  var term = $("term"), banner = $("banner"), verdict = $("verdict"), pills = $("pills");
  var ids = ["tank_low_low", "tank_low", "tank_high", "tank_high_high", "deadband", "delay_samples"];
  var buttons = lab.querySelectorAll("button");

  function busy(on) { buttons.forEach(function (b) { b.disabled = on; }); }
  function show(text) { term.textContent = text; }
  function setVerdict(text, state) {
    banner.textContent = text;
    verdict.className = "verdict" + (state ? " " + state : "");
  }
  function showReadouts(on) { $("lab-readouts").hidden = !on; $("ro-help").hidden = !on; }
  function clearVerdict() { pills.textContent = ""; showReadouts(false); setVerdict("Waiting for a run.", ""); }
  // errors go next to the buttons (not only in the panel further down) so they are not missed
  function showError(message) {
    pills.textContent = ""; showReadouts(false);
    setVerdict("Cannot run this: " + message, "bad");
    show("error: " + message);
  }

  function call(url, opts) {
    busy(true);
    return fetch(url, opts).then(function (r) {
      return r.json().then(function (j) { if (!r.ok) { throw new Error(j.error || r.statusText); } return j; });
    }).catch(function (e) { showError(e.message); return null; })
      .then(function (j) { busy(false); return j; });
  }

  function query() {
    return ids.map(function (i) { return i + "=" + encodeURIComponent($(i).value); }).join("&");
  }

  function drawStages(stages) {
    pills.textContent = "";
    stages.forEach(function (s) {
      var p = document.createElement("span");
      p.className = "pill " + s.status;
      p.textContent = s.stage.replace("_", " ") + " - " + (s.status === "gitlab" ? "GitLab only" : s.status);
      p.title = s.job + ": " + s.detail;
      pills.appendChild(p);
    });
  }

  // the trend chart: move the "your limit" line and recolour the faults that would be missed
  function updateChart(r) {
    var chart = $("chart");
    if (!chart) { return; }
    var top = +chart.dataset.yTop, bottom = +chart.dataset.yBottom, ymax = +chart.dataset.ymax;
    var y = bottom - (bottom - top) * r.limits.high / ymax;
    var line = $("limit-user"), label = $("limit-user-label");
    line.setAttribute("y1", y); line.setAttribute("y2", y);
    label.setAttribute("y", y < top + 16 ? y + 15 : y - 6);
    label.textContent = "your high limit (" + r.limits.high + ")";
    Object.keys(r.tank_detected).forEach(function (id) {
      var b = $("band-" + id);
      if (b) { b.setAttribute("class", "band " + (r.tank_detected[id] ? "ok" : "missed")); }
    });
    var note = $("chart-note");
    if (note) {
      var n = r.newly_missed.length;
      note.textContent = n === 0 ? "With your limits, every tank fault in this chart is still noticed."
                                 : "With your limits, " + n + " tank fault" + (n === 1 ? "" : "s") + " would go unnoticed (hatched red).";
    }
  }

  function setLimits(high, hh) { $("tank_high").value = high; $("tank_high_high").value = hh; }

  $("preset-a").onclick = function () { setLimits(lab.dataset.aHigh, lab.dataset.aHh); };
  $("preset-c").onclick = function () { setLimits(lab.dataset.cHigh, lab.dataset.cHh); };
  $("preset-reset").onclick = function () {
    ids.forEach(function (i) { $(i).value = $(i).dataset["default"]; });
    clearVerdict(); show("Reset to the current limits.");
  };

  // a number box holding text reads as "" in the browser, so say so instead of silently using defaults
  function firstBadField() {
    for (var i = 0; i < ids.length; i++) {
      var el = $(ids[i]);
      if (el.value === "" || el.validity.badInput) { return el.parentNode.firstChild.textContent; }
    }
    return null;
  }

  $("run-compare").onclick = function () {
    var bad = firstBadField();
    if (bad) { showError(bad + " must be a number"); return; }
    call("/api/lab/compare?" + query()).then(function (r) {
      if (!r) { return; }
      show(r.output);
      setVerdict(r.passed ? "Passes the review gate. It would go on to a human approval."
                          : "Blocked. This change would not be merged.", r.passed ? "good" : "bad");
      drawStages(r.stages);
      updateChart(r);
      $("ro-detect").textContent = r.base.faults_detected + " of " + r.base.faults_total + "  →  " +
                                   r.head.faults_detected + " of " + r.head.faults_total;
      $("ro-false").textContent = r.base.false_alarm_count + "  →  " + r.head.false_alarm_count;
      $("ro-false").className = r.head.false_alarm_count > r.base.false_alarm_count ? "worse" : "";
      $("ro-detect").className = r.head.faults_detected < r.base.faults_detected ? "worse" : "";
      showReadouts(true);
    });
  };
  $("run-baseline").onclick = function () {
    call("/api/lab/baseline").then(function (r) { if (r) { clearVerdict(); show(r.output); } });
  };
  $("run-scan").onclick = function () {
    call("/api/lab/scan", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: $("scan-text").value })
    }).then(function (r) {
      if (!r) { return; }
      show(r.output);
      setVerdict(r.blocked ? "Blocked by the security check." : "Nothing suspicious found.", r.blocked ? "bad" : "good");
      pills.textContent = ""; showReadouts(false);
    });
  };
  $("scan-example").onclick = function () {
    // a FAKE key, assembled at run time so this file never contains a key-shaped string
    $("scan-text").value = "aws_access_key_id=" + "AKIA" + "ABCDEFGHIJKLMNOP" + "\nregion=eu-west-1\n";
  };
  // the monitor screen: run the monitor on a log and fill in that log's panel
  var monNames = ["healthy", "drift"];
  function monBusy(on) { monNames.forEach(function (n) { var b = $("mon-run-" + n); if (b) { b.disabled = on; } }); }
  monNames.forEach(function (name) {
    var btn = $("mon-run-" + name);
    if (!btn) { return; }
    btn.onclick = function () {
      monBusy(true);
      fetch("/api/lab/monitor?log=" + name).then(function (r) {
        return r.json().then(function (j) { if (!r.ok) { throw new Error(j.error || r.statusText); } return j; });
      }).then(function (r) {
        $("mon-" + name).className = "monpanel " + (r.drift ? "bad" : "good");
        $("mon-" + name + "-status").textContent = r.drift ? "DRIFT DETECTED" : "NORMAL";
        $("mon-" + name + "-base").textContent = r.baseline_per_hour.toFixed(2) + " /h";
        $("mon-" + name + "-recent").textContent = r.recent_per_hour.toFixed(2) + " /h";
        $("mon-" + name + "-limit").textContent = r.threshold.toFixed(2) + " /h";
        $("mon-diag").textContent = r.output;
      }).catch(function (e) { $("mon-diag").textContent = "error: " + e.message; })
        .then(function () { monBusy(false); });
    };
  });

  // the three status tiles at the top open the lab with that change already running
  document.querySelectorAll("a.tile[data-load]").forEach(function (a) {
    a.addEventListener("click", function (e) {
      e.preventDefault();
      $("try").scrollIntoView();
      var which = a.dataset.load;
      if (which === "a") { $("preset-a").click(); $("run-compare").click(); }
      else if (which === "c") { $("preset-c").click(); $("run-compare").click(); }
      else { $("scan-example").click(); $("run-scan").click(); }
    });
  });

  // highlight the navbar link of the section being read
  var links = {};
  document.querySelectorAll(".links a").forEach(function (a) { links[a.getAttribute("href").slice(1)] = a; });
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting && links[en.target.id]) {
          Object.keys(links).forEach(function (k) { links[k].classList.remove("on"); });
          links[en.target.id].classList.add("on");
        }
      });
    }, { rootMargin: "-35% 0px -60% 0px" });
    Object.keys(links).forEach(function (id) { var s = $(id); if (s) { io.observe(s); } });
  }
})();
"""

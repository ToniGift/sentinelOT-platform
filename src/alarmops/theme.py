"""Stylesheet for the AlarmOps page. Visual idea: a control-room annunciator panel.

Hard edges, thin rules, backlit status lamps, monospace readouts, a hazard-stripe accent.
System fonts only (the page's security policy allows no external resources).
"""

CSS = r"""
:root{
  --bg:#0e1113;--panel:#151a1e;--panel2:#1b2227;--line:#2c363d;--ink:#ebe8de;--mute:#9aa4aa;
  --amber:#ffb02e;--amber-ink:#1a1200;--red:#ff5a47;--green:#43d17a;--steel:#8fa7b8;--term-bg:#0a0c0d;--term-fg:#cfe8d5;
  --lamp-off:#252d33;--plot:#0b0e10;--grid:#1f282e;--band:#12171a;--blueprint:rgba(143,167,184,.07);
  --head:"Bahnschrift","DIN Alternate","Barlow Condensed","Roboto Condensed","Arial Narrow",system-ui,sans-serif;
  --body:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  --mono:"Cascadia Mono","SF Mono",Consolas,ui-monospace,monospace;
}
@media (prefers-color-scheme:light){:root{
  --bg:#ece8de;--panel:#f6f3ea;--panel2:#e3ddcd;--line:#c4bca8;--ink:#1d1f1e;--mute:#5a605d;
  --amber:#b86e00;--amber-ink:#fff7e6;--red:#c0301f;--green:#1b7a45;--steel:#3f586a;--term-bg:#1a1d1c;--term-fg:#d7ecdc;
  --lamp-off:#cfc8b6;--plot:#fbf9f3;--grid:#e1dac8;--band:#e5e0d2;--blueprint:rgba(63,88,106,.08);
}}
*{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:64px}
body{margin:0;background:var(--bg);color:var(--ink);font:17px/1.6 var(--body)}
a{color:inherit}
.stripe{height:6px;background:repeating-linear-gradient(135deg,var(--amber) 0 10px,#15181a 10px 20px)}
.wrap{width:100%;margin:0;padding:0 clamp(20px,4.5vw,88px)}
.prose{max-width:62ch}

/* navbar */
.nav{position:sticky;top:0;z-index:20;background:color-mix(in srgb,var(--bg) 92%,transparent);backdrop-filter:blur(6px);border-bottom:1px solid var(--line)}
.nav .wrap{display:flex;align-items:center;gap:18px;height:54px}
.brand{display:flex;align-items:center;gap:10px;font:700 1.05rem/1 var(--head);letter-spacing:.14em;text-decoration:none;white-space:nowrap}
.glyph{width:18px;height:18px;border:2px solid var(--amber);display:grid;grid-template-columns:1fr 1fr;gap:2px;padding:2px}
.glyph i{background:var(--amber)}.glyph i:nth-child(2){background:var(--red)}.glyph i:nth-child(3){background:var(--green)}.glyph i:nth-child(4){background:var(--lamp-off)}
.links{display:flex;gap:2px;margin-left:8px;overflow-x:auto;scrollbar-width:none;flex:1}
.links::-webkit-scrollbar{display:none}
.links a{font:600 .78rem/1 var(--head);letter-spacing:.12em;text-transform:uppercase;text-decoration:none;color:var(--mute);padding:10px 12px;border-bottom:2px solid transparent;white-space:nowrap}
.links a:hover{color:var(--ink)}.links a.on{color:var(--ink);border-bottom-color:var(--amber)}
.simtag{font:700 .7rem/1 var(--mono);letter-spacing:.12em;padding:6px 8px;border:1px solid var(--amber);color:var(--amber);white-space:nowrap}
@media (max-width:640px){.simtag{display:none}.nav .wrap{gap:8px}}

/* type */
.kicker{font:600 .78rem/1 var(--mono);letter-spacing:.16em;text-transform:uppercase;color:var(--amber);margin:0 0 10px}
h1,h2,h3{font-family:var(--head);font-weight:700;letter-spacing:.01em;line-height:1.05;margin:0}
h1{font-size:clamp(2.4rem,6.4vw,6rem);text-transform:uppercase}
h2{font-size:clamp(1.8rem,4vw,3.2rem);text-transform:uppercase}
h3{font-size:1.15rem;letter-spacing:.04em;text-transform:uppercase}
p{margin:.6em 0}.lead{font-size:clamp(1.15rem,1.6vw,1.45rem);color:var(--mute);max-width:46ch}
.mute{color:var(--mute)}.small{font-size:.88rem}
section{padding:72px 0 64px;border-top:1px solid var(--line)}
section:nth-of-type(even){background:var(--band)}
.sectionhead{display:grid;grid-template-columns:1fr;gap:6px;margin-bottom:22px;max-width:62ch}

/* hero */
.herobg{background:linear-gradient(var(--blueprint) 1px,transparent 1px) 0 0/48px 48px,linear-gradient(90deg,var(--blueprint) 1px,transparent 1px) 0 0/48px 48px}
.hero{display:grid;grid-template-columns:1.1fr 1fr;gap:clamp(28px,5vw,96px);align-items:center;padding-top:clamp(44px,8vw,110px);padding-bottom:clamp(40px,6vw,90px)}
@media (max-width:860px){.hero{grid-template-columns:1fr;gap:28px}}
@media (min-width:861px){.hero{padding-top:clamp(22px,4vw,55px)}}
.cta{display:flex;flex-wrap:wrap;gap:10px;margin-top:22px}
.btn{font:700 .82rem/1 var(--head);letter-spacing:.12em;text-transform:uppercase;text-decoration:none;display:inline-block;
  padding:13px 18px;border:1px solid var(--amber);background:var(--amber);color:var(--amber-ink);cursor:pointer;border-radius:2px}
.btn.ghost{background:transparent;color:var(--amber)}
.btn:hover{filter:brightness(1.1)}.btn:disabled{opacity:.45;cursor:wait}
:focus-visible{outline:2px solid var(--amber);outline-offset:2px}

/* annunciator panel */
.panel{border:2px solid var(--line);background:var(--panel);padding:14px;position:relative}
.panel::before,.panel::after{content:"";position:absolute;width:6px;height:6px;border-radius:50%;background:var(--line);top:5px}
.panel::before{left:5px}.panel::after{right:5px}
.panelhead{font:600 .7rem/1 var(--mono);letter-spacing:.16em;color:var(--mute);text-transform:uppercase;margin:2px 14px 12px}
.tile{display:grid;grid-template-columns:auto 1fr;gap:4px 14px;align-items:center;text-decoration:none;
  background:var(--plot);border:1px solid var(--line);padding:14px 16px;margin-bottom:10px;position:relative}
.tile:last-child{margin-bottom:0}
.tile:hover{border-color:var(--steel)}
.lamp{grid-row:1/3;width:44px;height:44px;border:2px solid var(--line);background:var(--lamp-off);position:relative}
.tile.bad .lamp{background:var(--red);box-shadow:0 0 18px var(--red);border-color:var(--red)}
.tile.good .lamp{background:var(--green);box-shadow:0 0 18px var(--green);border-color:var(--green)}
@media (prefers-reduced-motion:no-preference){.tile.bad .lamp{animation:blink 2.4s ease-in-out infinite}}
@keyframes blink{50%{opacity:.55}}
.tile .t1{font:700 .72rem/1 var(--mono);letter-spacing:.14em;color:var(--mute);text-transform:uppercase}
.tile .t2{font:700 1.35rem/1.1 var(--head);letter-spacing:.06em;text-transform:uppercase}
.tile.bad .t2{color:var(--red)}.tile.good .t2{color:var(--green)}
.tile .t3{grid-column:2;font:.84rem/1.3 var(--mono);color:var(--mute)}

/* problem + words */
.two{display:grid;grid-template-columns:1fr 1fr;gap:clamp(28px,4vw,80px)}
@media (max-width:860px){.two{grid-template-columns:1fr}}
.callout{border-left:4px solid var(--amber);background:var(--panel);padding:14px 18px;margin:18px 0}
dl.words{margin:0;display:grid;gap:0}
dl.words div{display:grid;grid-template-columns:150px 1fr;gap:14px;padding:10px 0;border-top:1px solid var(--line)}
dl.words dt{font:700 .78rem/1.5 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--amber)}
dl.words dd{margin:0;font-size:.95rem}
@media (max-width:520px){dl.words div{grid-template-columns:1fr;gap:2px}}

/* chart */
figure{margin:0}
.chart{width:100%;height:auto;max-height:620px;display:block;background:var(--plot);border:1px solid var(--line)}
.chart text{font-family:var(--mono);font-size:11px;fill:var(--mute)}
.chart .gridline{stroke:var(--grid);stroke-width:1}
.chart .trace{fill:none;stroke:var(--steel);stroke-width:1.1}
.chart .band.ok{fill:var(--steel);opacity:.22}
.chart .band.missed{fill:url(#hatch);opacity:1;stroke:var(--red);stroke-width:1}
.chart .lim-now{stroke:var(--amber);stroke-width:2}
.chart .lim-user{stroke:var(--red);stroke-width:2;stroke-dasharray:7 5}
.chart .lbl-now{fill:var(--amber)}.chart .lbl-user{fill:var(--red)}
.legend{display:flex;flex-wrap:wrap;gap:6px 20px;font:.8rem/1.3 var(--mono);color:var(--mute);margin-top:10px}
.legend span::before{content:"";display:inline-block;width:14px;height:10px;margin-right:7px;vertical-align:-1px}
.legend .k-now::before{background:var(--amber)}.legend .k-user::before{background:var(--red)}
.legend .k-ok::before{background:var(--steel);opacity:.5}.legend .k-miss::before{background:repeating-linear-gradient(135deg,var(--red) 0 2px,transparent 2px 5px);border:1px solid var(--red)}

/* how it works: the rail */
ol.rail{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,200px),1fr));gap:0;counter-reset:r;border-top:1px solid var(--line);border-left:1px solid var(--line)}
@media (min-width:1500px){ol.rail{grid-template-columns:repeat(9,1fr)}}
ol.rail li{counter-increment:r;border-right:1px solid var(--line);border-bottom:1px solid var(--line);padding:16px 16px 18px;position:relative;background:var(--panel)}
ol.rail li::before{content:counter(r,decimal-leading-zero);font:700 .75rem/1 var(--mono);color:var(--amber);letter-spacing:.1em}
ol.rail b{display:block;font:700 1.02rem/1.2 var(--head);letter-spacing:.06em;text-transform:uppercase;margin:8px 0 6px}
ol.rail span{font-size:.9rem;color:var(--mute);display:block}
ol.rail li.human{background:var(--amber);color:var(--amber-ink)}
ol.rail li.human::before,ol.rail li.human span{color:var(--amber-ink)}
ol.rail li.human::after{content:"A PERSON DECIDES";position:absolute;top:14px;right:12px;font:700 .62rem/1 var(--mono);letter-spacing:.12em}

/* the lab */
.lab{border:2px solid var(--line);background:var(--panel)}
.labsteps{display:grid;grid-template-columns:repeat(3,1fr);border-bottom:1px solid var(--line)}
@media (max-width:700px){.labsteps{grid-template-columns:1fr}}
.labsteps div{padding:12px 16px;font-size:.92rem;border-right:1px solid var(--line)}
.labsteps div:last-child{border-right:0}
.labsteps b{font:700 .75rem/1 var(--mono);letter-spacing:.12em;color:var(--amber);display:block;margin-bottom:4px}
.labbody{padding:clamp(16px,2.4vw,34px);display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);gap:clamp(24px,3vw,56px);align-items:start}
.labcol{display:grid;gap:30px}.labout{position:sticky;top:76px}
@media (max-width:1000px){.labbody{grid-template-columns:1fr}.labout{position:static}}
.group h3{margin-bottom:4px}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}
.chip{font:700 .78rem/1 var(--head);letter-spacing:.1em;text-transform:uppercase;padding:10px 14px;background:transparent;color:var(--ink);
  border:1px solid var(--steel);cursor:pointer;border-radius:2px}
.chip:hover{border-color:var(--amber);color:var(--amber)}
.chip:disabled{opacity:.45;cursor:wait}
.fields{display:grid;grid-template-columns:repeat(auto-fit,minmax(118px,1fr));gap:10px;margin:12px 0}
.fields label{display:flex;flex-direction:column;gap:5px;font:600 .72rem/1.2 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--mute)}
.fields input,textarea{font:1rem/1.3 var(--mono);color:var(--ink);background:var(--plot);border:1px solid var(--line);padding:9px 10px;width:100%;border-radius:2px}
.fields input:focus,textarea:focus{border-color:var(--amber);outline:none}
textarea{min-height:76px;resize:vertical;font-size:.9rem}
.verdict{display:flex;align-items:center;gap:14px;min-height:56px;padding:10px 16px;border:1px solid var(--line);background:var(--plot);margin-top:14px}
.verdict .lamp{width:26px;height:26px;grid-row:auto;flex:none}
.verdict.bad .lamp{background:var(--red);box-shadow:0 0 14px var(--red);border-color:var(--red)}
.verdict.good .lamp{background:var(--green);box-shadow:0 0 14px var(--green);border-color:var(--green)}
#banner{font:700 1.02rem/1.3 var(--head);letter-spacing:.05em;text-transform:uppercase}
.verdict.bad #banner{color:var(--red)}.verdict.good #banner{color:var(--green)}
.pills{display:flex;flex-wrap:wrap;gap:0;margin-top:12px;border-top:1px solid var(--line);border-left:1px solid var(--line)}
.pill{font:600 .7rem/1.2 var(--mono);letter-spacing:.06em;text-transform:uppercase;padding:9px 11px;border-right:1px solid var(--line);border-bottom:1px solid var(--line);
  color:var(--mute);border-top:3px solid var(--lamp-off);background:var(--plot)}
.pill.pass{border-top-color:var(--green);color:var(--ink)}.pill.fail{border-top-color:var(--red);color:var(--red)}
.pill.manual{border-top-color:var(--amber);color:var(--amber)}.pill.skipped{opacity:.5}
pre.term{background:var(--term-bg);color:var(--term-fg);padding:14px 16px;overflow:auto;font:13px/1.5 var(--mono);min-height:260px;max-height:70vh;white-space:pre-wrap;margin:12px 0 0;border:1px solid var(--line)}
.hint{font-size:.85rem;color:var(--mute);margin:8px 0 0}

/* results */
.grid3{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:0;border-top:1px solid var(--line);border-left:1px solid var(--line)}
.cell{padding:20px;border-right:1px solid var(--line);border-bottom:1px solid var(--line);background:var(--panel)}
.cell .id{font:700 .72rem/1 var(--mono);letter-spacing:.14em;color:var(--amber)}
.cell h3{margin:8px 0 6px}
.readout{font:700 2.1rem/1.1 var(--mono);margin:12px 0 2px}
.readout small{font-size:.8rem;font-weight:400;color:var(--mute);letter-spacing:.04em}
.stamp{display:inline-block;font:700 .78rem/1 var(--head);letter-spacing:.14em;text-transform:uppercase;padding:7px 10px;border:2px solid;margin-top:12px;transform:rotate(-2deg)}
.stamp.bad{color:var(--red);border-color:var(--red)}.stamp.good{color:var(--green);border-color:var(--green)}
table{border-collapse:collapse;width:100%;font:.9rem/1.4 var(--mono)}
th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left}
th{font-size:.72rem;letter-spacing:.1em;text-transform:uppercase;color:var(--mute)}
.spark{width:100%;height:auto;display:block;background:var(--plot);border:1px solid var(--line)}
.spark .s{fill:none;stroke:var(--steel);stroke-width:1.8}.spark .s.drift{stroke:var(--red);stroke-width:2.2}
.spark .th{stroke:var(--amber);stroke-width:1.2;stroke-dasharray:5 4}.spark .rc{fill:var(--amber);opacity:.14}
.spark .gridline{stroke:var(--grid);stroke-width:1}
.spark text{font:10px var(--mono);fill:var(--mute)}
/* monitor screen */
.monpanel{border:2px solid var(--line);background:var(--panel);padding:14px}
.monhead{display:flex;align-items:center;gap:14px;margin-bottom:12px;flex-wrap:wrap}
.monhead>div{flex:1;min-width:140px}
.monhead b{display:block;font:700 1.05rem/1.2 var(--head);letter-spacing:.08em;text-transform:uppercase}
.monstatus{font:700 .78rem/1.3 var(--mono);letter-spacing:.12em;color:var(--mute)}
.monpanel .lamp{width:26px;height:26px;grid-row:auto;flex:none}
.monpanel.bad{border-color:var(--red)}.monpanel.bad .lamp{background:var(--red);box-shadow:0 0 14px var(--red);border-color:var(--red)}.monpanel.bad .monstatus{color:var(--red)}
.monpanel.good{border-color:var(--green)}.monpanel.good .lamp{background:var(--green);box-shadow:0 0 14px var(--green);border-color:var(--green)}.monpanel.good .monstatus{color:var(--green)}
dl.readouts{display:grid;grid-template-columns:repeat(3,1fr);margin:12px 0 0;border-top:1px solid var(--line)}
dl.readouts div{padding:10px 12px 0 0}
dl.readouts dt{font:600 .68rem/1.2 var(--mono);letter-spacing:.1em;text-transform:uppercase;color:var(--mute)}
dl.readouts dd{margin:4px 0 0;font:700 1.35rem/1.1 var(--mono)}
dl.readouts dd.worse{color:var(--red)}
dl.readouts[hidden],.hint[hidden]{display:none}
#mon-diag{margin:18px 0 6px;min-height:90px}
details{border:1px solid var(--line);background:var(--panel);padding:12px 16px;margin-top:14px}
summary{cursor:pointer;font:700 .8rem/1.2 var(--head);letter-spacing:.1em;text-transform:uppercase}

/* about */
.limits{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:0;border-top:1px solid var(--line);border-left:1px solid var(--line)}
.limits div{padding:18px;border-right:1px solid var(--line);border-bottom:1px solid var(--line);background:var(--panel)}
.limits b{font:700 .78rem/1 var(--mono);letter-spacing:.12em;text-transform:uppercase;color:var(--amber);display:block;margin-bottom:8px}
footer{margin-top:0;border-top:1px solid var(--line);padding:26px 0 48px;font:.82rem/1.6 var(--mono);color:var(--mute)}
footer .wrap{display:flex;flex-wrap:wrap;gap:8px 28px;justify-content:space-between}
code{font-family:var(--mono);font-size:.9em}
@media print{.nav,.stripe{display:none}}
"""

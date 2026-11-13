"""Contrast check for the colours of static/sentinelot.html, light and dark.

Reads the colour tokens from the page's own CSS, so it fails if someone changes a colour
to one that is hard to read. Text needs 4.5:1 (WCAG AA); lines and outlines need 3:1.
Run it on its own to print the table:  python tests/test_palette_contrast.py
"""
import re
from pathlib import Path

import pytest

CSS = (Path(__file__).resolve().parents[1] / "static" / "sentinelot.html").read_text(encoding="utf-8")


def tokens(block):
    return dict(re.findall(r"(--[a-z-]+):\s*(#[0-9A-Fa-f]{6})", block))


LIGHT = tokens(CSS[CSS.index(":root{"):CSS.index("@media (prefers-color-scheme: dark)")])
_d = CSS.index(':root[data-theme="dark"]{')
DARK = tokens(CSS[_d:CSS.index("}", _d)])
_m = CSS.index(':root:not([data-theme="light"]){')
DARK_MEDIA = tokens(CSS[_m:CSS.index("}", _m)])

# (what it is, foreground token, background token, ratio needed)
PAIRS = [
    ("text on the page", "--ink", "--bg", 4.5),
    ("text on a panel", "--ink", "--panel", 4.5),
    ("text in a well", "--ink", "--well", 4.5),
    ("muted text on the page", "--mute", "--bg", 4.5),
    ("muted text on a panel", "--mute", "--panel", 4.5),
    ("muted text in a well", "--mute", "--well", 4.5),
    ("value text on the page", "--live", "--bg", 4.5),
    ("value text in a well", "--live", "--well", 4.5),
    ("alarm text on a panel", "--alarm", "--panel", 4.5),
    ("alarm text in a well", "--alarm", "--well", 4.5),
    ("alarm value on the alarm tint", "--alarm", "--alarm-tint", 4.5),
    ("text on the alarm tint", "--ink", "--alarm-tint", 4.5),
    ("alarm window, filled: text on alarm", "--on-alarm", "--alarm", 4.5),
    ("alarm window, flash-off phase: alarm text on panel", "--alarm", "--panel", 4.5),
    ("warning window, filled: text on amber", "--on-warn", "--warn", 4.5),
    ("warning window, flash-off phase: text on panel", "--ink", "--panel", 4.5),
    ("first-out flag on an alarm window", "--alarm", "--on-alarm", 4.5),
    ("pressed tab and selected plate: page on ink", "--bg", "--ink", 4.5),
    ("pass badge: page on value colour", "--bg", "--live", 4.5),
    ("recorded badge: page on muted", "--bg", "--mute", 4.5),
    ("strong rules against the page (not text)", "--rule", "--bg", 3.0),
    ("floor hatching against the page (not text)", "--slab", "--bg", 3.0),
    ("equipment outlines against the page (not text)", "--edge", "--bg", 3.0),
    ("equipment outlines against their fill (not text)", "--edge", "--box", 3.0),
]


def _lin(c):
    c /= 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(h):
    r, g, b = (int(h[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def ratio(a, b):
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


CASES = [(mode, *p) for mode in ("light", "dark") for p in PAIRS]


@pytest.mark.parametrize("mode,name,fg,bg,need", CASES, ids=[f"{c[0]}: {c[1]}" for c in CASES])
def test_contrast(mode, name, fg, bg, need):
    t = LIGHT if mode == "light" else DARK
    assert ratio(t[fg], t[bg]) >= need, f"{mode}: {name}: {t[fg]} on {t[bg]} is {ratio(t[fg], t[bg]):.2f}:1"


def test_both_dark_blocks_hold_the_same_colours():
    assert DARK == DARK_MEDIA


if __name__ == "__main__":
    bad = 0
    for mode, t in (("LIGHT", LIGHT), ("DARK", DARK)):
        print(f"== {mode} ==")
        for name, fg, bg, need in PAIRS:
            r = ratio(t[fg], t[bg])
            ok = r >= need
            bad += not ok
            print(f"  {'PASS' if ok else 'FAIL'} {r:5.2f}:1 (need {need})  {name}  [{t[fg]} on {t[bg]}]")
    print("failures:", bad)

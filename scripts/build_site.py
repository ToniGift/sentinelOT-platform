"""Build the static showcase: copy static/sentinelot.html to site/index.html.

Render publishes the site/ folder as a static site. Only the showcase page goes there.
static/index.html is the triage interface, which needs the platform server and breaks without
one, so it is deliberately not copied.

Run this after every change to static/sentinelot.html, then commit site/index.html:

    python scripts/build_site.py

tests/test_site.py fails if site/index.html differs from static/sentinelot.html.
"""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "static" / "sentinelot.html"
DEST = ROOT / "site" / "index.html"


def build() -> Path:
    DEST.parent.mkdir(exist_ok=True)
    shutil.copyfile(SRC, DEST)          # a byte-for-byte copy: no rewriting, nothing to drift
    return DEST


if __name__ == "__main__":
    print("wrote", build().relative_to(ROOT))

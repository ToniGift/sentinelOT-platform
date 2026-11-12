"""Shared helpers for AlarmOps scripts."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def git_show(ref: str, path: str) -> str:
    """Return the contents of `path` at git ref `ref`."""
    proc = subprocess.run(["git", "show", f"{ref}:{path}"], capture_output=True,
                          text=True, cwd=ROOT)
    if proc.returncode != 0:
        raise FileNotFoundError(f"cannot read {path} at {ref}: {proc.stderr.strip()}")
    return proc.stdout

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("secret_guard", ROOT / "scripts" / "secret_guard.py")
sg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sg)


def _scan_text(tmp_path, monkeypatch, name, text):
    monkeypatch.setattr(sg, "ROOT", tmp_path)
    (tmp_path / name).write_text(text)
    return sg.scan([name])


def test_detects_fake_aws_key(tmp_path, monkeypatch):
    fake = "AKIA" + "ABCDEFGHIJKLMNOP"      # built at runtime so this file stays clean
    assert _scan_text(tmp_path, monkeypatch, "c.txt", f"key={fake}\n")


def test_detects_hardcoded_password(tmp_path, monkeypatch):
    assert _scan_text(tmp_path, monkeypatch, "c.py", 'password = "hunter2hunter2"\n')


def test_clean_and_allowlisted_lines_pass(tmp_path, monkeypatch):
    assert _scan_text(tmp_path, monkeypatch, "ok.yaml", "high: 80\ntoken_limit: 5\n") == []
    line = 'password = "hunter2hunter2"  # alarmops: allow-secret\n'
    assert _scan_text(tmp_path, monkeypatch, "al.py", line) == []

"""Shared test constants.

Tests must NOT depend on the live alarms.yaml (it changes with every alarm-limit
merge request). They use a frozen copy of the original baseline instead.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"
BASELINE_RULES = FIXTURES / "baseline_alarms.yaml"
BASELINE_REPORT = FIXTURES / "baseline_report.json"

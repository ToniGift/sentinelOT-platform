"""Alarm rules: loading and validation of alarms.yaml."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import yaml

LIMIT_KEYS = ("low_low", "low", "high", "high_high")


class RulesError(ValueError):
    """Raised when a rules file is malformed or physically inconsistent."""


@dataclass(frozen=True)
class TagRules:
    tag: str
    low_low: float
    low: float
    high: float
    high_high: float
    deadband: float = 0.0
    delay_samples: int = 1
    unit: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_rules(data: Any) -> dict[str, TagRules]:
    if not isinstance(data, dict) or "tags" not in data or not isinstance(data["tags"], dict):
        raise RulesError("rules file must contain a top-level 'tags' mapping")
    rules: dict[str, TagRules] = {}
    for tag, cfg in data["tags"].items():
        if not isinstance(cfg, dict):
            raise RulesError(f"tag '{tag}': expected a mapping")
        missing = [k for k in LIMIT_KEYS if k not in cfg]
        if missing:
            raise RulesError(f"tag '{tag}': missing limits {missing}")
        try:
            limits = {k: float(cfg[k]) for k in LIMIT_KEYS}
            deadband = float(cfg.get("deadband", 0.0))
            delay = int(cfg.get("delay_samples", 1))
        except (TypeError, ValueError) as exc:
            raise RulesError(f"tag '{tag}': non-numeric value ({exc})") from exc
        if not (limits["low_low"] < limits["low"] < limits["high"] < limits["high_high"]):
            raise RulesError(f"tag '{tag}': limits must satisfy low_low < low < high < high_high")
        if deadband < 0:
            raise RulesError(f"tag '{tag}': deadband must be >= 0")
        if delay < 1:
            raise RulesError(f"tag '{tag}': delay_samples must be >= 1")
        rules[str(tag)] = TagRules(
            tag=str(tag), deadband=deadband, delay_samples=delay,
            unit=str(cfg.get("unit", "")), **limits,
        )
    if not rules:
        raise RulesError("rules file defines no tags")
    return rules


def load_rules_text(text: str) -> dict[str, TagRules]:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise RulesError(f"invalid YAML: {exc}") from exc
    return parse_rules(data)


def load_rules(path: str | Path) -> dict[str, TagRules]:
    return load_rules_text(Path(path).read_text(encoding="utf-8"))

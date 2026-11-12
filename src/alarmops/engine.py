"""Alarm engine: per-tag state machine with deadband and on-delay."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from .rules import TagRules

# Severity rank: used to decide whether a change needs confirmation (raise)
# or is immediate (clear / de-escalate).
RANK = {"normal": 0, "low": 1, "high": 1, "low_low": 2, "high_high": 2}


@dataclass(frozen=True)
class AlarmEvent:
    tag: str
    t: int
    level: str
    value: float


class TagAlarmState:
    """Streaming alarm state for one tag.

    * An alarm is raised only after the new level persists for
      ``delay_samples`` consecutive samples (on-delay).
    * Clearing is immediate, but only once the value is back inside the limit
      by ``deadband`` (hysteresis), which prevents chattering.
    * An event is emitted when an alarm is raised or escalated, not while it
      stays active.
    """

    def __init__(self, rules: TagRules) -> None:
        self.rules = rules
        self.state = "normal"
        self._pending: Optional[str] = None
        self._count = 0

    def _raw_level(self, v: float) -> str:
        r = self.rules
        if v >= r.high_high:
            return "high_high"
        if v >= r.high:
            return "high"
        if v <= r.low_low:
            return "low_low"
        if v <= r.low:
            return "low"
        return "normal"

    def _within_deadband_of(self, level: str, v: float) -> bool:
        r = self.rules
        db = r.deadband
        if level == "high_high":
            return v >= r.high_high - db
        if level == "high":
            return v >= r.high - db
        if level == "low_low":
            return v <= r.low_low + db
        if level == "low":
            return v <= r.low + db
        return False

    def _candidate(self, v: float) -> str:
        cand = self._raw_level(v)
        s = self.state
        if s != "normal" and RANK[cand] < RANK[s]:
            # Hysteresis: stay in the current state until clear of the deadband.
            if self._within_deadband_of(s, v):
                return s
            # De-escalation from a *_high state to its lower-severity partner.
            if s == "high_high" and self._within_deadband_of("high", v):
                return "high"
            if s == "low_low" and self._within_deadband_of("low", v):
                return "low"
        return cand

    def update(self, t: int, v: float) -> Optional[AlarmEvent]:
        cand = self._candidate(v)
        if cand == self.state:
            self._pending, self._count = None, 0
            return None
        if cand == "normal" or RANK[cand] < RANK[self.state]:
            self.state = cand
            self._pending, self._count = None, 0
            return None
        # Raise or escalate: needs delay_samples consecutive confirmations.
        if cand == self._pending:
            self._count += 1
        else:
            self._pending, self._count = cand, 1
        if self._count >= self.rules.delay_samples:
            self.state = cand
            self._pending, self._count = None, 0
            return AlarmEvent(self.rules.tag, t, cand, v)
        return None


def evaluate_series(
    rules: TagRules, times: Sequence[int], values: Iterable[float]
) -> list[AlarmEvent]:
    state = TagAlarmState(rules)
    events: list[AlarmEvent] = []
    for t, v in zip(times, values):
        ev = state.update(t, v)
        if ev is not None:
            events.append(ev)
    return events

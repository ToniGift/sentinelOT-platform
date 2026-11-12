from alarmops.engine import TagAlarmState, evaluate_series
from alarmops.rules import TagRules


def rules(**over):
    d = dict(tag="x", low_low=10, low=20, high=80, high_high=90, deadband=2, delay_samples=3)
    d.update(over)
    return TagRules(**d)


def run(r, values):
    return evaluate_series(r, list(range(len(values))), values)


def test_no_alarm_in_normal_band():
    assert run(rules(), [50] * 20) == []


def test_on_delay_requires_consecutive_samples():
    # Two samples above 'high' is not enough for delay_samples=3.
    assert run(rules(), [50, 85, 85, 50, 50]) == []
    ev = run(rules(), [50, 85, 85, 85, 85])
    assert len(ev) == 1 and ev[0].level == "high" and ev[0].t == 3


def test_event_only_on_raise_not_while_active():
    assert len(run(rules(), [85] * 30)) == 1


def test_deadband_prevents_chatter():
    # Dips to 79 (inside the 2-unit deadband) must not clear/re-raise the alarm.
    ev = run(rules(delay_samples=1), [85, 79, 85, 79, 85])
    assert len(ev) == 1
    # Dropping clear of the deadband (<78) then returning raises a second alarm.
    ev = run(rules(delay_samples=1), [85, 70, 85])
    assert len(ev) == 2


def test_escalation_high_to_high_high():
    ev = run(rules(delay_samples=1), [85, 95])
    assert [e.level for e in ev] == ["high", "high_high"]


def test_deescalation_is_silent():
    ev = run(rules(delay_samples=1), [95, 85])
    assert [e.level for e in ev] == ["high_high"]


def test_low_side_alarms():
    ev = run(rules(delay_samples=1), [50, 15, 5])
    assert [e.level for e in ev] == ["low", "low_low"]


def test_widened_limit_misses_what_baseline_catches():
    values = [50] * 5 + [84] * 6 + [50] * 5
    assert len(run(rules(high=80), values)) == 1
    assert run(rules(high=88), values) == []


def test_streaming_state_matches_series():
    r = rules()
    st = TagAlarmState(r)
    vals = [50, 85, 85, 85, 95, 95, 95, 50]
    streamed = [e for t, v in enumerate(vals) if (e := st.update(t, v))]
    assert streamed == run(r, vals)

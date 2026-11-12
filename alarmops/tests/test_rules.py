import pytest
from conftest import BASELINE_RULES, ROOT
from alarmops.rules import RulesError, load_rules, load_rules_text, parse_rules


def _tag(**over):
    base = dict(low_low=10, low=20, high=80, high_high=90, deadband=1, delay_samples=2)
    base.update(over)
    return {"tags": {"t1": base}}


def test_live_rules_file_is_valid():
    # Structure only: the live file legitimately changes with each limit change.
    rules = load_rules(ROOT / "alarms.yaml")
    assert {"tank_level", "pump_pressure", "flow_rate"} <= set(rules)


def test_frozen_baseline_values():
    assert load_rules(BASELINE_RULES)["tank_level"].high == 80.0


def test_valid_rules_parse():
    r = parse_rules(_tag())["t1"]
    assert (r.low_low, r.low, r.high, r.high_high) == (10, 20, 80, 90)


@pytest.mark.parametrize("over", [
    dict(high=95),            # high > high_high
    dict(low=5),              # low < low_low
    dict(deadband=-1),
    dict(delay_samples=0),
])
def test_invalid_rules_rejected(over):
    with pytest.raises(RulesError):
        parse_rules(_tag(**over))


def test_missing_limit_and_bad_shape():
    cfg = _tag()
    del cfg["tags"]["t1"]["high"]
    with pytest.raises(RulesError):
        parse_rules(cfg)
    with pytest.raises(RulesError):
        parse_rules({"nope": 1})
    with pytest.raises(RulesError):
        load_rules_text("tags: [unclosed")

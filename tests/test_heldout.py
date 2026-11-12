from attack_ics import catalogue, load_ics
from scenarios_heldout import EXPECTED, SCENARIOS, tech_ok


def test_heldout_set_is_consistent():
    assert len(SCENARIOS) == 10
    assert set(SCENARIOS) == set(EXPECTED)
    ids = {c["id"] for c in catalogue(load_ics())}
    for sid, exp in EXPECTED.items():
        assert exp["verdict"] in {"escalate", "investigate", "likely_benign"}
        for t in exp["techniques"]:
            assert t in ids, f"{sid}: {t} not in ATT&CK data"


def test_tech_ok_rules():
    strict_empty = {"techniques": []}
    assert tech_ok([], strict_empty) and not tech_ok(["T0801"], strict_empty)
    optional = {"techniques": ["T0801"], "allow_empty": True}
    assert tech_ok([], optional) and tech_ok(["T0801"], optional)
    assert not tech_ok(["T0858"], optional)
    required = {"techniques": ["T0843"]}
    assert tech_ok(["T0843.001"], required) and not tech_ok([], required)

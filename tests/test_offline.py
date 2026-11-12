from llm import extract_json
from scenarios import SCENARIOS, EXPECTED, technique_match
from attack_ics import load_ics, candidates
from assets import lookup_asset


def test_extract_json_variants():
    assert extract_json('\n\n{"ok": true}') == {"ok": True}
    assert extract_json('<think>hmm {x}</think>{"a": 1}') == {"a": 1}
    assert extract_json('```json\n{"a": 2}\n```') == {"a": 2}


def test_scenarios_and_labels_match():
    assert len(SCENARIOS) == 12
    assert set(SCENARIOS) == set(EXPECTED)


def test_assets_lookup():
    assert lookup_asset("10.10.20.11")["name"] == "PLC-Line1"
    assert lookup_asset("PLC-Line1")["known"] is True
    assert lookup_asset("10.10.20.99")["known"] is False


def test_expected_techniques_exist_in_attack_data():
    ids = {t["id"] for t in load_ics()}
    for sid, exp in EXPECTED.items():
        for tid in exp["techniques"]:
            assert tid in ids, f"{sid}: {tid} not in ATT&CK data"


def test_catalogue_contains_all_expected():
    from attack_ics import catalogue
    ids = {c["id"] for c in catalogue(load_ics())}
    assert len(ids) > 80
    for exp in EXPECTED.values():
        for tid in exp["techniques"]:
            assert tid in ids

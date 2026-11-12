from guards import (check_evidence, clamp_priority, consistent,
                    detect_injection)
from scenarios import SCENARIOS as DEV
from scenarios_heldout import SCENARIOS as H1
from scenarios_heldout2 import EXPECTED as X_EXP, SCENARIOS as X
from attack_ics import catalogue, load_ics


def _text(a):
    return a.title + " " + a.description


def test_injection_detector_flags_known_injections_only():
    assert detect_injection(_text(H1["h06"]))
    assert detect_injection(_text(H1["h07"]))
    clean = [k for k in H1 if k not in ("h06", "h07")]
    for k in clean:
        assert not detect_injection(_text(H1[k])), k
    for k, a in DEV.items():
        assert not detect_injection(_text(a)), k


def test_consistency_and_clamp():
    assert consistent("escalate", "P1") and not consistent("investigate", "P1")
    assert consistent("likely_benign", "P4") and not consistent("likely_benign", "P2")
    assert clamp_priority("investigate", "P1") == "P2"
    assert clamp_priority("escalate", "P4") == "P2"
    assert clamp_priority("likely_benign", "P1") == "P3"


def test_evidence_must_cite_existing_data():
    payload = {"alert": {"description": "x", "raw": {}, "src_ip": "1.2.3.4"},
               "assets": {"src": {"zone": "L4"}},
               "intel": {"items": [{"url": "https://a.b"}]}}
    ev = ["alert.src_ip: 1.2.3.4", "alert.raw: function code 5",
          "assets.src.zone: L4", "assets.src.owner: nobody",
          "intel.items[0].url: https://a.b", "intel.items[3].url: x",
          "free text without a path"]
    kept, dropped = check_evidence(ev, payload)
    assert dropped == ["alert.raw: function code 5",
                       "assets.src.owner: nobody", "intel.items[3].url: x"]
    assert "free text without a path" in kept and len(kept) == 4


def test_second_heldout_set_consistent():
    assert len(X) == 10 and set(X) == set(X_EXP)
    ids = {c["id"] for c in catalogue(load_ics())}
    for sid, exp in X_EXP.items():
        assert exp["verdict"] in {"escalate", "investigate", "likely_benign"}
        assert all(t in ids for t in exp["techniques"]), sid

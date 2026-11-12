import json
import struct

import lab_common
import lab_elk
from attack_ics import load_ics
from lab_sniffer import Detector, parse_modbus
from scenarios_lab import EXPECTED, LAB_ATTACKS

SCADA, ATTACKER, PLC = "192.0.2.10", "192.0.2.66", "192.0.2.20"


def req(fc, addr, second, unit=1, tid=1):
    return struct.pack(">HHHBBHH", tid, 0, 6, unit, fc, addr, second)


def test_parse_modbus():
    f = parse_modbus(req(6, 21, 9500) + req(3, 0, 10, unit=2))
    assert f[0] == {"unit": 1, "fc": 6, "addr": 21, "value": 9500,
                    "quantity": None}
    assert f[1]["fc"] == 3 and f[1]["quantity"] == 10 and f[1]["unit"] == 2
    assert parse_modbus(b"GET / HTTP/1.1\r\n\r\n") == []
    assert parse_modbus(b"\x00") == []


def test_approved_master_raises_nothing():
    d = Detector({SCADA})
    for i in range(100):
        assert d.feed(1000 + i, SCADA, PLC, req(3, i, 10)) == []
    assert d.feed(1200, SCADA, PLC, req(6, 5, 1)) == []


def test_unapproved_write_once_per_cooldown():
    d = Detector({SCADA})
    a = d.feed(1000, ATTACKER, PLC, req(5, 12, 0xFF00))
    assert [x.raw["rule"] for x in a] == ["unapproved_write"]
    assert a[0].source == "labshock-sniffer" and a[0].protocol == "modbus"
    assert a[0].src_ip == ATTACKER and a[0].dst_ip == PLC
    assert "function code 5" in a[0].description
    assert d.feed(1010, ATTACKER, PLC, req(5, 12, 0)) == []
    assert len(d.feed(1400, ATTACKER, PLC, req(5, 12, 0))) == 1


def test_read_only_master_cannot_write():
    d = Detector({SCADA, "192.0.2.11"}, writers={SCADA})
    a = d.feed(1000, "192.0.2.11", PLC, req(16, 0, 2))
    assert [x.raw["rule"] for x in a] == ["unapproved_write"]


def test_scan():
    d = Detector({SCADA})
    rules = []
    for unit in range(1, 31):
        rules += [x.raw["rule"] for x in
                  d.feed(1000 + unit, ATTACKER, PLC, req(3, 0, 1, unit=unit))]
    assert rules == ["unapproved_master", "scan"]
    slow = Detector({SCADA})
    rules = []
    for unit in range(1, 31):
        rules += [x.raw["rule"] for x in slow.feed(
            1000 + unit * 100, ATTACKER, PLC, req(3, 0, 1, unit=unit))]
    assert "scan" not in rules


def test_elk_ecs_document():
    a = lab_elk.to_alert({"_id": "abc", "_index": "i", "_source": {
        "@timestamp": "2026-11-12T10:00:00Z",
        "kibana.alert.rule.name": "Modbus write from new host",
        "kibana.alert.severity": "high",
        "source": {"ip": ATTACKER},
        "destination": {"ip": PLC, "port": 502}}})
    assert a.source == "labshock-elk" and a.alert_id == "lab-elk-abc"
    assert a.title == "Modbus write from new host"
    assert (a.src_ip, a.dst_ip, a.protocol) == (ATTACKER, PLC, "modbus")
    assert a.severity_src == "high" and ATTACKER in a.description


def test_elk_suricata_document():
    a = lab_elk.to_alert({"_id": "x1", "_source": {
        "timestamp": "2026-11-12T10:00:00Z", "event_type": "alert",
        "src_ip": ATTACKER, "dest_ip": PLC, "dest_port": 502,
        "proto": "TCP", "app_proto": "modbus",
        "alert": {"signature": "Modbus write coil", "severity": 2}}})
    assert a.title == "Modbus write coil" and a.protocol == "modbus"
    assert a.severity_src == "2" and a.timestamp == "2026-11-12T10:00:00Z"


def test_elk_empty_document_still_valid():
    a = lab_elk.to_alert({"_id": "e", "_source": {}})
    assert a.src_ip is None and a.title


def test_dry_run_does_not_post(monkeypatch, tmp_path, capsys):
    def boom(*a, **k):
        raise AssertionError("posted during dry run")
    monkeypatch.setattr(lab_common.httpx, "post", boom)
    alert = Detector({SCADA}).feed(1000, ATTACKER, PLC, req(6, 1, 2))[0]
    out = tmp_path / "a.jsonl"
    assert lab_common.post_alert(alert, dry_run=True, out=str(out)) is None
    assert json.loads(out.read_text())["alert"]["alert_id"] == alert.alert_id
    assert "labshock-sniffer" in capsys.readouterr().out


def test_expected_labels_use_real_techniques():
    known = {t["id"] for t in load_ics()}
    for k, v in EXPECTED.items():
        assert v["verdict"] in ("escalate", "investigate", "likely_benign")
        assert set(v["techniques"]) <= known, k
    assert set(EXPECTED) == set(LAB_ATTACKS)

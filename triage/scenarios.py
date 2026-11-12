"""12 synthetic OT alerts with expected labels (set BEFORE running the system).
ATT&CK IDs follow the ICS data file v19.2 downloaded on 6 Oct 2026, where
several older IDs were revoked (e.g. T0855 -> T1692.001)."""
from schemas import Alert


def A(i, ts, title, desc, proto, src, dst, sev="medium", sa=None, da=None):
    return Alert(alert_id=i, timestamp=ts, source="synthetic", title=title,
                 description=desc, severity_src=sev, protocol=proto,
                 src_ip=src, dst_ip=dst, src_asset=sa, dst_asset=da)


# TODO before final evaluation: replace with a real CVE that appears in a
# current CISA ICS advisory, so Tavily returns real content for scenario 12.
CVE_FOR_S12 = "CVE-2026-76504"

_list = [
    A("s01", "2026-10-06T14:22:10+02:00",
      "Modbus write coil command to PLC from non-engineering host",
      "Modbus/TCP function code 5 (Write Single Coil) sent from 10.10.50.7 "
      "to 10.10.20.11 port 502, coil address 12, value ON. Source host has "
      "never written to this PLC before.",
      "modbus", "10.10.50.7", "10.10.20.11", "high"),
    A("s02", "2026-10-06T03:15:40+02:00",
      "Modbus unit ID and port sweep from new host",
      "Host 10.10.50.99 opened connections to 10.10.20.0/24 on ports "
      "502, 44818 and 20000 and probed Modbus unit IDs 1 to 247 within "
      "90 seconds. Host was first seen on the network today.",
      "modbus", "10.10.50.99", "10.10.20.11", "medium"),
    A("s03", "2026-10-08T02:40:05+02:00",
      "PLC program download outside change window",
      "Full program download to 10.10.20.12 from 10.10.40.8 at 02:40 on a "
      "Thursday. No change ticket is referenced.",
      "enip", "10.10.40.8", "10.10.20.12", "high"),
    A("s04", "2026-10-07T21:05:33+02:00",
      "PLC operating mode changed to PROGRAM",
      "Controller 10.10.20.11 changed operating mode from RUN to PROGRAM "
      "after a session from 10.10.40.8. Packaging line 1 output stopped.",
      "enip", "10.10.40.8", "10.10.20.11", "high"),
    A("s05", "2026-10-06T22:48:19+02:00",
      "New remote session to HMI from VPN subnet",
      "RDP session established from 10.10.90.14 (VPN pool) to 10.10.30.5. "
      "The account used has not logged in to this HMI before.",
      "rdp", "10.10.90.14", "10.10.30.5", "medium"),
    A("s06", "2026-10-06T09:10:27+02:00",
      "Engineering workstation reading PLC holding registers",
      "Modbus function code 3 (Read Holding Registers) from 10.10.40.8 to "
      "10.10.20.11, 120 registers, polled every 5 seconds for 20 minutes.",
      "modbus", "10.10.40.8", "10.10.20.11", "low"),
    A("s07", "2026-10-06T16:31:02+02:00",
      "ARP spoofing pattern on control network",
      "Host 10.10.20.77 sent unsolicited ARP replies claiming the MAC "
      "address of 10.10.20.11 to the HMI and SCADA server. Duplicate IP "
      "to MAC mappings detected.",
      "arp", "10.10.20.77", "10.10.30.5", "high"),
    A("s08", "2026-10-07T11:12:48+02:00",
      "Setpoint register written outside normal range",
      "Modbus function code 6 (Write Single Register) from 10.10.30.5 to "
      "10.10.20.11, register 40021 set to 9500. Normal range for this "
      "register is 1000 to 3000. Source is the HMI, a known writer.",
      "modbus", "10.10.30.5", "10.10.20.11", "high"),
    A("s09", "2026-10-06T01:02:51+02:00",
      "Repeated failed OPC-UA authentication",
      "47 failed OPC-UA session activations against 10.10.30.10 within "
      "5 minutes from 10.10.50.7 using different usernames.",
      "opcua", "10.10.50.7", "10.10.30.10", "medium"),
    A("s10", "2026-10-07T04:44:09+02:00",
      "DNP3 unsolicited response from unknown outstation",
      "SCADA master 10.10.30.10 received DNP3 unsolicited responses with "
      "analog input values from 10.10.20.99, which is not a configured "
      "outstation. Values differ from outstation 3.",
      "dnp3", "10.10.20.99", "10.10.30.10", "high"),
    A("s11", "2026-10-08T23:19:36+02:00",
      "EtherNet/IP firmware update command to I/O module",
      "CIP firmware update service request sent from 10.10.40.8 to the "
      "I/O module attached to 10.10.20.12 outside any maintenance window.",
      "enip", "10.10.40.8", "10.10.20.12", "high"),
    A("s12", "2026-10-06T18:55:12+02:00",
      "Exploit attempt against HMI web server referencing a known CVE",
      f"IDS signature matched an exploit attempt for {CVE_FOR_S12} against "
      "the web interface of 10.10.30.5 from 10.10.90.14.",
      "http", "10.10.90.14", "10.10.30.5", "high"),
]

SCENARIOS = {a.alert_id: a for a in _list}

EXPECTED = {
    "s01": {"verdict": "escalate",      "techniques": ["T1692.001"]},
    "s02": {"verdict": "investigate",   "techniques": ["T0846"]},
    "s03": {"verdict": "escalate",      "techniques": ["T0843"]},
    "s04": {"verdict": "escalate",      "techniques": ["T0858"]},
    "s05": {"verdict": "investigate",   "techniques": ["T0822"]},
    "s06": {"verdict": "likely_benign", "techniques": []},
    "s07": {"verdict": "escalate",      "techniques": ["T0830"]},
    "s08": {"verdict": "escalate",      "techniques": ["T0836"]},
    "s09": {"verdict": "investigate",   "techniques": ["T0859"]},
    "s10": {"verdict": "investigate",   "techniques": ["T1692.002"]},
    "s11": {"verdict": "escalate",      "techniques": ["T1693.002"]},
    "s12": {"verdict": "investigate",   "techniques": ["T0866"]},
}


def technique_match(got_ids, want_ids):
    """True if any expected technique matches (parent or sub-technique)."""
    base = lambda x: x.split(".")[0]
    return any(base(g) == base(w) for g in got_ids for w in want_ids)

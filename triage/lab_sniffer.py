"""Passive Modbus/TCP sniffer for the Labshock lab.

Listens on a mirror port or lab interface (or reads a .pcap), applies a
fixed rule, and posts each alarm to SentinelOT as an Alert with
source="labshock-sniffer". It only listens: it never sends a frame to the
control network.

The rule, the same one the showcase page demonstrates:
  unapproved_write   a write function code from a host that is not an
                     approved writer
  unapproved_master  any Modbus request from a host that is not an
                     approved master
  scan               an unapproved host touches many different
                     unit/register targets in a short time

Run from the repo root (needs: pip install -r requirements-lab.txt):
  python triage/lab_sniffer.py --iface eth0 --masters 192.0.2.10 --dry-run
  python triage/lab_sniffer.py --pcap capture.pcap --masters 192.0.2.10
"""
import argparse
import os
import struct
from collections import defaultdict
from datetime import datetime, timezone

from lab_common import csv_set, post_alert
from schemas import Alert

FC_NAMES = {1: "Read Coils", 2: "Read Discrete Inputs",
            3: "Read Holding Registers", 4: "Read Input Registers",
            5: "Write Single Coil", 6: "Write Single Register",
            15: "Write Multiple Coils", 16: "Write Multiple Registers",
            22: "Mask Write Register", 23: "Read/Write Multiple Registers"}
WRITE_FCS = {5, 6, 15, 16, 22, 23}


def parse_modbus(payload: bytes):
    """Parse the Modbus/TCP requests in one TCP payload.

    Returns a list of dicts: unit, fc, addr, and value (fc 5, 6) or
    quantity (reads and multiple writes). Bytes that are not Modbus/TCP
    give an empty list.
    """
    frames, i = [], 0
    while len(payload) - i >= 8:
        _tid, pid, length, unit, fc = struct.unpack_from(">HHHBB", payload, i)
        if pid != 0 or length < 2 or length > 254:
            break
        pdu = payload[i + 8:i + 6 + length]
        f = {"unit": unit, "fc": fc, "addr": None, "value": None,
             "quantity": None}
        if fc in FC_NAMES and len(pdu) >= 4:
            f["addr"], second = struct.unpack_from(">HH", pdu, 0)
            f["value" if fc in (5, 6) else "quantity"] = second
        frames.append(f)
        i += 6 + length
    return frames


def _iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(
        timespec="seconds")


class Detector:
    def __init__(self, masters, writers=None, scan_targets=20,
                 scan_window=60.0, cooldown=300.0):
        self.masters = set(masters)
        # Approved writers default to the approved masters.
        self.writers = set(writers) if writers else set(masters)
        self.scan_targets = scan_targets
        self.scan_window = scan_window
        self.cooldown = cooldown
        self._last = {}                    # (rule, src, dst) -> time
        self._seen = defaultdict(dict)     # (src, dst) -> {target: time}
        self._n = 0

    def _fire(self, rule, ts, src, dst):
        key = (rule, src, dst)
        if ts - self._last.get(key, -1e18) < self.cooldown:
            return False
        self._last[key] = ts
        return True

    def _alert(self, rule, ts, src, dst, title, desc, sev, frame, extra=None):
        self._n += 1
        raw = {"rule": rule, "detector": "lab_sniffer", **frame,
               **(extra or {})}
        return Alert(alert_id=f"lab-mb-{int(ts)}-{self._n}",
                     timestamp=_iso(ts), source="labshock-sniffer",
                     title=title, description=desc, severity_src=sev,
                     protocol="modbus", src_ip=src, dst_ip=dst, raw=raw)

    def feed(self, ts, src, dst, payload):
        """One TCP payload sent to the Modbus port. Returns new alerts."""
        alerts = []
        for f in parse_modbus(payload):
            fc = f["fc"]
            name = FC_NAMES.get(fc, "unknown function")
            what = f"Modbus/TCP function code {fc} ({name}) sent from " \
                   f"{src} to {dst} port 502, unit {f['unit']}"
            if f["addr"] is not None:
                what += f", address {f['addr']}"
            if f["value"] is not None:
                what += f", value {f['value']}"
            if f["quantity"] is not None:
                what += f", quantity {f['quantity']}"

            if fc in WRITE_FCS and src not in self.writers:
                if self._fire("unapproved_write", ts, src, dst):
                    alerts.append(self._alert(
                        "unapproved_write", ts, src, dst,
                        "Modbus write command to PLC from unapproved host",
                        what + ". Source is not on the approved writers "
                        "list for this PLC.", "high", f))
            if src in self.masters:
                continue
            if fc not in WRITE_FCS and \
                    self._fire("unapproved_master", ts, src, dst):
                alerts.append(self._alert(
                    "unapproved_master", ts, src, dst,
                    "Modbus request to PLC from unapproved master",
                    what + ". Source is not on the approved masters list "
                    "for this PLC.", "medium", f))

            seen = self._seen[(src, dst)]
            seen[(f["unit"], fc, f["addr"])] = ts
            for k in [k for k, t in seen.items()
                      if ts - t > self.scan_window]:
                del seen[k]
            if len(seen) >= self.scan_targets and \
                    self._fire("scan", ts, src, dst):
                units = sorted({k[0] for k in seen})
                alerts.append(self._alert(
                    "scan", ts, src, dst,
                    "Modbus register and unit ID scan from unapproved host",
                    f"Host {src} sent Modbus/TCP requests to {dst} port 502 "
                    f"covering {len(seen)} different unit/function/address "
                    f"targets ({len(units)} unit IDs) within "
                    f"{int(self.scan_window)} seconds. Source is not on the "
                    "approved masters list.", "medium", f,
                    {"targets": len(seen), "unit_ids": len(units)}))
        return alerts


def main():
    from dotenv import load_dotenv
    load_dotenv()
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--iface", help="interface to listen on")
    g.add_argument("--pcap", help="read a capture file instead")
    p.add_argument("--port", type=int, default=502)
    p.add_argument("--plc", help="only watch this PLC address")
    p.add_argument("--masters", default=os.getenv("LAB_APPROVED_MASTERS"),
                   help="approved masters, comma separated")
    p.add_argument("--writers", default=os.getenv("LAB_APPROVED_WRITERS"),
                   help="approved writers (default: same as masters)")
    p.add_argument("--dry-run", action="store_true",
                   help="print alerts, do not post them")
    p.add_argument("--out", help="append alerts and job ids to this .jsonl")
    a = p.parse_args()
    if not a.masters:
        raise SystemExit("Give --masters (or LAB_APPROVED_MASTERS).")

    from scapy.all import IP, TCP, sniff     # optional dependency
    det = Detector(csv_set(a.masters), csv_set(a.writers))

    def handle(pkt):
        if IP not in pkt or TCP not in pkt or pkt[TCP].dport != a.port:
            return
        if a.plc and pkt[IP].dst != a.plc:
            return
        data = bytes(pkt[TCP].payload)
        if data:
            for alert in det.feed(float(pkt.time), pkt[IP].src,
                                  pkt[IP].dst, data):
                post_alert(alert, dry_run=a.dry_run, out=a.out)

    kw = {"offline": a.pcap} if a.pcap else {"iface": a.iface}
    sniff(filter=f"tcp dst port {a.port}", prn=handle, store=False, **kw)


if __name__ == "__main__":
    main()

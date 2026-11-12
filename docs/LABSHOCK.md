# Lab alerts from Labshock

[Back to the README](../README.md)

---

**Status: built, not yet run against the lab.** There are no lab results yet. Everything below describes how the test is meant to be run.

Until now SentinelOT has only seen alerts written by hand. This adds two ways to feed it alerts from a Labshock home lab. Both only listen. Neither sends anything to the control network, and SentinelOT still only recommends.

| Feed | File | `source` on the alert | Where the detection comes from |
|---|---|---|---|
| ELK adapter | `triage/lab_elk.py` | `labshock-elk` | The lab's own detection rules in Elasticsearch |
| Modbus sniffer | `triage/lab_sniffer.py` | `labshock-sniffer` | A fixed rule in the sniffer: approved masters and writers, plus a scan threshold |

Each alert is posted to `POST /api/triage` with the admin token, the same way any free-form alert is.

## Before the first run

1. **Fill in the lab inventory.** `data/assets_lab.json` is empty on purpose. Add the lab PLC, SCADA and attacker machine in the same format as `data/assets.json`. The fictional plant stays in its own file so the evaluation numbers remain comparable.
2. **Start SentinelOT with the lab inventory:** set `ASSETS_FILE=data/assets_lab.json` and `APP_ADMIN_TOKEN` in `.env`.
3. **Expected labels are fixed first.** The labels in `triage/scenarios_lab.py` were confirmed on 12 November 2026, before any attack was run. Do not change them after seeing a result.

## ELK adapter

```
python triage/lab_elk.py --dry-run --once
```

`--dry-run` prints the alerts it would send. Use it first to check that the index (`LAB_ES_INDEX`) and the field mapping fit the lab's documents. The adapter tries Elastic Common Schema field names and Suricata EVE field names. Drop `--dry-run` to post, and add `--out results/lab_alerts.jsonl` to keep a record of each alert and its job id.

## Modbus sniffer

```
pip install -r requirements-lab.txt
python triage/lab_sniffer.py --iface eth0 --masters <SCADA address> --dry-run
```

`--pcap file.pcap` reads a saved capture instead of a live interface. One alert is raised per rule, source and destination every five minutes at most, so a burst of frames does not start a burst of triage runs.

## Recording results

For each attack in `triage/scenarios_lab.py`, note the time it was run, then compare the verdict and techniques SentinelOT returned with the expected ones. Report lab results separately from the synthetic evaluation.

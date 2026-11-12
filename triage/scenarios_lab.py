"""Planned Labshock lab attacks with expected labels.

As in scenarios.py, the labels are set BEFORE the attacks are run. Unlike
scenarios.py there are no Alert objects here: the alerts come from the lab
(lab_sniffer.py or lab_elk.py) when each attack is carried out.

STATUS: labels confirmed by the author on 12 Nov 2026, before any run.
Not yet run: no lab result exists for any of these.

"rule" is the lab_sniffer rule that should raise the alert. For ELK
alerts, match by time and source address instead.
"""

LAB_ATTACKS = {
    "la01": {
        "what": "Write Single Coil (function code 5) to the lab PLC from "
                "the attacker machine",
        "rule": "unapproved_write",
        "verdict": "escalate", "techniques": ["T1692.001"]},
    "la02": {
        "what": "Write Single Register (function code 6) changing a "
                "setpoint on the lab PLC from the attacker machine",
        "rule": "unapproved_write",
        "verdict": "escalate", "techniques": ["T1692.001", "T0836"]},
    "la03": {
        "what": "Register and unit ID scan of the lab PLC from the "
                "attacker machine",
        "rule": "scan",
        "verdict": "investigate", "techniques": ["T0846"]},
    "la04": {
        "what": "Control: normal polling of the lab PLC by the lab SCADA. "
                "The sniffer should raise nothing; if ELK raises an alert "
                "it should be judged benign",
        "rule": None,
        "verdict": "likely_benign", "techniques": []},
}

EXPECTED = {k: {"verdict": v["verdict"], "techniques": v["techniques"]}
            for k, v in LAB_ATTACKS.items()}

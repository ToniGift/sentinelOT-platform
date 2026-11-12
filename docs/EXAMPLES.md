# Examples

[Home](../README.md) | [About](ABOUT.md) | **Examples** | [How it works](HOW_IT_WORKS.md) | [Nemotron and Nebius](NEMOTRON_AND_NEBIUS.md) | [Web interface](WEB_INTERFACE.md) | [Run it](RUN_IT.md) | [Testing the demo](TESTING.md) | [Test plant](TEST_PLANT.md) | [Evaluation](EVALUATION.md)

---

Every example here uses a synthetic alert in a fictional plant (see [Test plant](TEST_PLANT.md)). To try one yourself, follow [Testing the demo](TESTING.md).

## Example 1: an office PC writes to a production PLC

**The alert:** a Modbus/TCP "write single coil" command (function code 5) from an office PC to the line 1 PLC, setting coil 12 to ON. The source host had never written to this PLC before.

SentinelOT returned, in 26 seconds:

- **Verdict:** escalate, priority P1, confidence 90%
- **Why:** an office workstation (Level 4 enterprise, low criticality) sent the first write it had ever sent to a high-criticality PLC in Level 1 control, and it is not an engineering station. The result called this unauthorized command traffic reaching a safety-relevant control asset.
- **ATT&CK for ICS:** two techniques mapped. The explanation mentions an unauthorized command message and I/O image manipulation.
- **Threat intelligence:** two CISA advisories, both marked as on the trusted list: one about a Delta Electronics PLC that exposes Modbus TCP without authentication, and one about the Schneider Electric Modicon Modbus protocol sending commands in cleartext. They are background about Modbus in general, not about the plant's own PLC.
- **Evidence:** 21 lines, each citing a field of the alert, a field of the asset record or a retrieved finding
- **Next steps:** three read-only checks (review the PLC diagnostic and Modbus traffic logs for the state of coil 12, check network flow and IDS logs for other connections from the same host, and interview the user of the office PC) and two that need operator approval (temporarily block Modbus traffic from the source to the PLC at the firewall or zone boundary, and, if the change was not intended, write the coil back to OFF from an approved engineering station)

![The pipeline for alert s01 after a finished run, with the time of every step](images/screenshot-s01-pipeline.png)

![The result for alert s01, showing the verdict, priority, confidence, reasoning and the start of the next steps](images/screenshot-s01-result.png)

![The next steps for alert s01 in two lanes, and the timing tab with the model, seconds and token counts of every step](images/screenshot-s01-next-steps.png)

![The Threat intel tab for alert s01, showing two CISA advisories marked as on the trusted list](images/screenshot-s01-threat-intel.png)

An earlier run of the same alert returned a confidence of 0.92 in about 28 seconds and mapped T0831, Manipulation of Control. Results vary between runs, which is why the [Evaluation](EVALUATION.md) page reports repeated runs.

## Example 2: a successful remote login to the SCADA server

**The alert:** five failed RDP logins, then a successful interactive login to the SCADA server from the VPN address pool, using a service account that had never logged in interactively before.

SentinelOT returned, in 29 seconds:

- **Verdict:** escalate, priority P1, confidence 90%
- **Why:** a successful interactive login to a high-criticality SCADA server in the Level 2 supervisory zone, from a VPN host, after failed attempts and with an account that had never been used this way. The asset record showed the server hosts an OPC-UA endpoint and a DNP3 master, so supervisory control was at stake.
- **ATT&CK for ICS:** T0822 External Remote Services and T0859 Valid Accounts
- **Threat intelligence:** six sources retrieved, including a finding that RDP is among the protocols targeted by credential stuffing
- **Evidence:** 20 lines, each citing a field of the alert, a field of the asset record or a retrieved finding
- **Next steps:** two read-only checks (review the Windows logon events on the server, and review the VPN authentication logs for the source address) and four that need operator approval (disable or reset the service account, require multi-factor authentication for remote RDP, block RDP from the VPN zone to the supervisory zone unless it is approved, and collect volatile memory and a forensic image of the server)

![The pipeline for alert x01 after a finished run, with the time of every step](images/screenshot-x01-pipeline.png)

![The result for alert x01, showing the verdict, priority, confidence, reasoning and the start of the next steps](images/screenshot-x01-result.png)

![The next steps for alert x01 in two lanes, and the timing tab with the model, seconds and token counts of every step](images/screenshot-x01-next-steps.png)

## Example 3: a routine engineering change

**The alert:** a Modbus/TCP "write multiple registers" command (function code 16) from the engineering workstation to the line 1 PLC, three registers, at 08:55 on a Tuesday, with a change ticket referenced in the session notes.

SentinelOT returned, in 26 seconds:

- **Verdict:** likely benign, priority P4, confidence 95%
- **Why:** the write came from the known engineering workstation, inside its documented Tuesday 08:00 to 10:00 change window, and referenced a change ticket. The destination is a high-criticality PLC, but programming PLCs is the workstation's approved function.
- **ATT&CK for ICS:** no techniques mapped. The mapper is allowed to return none when nothing fits.
- **Threat intelligence:** three sources, treated as background. They describe how Modbus function code 16 writes can be abused, including by the FrostyGoop malware and the INCONTROLLER tool, but nothing in this alert pointed to malicious behaviour.
- **Evidence:** 8 lines, citing fields of the alert, fields of the asset record, and the intake and intel summaries
- **Next steps:** two read-only checks (review the change ticket and its approval records, and check the Modbus logs for any other writes to the PLC outside the approved window) and none that need operator approval

![The pipeline for alert x03 after a finished run, with the time of every step](images/screenshot-x03-pipeline.png)

![The result for alert x03: verdict likely benign, priority P4, confidence 95%, with the reasoning and no actions needing an operator](images/screenshot-x03-result.png)

![The next steps for alert x03, with nothing in the operator lane, and the Evidence tab listing the eight lines the verdict rests on](images/screenshot-x03-next-steps.png)

Notice what is quiet here: the verdict is grey, no technique is mapped, and the "Needs an operator" lane is empty. The verdict also rests partly on the ticket reference in the alert text. SentinelOT has no access to a ticketing system, so its first suggested step is for a person to check the ticket. This is one of the limits listed on the [Evaluation](EVALUATION.md) page.

## Other runs from the live demo

| Alert | Verdict | Priority | Confidence | Run time |
|---|---|---|---|---|
| s01: Modbus write coil command to PLC from non-engineering host | Escalate | P1 | 90% | 26 s |
| s09: Repeated failed OPC-UA authentication | Investigate | P2 | 75% | 24 s |
| x01: Successful remote login to SCADA server from VPN | Escalate | P1 | 90% | 29 s |
| x03: Engineering workstation writing PLC parameters in change window | Likely benign | P4 | 95% | 26 s |
| x08: Unknown device reading from two PLCs | Investigate | P2 | 85% | 38 s |

These are single runs. Run times in this table range from 24 to 38 seconds, and results vary between runs, so see [Evaluation](EVALUATION.md) for what repeated runs show.

The page keeps these runs in its **Scan history** section, newest first, with the verdict, priority, confidence and run time of each:

![The Scan history section after five live runs: x03 likely benign, x08 investigate, x01 escalate, s09 investigate and s01 escalate](images/screenshot-history.png)

## What every result contains

- **Verdict, priority and confidence:** escalate, investigate or likely benign; P1 (highest) to P4; and a confidence score.
- **Why, and what it could do to the process:** a short explanation in plain language.
- **Evidence:** the facts the decision rests on, each tied to its source.
- **Threat intelligence:** retrieved sources, marked as trusted or unverified.
- **ATT&CK for ICS techniques:** chosen only from the official list, or none.
- **Next steps:** each labelled *read-only* or *needs operator approval*. SentinelOT never carries them out.
- **Checks and timing:** what the code checks removed or flagged, and the model, time and token use of every step.

---

[Back to the README](../README.md)

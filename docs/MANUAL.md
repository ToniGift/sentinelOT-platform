# SentinelOT Platform: Manual

**SIMULATED.** Everything in this manual describes a simulation. The plant, its machines, its network traffic, its sensor readings and its alerts are invented. Where this manual describes firewall rules, alarm limits or detection rules, they are **demo rules, not a recommendation for a real plant.** No real control system is connected to anything described here.

Written against the repository as committed at `0d50029` (16 November 2026). Figures that were measured are marked with the date they were measured. Anything that could not be checked is marked **not verified** or left out.

## How to read this manual

The manual is written for two kinds of reader: the person who built the project, and people who know little about industrial security. Each chapter opens with a short **In plain words** box. Terms are explained the first time they appear, and a glossary at the end collects them.

Three markers are used throughout:

- **SIMULATED** marks anything that exists only inside the demonstration.
- **Measured on (date)** marks a number that was produced by running the code or reading the recorded files on that date.
- **Not verified** marks a statement that comes from general knowledge or from the project's own notes, and that this manual's author did not check against the code, the data or a test.

## Contents

1. What SentinelOT Platform is
2. The plant and the Purdue model
3. The Live tab and the attacks
4. The annunciator and first-out
5. Firewall rules and Segmentation
6. Limits, AlarmOps and What-if
7. The Quiet attack control and the HMI write demo
8. The equipment list, the 3D controls and phone use
9. The AI triage
10. AlarmOps: the alarm-limit gate
11. How an attacker would attack each part
12. How each attack is detected and prevented here
13. What was learned
14. Running it, hosting it and testing it
15. Glossary

---

## 1. What SentinelOT Platform is

> **In plain words.** SentinelOT Platform is a teaching and demonstration tool about the security of a factory. It draws an invented packaging factory in 3D in your web browser and lets you attack it, defend it, and watch what happens. It has three parts that look at the same factory from different angles: a 3D page, an AI-assisted alert reviewer, and a checker for changes to alarm limits. It only ever recommends. It never changes anything.

### 1.1 The problem it shows

A factory is run by small computers called **controllers** that read sensors and switch machines on and off. Those controllers talk to each other and to operators' screens over a network. Two kinds of trouble on that network are easy to miss and costly.

The first is **a command that should not arrive**: someone on the office network, who has no business controlling a machine, sends a command to a controller. The second is **a quieter change**: an engineer widens an **alarm limit**, the reading at which the control system calls a person, and a real fault that used to raise an alarm now passes in silence.

This project shows both on one invented plant, and shows how they combine: loosen the alarm limit first, then attack, and the attack makes no noise in the process alarms at all.

### 1.2 The three parts

| Part | What it is | Where it lives | What it needs |
|---|---|---|---|
| **The 3D plant page** | One web page that draws the factory as stacked layers, simulates network traffic and attacks, and shows alarms | `static/sentinelot.html` | Only a web browser. It opens straight from a file. |
| **The AI triage** | A server that takes one alert, runs five AI agents in a fixed order, checks their answers with ordinary code, and returns a verdict with reasoning and suggested next steps | `triage/` (server), `static/index.html` (its web page) | A server, model access keys and a search key |
| **AlarmOps** | A checker that replays a labelled set of sensor readings against a proposed set of alarm limits and says whether the change should be allowed | `alarmops/` (an unmodified copy of the AlarmOps project, used as a library) and `triage/alarm_limits.py` (three read-only routes) | The server, for a live check. The page carries a recorded copy of the answer for when no server is running. |

A fourth folder, `plant/`, ties the parts together. It holds the alarm limits, the generated sensor dataset, and a small file that says which equipment each alarm tag belongs to, using the same names the 3D page draws.

### 1.3 How the parts connect, and what does not connect

```mermaid
flowchart TD
  A["Office computer, level 4"] -->|"Modbus write, 240 C"| B["Line 1 controller, level 1"]
  A -->|"crosses three firewalls"| T["Triage: verdict, technique, next steps"]
  B --> C["Heat sealer, level 0"]
  C --> S["Sealer temperature, read at the sensor gateway"]
  S --> G["Alarm gate: would this limit still catch the fault?"]
  T -.- N["no data passes between them"]
  N -.- G
```

*Figure: the diagram from the project README. The dotted line is the point: no data passes between the triage half and the alarm-limit half.*

What is connected, from the code:

- The page's **Limits** tab asks the server's `/api/alarmops/...` routes for a live answer. When there is no server it shows a **recorded** answer that is saved inside the page, and says so.
- The page and AlarmOps share one plant: the alarm tag `sealer_temperature` is measured at `SENSOR-GW-1` and read by `PLC-Line1`, so a blocked limit change lights up those machines on the 3D plant.
- The page's **Recorded** tab shows eight alerts with the verdicts the AI triage returned for them in its evaluation run. The page does not call the triage server to get them. They are stored in the page.

What is **not** connected, and the page and the project say so:

- The live attack on the page is **never sent to AlarmOps**, and AlarmOps **never looks at network traffic**. The page only shows that the limit AlarmOps protects is the limit that catches the sealer attack.
- The page **never sends its live traffic to the triage server**. The only call the page makes to a server is to the alarm-limit routes (and, to find out whether a server is there at all, one request for itself). This was checked in the page's code.
- The alarm that appears on the page when you attack comes from two simple rules inside the page, not from the AI triage. Chapter 7 describes them.

### 1.4 It recommends, never acts

Nothing in this project writes to a control network, blocks a connection, changes a setting on a controller or deploys anything. Every suggestion the triage makes is labelled either **read-only** or **needs operator approval**, and a person decides. The page's alarm notes say the same thing in their own words. The AlarmOps gate in this repository only answers a question: it stores nothing, and a proposed change exists only in the reply.

### 1.5 Not built yet

Two features have been planned but **do not exist** in this repository. This manual does not describe them as if they did.

- **Incident replay**: recording the events of an incident and scrubbing back and forth through them. Planned, not built.
- **Blast radius**: clicking an asset to see everything it can reach and everything that can reach it, with a small map of what depends on what. Planned, not built. (The Segmentation tab's reach counter, chapter 5, answers a narrower question for one host, OFFICE-PC-14. It is not the blast-radius feature.)

---

## 2. The plant and the Purdue model

> **In plain words.** The factory is drawn as a stack of floors. Machines are at the bottom and the internet is at the top. Between the floors are firewalls, which decide what traffic may pass. The stack follows a widely used way of organising industrial networks called the Purdue model. Every item has a short tag, like a label on an engineering drawing.

### 2.1 The Purdue model in one page

Industrial networks are usually described as layers, numbered from the machines up to the outside world. The layers exist on purpose: equipment that touches the product sits at the bottom, office computers sit near the top, and every boundary is a place to stop traffic that should not cross it. The numbering used here is the one the project README describes as the Purdue model.

| Level | Name used on the page | What it is | Typical contents here |
|---|---|---|---|
| 5 | Internet | Outside the company | The internet cloud and the VPN gateway staff and suppliers dial into |
| 4 | Enterprise | The office network | An ordinary desk computer, the ERP server |
| 3.5 | DMZ | A buffer zone between office and plant. "DMZ" means demilitarised zone. | The jump server, the patch server, a read-only copy of plant data |
| 3 | Operations | Plant-wide systems | The engineering workstation, the historian, the production scheduler, the plant's login server |
| 2 | Supervisory | The screens operators watch | The HMI, the SCADA server, the utilities console and server |
| 1 | Control | The computers that run the machines | The two line controllers, the remote controller, the utilities controller |
| 0 | Field | The machines and sensors themselves | The sealer, the conveyor drive and motor, the robot, the tank, pump and flow meter |

Some terms used in that table, explained once here:

- A **PLC** (programmable logic controller) is a small rugged computer that runs one machine or line.
- A **DCS** (distributed control system) does the same job for a continuous process such as steam or cooling water.
- An **HMI** (human-machine interface) is the screen an operator uses to watch and adjust a machine.
- An **RTU** (remote terminal unit) is a controller in a remote spot that reports readings back.
- **SCADA** (supervisory control and data acquisition) is the software layer that gathers data from many controllers.
- A **historian** is a database that stores process readings over time.

### 2.2 Zones, conduits and firewalls

The page's model (called `NetworkModel` in the code) describes the plant with three simple ideas.

- A **zone** is one level. There are seven: levels 0, 1, 2, 3, 3.5, 4 and 5.
- A **conduit** is the link between two neighbouring zones. There are six.
- A **firewall** is a device on a conduit that decides what may cross. Four of the six conduits have one. **Two do not**, and the model keeps them in on purpose, because an unfiltered boundary is a fact about a plant.

| Conduit | Joins | Firewall | Rule behind its switch |
|---|---|---|---|
| C-0-1 | Level 0 and level 1 | **none** | none |
| C-1-2 | Level 1 and level 2 | FW-304 (FW-Cell-1) | SEG-304 |
| C-2-3 | Level 2 and level 3 | **none** | none |
| C-3-3.5 | Level 3 and level 3.5 | FW-303 (FW-DMZ-OT) | SEG-303 |
| C-3.5-4 | Level 3.5 and level 4 | FW-302 (FW-IT-DMZ) | SEG-302 |
| C-4-5 | Level 4 and level 5 | FW-301 (FW-Edge) | SEG-301 |

A path between two zones crosses every conduit between them, in order. This is why an attack from the office (level 4) to a controller (level 1) crosses the conduits at levels 4 to 3.5, 3.5 to 3, 3 to 2 and 2 to 1: three firewalls and one gap.

**Subnets and VLANs.** Each zone is given one **subnet** (a block of network addresses) and one **VLAN** (a virtual network number). On the page these are derived from the demo addresses: the third part of an address like 10.10.20.11 gives the zone, so level 1 is `10.10.20.0/24` with VLAN 20, level 3.5 is `10.10.45.0/24` with VLAN 45, and so on. **SIMULATED: demo numbering, not a recommendation for a real plant.**

### 2.3 The four firewalls

All four are demo additions. They are not in the project's asset file.

| Tag | Name | Between | What it is meant to stop | Origin |
|---|---|---|---|---|
| FW-301 | FW-Edge | levels 5 and 4 | Internet edge firewall. Only the VPN gateway and outbound web traffic may pass | Demo only |
| FW-302 | FW-IT-DMZ | levels 4 and 3.5 | Separates the office network from the OT DMZ. Office hosts may reach the DMZ servers only | Demo only |
| FW-303 | FW-DMZ-OT | levels 3.5 and 3 | Separates the DMZ from operations. No direct path from the office network to the plant floor | Demo only |
| FW-304 | FW-Cell-1 | levels 2 and 1 | Cell firewall on the level 2 to level 1 boundary: this model has one conduit between those levels, so every level 1 controller sits behind it. Only HMI-Line1, the historian and the engineering workstation may reach PLC-Line1. As found it was named the line 1 cell firewall | Demo only |

Each firewall has one switch on the page, labelled with its rule, reading **ALLOW** or **DENY**. Chapter 5 explains them. A note on one name: FW-304 is called FW-Cell-1 and was first described as the "line 1 cell firewall". The model has a single conduit between level 2 and level 1, so FW-304 actually stands in front of **every** level 1 controller (PLC-Line1, PLC-Line2, DCS-CTRL-01 and RTU-Outstation-3), not only line 1's. The page now calls it the cell firewall on the level 2 to level 1 boundary and keeps the old name in its notes. Chapter 13 tells that story.

### 2.4 Asset tags

Every item carries a short **tag**, like the labels on a plant drawing. The tags are ISA-style: loosely modelled on the instrument naming used on engineering drawings, assigned for this demo and not an official scheme. A tag is a letter code and a three-digit number. The first digit of the number is the area:

| First digit | Area |
|---|---|
| 1 | Line 1 |
| 2 | Line 2 |
| 3 | Network security (the firewalls) |
| 4 | Enterprise and DMZ |
| 5 | Utilities |
| 6 | Operations, and supervisory servers and workstations |

IT equipment uses plain asset-class prefixes: `SRV` (server), `WS` (workstation), `DB` (database) and `PC`. A transmitter prefix (`TT`, `LT`, `PT`, `FT`, `ST`) goes only on a device that measures something. So `PLC-101` is PLC-Line1 and `FW-304` is FW-Cell-1.

### 2.5 Every asset and what it does

There are 28 drawn assets. **Fourteen** of them are in the project's asset file, `data/assets.json`, which is what the AI triage looks up. The other **fourteen** were added to make the page worth looking at and are marked **Demo only**. The descriptions below are the ones the page itself shows.

| Tag | Name | Level | What it does | Origin |
|---|---|---|---|---|
| T-501 | TANK-Utility-1 | 0 field | Chilled-water buffer tank. Its level transmitter is wired to DCS-CTRL-01 | Demo only |
| VFD-101 | VFD-Conveyor-1 | 0 field | Drives the line 1 conveyor motor | Project asset file |
| M-101 | MOTOR-Conveyor-1 | 0 field | Line 1 conveyor motor, driven by VFD-Conveyor-1 | Demo only |
| RB-101 | ROBOT-Pick-1 | 0 field | Packs line 1 product into cases, enabled by PLC-Line1 | Demo only |
| IO-201 | IO-Module-Line2 | 0 field | EtherNet/IP remote I/O for PLC-Line2 | Project asset file |
| P-501 | PUMP-Utility-1 | 0 field | Chilled-water circulation pump. Its pressure transmitter is wired to PLC-Line2 | Demo only |
| FT-501 | FLOW-Meter-1 | 0 field | Chilled-water flow meter on the pump discharge. Wired to PLC-Line2 | Demo only |
| SL-101 | SEALER-Line1 | 0 field | Heat-seals the film on line 1. Its temperature sensors are read through SENSOR-GW-1 | Demo only |
| GW-101 | SENSOR-GW-1 | 0 field | Modbus TCP gateway for the line 1 sealer temperature sensors | Project asset file |
| DCS-501 | DCS-CTRL-01 | 1 control | Redundant controller pair running the utilities control loops. Reads the level of TANK-Utility-1 | Demo only |
| PLC-101 | PLC-Line1 | 1 control | Packaging line 1 control | Project asset file |
| PLC-201 | PLC-Line2 | 1 control | Packaging line 2 control | Project asset file |
| RTU-501 | RTU-Outstation-3 | 1 control | Utility metering outstation, reports to SCADA over DNP3 | Project asset file |
| HMI-101 | HMI-Line1 | 2 supervisory | Operator screen for line 1, the approved Modbus master | Project asset file |
| SRV-603 | SCADA-SRV-01 | 2 supervisory | SCADA server with OPC UA endpoint and DNP3 master | Project asset file |
| WS-501 | DCS-OPS-01 | 2 supervisory | Operator console for the plant utilities: steam, compressed air and chilled water | Demo only |
| SRV-501 | DCS-SRV-01 | 2 supervisory | DCS application server: holds the control configuration, alarms and trends for the utilities | Demo only |
| WS-601 | ENG-WS-01 | 3 operations | PLC programming. Approved change window: Tuesday 08:00 to 10:00 | Project asset file |
| DB-601 | HIST-01 | 3 operations | Process data historian, polls PLCs read-only | Project asset file |
| SRV-601 | MES-SRV-01 | 3 operations | Manufacturing execution system: schedules production orders and tracks batches | Demo only |
| SRV-602 | AD-OT-01 | 3 operations | Logins and group policy for the OT workstations and servers | Demo only |
| SRV-402 | JUMP-SRV-01 | 3.5 DMZ | Remote access entry point for OT | Project asset file |
| SRV-403 | PATCH-SRV-01 | 3.5 DMZ | Stages approved patches for OT | Project asset file |
| DB-401 | HIST-DMZ-01 | 3.5 DMZ | Read-only copy of historian data for the enterprise network | Project asset file |
| PC-401 | OFFICE-PC-14 | 4 enterprise | Office workstation, not an engineering station | Project asset file |
| SRV-401 | ERP-SRV-01 | 4 enterprise | Production planning and customer orders | Demo only |
| - | INTERNET | 5 internet | Public internet and cloud services | Demo only |
| VPN-301 | VPN-GW-01 | 5 internet | Remote access for staff and vendors, hands out the 10.10.90.0/24 pool | Demo only |

Five more tags are not equipment. They are **signals**: a measurement on one item, read through another. All five are demo only.

| Tag | What it measures | Measured on | Read through |
|---|---|---|---|
| TT-101 | Sealer temperature | SEALER-Line1 | SENSOR-GW-1 |
| ST-101 | Conveyor speed | MOTOR-Conveyor-1 | VFD-Conveyor-1 |
| LT-501 | Utilities tank level | TANK-Utility-1 | DCS-CTRL-01 |
| PT-501 | Pump pressure | PUMP-Utility-1 | PLC-Line2 |
| TIC-101 | Sealer temperature controller, setpoint | PLC-Line1 | inside PLC-Line1 |

Each of the five alarm-limit tags in AlarmOps maps to one of these (or to the flow meter's own tag, `FT-501`), and that tag lights up on the plant when a limit change is blocked or would miss an alarm.

A few assets have no network address: the drawn internet cloud, the tank, the pump, the flow meter, the sealer and the conveyor motor. They are wired to a controller or gateway, not on the network. That is why they are left out of the reach counter in chapter 5.

![The plant in the isometric view, with every tag plate shown. Levels run from the field at the bottom to the internet at the top. SIMULATED.](images/manual/plant-3d.png)

---

## 3. The Live tab and the attacks

> **In plain words.** The Live tab is where you play the attacker. Three buttons send invented network messages to the line 1 controller from a computer that has no right to control it. The page notices, raises an alarm, draws the path the message took through the factory, and explains what it could do to the machine. Nothing leaves your browser.

![The Live tab after the sealer setpoint attack, with the trace drawn on the plant and the first alarm showing. Opened from a file, so the analyst note is the pre-written one. SIMULATED.](images/manual/live-tab.png)

### 3.1 What is on the screen

The page has five regions. The **Views** column on the left holds five tabs: Live attack, Recorded, Limits, What-if and Segmentation. The **stage** in the middle is the 3D plant. The **panel** on the right holds the controls and detail of the tab you chose. The **annunciator** under the stage is a row of alarm windows (chapter 4). Below that are a small **title block** in the style of an engineering drawing, a **Line 1 process** panel showing the sealer setpoint, sealer temperature, conveyor speed and packs per minute with a chart, and a **Modbus/TCP traffic** log. A header strip with the drawing details, section links, a SIMULATED badge and a light and dark switch stays at the top of the page as you scroll.

### 3.2 The traffic

**Modbus/TCP** is a very common language industrial controllers speak over a network. The traffic log lists its messages. In normal running, two computers are approved to talk to the line 1 controller (PLC-Line1, address 10.10.20.11): the operator screen **HMI-Line1** (10.10.30.5), which may read and write, and the historian **HIST-01** (10.10.40.20), which only reads. The page generates a steady pattern of their reads and the controller's replies. Roughly one message passes every 0.7 seconds, and each is shown with its time, its two addresses, its function code, a plain-language description and the raw bytes in hexadecimal.

A **function code** is a number inside a Modbus message that says what is being asked. The ones that appear here are 3 (read holding registers), 1 (read coils), 5 (write a single coil) and 6 (write a single register). A **register** is a numbered memory slot in the controller holding a value; a **coil** is a numbered on/off switch.

The controller's register map on this page is invented for the demo: register 40001 is the sealer setpoint (in tenths of a degree), 40002 the sealer temperature, 40003 the conveyor speed and 40004 the packs per minute. Coil 00001 is the sealer heater, 00002 the conveyor run switch and 00003 the packing robot enable.

### 3.3 The three attacks

Each button queues a short exchange: the attacker's message, then the controller's reply.

| Button | Who sends it | What the message does | What the process does |
|---|---|---|---|
| **Raise the sealer setpoint** | OFFICE-PC-14 (10.10.50.7), an ordinary office computer | A write of function code 6 to register 40001, setting the sealer setpoint to 240 °C. The normal setpoint is 160 °C. | The sealer temperature climbs towards 240 °C, passing its 190 °C high limit. The page's note says film can burn or melt onto the sealing bars and the line may need to stop for cleaning. |
| **Stop the packing robot** | OFFICE-PC-14 | A write of function code 5 to coil 00003, switching the robot enable off | The robot stops while the conveyor keeps running, so product piles up at the end of line 1 |
| **Scan the register map** | A host first seen today, 10.10.50.99 | Five reads of function code 3 at addresses the controller does not use; the controller answers each with exception 02, "illegal data address" | Nothing in the process changes. The page's note says this is how someone maps a controller before sending a write. |

Each attack button is disabled while it is already active or while a message is still being sent. A second attack can be started before the first is acknowledged, and both alarms stay active.

### 3.4 What raises the alarm

In the live demo, a small piece of code in the page watches every message sent to the controller and applies **two rules**. Both look at **who is sending**, not at what value is being written:

1. **Write from a host that is not an approved master.** A write (function code 5, 6, 15 or 16) to the controller from any address other than the HMI or the historian raises a **critical** alarm at once.
2. **Three or more reads of unmapped addresses from one unapproved host.** This raises a **warning**, a register scan.

The two approved addresses are the only ones the rules trust. Chapter 7 explains what this means for an attack that comes from an approved host. A third alarm, the **TT-101 process alarm**, is not a network rule at all. It is the sealer temperature crossing its high limit, and it fires a few seconds after the setpoint attack, once the sealer has actually heated up.

### 3.5 Reading an alarm

An alarm card shows a severity label, a title, the **source** and **target**, a folded **alarm detail** (sequence number, state, time, the rule that fired and the firewalls the message crossed) and an **analyst note**.

The analyst note is three short paragraphs: what happened, what it could do to the process, and what to do first. There are two ways the note is produced, and the card says which:

- **Pre-written.** Used when the page is opened without an AI helper, which is the normal case for a file or a static site. The label reads "Analyst note (pre-written, live AI isn’t available in this view)".
- **Written live by AI.** Used only when the page is opened somewhere that supplies an AI helper to the page. The label then reads "Analyst note, written live by AI". The page does not itself contain any model key. How such a helper is provided is outside this repository, and was **not verified** here.

The card has two buttons. **Acknowledge** stops the flashing. **Restore from HMI-Line1** puts the setpoint or the robot back, as an operator would from the operator screen. The setpoint attack's card also carries a sentence about AlarmOps and a **See the blocked change** button that opens the Limits tab (chapter 6).

On a phone the card is shorter: the first sentence of the analyst note leads, and the rest folds behind **Read the full note** (chapter 8).

### 3.6 When a firewall stops the message

If a firewall switch is set to DENY on the route, the attack is stopped before it reaches the controller. Then:

- Nothing changes in the plant, so **no alarm is raised**.
- The traffic log shows one row marked **DENY at FW-xxx · did not reach PLC-101**.
- An informational window appears and says, in as many words, that **SentinelOT did not see the attempt**: the passive sensor sits between the masters and the controller, and a message stopped further up never reaches it. The note comes from a simulated firewall log.
- The 3D view draws the path stopping at the firewall that denied it, and does not light the controller.

The page is making a point here: segmentation (stopping traffic) and monitoring (seeing traffic) are different controls.

---

## 4. The annunciator and first-out

> **In plain words.** An annunciator is the row of lit boxes on a control-room panel, one box per kind of trouble. The one that lit first is marked, because the first alarm is usually the cause and the later ones are consequences. This page copies that habit.

### 4.1 The five windows

| Window | Tag | Meaning | Kind |
|---|---|---|---|
| SP changed | TIC-101 | The sealer setpoint was written by an unapproved host | Critical alarm |
| Robot stopped | RB-101 | The robot enable was written off by an unapproved host | Critical alarm |
| Register scan | PLC-101 | An unapproved host is scanning the controller | Warning |
| High limit | TT-101 | The sealer temperature is over its high limit (the window shows the limit in force, for example "High 190 °C") | Warning |
| Blocked | FW-30x | A firewall stopped an attempt | **Information, not an alarm** |

The Blocked window never flashes, is never marked first out, and is not counted in the number of active alarms, because nothing is wrong in the plant when a firewall does its job.

### 4.2 States, in words

Every state is written as text in the window, never shown by colour alone.

| Text in the window | Meaning |
|---|---|
| NORMAL | Nothing wrong |
| #1 ALARM · UNACK | Active alarm, number 1 in the order raised, not yet acknowledged. It flashes. |
| #1 ALARM · ACK | Active and acknowledged. The flashing stops. |
| #1 RETURNED · UNACK | The condition has gone away but nobody has acknowledged it yet |
| #1 RETURNED · ACK | Acknowledged and back to normal |
| SILENT · LIMIT WIDENED | Only on the TT-101 window: the setpoint is raised but the widened limit means no process alarm (chapter 7) |

A status line above the windows reads, for example, "2 ACTIVE · 1 UNACK · FIRST OUT: TIC-101 SP CHANGED".

### 4.3 First-out, acknowledge and reset

- **First out.** The alarm that came first in the current sequence carries a **FIRST OUT** mark. It stays on that alarm until Reset, whatever else happens. If an attack is followed a few seconds later by the TT-101 process alarm, the setpoint alarm is first out and TT-101 is a consequence.
- **Ack all** stops the flashing and changes nothing else.
- **Restore from HMI-Line1** puts the process back. The alarm then shows RETURNED, and stays listed until it has been acknowledged and reset.
- **Reset** removes the alarms that are both acknowledged and back to normal, and clears the first-out mark.

When the viewer's system asks for reduced motion, the page's style sheet switches the flashing animation off. The state text still says UNACK, so nothing depends on the flashing.

---

## 5. Firewall rules and Segmentation

> **In plain words.** Four switches on the page turn four over-broad firewall rules off, one by one. The Segmentation tab then shows what that does to the whole factory: which zones can talk to which, whether a particular message would get through, and how many machines a compromised office computer could reach. It also lets you compare with a **flat network**, one with no walls at all.

**SIMULATED: demo rules, not a recommendation for a real plant.**

### 5.1 The four switches

Each firewall has one switch controlling one rule: the **as-found over-broad allow** for hosts that are not approved. They start as found, every one **ALLOW**, which is the state these paths were actually in when the model was written. Setting a switch to DENY removes that one over-broad rule.

| Switch | Rule | What it allows while it is ALLOW |
|---|---|---|
| FW-301 | SEG-301 | Anything arriving from the internet or the VPN pool may reach the plant networks (level 5 to level 4, any port) |
| FW-302 | SEG-302 | Any office workstation may carry on past the DMZ servers it is meant to stop at (level 4 to level 3.5, any port) |
| FW-303 | SEG-303 | Anything that reached the DMZ may carry on down into operations (level 3.5 to level 3, any port) |
| FW-304 | SEG-304 | Any host may speak Modbus (port 502) or DNP3 (port 20000) across the level 2 to level 1 boundary, in either direction |

### 5.2 Approved flows

Some traffic is legitimate, and no switch touches it. The model holds six **approved flows**, each with its own fixed rule:

| Flow | From | To | Protocol and port | Note |
|---|---|---|---|---|
| hmi-plc1 | HMI-Line1 | PLC-Line1 | Modbus/TCP 502 | The operator screen for line 1: the approved master, read and write |
| hist-plc1 | HIST-01 | PLC-Line1 | Modbus/TCP 502 | The historian polls read-only |
| hist-plc2 | HIST-01 | PLC-Line2 | Modbus/TCP 502 | The historian polls read-only |
| eng-plc1 | ENG-WS-01 | PLC-Line1 | Modbus/TCP 502 | The engineering workstation. Its change window is a procedure, not a firewall rule |
| eng-plc2 | ENG-WS-01 | PLC-Line2 | Modbus/TCP 502 | As above |
| rtu-scada | RTU-Outstation-3 | SCADA-SRV-01 | DNP3 20000 | The one configured outstation |

That is why the traffic log keeps filling even with all four switches set to DENY: the polling is approved traffic.

### 5.3 How a path is judged

The decision is one small function, `canPass`. Given a path (a start zone, an end zone, a port, and whether an approved flow covers it) and the switch settings, it works as follows:

1. Find the conduits between the two zones, nearest the start first.
2. At a conduit with **no firewall**, the path passes. This is a **gap**.
3. At a conduit with a firewall, an **approved** path passes. Any other path is stopped if that firewall's switch is DENY **and** the rule covers the port. Rules for FW-301, FW-302 and FW-303 cover every port; the rule for FW-304 covers only ports 502 and 20000.
4. **The first DENY on the route wins.** Nothing past it is reached.

Which attacks get through therefore follows from which firewalls lie between their two ends. This table is from the project README and is checked by `tests/test_segmentation.py` against every combination of the four switches.

| Path | From to | Stopped by |
|---|---|---|
| All three live attacks | Office (level 4) to PLC-101 (level 1) | Any one of FW-302, FW-303, FW-304 |
| Alert 1, office PC writes a coil | Level 4 to level 1 | Any one of FW-302, FW-303, FW-304 |
| Alert 5, unit ID and port sweep | Level 4 to level 1 | Any one of FW-302, FW-303, FW-304 |
| Alert 4, VPN pool to the HMI | Level 5 to level 2 | Any one of FW-301, FW-302, FW-303 |
| Alert 7, failed OPC UA logins | Level 4 to level 2 | FW-302 or FW-303 |
| Alert 6, DNP3 from an unknown outstation | Level 1 to level 2 | FW-304 only |
| Alerts 2, 3 and 8 | Level 3 or level 2 to level 1 | **No switch**, because they come from approved hosts |

The last row is the important one. A program download outside the change window, a setpoint written outside its normal range, and a workstation polling registers all come from hosts a firewall is right to allow. **A firewall rule sees source, destination and port, not the change window or the value being written.**

### 5.4 The Segmentation tab

The tab has four parts, and the four switches drive all of them together. The tab shows its own copy of the four switches. That copy and the one on the Live tab are two views of one state: set a switch in either place and both change.

**Segmented and flat.** A **Segmented** and **Flat network** pair of buttons switches the mode. In flat mode there are no zones, no VLANs and no firewalls: every host can reach every other. **Show zones in 3D** outlines each level as a box with a plate giving its subnet and VLAN (for example "L4 · 10.10.50.0/24 · VLAN 50"). One stripe pattern marks only the picked or focused zone, and the plate text, not the pattern, carries the meaning. In flat mode one outline wraps the whole plant and its plate reads "One flat network · no VLANs · nothing between the levels".

**The reach counter.** It answers: *if OFFICE-PC-14 is compromised, how many of the other addressed hosts can it reach?* "Addressed hosts" means the 22 items that have a network address: the 14 in the project asset file and 8 more with addresses invented for the demo (VPN-GW-01, ERP-SRV-01, MES-SRV-01, AD-OT-01, DCS-OPS-01, DCS-SRV-01, DCS-CTRL-01 and ROBOT-Pick-1, each marked demo-only in a fold under the counter). The counter asks about the other 21. It is counted on Modbus/TCP port 502, the live attacks' protocol, and shows three measured states plus the switches as they stand:

| State | Hosts reached, of 21 |
|---|---|
| One flat network, no segmentation | 21 |
| Segmented, as found: all four switches ALLOW | 21 |
| Segmented, all four switches DENY | 1 (only ERP-SRV-01, which is in the same zone as the office PC) |

*Measured on 2026-11-16, by the page's own counter, which is checked by `tests/test_reach.py` against a second implementation written independently in Python.* The point of the second row is that, as found, the segmented plant reaches exactly as many hosts as a flat one: the walls exist but have an over-broad door in every one.

**The flow matrix.** A grid with source zone by row and destination zone by column, under a protocol picker (Modbus/TCP 502, DNP3 20000, OPC UA 4840, RDP 3389). It is **directional**: the cell for level 4 to level 1 and the cell for level 1 to level 4 are different. Each cell says **Allowed**, **Denied at FW-xxx**, or **Allowed, no firewall** where the route crosses only a gap. A **diagonal** cell, a zone to itself, reads "Same zone, no conduit": traffic inside one zone crosses no conduit, so no firewall ever sees it. Upward flows such as the DNP3 alert (level 1 up to level 2) are handled like any other. Choosing RDP shows that FW-304's rule does not cover that port. Clicking a cell lights that path in the 3D view, with a visible break where a conduit has no firewall and a stop at the first deny. On a phone the matrix scrolls sideways inside its own labelled region that a keyboard can reach.

![The Segmentation tab's flow matrix with FW-304 set to DENY: the rows for level 1 and level 0 show every path up to the columns shown (levels 5 to 3) denied at FW-304, while same-zone cells read "Same zone, no conduit". SIMULATED.](images/manual/segmentation-matrix.png)

**The path test.** Choose a source host, a target host and a protocol. The result lists each conduit in order, the firewall that allows or denies, the **unfiltered gaps** ("no firewall: an unfiltered gap, nothing to set"), and approved flows called out as fixed rules. It ends with ALLOWED, ALLOWED · APPROVED FLOW, or STOPPED AT FW-xxx. The path is drawn in 3D.

### 5.5 What this tab does not tell you

It tells you what the demo's own rules do. It is not a measurement of any real network, and the rules, subnets and VLAN numbers are demo values. The reach counter counts addressed hosts on one protocol; it is not the planned blast-radius feature (chapter 1.5).

---

## 6. Limits, AlarmOps and What-if

> **In plain words.** An alarm limit is the number at which a control system calls for a person: a tank that is too full, a sealer that is too hot. The Limits tab lets you try to change one, and asks AlarmOps whether the new limit would still catch the faults the old one caught. The What-if tab lets you drive the invented process yourself and see what goes wrong.

**SIMULATED.** Every number on both tabs comes from replaying a generated dataset or running the page's own simplified model. Nothing is sent to a plant.

### 6.1 The Limits tab

![The Limits tab after pressing "Widen the sealer high limit to 250 °C". The page was opened from a file, so the result shown is the recorded one and says so: BLOCKED (RECORDED), detection 100.0% to 85.7%, 30 of 35 faults. SIMULATED.](images/manual/limits-blocked.png)

The tab shows one **tag** at a time (there are five: tank level, pump pressure, flow rate, sealer temperature and conveyor speed) with its four limits: **low low**, **low**, **high** and **high high**. A limit set must keep the order low low < low < high < high high.

- **At first** the tab shows the **baseline replay**: the limits in force, replayed against the dataset. On the shared plant that is 35 of 35 labelled faults caught and no false alarms (chapter 10).
- **Edit the limits** and press **Check change**. The page asks the server's `compare` route to replay the dataset with your numbers and put the result through the gate.
- **The answer** is either **Passes the gate** or **Blocked**. It shows the detection rate before and after, the false alarm count, why (for example "detection rate 85.7% is below the minimum 90.0%"), and a list of the faults the change would stop catching.
- **A single button**, **Widen the sealer high limit to 250 °C**, loads the one change the page ties to the live attack: sealer high from 190 to 250 °C, with high high moving from 205 to 265 so the order stays valid.
- **The equipment lights up.** The tag the limit belongs to (for example `TT-101`) lights on the plant and in the equipment list, and the 3D view draws a line from the device that measures it to the controller that reads it.

**Current and recorded.** Check change needs the server. When no server is running, the page says so and shows a **recorded** answer instead: the result of the baseline replay and of the 250 °C sealer preset, saved inside the page when it was built. The badge then reads **Recorded** and **Check change** is disabled. A test (`test_page_recorded_copy_matches_the_api`) checks that this saved copy still equals what the routes return. If the page is hosted somewhere that answers `/api/...` with an error page, a web page or text that is not JSON, the page treats the server as missing and goes back to the recorded copy. A reply that is JSON with a `detail` message, such as a complaint about a bad limit, counts as the server speaking and is shown as "Not checked: ...".

**The third route.** The server also has a `monitor` route that does a drift check over a bundled, simulated log of alarm counts after a release. The page does not call it. It is described in chapter 10.

### 6.2 The What-if tab

The What-if tab is a **simplified demo model, not plant physics**, and the page says so beside the controls. You can change four inputs: the **sealer setpoint** (100 to 260 °C), the **conveyor motor speed** (0 to 2,000 rpm), the **tank level** (0 to 100 %) and whether the **pump is running**. The rules are these, and nothing more:

- The sealer temperature moves 6 % of the way towards its setpoint on each step.
- Packs arrive in proportion to the conveyor speed: 42 a minute at the nominal 1,200 rpm. The robot picks at most 45 a minute, and anything above that becomes a backlog.
- The pump holds 5 bar while it is running and the tank is above 10 %. Below that it runs dry and the pressure falls towards 1 bar. Switched off, it reads zero.
- The flow follows the pressure: 120 m³/h at 5 bar.

These four rules are enough to make the machines go wrong in ways you can see. The sealing bars glow orange then red and the page writes "Film burns on the bars". Push the conveyor past 1,500 rpm and packs pile up behind the robot. Fill the tank to 100 % and it overflows. Empty it and the pump runs dry. Every state is written as words as well as shown as colour, and nothing flashes if the system asks for reduced motion.

**Comparing two sets of limits.** The same readings are compared against two sets of limits side by side, the **current** ones and the **proposed** ones. The button **Propose sealer high 250 °C** loads the same change as the Limits tab, and then setting the sealer to 230 °C shows the current limits raising **High high** and the proposed limits raising nothing, with a sentence spelling out what that would mean. This comparison is **instant**: it ignores the deadband and delay that the real gate applies, and the page says so.

**How it relates to the live plant.** The sandbox keeps its own inputs and state and never writes to the live plant. While the What-if tab is open the live traffic pauses; leaving the tab puts the live plant back exactly as it was, including any alarm still showing. The **proposed limits** are shared between the Limits tab and the What-if tab, so a change loaded in one is seen in the other.

---

## 7. The Quiet attack control and the HMI write demo

> **In plain words.** What if someone loosened the alarm limit first, and then attacked? This control shows that world. With the limit widened, the sealer attack is still noticed by the security alarm, but the alarm that would have said "the sealer is too hot" never fires, because the sealer has not yet reached the widened limit. The attack becomes quiet in the process.

**SIMULATED.** The control is on the Live tab, under the attack buttons.

![The Live tab with the alarm limit WIDENED, after the sealer setpoint attack. The TIC-101 security window is lit and first out; the TT-101 window reads "High 250 °C" and "SILENT · LIMIT WIDENED". The table beside it compares both limit states at the commanded 240 °C. SIMULATED.](images/manual/quiet-attack.png)

### 7.1 What the control is, and is not

The control, **Alarm limit**, has two settings: **AS PROTECTED (190 / 205)** and **WIDENED (250 / 265)**. The numbers are read from the model: the protected pair from the AlarmOps baseline, the widened pair from the same preset the Limits tab loads.

**WIDENED stands for a limit change that was not blocked.** AlarmOps blocks that change in the Limits tab (the recorded result is a detection rate falling from 100.0 % to 85.7 %). This control shows the world where the block did not happen. The box says so on the page, and says that **the attack does not feed AlarmOps, and AlarmOps does not watch the attack**.

### 7.2 What happens, in both states

| Limit | Security alarm after the 240 °C write from the office PC | Process alarm TT-101 |
|---|---|---|
| As protected (190 / 205) | Raised | Raised once the sealer passes 190 °C, a few seconds later. It is not first out; the security alarm is. |
| Widened (250 / 265) | Raised | **Not raised.** The TT-101 window reads "SILENT · LIMIT WIDENED". A line under the annunciator reads "TT-101: no process alarm at 240.0 °C commanded. Limit is 250 °C, widened from 190 °C." |

With the limit widened, the sealer still climbs towards 240 °C, the temperature at which the page's own notes say film can burn onto the sealing bars. What changed is that the alarm that would have told an operator about it is silent. TT-101 would still fire at 250 °C, and a test forces the setpoint to 260 °C to show that it does.

**The side-by-side table.** After the write, a small table compares both limit states under the heading **at the commanded 240 °C**. It is what the model gives for that value, **not a measurement** of the sealer. It reads "Security alarm: raised" in both columns, and "Process alarm (TT-101): raised (high high)" under the protected limit against "not raised" under the widened one. On a phone the box folds, and a one-line outcome stays outside the fold so a visitor sees the difference without opening it.

### 7.3 Changing the limit during an attack

Changing the limit mid-attack re-judges TT-101 at once.

- Switching to **protected** while the sealer is already over 190 °C raises TT-101, and an earlier security alarm **stays first out**.
- **Widening while TT-101 is active** returns it to normal.
- Switching back to protected afterwards brings it back, unacknowledged.

### 7.4 Why the security alarm is raised, and what the live detector does not catch

The live demo's detector has **two rules**, and both look only at who is sending a message:

1. A write to the controller from a host that is not an approved master raises the security alarm.
2. Three or more reads of unmapped addresses from one unapproved host raises the scan warning.

It does not look at the value being written. **In this live demo's detector the security alarm exists only because the write came from a host that is not an approved master.** A write from an approved source raises no security alarm.

A button, **Write 240 °C from HMI-Line1**, shows this. It sends the same 240 °C write from HMI-Line1, an approved master. The live detector raises no security alarm. With the limit as protected, TT-101 still fires once the sealer passes 190 °C, and it is then the only alarm and so first out. With the limit widened, **nothing fires at all** while the sealer climbs to 240 °C. A button puts the setpoint back to 160 °C afterwards.

This is a limit of the live demo's detector, not of SentinelOT as a whole. **Recorded alert 3** (on the Recorded tab) is a setpoint written from the HMI, an approved master, with the value 9500 where the normal range is 1000 to 3000, and the full pipeline's recorded verdict is **escalate, priority P1**: it caught an approved host by the value. The page's box says this, and points to it.

### 7.5 How the control relates to the Limits and What-if tabs

It is **independent** of them, and **read-only** towards them. It changes only what the Live tab judges TT-101 against. It does not change the Limits tab's current limits, the proposed limits that the What-if tab shares, the AlarmOps results or the recorded copy. A separate button in the box, **Open the Limits tab with the 250 / 265 sealer preset loaded**, does load that preset into the proposed limits that What-if shares. **That button, not the control, does it.** Sharing the control's state with the Limits tab would have made the Limits tab show 250 as the current limit, which is not what the gate compares against.

### 7.6 Under the hood

The decision "does this limit raise an alarm at this value" is a pure function, `alarmRaised`, built on the page's existing `alarmState` function, which the What-if tab also uses. A second pure function, `quietOutcome`, adds the live detector's rule about who is writing. Because the live TT-101 alarm now uses the same function as the What-if tab, it fires **at or above** the limit, where it used to fire strictly above it. `tests/test_quiet_attack.py` checks both functions against a second implementation written independently in Python from the limit table, for both limit sets and a range of values around each limit. The tests check the code against the demo's model, not the model against a real plant.

![The same control on a phone: the folded box's summary states the limit in force, and the one-line outcome sits outside the fold between the attack buttons and the alarm card. SIMULATED.](images/manual/phone-quiet-attack.png)

---

## 8. The equipment list, the 3D controls and phone use

> **In plain words.** Below the plant is a table of everything on it, with its tag and where it came from. The plant itself can be turned, tilted, zoomed and jumped to a level, with a keyboard as well as a mouse. On a phone the same page rearranges itself so the controls fit under a thumb.

### 8.1 The equipment list

Section 06 of the page lists every drawn item: tag, name, type, level, the AlarmOps tag that maps to it (if any) and its **origin**: "Project asset file" or "Demo only". The five signal tags have rows too, marked "Signal, demo only". When an alarm or a blocked limit change lights an item on the plant, its row lights too and says why in capital letters, for example "LIMIT CHANGE BLOCKED" or "HIGH". The full list is in chapter 2.

### 8.2 The 3D view

| To do this | Do this |
|---|---|
| Turn the plant | Drag, or use the arrow keys when the plant has focus |
| Move the view up or down | Page Up and Page Down, the **Up** and **Down** buttons, or Shift and drag, or right-drag |
| Zoom | The **+** and **−** buttons, or the pinch of two fingers on a touch screen |
| See it face-on | **Front view** |
| Let it turn by itself | **Rotate plant** (**Pause rotation** stops it). The plant starts still, not turning, when the system asks for reduced motion. |
| Flat engineering view | **Iso**. **Persp** returns to perspective. |
| Jump to one level | The level keys **L0** to **L5** (and **L3.5**). The other levels fade; press the same key again to bring them back. |
| See what an item is | Click it. A card shows its name and tag, what it does, its type, its address (or what it is wired to), its zone, its origin and its criticality. |

**Tag plates and collisions.** Thirty-plus tag plates cannot all fit on screen at every angle, so some are hidden when they would overlap. The rule for who wins is: a plate that is lit (in alarm) first, then a selected one, then the four firewalls and PLC-101 (what the traces are about), then everything else. A plate hidden at one angle can always be brought back: jumping to its level, with a zoom if needed, shows it. A test walks the plant round in eight steps of 45 degrees, in both cameras, and checks this for every tagged plate.

**Level names** sit in a fixed gutter down the left with a leader line to their floor, so equipment cannot cover them.

### 8.3 The page on a phone

At phone width (about 390 pixels) the page keeps all five tabs on one line using short labels (Live, Recorded, Limits, What-if, Seg), and several things change so everything stays reachable:

- **Fewer plates.** Only the four firewalls, PLC-101 and whatever is lit, selected or on the level you picked keep their plate. The full set would not fit.
- **Folded sections.** The firewall switches, the Segmentation tab's copy of them and the Quiet attack box start folded, so the attack buttons and the annunciator stay close together. Each opens with a tap or from the keyboard and stays open.
- **The attack buttons sit below the plant.** Launching an attack scrolls back up to the plant so the trace is on screen. If you then scroll away to read the alarm, a **Show trace** button appears to bring you back.
- **A compact alarm card.** The first sentence of the analyst note leads, the extra fact rows fold, and the full note is one tap away.
- **The flow matrix scrolls sideways** inside its own labelled region that a keyboard can reach and scroll.
- **Thumb-sized controls.** Buttons, switches and the matrix cells are at least 40 pixels tall.
- **One finger scrolls the page; two fingers move the 3D view.**

A tablet width (about 820 pixels) uses a one-column layout with all the plates.

---

## 9. The AI triage

> **In plain words.** When a security tool raises an alert, a human analyst has to decide: is this serious, or noise? The triage part of the project does a first pass of that work. Five AI agents read the alert in a fixed order, and ordinary computer code checks everything they say before it reaches the analyst. The result is a verdict, a priority, an explanation and a list of suggested next steps. It recommends. It never acts.

### 9.1 What goes in

An alert is a small record (defined in `triage/schemas.py`) with an id, a timestamp, a source (such as `synthetic`), a title, a description, an optional severity from the source tool, an optional protocol (Modbus, OPC UA, EtherNet/IP, DNP3 or PROFINET), source and destination addresses or asset names, and a free-form `raw` field.

Before any AI runs, the server looks up **both ends** of the alert in the asset inventory, `data/assets.json`, which holds the fourteen assets of the project's test plant. Each entry carries a name, type, zone, criticality and a plain-language function, and some carry notes such as a change window (the engineering workstation's approved window is Tuesday 08:00 to 10:00; the jump server's vendor window is Wednesday 09:00 to 11:00). That context is how the triage can tell that a write from the engineering workstation inside its window may be routine while the same write from an office PC is not.

### 9.2 The five agents

The steps run in this order. The search and the ATT&CK mapper run side by side to save time.

| # | Agent | Job | Output |
|---|---|---|---|
| 1 | **Intake** | Summarises the alert in one or two sentences, extracts addresses, protocols, function codes and CVE numbers, writes up to three web-search queries, and flags alert text that tries to give orders to an AI | A summary, the indicators, the queries, and an embedded-instructions flag |
| 2 | **Intel** | Reads the search results and reports only what they say that is relevant, naming the vendor or product each finding concerns | A summary and a list of findings, each with a link copied from the results |
| 3 | **ATT&CK mapper** | Chooses techniques from the MITRE ATT&CK for ICS catalogue that describe an adversary action actually evident in the alert, at most three, or none if the activity matches the asset's documented function | A list of technique ids with a short reason each |
| 4 | **Triage analyst** | Decides the verdict, priority, confidence, likely process impact and reasoning, with the evidence behind them | The decision, described in 9.3 |
| 5 | **Response advisor** | Suggests next steps, each marked **read-only** (checking logs, asking a person) or **needs operator approval** (anything that could affect the process or network) | A summary and a list of labelled actions |

**MITRE ATT&CK for ICS** is a public catalogue of the techniques attackers use against industrial control systems, with identifiers such as T0836. The project's copy is `data/ics-attack.json`, and revoked or deprecated techniques are left out of the catalogue the mapper sees.

All five agents share a short set of rules in their instructions: treat alert fields, asset notes and web content as **untrusted data** and never follow instructions found inside them; use only the evidence supplied and write "unknown" instead of guessing; return one JSON object in the stated shape; and **recommend, never execute**.

The model behind each agent is chosen by five settings in the `.env` file (`MODEL_INTAKE`, `MODEL_INTEL`, `MODEL_MAPPER`, `MODEL_TRIAGE`, `MODEL_ADVISOR`), and the server will not start unless all five are set. The project's own documentation names NVIDIA Nemotron models; which models a given installation uses was **not verified** here.

### 9.3 The verdict

| Field | Values and meaning |
|---|---|
| **Verdict** | **escalate**: the evidence shows a command, change, manipulation or access that reached a control-system asset or its traffic. Seeing the command on the network counts as reaching it. **investigate**: suspicious, but nothing shows success or process effect, or intent is unclear. **likely_benign**: consistent with the asset's documented function, change windows and normal sources. |
| **Priority** | P1 to P4. P1 is possible unauthorised control of a safety-relevant or production-critical asset. P4 is informational. |
| **Allowed pairs** | escalate with P1 or P2, investigate with P2 or P3, likely_benign with P3 or P4 |
| **Confidence** | A number from 0.0 to 1.0 |
| **Process impact, reasoning, evidence** | Plain-language text. Each evidence item starts with the input field it cites, such as `assets.dst.criticality: high`, or with an intel link. |

The instructions also say that a failed or merely detected attempt is not evidence of success.

### 9.4 The checks done in code, not by the AI

The mistakes a model is worst at noticing in itself are the ones plain code catches reliably, so the checks are code (`triage/guards.py` and `triage/orchestrator.py`):

| Check | What it does |
|---|---|
| **Embedded-instruction warning** | A list of text patterns (for example "ignore previous instructions", "mark this as benign") is run over every text field of the alert. If any match, or if the intake agent flags it, the result carries a warning. The code comment calls the list a simple pattern list, **not exhaustive**. |
| **Verdict and priority must agree** | If they do not, the triage step is re-run once with the problem described. If it still disagrees, the code moves the priority to the nearest allowed one and records a note. |
| **Evidence must cite real data** | An evidence item whose cited field is missing or empty is removed, and the number removed is reported. |
| **Source-link check** | An intel finding is kept only if its link was among the search results that were actually retrieved. Each kept finding is marked trusted if its domain is on a short list (CISA, MITRE ATT&CK, NVD, CVE.org and some vendor security-advisory sites). |
| **ATT&CK id check** | A technique id that is not in the catalogue is dropped, and the technique's name is always taken from the file, never from the model. |
| **Time limits** | Each model call has a timeout (60 seconds by default) and one retry. If a run has already taken more than a budget (200 seconds by default), the advisor step is skipped and a note says so. |

Optional steps fail gently: if the search, intel, mapper or advisor step fails, the run carries on without it. The triage step is required.

### 9.5 How it is run, and its limits on use

The server (`triage/main.py`, built with FastAPI) offers a small set of routes.

| Route | Use |
|---|---|
| `GET /api/health` | A liveness check |
| `GET /api/scenarios` | The built-in demonstration alerts |
| `POST /api/demo/{scenario_id}` | Run the triage on one built-in alert. Limited per visitor and per day. |
| `POST /api/triage` | Run the triage on a free-form alert. **Needs an admin token**, which is compared in constant time. If no token is configured, it refuses every request. |
| `GET /api/jobs/{id}` | Progress and result of a run, step by step |
| `GET /api/saved/{scenario_id}` | The last saved result for a scenario |

The public demo route is limited by two settings: **10 runs per visitor per hour** and **200 runs per day** by default. Each run is saved to a small local database. The triage interface, `static/index.html`, is a single web page that talks to these routes. It needs the server and does not work without one.

### 9.6 How alerts are brought in: the ELK adapter and the sniffer

Two small programs feed alerts from an outside environment to the triage. Both only listen. Neither sends anything to a control network. The ELK adapter reads from an Elasticsearch server, the sniffer reads network frames or a saved capture, and each posts the alerts it builds to the triage server's own `/api/triage` route. They are described by the project as built for an external home-lab environment, and the project's own notes state: **built, not yet run against the lab, so there are no lab results.** What this manual can verify is that the code exists and that ten offline tests (`tests/test_lab.py`) pass against stub data. A real lab run is **not verified**.

**The ELK adapter** (`triage/lab_elk.py`) reads alert documents from an Elasticsearch index, the store used by the ELK logging stack, and posts each as an alert. It tries both Elastic Common Schema field names and Suricata EVE field names, so either style maps without extra setup, fills in the protocol from the destination port if the document does not name one (502 as Modbus, 4840 as OPC UA, 44818 as EtherNet/IP, 20000 as DNP3), and caps the number of alerts per poll because each one costs a full triage run. A `--dry-run` option prints what would be sent.

**The Modbus sniffer** (`triage/lab_sniffer.py`) listens passively on a mirror port or reads a saved capture, parses Modbus/TCP messages, and applies three fixed rules:

| Rule | Fires when |
|---|---|
| `unapproved_write` | A write function code (5, 6, 15, 16, 22 or 23) comes from a host that is not on the approved writers list |
| `unapproved_master` | A read request comes from a host that is not an approved master |
| `scan` | An unapproved host touches many different unit, function and address targets in a short time: by default 20 distinct targets within 60 seconds |

An alert is raised at most once per rule, source and destination every five minutes, so a burst of messages does not start a burst of triage runs. The scan threshold here (20 targets in 60 seconds) is not the same as the 3 reads the 3D page's demonstration rule uses. Like the page's rules, **none of these three rules looks at the value being written**; the value-aware judgement comes from the triage that reads the alert afterwards.

### 9.7 The eight recorded alerts on the page

The page's **Recorded** tab holds eight alerts and the verdicts the pipeline returned for them in its evaluation run on 6 October 2026. Picking one traces it on the plant and says where it would stop under the firewall rules you have set. The alerts are invented.

| # | Alert | Path | Verdict, priority | ATT&CK technique |
|---|---|---|---|---|
| 1 | Modbus write coil to PLC from an office PC | 10.10.50.7 to 10.10.20.11, Modbus | escalate, P1 | T0835 Manipulate I/O Image |
| 2 | PLC program download outside the change window | 10.10.40.8 (engineering workstation) to 10.10.20.12, Modbus | escalate, P1 | T0843.001 Download All |
| 3 | Setpoint written outside its normal range | 10.10.30.5 (HMI) to 10.10.20.11, Modbus | escalate, P1 | T0836 Modify Parameter |
| 4 | New remote session to the HMI from the VPN pool | 10.10.90.14 to 10.10.30.5, RDP | investigate, P2 | T0822 External Remote Services |
| 5 | Modbus unit ID and port sweep from a new host | 10.10.50.99 to 10.10.20.11, Modbus | investigate, P2 | T0846.001 Port Scan |
| 6 | DNP3 responses from an unknown outstation | 10.10.20.99 to 10.10.30.10, DNP3 | investigate, P2 | T1692.002 Reporting Message |
| 7 | Repeated failed OPC UA logins | 10.10.50.7 to 10.10.30.10, OPC UA | investigate, P2 | T0822 External Remote Services |
| 8 | Engineering workstation reading PLC registers | 10.10.40.8 to 10.10.20.11, Modbus | likely_benign, P4 | none |

Alerts 2, 3 and 8 come from approved hosts, so no firewall switch stops them (chapter 5). That is deliberate: it is the point at which a firewall's view (who, where, which port) runs out and the triage's view (what, when, how much) begins.

### 9.8 How well it did, and how far to trust that

The recorded runs are in the `results/` folder as CSV files. The figures below were **re-derived on 2026-11-16 by reading those files**, not by calling the models again.

| Set | Runs | Verdict matched the label written beforehand | Technique acceptable |
|---|---|---|---|
| Fresh held-out set (10 scenarios, 3 runs each) | 30 | 29 | 28 |
| Development set (12 scenarios, 3 runs each, used for tuning) | 36 | 29 | 23 |

Across all 100 recorded run rows that carry a time, the **median time per alert was 26.4 seconds** (fastest 11.05, slowest 513.43). The project's evaluation page quotes a median of about 26 seconds over 66 runs; which 66 runs those are was not worked out here, so only the 100-row figure is relied on. The scenarios total 32 built-in alerts (12 development, 10 held-out and 10 in a second held-out set).

**Not verified:** the project reports a controlled prompt-injection test (0 of 10 injected runs followed the hidden instruction). Its raw output is not among the committed files, so it was not re-measured and the figure is not relied on here.

Read these figures with the limits the project itself states: the sample sizes are small, so three runs of one scenario are not independent evidence; one person set the labels, with AI assistance, and nobody independent reviewed them; all the data is synthetic, with no real plant alerts and no working analysts; and technique choice is noisy, so technique suggestions are hints for an analyst to check.

### 9.9 What it cannot do

- **It cannot act.** It cannot isolate a host, block a port or change a controller. Every action is a suggestion for a person.
- **It cannot check what it is told.** A change-ticket reference in an alert is text to it; it has no way to look the ticket up. Benign verdicts lean on notes in the asset inventory and on what the alert text says.
- **It can under-call a real threat.** The project's own notes record one run in which a detected exploit attempt was called likely benign.
- **It sees only what is sent to it.** It never looks at network traffic itself. In the lab design a passive sensor sits on a mirror port, and traffic that a firewall stopped upstream never reaches that sensor, so there is nothing for the triage to judge.
- **It needs a running server and outside services.** The agents call a hosted model service, and the search step calls a web-search service; both need keys held on the server. Neither is available on a static host (chapter 14).
- **Its injection defence is a heuristic.** The pattern list is not exhaustive, and the agents' instructions to ignore embedded commands are not a guarantee.
- **It is a research prototype, not a production security tool**, in the project's own words.

---

## 10. AlarmOps: the alarm-limit gate

> **In plain words.** Alarm limits get edited over the years. Set too wide, a real fault passes in silence. Set too narrow, operators drown in alarms they learn to ignore. AlarmOps measures a proposed limit instead of arguing about it: it replays a set of readings whose faults are already labelled and counts how many faults the new limits would still catch. If too few, the change is blocked.

### 10.1 What AlarmOps is here

AlarmOps is a separate project. A copy of it sits unmodified in the `alarmops/` folder and is used as a library. **Only one file, `triage/alarm_limits.py`, imports it**, and that file adds three read-only routes. In its own repository, AlarmOps also runs this replay on every proposed edit through a continuous-integration pipeline, writes a change record, deploys to staging, waits for a person before production and watches the alarm rate afterwards. **That pipeline does not run in this repository.** This repository carries out no staging, approval or deployment.

### 10.2 What the gate checks

The alarm logic for each tag has four limits (low low, low, high, high high), a **deadband** (how far back from a limit a reading must fall before the alarm clears, to stop flicker) and a **delay** in samples (how long a reading must stay beyond a limit before the alarm counts). For example the tank has a deadband of 2 and a delay of 3 samples.

The replay runs that logic across the readings with a given set of limits. A labelled fault counts as **caught** if an alarm for its tag fires inside the fault's window. An alarm that fires outside every window is a **false alarm**.

The gate (`plant/gate.yaml`) then applies four thresholds:

| Threshold | Value |
|---|---|
| Minimum share of faults caught | 90 % |
| Largest allowed fall in that share compared with the limits in force | 5 percentage points |
| Largest allowed number of false alarms | 3 |
| Largest allowed rise in false alarms compared with the limits in force | 2 |

A change that breaks any of them is **blocked**, and the answer lists the faults it would have missed. The file states that **these thresholds are policy choices for this simulation, not an industry standard.**

### 10.3 The dataset, and what it is worth

**Part of the dataset is generated for the demo and is not independent evidence.** In detail:

- A seeded generator writes 6,000 readings for each tag: a slow wave with noise, into which it injects labelled faults of three kinds, **spikes**, **drifts** and readings that **freeze** (stuck). Each fault is recorded with its tag, kind, direction and the sample numbers at which it starts and ends, so the file knows the right answer.
- The original AlarmOps dataset has **3 tags and 21 labelled faults** (tank level, pump pressure, flow rate; 7 each).
- The shared plant adds two tags for the packaging line, **sealer temperature and conveyor speed**, with 7 more faults each. These **14 extra faults, F22 to F35, were generated for this demo by the same seeded generator**, run once more with two extra tags. The shared plant's 35 faults are 15 spikes, 10 stuck and 10 drifts (counted on 2026-11-16).
- The faults and readings are made up by a program. They describe what the gate does on made-up data. They say nothing about how a real plant's alarms behave.

The extra faults exist so the sealer and the conveyor have something to be measured against. They are the reason the sealer's 250 °C widening can be shown blocked at all.

### 10.4 The three routes

All three accept GET only and store nothing. A proposed change exists only in the reply.

| Route | Answer |
|---|---|
| `GET /api/alarmops/baseline` | The limits in force, replayed, with every tag's faults and the equipment it belongs to |
| `GET /api/alarmops/compare` | One tag's edited limits, replayed and put through the gate: passed or blocked, which faults are newly missed, and why |
| `GET /api/alarmops/monitor` | A drift check over a bundled, simulated log of alarm counts after a release (one healthy log and one drifting log) |

At most four replays run at once. An environment setting can point the routes at the original AlarmOps files instead of the shared plant. The details of the `monitor` route's drift logic were **not verified** beyond this description.

### 10.5 The blocked rates, exactly as measured

*Measured on 2026-11-16 by calling the routes in this repository and reading the answers.*

**The original AlarmOps dataset** (3 tags, 21 labelled faults):

| Limits | Result |
|---|---|
| As they stand | 21 of 21 faults caught, 0 false alarms |
| Tank widened to 88 / 95 (high / high high) | **Blocked.** Detection 100 % to 81.0 %, 17 of 21. Four tank faults missed (F04 to F07). Violations: detection 81.0 % is below the 90.0 % minimum, and it fell by 19.1 points, more than the 5.0 allowed. |
| Tank tightened to 75 / 88 | **Passes.** 21 of 21 |

**The shared plant dataset** (5 tags, 35 labelled faults):

| Limits | Result |
|---|---|
| As they stand | 35 of 35 faults caught, 0 false alarms |
| Tank widened to 88 / 95 | **Blocked.** Detection 100 % to 88.6 %, 31 of 35. The same four tank faults missed. Violations: below the 90.0 % minimum, and a fall of 11.4 points. |
| Tank tightened to 75 / 88 | **Passes.** 35 of 35, 0 false alarms |
| Sealer high raised from 190 to 250 °C, high high from 205 to 265 | **Blocked.** Detection 100 % to 85.7 %, 30 of 35. Five sealer faults missed (F22, F24, F25, F26 and F28). Violations: below the 90.0 % minimum, and a fall of 14.3 points. |

The two tank rows disagree on percentages because they count the same four missed faults out of different totals (21 and 35). **The 14 extra faults are not independent evidence.** The sealer row's result depends entirely on them.

### 10.6 What the gate does not do

- It does **not** enforce anything here. It answers a question. Nothing in this repository stops anyone widening a limit somewhere else.
- It measures only **detection of the labelled generated faults** and false alarms on generated readings. It does not know what a fault would do to a real process.
- It covers **five tags**. A change to any other alarm is outside it.
- On the 3D page it appears only on the Limits tab. The live attack on the Live tab is not run through it (chapter 7).

---

## 11. How an attacker would attack each part

> **In plain words.** To defend something you have to understand how it can be attacked. This chapter describes, for each part of the simulated plant, the weakness an attacker would look for, why it works, and what it would do to the machines. It is written at the level of ideas only. It contains no exploit code and no step-by-step instructions, and it describes only attacks that the simulation itself shows.

**SIMULATED.** Every attack below is an invented event on an invented plant. The firewall rules are demo rules, not a recommendation for a real plant. Where a statement about how a protocol or a technique works in general is **background knowledge** rather than something this manual's author checked in the code, it is marked **background, not verified here**.

Chapter 12 explains how the platform detects and prevents each one, and where each defence falls short.

### 11.1 The attacker's view of the plant

An attacker who has reached the office network, and in particular a single ordinary desk computer such as OFFICE-PC-14 on level 4, wants to reach something that moves product or heat. In this plant that means the line 1 controller, PLC-Line1 on level 1, which runs the heat sealer, the conveyor drive and the packing robot. Between the two lie six levels, three firewalls and one unfiltered gap. The attacks below are the ways across, and the ways to stay unnoticed afterwards.

### 11.2 Attack 1: writing a new setpoint to the controller

| | |
|---|---|
| **Asset** | PLC-Line1 (PLC-101), and through it the sealer's temperature setpoint (TIC-101). The sender is OFFICE-PC-14. |
| **Weakness** | The controller does what a well-formed write message asks, from whoever can reach it. In this demo the only thing between an office computer and the controller is the firewall rules, and as found every one of the four over-broad rules is ALLOW. *Background, not verified here:* the Modbus/TCP protocol itself has no built-in login. |
| **Why it works** | A write to a register looks the same whoever sends it. The path from level 4 to level 1 crosses FW-302, FW-303, an unfiltered gap and FW-304, and each firewall in the as-found state passes it. |
| **Process effect** | The setpoint changes from 160 °C to 240 °C. The sealer climbs past its 190 °C high limit. The page's note says film can burn or melt onto the sealing bars and the line may need to stop for cleaning. |
| **How detected** | The live demo's first rule raises a critical TIC-101 alarm, because the write came from a host that is not an approved master. The TT-101 process alarm follows a few seconds later. None of the eight recorded alerts is exactly this write; the nearest, an office PC writing a coil (alert 1), has the recorded verdict escalate, P1. |
| **How prevented** | Setting any one of FW-302, FW-303 or FW-304 to DENY stops it. Restoring the setpoint from the operator screen undoes the effect. |

### 11.3 Attack 2: switching a machine off

| | |
|---|---|
| **Asset** | The packing robot's enable coil (00003) on PLC-Line1, which enables ROBOT-Pick-1. The sender is OFFICE-PC-14. |
| **Weakness** | The same as attack 1. A coil is a single on/off bit, so one tiny message changes the state of a machine. |
| **Why it works** | The controller accepts the write. Nothing in the message says who the sender is, and the path is open. |
| **Process effect** | The robot stops while the conveyor keeps running, so product piles up at the end of line 1. The page's note asks the operator to check the cell is safe before re-enabling. |
| **How detected** | The live demo's first rule raises a critical RB-101 alarm. Recorded alert 1, a coil write from an office PC, has the recorded verdict escalate, P1 (technique T0835, Manipulate I/O Image). |
| **How prevented** | The same firewall switches as attack 1. Restore from the operator screen re-enables the robot. |

### 11.4 Attack 3: mapping the controller before the real attack

| | |
|---|---|
| **Asset** | The register map of PLC-Line1, probed from a host first seen today, 10.10.50.99. |
| **Weakness** | A controller answers reads for the addresses it has. For addresses it does not have it answers with an error ("exception 02, illegal data address"). *Background, not verified here:* that difference tells a prober which addresses exist. |
| **Why it works** | Reads look like ordinary monitoring traffic, and the error replies are part of the protocol. A prober learns the controller's layout without changing anything. |
| **Process effect** | None. The page's note says nothing in the process has changed yet and that this is how someone maps a controller before sending a write. |
| **How detected** | The live demo's second rule raises a scan warning after three reads of unmapped addresses from one unapproved host. The lab sniffer would raise a scan alert after 20 different targets in 60 seconds. The recorded verdict for the unit ID and port sweep alert is investigate, P2 (technique T0846.001, Port Scan). |
| **How prevented** | The same firewall switches stop the probe from arriving at all. A scan slower or smaller than the thresholds is not caught by either rule. |

### 11.5 Attack 4: moving through a flat or over-permissive network

| | |
|---|---|
| **Asset** | Every conduit in the plant, and the two conduits that have no firewall: level 0 to level 1 and level 2 to level 3. OFFICE-PC-14 is the starting foothold. |
| **Weakness** | Boundaries that allow everything, and boundaries that are not there. A **flat** network has no internal boundaries at all. As found, this plant's four walls each have an over-broad allow rule. |
| **Why it works** | Traffic crossing a conduit is stopped only if a rule says so. With every switch ALLOW, the segmented plant lets the office PC reach exactly as many hosts as a flat network does. |
| **Process effect** | None directly. It lets one foothold reach controllers, servers and the engineering workstation of the attacker's choosing, and every later attack depends on it. |
| **How detected** | Not by the live demo's rules: reaching a host raises no alarm. The page makes the exposure visible instead: the Segmentation tab's reach counter and matrix show it. |
| **How prevented** | Setting the four switches to DENY drops the office PC's reach from 21 of 21 other addressed hosts to 1 (ERP-SRV-01, in its own zone), measured on 2026-11-16. The two unfiltered conduits have no switch: the model shows them as gaps and offers nothing to set. |

### 11.6 Attack 5: widening the alarm limit first, then attacking

| | |
|---|---|
| **Asset** | The sealer's TT-101 high alarm limit (190 °C, high high 205 °C), then the sealer setpoint as in attack 1. |
| **Weakness** | An alarm limit is only a number, and it can be edited. If nobody measures what an edit loses, a widened limit looks like a harmless tuning change. |
| **Why it works** | With the high limit at 250 °C, a setpoint of 240 °C never crosses it. The sealer heats up and the process alarm that would have told an operator stays silent. |
| **Process effect** | The same as attack 1: the sealer climbs towards 240 °C. What changes is that the process alarm is silent, so the first sign may be damaged film. |
| **How detected** | AlarmOps blocks the widening itself in the Limits tab (detection falls from 100.0 % to 85.7 %, five sealer faults missed). On the Live tab the **security** alarm is still raised, but only if the write came from an unapproved host. The TT-101 window says "SILENT · LIMIT WIDENED". |
| **How prevented** | The gate, if the change goes through it. Nothing in this repository forces a change to go through it. |

### 11.7 Attack 6: using a host the network trusts

| | |
|---|---|
| **Asset** | HMI-Line1, ENG-WS-01 or HIST-01, the hosts allowed to talk to the controllers. |
| **Weakness** | Firewalls and the live detector trust a **host**, not what the host does. If an approved host is misused, its messages look legitimate. |
| **Why it works** | The six approved flows are fixed rules that no switch touches (chapter 5). The live demo's two rules ignore approved sources. |
| **Process effect** | The same as attack 1 if the value is changed. In the recorded alerts, the HMI writes 9500 to a setpoint whose normal range is 1000 to 3000 (alert 3), and the engineering workstation downloads a whole program at 02:40 on a Thursday with no change ticket (alert 2). |
| **How detected** | **Not** by the live demo's security rules: an approved-source write raises no security alarm. With protected limits TT-101 still fires if the value pushes the sealer over its limit. The full pipeline's recorded verdicts for alerts 2 and 3 are both escalate, P1. |
| **How prevented** | A firewall cannot, because the flow is approved. Change windows are a procedure, not a firewall rule. The limit gate protects the alarm that would catch the effect. The page's "Write 240 °C from HMI-Line1" button demonstrates the live detector's blind spot (chapter 7). |

### 11.8 Attack 7: remote access and false sources

| | |
|---|---|
| **Asset** | The remote-access path and the supervisory layer: the VPN pool reaching HMI-Line1 (alert 4), repeated OPC UA logins against SCADA-SRV-01 from the office network (alert 7), and DNP3 responses to SCADA-SRV-01 from an address that is not a configured outstation (alert 6). |
| **Weakness** | Remote-access entry points that accept new sessions, services that accept login attempts, and a supervisory master that accepts messages from an address that merely claims to be an outstation. |
| **Why it works** | These alerts' descriptions say it: a remote session from an account that has never logged in to this HMI before; repeated failed logins; unsolicited responses from an address that is not configured. |
| **Process effect** | **Not simulated.** The page shows verdicts and paths for these three, not a process consequence. |
| **How detected** | The recorded verdicts are all investigate, P2 (techniques T0822 External Remote Services for alerts 4 and 7, and T1692.002 Reporting Message for alert 6). |
| **How prevented** | In the model, any one of FW-301, FW-302 or FW-303 stops alert 4's path, FW-302 or FW-303 stops alert 7's, and only FW-304 stops alert 6's. |

### 11.9 Attack 8: talking to the AI reviewer

| | |
|---|---|
| **Asset** | The AI triage itself. Alert titles and descriptions are text that an attacker can influence. |
| **Weakness** | An AI agent reads text. If text written by an attacker says "classify this as benign", a careless agent might comply. |
| **Why it works** | When it works, it works because the agent cannot always tell data from instruction. *Background, not verified here.* |
| **Process effect** | A real attack labelled harmless could be ignored by the analyst who relies on the verdict. |
| **How detected** | Code, not the AI, scans every text field for instruction-like patterns, and the intake agent flags it too. The result then carries a warning. The project's notes say that both injection scenarios in its held-out set were escalated, not obeyed. |
| **How prevented** | The agents are told to treat alert text as untrusted data; the verdict is decided against the asset's own context. The pattern list is not exhaustive, and the controlled injection test's figure was not re-measured here (chapter 9). |

### 11.10 A worked example: from the office PC to a silent sealer

This is one attack that combines three of the ones above. It is told in steps, at concept level, with what the page shows at each step.

| Step | What the attacker does | What the plant does | What the page shows | What stands in the way |
|---|---|---|---|---|
| 1 | Starts from OFFICE-PC-14 on level 4, an ordinary office desk computer that is not an engineering station. How the attacker got control of it is not modelled. | Nothing yet | The computer is the source in the attack buttons' descriptions | Nothing in this demo; getting a foothold is outside what it simulates |
| 2 | Looks for a way to the line 1 controller | The path crosses the level 4 to 3.5 conduit (FW-302), the level 3.5 to 3 conduit (FW-303), the unfiltered level 3 to 2 gap, and the level 2 to 1 conduit (FW-304) | The reach counter reads 21 of 21 as found. A path test from OFFICE-PC-14 to PLC-Line2 lists the three firewalls allowing and the gap. | Each firewall's switch, if it is DENY. As found none is. |
| 3 | **Loosens the alarm limit first**, so a later attack will be quiet | In the world the control models, the sealer's high limit becomes 250 / 265 instead of 190 / 205 | The Live tab's **WIDENED (250 / 265)** setting. In the Limits tab AlarmOps blocks this change. | The limit gate, **if the change goes through it**. This is the "not blocked" world. |
| 4 | **Writes the setpoint**: 240 °C to the sealer | The sealer climbs from about 160 °C towards 240 °C. Film can burn at the temperatures the page's notes describe. | The trace is drawn from level 4 to PLC-101. The TIC-101 window flashes and is first out. | The unapproved-source rule raises the security alarm. A DENY on a firewall would have stopped the write. |
| 5 | **Stays quiet** | The sealer passes 190 °C, then keeps going | The TT-101 window reads "SILENT · LIMIT WIDENED". The line under the annunciator says no process alarm at 240 °C commanded, limit 250 °C. The comparison table says the process alarm would have been raised under the protected limit. | Nothing: the process alarm that would have caught it is the one that was loosened. |
| 6 | **Variant: sends the write from an approved host instead** | The same | With the limit widened, **no alarm at all**. With the limit as protected, TT-101 fires alone. | The live detector's two rules ignore an approved source. The full pipeline, on a recorded alert like alert 3, escalated an HMI write by its value. |

The lesson of the example is that the defences are layers, and each layer can be made quiet by the one before it. Chapter 12 goes through the layers, and what each cannot do.

---

## 12. How each attack is detected and prevented here

> **In plain words.** The platform has several layers of defence, and none of them is enough alone. Some stop an attack, some notice it, and some warn you before it happens. This chapter goes through each layer, says what it really does, and says plainly what it cannot do. The honest answer for every layer is "it depends on the others".

**SIMULATED: demo rules, not a recommendation for a real plant.**

### 12.1 Layer 1: segmentation and firewall rules (prevent)

**What it does.** The four switches decide whether the as-found over-broad rule at each firewall lets traffic through. The first DENY on a path's route stops the message there, and nothing past it is reached. A message stopped this way raises no alarm, changes nothing in the plant, and is recorded as an informational entry. In the plant model, the three live attacks are stopped by any one of FW-302, FW-303 or FW-304.

**Evidence.** `tests/test_segmentation.py` checks every path the page can draw against every combination of the four switches, against a second implementation written independently in Python. `tests/test_reach.py` does the same for the reach counter and the hop-by-hop path test.

**What it cannot do.**

- **It does not look at the value or the time.** A firewall rule sees source, destination and port. It cannot see that a setpoint is out of range or that a download is outside its change window.
- **It does not stop approved flows.** The six approved flows pass whatever the switches say.
- **Two conduits have no firewall.** The model has no switch for them.
- **FW-304's rule covers only Modbus 502 and DNP3 20000.** Another protocol across that boundary, for example RDP on 3389, is not covered by it (the Segmentation matrix shows this when the protocol picker is changed).
- **A blocked message is invisible to the passive sensor.** The sensor sits between the approved masters and the controller, so frames stopped further up never reach it. The page says so. Segmentation prevents; it does not leave a trail for monitoring.
- **It is a model of demo rules.** It measures nothing about a real network.

### 12.2 Layer 2: approved-flow checks (detect)

**What it does.** The live demo's detector applies two rules, and both look only at **who is sending**:

1. A **write** to the controller from a host that is not an approved master raises a critical security alarm. The approved addresses are HMI-Line1 and the historian.
2. **Three or more reads of unmapped addresses** from one unapproved host raise a scan warning.

The lab sniffer applies the same idea with three rules and different thresholds (chapter 9).

**What the live demo's detector does not catch.**

- **A write from an approved source, of any value.** It raises no security alarm. The page demonstrates this on purpose (chapter 7).
- **A scan below its threshold.** Fewer than three unmapped reads do nothing.
- **Anything it is not given.** It only sees the traffic the page itself generates for the three attacks and the normal polling. It is a demonstration of a rule, not a monitor of a network.
- **Anything about the process.** It looks at messages. Whether the sealer is too hot is a separate alarm (12.3).

### 12.3 Layer 3: process alarms (detect the effect)

**What it does.** The TT-101 alarm fires when the sealer temperature reaches its high limit, and it returns to normal when the temperature falls 10 °C below the limit. It catches the **effect** of an attack on the process whoever caused it. With protected limits it fires on every route that heats the sealer: the office PC's write, or an approved host's.

**What it cannot do.** It is only as good as its limit. With the limit widened to 250 °C it stays silent while the sealer sits at 240 °C. It also fires late: only after the sealer has actually heated up, a few seconds in this simulation, so it is a consequence alarm, not a warning. The TT-101 window and the line under the annunciator say in words when it is silent because of a widened limit.

### 12.4 Layer 4: the limit gate (prevent a quiet change)

**What it does.** AlarmOps replays labelled faults against a proposed limit and blocks a change that would lose too much detection. The sealer's widening to 250 / 265 is blocked: detection falls from 100.0 % to 85.7 % (30 of 35 faults), below the 90 % minimum (chapter 10, measured on 2026-11-16).

**What it cannot do.**

- **It enforces nothing in this repository.** It answers a question. If a change is made somewhere that does not ask, the limit still changes. The Quiet attack control shows that world.
- **Its evidence is partly generated.** The sealer result rests on 14 faults generated for the demo, not on independent data.
- **Its thresholds are policy choices for the simulation,** not an industry standard.
- **It covers five tags** and measures fault detection on generated readings, not what a fault would do to a real process.

### 12.5 Layer 5: the AI triage (judge by context and value)

**What it does.** It reads an alert, the context of both assets, public threat information and the ATT&CK catalogue, and gives a verdict with reasoning. This is the layer that can judge **what was done**, not only **who did it**. Where the live demo's detector would be silent, the recorded results show the full pipeline reaching a different conclusion:

- **Recorded alert 3**, a setpoint written from the HMI (an approved master) with a value outside its normal range, has the recorded verdict **escalate, P1**: the full pipeline caught an approved host by the value.
- **Recorded alert 2**, a program download from the engineering workstation (also approved) outside its change window with no ticket, is **escalate, P1**.
- **Recorded alert 8**, the same workstation merely reading registers, is **likely benign, P4**. The context makes the same host and the same target an expected one.

**What it cannot do.** Chapter 9 lists the limits in full. The ones that matter most here: it recommends and never acts; it works only on alerts that something else raised and sent to it; it cannot check a change ticket; its injection defence is a heuristic; and the evidence behind these results is small, synthetic, labelled by one person, and three runs per scenario. These recorded verdicts are for invented alerts. They are **not** a claim about how it would do against a real attacker.

### 12.6 Which defence answers which attack

Each cell says in words what the layer does for that attack in this platform.

| Attack | Segmentation (prevent) | Approved-flow rules (detect) | Process alarm (detect effect) | Limit gate | AI triage |
|---|---|---|---|---|---|
| 1. Setpoint write from the office PC | Stops it if FW-302, 303 or 304 is DENY | Raises a critical security alarm | TT-101 fires later, if the limit is protected | Protects the limit that makes TT-101 fire | No recorded alert is exactly this write |
| 2. Robot switched off | Same switches | Raises a critical security alarm | The packs tile shows "Stopped", but the page has no process alarm window for it | Not involved | Recorded alert 1, a coil write from an office PC: escalate, P1 |
| 3. Register scan | Same switches | Raises a warning after three unmapped reads | None | Not involved | Recorded alert 5: investigate, P2 |
| 4. Flat or open network | The switches at DENY cut reach from 21 to 1 | Raises nothing for mere reachability | None | Not involved | Not involved |
| 5. Widened limit, then attack | Same switches | Security alarm only if the source is unapproved | **Silent** while the limit is widened | **Blocks the widening in the Limits tab**, if asked | Not involved |
| 6. Misuse of an approved host | **Cannot** stop an approved flow | **Does not catch it** | TT-101 fires if the limit is protected and the value is harmful | Protects the limit | Recorded alerts 2 and 3: escalate, P1 |
| 7. Remote access, false sources | FW-301, 302, 303 or 304, depending on the path | Not applicable to these paths | Not involved | Not involved | Recorded alerts 4, 6 and 7: investigate, P2 |
| 8. Instructions hidden in alert text | Not involved | Not involved | Not involved | Not involved | Code pattern check and flag; the agents are told to ignore it |

### 12.7 Putting it together

The worked example in chapter 11 shows why the layers need each other. Take the office PC's write. Segmentation, if switched to DENY, stops it before it arrives. If it arrives, the live detector's source rule raises the security alarm. If the limit was widened first, the process alarm is silent, and only the security alarm and, upstream of everything, the gate remain. If the write comes from an approved host, the source rule is silent too, the firewalls pass it, and the only things left are the process alarm (if the limit is protected) and the triage's judgement of the value.

No single layer covers every case, and the demo makes that visible on purpose.

---

## 13. What was learned

> **In plain words.** Building a security demo taught several lessons that were not obvious at the start. This chapter records the design decisions, the bugs that were found and how they were fixed, and honestly lists what a real plant would need that this demo does not have.

### 13.1 Design decisions

- **One model, not two.** The page's network model (zones, conduits, flows, and a function that decides whether a path may pass) is the single source of truth. The Segmentation tab, the firewall switches and the reach counter all read it. A second copy of the rules would drift from the first, so none was written.
- **Decisions are pure functions.** The questions "can this path pass?", "who can this host reach?", "does this limit raise an alarm at this value?" are small functions with no screen, clock or network in them, so tests can call them directly.
- **Every pure function has an independent twin in the tests.** The expected answers come from a second implementation, written in Python from the rules' table rather than translated from the JavaScript, so an identical mistake in both is unlikely. Each test file states in its docstring what that proves and what it does not: it **checks the code against the demo's model, not the model against a real plant.**
- **It recommends and never acts.** No part of the project writes to a network or a controller.
- **Everything says SIMULATED.** The plant, the numbers and the rules are invented, and the page, the footer and this manual say so wherever rules and figures appear.
- **Text for every state.** No state is shown by colour or pattern alone: alarms, switches, reach counts, zone plates and the quiet-attack silence all have words.
- **The Quiet attack control is independent of the Limits and What-if tabs.** Sharing its state with them would have made the Limits tab show a widened limit as the *current* one, which is not what the gate compares against.
- **A recorded copy of the gate's answer lives in the page,** so the page is useful on a static host, and a test keeps that copy equal to what the routes return.
- **Only one test hook was added for the Quiet attack,** to reach the 260 °C case without waiting half a minute for the sealer.

### 13.2 Bugs found, and how they were fixed

| Problem | What was wrong | How it was fixed | How it is kept fixed |
|---|---|---|---|
| **Plates hid each other.** | Thirty-plus tag plates overlap at some camera angles, and a firewall or PLC-101 plate could be hidden by a neighbour, which are the very items the traces are about | A priority rule: lit plates first, then selected, then the four firewalls and PLC-101, then the rest. A plate on a faded level gives way to the level in focus. | `test_no_two_plates_overlap_and_lit_ones_stay_on_top`, and an angle sweep, `test_every_plate_can_be_brought_back_at_any_angle`, that walks eight angles in both cameras and checks every tagged plate can be brought back by jumping to its level |
| **Zone plates joined the problem.** | When zone plates were added to the segmentation view, the angle sweep failed. Two causes: a path highlight was lighting five plates as "hot" before anyone asked for it, and the nudging that moves a plate up out of the way could oscillate between two boxes. | The highlight now appears only once the reader picks a path or a cell. Nudging is strictly upward. Zone plates were made narrower, because the level names already sit in a gutter. | The same sweep, with the zone plates turned on |
| **Switch rows were cut by the fold.** | Rows of different heights meant the panel could scroll with a switch cut in half | Every row is one fixed height and snaps to the top on scroll. The long sentence that explains each rule lives in the README, not on the page. | `test_every_switch_row_is_the_same_height_so_none_is_cut_at_the_fold` and `test_scrolling_the_panel_never_leaves_a_switch_row_cut_in_half` |
| **Two copies of the switches.** | The Segmentation tab needed its own copy, and a copy could duplicate element ids and drift from the first | One state behind both, buttons found by a data attribute, never a repeated id | A test that no element id appears twice, and a test that either copy moves both |
| **A variable shadowed the plant state.** | Found while building the Quiet attack: a local variable named `st` inside the annunciator code hid the plant state of the same name, so a new line read an undefined value and the page threw | The local variable was renamed | The Quiet attack tests, which drive the annunciator |
| **An approved write left a table empty.** | Found in a screenshot: with the limit widened, the HMI write raises no alarm, and nothing else redrew the "after the write" table | The write now redraws the table itself | A test that the table is drawn although nothing was raised |
| **A cleared TT-101 alarm could not come back.** | Widening cleared the alarm, but it forgot which limit it had been cleared under, so switching back to protected did not bring it back | A cleared alarm remembers the limit it was cleared under | A test that widening clears TT-101 and switching back restores it |
| **A static host made the browser log errors.** | A page asking for `/api/...` on a static host gets a 404, and the browser logs a failed request however the page's code handles it | The platform server marks every response with a header; the page makes one harmless request for itself and calls the API only if it sees the mark. Any bad answer (a 404 page, HTML, or text that is not JSON) puts the Limits tab back to its recorded copy. | `tests/test_site.py`, which serves the site with a plain static server and asserts no console errors and no request to `/api/` |
| **Anchor links landed behind the sticky header.** | Making the header stay at the top meant jump links scrolled the heading under it | The page's scroll padding follows the header's measured height | A test that the header stays at the top and that an anchor lands below it |

### 13.3 What the segmentation work found

- **As found, segmentation was nominal.** With every switch ALLOW, the office PC reaches 21 of 21 other addressed hosts, exactly what a flat network gives. Setting every switch to DENY drops it to 1. The walls existed, and each had an over-broad door.
- **Some traffic no firewall rule can stop.** Approved flows pass whatever the switches say, and a firewall cannot see a value or a change window. That is the gap the triage is there for.
- **Two conduits have no firewall at all,** level 0 to level 1 and level 2 to level 3. The model keeps them in rather than leaving them out, because an unfiltered boundary is a fact about a plant.
- **The FW-304 modelling.** The page first called FW-304 (FW-Cell-1) the "line 1 cell firewall". The model has only one conduit between level 2 and level 1, and the decision function works on zones, so every level 1 controller is behind that one firewall: PLC-Line1, PLC-Line2, DCS-CTRL-01 and RTU-Outstation-3. No path reaches PLC-Line2 without crossing FW-304. So this was a naming mismatch, not a gap in the model, and no second cell firewall was invented. The page now calls FW-304 the cell firewall on the level 2 to level 1 boundary, keeps the old name in its notes, and says a real plant would give each line its own cell firewall.

### 13.4 What a real plant would need that this demo does not have

*Background, not verified here.* This list is general knowledge, not something the project tested.

- **Real data.** Alarm limits judged against a plant's own history, and alerts from a plant's own sensors, not generated readings and invented alerts.
- **Network facts, not a model.** An inventory built by discovery, and firewall rules read from the real devices under change control, per production line.
- **Monitoring that covers the internal paths,** with sensors placed where the traffic is, and a way to see what the firewalls block.
- **Authentication where devices support it,** and protection for remote access.
- **Change management that enforces,** so a widened alarm limit cannot go in without passing a gate, and a record of who changed what.
- **Process safety independent of the control network.** A real plant has safety systems that do not rely on the alarms and controllers shown here.
- **People and practice:** trained operators, tested response plans, and review by the people who own the plant's safety.

---

## 14. Running it, hosting it and testing it

> **In plain words.** The 3D page runs on its own with nothing to install: open the file. The AI triage needs a small server, a hosted AI model service and a search service, and keys for both. The page can also be published as a static site, which is the easiest way to share the demo, but the parts that need a server stay off there.

### 14.1 Open the 3D page with nothing installed

Open `static/sentinelot.html` in a web browser. The attacks, the 3D plant, the firewall switches, the Segmentation tab and the What-if sandbox all work from the file. The Limits tab shows its **recorded** result, labelled as such, and **Check change** is disabled, because that needs the server. The analyst notes are the pre-written ones.

To see what a static host serves, run a plain web server over the `site/` folder:

```
python -m http.server --directory site
```

and open the address it prints.

### 14.2 Run the whole platform without Docker

You need Python 3.11 or newer, a hosted-model API key and a search API key.

```
git clone <the repository's address>
cd sentinelot-platform
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

(On Linux or macOS, activate with `source .venv/bin/activate` and copy with `cp`.) Open `.env` and fill in the keys. **Never commit `.env`**: it is listed in `.gitignore`. Then start the server:

```
python -m uvicorn triage.main:app --port 8000
```

and open `http://localhost:8000` for the triage interface, or `http://localhost:8000/sentinelot.html` for the 3D page with a live Limits check. The `.env` file holds these settings; only their names are given here.

| Setting | Meaning |
|---|---|
| `NEBIUS_API_KEY`, `NEBIUS_BASE_URL` | The hosted model service key and its address |
| `TAVILY_API_KEY` | The web-search service key |
| `APP_ADMIN_TOKEN` | A secret that protects free-form alert submission |
| `MODEL_INTAKE`, `MODEL_INTEL`, `MODEL_MAPPER`, `MODEL_ADVISOR`, `MODEL_TRIAGE` | The model for each agent |
| `DEMO_PER_IP_HOUR`, `DEMO_DAILY_CAP` | Public run limits per visitor per hour and per day |
| `SITE_ADDRESS` | `:80` for plain HTTP, or a domain name for automatic HTTPS (Docker only) |

### 14.3 Run it with Docker

```
docker compose up --build
```

Open `http://localhost`. Docker Compose starts the app and Caddy, a small web server that sits in front of it. After changing a page, rebuild with `docker compose up -d --build` so the new page is copied into the image. The image is built from a small Python base image and starts the server with `uvicorn`.

### 14.4 Run the tests

```
pip install -r requirements-dev.txt -r alarmops/requirements-dev.txt
python -m pytest
python -m pytest alarmops
```

The tests that drive the page need Playwright and an installed Microsoft Edge (or Chrome), which they launch directly, so no browser download is needed. Without them those tests are **skipped**, and `pytest.ini` turns on a summary that lists every skip and its reason, so a skipped test is never mistaken for a passing one. No test calls a model or reaches the network beyond a local test server.

**Measured counts, on 2026-11-16** (run at commit `0d50029`; this manual's later steps did not re-run the full suite): **482 passed, 0 skipped** for the platform and **86 passed, 0 skipped** for the AlarmOps copy. The platform's 482 add up like this:

| Group | Tests |
|---|---|
| The server and the data (API, rate limits, guards, orchestrator, scenarios, lab feeds, alarm-limit routes) | 47 |
| The plant page driven in a browser (`test_page_model.py` 61, `test_page_segmentation.py` 17) | 78 |
| The Quiet attack (`test_quiet_attack.py`) | 28 |
| Colour contrast of the page (`test_palette_contrast.py`) | 49 |
| Firewall rules and reachability against an independent Python version (`test_segmentation.py` 223, `test_reach.py` 42) | 265 |
| The static site and the page with no API (`test_site.py`) | 15 |
| **Total** | **482** |

These are counts for that date. They will change as tests are added.

### 14.5 Hosting: static site or full app

| | Static site (the `site/` folder) | Full app (server) |
|---|---|---|
| The 3D plant, attacks, firewall switches, Segmentation, What-if, Show trace | Works | Works |
| The Quiet attack control and the HMI write | Works | Works |
| The Limits tab | Shows the **recorded** result. Check change is off. | A live replay, with Check change on |
| The analyst note on an alarm | The pre-written one | Pre-written, or written live by AI if the page is hosted where a helper is provided (not verified here) |
| The triage interface and its five agents | **Not available** | Available |

**The static copy.** `site/index.html` is a byte-for-byte copy of `static/sentinelot.html`, made by `scripts/build_site.py`. Only the 3D page goes there. The triage interface is not copied, because it needs the server and shows nothing useful without one. **Every change to the page needs `python scripts/build_site.py` and a commit of `site/index.html`.** `tests/test_site.py` fails if the two differ, so a forgotten rebuild is caught before anything is published.

**Render settings.** The README gives these for the static site: service type **Static Site**, publish directory `site`, build command empty. Render's documentation, as read while writing the README, does not say whether the dashboard accepts an empty build command, so that setting is **unconfirmed**. If the form insists on a value, a command that does nothing, such as `echo ok`, is the fallback.

**Why the AI part needs a server.** The five agents call a hosted model service, and the search step calls a web-search service. Both need secret keys. A key must be kept on a server, never in a web page, because anyone could read it from a page. A static host serves files and cannot hold a secret or make those calls on your behalf. So the triage cannot run on a static host, and the 3D page keeps working there by design because it contains no key and makes no model calls.

---

## 15. Glossary

| Term | Meaning |
|---|---|
| **Acknowledge** | Tell the control system a person has seen an alarm. It stops the flashing and changes nothing else. |
| **AlarmOps** | A project that checks changes to alarm limits against labelled test data. A copy is used here as a library. |
| **Alarm limit** | The reading at which a control system calls for a person, such as a tank level that is too high |
| **Annunciator** | A row of lit boxes, one per kind of trouble, on a control-room panel |
| **Approved flow** | A legitimate kind of traffic with its own fixed rule that no firewall switch touches |
| **Asset tag** | A short label for an item, such as PLC-101, in the style of an engineering drawing |
| **ATT&CK for ICS** | A public catalogue of the techniques attackers use against industrial control systems |
| **Baseline** | The limits in force and their measured result, which a proposed change is compared with |
| **Coil** | A numbered on/off switch inside a controller |
| **Conduit** | The link between two neighbouring zones, where a firewall may sit |
| **DCS** | Distributed control system: a controller system for a continuous process such as steam or cooling water |
| **Deadband** | How far back from a limit a reading must fall before an alarm clears, to stop flicker |
| **Demo only** | Marks anything not in the project's asset file, `data/assets.json` |
| **DMZ** | Demilitarised zone: a buffer between the office network and the plant (level 3.5) |
| **DNP3** | An industrial protocol, used here between the SCADA server and a remote outstation (port 20000) |
| **False alarm** | An alarm that fires when no fault is present |
| **Firewall** | A device that decides what traffic may cross a boundary |
| **First out** | The mark on the alarm that came first in a sequence, which is usually the cause |
| **Flat network** | A network with no internal boundaries, where every host can reach every other |
| **Function code** | The number in a Modbus message that says what is being asked, such as read or write |
| **Gap** | A conduit with no firewall, so nothing there can be set to deny |
| **Gate** | A check that allows or blocks a change. Here, the AlarmOps gate on alarm limits. |
| **HMI** | Human-machine interface: the screen an operator uses to watch and adjust a machine |
| **Historian** | A database that stores process readings over time |
| **Jump server** | The single, controlled door into the plant network from outside |
| **Level (Purdue)** | One of the numbered layers from 0 (machines) to 5 (internet), with a DMZ at 3.5 |
| **Modbus/TCP** | A very common language for industrial controllers, spoken over a network (port 502) |
| **OPC UA** | An industrial data protocol, used here for the SCADA server's endpoint (port 4840) |
| **OT** | Operational technology: the computers and networks that run physical processes |
| **Passive sensor** | A listener that reads traffic and never sends any |
| **PLC** | Programmable logic controller: a small rugged computer that runs a machine or line |
| **Priority (P1 to P4)** | How urgent a triage verdict is. P1 is the most urgent. |
| **Process alarm** | An alarm raised because a process reading crossed a limit, such as TT-101 |
| **Prompt injection** | Text written to give orders to an AI that is only meant to read it |
| **Purdue model** | A way of organising an industrial network into numbered layers |
| **Reach counter** | The Segmentation tab's count of how many hosts a compromised OFFICE-PC-14 can reach |
| **Recorded** | A result saved inside the page, shown when no server is available |
| **Register** | A numbered memory slot in a controller that holds a value |
| **RTU** | Remote terminal unit: a controller in a remote spot that reports back |
| **SCADA** | Supervisory control and data acquisition: software that gathers data from many controllers |
| **Security alarm** | An alarm raised because of who sent a message. On the page, a write from a host that is not an approved master. |
| **Segmentation** | Dividing a network into zones with controlled links between them |
| **Setpoint** | The value a controller is told to hold, such as the sealer temperature |
| **SIMULATED** | Marks everything that exists only inside the demonstration |
| **Subnet** | A block of network addresses. Each zone has one here. |
| **Triage** | A first pass at deciding how serious an alert is and what to do about it |
| **TT-101** | The sealer temperature signal and its process alarm |
| **Verdict** | The triage's decision: escalate, investigate or likely benign |
| **VLAN** | A virtual network number. Each zone is given one here, as demo numbering. |
| **WIDENED** | The Quiet attack setting that stands for an alarm-limit change that was not blocked |
| **Zone** | One level of the plant model, treated as one security area |

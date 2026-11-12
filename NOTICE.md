# Third-party notices

SentinelOT's own source code is released under the MIT License (see `LICENSE`,
copyright held by Anthony Afonughe). This project also uses the third-party
material described below. That material is not covered by the MIT License and
stays under its owners' terms.

## MITRE ATT&CK(R) for ICS

The file `data/ics-attack.json` is a copy of MITRE's ATT&CK for ICS data in
STIX format. It was downloaded on 6 October 2026 (ATT&CK version 19.2) from
MITRE's public `attack-stix-data` repository on GitHub. SentinelOT reads this
file to check technique IDs and names and to give its ATT&CK mapper agent the
list of techniques to choose from.

MITRE ATT&CK(R) is a registered trademark of The MITRE Corporation. SentinelOT
is an independent project. It is not affiliated with, sponsored by or endorsed
by MITRE.

Use of ATT&CK is governed by MITRE's terms of use:
https://attack.mitre.org/resources/legal-and-branding/terms-of-use/

MITRE's licence requires that any copy of ATT&CK reproduce MITRE's copyright
designation and the licence. They are reproduced below, exactly as published
on the page above.

### MITRE ATT&CK® Terms of Use

Copied from https://attack.mitre.org/resources/legal-and-branding/terms-of-use/

**LICENSE**

The MITRE Corporation (MITRE) hereby grants you a non-exclusive, royalty-free license to use ATT&CK® for research, development, and commercial purposes. Any copy you make for such purposes is authorized provided that you reproduce MITRE's copyright designation and this license in any such copy.

"© 2026 The MITRE Corporation. This work is reproduced and distributed with the permission of The MITRE Corporation."

**DISCLAIMERS**

MITRE does not claim ATT&CK enumerates all possibilities for the types of actions and behaviors documented as part of its adversary model and framework of techniques. Using the information contained within ATT&CK to address or cover full categories of techniques will not guarantee full defensive coverage as there may be undisclosed techniques or variations on existing techniques not documented by ATT&CK.

ALL DOCUMENTS AND THE INFORMATION CONTAINED THEREIN ARE PROVIDED ON AN "AS IS" BASIS AND THE CONTRIBUTOR, THE ORGANIZATION HE/SHE REPRESENTS OR IS SPONSORED BY (IF ANY), THE MITRE CORPORATION, ITS BOARD OF TRUSTEES, OFFICERS, AGENTS, AND EMPLOYEES, DISCLAIM ALL WARRANTIES, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTY THAT THE USE OF THE INFORMATION THEREIN WILL NOT INFRINGE ANY RIGHTS OR ANY IMPLIED WARRANTIES OF MERCHANTABILITY OR FITNESS FOR A PARTICULAR PURPOSE.

<!-- END OF MITRE TEXT -->

## Other material

- **Python packages** listed in `requirements.txt` are installed from PyPI
  and used under their own licences. They are not copied into this repository.
- **Docker base images** (Python and Caddy) are pulled by Docker at build time
  under their own licences. They are not copied into this repository.
- **Runtime services:** Nebius Token Factory (NVIDIA Nemotron models) and the
  Tavily Search API are called over the internet under their providers' terms.
  No model weights or service code are included here.

## Origin

The triage code in `triage/`, the web interface in `static/index.html`, the
test plant, the evaluation results in `results/` and most pages in `docs/`
come from SentinelOT, built by Anthony Afonughe for the Nebius x NVIDIA Global
AI Hackathon (track: Best Apps and Agents):

- Original repository: https://github.com/ToniGift/sentinelOT
- Imported from commit `4766d662da3ddd845d72a371216b4e2eecdcf4ae`
- The original repository is kept unchanged as the hackathon submission.

The synthetic alerts in the scenario files were written with AI assistance
(Claude), then reviewed and run by the author.

## Material added in this repository

- **three.js r128** (MIT License) is loaded by `static/sentinelot.html` from
  the cdnjs CDN at view time. It is not copied into this repository.
- **Scapy** (GPL-2.0) is an optional dependency listed in
  `requirements-lab.txt` and used only by `triage/lab_sniffer.py`. It is
  installed from PyPI under its own licence and is not copied into this
  repository.

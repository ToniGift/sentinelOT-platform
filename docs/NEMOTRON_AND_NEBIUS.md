# How we use NVIDIA Nemotron, Token Factory and Nebius

[Home](../README.md) | [About](ABOUT.md) | [Examples](EXAMPLES.md) | [How it works](HOW_IT_WORKS.md) | **Nemotron and Nebius** | [Web interface](WEB_INTERFACE.md) | [Run it](RUN_IT.md) | [Testing the demo](TESTING.md) | [Test plant](TEST_PLANT.md) | [Evaluation](EVALUATION.md)

---

- **Nemotron models on Nebius Token Factory** do all the reasoning. **Nemotron 3 Ultra** makes the main triage decision. **Nemotron 3 Super** handles the four faster steps.
- **Where Token Factory helped:** one OpenAI-compatible API (we use the standard `openai` Python SDK with the Token Factory base URL), a catalogue that let us give the hard decision to the large model and the quick steps to the smaller one, and low per-token prices. By our estimate a full triage costs about 1 to 1.5 cents.
- **What we learned:** the small Nemotron 3.5 Lightning model spent many reasoning tokens on simple extraction and made the first step slow, so we moved that step to Super. Reasoning tokens count against the output limit, so our client allows generous output sizes and parses JSON from the reply.
- **Tavily Search API** supplies live threat intelligence. Searches go first to trusted sites (CISA, MITRE ATT&CK, NVD, CVE.org). Results from other sites are labelled as unverified.
- **Nebius AI Cloud:** the public demo runs in Docker on a Nebius AI Cloud virtual machine.

## What Tavily returned

SentinelOT does not scan any network or the internet. It searches for published advisories with the Tavily Search API and summarises what comes back. For the s01 alert (an office PC writing to a PLC), the Threat intel tab shows two results, both from `cisa.gov` and both marked **On the trusted list**.

![The Threat intel tab for alert s01, showing two CISA advisories marked as on the trusted list, each with a link and a short finding](images/screenshot-s01-threat-intel.png)

Both are real, public CISA advisories, and the findings match them:

| Result shown | Advisory | What it says |
|---|---|---|
| Delta Electronics DVP12SE PLC | ICSA-26-181-07, published by CISA at the end of June 2026 (CVE-2026-12819) | The PLC exposes a Modbus TCP service without authentication or access control |
| Schneider Electric Modicon Modbus Protocol | ICSA-17-101-01, published in 2017 and now archived on the CISA site (CVE-2017-6034) | Commands are sent in cleartext and can be replayed, and a session weakness makes brute-force attacks possible |

Two things to keep in mind when reading results like this:

- **They are background, not a match for the plant's own PLC.** Both advisories are about specific products. The inventory entry for the line 1 PLC names no vendor or model, so the result treats them as general evidence that Modbus often lacks authentication. The explanation in the run says so.
- **The open web is a fallback.** Searches go to the trusted sites first. A result from anywhere else is labelled as an unverified source. In this run there were none.

## Our feedback

The build log, the per-step measurements and our written feedback on Nebius Token Factory, NVIDIA Nemotron and Tavily are in [NOTES.md](NOTES.md).

---

[Back to the README](../README.md)

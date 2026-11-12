# Build notes

Working notes kept while building SentinelOT for the Nebius x NVIDIA Global AI Hackathon. The log records what worked and what broke. The feedback section is written for Nebius, NVIDIA and Tavily, and it is what goes into the Devpost submission.

How to read the tags:

- **(hit this myself)** happened during the build.
- **(from reading)** comes from documentation or public issues and has not been confirmed on this project.
- **[confirm]** needs checking before it is submitted.

## Log

### 5 to 6 Oct: setup, pipeline, first evaluations

**What worked**

- The Token Factory and Tavily keys worked on the first smoke test, and all three Nemotron models returned valid JSON.
- The single-agent baseline gave valid output on 12 of 12 scenarios from the command line.
- Five agents run in a fixed order under a plain Python orchestrator. The search and the ATT&CK mapper run side by side.
- First full evaluation on the 12 development scenarios: 11 of 12 verdicts and 8 of 12 techniques matched.
- The held-out set was written and labelled before it was run. First run: 9 of 10 verdicts and 9 of 10 techniques. Both injection cases (h06 and h07) were escalated, so the hidden instructions were not obeyed.
- The Docker image ran on my own PC. Timeout and run-budget safeguards are in, 26 tests pass, and the secrets check of the git history was clean before the first push.

**What broke**

- Token Factory returned 402 errors until I switched the account from trial to paid usage.
- Nemotron 3.5 Lightning spent hundreds of reasoning tokens on small tasks and made Intake very slow. I moved Intake to Super.
- The ATT&CK keyword shortlist was replaced. The mapper now gets the full technique list with short descriptions. The first full run had matched only 8 of 12 techniques.
- Three expected technique IDs (T0855, T0856 and T0839) had been retired in ATT&CK for ICS v19.2. They are now T1692.001, T1692.002 and T1693.002. I found this by checking my labels against the official data file.
- The one held-out miss was h05: a successful login after repeated failures from a new VPN address, called investigate where I expected escalate. My escalate definition covered commands and changes that reached a control asset, but not successful unauthorized access. I kept the labels as written and reported 9 of 10, widened the definitions in version 2, and tested on a fresh held-out set.

**Platform note**

- Token Factory and AI Cloud have separate balances. I first treated the event credit as one.

### 7 Oct: web page and live runs

- The first version of my page expected the full result in the reply to `POST /api/demo/{id}`. The API actually returns a `job_id`, and the result comes from `GET /api/jobs/{job_id}`. Until I followed that two-step flow, the page showed an empty result.
- Live runs against the real API: s01 escalate P1 90% in 26 s, s09 investigate P2 75% in 24 s, x01 escalate P1 90% in 29 s.
- For s01, Tavily returned two cisa.gov advisories. I checked both against the public record: ICSA-26-181-07 (Delta Electronics DVP12SE PLC) and ICSA-17-101-01 (Schneider Electric Modicon Modbus Protocol).
- The token counts on the timing tab let me work out a cost per run. At the prices listed in my build plan, which came from an aggregator listing and not from Nebius, it is about 1.4 cents for each of the two runs below. **[confirm]** on the Token Factory usage page.

## Per-step measurements

| Step | Model | x01: seconds | x01: tokens in / out | s01: seconds | s01: tokens in / out |
|---|---|---|---|---|---|
| intake | nemotron-3-super-120b-a12b | 3.6 | 644 / 635 | 3.1 | 687 / 559 |
| search | Tavily (code) | 4.7 | n/a | 3.8 | n/a |
| intel | nemotron-3-super-120b-a12b | 10.9 | 4,132 / 2,251 | 8.7 | 3,638 / 1,688 |
| mapper | nemotron-3-super-120b-a12b | 6.3 | 5,232 / 1,019 | 7.4 | 5,283 / 1,474 |
| triage | Nemotron-3-Ultra-550b-a55b | 3.3 | 1,952 / 1,322 | 3.6 | 1,705 / 1,404 |
| advisor | nemotron-3-super-120b-a12b | 6.5 | 1,234 / 1,258 | 5.8 | 1,227 / 1,109 |

What the numbers show:

- Intake produced about as many output tokens as it was given (635 out for 644 in, 559 out for 687 in), for a short extraction job.
- Intel was the slowest step in both runs and produced the most output tokens.
- Triage on Ultra took 3.3 and 3.6 seconds, faster than the Intel, mapper and advisor steps on Super in both runs, with 1,322 and 1,404 output tokens.
- The steps add up to 35.3 s (x01) and 32.4 s (s01). The run took 29 s and 26 s because the search and the mapper run side by side. The longest path through the steps is 29.0 s and 25.0 s.

## Feedback for Nebius, NVIDIA and Tavily

Draft for the Devpost form. Check each **[confirm]** and adjust anything that does not match what you actually saw.

### Nebius Token Factory

**What worked**

- The OpenAI-compatible API worked with the standard `openai` Python SDK. I changed only the base URL and the key.
- One catalogue let me give the hard decision to the large model and the quick steps to a smaller one.
- A full triage costs about 1.4 cents at the listed prices. **[confirm]**

**What was hard**

- I got 402 errors until I moved the account from trial to paid usage. *(hit this myself)* **[add the exact message you saw, and say whether it explained the cause]**
- The Token Factory and AI Cloud balances are separate, and I first treated the event credit as one. *(hit this myself)*
- Model ID strings use different styles, for example `nvidia/nemotron-3-super-120b-a12b` and `nvidia/Nemotron-3-Ultra-550b-a55b`. I copied the exact strings from the models list instead of typing them. *(hit this myself)*
- Older repositories still show the old base URL (`api.studio.nebius.ai/v1`), while the current documentation uses `api.tokenfactory.nebius.com`. *(from reading)*
- Public reports on how Nemotron models behave with tool calls disagreed with each other, so I did not build on native tool calling. *(from reading)*

**Suggestions**

1. Make the 402 text say plainly that trial usage has ended and where to switch to paid. **[adjust to what the message said]**
2. Show the Token Factory and AI Cloud credit balances together, or explain on the event credit email that they are separate.
3. Use one naming style for model IDs, or say in the docs whether they are case sensitive.
4. Add a table of which models support JSON mode and tool calling, so developers do not have to piece it together from issues.

### Nebius AI Cloud

Not deployed yet. After the rehearsal VM, add: how long creating the VM took, the CPU-only VM price from the pricing page **[confirm]**, and anything that went wrong with the firewall, ports, disk or billing.

### NVIDIA Nemotron models

**What worked**

- All three models I tried (Lightning, Super and Ultra) returned valid JSON in the smoke test.
- Super handles four of the five steps and Ultra makes the triage decision, and that split worked end to end.
- In a controlled test, 0 of 10 injected runs followed the instruction hidden in the alert.

**What was hard**

- Lightning spent hundreds of reasoning tokens on small tasks. *(hit this myself)* Even on Super, Intake's output was about the size of its input. *(see the table)*
- In my pipeline, ATT&CK technique choice varied between runs, and in one run a detected exploit attempt was called likely benign. *(hit this myself)*

**Suggestions**

1. A documented per-request way to limit reasoning would help, because reasoning tokens count as output and slowed Intake. **[check the current Nemotron and Token Factory docs first. If such a control exists, rewrite this as how hard it was to find.]**
2. Per-model guidance on structured JSON output and tool calling would have saved research time. *(from reading)*

### Tavily

**What worked**

- Restricting searches to a trusted list of domains returned real cisa.gov advisories for s01, and every result carried a link I could open and check.
- A disk cache of results kept repeated evaluation runs from spending credits and made them repeatable.

**Not confirmed yet**

- How many credits one search costs at each `search_depth` setting. **[confirm]**

## Open items before submitting

- [ ] Real cost per run from the Token Factory usage page
- [ ] Tavily credits per search at each depth
- [ ] Nebius data-handling terms
- [ ] Whether JSON mode (`response_format`) works with the chosen Nemotron models (not tested)
- [ ] Whether native tool calling works with them (not tested)
- [ ] Credit expiry dates
- [ ] AI Cloud notes after the rehearsal VM
- [ ] Optional: compare Ultra and Super for the triage step (not done)

## Template for each day

```
### [date]
What worked:
What broke:
Nebius, NVIDIA or Tavily problems:
```

# Evaluation

[Home](../README.md) | [About](ABOUT.md) | [Examples](EXAMPLES.md) | [How it works](HOW_IT_WORKS.md) | [Nemotron and Nebius](NEMOTRON_AND_NEBIUS.md) | [Web interface](WEB_INTERFACE.md) | [Run it](RUN_IT.md) | [Testing the demo](TESTING.md) | [Test plant](TEST_PLANT.md) | **Evaluation**

---

All scenarios are synthetic and were written with AI assistance, then reviewed and run by the author. The plant they are set in is described on the [Test plant](TEST_PLANT.md) page. Each has an expected verdict and acceptable ATT&CK techniques written before the run. Each set was run three times because results vary between runs. These results were produced when the inventory held the eight assets at Levels 1 to 4. The six Level 0 and Level 3.5 assets were added afterwards, and the results have not been re-run since.

| Set | Scenarios | Verdicts correct | Techniques acceptable |
|---|---|---|---|
| Fresh held-out (written before the final prompts ran) | 10 | **29 of 30 runs** | 28 of 30 runs |
| Development (used for tuning) | 12 | 29 of 36 runs | 23 of 36 runs |

The raw per-run results, including the misses, are in the results/ folder (CSV files).

- **Prompt injection:** in a controlled test, **0 of 10** injected runs followed the hidden instruction. In the final version, the warning fired on the one authority-claim injection in 3 of 3 runs and on none of the 63 other runs.
- **Speed:** median **26 seconds** per alert across 66 runs.
- **Weak spot:** ATT&CK technique choice is noisy. Treat technique suggestions as hints for an analyst to check.

Reproduce:

```
python -m triage.eval heldout2 3      # fresh held-out set, 3 runs
python -m triage.eval dev 3           # development set, 3 runs
python -m triage.injection_test       # controlled prompt-injection test
python -m pytest -q tests      # offline tests
```

## Limits you should know about

- Small sample sizes. Three runs of one scenario are not independent evidence.
- One person set the labels, with AI assistance. No independent review.
- Synthetic data only. Not tested on real plant alerts or by working SOC analysts.
- Benign verdicts lean on notes in the asset inventory and on what the alert text says, such as a change ticket reference that SentinelOT cannot check.
- It can under-call a real threat. In one run, a detected exploit attempt was called likely benign.
- This is a research prototype, not a production security tool.

---

[Back to the README](../README.md)

# Testing the demo (for judges)

[Home](../README.md) | [About](ABOUT.md) | [Examples](EXAMPLES.md) | [How it works](HOW_IT_WORKS.md) | [Nemotron and Nebius](NEMOTRON_AND_NEBIUS.md) | [Web interface](WEB_INTERFACE.md) | [Run it](RUN_IT.md) | **Testing the demo** | [Test plant](TEST_PLANT.md) | [Evaluation](EVALUATION.md)

---

1. Open the live demo link in the [README](../README.md#links): http://sentinelot.213-239-174-15.sslip.io/ (backup: http://213.239.174.15). If the name link does not open, use the backup address. It is served over plain HTTP, so if your browser warns, choose Continue to site. There is no login.
2. Choose a synthetic alert from the list, or press **Start with an example**. The set has three groups: a development set, and two held-out sets.
3. Press **Run triage**. The steps light up as each agent finishes, and a full result follows in about 20 to 50 seconds.
4. Press **Show last saved result** to see a stored result for the chosen scenario at any time. This works even if the model service is slow.
5. Try the alerts that contain hidden instructions (`h06`, `h07` and `x07`) to see the embedded-instruction warning. Scenarios H06, H07 and X07 contain hidden instructions and show a warning.
6. Open the **History** section. On the live demo, the History section also lists the last 20 runs saved on the server, from any device. In a copy you run yourself, history is kept in your own browser.

To protect the project's credit, public runs are rate-limited per visitor and per day. When a limit is reached, saved results always work. Alerts are synthetic, so no real plant data is involved (see [Test plant](TEST_PLANT.md)).

---

[Back to the README](../README.md)

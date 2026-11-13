# Run it yourself

[Home](../README.md) | [About](ABOUT.md) | [Examples](EXAMPLES.md) | [How it works](HOW_IT_WORKS.md) | [Nemotron and Nebius](NEMOTRON_AND_NEBIUS.md) | [Web interface](WEB_INTERFACE.md) | **Run it** | [Testing the demo](TESTING.md) | [Test plant](TEST_PLANT.md) | [Evaluation](EVALUATION.md)

---

## 1. Run it with Python

You need Python 3.11 or newer, a Nebius Token Factory API key and a Tavily API key.

```
git clone https://github.com/ToniGift/sentinelot-platform.git
cd sentinelot-platform
python -m venv .venv
.venv\Scripts\activate            # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env            # Linux/macOS: cp .env.example .env
```

Open `.env` and fill in your keys. Then list the models your key can use and copy the exact Nemotron model IDs into the `MODEL_*` lines:

```
python -m triage.smoke_test
python -m triage.smoke_test nvidia/nemotron-3-super-120b-a12b     # tests one model for valid JSON
```

Start the web app and open http://localhost:8000:

```
python -m uvicorn triage.main:app --port 8000
```

Or triage one scenario from the command line:

```
python -m triage.run_pipeline s01
```

## 2. Run it with Docker

```
docker compose up --build
```

Open http://localhost. Docker Compose starts the app and Caddy, a small web server that sits in front of it. Stop with Ctrl+C, then `docker compose down`.

After you change `static/index.html`, rebuild so the new page is copied into the image:

```
docker compose up -d --build
```

## 3. Deploy to a server

[`DEPLOY.md`](DEPLOY.md) explains how to put it on a virtual machine step by step.

## Configuration (`.env`)

| Setting | Meaning |
|---|---|
| `NEBIUS_API_KEY` | Your Token Factory key |
| `NEBIUS_BASE_URL` | `https://api.tokenfactory.nebius.com/v1/` |
| `TAVILY_API_KEY` | Your Tavily key |
| `APP_ADMIN_TOKEN` | Secret that protects free-form alert submission |
| `MODEL_INTAKE`, `MODEL_INTEL`, `MODEL_MAPPER`, `MODEL_ADVISOR` | Model IDs for those four agents |
| `MODEL_TRIAGE` | Model ID for the triage decision |
| `DEMO_PER_IP_HOUR`, `DEMO_DAILY_CAP` | Public run limits per visitor per hour and per day |
| `SITE_ADDRESS` | `:80` for plain HTTP, or a domain name for automatic HTTPS (Docker only) |

Never commit `.env`. It is listed in `.gitignore`.

## Project layout

```
main.py             web API and rate limits
orchestrator.py     runs the five agents and the code checks
prompts.py          the agent prompts
schemas.py          data shapes for every agent output
guards.py           injection warning, verdict/priority and evidence checks
llm.py              Token Factory client with JSON parsing and retries
intel.py            Tavily search with trusted-site filter and cache
attack_ics.py       loads the ATT&CK for ICS data
assets.py           asset inventory lookup (data/assets.json)
scenarios*.py       the 32 synthetic alerts and their expected labels
eval.py             evaluation runner
injection_test.py   controlled prompt-injection test
static/index.html   the web page (a single file, no build step)
Dockerfile, docker-compose.yml, Caddyfile   container setup
tests/              offline tests
```

---

[Back to the README](../README.md)

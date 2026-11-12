import os
import secrets
import threading
import time
import uuid
from collections import OrderedDict, defaultdict
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.staticfiles import StaticFiles

import store
from orchestrator import run_triage
from scenarios import SCENARIOS as DEV
from scenarios_heldout import SCENARIOS as HELD
from scenarios_heldout2 import SCENARIOS as HELD2
from schemas import Alert

app = FastAPI(title="SentinelOT")

ALL = {**{k: ("development", v) for k, v in DEV.items()},
       **{k: ("held-out", v) for k, v in HELD.items()},
       **{k: ("held-out-2", v) for k, v in HELD2.items()}}

PER_IP = int(os.getenv("DEMO_PER_IP_HOUR", "10"))
DAILY_CAP = int(os.getenv("DEMO_DAILY_CAP", "200"))
_lock = threading.Lock()
_ip_hits = defaultdict(list)
_day = {"date": time.strftime("%Y-%m-%d"), "n": 0}
JOBS = OrderedDict()
POOL = ThreadPoolExecutor(max_workers=4)


def client_ip(request: Request):
    if os.getenv("TRUST_PROXY") == "1":
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_limits(ip):
    now = time.time()
    with _lock:
        today = time.strftime("%Y-%m-%d")
        if _day["date"] != today:
            _day.update(date=today, n=0)
        if _day["n"] >= DAILY_CAP:
            raise HTTPException(429, "The daily demo limit has been reached. "
                                "Use 'Show last saved result' or try again "
                                "tomorrow.")
        hits = [t for t in _ip_hits[ip] if now - t < 3600]
        if len(hits) >= PER_IP:
            raise HTTPException(429, f"Limit of {PER_IP} runs per hour "
                                "reached. Use 'Show last saved result'.")
        hits.append(now)
        _ip_hits[ip] = hits
        _day["n"] += 1


def start_job(alert, scenario_id=None):
    job_id = uuid.uuid4().hex[:12]
    job = {"status": "running", "trace": [], "result": None, "error": None}
    JOBS[job_id] = job
    while len(JOBS) > 200:
        JOBS.popitem(last=False)

    def work():
        try:
            res = run_triage(alert, trace_sink=job["trace"])
            store.save_result(res, scenario_id)
            job["result"] = res
            job["status"] = "done"
        except Exception as e:
            job["error"] = str(e)[:300]
            job["status"] = "error"

    POOL.submit(work)
    return job_id


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/scenarios")
def scenarios():
    return [{"id": k, "group": g, "title": a.title,
             "description": a.description, "protocol": a.protocol,
             "src_ip": a.src_ip, "dst_ip": a.dst_ip,
             "timestamp": a.timestamp}
            for k, (g, a) in ALL.items()]


@app.post("/api/demo/{scenario_id}")
def demo(scenario_id: str, request: Request):
    if scenario_id not in ALL:
        raise HTTPException(404, "Unknown scenario")
    check_limits(client_ip(request))
    return {"job_id": start_job(ALL[scenario_id][1], scenario_id)}


@app.post("/api/triage")
def triage(alert: Alert, x_admin_token: str = Header(default="")):
    expected = os.environ.get("APP_ADMIN_TOKEN", "")
    if not expected or not secrets.compare_digest(x_admin_token, expected):
        raise HTTPException(401, "Unauthorized")
    return {"job_id": start_job(alert, None)}


@app.get("/api/jobs/{job_id}")
def job(job_id: str):
    j = JOBS.get(job_id)
    if not j:
        raise HTTPException(404, "Unknown job")
    return {"status": j["status"], "trace": list(j["trace"]),
            "result": j["result"], "error": j["error"]}


@app.get("/api/saved/{scenario_id}")
def saved(scenario_id: str):
    res = store.latest_for_scenario(scenario_id)
    if not res:
        raise HTTPException(404, "No saved result for this scenario yet")
    return res


app.mount("/", StaticFiles(directory="static", html=True), name="static")

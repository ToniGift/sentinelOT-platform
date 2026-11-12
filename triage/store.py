import json
import os
import sqlite3
import time
from contextlib import closing

STATE_DIR = os.getenv("STATE_DIR", "data")
DB = f"{STATE_DIR}/sentinelot.sqlite"


def _con():
    os.makedirs(os.path.dirname(DB) or ".", exist_ok=True)
    con = sqlite3.connect(DB, timeout=10)
    con.execute("CREATE TABLE IF NOT EXISTS results ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, "
                "scenario_id TEXT, verdict TEXT, result_json TEXT)")
    return con


def save_result(result, scenario_id=None):
    with closing(_con()) as con, con:
        cur = con.execute(
            "INSERT INTO results (created_at, scenario_id, verdict, "
            "result_json) VALUES (?, ?, ?, ?)",
            (time.strftime("%Y-%m-%dT%H:%M:%S"), scenario_id,
             result["triage"]["verdict"], json.dumps(result)))
        return cur.lastrowid


def latest_for_scenario(scenario_id):
    with closing(_con()) as con:
        row = con.execute(
            "SELECT result_json FROM results WHERE scenario_id = ? "
            "ORDER BY id DESC LIMIT 1", (scenario_id,)).fetchone()
    return json.loads(row[0]) if row else None


def list_results(limit=20):
    with closing(_con()) as con:
        rows = con.execute(
            "SELECT id, created_at, scenario_id, verdict FROM results "
            "ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [{"id": r[0], "created_at": r[1], "scenario_id": r[2],
             "verdict": r[3]} for r in rows]

"""Tiny GitLab REST helper (stdlib only). Used by CI scripts."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

REQUIRED_ENV = ("GITLAB_API_TOKEN", "CI_API_V4_URL", "CI_PROJECT_ID")


def missing_env(extra: tuple[str, ...] = ()) -> list[str]:
    return [k for k in REQUIRED_ENV + extra if not os.environ.get(k)]


def request(method: str, path: str, body: Optional[dict] = None,
            query: Optional[dict] = None, timeout: int = 20) -> Any:
    base = os.environ["CI_API_V4_URL"].rstrip("/")
    url = f"{base}/projects/{os.environ['CI_PROJECT_ID']}{path}"
    if query:
        url += "?" + urllib.parse.urlencode(query)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "PRIVATE-TOKEN": os.environ["GITLAB_API_TOKEN"],
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:300]
        raise RuntimeError(f"GitLab API {method} {path} failed: {exc.code} {detail}") from exc

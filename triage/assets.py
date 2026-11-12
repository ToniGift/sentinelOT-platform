import json
import os

# ASSETS_FILE lets a lab run use its own inventory (data/assets_lab.json)
# without touching the fictional plant the evaluation numbers are based on.
_A = json.load(open(os.getenv("ASSETS_FILE", "data/assets.json"),
                    encoding="utf-8"))


def lookup_asset(key):
    if not key:
        return {"known": False}
    for ip, v in _A.items():
        if key == ip or key == v["name"]:
            return {"known": True, "ip": ip, **v}
    return {"known": False, "id": key}

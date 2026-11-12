"""Download the MITRE ATT&CK for ICS STIX file to data/ics-attack.json."""
import os
import sys
import urllib.request

BASE = "https://raw.githubusercontent.com/mitre-attack/attack-stix-data"
PATH = "ics-attack/ics-attack.json"
os.makedirs("data", exist_ok=True)

for branch in ("master", "main"):
    url = f"{BASE}/{branch}/{PATH}"
    try:
        print("Trying", url)
        urllib.request.urlretrieve(url, "data/ics-attack.json")
        break
    except Exception as e:
        print("  failed:", e)
else:
    sys.exit("Could not download. Open the attack-stix-data repository on "
             "GitHub, find ics-attack/ics-attack.json and save it to data/.")

from attack_ics import load_ics  # noqa: E402

techs = load_ics()
print(f"Loaded {len(techs)} ICS techniques.")
for tid in ("T0855", "T0843", "T0836"):
    hit = next((t for t in techs if t["id"] == tid), None)
    print(" ", tid, "->", hit["name"] if hit else "NOT FOUND")

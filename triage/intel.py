import hashlib
import json
import os
from urllib.parse import urlparse

from tavily import TavilyClient

tv = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
TRUSTED = ["cisa.gov", "attack.mitre.org", "nvd.nist.gov", "cve.org"]
# Vendor security-advisory sites. Add the vendors in your own asset list.
VENDORS = ["cisco.com", "siemens.com", "schneider-electric.com",
           "rockwellautomation.com", "mitsubishielectric.com", "abb.com"]
CACHE = os.path.join(os.getenv("STATE_DIR", "data"), "cache")
DEPTH = os.getenv("TAVILY_SEARCH_DEPTH", "basic")   # "basic" or "advanced"
os.makedirs(CACHE, exist_ok=True)


def is_trusted(url):
    """Trust is decided by the domain of the result, not by which search
    pass found it."""
    host = urlparse(url or "").netloc.lower()
    return any(host == d or host.endswith("." + d)
               for d in TRUSTED + VENDORS)


def _fetch(query, trusted, max_results):
    kw = {"search_depth": DEPTH, "max_results": max_results}
    if DEPTH == "advanced":
        kw["chunks_per_source"] = 3
    if trusted:
        kw["include_domains"] = TRUSTED
    r = tv.search(query, **kw)
    return [{"title": x.get("title"), "url": x.get("url"),
             "content": (x.get("content") or "")[:800],
             "trusted": is_trusted(x.get("url"))}
            for x in r.get("results", [])]


def search(query, max_results=5):
    """Trusted domains first; open web only if nothing came back (those
    hits carry trusted=False). Results are cached on disk by query."""
    key = hashlib.sha256(f"v3|{DEPTH}|{query}".encode()).hexdigest()[:16]
    path = f"{CACHE}/{key}.json"
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))
    hits = _fetch(query, True, max_results)
    if not hits:
        hits = _fetch(query, False, max_results)
    json.dump(hits, open(path, "w", encoding="utf-8"))
    return hits


def canon(url):
    """Canonical form of a URL for de-duplication (www. and the old
    us-cert.cisa.gov host point at the same CISA pages)."""
    p = urlparse(url or "")
    host = p.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if host == "us-cert.cisa.gov":
        host = "cisa.gov"
    return host + p.path.rstrip("/").lower()

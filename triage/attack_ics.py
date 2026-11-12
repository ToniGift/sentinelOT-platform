import json
import math
import re


def load_ics(path="data/ics-attack.json"):
    bundle = json.load(open(path, encoding="utf-8"))
    out = []
    for o in bundle["objects"]:
        if (o.get("type") != "attack-pattern" or o.get("revoked")
                or o.get("x_mitre_deprecated")):
            continue
        ext = next((r["external_id"] for r in o.get("external_references", [])
                    if r.get("source_name") == "mitre-attack"), None)
        if ext:
            out.append({"id": ext, "name": o["name"],
                        "desc": o.get("description", "")})
    return out


def _words(s):
    return set(re.findall(r"[a-z]{4,}", s.lower()))


def candidates(techs, text, k=8):
    """Rank techniques by shared rare words. Name matches count triple."""
    n = len(techs)
    docs = [(t, _words(t["name"]), _words(t["desc"])) for t in techs]
    df = {}
    for _, nw, dw in docs:
        for w in nw | dw:
            df[w] = df.get(w, 0) + 1
    q = _words(text)
    scored = []
    for t, nw, dw in docs:
        s = sum(math.log(n / df[w]) * (3 if w in nw else 1)
                for w in q if w in nw or w in dw)
        scored.append((s, t))
    scored.sort(key=lambda x: -x[0])
    return [t for s, t in scored[:k] if s > 0]


def _short(desc, limit=220):
    """First sentence of an ATT&CK description, with citations and
    markdown links removed."""
    d = re.sub(r"\(Citation:[^)]*\)", "", desc)
    d = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", d)
    d = re.sub(r"\s+", " ", d).strip()
    m = re.search(r"(?<=[a-z\)])\.\s", d)
    first = d[:m.start() + 1] if m else d
    return first[:limit].rstrip()


def catalogue(techs):
    """Full compact list (id, name, short description) for the Mapper. ICS
    has under 100 entries, so the whole list fits in the model's context.
    Sub-technique names are prefixed with the parent name, because several
    sub-techniques share a name (two different 'Command Message' entries)
    and are ambiguous without it."""
    names = {t["id"]: t["name"] for t in techs}
    out = []
    for t in sorted(techs, key=lambda x: x["id"]):
        name = t["name"]
        if "." in t["id"]:
            parent = names.get(t["id"].split(".")[0])
            if parent:
                name = f"{parent}: {name}"
        out.append({"id": t["id"], "name": name,
                    "what": _short(t.get("desc", ""))})
    return out

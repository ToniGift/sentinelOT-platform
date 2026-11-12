"""Deterministic checks that run in code, after or beside the LLM agents."""
import re

# ---- prompt-injection heuristic (simple pattern list, not exhaustive) ----
_PATTERNS = [
    r"ignore (all |any |the )?(previous|prior|above|earlier) (instructions|prompts?)",
    r"disregard (all |any |the )?(previous|prior|above|earlier)",
    r"note to (the )?(analy[sz]\w*|ai|assistant|system|model)",
    r"system (message|prompt|note|override)",
    r"classify (this|the) (alert|event|activity) as",
    r"(mark|label|rate|treat) (this|it|the alert) as (benign|harmless|safe|a false positive)",
    r"do not (escalate|alert|report|recommend|flag)",
    r"you (must|should) (now )?(classify|ignore|output|respond)",
]
_RE = [re.compile(p, re.I) for p in _PATTERNS]


def detect_injection(*texts):
    hay = " ".join(t for t in texts if t)
    return [m.group(0) for r in _RE for m in [r.search(hay)] if m]


# ---- verdict / priority consistency ----
ALLOWED = {"escalate": {"P1", "P2"}, "investigate": {"P2", "P3"},
           "likely_benign": {"P3", "P4"}}
_ORDER = ["P1", "P2", "P3", "P4"]


def consistent(verdict, priority):
    return priority in ALLOWED[verdict]


def clamp_priority(verdict, priority):
    """Nearest allowed priority for the verdict (used only if a re-check
    by the model still disagrees)."""
    i = _ORDER.index(priority)
    return min(sorted(ALLOWED[verdict]), key=lambda p: abs(_ORDER.index(p) - i))


# ---- evidence must cite data that exists ----
_PATH = re.compile(r"^\s*([a-z_]+(?:\.[A-Za-z_][A-Za-z0-9_]*|\[\d+\])+)")
_TOK = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\[\d+\]")


def _resolve(path, payload):
    cur = payload
    for tok in _TOK.findall(path):
        if tok.startswith("["):
            i = int(tok[1:-1])
            if not isinstance(cur, list) or i >= len(cur):
                return None
            cur = cur[i]
        else:
            if not isinstance(cur, dict) or tok not in cur:
                return None
            cur = cur[tok]
    return cur


def _empty(v):
    return v is None or v == "" or v == {} or v == []


def check_evidence(evidence, payload):
    """Drop evidence items whose cited field path is missing or empty.
    Items that do not start with a field path are kept."""
    kept, dropped = [], []
    for e in evidence:
        m = _PATH.match(e)
        if m and _empty(_resolve(m.group(1), payload)):
            dropped.append(e)
        else:
            kept.append(e)
    return kept, dropped

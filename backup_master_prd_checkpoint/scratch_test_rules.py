import re
from typing import Dict, Any, Optional

UNIT_TABLE_EXTENDED = {
    "metres": ("length", 1.0, "m"),
    "metre": ("length", 1.0, "m"),
    "percent": ("percentage", 1.0, "%"),
    "percentage": ("percentage", 1.0, "%"),
    "pct": ("percentage", 1.0, "%"),
    "lumens per watt": ("luminous_efficacy", 1.0, "lm/W"),
    "lumens/watt": ("luminous_efficacy", 1.0, "lm/W"),
    "lumen/watt": ("luminous_efficacy", 1.0, "lm/W"),
    "lm/w": ("luminous_efficacy", 1.0, "lm/W"),
    "lm/watt": ("luminous_efficacy", 1.0, "lm/W"),
    "nodes": ("count", 1.0, "nodes"),
    "node": ("count", 1.0, "nodes"),
    "tls": ("protocol_tls", 1.0, "TLS"),
}

SYNONYMS = [
    (r"\brole[- ]based access control\b", "rbac"),
    (r"\boperation[s]? and maintenance\b", "o&m"),
    (r"\boperating and maintenance\b", "o&m"),
    (r"\bgnss\b", "gps"),
    (r"\blatitude/longitude\b", "location tagging"),
    (r"\brest endpoints\b", "rest api"),
    (r"\bindian standards\b", "bis"),
    (r"\blithium iron phosphate\b", "lifepo4"),
    (r"\blithium ferro phosphate\b", "lifepo4"),
    (r"\blfp\b", "lifepo4"),
    (r"\bmetres\b", "m"),
    (r"\bmeters\b", "m"),
    (r"\bpercent\b", "%"),
]

def canonicalize(text: str) -> str:
    t = text.lower()
    for pat, rep in SYNONYMS:
        t = re.sub(pat, rep, t)
    return t

print("Script template ready.")

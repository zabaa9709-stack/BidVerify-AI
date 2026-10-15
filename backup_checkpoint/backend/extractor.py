"""
BidVerify AI - Dynamic Procurement Requirement Extractor

Extracts requirements and vendor specifications from ANY procurement document
without hardcoded knowledge of the product category, requirement names, or
document structure.

Works for: laptops, bicycles, hospital equipment, solar panels, vehicles,
machinery, furniture, networking equipment, software/services, and any
other procurement category that has never been seen before.

Four-phase extraction pipeline:
  Phase 1 — Structured table / numbered-list sequence detection
  Phase 2 — Universal key-value pair extraction (any key, any value)
  Phase 3 — Bullet-point requirement clauses
  Phase 4 — Requirement-signal sentence detection

All four phases are document-structure-agnostic and terminology-agnostic.
"""

import re
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

# UNIT_TABLE is the canonical source in comparator.py.
# Import it here for numeric parsing without duplicating 200 lines.
from comparator import UNIT_TABLE


# ─────────────────────────────────────────────────────────────────────────────
# Category inference
# ─────────────────────────────────────────────────────────────────────────────

_COMMERCIAL_KW = frozenset({
    "price", "cost", "budget", "value", "amount", "bid", "emd", "earnest",
    "deposit", "turnover", "revenue", "financial", "payment", "invoice",
    "quote", "quotation", "rate", "tariff", "fee", "charge", "tender value",
})

_OPERATIONAL_KW = frozenset({
    "warranty", "guarantee", "amc", "maintenance", "delivery", "dispatch",
    "installation", "commissioning", "schedule", "timeline", "period",
    "support", "service", "sla", "response time", "lead time", "quantity",
    "qty", "nos", "units", "pieces", "sets", "documentation", "certificate",
    "certification", "compliance", "training", "handover", "after-sales",
})


def _infer_category(name: str, value: str) -> str:
    text = (name + " " + value).lower()
    if any(k in text for k in _COMMERCIAL_KW):
        return "commercial"
    if any(k in text for k in _OPERATIONAL_KW):
        return "operational"
    return "technical"


# ─────────────────────────────────────────────────────────────────────────────
# Condition detection
# ─────────────────────────────────────────────────────────────────────────────

_MIN_KW = (
    "minimum", "min.", "min ", "at least", "not less than", "≥", ">=",
    "or higher", "or above", "or more", "upwards of", "no less than",
    "atleast", "not below",
)
_MAX_KW = (
    "maximum", "max.", "max ", "not more than", "not exceeding", "≤", "<=",
    "or lower", "or less", "up to", "within", "ceiling", "shall not exceed",
    "no more than", "not above",
)
_RANGE_PAT = re.compile(
    r"\d+(?:\.\d+)?\s*[a-zA-Z°℃%/\"]*\s*(?:to|–|—)\s*\d+",
    re.IGNORECASE
)


def _detect_condition(text: str, default: str = "minimum") -> str:
    t = text.lower()
    if _RANGE_PAT.search(text):
        return "range"
    if any(k in t for k in _MIN_KW):
        return "minimum"
    if any(k in t for k in _MAX_KW):
        return "maximum"
    if re.search(r"\b(exactly|strictly|only|equal to)\b", t):
        return "exact"
    return default


# ─────────────────────────────────────────────────────────────────────────────
# Numeric parsing (using UNIT_TABLE from comparator.py)
# ─────────────────────────────────────────────────────────────────────────────

_IGNORE_SUFFIXES = frozenset({"th", "rd", "st", "nd", "bit", "gen", "generation", "x"})


def _parse_primary_quantity(text: str) -> Dict[str, Any]:
    """
    Extracts the primary numeric quantity and unit from text.
    Returns enriched dict or {} if no numeric found.
    """
    # Handle expandable: "16 GB expandable to 64 GB" → use base
    exp_m = re.search(
        r"(?:expandable|upgradable|scalable)\s+(?:up\s+)?to\s+[\d,]+",
        text, re.IGNORECASE
    )
    if exp_m:
        text = text[:exp_m.start()].strip()

    # Currency shortcut (lakhs / crores)
    curr = re.search(r"(\d+(?:\.\d+)?)\s*(lakhs?|crores?|cr\b|l\b)", text, re.IGNORECASE)
    if curr:
        val = float(curr.group(1))
        u   = curr.group(2).lower()
        val = val * 10_000_000 if u in ("crore", "crores", "cr") else val * 100_000
        return {"value": val, "unit": "INR", "dimension": "currency",
                "norm_val": val, "base_unit": "INR"}

    # Digital storage
    stor = re.search(r"(\d+(?:\.\d+)?)\s*(TB|GB|MB)\b", text, re.IGNORECASE)
    if stor:
        val  = float(stor.group(1))
        unit = stor.group(2).upper()
        nv   = val * 1024 if unit == "TB" else (val / 1024 if unit == "MB" else val)
        return {"value": val, "unit": unit, "dimension": "storage_gb",
                "norm_val": nv, "base_unit": "GB"}

    # General number + unit
    best: Dict[str, Any] = {}
    best_priority = -1
    for m in re.finditer(r"([\d,]+(?:\.\d+)?)\s*([a-zA-Z°℃%/\"]+)?", text):
        raw_num = m.group(1).replace(",", "")
        try:
            num = float(raw_num)
        except ValueError:
            continue
        unit_str = (m.group(2) or "").strip().lower()
        if unit_str in _IGNORE_SUFFIXES:
            continue
        if unit_str in UNIT_TABLE:
            dim, factor, base_unit = UNIT_TABLE[unit_str]
            cand = {"value": num, "unit": unit_str, "dimension": dim,
                    "norm_val": num * factor, "base_unit": base_unit, "priority": 2}
        elif unit_str:
            cand = {"value": num, "unit": unit_str, "dimension": f"custom_{unit_str}",
                    "norm_val": num, "base_unit": unit_str, "priority": 1}
        else:
            cand = {"value": num, "unit": "", "dimension": "unitless",
                    "norm_val": num, "base_unit": "", "priority": 0}
        if cand["priority"] > best_priority:
            best = cand
            best_priority = cand["priority"]

    return best


def _parse_range_from_text(text: str) -> Optional[Dict[str, Any]]:
    """Extracts a numeric range [min, max] with unit from text."""
    pat = re.compile(
        r"(?:between|from)?\s*([\d,]+(?:\.\d+)?)\s*([a-zA-Z°℃%/\"]*)?\s*"
        r"(?:to|–|—|\s+-\s+|(?<=\d)-(?=\d))\s*([\d,]+(?:\.\d+)?)\s*([a-zA-Z°℃%/\"]*)?",
        re.IGNORECASE
    )
    m = pat.search(text)
    if not m:
        return None
    try:
        n1 = float(m.group(1).replace(",", ""))
        n2 = float(m.group(3).replace(",", ""))
    except ValueError:
        return None
    unit_str = (m.group(4) or m.group(2) or "").strip().lower()
    mn, mx = min(n1, n2), max(n1, n2)
    dim, factor, base_unit = None, 1.0, unit_str
    if unit_str in UNIT_TABLE:
        dim, factor, base_unit = UNIT_TABLE[unit_str]
    return {"min": mn, "max": mx, "norm_min": mn * factor, "norm_max": mx * factor,
            "unit": unit_str, "dimension": dim, "base_unit": base_unit}


# ─────────────────────────────────────────────────────────────────────────────
# Mandatory detection
# ─────────────────────────────────────────────────────────────────────────────

_MANDATORY_KW = (
    "shall", "must", "required", "mandatory", "essential", "compulsory",
    "minimum", "at least", "necessary", "obligatory",
)


def _is_mandatory(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in _MANDATORY_KW)


# ─────────────────────────────────────────────────────────────────────────────
# Text normalisation helpers
# ─────────────────────────────────────────────────────────────────────────────

def _normalize_name(raw: str) -> str:
    """Title-cases a raw requirement name, stripping leading bullets/numbers."""
    cleaned = re.sub(r"^[\d\.)\(\[\]#\-\*•\s]+", "", raw)
    cleaned = re.sub(r"[:—–=|\-]+$", "", cleaned).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.title() if cleaned else raw.strip().title()


def _clean_value(val: str) -> str:
    """Strips leading/trailing artefacts from extracted values."""
    val = re.sub(r"^[–—\-:\s]+", "", val)
    val = re.sub(r"[\s\.,;]+$", "", val)
    return re.sub(r"\s+", " ", val).strip()


# ─────────────────────────────────────────────────────────────────────────────
# Enrichment — build a full requirement dict from name + value text
# ─────────────────────────────────────────────────────────────────────────────

def _enrich(name: str, value: str, raw_text: str) -> Dict[str, Any]:
    """
    Builds a rich requirement dict from a name/value pair.
    Handles numeric, range, and qualitative requirements generically.
    """
    condition = _detect_condition(value, default="minimum")
    category  = _infer_category(name, value)
    mandatory = _is_mandatory(raw_text + " " + value)

    # Try range first (more specific)
    range_info = None
    if condition == "range" or re.search(r"\bto\b", value, re.IGNORECASE):
        range_info = _parse_range_from_text(value)

    qty_info  = _parse_primary_quantity(value) if not range_info else {}
    is_numeric = bool(range_info) or bool(qty_info)

    return {
        "requirement_id": "req_" + uuid.uuid4().hex[:8],
        "requirement":    name,
        "value":          value,
        "condition":      condition,
        "category":       category,
        "mandatory":      mandatory,
        "is_numeric":     is_numeric,
        # Numeric fields (None when not applicable)
        "numeric_value":  qty_info.get("value")      if qty_info else None,
        "min_value":      range_info["min"]           if range_info else None,
        "max_value":      range_info["max"]           if range_info else None,
        "unit":           (range_info["unit"]         if range_info else qty_info.get("unit")),
        "dimension":      (range_info["dimension"]    if range_info else qty_info.get("dimension")),
        "norm_value":     (range_info["norm_min"]     if range_info else qty_info.get("norm_val")),
        "norm_max":       range_info["norm_max"]      if range_info else None,
        "base_unit":      (range_info["base_unit"]    if range_info else qty_info.get("base_unit")),
        # Source evidence
        "raw_text":       raw_text.strip(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Requirement-signal patterns (Phase 3 / 4)
# ─────────────────────────────────────────────────────────────────────────────

_REQ_SIGNAL = re.compile(
    r"\b(?:"
    r"minimum|maximum|at\s+least|not\s+less\s+than|not\s+more\s+than"
    r"|not\s+exceeding|shall|must|required|mandatory"
    r"|certified|certification|comply|compliance|conform|standard"
    r"|approved|accredited|iso\s*\d+|bis\s*\d*"
    r"|shall\s+include|must\s+include|shall\s+provide|shall\s+support"
    r")\b"
    r"|(?:\d+\s*(?:[a-zA-Z°℃]+)?\s*(?:to|–)\s*\d+)",   # Range pattern
    re.IGNORECASE
)

_MIN_CLAUSE_LEN = 15


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 1 — Numbered / table sequence detector
# ─────────────────────────────────────────────────────────────────────────────

_FOOTER_PHRASES = (
    "compliance note", "compliance instruction", "vendor declaration",
    "note:", "terms and conditions", "disclaimer", "general conditions",
    "authorized signatory", "company seal",
)


def _parse_table_sequence(lines: List[str]) -> List[Dict[str, str]]:
    """
    Detects a continuous ascending sequence of row numbers (1, 2, 3 …) and
    extracts the requirement name and value from each row's content lines.
    Works for any structured tender table flattened by PDF extraction.
    """
    row_candidates = []
    for idx, line in enumerate(lines):
        stripped = line.strip().lstrip("#").rstrip(".").rstrip(")").rstrip("]").lstrip("[").strip()
        if stripped.isdigit():
            n = int(stripped)
            if 1 <= n <= 500:
                row_candidates.append((n, idx))

    # Find the longest continuous ascending sequence starting from 1
    valid_seq: List[Tuple[int, int]] = []
    for num, idx in row_candidates:
        if not valid_seq:
            if num in (0, 1):
                valid_seq.append((num, idx))
        elif num == valid_seq[-1][0] + 1:
            valid_seq.append((num, idx))

    if len(valid_seq) < 3:
        return []

    results = []
    for i, (num, start_idx) in enumerate(valid_seq):
        end_idx = valid_seq[i + 1][1] if i + 1 < len(valid_seq) else min(start_idx + 8, len(lines))
        content_lines = lines[start_idx + 1: end_idx]

        filtered = []
        for cl in content_lines:
            cl_l = cl.strip().lower()
            if any(cl_l.startswith(fp) for fp in _FOOTER_PHRASES):
                break
            if cl.strip():
                filtered.append(cl.strip())

        if not filtered:
            continue

        if len(filtered) >= 2:
            raw_name = filtered[0]
            raw_val  = " ".join(filtered[1:])
        else:
            single = filtered[0]
            parts  = re.split(r"\s*[:—–=|-]\s*", single, maxsplit=1)
            raw_name, raw_val = (parts[0], parts[1]) if len(parts) == 2 else (single, single)

        # Trim any footer text that leaked into the value
        for fp in _FOOTER_PHRASES:
            fp_pos = raw_val.lower().find(fp)
            if fp_pos != -1:
                raw_val = raw_val[:fp_pos].strip()

        raw_snippet = "\n".join([lines[start_idx]] + filtered)
        results.append({"raw_name": raw_name, "raw_value": raw_val, "raw_text": raw_snippet})

    return results


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2 — Universal key-value extractor
# ─────────────────────────────────────────────────────────────────────────────

# Accepts any key of 2–50 chars followed by a separator and a value.
# No filtering by known requirement names.
_KV_PATTERN = re.compile(
    r"^(?:(?:\d{1,3}|[a-z])[\.\)]\s*)?"        # optional bullet/number
    r"([A-Za-z][A-Za-z0-9\s/_\-]{1,49})"        # key: 2-50 chars
    r"\s*[:—–=|-]\s*"                            # separator
    r"(.+)$"                                     # value
)
_MIN_VAL_LEN = 2
_MAX_WORDS_IN_VAL = 35  # reject full-sentence prose as values


def _parse_kv_lines(lines: List[str]) -> List[Dict[str, str]]:
    """Extracts key-value pairs from any line, for any key, for any category."""
    results = []
    for line in lines:
        m = _KV_PATTERN.match(line.strip())
        if not m:
            continue
        raw_key = m.group(1).strip()
        raw_val = m.group(2).strip()
        if len(raw_val) < _MIN_VAL_LEN:
            continue
        if len(raw_val) > 300:
            continue
        if raw_val.count(" ") > _MAX_WORDS_IN_VAL:
            continue
        results.append({"raw_name": raw_key, "raw_value": raw_val, "raw_text": line.strip()})
    return results


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 3 — Bullet-point requirement clauses
# ─────────────────────────────────────────────────────────────────────────────

_BULLET_PAT = re.compile(r"^[\-\*•◦▸►✓✔⬥]\s+(.+)$")


def _parse_bullet_items(lines: List[str]) -> List[Dict[str, str]]:
    """Extracts bullet-point clauses that contain requirement signal keywords."""
    results = []
    for line in lines:
        m = _BULLET_PAT.match(line.strip())
        if not m:
            continue
        content = m.group(1).strip()
        if len(content) < _MIN_CLAUSE_LEN or not _REQ_SIGNAL.search(content):
            continue
        kv = re.match(r"([A-Za-z][A-Za-z0-9\s/_\-]{1,40})\s*[:—–=|-]\s*(.+)", content)
        if kv:
            results.append({"raw_name": kv.group(1).strip(),
                            "raw_value": kv.group(2).strip(), "raw_text": line.strip()})
        else:
            results.append({"raw_name": content[:50].strip(),
                            "raw_value": content, "raw_text": line.strip()})
    return results


# ─────────────────────────────────────────────────────────────────────────────
# PHASE 4 — Requirement-signal sentence detection
# ─────────────────────────────────────────────────────────────────────────────

def _detect_req_sentences(lines: List[str]) -> List[Dict[str, str]]:
    """
    Scans every line for procurement requirement signal patterns.
    Suitable for free-text paragraphs and non-structured clauses.
    """
    results = []
    seen: Set[str] = set()

    for line in lines:
        stripped = line.strip()
        if len(stripped) < _MIN_CLAUSE_LEN or stripped in seen:
            continue
        if not _REQ_SIGNAL.search(stripped):
            continue
        seen.add(stripped)

        # Try key: value split
        kv = re.match(
            r"^(?:[\d\.)\(\[\]#\-\*•\s]{0,10})?"
            r"([A-Za-z][A-Za-z0-9\s/_\-]{2,40})\s*[:—–=|-]\s*(.+)$",
            stripped
        )
        if kv:
            raw_name = kv.group(1).strip()
            raw_val  = kv.group(2).strip()
        else:
            label = re.match(
                r"^([A-Za-z][A-Za-z0-9\s/_\-]{2,35})"
                r"(?:\s+shall|\s+must|\s+should|\s+is|\s+are|\s+will)?\b",
                stripped, re.IGNORECASE
            )
            raw_name = label.group(1).strip() if label else stripped[:40].strip()
            raw_val  = stripped

        results.append({"raw_name": raw_name, "raw_value": raw_val, "raw_text": stripped})

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Main extraction function
# ─────────────────────────────────────────────────────────────────────────────

def extract_requirements_from_text(text: str) -> List[Dict[str, Any]]:
    """
    Dynamically extracts procurement requirements from ANY document text.

    Does NOT use hardcoded requirement names or product-specific patterns.
    Works for laptops, bicycles, hospital equipment, solar panels, vehicles,
    furniture, construction materials, software/services, or any other
    category that has never been seen before.

    Runs four phases in order of structural confidence:
      1. Numbered / table row sequence
      2. Universal key-value pairs
      3. Bullet-point requirement clauses
      4. Requirement-signal sentences

    Returns a list of enriched requirement dicts with the schema:
    {
        requirement_id, requirement, value, condition, category, mandatory,
        is_numeric, numeric_value, min_value, max_value, unit, dimension,
        norm_value, norm_max, base_unit, raw_text
    }
    """
    if not text or not text.strip():
        return []

    lines = [line for line in text.split("\n") if line.strip()]

    seen_names: Set[str] = set()
    candidates: List[Dict[str, str]] = []

    def _add(raw_name: str, raw_value: str, raw_text: str) -> None:
        name  = _normalize_name(raw_name)
        value = _clean_value(raw_value)
        if not name or not value or len(value) < 2:
            return
        key = name.lower()
        if key in seen_names:
            return
        seen_names.add(key)
        candidates.append({"raw_name": name, "raw_value": value, "raw_text": raw_text})

    # ── Phase 1 ──────────────────────────────────────────────────────────────
    for row in _parse_table_sequence(lines):
        _add(row["raw_name"], row["raw_value"], row["raw_text"])

    # ── Phase 2 ──────────────────────────────────────────────────────────────
    for row in _parse_kv_lines(lines):
        _add(row["raw_name"], row["raw_value"], row["raw_text"])

    # ── Phase 3 ──────────────────────────────────────────────────────────────
    for row in _parse_bullet_items(lines):
        _add(row["raw_name"], row["raw_value"], row["raw_text"])

    # ── Phase 4 ──────────────────────────────────────────────────────────────
    for row in _detect_req_sentences(lines):
        _add(row["raw_name"], row["raw_value"], row["raw_text"])

    # ── Enrich ───────────────────────────────────────────────────────────────
    return [_enrich(c["raw_name"], c["raw_value"], c["raw_text"]) for c in candidates]

"""
BidVerify AI - Generic Compliance Comparison Engine

Evaluates vendor specifications against tender requirements using:
  - Numeric constraint evaluation: MINIMUM, MAXIMUM, RANGE, EXACT
  - Generic unit normalization across physical dimensions
  - Qualitative semantic comparison (deterministic + AI-assisted)
  - Multi-confidence decision model

No product-specific rules. Works for laptops, bicycles, hospital equipment,
solar panels, vehicles, machinery, furniture, or any other procurement category.
"""

import re
from typing import Any, Dict, List, Optional, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# Legacy parse helpers (kept for backward compatibility with any direct callers)
# ─────────────────────────────────────────────────────────────────────────────

def _parse_bytes_capacity_gb(text: str) -> Optional[float]:
    """Extracts digital storage/memory capacity and normalizes to GB."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*(TB|GB|MB)\b", text, re.IGNORECASE)
    if not m:
        return None
    val = float(m.group(1))
    unit = m.group(2).upper()
    if unit == "TB":
        return val * 1024.0
    if unit == "MB":
        return val / 1024.0
    return val


def _parse_weight_kg(text: str) -> Optional[float]:
    """Extracts weight value and normalizes to Kilograms."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*(kg|kilograms?|grams?|g)\b", text, re.IGNORECASE)
    if not m:
        return None
    val = float(m.group(1))
    unit = m.group(2).lower()
    if unit in ("g", "gram", "grams"):
        return val / 1000.0
    return val


def _parse_days(text: str) -> Optional[float]:
    """Extracts duration and normalizes to Days."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*(days?|weeks?|months?)\b", text, re.IGNORECASE)
    if not m:
        return None
    val = float(m.group(1))
    unit = m.group(2).lower()
    if "week" in unit:
        return val * 7.0
    if "month" in unit:
        return val * 30.0
    return val


def _parse_hours(text: str) -> Optional[float]:
    """Extracts duration in hours."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?)\b", text, re.IGNORECASE)
    if not m:
        return None
    return float(m.group(1))


def _parse_years(text: str) -> Optional[float]:
    """Extracts duration in years."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:years?|yrs?|months?)\b", text, re.IGNORECASE)
    if not m:
        return None
    val = float(m.group(1))
    unit_text = text[m.start(0):m.end(0)].lower()
    if "month" in unit_text:
        return val / 12.0
    return val


def _parse_currency_amount(text: str) -> Optional[float]:
    """Extracts currency values (INR / Rs / ₹) handling Lakhs, Crores."""
    m_word = re.search(r"(\d+(?:\.\d+)?)\s*(lakhs?|crores?|cr|l)\b", text, re.IGNORECASE)
    if m_word:
        val = float(m_word.group(1))
        unit = m_word.group(2).lower()
        if unit in ("crore", "crores", "cr"):
            return val * 10_000_000.0
        return val * 100_000.0
    m_num = re.search(
        r"(?:INR|Rs\.?|₹)?\s*([0-9]{1,3}(?:,[0-9]{2,3})+(?:\.[0-9]+)?|[0-9]{4,}(?:\.[0-9]+)?)",
        text, re.IGNORECASE
    )
    if m_num:
        try:
            return float(m_num.group(1).replace(",", ""))
        except ValueError:
            return None
    return None


def _parse_quantity(text: str) -> Optional[int]:
    """Extracts unit counts from quantity specifications."""
    m = re.search(r"(\d+[\d,]*)\s*(?:units?|nos?\.?|pieces?|sets?|items?)?", text, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1).replace(",", ""))
        except ValueError:
            return None
    return None


def _parse_webcam_mp(text: str) -> Optional[float]:
    """Extracts camera resolution in Megapixels or equivalent resolution."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*MP\b", text, re.IGNORECASE)
    if m:
        return float(m.group(1))
    if re.search(r"\b(?:4K|UHD)\b", text, re.IGNORECASE):
        return 8.0
    if re.search(r"\b(?:1080p|Full\s*HD|FHD)\b", text, re.IGNORECASE):
        return 2.0
    if re.search(r"\b(?:720p|HD)\b", text, re.IGNORECASE):
        return 1.0
    return None


def _parse_cores(text: str) -> Optional[int]:
    """Extracts CPU core count."""
    m = re.search(r"(\d+)\s*(?:cores?|octa[- ]core)\b", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    if "octa-core" in text.lower() or "octa core" in text.lower():
        return 8
    if "hexa-core" in text.lower() or "six core" in text.lower():
        return 6
    if "quad-core" in text.lower() or "quad core" in text.lower():
        return 4
    return None


def _clean_text(s: str) -> str:
    """Normalizes whitespace, casing, and standard symbols for text comparison."""
    s = s.lower()
    s = re.sub(r"[^\w\s\.+°℃-]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _clean_number(num_str: str) -> Optional[float]:
    """Cleans commas and whitespace from numeric string and converts to float."""
    clean = num_str.replace(",", "").strip()
    try:
        return float(clean)
    except ValueError:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# UNIT_TABLE — canonical source of truth for all physical unit conversions.
# Format: unit_string → (dimension_name, factor_to_base_unit, display_base_unit)
# ─────────────────────────────────────────────────────────────────────────────

UNIT_TABLE: Dict[str, Tuple[str, float, str]] = {
    # Luminous flux
    "lumens": ("luminous_flux", 1.0, "lumens"),
    "lumen":  ("luminous_flux", 1.0, "lumens"),
    "lm":     ("luminous_flux", 1.0, "lumens"),
    "klm":    ("luminous_flux", 1000.0, "lumens"),
    # Illuminance & intensity
    "lux":    ("illuminance", 1.0, "lux"),
    "lx":     ("illuminance", 1.0, "lux"),
    "cd":     ("intensity", 1.0, "cd"),
    "candela":("intensity", 1.0, "cd"),
    # Temperature
    "k":          ("temp_k", 1.0, "K"),
    "kelvin":     ("temp_k", 1.0, "K"),
    "°c":         ("temp_c", 1.0, "°C"),
    "℃":          ("temp_c", 1.0, "°C"),
    "c":          ("temp_c", 1.0, "°C"),
    "deg c":      ("temp_c", 1.0, "°C"),
    "degree c":   ("temp_c", 1.0, "°C"),
    "degrees c":  ("temp_c", 1.0, "°C"),
    "°f":         ("temp_f", 1.0, "°F"),
    "℉":          ("temp_f", 1.0, "°F"),
    "f":          ("temp_f", 1.0, "°F"),
    # Electric charge / battery capacity
    "ah":           ("electric_charge", 1.0, "Ah"),
    "ampere-hour":  ("electric_charge", 1.0, "Ah"),
    "ampere-hours": ("electric_charge", 1.0, "Ah"),
    "amp-hour":     ("electric_charge", 1.0, "Ah"),
    "amp-hours":    ("electric_charge", 1.0, "Ah"),
    "mah":          ("electric_charge", 0.001, "Ah"),
    # Energy
    "wh":          ("energy", 1.0, "Wh"),
    "watt-hour":   ("energy", 1.0, "Wh"),
    "watt-hours":  ("energy", 1.0, "Wh"),
    "kwh":         ("energy", 1000.0, "Wh"),
    "mwh":         ("energy", 1_000_000.0, "Wh"),
    # Power
    "w":        ("power", 1.0, "W"),
    "watts":    ("power", 1.0, "W"),
    "watt":     ("power", 1.0, "W"),
    "kw":       ("power", 1000.0, "W"),
    "kilowatt": ("power", 1000.0, "W"),
    "kilowatts":("power", 1000.0, "W"),
    "mw":       ("power", 0.001, "W"),
    "hp":       ("power", 745.7, "W"),
    # Voltage
    "v":     ("voltage", 1.0, "V"),
    "volts": ("voltage", 1.0, "V"),
    "volt":  ("voltage", 1.0, "V"),
    "kv":    ("voltage", 1000.0, "V"),
    "mv":    ("voltage", 0.001, "V"),
    # Current
    "a":       ("current", 1.0, "A"),
    "amps":    ("current", 1.0, "A"),
    "amp":     ("current", 1.0, "A"),
    "amperes": ("current", 1.0, "A"),
    "ampere":  ("current", 1.0, "A"),
    "ma":      ("current", 0.001, "A"),
    # Mass / Weight
    "kg":        ("mass", 1.0, "kg"),
    "kgs":       ("mass", 1.0, "kg"),
    "kilogram":  ("mass", 1.0, "kg"),
    "kilograms": ("mass", 1.0, "kg"),
    "g":         ("mass", 0.001, "kg"),
    "gram":      ("mass", 0.001, "kg"),
    "grams":     ("mass", 0.001, "kg"),
    "mg":        ("mass", 0.000001, "kg"),
    "ton":       ("mass", 1000.0, "kg"),
    "tons":      ("mass", 1000.0, "kg"),
    "tonne":     ("mass", 1000.0, "kg"),
    "tonnes":    ("mass", 1000.0, "kg"),
    "quintal":   ("mass", 100.0, "kg"),
    "quintals":  ("mass", 100.0, "kg"),
    "lbs":       ("mass", 0.453592, "kg"),
    "pound":     ("mass", 0.453592, "kg"),
    "pounds":    ("mass", 0.453592, "kg"),
    # Digital storage
    "tb":        ("storage_gb", 1024.0, "GB"),
    "terabytes": ("storage_gb", 1024.0, "GB"),
    "gb":        ("storage_gb", 1.0, "GB"),
    "gigabytes": ("storage_gb", 1.0, "GB"),
    "mb":        ("storage_gb", 1.0 / 1024.0, "GB"),
    "megabytes": ("storage_gb", 1.0 / 1024.0, "GB"),
    "kb":        ("storage_gb", 1.0 / (1024.0 * 1024.0), "GB"),
    # Time — days
    "days":   ("time_days", 1.0, "days"),
    "day":    ("time_days", 1.0, "days"),
    "weeks":  ("time_days", 7.0, "days"),
    "week":   ("time_days", 7.0, "days"),
    "wks":    ("time_days", 7.0, "days"),
    "wk":     ("time_days", 7.0, "days"),
    "months": ("time_days", 30.0, "days"),
    "month":  ("time_days", 30.0, "days"),
    "years":  ("time_days", 365.0, "days"),
    "year":   ("time_days", 365.0, "days"),
    "yrs":    ("time_days", 365.0, "days"),
    "yr":     ("time_days", 365.0, "days"),
    # Time — hours
    "hours":   ("time_hours", 1.0, "hours"),
    "hour":    ("time_hours", 1.0, "hours"),
    "hrs":     ("time_hours", 1.0, "hours"),
    "hr":      ("time_hours", 1.0, "hours"),
    "minutes": ("time_hours", 1.0 / 60.0, "hours"),
    "minute":  ("time_hours", 1.0 / 60.0, "hours"),
    "mins":    ("time_hours", 1.0 / 60.0, "hours"),
    "min":     ("time_hours", 1.0 / 60.0, "hours"),
    # Speed
    "km/h":  ("speed", 1.0, "km/h"),
    "kmph":  ("speed", 1.0, "km/h"),
    "kph":   ("speed", 1.0, "km/h"),
    "m/s":   ("speed", 3.6, "km/h"),
    "mph":   ("speed", 1.60934, "km/h"),
    # Length
    "mm":     ("length", 0.001, "m"),
    "cm":     ("length", 0.01, "m"),
    "m":      ("length", 1.0, "m"),
    "meters": ("length", 1.0, "m"),
    "meter":  ("length", 1.0, "m"),
    "km":     ("length", 1000.0, "m"),
    "inch":   ("length", 0.0254, "m"),
    "inches": ("length", 0.0254, "m"),
    "\"":     ("length", 0.0254, "m"),
    "ft":     ("length", 0.3048, "m"),
    "feet":   ("length", 0.3048, "m"),
    # Pressure
    "bar":    ("pressure", 1.0, "bar"),
    "psi":    ("pressure", 0.0689476, "bar"),
    "kpa":    ("pressure", 0.01, "bar"),
    "mpa":    ("pressure", 10.0, "bar"),
    # Rotational speed
    "rpm": ("rpm", 1.0, "rpm"),
    # Frequency
    "hz":  ("frequency", 1.0, "Hz"),
    "khz": ("frequency", 1_000.0, "Hz"),
    "mhz": ("frequency", 1_000_000.0, "Hz"),
    "ghz": ("frequency", 1_000_000_000.0, "Hz"),
    # Resolution
    "mp":         ("resolution_mp", 1.0, "MP"),
    "megapixels": ("resolution_mp", 1.0, "MP"),
    # Processor cores
    "cores": ("cores", 1.0, "cores"),
    "core":  ("cores", 1.0, "cores"),
    # Count / Units
    "units":  ("count", 1.0, "units"),
    "unit":   ("count", 1.0, "units"),
    "nos":    ("count", 1.0, "units"),
    "no":     ("count", 1.0, "units"),
    "pieces": ("count", 1.0, "units"),
    "pcs":    ("count", 1.0, "units"),
    "sets":   ("count", 1.0, "units"),
    "items":  ("count", 1.0, "units"),
    # Area
    "sqm":   ("area", 1.0, "m²"),
    "m2":    ("area", 1.0, "m²"),
    "sqft":  ("area", 0.0929, "m²"),
    "sqkm":  ("area", 1_000_000.0, "m²"),
    # Volume
    "l":     ("volume", 1.0, "L"),
    "ml":    ("volume", 0.001, "L"),
    "liter": ("volume", 1.0, "L"),
    "litre": ("volume", 1.0, "L"),
    # Bandwidth / data rate
    "bps":   ("data_rate", 1.0, "bps"),
    "kbps":  ("data_rate", 1_000.0, "bps"),
    "mbps":  ("data_rate", 1_000_000.0, "bps"),
    "gbps":  ("data_rate", 1_000_000_000.0, "bps"),
    # Percentage
    "%":     ("percentage", 1.0, "%"),
}


# ─────────────────────────────────────────────────────────────────────────────
# Range & Quantity Parsing
# ─────────────────────────────────────────────────────────────────────────────

def _parse_range(text: str) -> Optional[Dict[str, Any]]:
    """
    Extracts a numeric range [min, max] and associated unit from text.
    Handles: "4000 K to 6500 K", "10°C to 35°C", "10-15 days", "between 5 and 10 kg"
    """
    pat = re.compile(
        r"(?:(?:between|from)\s+)?"
        r"([0-9]{1,3}(?:,[0-9]{2,3})+|[0-9]+(?:\.[0-9]+)?)"
        r"\s*([a-zA-Z°℃%/\"]+)?"
        r"\s*(?:\bto\b|–|—|\s+-\s+|(?<=\d)-(?=\d))\s*"
        r"([0-9]{1,3}(?:,[0-9]{2,3})+|[0-9]+(?:\.[0-9]+)?)"
        r"\s*([a-zA-Z°℃%/\"]+)?",
        re.IGNORECASE
    )
    m = pat.search(text)
    if not m:
        return None

    n1 = _clean_number(m.group(1))
    n2 = _clean_number(m.group(3))
    if n1 is None or n2 is None:
        return None

    unit1 = (m.group(2) or "").strip().lower()
    unit2 = (m.group(4) or "").strip().lower()
    unit = unit2 if unit2 else unit1
    min_val, max_val = min(n1, n2), max(n1, n2)

    dim, factor, base_unit = None, 1.0, unit
    if unit in UNIT_TABLE:
        dim, factor, base_unit = UNIT_TABLE[unit]
    elif unit:
        dim = f"custom_{unit}"

    return {
        "min": min_val, "max": max_val,
        "norm_min": min_val * factor, "norm_max": max_val * factor,
        "unit": unit, "dimension": dim, "base_unit": base_unit,
        "raw_text": m.group(0),
    }


def _handle_expandable(text: str) -> Tuple[str, Optional[float], Optional[str]]:
    """Separates base specification from maximum expandable capacity."""
    m = re.search(
        r"(?:expandable|upgradable|scalable)\s+(?:up\s+)?to\s+"
        r"([0-9]{1,3}(?:,[0-9]{2,3})+|[0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z]+)?",
        text, re.IGNORECASE
    )
    if m:
        exp_val = _clean_number(m.group(1))
        exp_unit = (m.group(2) or "").strip()
        base_text = text[:m.start(0)].strip()
        return base_text, exp_val, exp_unit
    return text, None, None


def _parse_quantity_and_unit(text: str) -> Optional[Dict[str, Any]]:
    """Extracts primary number and unit from string with UNIT_TABLE normalization."""
    # 1. Currency
    amt = _parse_currency_amount(text)
    if amt is not None and any(k in text.lower() for k in ["inr", "rs", "₹", "lakh", "crore", "cr", "budget", "price", "cost", "value"]):
        return {"value": amt, "unit": "INR", "dimension": "currency", "norm_val": amt, "base_unit": "INR"}

    # 2. Expandable split
    base_text, exp_val, exp_unit = _handle_expandable(text)

    # 3. Digital storage (TB/GB/MB)
    cap_gb = _parse_bytes_capacity_gb(base_text)
    if cap_gb is not None:
        m_st = re.search(r"(\d+(?:\.\d+)?)\s*(TB|GB|MB)\b", base_text, re.IGNORECASE)
        unit_st = m_st.group(2).upper() if m_st else "GB"
        val_st = float(m_st.group(1)) if m_st else cap_gb
        return {"value": val_st, "unit": unit_st, "dimension": "storage_gb",
                "norm_val": cap_gb, "base_unit": "GB", "expandable_val": exp_val}

    # 4. General number + unit
    matches = list(re.finditer(
        r"([0-9]{1,3}(?:,[0-9]{2,3})+|[0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z°℃%/\"]+)?",
        base_text
    ))

    candidates = []
    for m in matches:
        num = _clean_number(m.group(1))
        if num is None:
            continue
        unit_str = (m.group(2) or "").strip().lower()
        if unit_str in ("th", "rd", "st", "nd", "bit", "gen", "generation"):
            continue
        if unit_str in UNIT_TABLE:
            dim, factor, base_unit = UNIT_TABLE[unit_str]
            candidates.append({"value": num, "unit": unit_str, "dimension": dim,
                                "norm_val": num * factor, "base_unit": base_unit, "priority": 2})
        elif unit_str:
            candidates.append({"value": num, "unit": unit_str, "dimension": f"custom_{unit_str}",
                                "norm_val": num, "base_unit": unit_str, "priority": 1})
        else:
            candidates.append({"value": num, "unit": "", "dimension": "unitless",
                                "norm_val": num, "base_unit": "", "priority": 0})

    if not candidates:
        return None

    candidates.sort(key=lambda c: c["priority"], reverse=True)
    best = candidates[0]
    if exp_val is not None:
        best["expandable_val"] = exp_val
        if exp_unit is not None:
            best["expandable_unit"] = exp_unit
    return best


def _normalize_to_common_unit(
    q1: Dict[str, Any], q2: Dict[str, Any]
) -> Optional[Tuple[float, float, str]]:
    """Normalizes two quantities to a common base unit if compatible."""
    dim1, dim2 = q1.get("dimension"), q2.get("dimension")

    if dim1 == dim2 and dim1 is not None:
        return q1["norm_val"], q2["norm_val"], q1.get("base_unit", "")

    # Temperature: K ↔ °C
    if {dim1, dim2} == {"temp_k", "temp_c"}:
        v1 = q1["value"] if dim1 == "temp_k" else q1["value"] + 273.15
        v2 = q2["value"] if dim2 == "temp_k" else q2["value"] + 273.15
        return v1, v2, "K"

    # Time: days ↔ hours
    if {dim1, dim2} == {"time_days", "time_hours"}:
        v1 = q1["norm_val"] * 24.0 if dim1 == "time_days" else q1["norm_val"]
        v2 = q2["norm_val"] * 24.0 if dim2 == "time_days" else q2["norm_val"]
        return v1, v2, "hours"

    # Unitless ↔ count
    if {dim1, dim2} == {"unitless", "count"}:
        return q1["norm_val"], q2["norm_val"], "units"

    # Same raw unit string
    if q1.get("unit") and q1.get("unit") == q2.get("unit"):
        return q1["value"], q2["value"], q1["unit"]

    return None


def _detect_constraint_type(text: str, default_cond: str, req_name: str) -> str:
    """Determines whether the constraint is RANGE, MINIMUM, MAXIMUM, or EXACT."""
    text_lower = text.lower()
    name_lower = req_name.lower()

    # Range first (most specific)
    if _parse_range(text) is not None:
        return "RANGE"

    if default_cond == "maximum" or any(k in text_lower for k in [
        "maximum", "max.", "max ", "not more than", "not exceeding", "<=", "≤",
        "or lower", "or less", "up to", "within", "ceiling", "shall not exceed",
    ]):
        return "MAXIMUM"

    if default_cond == "minimum" or any(k in text_lower for k in [
        "minimum", "min.", "min ", "at least", "not less than", ">=", "≥",
        "or higher", "or above", "or more", "upwards of", "no less than",
    ]):
        return "MINIMUM"

    if default_cond == "exact" or any(k in text_lower for k in ["strictly", "exactly", "exact ", "only "]):
        return "EXACT"

    # Domain-name heuristics (generic — price/cost/weight/delivery are always ceilings)
    if any(k in name_lower for k in [
        "price", "cost", "budget", "bid value", "weight", "delivery", "installation",
        "timeline", "response time", "lead time",
    ]):
        return "MAXIMUM"

    return "MINIMUM"


# ─────────────────────────────────────────────────────────────────────────────
# Core numeric comparison engine
# ─────────────────────────────────────────────────────────────────────────────

def compare_generic_quantitative(
    req_name: str,
    tender_val: str,
    tender_cond: str,
    vendor_val: str,
) -> Optional[Dict[str, Any]]:
    """
    Universally compares quantitative tender requirements against vendor values.
    Supports MINIMUM, MAXIMUM, RANGE, and EXACT constraints with dynamic unit
    normalization across ANY physical dimension.

    Returns a compliance result dict or None if no numeric comparison is possible.
    """
    t_range = _parse_range(tender_val)
    v_range = _parse_range(vendor_val)
    t_quant = _parse_quantity_and_unit(tender_val)
    v_quant = _parse_quantity_and_unit(vendor_val)

    if t_range is None and t_quant is None:
        return None
    if v_range is None and v_quant is None:
        return None

    constraint = _detect_constraint_type(tender_val, tender_cond, req_name)

    # ── RANGE ─────────────────────────────────────────────────────────────────
    if constraint == "RANGE" or t_range is not None:
        if t_range is not None:
            t_min, t_max = t_range["norm_min"], t_range["norm_max"]
            dim_t, unit_t = t_range["dimension"], t_range["base_unit"]
        elif t_quant is not None:
            t_min = t_max = t_quant["norm_val"]
            dim_t, unit_t = t_quant["dimension"], t_quant["base_unit"]
        else:
            return None

        def _make_q(norm_val, raw_val, dim, unit):
            return {"dimension": dim, "norm_val": norm_val, "base_unit": unit, "value": raw_val}

        if v_range is not None:
            pair_min = _normalize_to_common_unit(
                _make_q(t_min, t_range["min"] if t_range else t_min, dim_t, unit_t),
                _make_q(v_range["norm_min"], v_range["min"], v_range["dimension"], v_range["base_unit"])
            )
            pair_max = _normalize_to_common_unit(
                _make_q(t_max, t_range["max"] if t_range else t_max, dim_t, unit_t),
                _make_q(v_range["norm_max"], v_range["max"], v_range["dimension"], v_range["base_unit"])
            )
            if pair_min is None or pair_max is None:
                return None
            t_lo, v_lo, _ = pair_min
            t_hi, v_hi, _ = pair_max
            if v_lo >= t_lo and v_hi <= t_hi:
                return {"status": "COMPLIANT", "reason": f"Vendor offers {vendor_val}, which falls within the required range of {tender_val}.", "confidence": 0.98}
            return {"status": "NON_COMPLIANT", "reason": f"Vendor offers {vendor_val}, which is outside the required range of {tender_val}.", "confidence": 0.98}

        elif v_quant is not None:
            pair_lo = _normalize_to_common_unit(_make_q(t_min, t_range["min"] if t_range else t_min, dim_t, unit_t), v_quant)
            pair_hi = _normalize_to_common_unit(_make_q(t_max, t_range["max"] if t_range else t_max, dim_t, unit_t), v_quant)
            if pair_lo is None or pair_hi is None:
                return None
            t_lo, v_val, _ = pair_lo
            t_hi, _, _ = pair_hi
            if t_lo <= v_val <= t_hi:
                return {"status": "COMPLIANT", "reason": f"Vendor offers {vendor_val}, which falls within the required range of {tender_val}.", "confidence": 0.98}
            if v_val < t_lo:
                return {"status": "NON_COMPLIANT", "reason": f"Vendor offers {vendor_val}, which is outside the required range of {tender_val} (below minimum threshold).", "confidence": 0.98}
            return {"status": "NON_COMPLIANT", "reason": f"Vendor offers {vendor_val}, which is outside the required range of {tender_val} (exceeds maximum threshold).", "confidence": 0.98}

    # ── MAXIMUM ───────────────────────────────────────────────────────────────
    if constraint == "MAXIMUM":
        if t_quant is None:
            return None
        if v_range is not None:
            pair = _normalize_to_common_unit(
                t_quant,
                {"dimension": v_range["dimension"], "norm_val": v_range["norm_max"],
                 "base_unit": v_range["base_unit"], "value": v_range["max"]}
            )
            if pair is None:
                return None
            t_ceil, v_max_val, du = pair
            if v_max_val <= t_ceil:
                return {"status": "COMPLIANT", "reason": f"Vendor offers {vendor_val} (maximum {v_range['max']} {du}), which satisfies the required maximum of {tender_val}.", "confidence": 0.98}
            return {"status": "NON_COMPLIANT", "reason": f"Vendor offers {vendor_val} (maximum {v_range['max']} {du}), which exceeds the required maximum of {tender_val}.", "confidence": 0.98}
        elif v_quant is not None:
            pair = _normalize_to_common_unit(t_quant, v_quant)
            if pair is None:
                return None
            t_val, v_val, _ = pair
            if v_val <= t_val:
                return {"status": "COMPLIANT", "reason": f"Vendor offers {vendor_val}, which satisfies the required maximum limit of {tender_val}.", "confidence": 0.98}
            return {"status": "NON_COMPLIANT", "reason": f"Vendor offers {vendor_val}, which exceeds the required maximum limit of {tender_val}.", "confidence": 0.98}

    # ── MINIMUM ───────────────────────────────────────────────────────────────
    if constraint == "MINIMUM":
        if t_quant is None:
            return None
        if v_range is not None:
            pair = _normalize_to_common_unit(
                t_quant,
                {"dimension": v_range["dimension"], "norm_val": v_range["norm_min"],
                 "base_unit": v_range["base_unit"], "value": v_range["min"]}
            )
            if pair is None:
                return None
            t_floor, v_min_val, _ = pair
            if v_min_val >= t_floor:
                return {"status": "COMPLIANT", "reason": f"Vendor offers {vendor_val}, which meets/exceeds the required minimum of {tender_val}.", "confidence": 0.98}
            return {"status": "NON_COMPLIANT", "reason": f"Vendor offers {vendor_val}, which is below the required minimum of {tender_val}.", "confidence": 0.98}
        elif v_quant is not None:
            pair = _normalize_to_common_unit(t_quant, v_quant)
            if pair is None:
                return None
            t_val, v_val, _ = pair
            if v_val >= t_val:
                return {"status": "COMPLIANT", "reason": f"Vendor offers {vendor_val}, which meets/exceeds the required minimum of {tender_val}.", "confidence": 0.98}
            return {"status": "NON_COMPLIANT", "reason": f"Vendor offers {vendor_val}, which is below the required minimum of {tender_val}.", "confidence": 0.98}

    # ── EXACT ─────────────────────────────────────────────────────────────────
    if constraint == "EXACT":
        if t_quant is None or v_quant is None:
            return None
        pair = _normalize_to_common_unit(t_quant, v_quant)
        if pair is None:
            return None
        t_val, v_val, _ = pair
        if v_val == t_val:
            return {"status": "COMPLIANT", "reason": f"Vendor offers {vendor_val}, which satisfies the required exact specification of {tender_val}.", "confidence": 0.95}
        return {"status": "NON_COMPLIANT", "reason": f"Vendor offers {vendor_val}, which does not match the required exact specification of {tender_val}.", "confidence": 0.95}

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Single-requirement comparison (generic, no product-specific logic)
# ─────────────────────────────────────────────────────────────────────────────

_GENERIC_STOP = frozenset({
    "the", "a", "an", "and", "or", "of", "in", "to", "for", "is", "are",
    "be", "with", "at", "by", "from", "as", "on", "it", "its", "not",
    "must", "shall", "should", "will", "can", "may", "per", "unit",
})


def compare_single_requirement(
    req_name: str,
    tender_val: str,
    tender_cond: str,
    vendor_val: Optional[str],
    provider=None,
) -> Dict[str, Any]:
    """
    Compares a single tender requirement against a vendor specification.

    Evaluation order:
      1. NOT_FOUND  — vendor value is absent or empty
      2. Numeric    — compare_generic_quantitative (MINIMUM/MAXIMUM/RANGE/EXACT)
      3. AI         — provider.compare_qualitative if available
      4. Text       — deterministic token-overlap qualitative fallback

    No product-specific rules. Works for any procurement category.
    """
    if vendor_val is None or not str(vendor_val).strip():
        return {
            "status": "NOT_FOUND",
            "reason": (
                f"{req_name} is required in the tender but was not mentioned "
                "or offered in the vendor bid."
            ),
            "confidence": 0.95,
        }

    t_val = tender_val.strip()
    v_val = vendor_val.strip()
    cond  = tender_cond.lower()

    # ── 1. Numeric quantitative comparison ────────────────────────────────────
    quant_res = compare_generic_quantitative(req_name, t_val, cond, v_val)
    if quant_res is not None:
        return quant_res

    # ── 2. Deterministic text equivalence (fast, clear cases) ─────────────────
    t_clean = _clean_text(t_val)
    v_clean = _clean_text(v_val)

    # Full containment or exact match
    if t_clean == v_clean or t_clean in v_clean or v_clean in t_clean:
        return {
            "status": "COMPLIANT",
            "reason": f"Offered specification ({v_val}) matches required tender specification ({t_val}).",
            "confidence": 0.95,
        }

    t_words = set(w for w in t_clean.split() if len(w) > 2 and w not in _GENERIC_STOP)
    v_words = set(w for w in v_clean.split() if len(w) > 2 and w not in _GENERIC_STOP)
    overlap = t_words & v_words

    if t_words and t_words.issubset(v_words):
        return {
            "status": "COMPLIANT",
            "reason": f"Offered specification ({v_val}) satisfies all required criteria ({t_val}).",
            "confidence": 0.92,
        }

    if t_words and len(overlap) >= len(t_words) * 0.70:
        return {
            "status": "COMPLIANT",
            "reason": f"Offered specification ({v_val}) substantially corresponds to tender requirement ({t_val}).",
            "confidence": 0.88,
        }

    # ── 3. AI-assisted qualitative comparison (only when genuinely needed/uncertain) ──
    if provider is not None and type(provider).__name__ != "DeterministicProvider":
        try:
            ai_res = provider.compare_qualitative(
                requirement_text=t_val,
                vendor_text=v_val,
                requirement_name=req_name,
            )
            if ai_res is not None:
                print(f"[BidVerify Comparator] '{req_name}' evaluated via Gemini AI ({ai_res.get('status')})")
                return ai_res
            else:
                print(f"[BidVerify Comparator] '{req_name}' Gemini returned None; fallback to deterministic text equivalence.")
        except Exception as e:
            print(f"[BidVerify Comparator] Gemini qualitative comparison failed: {e}. Falling back to deterministic.")

    # ── 4. Deterministic qualitative fallback ─────────────────────────────────
    if overlap:
        return {
            "status": "NEEDS_REVIEW",
            "reason": (
                f"Offered specification ({v_val}) partially matches tender requirement ({t_val}); "
                "human officer review advised."
            ),
            "confidence": 0.65,
        }

    return {
        "status": "NON_COMPLIANT",
        "reason": f"Offered specification ({v_val}) does not match tender requirement ({t_val}).",
        "confidence": 0.85,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline result assembler (replaces compare_compliance)
# ─────────────────────────────────────────────────────────────────────────────

def compare_matched_pairs(
    matched_pairs: List[Dict[str, Any]],
    provider=None,
) -> Dict[str, Any]:
    """
    Evaluates compliance for a list of pre-matched tender/vendor pairs produced
    by matcher.match_requirements().

    Returns the standard structured result shape consumed by the frontend:
    {
      "summary": {total, compliant, non_compliant, not_found, needs_review},
      "results": [{requirement, category, condition, required_value, vendor_value,
                   status, reason, confidence, tender_evidence, vendor_evidence,
                   match_score, match_method}, ...]
    }
    """
    results: List[Dict[str, Any]] = []
    summary: Dict[str, Any] = {
        "total": len(matched_pairs),
        "compliant": 0,
        "non_compliant": 0,
        "not_found": 0,
        "needs_review": 0,
        "compliance_score": 0.0,
    }

    for pair in matched_pairs:
        req     = pair["tender_req"]
        claim   = pair.get("vendor_claim")
        score   = pair.get("match_score", 0.0)
        method  = pair.get("match_method", "unknown")
        ambig   = pair.get("ambiguous", False)

        t_name     = req.get("requirement", "")
        t_val      = req.get("value", "")
        t_cond     = req.get("condition", "minimum")
        t_cat      = req.get("category", "technical")
        t_evidence = req.get("raw_text", "")

        v_val      = claim.get("value")      if claim else None
        v_evidence = claim.get("raw_text", "") if claim else ""

        if ambig and claim is not None:
            comp = {
                "status": "NEEDS_REVIEW",
                "reason": (
                    f"Multiple vendor claims may correspond to '{t_name}'. "
                    "Manual verification is recommended."
                ),
                "confidence": round(score * 0.75, 3),
            }
        else:
            comp = compare_single_requirement(
                req_name=t_name,
                tender_val=t_val,
                tender_cond=t_cond,
                vendor_val=v_val,
                provider=provider,
            )

        status = comp["status"]
        summary[{
            "COMPLIANT": "compliant",
            "NON_COMPLIANT": "non_compliant",
            "NOT_FOUND": "not_found",
            "NEEDS_REVIEW": "needs_review",
        }.get(status, "needs_review")] += 1

        results.append({
            # Core fields (frontend consumes these)
            "requirement":    t_name,
            "category":       t_cat,
            "condition":      t_cond,
            "required_value": t_val,
            "vendor_value":   v_val if v_val else "Not Provided",
            "status":         status,
            "reason":         comp["reason"],
            "confidence":     comp["confidence"],
            "tender_evidence": t_evidence,
            "vendor_evidence": v_evidence,
            # Extended fields (backward compatible)
            "match_score":    round(score, 3),
            "match_method":   method,
        })

    total = summary["total"]
    compliant = summary["compliant"]
    summary["compliance_score"] = round((compliant / total * 100), 1) if total > 0 else 0.0

    return {"summary": summary, "results": results}

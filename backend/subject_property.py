"""
BidVerify AI - Subject & Property Semantic Engine
==================================================

Enforces fundamental procurement requirement semantics:
  1. Distinguishes SUBJECT (entity: battery, storage, memory, LED, display, controller)
     from PROPERTY (attribute: capacity, runtime, color temperature, operating temperature).
  2. Implements strict Subject/Property compatibility gating to prevent:
     - Storage capacity from matching Memory capacity.
     - Color temperature (CCT) from matching Operating temperature (°C).
     - Battery capacity (Ah) from matching Backup duration (hours).
     - Display resolution from matching Mounting height / Pole dimension.
     - Power consumption from matching Power output.
     - Surge protection (kV) from matching Operating voltage (V).
  3. Domain-agnostic, local, fast, and deterministic.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class SubjectProperty:
    subject: str                    # e.g., "storage", "memory", "battery", "led", "display", "controller"
    property: str                   # e.g., "storage_capacity", "memory_capacity", "color_temp", "operating_temp"
    sub_category: Optional[str] = None  # e.g., "optical", "thermal", "electrical", "mechanical"
    dimension: Optional[str] = None     # e.g., "storage_gb", "electric_charge", "temperature_k", "temperature_c"
    raw_keywords: Set[str] = field(default_factory=set)


@dataclass
class CompatibilityResult:
    compatible: bool
    status: str             # "COMPATIBLE", "RELATED_INCOMPATIBLE", "UNRELATED"
    reason: str
    penalty: float = 0.0    # Subtracted from candidate score if incompatible


# ─────────────────────────────────────────────────────────────────────────────
# Canonical Taxonomy of Incompatible Property Pairs
# ─────────────────────────────────────────────────────────────────────────────

# Explicitly conflicting property pairs where candidates MUST NEVER become evidence
_INCOMPATIBLE_PROPERTY_PAIRS = frozenset({
    # Compute: Storage (disk/SSD/HDD) vs Memory (RAM/DDR)
    frozenset({"storage_capacity", "memory_capacity"}),
    frozenset({"storage_capacity", "memory_generation"}),
    frozenset({"storage_capacity", "memory_speed"}),
    
    # Thermal/Optical: Color Temperature (CCT, Kelvins) vs Operating Temperature (Ambient, °C)
    frozenset({"color_temperature", "operating_temperature"}),
    frozenset({"color_temperature", "storage_temperature"}),
    frozenset({"color_temperature", "junction_temperature"}),
    
    # Electrical/Energy: Battery Capacity (Ah/mAh) vs Backup Runtime (hours/days)
    frozenset({"battery_capacity", "backup_duration"}),
    frozenset({"battery_capacity", "solar_pv_capacity"}),
    frozenset({"battery_capacity", "charge_time"}),
    
    # Display vs Mechanical: Screen Resolution vs Pole/Mounting Height
    frozenset({"display_resolution", "mounting_height"}),
    frozenset({"display_resolution", "pole_height"}),
    frozenset({"display_resolution", "physical_dimensions"}),
    
    # Photometric: Luminous Flux (lm) vs Efficacy (lm/W) vs Color Temperature (K)
    frozenset({"luminous_flux", "color_temperature"}),
    frozenset({"luminous_flux", "mounting_height"}),
    frozenset({"luminous_efficacy", "color_temperature"}),
    
    # Power: Consumption (input) vs Output (generation) vs Surge Protection
    frozenset({"power_consumption", "power_output"}),
    frozenset({"surge_protection", "operating_voltage"}),
    frozenset({"surge_protection", "power_consumption"}),
    frozenset({"surge_protection", "power_output"}),
    frozenset({"power_factor", "surge_protection"}),
    
    # Network vs Mechanical
    frozenset({"network_interface", "mounting_height"}),
    frozenset({"cellular_connectivity", "mounting_height"}),
    
    # Commercial: Delivery Timeline vs Warranty Period
    frozenset({"delivery_timeline", "warranty_period"}),
})


# ─────────────────────────────────────────────────────────────────────────────
# Semantic Subject & Property Analyzer
# ─────────────────────────────────────────────────────────────────────────────

class SubjectPropertyAnalyzer:
    """
    Extracts Subject and Property from requirement or claim text using
    domain-agnostic pattern matching and lexical semantics.
    """

    @classmethod
    def analyze(cls, text: str, name: str = "", unit: Optional[str] = None) -> SubjectProperty:
        combined = f"{name} {text}".lower()
        cleaned = re.sub(r"[^\w\s°℃%/-]", " ", combined)
        tokens = set(cleaned.split())

        # ── 1. COMPUTE: Storage vs Memory ────────────────────────────────────
        # Memory (RAM / DDR)
        is_memory = (
            any(w in combined for w in ("ram", "ddr", "lpddr", "system memory", "random access memory"))
            or ("memory" in combined and "flash" not in combined and "storage" not in combined and "card" not in combined)
        )
        if is_memory:
            return SubjectProperty(
                subject="memory",
                property="memory_capacity",
                sub_category="compute",
                dimension="storage_gb",
                raw_keywords=tokens,
            )

        # Storage (SSD / HDD / Drive / Disk)
        is_storage = (
            any(w in combined for w in ("ssd", "hdd", "nvme", "hard disk", "hard drive", "emmc", "internal storage", "solid state", "disk capacity", "flash storage"))
            or ("storage" in combined and "temperature" not in combined and "temp" not in combined and "network" not in combined and "loss" not in combined)
        )
        if is_storage:
            return SubjectProperty(
                subject="storage",
                property="storage_capacity",
                sub_category="compute",
                dimension="storage_gb",
                raw_keywords=tokens,
            )

        # ── 2. TEMPERATURE: Color Temperature (CCT) vs Operating Temperature ─
        # Optical Color Temperature (Kelvins / CCT)
        is_cct = (
            any(w in combined for w in ("cct", "color temp", "colour temp", "correlate color", "correlated color"))
            or (re.search(r"\b\d{4}\s*k\b", combined) and "operating" not in combined and "deg" not in combined and "°c" not in combined)
            or ("kelvin" in combined and "operating" not in combined)
        )
        if is_cct:
            return SubjectProperty(
                subject="led_lighting",
                property="color_temperature",
                sub_category="optical",
                dimension="temperature_k",
                raw_keywords=tokens,
            )

        # Operating / Ambient Temperature (°C / Celsius)
        is_operating_temp = (
            any(w in combined for w in ("operating temp", "ambient temp", "working temp", "operating temperature", "ambient temperature", "environmental temp"))
            or "°c" in combined
            or "℃" in combined
            or "deg c" in combined
            or "celsius" in combined
        )
        if is_operating_temp:
            return SubjectProperty(
                subject="environmental",
                property="operating_temperature",
                sub_category="thermal",
                dimension="temperature_c",
                raw_keywords=tokens,
            )

        # ── 3. BATTERY: Electrical Capacity (Ah) vs Backup Runtime (Hours) ───
        # Battery Electrical Capacity (Ah / mAh / Wh / kWh)
        is_batt_capacity = (
            ("battery" in combined and any(w in combined for w in ("capacity", "ah", "mah", "wh", "kwh", "rating", "cell")))
            or re.search(r"\b\d+\s*ah\b", combined)
            or re.search(r"\b\d+\s*mah\b", combined)
        )
        if is_batt_capacity and "backup" not in combined and "autonomy" not in combined:
            return SubjectProperty(
                subject="battery",
                property="battery_capacity",
                sub_category="electrical",
                dimension="electric_charge",
                raw_keywords=tokens,
            )

        # Battery Backup / Autonomy Runtime (hours, days, nights)
        is_backup_runtime = (
            any(w in combined for w in ("backup", "autonomy", "autonomous", "operating hour", "run time", "runtime", "nights backup", "days autonomy"))
            or (("battery" in combined or "backup" in combined) and any(w in combined for w in ("hours", "hrs", "days", "nights")))
        )
        if is_backup_runtime:
            return SubjectProperty(
                subject="battery",
                property="backup_duration",
                sub_category="electrical",
                dimension="time_hours",
                raw_keywords=tokens,
            )

        # Battery Chemistry / Technology
        if "lifepo4" in combined or "lithium iron" in combined or "lfp" in combined or "lead acid" in combined or "lithium ion" in combined:
            return SubjectProperty(
                subject="battery",
                property="battery_chemistry",
                sub_category="chemical",
                raw_keywords=tokens,
            )

        # ── 4. SOLAR PV: PV Module / Generation vs Battery ───────────────────
        if any(w in combined for w in ("pv module", "solar panel", "solar module", "photovoltaic", "wp", "watt peak")) and "battery" not in combined:
            return SubjectProperty(
                subject="solar_pv",
                property="solar_pv_capacity",
                sub_category="electrical",
                dimension="power",
                raw_keywords=tokens,
            )

        # ── 5. OPTICAL / PHOTOMETRIC: Luminous Flux vs Efficacy vs CRI ───────
        if any(w in combined for w in ("lumen per watt", "lumens per watt", "lm/w", "luminous efficacy", "luminaire efficacy", "efficacy")):
            return SubjectProperty(
                subject="led_lighting",
                property="luminous_efficacy",
                sub_category="optical",
                dimension="efficacy",
                raw_keywords=tokens,
            )

        if any(w in combined for w in ("luminous flux", "luminaire flux", "light output", "output lumen", "lumens output", "lumen", "lumens", "lm\b")):
            return SubjectProperty(
                subject="led_lighting",
                property="luminous_flux",
                sub_category="optical",
                dimension="luminous_flux",
                raw_keywords=tokens,
            )

        if any(w in combined for w in ("cri", "color rendering", "colour rendering", "ra >", "ra >=")):
            return SubjectProperty(
                subject="led_lighting",
                property="color_rendering_index",
                sub_category="optical",
                raw_keywords=tokens,
            )

        # ── 6. DISPLAY vs MECHANICAL: Resolution vs Height / Dimensions ───────
        if any(w in combined for w in ("resolution", "pixel", "1080p", "4k", "fhd", "qhd", "aspect ratio", "display resolution")) and "pole" not in combined:
            return SubjectProperty(
                subject="display",
                property="display_resolution",
                sub_category="video",
                raw_keywords=tokens,
            )

        if any(w in combined for w in ("mounting height", "pole height", "installation height", "pole length", "mast height", "luminaire height")):
            return SubjectProperty(
                subject="mechanical",
                property="mounting_height",
                sub_category="structural",
                dimension="length",
                raw_keywords=tokens,
            )

        # ── 7. ELECTRICAL / POWER: Surge vs Factor vs THD vs Voltage ─────────
        if any(w in combined for w in ("surge", "spd", "transient", "10 kv", "6 kv", "surge protection", "lightning")):
            return SubjectProperty(
                subject="power",
                property="surge_protection",
                sub_category="protection",
                dimension="voltage_kv",
                raw_keywords=tokens,
            )

        if any(w in combined for w in ("power factor", " pf ", "pf >", "pf >=")):
            return SubjectProperty(
                subject="power",
                property="power_factor",
                sub_category="electrical",
                raw_keywords=tokens,
            )

        if any(w in combined for w in ("thd", "total harmonic", "harmonic distortion")):
            return SubjectProperty(
                subject="power",
                property="harmonic_distortion",
                sub_category="electrical",
                raw_keywords=tokens,
            )

        # ── 8. INGRESS & IMPACT PROTECTION (IP / IK) ─────────────────────────
        if re.search(r"\bip\s*[56][0-9]\b", combined) or "ingress protection" in combined or "water ingress" in combined:
            return SubjectProperty(
                subject="enclosure",
                property="ingress_protection",
                sub_category="protection",
                raw_keywords=tokens,
            )

        if re.search(r"\bik\s*0?[6-9]|ik\s*10\b", combined) or "impact resistance" in combined or "impact protection" in combined:
            return SubjectProperty(
                subject="enclosure",
                property="impact_protection",
                sub_category="protection",
                raw_keywords=tokens,
            )

        # ── 9. CONNECTIVITY & NETWORKING ─────────────────────────────────────
        if any(w in combined for w in ("4g", "lte", "cellular", "sim card", "gsm", "nb-iot", "lora")):
            return SubjectProperty(
                subject="network",
                property="cellular_connectivity",
                sub_category="telecom",
                raw_keywords=tokens,
            )

        if any(w in combined for w in ("ethernet", "wi-fi", "wifi", "bluetooth", "lan port", "rj45", "wpa2")):
            return SubjectProperty(
                subject="network",
                property="network_interface",
                sub_category="telecom",
                raw_keywords=tokens,
            )

        if any(w in combined for w in ("ntp", "clock sync", "time sync", "synchronize time", "network time")):
            return SubjectProperty(
                subject="controller",
                property="time_synchronization",
                sub_category="control",
                raw_keywords=tokens,
            )

        if any(w in combined for w in ("gps", "gnss", "latitude", "longitude", "location tagging", "geotag")):
            return SubjectProperty(
                subject="controller",
                property="location_tagging",
                sub_category="telecom",
                raw_keywords=tokens,
            )

        if any(w in combined for w in ("ota", "firmware update", "over the air", "rollback")):
            return SubjectProperty(
                subject="controller",
                property="firmware_update",
                sub_category="control",
                raw_keywords=tokens,
            )

        if any(w in combined for w in ("dashboard", "web portal", "portal view", "noc dashboard", "monitoring platform")):
            return SubjectProperty(
                subject="software",
                property="monitoring_dashboard",
                sub_category="software",
                raw_keywords=tokens,
            )

        if any(w in combined for w in ("encryption at rest", "encrypted at rest", "stored credentials", "secrets encrypted")):
            return SubjectProperty(
                subject="security",
                property="data_encryption",
                sub_category="security",
                raw_keywords=tokens,
            )

        # ── 10. COMMERCIAL: Delivery vs Warranty vs Certifications ───────────
        if any(w in combined for w in ("delivery", "dispatch", "lead time", "transit", "supply period")):
            return SubjectProperty(
                subject="commercial",
                property="delivery_timeline",
                sub_category="logistics",
                dimension="time_days",
                raw_keywords=tokens,
            )

        if any(w in combined for w in ("warranty", "guarantee", "amc", "camc", "after-sales")):
            return SubjectProperty(
                subject="commercial",
                property="warranty_period",
                sub_category="commercial",
                dimension="time_years",
                raw_keywords=tokens,
            )

        if any(w in combined for w in ("oem authorization", "manufacturer authorization", "authorization letter", "oem letter")):
            return SubjectProperty(
                subject="eligibility",
                property="oem_authorization",
                sub_category="compliance",
                raw_keywords=tokens,
            )

        if any(w in combined for w in ("bis", "iec", "iso", "ce marked", "ce mark", "standard compliance", "certified")):
            return SubjectProperty(
                subject="certification",
                property="standard_compliance",
                sub_category="compliance",
                raw_keywords=tokens,
            )

        # Fallback general subject/property
        subject = name.split()[0].lower() if name else "general"
        prop = re.sub(r"[^\w]", "_", name.lower()) if name else "general_specification"
        return SubjectProperty(
            subject=subject,
            property=prop,
            sub_category="general",
            raw_keywords=tokens,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Compatibility Gate
# ─────────────────────────────────────────────────────────────────────────────

def check_subject_property_compatibility(
    req_sp: SubjectProperty,
    claim_sp: SubjectProperty,
) -> CompatibilityResult:
    """
    Evaluates whether a candidate vendor claim is compatible with a tender requirement.
    Rejects incompatible properties (e.g. Memory claim for Storage requirement).
    """
    pair = frozenset({req_sp.property, claim_sp.property})
    if pair in _INCOMPATIBLE_PROPERTY_PAIRS:
        return CompatibilityResult(
            compatible=False,
            status="RELATED_INCOMPATIBLE",
            reason=(
                f"Candidate property '{claim_sp.property}' (subject: {claim_sp.subject}) "
                f"is incompatible with required property '{req_sp.property}' (subject: {req_sp.subject})."
            ),
            penalty=-2.0,
        )

    # Cross-subject fundamental exclusions
    if req_sp.subject == "storage" and claim_sp.subject == "memory":
        return CompatibilityResult(
            compatible=False,
            status="RELATED_INCOMPATIBLE",
            reason="Vendor claim describes memory/RAM capacity, not internal storage capacity.",
            penalty=-2.0,
        )

    if req_sp.subject == "memory" and claim_sp.subject == "storage":
        return CompatibilityResult(
            compatible=False,
            status="RELATED_INCOMPATIBLE",
            reason="Vendor claim describes internal storage, not system memory/RAM.",
            penalty=-2.0,
        )

    if req_sp.property == "color_temperature" and claim_sp.property == "operating_temperature":
        return CompatibilityResult(
            compatible=False,
            status="RELATED_INCOMPATIBLE",
            reason="Vendor claim describes ambient operating temperature, not LED color temperature (CCT).",
            penalty=-2.0,
        )

    if req_sp.property == "operating_temperature" and claim_sp.property == "color_temperature":
        return CompatibilityResult(
            compatible=False,
            status="RELATED_INCOMPATIBLE",
            reason="Vendor claim describes optical color temperature, not environmental operating temperature.",
            penalty=-2.0,
        )

    if req_sp.property == "battery_capacity" and claim_sp.property == "backup_duration":
        return CompatibilityResult(
            compatible=False,
            status="RELATED_INCOMPATIBLE",
            reason="Vendor claim describes backup duration (hours), not battery electrical capacity (Ah).",
            penalty=-2.0,
        )

    if req_sp.property == "display_resolution" and claim_sp.property in ("mounting_height", "pole_height"):
        return CompatibilityResult(
            compatible=False,
            status="RELATED_INCOMPATIBLE",
            reason="Vendor claim describes structural pole/mounting height, not display resolution.",
            penalty=-2.0,
        )

    # Dimensions incompatibility
    if req_sp.dimension and claim_sp.dimension:
        # Incompatible physical dimensions
        incompat_dims = {
            ("temperature_k", "temperature_c"),
            ("temperature_c", "temperature_k"),
            ("electric_charge", "time_hours"),
            ("time_hours", "electric_charge"),
            ("luminous_flux", "efficacy"),
            ("voltage_kv", "power"),
        }
        if (req_sp.dimension, claim_sp.dimension) in incompat_dims:
            return CompatibilityResult(
                compatible=False,
                status="RELATED_INCOMPATIBLE",
                reason=f"Physical dimension '{claim_sp.dimension}' is incompatible with required '{req_sp.dimension}'.",
                penalty=-1.5,
            )

    return CompatibilityResult(
        compatible=True,
        status="COMPATIBLE",
        reason="Subject and property are compatible.",
        penalty=0.0,
    )

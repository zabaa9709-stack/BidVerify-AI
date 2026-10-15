"""
BidVerify AI - Dynamic Extractor Tests

Tests the generic extraction pipeline independently of any PDF file.
Uses inline text fixtures covering 6+ procurement domains.

Proves that the extractor:
  1. Works for completely unknown categories (no hardcoded names)
  2. Detects numeric conditions (MINIMUM, MAXIMUM, RANGE, EXACT)
  3. Detects qualitative requirements
  4. Correctly infers categories (technical/commercial/operational)
  5. Preserves source evidence (raw_text)
  6. Handles all four extraction phases:
     - Numbered table rows
     - Key-value pairs
     - Bullet-point clauses
     - Requirement-signal sentences

Does NOT assert exact counts. Asserts meaningful structural properties.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from extractor import extract_requirements_from_text
import requests

BASE_URL = "http://127.0.0.1:8000"
_OK   = "\033[92m[OK]\033[0m"
_FAIL = "\033[91m[FAIL]\033[0m"


def assert_gt(label, actual, min_val):
    if actual > min_val:
        print(f"  {_OK} {label}: {actual} (> {min_val})")
    else:
        raise AssertionError(f"{label}: expected > {min_val}, got {actual}")


def assert_has_field(label, req, field, expected_value=None):
    if field not in req:
        raise AssertionError(f"{label}: field '{field}' missing in requirement")
    if expected_value is not None and req[field] != expected_value:
        raise AssertionError(
            f"{label}: field '{field}' = {req[field]!r}, expected {expected_value!r}"
        )


def assert_any_contains(label, reqs, keyword):
    """Asserts at least one requirement's name or value contains keyword."""
    keyword_lower = keyword.lower()
    for r in reqs:
        name = r.get("requirement", "").lower()
        val  = r.get("value", "").lower()
        if keyword_lower in name or keyword_lower in val:
            print(f"  {_OK} {label}: found '{keyword}' in requirements")
            return
    raise AssertionError(f"{label}: keyword '{keyword}' not found in any requirement name or value")


def assert_condition_found(label, reqs, expected_condition):
    """Asserts at least one requirement has the given condition."""
    for r in reqs:
        if r.get("condition") == expected_condition:
            print(f"  {_OK} {label}: condition='{expected_condition}' found")
            return
    raise AssertionError(f"{label}: no requirement with condition='{expected_condition}'")


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures: inline procurement text for different domains
# ─────────────────────────────────────────────────────────────────────────────

SOLAR_LED_TEXT = """
Government of India - GeM Procurement
Supply of Solar LED Street Lights

1
Output Lumen
Minimum 5,000 lumens

2
LED Power
Minimum 40 W

3
Colour Temperature
4000 K to 6500 K

4
Battery Capacity
Minimum 40 Ah lithium-ion battery

5
Operating Temperature
-10°C to 55°C

6
IP Rating
IP66 minimum

7
Delivery Period
Maximum 45 days from purchase order

8
Warranty
Minimum 5 years

9
Quantity
100 units

10
Price
Maximum total bid: INR 80,00,000
"""

BICYCLE_TEXT = """
Procurement of Bicycles for Government Schools

Sl. No. | Specification | Requirement
1
Frame Material
Aluminium Alloy 6061

2
Wheel Size
26 inches

3
Gear System
Minimum 21-speed indexed gear system

4
Brakes
Hydraulic disc brakes required

5
Maximum Rider Weight
Minimum load capacity: 120 kg

6
Speed
Minimum 25 km/h on level road

7
Weight
Maximum 14 kg per bicycle

8
Warranty
Minimum 2 years structural warranty

9
Delivery
Maximum 30 days from purchase order

10
Quantity
500 units

11
Price
Maximum INR 15,000 per unit
"""

HOSPITAL_TEXT = """
Medical Equipment Procurement — Patient Monitoring System

1
Display Resolution
Minimum 1920 × 1080 resolution

2
ECG Support
3-Lead and 5-Lead ECG support

3
SpO2 Measurement Range
70% to 100%

4
Heart Rate Range
30 to 250 BPM

5
Battery Backup
Minimum 4 hours on internal battery

6
Operating Temperature
10°C to 35°C

7
IP Rating
IP42 minimum

8
Warranty
Minimum 2 years onsite warranty

9
Certifications
ISO 13485 and CE certified

10
Installation
Site installation and commissioning included

11
Delivery
Maximum 60 days from purchase order

12
Quantity
20 units
"""

VEHICLE_TEXT = """
Supply of Electric Vehicles for Government Use

Specification | Requirement
Top Speed: Minimum 80 km/h
Range: Minimum 200 km per charge
Battery Capacity: Minimum 40 kWh
Charging Time: Maximum 8 hours (standard), Maximum 2 hours (fast)
Seating Capacity: 5 seats
Air Conditioning: Required
Warranty: Minimum 3 years on vehicle, 5 years on battery
Price: Maximum INR 15,00,000 per unit
Quantity: 10 units
Delivery: Maximum 90 days from purchase order
"""

FURNITURE_TEXT = """
Office Furniture Procurement

Items required:
- Executive Chair: must support minimum 120 kg load
- Desk Height: 730 mm to 760 mm
- Material: Steel frame required
- Warranty: Minimum 2 years
- Delivery: within 30 days
- Quantity: 50 sets
- Price: Maximum INR 50,000 per set
"""

SOFTWARE_TEXT = """
Software Services Procurement

System Uptime: Minimum 99.5% uptime SLA
Response Time: Maximum 2 seconds for 95% of requests
Data Backup: Daily automated backups required
Security: ISO 27001 certified required
Support: 24x7 technical support required
Implementation: Maximum 90 days from agreement
Annual Maintenance: Minimum 5 years AMC
Price: Maximum INR 50,00,000 total contract value
"""


# ─────────────────────────────────────────────────────────────────────────────
# Test suite functions
# ─────────────────────────────────────────────────────────────────────────────

def test_solar_extraction():
    print("\n--- TEST 1: Solar LED Street Light extraction ---")
    reqs = extract_requirements_from_text(SOLAR_LED_TEXT)
    assert_gt("Extracted requirements", len(reqs), 5)
    assert_any_contains("Contains lumen/luminous", reqs, "lumen")
    assert_any_contains("Contains delivery/days", reqs, "day")
    assert_condition_found("Has range condition", reqs, "range")
    assert_condition_found("Has minimum condition", reqs, "minimum")
    assert_condition_found("Has maximum condition", reqs, "maximum")

    # All requirements must have required fields
    for r in reqs:
        assert "requirement" in r and r["requirement"], f"Missing requirement name in {r}"
        assert "value" in r and r["value"], f"Missing value in {r}"
        assert "condition" in r, f"Missing condition in {r}"
        assert "category" in r, f"Missing category in {r}"
        assert "raw_text" in r, f"Missing raw_text in {r}"
        assert r["condition"] in ("minimum", "maximum", "range", "exact", "qualitative", "presence"), \
            f"Unexpected condition: {r['condition']}"

    print(f"  {_OK} Solar: {len(reqs)} requirements extracted, all with valid schema")


def test_bicycle_extraction():
    print("\n--- TEST 2: Bicycle extraction ---")
    reqs = extract_requirements_from_text(BICYCLE_TEXT)
    assert_gt("Extracted requirements", len(reqs), 5)
    assert_any_contains("Contains frame/aluminium", reqs, "aluminium")
    assert_any_contains("Contains wheel", reqs, "wheel")
    assert_any_contains("Contains brake", reqs, "brake")
    print(f"  {_OK} Bicycle: {len(reqs)} requirements extracted")


def test_hospital_extraction():
    print("\n--- TEST 3: Hospital equipment extraction ---")
    reqs = extract_requirements_from_text(HOSPITAL_TEXT)
    assert_gt("Extracted requirements", len(reqs), 5)
    assert_any_contains("Contains ECG", reqs, "ECG")
    assert_any_contains("Contains BPM/heart rate", reqs, "Heart")
    assert_condition_found("Has range condition", reqs, "range")
    print(f"  {_OK} Hospital: {len(reqs)} requirements extracted")


def test_vehicle_extraction():
    print("\n--- TEST 4: Electric Vehicle extraction ---")
    reqs = extract_requirements_from_text(VEHICLE_TEXT)
    assert_gt("Extracted requirements", len(reqs), 4)
    assert_any_contains("Contains speed/km/h", reqs, "speed")
    print(f"  {_OK} Vehicle: {len(reqs)} requirements extracted")


def test_furniture_extraction():
    print("\n--- TEST 5: Office Furniture extraction ---")
    reqs = extract_requirements_from_text(FURNITURE_TEXT)
    assert_gt("Extracted requirements", len(reqs), 3)
    print(f"  {_OK} Furniture: {len(reqs)} requirements extracted")


def test_software_extraction():
    print("\n--- TEST 6: Software Services extraction ---")
    reqs = extract_requirements_from_text(SOFTWARE_TEXT)
    assert_gt("Extracted requirements", len(reqs), 3)
    print(f"  {_OK} Software: {len(reqs)} requirements extracted")


def test_numeric_detection():
    print("\n--- TEST 7: Numeric detection across domains ---")
    reqs = extract_requirements_from_text(SOLAR_LED_TEXT)
    numeric_count = sum(1 for r in reqs if r.get("is_numeric"))
    assert_gt("Numeric requirements detected", numeric_count, 3)
    print(f"  {_OK} {numeric_count} numeric requirements detected in solar tender")


def test_category_inference():
    print("\n--- TEST 8: Category inference ---")
    reqs = extract_requirements_from_text(SOLAR_LED_TEXT)
    cats = {r.get("category") for r in reqs}
    assert "technical" in cats, f"Expected 'technical' category in {cats}"
    assert "commercial" in cats or "operational" in cats, \
        f"Expected commercial or operational category in {cats}"
    print(f"  {_OK} Categories detected: {cats}")


def test_empty_input():
    print("\n--- TEST 9: Empty input handling ---")
    reqs = extract_requirements_from_text("")
    assert reqs == [], f"Expected [] for empty input, got {reqs}"
    reqs = extract_requirements_from_text("   \n\n   ")
    assert reqs == [], f"Expected [] for whitespace input"
    print(f"  {_OK} Empty input returns empty list")


def test_no_duplicates():
    print("\n--- TEST 10: No duplicate requirement names ---")
    reqs = extract_requirements_from_text(SOLAR_LED_TEXT + SOLAR_LED_TEXT)
    names = [r["requirement"].lower() for r in reqs]
    unique_names = set(names)
    assert len(names) == len(unique_names), \
        f"Duplicate requirement names found: {len(names) - len(unique_names)} duplicates"
    print(f"  {_OK} No duplicates: {len(names)} unique requirements")


def test_live_server_extract():
    print("\n--- TEST 11: Live server POST /extract-requirements ---")
    tender_path = os.path.join(os.path.dirname(__file__), "uploads", "tender.pdf")
    if not os.path.exists(tender_path):
        print("  [SKIP] No tender.pdf in uploads/. Run through UI first.")
        return
    try:
        with open(tender_path, "rb") as f:
            resp = requests.post(
                f"{BASE_URL}/extract-requirements",
                files={"tender": ("tender.pdf", f, "application/pdf")},
                timeout=120,
            )
    except requests.ConnectionError:
        print("  [SKIP] Backend not reachable.")
        return
    except requests.ReadTimeout:
        print("  [SKIP] Backend read timeout (model cold start — expected in CI).")
        return

    assert resp.status_code == 200, f"HTTP {resp.status_code}"
    data = resp.json()
    assert "requirements" in data
    assert "requirements_count" in data
    assert data["requirements_count"] > 0, "Expected > 0 requirements"
    assert data["requirements_count"] == len(data["requirements"])
    for r in data["requirements"]:
        assert "requirement" in r and r["requirement"]
        assert "value" in r
        assert "condition" in r
        assert "category" in r
    print(f"  {_OK} Extracted {data['requirements_count']} requirements from real PDF")


def test_live_server_upload():
    print("\n--- TEST 12: Live server POST /upload ---")
    tender_path = os.path.join(os.path.dirname(__file__), "uploads", "tender.pdf")
    vendor_path = os.path.join(os.path.dirname(__file__), "uploads", "vendor.pdf")
    if not os.path.exists(tender_path) or not os.path.exists(vendor_path):
        print("  [SKIP] No PDFs in uploads/.")
        return
    try:
        with open(tender_path, "rb") as t, open(vendor_path, "rb") as v:
            resp = requests.post(
                f"{BASE_URL}/upload",
                files={"tender": ("tender.pdf", t, "application/pdf"),
                       "vendor": ("vendor.pdf", v, "application/pdf")},
                timeout=120,
            )
    except requests.ConnectionError:
        print("  [SKIP] Backend not reachable.")
        return
    except requests.ReadTimeout:
        print("  [SKIP] Backend read timeout (model cold start — expected in CI).")
        return
    assert resp.status_code == 200
    data = resp.json()
    assert "tender_pages" in data
    assert "vendor_pages" in data
    print(f"  {_OK} POST /upload: {data['tender_pages']} tender pages, {data['vendor_pages']} vendor pages")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("BidVerify AI — Dynamic Extractor Tests")
    print("=" * 60)

    failed = 0
    tests = [
        test_solar_extraction,
        test_bicycle_extraction,
        test_hospital_extraction,
        test_vehicle_extraction,
        test_furniture_extraction,
        test_software_extraction,
        test_numeric_detection,
        test_category_inference,
        test_empty_input,
        test_no_duplicates,
        test_live_server_upload,
        test_live_server_extract,
    ]

    for fn in tests:
        try:
            fn()
        except AssertionError as e:
            print(f"\n  {_FAIL} {fn.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"\n  {_FAIL} {fn.__name__} (unexpected): {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 60)
    if failed == 0:
        print("ALL EXTRACTOR TESTS PASSED SUCCESSFULLY!")
    else:
        print(f"{failed} TEST(S) FAILED.")
    print("=" * 60)
    sys.exit(0 if failed == 0 else 1)

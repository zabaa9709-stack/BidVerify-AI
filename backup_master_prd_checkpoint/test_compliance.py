"""
BidVerify AI - Generic Compliance Engine Tests

Tests the comparison engine independently of any PDF or product category.
Proves generality across: solar equipment, hospital equipment, bicycles,
vehicles, furniture, construction, software/services, and more.

Does NOT assert exact requirement counts.
Does NOT import compare_compliance (removed in the redesign).
Does test the new compare_matched_pairs pipeline.

Test suites:
  1. MINIMUM constraint — multiple domains
  2. MAXIMUM constraint — multiple domains
  3. RANGE constraint — multiple domains
  4. EXACT constraint
  5. Unit conversion across domains
  6. NOT_FOUND behavior
  7. NEEDS_REVIEW behavior
  8. Qualitative text matching
  9. compare_matched_pairs pipeline
  10. Live server integration (POST /verify — structure only, no count assertions)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests

from comparator import compare_single_requirement, compare_matched_pairs

BASE_URL = "http://127.0.0.1:8000"

_OK   = "\033[92m[OK]\033[0m"
_FAIL = "\033[91m[FAIL]\033[0m"


def assert_status(label, result, expected_status, show_reason=True):
    status = result["status"]
    if status == expected_status:
        msg = f"  {_OK} {label}: {result['reason']}" if show_reason else f"  {_OK} {label}"
        print(msg)
    else:
        print(f"  {_FAIL} {label}")
        print(f"         Expected: {expected_status}")
        print(f"         Got:      {status}  — {result['reason']}")
        raise AssertionError(f"[{label}] Expected {expected_status}, got {status}")


# ─────────────────────────────────────────────────────────────────────────────
# Suite 1: MINIMUM constraint across domains
# ─────────────────────────────────────────────────────────────────────────────

def test_minimum():
    print("\n--- SUITE 1: MINIMUM constraint (multi-domain) ---")
    cases = [
        # (label, req, vendor, expected_status)
        # Solar lighting
        ("Solar: 5000 lm satisfied by 5500 lm",
         "Minimum 5,000 lumens", "5,500 lumens", "COMPLIANT"),
        ("Solar: 5000 lm violated by 4200 lm",
         "Minimum 5,000 lumens", "4,200 lumens", "NON_COMPLIANT"),
        # Solar panel
        ("Solar panel: 40 W satisfied by 50 W",
         "Minimum 40 W solar panel", "50 W solar panel", "COMPLIANT"),
        # Battery
        ("Battery: 40 Ah violated by 36 Ah",
         "Minimum 40 Ah lithium-ion battery", "36 Ah lithium-ion battery", "NON_COMPLIANT"),
        # Bicycle load capacity
        ("Bicycle: 120 kg violated by 90 kg",
         "Minimum load capacity: 120 kg", "Maximum load capacity: 90 kg", "NON_COMPLIANT"),
        # Vehicle speed
        ("Vehicle: 25 km/h satisfied by 30 km/h",
         "Speed: Minimum 25 km/h", "30 km/h", "COMPLIANT"),
        # Laptop RAM (still works)
        ("Laptop RAM: 32 GB violated by 16 GB base",
         "Minimum 32 GB DDR5", "16 GB expandable to 64 GB", "NON_COMPLIANT"),
        # Lab equipment - storage
        ("Lab: 2 TB satisfied by 4 TB",
         "Minimum 2 TB storage", "4 TB SSD", "COMPLIANT"),
        # Hospital - resolution
        ("Hospital: 1920×1080 — qualitative, not violated",
         "Minimum 8 MP camera", "10 MP camera with autofocus", "COMPLIANT"),
    ]

    for label, t_val, v_val, expected in cases:
        result = compare_single_requirement("Test", t_val, "minimum", v_val)
        assert_status(label, result, expected)


# ─────────────────────────────────────────────────────────────────────────────
# Suite 2: MAXIMUM constraint across domains
# ─────────────────────────────────────────────────────────────────────────────

def test_maximum():
    print("\n--- SUITE 2: MAXIMUM constraint (multi-domain) ---")
    cases = [
        # Delivery
        ("Delivery: max 30 days satisfied by 25 days",
         "Delivery: within 30 Days", "25 days", "COMPLIANT"),
        ("Delivery: max 30 days violated by 45 days",
         "Delivery: within 30 Days", "45 days", "NON_COMPLIANT"),
        ("Delivery: max 30 days with vendor range 10-15",
         "Delivery: within 30 Days", "10 to 15 days", "COMPLIANT"),
        ("Delivery: max 30 days violated by range 35-40",
         "Delivery: within 30 Days", "35 to 40 days", "NON_COMPLIANT"),
        # Weight
        ("Weight: max 2.0 kg violated by 2.3 kg",
         "Maximum 2.0 kg per unit", "2.3 kg per unit", "NON_COMPLIANT"),
        ("Weight: max 2.0 kg satisfied by 1.8 kg",
         "Maximum 2.0 kg per unit", "1.8 kg per unit", "COMPLIANT"),
        # Price / budget
        ("Price: max 48 lakhs satisfied by 46.5 lakhs",
         "Maximum total bid value: INR 48,00,000", "INR 46,50,000 total", "COMPLIANT"),
        # Temperature max
        ("Temperature: max 6 hrs battery — satisfied",
         "Maximum 6 hours", "5 hours", "COMPLIANT"),
        ("Temperature: max 6 hrs battery — violated",
         "Maximum 6 hours", "7 hours", "NON_COMPLIANT"),
    ]

    for label, t_val, v_val, expected in cases:
        result = compare_single_requirement("Test", t_val, "maximum", v_val)
        assert_status(label, result, expected)


# ─────────────────────────────────────────────────────────────────────────────
# Suite 3: RANGE constraint across domains
# ─────────────────────────────────────────────────────────────────────────────

def test_range():
    print("\n--- SUITE 3: RANGE constraint (multi-domain) ---")
    cases = [
        # Colour temperature
        ("Colour temp: 4000-6500 K, vendor 5000 K",
         "4000 K to 6500 K", "5000 K", "COMPLIANT"),
        ("Colour temp: 4000-6500 K, vendor 3500 K",
         "4000 K to 6500 K", "3500 K", "NON_COMPLIANT"),
        ("Colour temp: 4000-6500 K, vendor 7000 K",
         "4000 K to 6500 K", "7000 K", "NON_COMPLIANT"),
        # Operating temperature
        ("Op temp: 10-35 °C, vendor 25 °C",
         "10°C to 35°C", "25°C", "COMPLIANT"),
        ("Op temp: 10-35 °C, vendor 5 °C",
         "10°C to 35°C", "5°C", "NON_COMPLIANT"),
        # Heart rate monitor
        ("Heart rate: 30-250 BPM, vendor 30-250",
         "Heart-Rate Range: 30 to 250 BPM", "30-250 BPM", "COMPLIANT"),
        # Pressure range
        ("Pressure: 2-8 bar, vendor 5 bar",
         "Operating pressure: 2 bar to 8 bar", "5 bar", "COMPLIANT"),
        # RPM range
        ("RPM: 1000-3000, vendor 2500",
         "Engine speed: 1000 to 3000 RPM", "2500 RPM", "COMPLIANT"),
    ]

    for label, t_val, v_val, expected in cases:
        result = compare_single_requirement("Test", t_val, "range", v_val)
        assert_status(label, result, expected)


# ─────────────────────────────────────────────────────────────────────────────
# Suite 4: EXACT constraint
# ─────────────────────────────────────────────────────────────────────────────

def test_exact():
    print("\n--- SUITE 4: EXACT constraint ---")
    cases = [
        ("Quantity: 40 units exact match",
         "40 units", "40 units", "COMPLIANT"),
        ("Quantity: 40 vs 35 mismatch",
         "40 units", "35 units", "NON_COMPLIANT"),
    ]
    for label, t_val, v_val, expected in cases:
        result = compare_single_requirement("Test", t_val, "exact", v_val)
        assert_status(label, result, expected)


# ─────────────────────────────────────────────────────────────────────────────
# Suite 5: Unit conversion across domains
# ─────────────────────────────────────────────────────────────────────────────

def test_unit_conversion():
    print("\n--- SUITE 5: Unit conversion (cross-domain) ---")
    cases = [
        ("Luminous flux: 5000 lm vs 5.5 klm",
         "Minimum 5,000 lumens", "minimum", "5.5 klm", "COMPLIANT"),
        ("Battery: 36000 mAh vs 40 Ah",
         "Minimum 40 Ah", "minimum", "36000 mAh", "NON_COMPLIANT"),
        ("Storage: 1 TB vs 1024 GB",
         "Minimum 1 TB storage", "minimum", "1024 GB SSD", "COMPLIANT"),
        # 420 min = 7.0 hours < 8.0 hours → correctly NON_COMPLIANT
        ("Duration: 420 minutes vs 8 hours minimum",
         "Minimum 8 hours", "minimum", "420 minutes battery backup", "NON_COMPLIANT"),
        ("Weight: 5 kg vs 5000 g",
         "Maximum 5 kg", "maximum", "5000 g", "COMPLIANT"),
        ("Speed: 36 km/h vs 10 m/s",
         "Minimum 30 km/h", "minimum", "10 m/s", "COMPLIANT"),
        ("Delivery: 2 weeks vs 10 days",
         "Maximum 2 weeks", "maximum", "10 days", "COMPLIANT"),
        ("Delivery: 2 weeks vs 20 days",
         "Maximum 2 weeks", "maximum", "20 days", "NON_COMPLIANT"),
    ]
    for label, t_val, cond, v_val, expected in cases:
        result = compare_single_requirement("Test", t_val, cond, v_val)
        assert_status(label, result, expected)


# ─────────────────────────────────────────────────────────────────────────────
# Suite 6: NOT_FOUND behavior
# ─────────────────────────────────────────────────────────────────────────────

def test_not_found():
    print("\n--- SUITE 6: NOT_FOUND behavior ---")
    cases = [
        ("None vendor value",
         "Minimum 5 years warranty", None),
        ("Empty string vendor value",
         "Minimum 5 years warranty", ""),
        ("Whitespace-only vendor value",
         "Minimum 5 years warranty", "   "),
    ]
    for label, t_val, v_val in cases:
        result = compare_single_requirement("Warranty", t_val, "minimum", v_val)
        assert_status(label, result, "NOT_FOUND")


# ─────────────────────────────────────────────────────────────────────────────
# Suite 7: Qualitative text matching
# ─────────────────────────────────────────────────────────────────────────────

def test_qualitative():
    print("\n--- SUITE 7: Qualitative matching (multi-domain) ---")
    cases = [
        # (label, t_val, condition, v_val, expected)
        ("Frame material: Aluminium Alloy match",
         "Frame material: Aluminium Alloy", "minimum",
         "6061 Aluminium Alloy frame",
         "COMPLIANT"),
        ("Brakes: Hydraulic disc match",
         "Hydraulic disc brakes required", "minimum",
         "Hydraulic disc brakes on front and rear",
         "COMPLIANT"),
        ("OS: Ubuntu 24.04 exact text",
         "Ubuntu 24.04 LTS 64-bit", "exact",
         "Ubuntu 24.04 LTS 64-bit",
         "COMPLIANT"),
        # Certification: partial overlap → NEEDS_REVIEW (50% token match)
        ("Certification: CE marking partial match",
         "CE marked required", "minimum",
         "CE marked and BIS certified product",
         "NEEDS_REVIEW"),
        # Full text containment → COMPLIANT
        ("Certification: full keyword containment",
         "hydraulic disc brakes", "minimum",
         "Front and rear hydraulic disc brakes installed",
         "COMPLIANT"),
    ]
    for label, t_val, cond, v_val, expected in cases:
        result = compare_single_requirement("Test", t_val, cond, v_val)
        assert_status(label, result, expected)


# ─────────────────────────────────────────────────────────────────────────────
# Suite 8: compare_matched_pairs pipeline test
# ─────────────────────────────────────────────────────────────────────────────

def test_compare_matched_pairs():
    print("\n--- SUITE 8: compare_matched_pairs pipeline ---")

    def _req(name, value, condition="minimum", category="technical"):
        return {"requirement": name, "value": value, "condition": condition,
                "category": category, "raw_text": value}

    def _claim(name, value):
        return {"requirement": name, "value": value, "raw_text": value}

    pairs = [
        {"tender_req": _req("Output Power", "Minimum 40 W"),
         "vendor_claim": _claim("Output Power", "50 W"),
         "match_score": 1.0, "match_method": "exact", "ambiguous": False},
        {"tender_req": _req("Battery Capacity", "Minimum 40 Ah"),
         "vendor_claim": _claim("Battery", "36 Ah"),
         "match_score": 0.9, "match_method": "deterministic", "ambiguous": False},
        {"tender_req": _req("Operating Temperature", "10°C to 35°C", "range"),
         "vendor_claim": _claim("Operating Temperature", "0°C to 45°C"),
         "match_score": 1.0, "match_method": "exact", "ambiguous": False},
        {"tender_req": _req("Warranty", "Minimum 5 years", "minimum", "operational"),
         "vendor_claim": None,
         "match_score": 0.0, "match_method": "not_found", "ambiguous": False},
    ]

    result = compare_matched_pairs(pairs)
    summary = result["summary"]
    results = result["results"]

    assert summary["total"] == 4, f"Expected 4, got {summary['total']}"
    assert summary["compliant"] == 1, f"Expected 1 compliant"
    assert summary["non_compliant"] >= 1, "Expected at least 1 non_compliant"
    assert summary["not_found"] == 1, "Expected 1 not_found"

    for r in results:
        assert "requirement" in r
        assert "status" in r
        assert r["status"] in ("COMPLIANT", "NON_COMPLIANT", "NOT_FOUND", "NEEDS_REVIEW")
        assert "confidence" in r
        assert "reason" in r

    print(f"  {_OK} compare_matched_pairs: {summary}")


# ─────────────────────────────────────────────────────────────────────────────
# Suite 9: Live server — POST /verify (structure validation only)
# ─────────────────────────────────────────────────────────────────────────────

def test_live_server_verify():
    print("\n--- SUITE 9: Live server POST /verify (structure validation) ---")
    tender_path = os.path.join(os.path.dirname(__file__), "uploads", "tender.pdf")
    vendor_path = os.path.join(os.path.dirname(__file__), "uploads", "vendor.pdf")

    if not os.path.exists(tender_path) or not os.path.exists(vendor_path):
        print(f"  [SKIP] No saved PDFs in uploads/. Run through the UI first.")
        return

    try:
        with open(tender_path, "rb") as t_f, open(vendor_path, "rb") as v_f:
            response = requests.post(
                f"{BASE_URL}/verify",
                files={"tender": ("tender.pdf", t_f, "application/pdf"),
                       "vendor": ("vendor.pdf", v_f, "application/pdf")},
                timeout=120,
            )
    except requests.ConnectionError:
        print("  [SKIP] Backend server not reachable.")
        return

    assert response.status_code == 200, f"HTTP {response.status_code}"
    data = response.json()

    # Structural checks — no exact count assertions
    assert "summary" in data, "Missing 'summary' key"
    assert "results" in data, "Missing 'results' key"
    summary = data["summary"]
    assert "total" in summary
    assert "compliant" in summary
    assert "non_compliant" in summary
    assert "not_found" in summary
    assert "needs_review" in summary
    assert summary["total"] == len(data["results"])
    assert summary["total"] > 0, "Expected at least 1 result"

    for r in data["results"]:
        assert "requirement" in r
        assert "status" in r
        assert r["status"] in ("COMPLIANT", "NON_COMPLIANT", "NOT_FOUND", "NEEDS_REVIEW")
        assert "confidence" in r
        assert "reason" in r
        assert "tender_evidence" in r
        assert "vendor_evidence" in r

    print(f"  {_OK} POST /verify — {summary['total']} results, structure valid")
    print(f"  Summary: compliant={summary['compliant']}, non_compliant={summary['non_compliant']}, "
          f"not_found={summary['not_found']}, needs_review={summary['needs_review']}")


# ─────────────────────────────────────────────────────────────────────────────
# Suite 10: Live server — POST /upload health check
# ─────────────────────────────────────────────────────────────────────────────

def test_live_server_health():
    print("\n--- SUITE 10: Live server health check ---")
    try:
        r = requests.get(f"{BASE_URL}/", timeout=5)
        assert r.status_code == 200
        data = r.json()
        assert "message" in data
        assert "ai_provider" in data
        print(f"  {_OK} GET / — {data['message']} (provider: {data['ai_provider']})")
    except requests.ConnectionError:
        print("  [SKIP] Backend server not reachable.")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("BidVerify AI — Generic Compliance Tests")
    print("=" * 60)

    failed = 0
    tests = [
        test_minimum,
        test_maximum,
        test_range,
        test_exact,
        test_unit_conversion,
        test_not_found,
        test_qualitative,
        test_compare_matched_pairs,
        test_live_server_health,
        test_live_server_verify,
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
        print("ALL GENERIC COMPLIANCE TESTS PASSED SUCCESSFULLY!")
    else:
        print(f"{failed} TEST(S) FAILED.")
    print("=" * 60)
    sys.exit(0 if failed == 0 else 1)

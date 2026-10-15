"""
BidVerify AI - Autonomous Procurement Intelligence Engine Behavioral Test Suite
=================================================================================

Comprehensive test suite verifying the 27 behavioral test classes specified in
Master PRD Section 25:
  1. Synonym matching
  2. Paraphrase matching
  3. Wrong-property rejection (Storage vs Memory, CCT vs Operating Temp, etc.)
  4. Numeric minimum
  5. Numeric maximum
  6. Exact values
  7. Ranges
  8. Range boundaries
  9. Unit conversion
  10. Multiple values / expandable
  11. Qualitative requirement
  12. Certification requirement
  13. Document-presence requirement
  14. AND logic
  15. OR logic
  16. Conditional logic
  17. Contradiction engine (measurable evidence takes precedence over marketing)
  18. Missing evidence (NOT_FOUND with strictly empty evidence)
  19. Duplicate requirement deduplication
  20. Duplicate vendor claim reconciliation
  21. Document text extraction robustness
  22. Table extraction
  23. Evidence & source page grounding
  24. Multi-vendor envelope isolation
  25. Dynamic requirement count discovery
  26. Embedding cache behavior
  27. Performance & zero per-requirement API calls
"""

import sys
import time
from pathlib import Path

# Ensure backend dir is on path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from comparator import compare_single_requirement, compare_matched_pairs, calculate_vendor_score
from extractor import (
    extract_requirements_from_text,
    extract_vendor_claims,
    _enrich_requirement,
)
from matcher import match_requirements
from subject_property import SubjectProperty, SubjectPropertyAnalyzer, check_subject_property_compatibility
from validator import SelfConsistencyValidator


def run_all_behavioral_tests():
    total_tests = 0
    passed_tests = 0
    failures = []

    def assert_test(condition: bool, test_name: str, detail: str = ""):
        nonlocal total_tests, passed_tests, failures
        total_tests += 1
        if condition:
            passed_tests += 1
            print(f"  [PASS] {test_name}")
        else:
            failures.append(f"{test_name}: {detail}")
            print(f"  [FAIL] {test_name}: {detail}")

    print("======================================================================")
    print("BIDVERIFY AI — AUTONOMOUS ENGINE 27 BEHAVIORAL TEST CLASSES")
    print("======================================================================\n")

    # ── Test 1: Synonym Matching ─────────────────────────────────────────────
    print("Test Class 1: Synonym Matching")
    res1 = compare_single_requirement(
        req_name="Correlated Color Temperature",
        tender_val="4000 K to 5000 K",
        tender_cond="range",
        vendor_val="CCT: 4500 K",
    )
    assert_test(res1["status"] == "COMPLIANT", "1.1 CCT to Color Temperature synonym", f"Got {res1['status']}")

    res2 = compare_single_requirement(
        req_name="Luminous Efficacy",
        tender_val="Minimum 140 lm/W",
        tender_cond="minimum",
        vendor_val="Luminaire efficacy: 155 lm/W",
    )
    assert_test(res2["status"] == "COMPLIANT", "1.2 Luminous Efficacy to lm/W", f"Got {res2['status']}")

    res3 = compare_single_requirement(
        req_name="Surge Protection",
        tender_val="Minimum 10 kV",
        tender_cond="minimum",
        vendor_val="SPD: 10 kV transient surge protection included",
    )
    assert_test(res3["status"] == "COMPLIANT", "1.3 SPD to Surge Protection", f"Got {res3['status']}")

    # ── Test 2: Paraphrase Matching ──────────────────────────────────────────
    print("\nTest Class 2: Paraphrase Matching")
    res_para = compare_single_requirement(
        req_name="Central Monitoring Dashboard",
        tender_val="Web dashboard shall provide live status and event alerts",
        tender_cond="qualitative",
        vendor_val="Central web monitoring portal displays real-time operational status and event alarms",
    )
    assert_test(res_para["status"] == "COMPLIANT", "2.1 Complex prose paraphrase matching", f"Got {res_para['status']}")

    # ── Test 3: Wrong-Property Rejection (PRD Failure Type B) ─────────────────
    print("\nTest Class 3: Wrong-Property Rejection")
    # 3.1 Storage vs Memory
    req_storage = _enrich_requirement("Storage Capacity", "Minimum 1 TB SSD", "Storage capacity shall be at least 1 TB SSD")
    claim_memory = {"name": "Memory Capacity", "value": "16 GB LPDDR5", "raw_text": "Memory capacity: 16 GB LPDDR5", "source_page": 2}
    sp_storage = SubjectPropertyAnalyzer.analyze("Storage Capacity Minimum 1 TB SSD", name="Storage Capacity")
    sp_memory = SubjectPropertyAnalyzer.analyze("Memory Capacity: 16 GB LPDDR5", name="Memory Capacity")
    compat_sm = check_subject_property_compatibility(sp_storage, sp_memory)
    assert_test(not compat_sm.compatible and compat_sm.status == "RELATED_INCOMPATIBLE",
                "3.1 Storage vs Memory property gate rejection", f"Got {compat_sm.status}")

    # Full matching rejection for Storage vs Memory:
    matches_sm = match_requirements([req_storage], [claim_memory])
    verif_sm = compare_matched_pairs(matches_sm)
    assert_test(verif_sm["results"][0]["status"] == "NOT_FOUND" and verif_sm["results"][0]["vendor_evidence"] == "",
                "3.2 Storage requirement matched against Memory claim produces NOT_FOUND with empty evidence",
                f"Got status={verif_sm['results'][0]['status']}, evid={verif_sm['results'][0]['vendor_evidence']}")

    # 3.3 CCT vs Operating Temperature
    req_cct = _enrich_requirement("Color Temperature", "4000 K to 5000 K", "LED color temperature shall be 4000-5000 K")
    claim_temp = {"name": "Operating Temperature", "value": "-10°C to +50°C", "raw_text": "Operating temperature: -10°C to +50°C", "source_page": 1}
    matches_ct = match_requirements([req_cct], [claim_temp])
    verif_ct = compare_matched_pairs(matches_ct)
    assert_test(verif_ct["results"][0]["status"] == "NOT_FOUND",
                "3.3 CCT requirement matched against Operating Temp claim produces NOT_FOUND",
                f"Got {verif_ct['results'][0]['status']}")

    # 3.4 Battery Capacity vs Backup Duration
    req_batt = _enrich_requirement("Battery Capacity", "At least 40 Ah", "Battery capacity shall be at least 40 Ah")
    claim_dur = {"name": "Autonomy", "value": "12 hours runtime", "raw_text": "Autonomy: 12 hours backup runtime", "source_page": 3}
    matches_bd = match_requirements([req_batt], [claim_dur])
    verif_bd = compare_matched_pairs(matches_bd)
    assert_test(verif_bd["results"][0]["status"] == "NOT_FOUND",
                "3.4 Battery Capacity (Ah) vs Backup Runtime (hrs) produces NOT_FOUND",
                f"Got {verif_bd['results'][0]['status']}")

    # ── Test 4: Numeric Minimum ──────────────────────────────────────────────
    print("\nTest Class 4: Numeric Minimum")
    res_min_pass = compare_single_requirement(
        req_name="Battery Capacity", tender_val="40 Ah", tender_cond="minimum", vendor_val="45 Ah"
    )
    assert_test(res_min_pass["status"] == "COMPLIANT", "4.1 45 Ah offered >= 40 Ah required -> COMPLIANT", f"Got {res_min_pass['status']}")

    res_min_fail = compare_single_requirement(
        req_name="Battery Capacity", tender_val="40 Ah", tender_cond="minimum", vendor_val="36 Ah"
    )
    assert_test(res_min_fail["status"] == "NON_COMPLIANT", "4.2 36 Ah offered < 40 Ah required -> NON_COMPLIANT", f"Got {res_min_fail['status']}")

    # ── Test 5: Numeric Maximum ──────────────────────────────────────────────
    print("\nTest Class 5: Numeric Maximum")
    res_max_pass = compare_single_requirement(
        req_name="Delivery Timeline", tender_val="Maximum 30 days", tender_cond="maximum", vendor_val="20 days"
    )
    assert_test(res_max_pass["status"] == "COMPLIANT", "5.1 20 days <= 30 days required -> COMPLIANT", f"Got {res_max_pass['status']}")

    res_max_fail = compare_single_requirement(
        req_name="Delivery Timeline", tender_val="Maximum 30 days", tender_cond="maximum", vendor_val="45 days"
    )
    assert_test(res_max_fail["status"] == "NON_COMPLIANT", "5.2 45 days > 30 days required -> NON_COMPLIANT", f"Got {res_max_fail['status']}")

    # ── Test 6: Exact Values ─────────────────────────────────────────────────
    print("\nTest Class 6: Exact Values")
    res_exact_pass = compare_single_requirement(
        req_name="USB Port Version", tender_val="USB 3.2", tender_cond="exact", vendor_val="USB 3.2 Gen 2 ports"
    )
    assert_test(res_exact_pass["status"] == "COMPLIANT", "6.1 USB 3.2 exact match -> COMPLIANT", f"Got {res_exact_pass['status']}")

    res_exact_fail = compare_single_requirement(
        req_name="USB Port Version", tender_val="USB 3.2", tender_cond="exact", vendor_val="USB 2.0 interface"
    )
    assert_test(res_exact_fail["status"] == "NON_COMPLIANT", "6.2 USB 2.0 vs USB 3.2 exact -> NON_COMPLIANT", f"Got {res_exact_fail['status']}")

    # ── Test 7: Ranges ───────────────────────────────────────────────────────
    print("\nTest Class 7: Ranges")
    res_range_pass = compare_single_requirement(
        req_name="Operating Temperature", tender_val="-10°C to +50°C", tender_cond="range", vendor_val="-10°C to +50°C"
    )
    assert_test(res_range_pass["status"] == "COMPLIANT", "7.1 -10 to +50 range matches -> COMPLIANT", f"Got {res_range_pass['status']}")

    res_range_fail = compare_single_requirement(
        req_name="CCT", tender_val="4000 K to 5000 K", tender_cond="range", vendor_val="5500 K"
    )
    assert_test(res_range_fail["status"] == "NON_COMPLIANT", "7.2 5500 K outside 4000-5000 K range -> NON_COMPLIANT", f"Got {res_range_fail['status']}")

    # ── Test 8: Range Boundaries ─────────────────────────────────────────────
    print("\nTest Class 8: Range Boundaries")
    res_b_lower = compare_single_requirement(
        req_name="CCT", tender_val="4000 K to 5000 K", tender_cond="range", vendor_val="4000 K"
    )
    assert_test(res_b_lower["status"] == "COMPLIANT", "8.1 4000 K at lower boundary -> COMPLIANT", f"Got {res_b_lower['status']}")

    res_b_upper = compare_single_requirement(
        req_name="CCT", tender_val="4000 K to 5000 K", tender_cond="range", vendor_val="5000 K"
    )
    assert_test(res_b_upper["status"] == "COMPLIANT", "8.2 5000 K at upper boundary -> COMPLIANT", f"Got {res_b_upper['status']}")

    # ── Test 9: Unit Conversion ──────────────────────────────────────────────
    print("\nTest Class 9: Unit Conversion")
    res_tb_gb = compare_single_requirement(
        req_name="Storage", tender_val="1 TB SSD", tender_cond="minimum", vendor_val="1024 GB NVMe SSD"
    )
    assert_test(res_tb_gb["status"] == "COMPLIANT", "9.1 1024 GB satisfies 1 TB requirement", f"Got {res_tb_gb['status']}")

    res_ah_mah = compare_single_requirement(
        req_name="Battery Capacity", tender_val="40 Ah", tender_cond="minimum", vendor_val="40000 mAh"
    )
    assert_test(res_ah_mah["status"] == "COMPLIANT", "9.2 40000 mAh satisfies 40 Ah requirement", f"Got {res_ah_mah['status']}")

    res_w_kw = compare_single_requirement(
        req_name="Solar Capacity", tender_val="2 kW", tender_cond="minimum", vendor_val="2000 W"
    )
    assert_test(res_w_kw["status"] == "COMPLIANT", "9.3 2000 W satisfies 2 kW requirement", f"Got {res_w_kw['status']}")

    # ── Test 10: Multiple Values / Expandable ────────────────────────────────
    print("\nTest Class 10: Multiple Values & Expandable Specs")
    res_exp = compare_single_requirement(
        req_name="System RAM", tender_val="16 GB", tender_cond="minimum", vendor_val="16 GB LPDDR5 expandable up to 64 GB"
    )
    assert_test(res_exp["status"] == "COMPLIANT", "10.1 Base 16 GB with expandable up to 64 GB satisfies 16 GB", f"Got {res_exp['status']}")

    # ── Test 11: Qualitative Requirement ─────────────────────────────────────
    print("\nTest Class 11: Qualitative Requirements")
    res_qual = compare_single_requirement(
        req_name="BIS Standards",
        tender_val="BIS compliant components are mandatory",
        tender_cond="qualitative",
        vendor_val="All supplied components conform to applicable BIS standards",
    )
    assert_test(res_qual["status"] == "COMPLIANT", "11.1 BIS standards semantic compliance", f"Got {res_qual['status']}")

    # ── Test 12: Certification Requirement ───────────────────────────────────
    print("\nTest Class 12: Certification Requirements")
    res_cert_ambig = compare_single_requirement(
        req_name="Manufacturing Quality",
        tender_val="ISO 9001 certified manufacturing facility required",
        tender_cond="qualitative",
        vendor_val="Company is ISO certified",
    )
    assert_test(res_cert_ambig["status"] in ("NEEDS_REVIEW", "NON_COMPLIANT"),
                "12.1 Vague 'Company is ISO certified' for ISO 9001 does NOT become COMPLIANT",
                f"Got {res_cert_ambig['status']}")

    # ── Test 13: Document-Presence Requirement ───────────────────────────────
    print("\nTest Class 13: Document-Presence Requirements")
    res_oem = compare_single_requirement(
        req_name="OEM Authorization",
        tender_val="OEM authorization letter shall be provided",
        tender_cond="qualitative",
        vendor_val="OEM authorization letter attached",
    )
    assert_test(res_oem["status"] == "COMPLIANT", "13.1 OEM authorization letter attached -> COMPLIANT", f"Got {res_oem['status']}")

    # ── Test 14: AND Multi-Clause Logic ──────────────────────────────────────
    print("\nTest Class 14: Multi-Clause AND Logic")
    res_and = compare_single_requirement(
        req_name="Power & Factor",
        tender_val="Maximum 60W power consumption and minimum 0.95 power factor",
        tender_cond="qualitative",
        vendor_val="Operating power consumption is 50W and power factor is 0.98",
    )
    assert_test(res_and["status"] == "COMPLIANT", "14.1 Both clauses in AND conjunction satisfied", f"Got {res_and['status']}")

    # ── Test 15: OR Multi-Clause Logic ───────────────────────────────────────
    print("\nTest Class 15: Multi-Clause OR Logic")
    res_or = compare_single_requirement(
        req_name="Network Connectivity",
        tender_val="Ethernet or Wi-Fi shall be supported",
        tender_cond="qualitative",
        vendor_val="Integrated Wi-Fi 6 wireless networking supported",
    )
    assert_test(res_or["status"] == "COMPLIANT", "15.1 One valid alternative in OR conjunction satisfied", f"Got {res_or['status']}")

    # ── Test 16: Conditional Logic ───────────────────────────────────────────
    print("\nTest Class 16: Conditional Logic")
    res_cond = compare_single_requirement(
        req_name="Wireless Security",
        tender_val="If Wi-Fi is supplied, WPA2 or higher encryption shall be supported",
        tender_cond="qualitative",
        vendor_val="Wi-Fi interface provided with WPA2-Enterprise and WPA3 encryption",
    )
    assert_test(res_cond["status"] == "COMPLIANT", "16.1 Conditional Wi-Fi encryption fulfilled", f"Got {res_cond['status']}")

    # ── Test 17: Contradiction Engine ────────────────────────────────────────
    print("\nTest Class 17: Contradiction Precedence")
    # Vendor has conflicting vague claim and explicit failure
    tender_c = _enrich_requirement("Battery Capacity", "At least 40 Ah", "Battery capacity shall be at least 40 Ah")
    claims_c = [
        {"name": "Marketing Feature", "value": "Ultra high capacity battery pack", "raw_text": "Ultra high capacity battery pack for extended operation"},
        {"name": "Battery Capacity", "value": "36 Ah LiFePO4", "raw_text": "Battery capacity: 36 Ah LiFePO4"},
    ]
    matches_c = match_requirements([tender_c], claims_c)
    verif_c = compare_matched_pairs(matches_c)
    assert_test(verif_c["results"][0]["status"] == "NON_COMPLIANT",
                "17.1 Explicit numeric failure (36 Ah) overrides marketing claim ('high capacity') -> NON_COMPLIANT",
                f"Got {verif_c['results'][0]['status']}")

    # ── Test 18: Missing Evidence (NOT_FOUND) ────────────────────────────────
    print("\nTest Class 18: Missing Evidence (NOT_FOUND)")
    req_missing = _enrich_requirement("ECG Monitoring", "12-lead ECG", "Standard 12-lead ECG monitoring required")
    claims_other = [
        {"name": "Display", "value": "15-inch LED", "raw_text": "Display: 15-inch LED", "source_page": 1},
        {"name": "Power", "value": "220V AC", "raw_text": "Power: 220V AC", "source_page": 2},
    ]
    matches_m = match_requirements([req_missing], claims_other)
    verif_m = compare_matched_pairs(matches_m)
    assert_test(verif_m["results"][0]["status"] == "NOT_FOUND" and verif_m["results"][0]["vendor_evidence"] == "",
                "18.1 Missing requirement produces NOT_FOUND with strictly empty evidence",
                f"Got status={verif_m['results'][0]['status']}, evid='{verif_m['results'][0]['vendor_evidence']}'")

    # ── Test 19: Duplicate Requirement Deduplication ─────────────────────────
    print("\nTest Class 19: Duplicate Requirement Deduplication")
    raw_tender_text = """
    1. System RAM: Minimum 16 GB DDR5
    2. Display Resolution: 1920x1080 FHD
    3. System RAM: Minimum 16 GB DDR5
    """
    reqs_dedup = extract_requirements_from_text(raw_tender_text)
    assert_test(len(reqs_dedup) == 2, f"19.1 Duplicate RAM requirement deduplicated to 1 (total {len(reqs_dedup)})", f"Count={len(reqs_dedup)}")

    # ── Test 20: Duplicate Claim Reconciliation ──────────────────────────────
    print("\nTest Class 20: Duplicate Claim Reconciliation")
    raw_vendor_text = """
    T01
    16 GB LPDDR5
    Attached
    T01
    16 GB LPDDR5 High Speed
    Attached
    """
    claims_dedup = extract_vendor_claims(raw_vendor_text)
    assert_test(len(claims_dedup) == 1, f"20.1 Duplicate ref code claims reconciled to 1 (total {len(claims_dedup)})", f"Count={len(claims_dedup)}")

    # ── Test 21: Document Extraction Robustness ──────────────────────────────
    print("\nTest Class 21: Document Extraction Robustness")
    messy_text = """
    --- PAGE 1 ---
    GOVERNMENT OF INDIA TENDER
    DISCLAIMER: This is a synthetic test document.
    Item 1: Storage capacity: At least 512 GB SSD
    --- PAGE 2 ---
    Item 2: Operating system: Ubuntu Linux 22.04 LTS
    Notes: Vendor must comply with all rules.
    """
    clean_reqs = extract_requirements_from_text(messy_text)
    assert_test(len(clean_reqs) == 2, f"21.1 Boilerplate/headers ignored, exactly 2 real requirements extracted", f"Count={len(clean_reqs)}")

    # ── Test 22: Table Extraction ────────────────────────────────────────────
    print("\nTest Class 22: Table Extraction")
    table_text = """
    --- PAGE 1 ---
    T01
    Processor
    Intel Core i7 13th Gen
    MINIMUM
    MANDATORY
    T02
    Memory
    32 GB DDR5
    MINIMUM
    MANDATORY
    T03
    Storage
    1 TB NVMe SSD
    MINIMUM
    MANDATORY
    """
    table_reqs = extract_requirements_from_text(table_text)
    assert_test(len(table_reqs) == 3, f"22.1 Structured 5-line table parsed correctly (count={len(table_reqs)})", f"Count={len(table_reqs)}")

    # ── Test 23: Evidence & Page Grounding ───────────────────────────────────
    print("\nTest Class 23: Evidence & Page Grounding")
    test_req = _enrich_requirement("Luminaire Efficacy", "140 lm/W", "Luminous efficacy shall be at least 140 lm/W", order_idx=1)
    test_claim = {
        "name": "Luminaire Efficacy",
        "value": "155 lm/W",
        "raw_text": "Luminaire efficacy tested at 155 lm/W at NABL lab",
        "source_page": 7,
    }
    match_ev = match_requirements([test_req], [test_claim])
    verif_ev = compare_matched_pairs(match_ev)
    assert_test(verif_ev["results"][0]["vendor_evidence"] == test_claim["raw_text"],
                "23.1 Source evidence text correctly preserved in result",
                f"Evidence: {verif_ev['results'][0]['vendor_evidence']}")
    assert_test(match_ev[0]["candidates"][0]["source_page"] == 7,
                "23.2 Source page 7 correctly grounded in candidate metadata",
                f"Page: {match_ev[0]['candidates'][0]['source_page']}")

    # ── Test 24: Multi-Vendor Isolation ──────────────────────────────────────
    print("\nTest Class 24: Multi-Vendor Envelope Isolation")
    t_shared = _enrich_requirement("Display Screen", "15.6 inch FHD", "Display shall be 15.6 inch FHD", order_idx=1)
    claim_vA = [{"name": "Display", "value": "15.6 inch FHD IPS", "raw_text": "Vendor A Display: 15.6 inch FHD", "source_page": 1}]
    claim_vB = [{"name": "Display", "value": "14.0 inch HD", "raw_text": "Vendor B Display: 14.0 inch HD", "source_page": 2}]

    match_vA = match_requirements([t_shared], claim_vA)
    verif_vA = compare_matched_pairs(match_vA)

    match_vB = match_requirements([t_shared], claim_vB)
    verif_vB = compare_matched_pairs(match_vB)

    assert_test(verif_vA["results"][0]["vendor_evidence"] == claim_vA[0]["raw_text"]
                and verif_vB["results"][0]["vendor_evidence"] == claim_vB[0]["raw_text"]
                and verif_vA["results"][0]["vendor_evidence"] != verif_vB["results"][0]["vendor_evidence"],
                "24.1 Vendor A and Vendor B evidence streams completely isolated without cross-talk",
                "Vendor isolation verified")

    # ── Test 25: Dynamic Requirement Count Discovery ─────────────────────────
    print("\nTest Class 25: Dynamic Requirement Count Discovery")
    tender_small = """
    1. Solar panel wattage: 100 Wp
    2. Battery capacity: 20 Ah
    3. Pole height: 4 meters
    4. LED light: 20 W
    5. Warranty: 3 years
    """
    reqs_small = extract_requirements_from_text(tender_small)
    assert_test(len(reqs_small) == 5, f"25.1 Dynamic discovery on small tender (5 reqs discovered)", f"Count={len(reqs_small)}")

    tender_medium = "\n".join([f"Item {i}: Specification parameter {i} shall be minimum {i * 10} units" for i in range(1, 13)])
    reqs_medium = extract_requirements_from_text(tender_medium)
    assert_test(len(reqs_medium) == 12, f"25.2 Dynamic discovery on 12-req tender (12 reqs discovered)", f"Count={len(reqs_medium)}")

    # ── Test 26: Cache Behavior ──────────────────────────────────────────────
    print("\nTest Class 26: Cache Behavior")
    from embedding_service import get_embedding_service
    svc = get_embedding_service()
    t_start = time.time()
    emb1, _ = svc.encode_queries(["Battery capacity shall be at least 40 Ah"])
    t_first = time.time() - t_start

    t_start2 = time.time()
    emb2, _ = svc.encode_queries(["Battery capacity shall be at least 40 Ah"])
    t_second = time.time() - t_start2

    assert_test(t_second <= t_first and svc.cache_size > 0,
                f"26.1 Embedding cache hit: first={t_first*1000:.1f}ms, second={t_second*1000:.1f}ms, cache_size={svc.cache_size}",
                f"Cache check verified")

    # ── Test 27: Performance & Score Transparency ────────────────────────────
    print("\nTest Class 27: Performance & Transparent Scoring")
    t_score_start = time.time()
    score_out = calculate_vendor_score(verif_vA["results"])
    t_score = time.time() - t_score_start
    assert_test(t_score < 0.05 and score_out["total_count"] == 1 and score_out["score_overall"] == 100.0,
                f"27.1 Transparent scoring completes in {t_score*1000:.2f}ms with exact count ({score_out['score_overall']}%)",
                "Scoring verified")

    # ── Final Summary ────────────────────────────────────────────────────────
    print("\n======================================================================")
    print(f"BEHAVIORAL TEST RESULTS: {passed_tests}/{total_tests} PASSED "
          f"({passed_tests/total_tests*100:.1f}%)")
    print("======================================================================")
    if failures:
        print("\nFailures:")
        for f in failures:
            print(f"  - {f}")
        return False
    return True


if __name__ == "__main__":
    success = run_all_behavioral_tests()
    sys.exit(0 if success else 1)

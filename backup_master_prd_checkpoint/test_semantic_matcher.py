"""
Focused test for Step 5: Semantic Qwen Embedding Retrieval & Deterministic Numeric Verification
"""

import os
import sys
import time

backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

from matcher import match_requirements, get_last_match_diagnostics
from comparator import compare_matched_pairs, compare_single_requirement
from ai_provider import DeterministicProvider

def test_semantic_retrieval_and_numeric_verification():
    print("=" * 70)
    print("Testing Semantic Candidate Retrieval + Deterministic Numeric Verification")
    print("=" * 70)

    # 1. Battery capacity: min 40 Ah vs 36 Ah (NON_COMPLIANT) & 45 Ah (COMPLIANT)
    req_battery = {
        "requirement": "Battery Capacity",
        "value": "minimum 40 Ah",
        "condition": "minimum",
        "raw_text": "Minimum battery capacity shall be 40 Ah.",
    }

    # Vendor 1 offers 36 Ah
    claims_v1 = [
        {"requirement": "Enclosure", "value": "Aluminum IP66", "raw_text": "System enclosure is aluminum with IP66 rating.", "source_page": 2},
        {"requirement": "Rated Battery Capacity", "value": "36 Ah", "raw_text": "Rated battery capacity: 36 Ah lithium-ion pack.", "source_page": 4},
        {"requirement": "Lighting Output", "value": "12000 lumens", "raw_text": "Luminous output is 12000 lumens.", "source_page": 5},
    ]

    matched_v1 = match_requirements([req_battery], claims_v1, provider=DeterministicProvider())
    assert len(matched_v1) == 1
    assert matched_v1[0]["vendor_claim"] is not None
    assert "36 Ah" in matched_v1[0]["vendor_claim"]["value"]
    assert matched_v1[0]["vendor_claim"]["source_page"] == 4

    comp_v1 = compare_matched_pairs(matched_v1)["results"][0]
    print(f"Test 1a (Battery 40Ah min vs 36Ah): Status = {comp_v1['status']} | Reason: {comp_v1['reason']}")
    assert comp_v1["status"] == "NON_COMPLIANT", f"Expected NON_COMPLIANT, got {comp_v1['status']}"

    # Vendor 2 offers 45 Ah
    claims_v2 = [
        {"requirement": "Enclosure", "value": "Aluminum IP66", "raw_text": "System enclosure is aluminum with IP66 rating.", "source_page": 2},
        {"requirement": "Nominal Battery Capacity", "value": "45 Ah", "raw_text": "Nominal battery capacity of 45 Ah.", "source_page": 3},
    ]
    matched_v2 = match_requirements([req_battery], claims_v2, provider=DeterministicProvider())
    comp_v2 = compare_matched_pairs(matched_v2)["results"][0]
    print(f"Test 1b (Battery 40Ah min vs 45Ah): Status = {comp_v2['status']} | Reason: {comp_v2['reason']}")
    assert comp_v2["status"] == "COMPLIANT", f"Expected COMPLIANT, got {comp_v2['status']}"

    # 2. Color temperature range: 4000-5000 K vs 5000 K (COMPLIANT) & 5500 K (NON_COMPLIANT)
    req_cct = {
        "requirement": "Color Temperature",
        "value": "4000-5000 K",
        "condition": "range",
        "raw_text": "Correlated color temperature shall be 4000–5000 K.",
    }
    claims_cct_ok = [
        {"requirement": "CCT", "value": "5000 K", "raw_text": "CCT: 5000 K daylight white.", "source_page": 1},
    ]
    matched_cct_ok = match_requirements([req_cct], claims_cct_ok, provider=DeterministicProvider())
    comp_cct_ok = compare_matched_pairs(matched_cct_ok)["results"][0]
    print(f"Test 2a (CCT 4000-5000K vs 5000K): Status = {comp_cct_ok['status']} | Reason: {comp_cct_ok['reason']}")
    assert comp_cct_ok["status"] == "COMPLIANT", f"Expected COMPLIANT, got {comp_cct_ok['status']}"

    claims_cct_fail = [
        {"requirement": "CCT", "value": "5500 K", "raw_text": "CCT: 5500 K cool white.", "source_page": 1},
    ]
    matched_cct_fail = match_requirements([req_cct], claims_cct_fail, provider=DeterministicProvider())
    comp_cct_fail = compare_matched_pairs(matched_cct_fail)["results"][0]
    print(f"Test 2b (CCT 4000-5000K vs 5500K): Status = {comp_cct_fail['status']} | Reason: {comp_cct_fail['reason']}")
    assert comp_cct_fail["status"] == "NON_COMPLIANT", f"Expected NON_COMPLIANT, got {comp_cct_fail['status']}"

    # 3. Luminous flux: 12000 lumens vs 12 klm
    req_lumens = {
        "requirement": "LED Luminaire Flux",
        "value": "minimum 12000 lumens",
        "condition": "minimum",
        "raw_text": "LED luminaire must provide at least 12000 lumens.",
    }
    claims_lumens = [
        {"requirement": "Light Output", "value": "12 klm", "raw_text": "Luminous output: 12 klm.", "source_page": 2},
        {"requirement": "Mounting", "value": "Pole mount", "raw_text": "Pole mount hardware included.", "source_page": 3},
    ]
    matched_lumens = match_requirements([req_lumens], claims_lumens, provider=DeterministicProvider())
    comp_lumens = compare_matched_pairs(matched_lumens)["results"][0]
    print(f"Test 3 (12000 lm vs 12 klm): Status = {comp_lumens['status']} | Matched claim: {matched_lumens[0]['vendor_claim']['requirement']} ({matched_lumens[0]['vendor_claim']['value']})")
    assert comp_lumens["status"] == "COMPLIANT", f"Expected COMPLIANT, got {comp_lumens['status']}"

    # 4. NOT_FOUND rule test: completely unmentioned requirement
    req_solar = {
        "requirement": "Solar Tracking Mechanism",
        "value": "Dual axis automated tracking",
        "condition": "exact",
        "raw_text": "Solar tracking system shall support dual-axis automatic sun tracking.",
    }
    laptop_claims = [
        {"requirement": "RAM", "value": "16 GB DDR5", "raw_text": "System has 16 GB DDR5 memory.", "source_page": 1},
        {"requirement": "Processor", "value": "Intel Core i7", "raw_text": "Intel Core i7-13700H CPU.", "source_page": 1},
    ]
    matched_nf = match_requirements([req_solar], laptop_claims, provider=DeterministicProvider())
    assert len(matched_nf) == 1
    assert matched_nf[0]["match_method"] == "not_found"
    assert matched_nf[0]["vendor_claim"] is None, "Evidence must be empty/null for NOT_FOUND!"
    comp_nf = compare_matched_pairs(matched_nf)["results"][0]
    print(f"Test 4 (Solar tracking in laptop tender -> NOT_FOUND): Status = {comp_nf['status']} | vendor_val = '{comp_nf['vendor_value']}' | vendor_evidence = '{comp_nf['vendor_evidence']}'")
    assert comp_nf["status"] == "NOT_FOUND"
    assert comp_nf["vendor_evidence"] == ""

    # 5. Diagnostics verification
    diag = get_last_match_diagnostics()
    print("\nDiagnostics:")
    for k, v in diag.items():
        print(f"  {k}: {v}")
    assert "embedding_model_load_time" in diag
    assert "requirement_embedding_time" in diag
    assert "vendor_embedding_time" in diag
    assert "semantic_matching_time" in diag
    assert "requirements_count" in diag
    assert "vendor_claims_count" in diag
    assert "candidate_matches_count" in diag
    assert "not_found_count" in diag

    print("\nAll semantic retrieval tests PASSED successfully!")

if __name__ == "__main__":
    test_semantic_retrieval_and_numeric_verification()

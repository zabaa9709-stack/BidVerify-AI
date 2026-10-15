"""
BidVerify AI - 50-Requirement Multi-Vendor Benchmark & Diagnostic Suite
Measures accuracy, execution timing, retrieval metrics, and score validation
against ground truth across AuroraGrid, NovaLite, and EcoRay synthetic bids.
"""

import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, List

# Ensure backend root is on python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from extractor import extract_text_from_pdf_path, extract_requirements_from_text, extract_vendor_claims
from matcher import match_requirements
from comparator import compare_matched_pairs, calculate_vendor_score
from ai_provider import DeterministicProvider

BENCHMARK_GROUND_TRUTH = {
    "AuroraGrid": {
        "expected_score": 94.0,
        "expected_compliant": 46,
        "expected_review": 2,
        "expected_non_compliant": 2,
        "expected_not_found": 0,
    },
    "NovaLite": {
        "expected_score": 78.0,
        "expected_compliant": 37,
        "expected_review": 4,
        "expected_non_compliant": 5,
        "expected_not_found": 4,
    },
    "EcoRay": {
        "expected_score": 67.0,
        "expected_compliant": 31,
        "expected_review": 5,
        "expected_non_compliant": 7,
        "expected_not_found": 7,
    },
}

VENDORS = [
    ("AuroraGrid", "Vendor_AuroraGrid_Synthetic_Bid.pdf"),
    ("NovaLite", "Vendor_NovaLite_Synthetic_Bid.pdf"),
    ("EcoRay", "Vendor_EcoRay_Synthetic_Bid.pdf"),
]


def run_benchmark(verbose_diagnostics: bool = False):
    print("=" * 80)
    print("BIDVERIFY AI — 50-REQUIREMENT BENCHMARK & DIAGNOSTIC RUNNER")
    print("=" * 80)

    # 1. Tender Extraction
    tender_pdf = Path("Tender_50_Requirements_Messy_Synthetic.pdf")
    if not tender_pdf.exists():
        print(f"ERROR: Tender PDF not found at {tender_pdf.resolve()}")
        sys.exit(1)

    t0 = time.time()
    tender_raw_text = extract_text_from_pdf_path(tender_pdf)
    t_tender_pdf = time.time() - t0

    t0 = time.time()
    tender_reqs = extract_requirements_from_text(tender_raw_text)
    t_tender_extract = time.time() - t0

    print(f"Tender Document Parsed: {len(tender_raw_text)} chars ({t_tender_pdf:.2f}s)")
    print(f"Tender Requirements Extracted: {len(tender_reqs)} requirements ({t_tender_extract:.2f}s)")
    print("-" * 80)

    benchmark_summary = []
    deterministic_provider = DeterministicProvider()

    for vendor_name, vendor_file in VENDORS:
        v_pdf = Path(vendor_file)
        if not v_pdf.exists():
            print(f"WARNING: Vendor file {vendor_file} not found, skipping.")
            continue

        print(f"\nEvaluating Vendor: {vendor_name} ({vendor_file})")

        # Extraction
        t0 = time.time()
        v_raw_text = extract_text_from_pdf_path(v_pdf)
        t_v_pdf = time.time() - t0

        t0 = time.time()
        v_claims = extract_vendor_claims(v_raw_text)
        if not v_claims:
            v_claims = extract_requirements_from_text(v_raw_text)
        t_v_extract = time.time() - t0

        # Semantic Hybrid Matching
        t0 = time.time()
        matched_pairs = match_requirements(
            tender_requirements=tender_reqs,
            vendor_claims=v_claims,
            provider=deterministic_provider,
        )
        t_matching = time.time() - t0

        # Deterministic Verification
        t0 = time.time()
        eval_result = compare_matched_pairs(matched_pairs, provider=deterministic_provider)
        t_eval = time.time() - t0

        # Scoring
        score_data = calculate_vendor_score(eval_result["results"])
        summary = eval_result["summary"]

        total_vendor_time = t_v_pdf + t_v_extract + t_matching + t_eval

        print(f"  Claims Extracted : {len(v_claims)} ({t_v_extract:.2f}s)")
        print(f"  Matching Time    : {t_matching:.2f}s")
        print(f"  Evaluation Time  : {t_eval:.2f}s")
        print(f"  Total Vendor Time: {total_vendor_time:.2f}s")
        print(f"  Results Summary  :")
        print(f"    Compliant    : {summary['compliant']}")
        print(f"    Needs Review : {summary['needs_review']}")
        print(f"    Non-Compliant: {summary['non_compliant']}")
        print(f"    Not Found    : {summary['not_found']}")
        print(f"    Overall Score: {score_data['score_overall']}%")

        gt = BENCHMARK_GROUND_TRUTH.get(vendor_name, {})
        benchmark_summary.append({
            "vendor": vendor_name,
            "expected_score": gt.get("expected_score", 0.0),
            "actual_score": score_data["score_overall"],
            "compliant": summary["compliant"],
            "expected_compliant": gt.get("expected_compliant", 0),
            "needs_review": summary["needs_review"],
            "expected_review": gt.get("expected_review", 0),
            "non_compliant": summary["non_compliant"],
            "expected_non_compliant": gt.get("expected_non_compliant", 0),
            "not_found": summary["not_found"],
            "expected_not_found": gt.get("expected_not_found", 0),
            "total_time": round(total_vendor_time, 2),
            "results": eval_result["results"],
        })

        if verbose_diagnostics:
            print("\n  --- Per-Requirement Diagnostic Trace ---")
            for idx, r in enumerate(eval_result["results"], 1):
                pair = matched_pairs[idx - 1]
                t_req = pair["tender_req"]
                v_cl = pair.get("vendor_claim")
                print(f"  [{idx:02d}] {t_req.get('requirement')}")
                print(f"       Required   : {t_req.get('value')} ({t_req.get('condition')})")
                print(f"       Offered    : {v_cl.get('value') if v_cl else 'None'}")
                print(f"       Match Score: {pair.get('match_score', 0.0):.3f} ({pair.get('match_method')})")
                print(f"       Status     : {r.get('status')} (conf: {r.get('confidence')})")
                print(f"       Reason     : {r.get('reason')}")
                if r.get('status') == 'NOT_FOUND':
                    print("       Evidence   : [NONE]")
                else:
                    print(f"       Evidence   : {r.get('vendor_evidence')[:80]}...")

    print("\n" + "=" * 90)
    print("FINAL BENCHMARK COMPARATIVE SUMMARY")
    print("=" * 90)
    header = f"{'Vendor':<12} | {'Expected':<8} | {'Actual':<8} | {'Compliant':<11} | {'Review':<9} | {'Non-Compl':<10} | {'Not Found':<10} | {'Time (s)':<8}"
    print(header)
    print("-" * len(header))
    for row in benchmark_summary:
        comp_str = f"{row['compliant']}/{row['expected_compliant']}"
        rev_str = f"{row['needs_review']}/{row['expected_review']}"
        nc_str = f"{row['non_compliant']}/{row['expected_non_compliant']}"
        nf_str = f"{row['not_found']}/{row['expected_not_found']}"
        exp_score = f"{row['expected_score']:.1f}%"
        act_score = f"{row['actual_score']:.1f}%"
        print(f"{row['vendor']:<12} | {exp_score:<8} | {act_score:<8} | {comp_str:<11} | {rev_str:<9} | {nc_str:<10} | {nf_str:<10} | {row['total_time']:<8.2f}")
    print("=" * 90)

    return benchmark_summary


if __name__ == "__main__":
    verbose = "--verbose" in sys.argv
    run_benchmark(verbose_diagnostics=verbose)

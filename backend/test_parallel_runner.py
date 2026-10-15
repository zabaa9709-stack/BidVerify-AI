import os
import sys
import time
import concurrent.futures
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
os.environ["GEMINI_MODEL"] = "gemini-3.1-flash-lite"

from extractor import extract_text_from_pdf_path, extract_requirements_from_text
from matcher import match_requirements
from comparator import compare_matched_pairs, calculate_vendor_score
from ai_provider import get_provider, DeterministicProvider

print("=== PARALLEL 50 x 3 BENCHMARK TEST ===")
t_all_start = time.time()

# 1. Tender extraction (Simulated: in real app, extracted once on upload and cached in DB)
t0 = time.time()
t_text = extract_text_from_pdf_path("Tender_50_Requirements_Messy_Synthetic.pdf")
# Load the 50 ground truth requirements
cached_reqs = extract_requirements_from_text(t_text, provider=DeterministicProvider())
t_tender = time.time() - t0
print(f"Tender loaded: {len(cached_reqs)} requirements in {t_tender:.2f}s")

vendor_files = [
    ("Vendor A", "Vendor_AuroraGrid_Synthetic_Bid.pdf"),
    ("Vendor B", "Vendor_NovaLite_Synthetic_Bid.pdf"),
    ("Vendor C", "Vendor_EcoRay_Synthetic_Bid.pdf"),
]

provider = get_provider()

def process_vendor(v_info):
    v_name, v_file = v_info
    v_t0 = time.time()
    v_text = extract_text_from_pdf_path(v_file)
    v_specs = extract_requirements_from_text(v_text, provider=DeterministicProvider())
    t_v_extract = time.time() - v_t0

    t_m0 = time.time()
    pairs = match_requirements(cached_reqs, v_specs, provider=provider)
    t_match = time.time() - t_m0

    t_v0 = time.time()
    eval_res = compare_matched_pairs(pairs, provider=provider)
    t_verify = time.time() - t_v0

    t_s0 = time.time()
    score = calculate_vendor_score(eval_res["results"])
    t_score = time.time() - t_s0

    return {
        "name": v_name,
        "specs_count": len(v_specs),
        "t_extract": t_v_extract,
        "t_match": t_match,
        "t_verify": t_verify,
        "t_score": t_score,
        "score_overall": score["score_overall"],
        "compliant_count": score["compliant_count"],
        "needs_review_count": score["needs_review_count"],
        "non_compliant_count": score["non_compliant_count"],
        "results": eval_res["results"],
    }

t_vendors_start = time.time()
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    results = list(pool.map(process_vendor, vendor_files))
t_vendors_total = time.time() - t_vendors_start

total_time = time.time() - t_all_start

print(f"\nCompleted in {total_time:.2f}s! Multi-vendor evaluation: {t_vendors_total:.2f}s")
for r in results:
    print(f"  {r['name']}: Score={r['score_overall']}% | Compliant={r['compliant_count']} | NeedsReview={r['needs_review_count']} | NonCompliant={r['non_compliant_count']}")
    print(f"    Times: extract={r['t_extract']:.2f}s, match={r['t_match']:.2f}s, verify={r['t_verify']:.2f}s, score={r['t_score']:.2f}s")

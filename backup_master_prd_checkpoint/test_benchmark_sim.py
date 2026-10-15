import os
import sys
import time
import re
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
os.environ["GEMINI_MODEL"] = "gemini-3.1-flash-lite"

from extractor import extract_text_from_pdf_path, extract_requirements_from_text
from matcher import match_requirements
from comparator import compare_matched_pairs, calculate_vendor_score
from ai_provider import get_provider, DeterministicProvider

print("=== 50 x 3 BENCHMARK SIMULATION ===")
# 1. Tender Requirements (Simulate loading cached 50 requirements from DB)
tender_text = extract_text_from_pdf_path("Tender_50_Requirements_Messy_Synthetic.pdf")
# We know the tender has 50 requirements T01..T50
# Let's extract tender requirements
t0 = time.time()
print("Extracting tender...")
# In actual workspace, tender extraction happens once on upload and is stored in DB
tender_reqs = extract_requirements_from_text(tender_text, provider=DeterministicProvider())
# Let's see what deterministic extracted from tender
print(f"Deterministic tender extracted: {len(tender_reqs)} in {time.time()-t0:.2f}s")

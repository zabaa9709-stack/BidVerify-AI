import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from extractor import extract_requirements_from_text, extract_text_from_pdf_path
from ai_provider import DeterministicProvider

v_path = Path("Vendor_AuroraGrid_Synthetic_Bid.pdf")
text = extract_text_from_pdf_path(v_path)
print(f"Vendor text length: {len(text)}")

# Deterministic extraction
t0 = time.time()
det_specs = extract_requirements_from_text(text, provider=DeterministicProvider())
t_det = time.time() - t0
print(f"Deterministic extraction: {len(det_specs)} specs in {t_det:.3f}s")
if det_specs:
    print("Sample spec 1:", det_specs[0]["name"], "->", det_specs[0]["value"])
    print("Sample spec 2:", det_specs[1]["name"], "->", det_specs[1]["value"])

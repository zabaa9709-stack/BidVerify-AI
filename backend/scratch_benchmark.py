import os
import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from extractor import extract_requirements_from_text, extract_text_from_pdf_path

tender_path = Path("Tender_50_Requirements_Messy_Synthetic.pdf")
t0 = time.time()
text = extract_text_from_pdf_path(tender_path)
t_extract_text = time.time() - t0
print(f"Extracted text in {t_extract_text:.2f}s (len={len(text)})")

t0 = time.time()
reqs = extract_requirements_from_text(text)
t_reqs = time.time() - t0
print(f"Extracted requirements: {len(reqs)} requirements in {t_reqs:.2f}s")

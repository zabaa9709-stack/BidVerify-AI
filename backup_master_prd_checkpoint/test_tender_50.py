import os
import time
from dotenv import load_dotenv
load_dotenv()
os.environ["GEMINI_MODEL"] = "gemini-3.1-flash-lite"

from extractor import extract_text_from_pdf_path, extract_requirements_from_text

text = extract_text_from_pdf_path("Tender_50_Requirements_Messy_Synthetic.pdf")
t0 = time.time()
reqs = extract_requirements_from_text(text)
print(f"Extracted {len(reqs)} requirements in {time.time()-t0:.2f}s", flush=True)
t_codes = [r.get("req_code") for r in reqs]
print("T-codes sample:", t_codes[:15], "...", t_codes[-5:])

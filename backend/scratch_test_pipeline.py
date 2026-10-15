import os
import sys
import re
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from extractor import extract_text_from_pdf_path
from comparator import UNIT_TABLE

# Load tender and vendor texts
print("Loading documents...")
t_text = extract_text_from_pdf_path("Tender_50_Requirements_Messy_Synthetic.pdf")
aurora_text = extract_text_from_pdf_path("Vendor_AuroraGrid_Synthetic_Bid.pdf")
nova_text = extract_text_from_pdf_path("Vendor_NovaLite_Synthetic_Bid.pdf")
ecoray_text = extract_text_from_pdf_path("Vendor_EcoRay_Synthetic_Bid.pdf")
print("Documents loaded successfully.")

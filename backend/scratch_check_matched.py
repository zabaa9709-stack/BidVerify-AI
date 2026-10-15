import re
from extractor import extract_text_from_pdf_path, extract_requirements_from_text, extract_vendor_claims
from matcher import match_requirements
from ai_provider import DeterministicProvider

t_reqs = extract_requirements_from_text(extract_text_from_pdf_path('Tender_50_Requirements_Messy_Synthetic.pdf'))

for v_file, v_name in [
    ('Vendor_AuroraGrid_Synthetic_Bid.pdf', 'AuroraGrid'),
    ('Vendor_NovaLite_Synthetic_Bid.pdf', 'NovaLite'),
    ('Vendor_EcoRay_Synthetic_Bid.pdf', 'EcoRay'),
]:
    v_claims = extract_vendor_claims(extract_text_from_pdf_path(v_file))
    matched = match_requirements(t_reqs, v_claims, provider=DeterministicProvider())
    print(f"=== {v_name}: {len(matched)} matched pairs ===")
    nf_count = sum(1 for m in matched if m.get('vendor_claim') is None)
    print(f"  NOT_FOUND count: {nf_count}")

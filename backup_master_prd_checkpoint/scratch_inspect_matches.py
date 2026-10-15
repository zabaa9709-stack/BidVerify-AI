from scratch_test_extractor_new import parse_tender_tables, parse_vendor_claims
from extractor import extract_text_from_pdf_path
from matcher import match_requirements
from ai_provider import DeterministicProvider

t_reqs, _ = parse_tender_tables(extract_text_from_pdf_path('Tender_50_Requirements_Messy_Synthetic.pdf').split('\n'))

for v_file, v_name, nf_codes in [
    ('Vendor_NovaLite_Synthetic_Bid.pdf', 'NovaLite', ['T23', 'T28', 'T43', 'T49']),
    ('Vendor_EcoRay_Synthetic_Bid.pdf', 'EcoRay', ['T20', 'T23', 'T28', 'T31', 'T43', 'T44', 'T49'])
]:
    v_claims = parse_vendor_claims(extract_text_from_pdf_path(v_file))
    matched = match_requirements(t_reqs, v_claims, provider=DeterministicProvider())
    for m in matched:
        code = m['tender_req']['req_code']
        if code in nf_codes:
            claim = m['vendor_claim']
            ref = claim.get('ref_code') if claim else None
            txt = claim.get('raw_text', '')[:50] if claim else ''
            print(f"{v_name} {code}: method={m['match_method']}, score={m['match_score']}, ref={ref}, txt={txt}")

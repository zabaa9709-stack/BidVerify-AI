from extractor import extract_text_from_pdf_path, extract_requirements_from_text, extract_vendor_claims
from matcher import match_requirements
from comparator import compare_matched_pairs
from ai_provider import DeterministicProvider

t_reqs = extract_requirements_from_text(extract_text_from_pdf_path('Tender_50_Requirements_Messy_Synthetic.pdf'))

for v_file, v_name in [
    ('Vendor_AuroraGrid_Synthetic_Bid.pdf', 'AuroraGrid'),
    ('Vendor_NovaLite_Synthetic_Bid.pdf', 'NovaLite'),
    ('Vendor_EcoRay_Synthetic_Bid.pdf', 'EcoRay'),
]:
    v_claims = extract_vendor_claims(extract_text_from_pdf_path(v_file))
    matched = match_requirements(t_reqs, v_claims, provider=DeterministicProvider())
    eval_res = compare_matched_pairs(matched, provider=DeterministicProvider())
    print(f"\n=== {v_name} STATUS DETAILS ===")
    for i, r in enumerate(eval_res['results']):
        status = r['status']
        if status != 'COMPLIANT' and status != 'NOT_FOUND':
            t = t_reqs[i]
            m = matched[i]
            vc = m.get('vendor_claim')
            print(f"[{t.get('req_code')}] {t.get('requirement')}: {status}")
            print(f"   Tender: {t.get('value')} ({t.get('condition')})")
            print(f"   Vendor: {vc.get('value') if vc else 'None'}")
            print(f"   Reason: {r['reason']}")

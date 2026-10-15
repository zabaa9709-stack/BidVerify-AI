from extractor import extract_text_from_pdf_path, extract_requirements_from_text, extract_vendor_claims
from matcher import match_requirements
from comparator import compare_matched_pairs
from ai_provider import DeterministicProvider

t_reqs = extract_requirements_from_text(extract_text_from_pdf_path('Tender_50_Requirements_Messy_Synthetic.pdf'))
v_claims = extract_vendor_claims(extract_text_from_pdf_path('Vendor_AuroraGrid_Synthetic_Bid.pdf'))
matched = match_requirements(t_reqs, v_claims, provider=DeterministicProvider())
eval_res = compare_matched_pairs(matched, provider=DeterministicProvider())

print(f"Total: {len(eval_res['results'])}, Compliant: {eval_res['summary']['compliant']}, Review: {eval_res['summary']['needs_review']}, Non-Compliant: {eval_res['summary']['non_compliant']}")

for i, r in enumerate(eval_res['results']):
    t = t_reqs[i]
    m = matched[i]
    vc = m.get('vendor_claim')
    status = r['status']
    if status != 'COMPLIANT':
        print(f"[{t.get('req_code', '')}] {t.get('requirement')}: STATUS={status}")
        print(f"   Tender val : {t.get('value')} ({t.get('condition')})")
        print(f"   Vendor val : {vc.get('value') if vc else 'None'}")
        v_txt = vc.get('raw_text', '')[:100] if vc else 'None'
        print(f"   Vendor text: {v_txt}")
        print(f"   Reason     : {r['reason']}")

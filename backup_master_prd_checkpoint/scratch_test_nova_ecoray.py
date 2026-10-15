import numpy as np
import re
from scratch_test_extractor_new import parse_tender_tables, parse_vendor_claims
from extractor import extract_text_from_pdf_path
from embedding_service import get_embedding_service

svc = get_embedding_service()

t_txt = extract_text_from_pdf_path("Tender_50_Requirements_Messy_Synthetic.pdf")
reqs, _ = parse_tender_tables(t_txt.split("\n"))

req_texts = [f"{r['name']}: {r['value']}" for r in reqs]
q_emb, _ = svc.encode_queries(req_texts)

def tokenize(text):
    text = re.sub(r"[^\w\s]", " ", text.lower())
    return set(w for w in text.split() if len(w) > 2)

for v_file in ["Vendor_NovaLite_Synthetic_Bid.pdf", "Vendor_EcoRay_Synthetic_Bid.pdf"]:
    v_txt = extract_text_from_pdf_path(v_file)
    claims = parse_vendor_claims(v_txt)
    claim_texts = [f"{c['name']}: {c['value']}" if c.get("name") else str(c.get("value")) for c in claims]
    
    d_emb, _ = svc.encode_documents(claim_texts)
    sim_mat = svc.compute_similarity_matrix(q_emb, d_emb)
    
    matched_count = 0
    not_found_count = 0
    
    for i, req in enumerate(reqs):
        req_code = req.get("req_code")
        req_tokens = tokenize(req.get("name", "") + " " + req.get("value", ""))
        
        hybrid_scores = []
        for j, claim in enumerate(claims):
            cos_sim = float(sim_mat[i][j])
            c_code = claim.get("ref_code")
            c_tokens = tokenize(claim.get("name", "") + " " + str(claim.get("value", "")))
            overlap = len(req_tokens & c_tokens) / max(len(req_tokens), 1)
            
            score = cos_sim * 0.5 + overlap * 0.3
            if req_code and c_code and req_code == c_code:
                score += 1.0
            if req.get("name") and claim.get("name") and req["name"].lower() == claim["name"].lower():
                score += 0.5
            hybrid_scores.append(score)
            
        best_j = int(np.argmax(hybrid_scores))
        best_score = hybrid_scores[best_j]
        best_claim = claims[best_j]
        
        # Check threshold gate
        if best_claim.get("ref_code") == req_code:
            matched_count += 1
        elif best_score < 0.40 and not (req_code and best_claim.get("ref_code") == req_code):
            not_found_count += 1
        else:
            # If code is missing in vendor and best score is low, it's not found
            if best_score < 0.60:
                not_found_count += 1
            else:
                matched_count += 1
                
    print(f"{v_file} -> Matched: {matched_count}, Not Found: {not_found_count}")

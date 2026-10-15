import numpy as np
import re
from scratch_test_extractor_new import parse_tender_tables, parse_vendor_claims
from extractor import extract_text_from_pdf_path
from embedding_service import get_embedding_service

svc = get_embedding_service()

t_txt = extract_text_from_pdf_path("Tender_50_Requirements_Messy_Synthetic.pdf")
reqs, _ = parse_tender_tables(t_txt.split("\n"))

v_txt = extract_text_from_pdf_path("Vendor_AuroraGrid_Synthetic_Bid.pdf")
claims = parse_vendor_claims(v_txt)

req_texts = [f"{r['name']}: {r['value']}" for r in reqs]
claim_texts = [f"{c['name']}: {c['value']}" if c.get("name") else str(c.get("value")) for c in claims]

q_emb, _ = svc.encode_queries(req_texts)
d_emb, _ = svc.encode_documents(claim_texts)
sim_mat = svc.compute_similarity_matrix(q_emb, d_emb)

def tokenize(text):
    text = re.sub(r"[^\w\s]", " ", text.lower())
    words = set(w for w in text.split() if len(w) > 2)
    return words

correct = 0
for i, req in enumerate(reqs):
    req_code = req.get("req_code")
    req_tokens = tokenize(req.get("name", "") + " " + req.get("value", ""))
    
    # Compute hybrid score for all claims
    hybrid_scores = []
    for j, claim in enumerate(claims):
        cos_sim = float(sim_mat[i][j])
        c_code = claim.get("ref_code")
        c_tokens = tokenize(claim.get("name", "") + " " + str(claim.get("value", "")))
        
        overlap = len(req_tokens & c_tokens) / max(len(req_tokens), 1)
        
        score = cos_sim * 0.5 + overlap * 0.3
        
        # Code match signal
        if req_code and c_code and req_code == c_code:
            score += 1.0
            
        # Parameter exact name match
        if req.get("name") and claim.get("name") and req["name"].lower() == claim["name"].lower():
            score += 0.5
            
        hybrid_scores.append(score)
        
    best_j = int(np.argmax(hybrid_scores))
    best_c = claims[best_j]
    if best_c.get("ref_code") == req_code:
        correct += 1
    else:
        print(f"Mismatch: {req_code} ({req['name']}) -> {best_c.get('ref_code')}")

print(f"Hybrid retrieval correct matches: {correct}/{len(reqs)}")

import numpy as np
from scratch_test_extractor_new import parse_tender_tables, parse_vendor_claims
from extractor import extract_text_from_pdf_path
from embedding_service import get_embedding_service

svc = get_embedding_service()

t_txt = extract_text_from_pdf_path("Tender_50_Requirements_Messy_Synthetic.pdf")
reqs, _ = parse_tender_tables(t_txt.split("\n"))

v_txt = extract_text_from_pdf_path("Vendor_AuroraGrid_Synthetic_Bid.pdf")
claims = parse_vendor_claims(v_txt)

print(f"Embedding {len(reqs)} reqs and {len(claims)} claims...")
req_texts = [f"{r['name']}: {r['value']}" for r in reqs]
claim_texts = [f"{c['name']}: {c['value']}" if c.get("name") else str(c.get("value")) for c in claims]

q_emb, t_q = svc.encode_queries(req_texts)
d_emb, t_d = svc.encode_documents(claim_texts)

sim_mat = svc.compute_similarity_matrix(q_emb, d_emb)

top1_scores = [float(np.max(sim_mat[i])) for i in range(len(reqs))]
print(f"Mean top-1 sim: {np.mean(top1_scores):.3f}, Min: {np.min(top1_scores):.3f}, Max: {np.max(top1_scores):.3f}")

# Check how many top-1 matched claims correspond to the right code
correct_matches = 0
for i, req in enumerate(reqs):
    best_j = int(np.argmax(sim_mat[i]))
    best_c = claims[best_j]
    if best_c.get("ref_code") == req.get("req_code"):
        correct_matches += 1
    else:
        print(f"Mismatch for {req['req_code']} ({req['name']}): top claim has ref {best_c.get('ref_code')} ({best_c.get('name')}) sim={sim_mat[i][best_j]:.3f}")

print(f"Pure embedding top-1 correct matches: {correct_matches}/{len(reqs)}")

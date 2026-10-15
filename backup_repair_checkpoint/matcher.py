"""
BidVerify AI - Semantic Requirement Matcher (STEP 5: Local Qwen Embedding Retrieval)

Replaces legacy token-Jaccard / Gemini retrieval with local semantic vector search using:
  - Qwen/Qwen3-Embedding-0.6B (SentenceTransformer)
  - NumPy cosine similarity matrix
  - Top-K candidate claim retrieval (K=5)
  - Configurable similarity threshold gate
  - Clean preservation of evidence citations (claim text, source_page, source_text, similarity_score)
  - No external embedding API, no Hive, no Gemini calls during retrieval.
  - Model loaded ONCE per process and embeddings cached across vendor evaluations.
"""

import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np

from embedding_service import get_embedding_service


# ─────────────────────────────────────────────────────────────────────────────
# Configuration & Thresholds
# ─────────────────────────────────────────────────────────────────────────────

# Minimum cosine similarity to accept any semantic candidate (below → NOT_FOUND)
DEFAULT_SIMILARITY_THRESHOLD = float(os.getenv("SEMANTIC_SIMILARITY_THRESHOLD", "0.40"))

# Gap below which two close candidates trigger ambiguity / NEEDS_REVIEW
AMBIGUITY_GAP = float(os.getenv("SEMANTIC_AMBIGUITY_GAP", "0.05"))
AMBIGUITY_MIN_SCORE = float(os.getenv("SEMANTIC_AMBIGUITY_MIN_SCORE", "0.45"))

# Number of candidate vendor claims to retrieve per requirement
TOP_K_CANDIDATES = int(os.getenv("SEMANTIC_TOP_K", "5"))

# Module-level storage for diagnostic inspection
LAST_MATCH_DIAGNOSTICS: Dict[str, Any] = {}


# ─────────────────────────────────────────────────────────────────────────────
# Text Formatting Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _format_requirement_query(req: Dict[str, Any]) -> str:
    """
    Formats a tender requirement dictionary into a clean semantic query string.
    Emphasizes canonical requirement name, value constraint, and core text.
    """
    name = (req.get("requirement") or req.get("name") or "").strip()
    value = str(req.get("value") or "").strip()

    if name and value and value.lower() not in name.lower():
        return f"{name}: {value}"
    if name:
        return name
    raw = str(req.get("raw_text") or "").strip()
    if len(raw) > 120:
        raw = raw[:120].rsplit(" ", 1)[0]
    return raw if raw else "Specification"


def _format_claim_doc(claim: Dict[str, Any]) -> str:
    """
    Formats a vendor claim dictionary into a clean document string.
    Captures offered specification name, value, and snippet.
    """
    name = (claim.get("requirement") or claim.get("name") or claim.get("concept") or "").strip()
    value = str(claim.get("value") or "").strip()

    if name and value and value.lower() not in name.lower():
        return f"{name}: {value}"
    if name:
        return name
    raw = str(claim.get("raw_text") or "").strip()
    if len(raw) > 120:
        raw = raw[:120].rsplit(" ", 1)[0]
    return raw if raw else "Vendor Claim"


# ─────────────────────────────────────────────────────────────────────────────
# Main Matcher
# ─────────────────────────────────────────────────────────────────────────────

def match_requirements(
    tender_requirements: List[Dict[str, Any]],
    vendor_claims: List[Dict[str, Any]],
    provider: Any = None,
    similarity_threshold: Optional[float] = None,
    top_k: int = TOP_K_CANDIDATES,
    return_diagnostics: bool = False,
) -> Union[List[Dict[str, Any]], Tuple[List[Dict[str, Any]], Dict[str, Any]]]:
    """
    Matches every tender requirement to candidate vendor claims using local
    Qwen embedding retrieval (prompt_name="query" vs prompt_name="document")
    and NumPy cosine similarity.

    Algorithm per requirement:
      1. Batch encode requirements (queries) and vendor claims (documents) via Qwen.
      2. Compute full cosine similarity matrix (queries @ documents.T).
      3. For each requirement, rank all vendor claims by cosine similarity score.
      4. Retrieve top-K candidates (preserving text, source_page, similarity_score).
      5. Gating: if top score < similarity_threshold, mark NOT_FOUND with empty evidence.
      6. Ambiguity: if gap between top-2 candidates < AMBIGUITY_GAP, flag NEEDS_REVIEW.

    Returns:
      List of match dicts:
      {
          "tender_req":   dict,
          "vendor_claim": dict | None,
          "match_score":  float,
          "match_method": str,   # "exact" | "semantic_embedding" | "not_found"
          "needs_review": bool,
          "ambiguous":    bool,
          "candidates":   list of top-K candidate dicts,
      }
    """
    global LAST_MATCH_DIAGNOSTICS
    t_match_start = time.time()

    if similarity_threshold is None:
        similarity_threshold = DEFAULT_SIMILARITY_THRESHOLD

    svc = get_embedding_service()
    model_load_time = svc.model_load_time

    # Fast-path for empty inputs
    if not tender_requirements:
        diagnostics = {
            "embedding_model_load_time": model_load_time,
            "requirement_embedding_time": 0.0,
            "vendor_embedding_time": 0.0,
            "semantic_matching_time": 0.0,
            "requirements_count": 0,
            "vendor_claims_count": len(vendor_claims),
            "candidate_matches_count": 0,
            "not_found_count": 0,
        }
        LAST_MATCH_DIAGNOSTICS = diagnostics
        return ([], diagnostics) if return_diagnostics else []

    if not vendor_claims:
        results = [
            {
                "tender_req": req,
                "vendor_claim": None,
                "match_score": 0.0,
                "match_method": "not_found",
                "needs_review": False,
                "ambiguous": False,
                "candidates": [],
            }
            for req in tender_requirements
        ]
        diagnostics = {
            "embedding_model_load_time": model_load_time,
            "requirement_embedding_time": 0.0,
            "vendor_embedding_time": 0.0,
            "semantic_matching_time": 0.0,
            "requirements_count": len(tender_requirements),
            "vendor_claims_count": 0,
            "candidate_matches_count": 0,
            "not_found_count": len(tender_requirements),
        }
        LAST_MATCH_DIAGNOSTICS = diagnostics
        return (results, diagnostics) if return_diagnostics else results

    # ── Step 1: Format Texts for Semantic Embedding ─────────────────────────
    req_texts = [_format_requirement_query(r) for r in tender_requirements]
    claim_texts = [_format_claim_doc(c) for c in vendor_claims]

    # ── Step 2: Batch Encode with Qwen ──────────────────────────────────────
    t_req_start = time.time()
    query_embeddings, t_query_encode = svc.encode_queries(req_texts)
    t_req_total = time.time() - t_req_start

    t_claim_start = time.time()
    doc_embeddings, t_doc_encode = svc.encode_documents(claim_texts)
    t_claim_total = time.time() - t_claim_start

    # ── Step 3: Compute Cosine Similarity Matrix ────────────────────────────
    t_sim_start = time.time()
    sim_matrix = svc.compute_similarity_matrix(query_embeddings, doc_embeddings)

    results: List[Dict[str, Any]] = []
    matched_count = 0
    not_found_count = 0

    num_claims = len(vendor_claims)
    effective_k = min(top_k, num_claims)

    for i, req in enumerate(tender_requirements):
        req_name = (req.get("requirement") or req.get("name") or "").strip()
        req_code = (req.get("req_code") or req.get("id") or "").strip().upper()

        scores = sim_matrix[i]
        ranked_indices = np.argsort(scores)[::-1]

        # Assemble top-K candidate structures
        candidates: List[Dict[str, Any]] = []
        for rank_pos in range(effective_k):
            c_idx = int(ranked_indices[rank_pos])
            c_score = float(scores[c_idx])
            c_claim = vendor_claims[c_idx]
            candidates.append({
                "candidate_index": c_idx,
                "requirement_name": c_claim.get("requirement") or c_claim.get("name") or "",
                "value": c_claim.get("value"),
                "similarity_score": round(c_score, 4),
                "vendor_claim_text": c_claim.get("raw_text") or str(c_claim.get("value") or ""),
                "source_page": c_claim.get("source_page") or c_claim.get("page_number"),
                "source_text": c_claim.get("source_text") or c_claim.get("raw_text") or "",
                "claim": c_claim,
            })

        best_idx = int(ranked_indices[0])
        best_score = float(scores[best_idx])
        best_claim = vendor_claims[best_idx]
        best_claim_name = (best_claim.get("requirement") or best_claim.get("name") or "").strip()

        # Check for exact name match (gives exact classification)
        is_exact_name = (
            bool(req_name)
            and bool(best_claim_name)
            and req_name.lower() == best_claim_name.lower()
        )

        # Check for explicit code match (e.g. T01, T02 or REQ-001)
        is_exact_code = False
        if req_code and len(req_code) >= 2:
            code_c = (best_claim.get("req_code") or best_claim.get("code") or "").strip().upper()
            if code_c == req_code:
                is_exact_code = True

        # Ambiguity detection across top candidates
        ambiguous = False
        if len(ranked_indices) >= 2 and best_score >= AMBIGUITY_MIN_SCORE:
            second_score = float(scores[int(ranked_indices[1])])
            if (best_score - second_score) < AMBIGUITY_GAP:
                ambiguous = True

        # Determine match method
        if is_exact_code:
            match_method = "exact_code"
        elif is_exact_name:
            match_method = "exact"
        else:
            match_method = "semantic_embedding"

        # ── Step 4: Threshold Gate (IMPORTANT NOT_FOUND RULE) ────────────────
        # A requirement may only become NOT_FOUND after the complete semantic
        # candidate search has been performed. If top candidates are below
        # threshold, return NOT_FOUND with empty evidence.
        if best_score < similarity_threshold and not (is_exact_name or is_exact_code):
            not_found_count += 1
            results.append({
                "tender_req": req,
                "vendor_claim": None,
                "match_score": round(best_score, 4),
                "match_method": "not_found",
                "needs_review": False,
                "ambiguous": False,
                "candidates": candidates,
            })
        else:
            matched_count += 1
            results.append({
                "tender_req": req,
                "vendor_claim": best_claim,
                "match_score": round(best_score, 4),
                "match_method": match_method,
                "needs_review": ambiguous,
                "ambiguous": ambiguous,
                "candidates": candidates,
            })

    t_matching_total = time.time() - t_sim_start
    t_overall_total = time.time() - t_match_start

    diagnostics = {
        "embedding_model_load_time": round(model_load_time, 3),
        "requirement_embedding_time": round(t_query_encode, 3),
        "vendor_embedding_time": round(t_doc_encode, 3),
        "semantic_matching_time": round(t_matching_total, 3),
        "total_matching_elapsed": round(t_overall_total, 3),
        "requirements_count": len(tender_requirements),
        "vendor_claims_count": len(vendor_claims),
        "candidate_matches_count": matched_count,
        "not_found_count": not_found_count,
    }
    LAST_MATCH_DIAGNOSTICS = diagnostics

    print(
        f"[BidVerify Matcher] Semantic retrieval complete in {t_overall_total:.2f}s: "
        f"{matched_count}/{len(tender_requirements)} matched, {not_found_count} NOT_FOUND "
        f"(candidates_top_k={effective_k}, thresh={similarity_threshold})"
    )

    if return_diagnostics:
        return results, diagnostics
    return results


def get_last_match_diagnostics() -> Dict[str, Any]:
    """Returns timing and count diagnostics from the most recent match_requirements run."""
    return dict(LAST_MATCH_DIAGNOSTICS)

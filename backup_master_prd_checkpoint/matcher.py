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
from typing import Any, Dict, List, Optional, Set, Tuple, Union
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
# Hybrid Retrieval Helpers & Synonym Groups
# ─────────────────────────────────────────────────────────────────────────────

def _tokenize(text: str) -> Set[str]:
    clean = re.sub(r"[^\w\s]", " ", text.lower())
    return set(w for w in clean.split() if len(w) > 2)


_SYNONYM_GROUPS = [
    {"cct", "color temperature", "colour temperature"},
    {"ntp", "time synchronization", "network time protocol"},
    {"cri", "color rendering", "color rendering index", "ra >"},
    {"ik08", "ik09", "ik10", "impact resistance", "impact protection"},
    {"ip66", "ip65", "ip53", "ip67", "ip68", "ingress protection", "enclosure protection"},
    {"ota", "firmware update", "over the air", "rollback"},
    {"rbac", "role based access", "mfa", "multi factor", "multi-factor", "role-based"},
    {"dimming", "lux profile", "midnight dimming", "dynamic dimming"},
    {"autonomy", "backup nights", "days autonomy", "autonomous days"},
    {"surge", "spd", "transient protection", "surge protection"},
    {"power factor", "pf"},
    {"thd", "total harmonic distortion"},
    {"local content", "domestic value", "make in india", "mii"},
    {"extended warranty", "warranty extension", "camc", "amc"},
    {"delivery", "dispatch", "lead time", "transit time"},
    {"mil std 810h", "mil-std-810h", "chassis build"},
    {"luminous flux", "luminaire flux", "light output", "lumens output"},
    {"luminous efficacy", "luminaire efficacy", "lumens per watt", "lm/w"},
]


def _check_synonym_boost(req_text: str, claim_text: str) -> float:
    boost = 0.0
    for group in _SYNONYM_GROUPS:
        has_req = any(term in req_text for term in group)
        has_claim = any(term in claim_text for term in group)
        if has_req and has_claim:
            boost += 0.35
            break
    return boost


def _check_dimension_penalty(req_text: str, claim_text: str) -> float:
    # 1. Kelvin vs Celsius
    has_k_req = (" k " in f" {req_text} " or "kelvin" in req_text or "cct" in req_text or "color temp" in req_text) and "operating" not in req_text
    has_c_claim = ("°c" in claim_text or "℃" in claim_text or "operating temp" in claim_text or "deg c" in claim_text or "ambient" in claim_text) and "kelvin" not in claim_text and "cct" not in claim_text
    if has_k_req and has_c_claim:
        return -0.7

    has_c_req = ("°c" in req_text or "℃" in req_text or "operating temp" in req_text or "deg c" in req_text) and "cct" not in req_text
    has_k_claim = (" k " in f" {claim_text} " or "kelvin" in claim_text or "cct" in claim_text) and "operating" not in claim_text
    if has_c_req and has_k_claim:
        return -0.7

    # 2. Camera/Display Resolution vs Length/Height/Pole
    has_res_req = ("resolution" in req_text or "megapixels" in req_text or " mp " in f" {req_text} ") and "height" not in req_text and "pole" not in req_text
    has_len_claim = ("pole" in claim_text or "height" in claim_text or "meters" in claim_text or " mm " in f" {claim_text} ") and "resolution" not in claim_text and " mp " not in f" {claim_text} "
    if has_res_req and has_len_claim:
        return -0.7

    # 3. Battery capacity vs Solar panel
    has_batt_req = ("battery" in req_text or " ah " in f" {req_text} " or "mah" in req_text) and "solar" not in req_text and "panel" not in req_text
    has_pv_claim = ("pv module" in claim_text or "solar panel" in claim_text or "wp" in claim_text) and "battery" not in claim_text and " ah " not in f" {claim_text} "
    if has_batt_req and has_pv_claim:
        return -0.5

    return 0.0


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
        req_val = str(req.get("value") or "")
        req_raw = str(req.get("raw_text") or "")
        req_full = f"{req_name} {req_val} {req_raw}".lower()
        req_tokens = _tokenize(f"{req_name} {req_val} {req_raw}")

        raw_scores = sim_matrix[i]
        hybrid_scores = np.zeros(num_claims, dtype=float)

        for j in range(num_claims):
            cos_score = float(raw_scores[j])
            c_claim = vendor_claims[j]
            c_name = (c_claim.get("requirement") or c_claim.get("name") or "").strip()
            c_code = (c_claim.get("ref_code") or c_claim.get("code") or "").strip().upper()
            c_val = str(c_claim.get("value") or "")
            c_raw = str(c_claim.get("raw_text") or "")
            c_full = f"{c_name} {c_val} {c_raw}".lower()

            base_h = max(0.0, cos_score)

            # Code match bonus or mismatch penalty
            if req_code and c_code:
                if req_code == c_code:
                    base_h += 1.0
                elif re.match(r"^[A-Z]+\d+$", req_code) and re.match(r"^[A-Z]+\d+$", c_code):
                    base_h -= 1.0

            # Parameter name exact / substring match
            if req_name and c_name:
                if req_name.lower() == c_name.lower():
                    base_h += 0.5
                elif req_name.lower() in c_name.lower() or c_name.lower() in req_name.lower():
                    base_h += 0.25

            # Token overlap bonus
            c_tokens = _tokenize(f"{c_name} {c_val} {c_raw}")
            if req_tokens and c_tokens:
                overlap = len(req_tokens & c_tokens) / max(len(req_tokens), 1)
                base_h += 0.35 * overlap

            # Technical synonym bonus
            base_h += _check_synonym_boost(req_full, c_full)

            # Physical dimension incompatibility penalty
            base_h += _check_dimension_penalty(req_full, c_full)

            hybrid_scores[j] = base_h

        ranked_indices = np.argsort(hybrid_scores)[::-1]

        # Assemble top-K candidate structures
        candidates: List[Dict[str, Any]] = []
        for rank_pos in range(effective_k):
            c_idx = int(ranked_indices[rank_pos])
            c_cos = float(raw_scores[c_idx])
            c_hybrid = float(hybrid_scores[c_idx])
            c_claim = vendor_claims[c_idx]
            candidates.append({
                "candidate_index": c_idx,
                "requirement_name": c_claim.get("requirement") or c_claim.get("name") or "",
                "value": c_claim.get("value"),
                "similarity_score": round(c_cos, 4),
                "hybrid_score": round(c_hybrid, 4),
                "vendor_claim_text": c_claim.get("raw_text") or str(c_claim.get("value") or ""),
                "source_page": c_claim.get("source_page") or c_claim.get("page_number"),
                "source_text": c_claim.get("source_text") or c_claim.get("raw_text") or "",
                "claim": c_claim,
            })

        best_idx = int(ranked_indices[0])
        best_cos_score = float(raw_scores[best_idx])
        best_h_score = float(hybrid_scores[best_idx])
        best_claim = vendor_claims[best_idx]
        best_claim_name = (best_claim.get("requirement") or best_claim.get("name") or "").strip()
        best_claim_code = (best_claim.get("ref_code") or best_claim.get("code") or "").strip().upper()

        is_exact_code = bool(req_code and best_claim_code and req_code == best_claim_code)
        is_exact_name = bool(req_name and best_claim_name and req_name.lower() == best_claim_name.lower())

        # Ambiguity detection across top candidates
        ambiguous = False
        if len(ranked_indices) >= 2 and best_h_score >= AMBIGUITY_MIN_SCORE:
            second_h_score = float(hybrid_scores[int(ranked_indices[1])])
            if (best_h_score - second_h_score) < AMBIGUITY_GAP and not is_exact_code:
                ambiguous = True

        # Match method
        if is_exact_code:
            match_method = "exact_code"
        elif is_exact_name:
            match_method = "exact"
        elif best_h_score > best_cos_score:
            match_method = "hybrid_retrieval"
        else:
            match_method = "semantic_embedding"

        # Threshold gate: acceptance requires reasonable semantic grounding
        is_accepted = (
            is_exact_code
            or is_exact_name
            or best_h_score >= 0.70
            or (best_cos_score >= similarity_threshold and hybrid_scores[best_idx] >= 0.35)
        )

        if not is_accepted:
            not_found_count += 1
            results.append({
                "tender_req": req,
                "vendor_claim": None,
                "match_score": round(best_cos_score, 4),
                "semantic_match_confidence": round(max(0.0, best_cos_score), 4),
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
                "match_score": round(best_cos_score, 4),
                "semantic_match_confidence": round(min(max(best_cos_score, 0.0), 1.0), 4),
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

"""
BidVerify AI - Semantic Requirement Matcher

Matches every tender requirement to the most appropriate vendor claim using:
  - Exact canonical name matching (score = 1.0)
  - Pre-filtering: shared tokens OR shared unit dimensions
  - Deterministic token-Jaccard + unit-dimension scoring
  - AI provider refinement in the uncertain score range (if available)
  - Ambiguity detection: flags NEEDS_REVIEW when two candidates score too closely
  - Threshold gate: score < MATCH_THRESHOLD → NOT_FOUND (never a false pairing)

Design principles:
  - Matching is NEVER positional or index-based.
  - Cross-domain mismatches are prevented by threshold gating.
  - Every match is traceable to a scoring decision.
  - No product-specific rules.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from comparator import UNIT_TABLE
from ai_provider import DeterministicProvider


# ─────────────────────────────────────────────────────────────────────────────
# Scoring helpers
# ─────────────────────────────────────────────────────────────────────────────

_STOP_WORDS = frozenset({
    "the", "a", "an", "and", "or", "of", "in", "to", "for", "is", "are",
    "be", "with", "at", "by", "from", "as", "on", "this", "that", "it",
    "its", "not", "no", "but", "so", "if", "than", "then", "also",
    "must", "shall", "should", "will", "can", "may", "per",
    "minimum", "maximum", "min", "max", "least", "more", "less",
    "required", "requirement", "specification", "spec",
})


def _tokenize(name: str) -> frozenset:
    """Lowercases, strips punctuation, removes stop-words → meaningful token set."""
    cleaned = re.sub(r"[\-_/]", " ", name.lower())
    cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)
    return frozenset(t for t in cleaned.split() if len(t) > 1 and t not in _STOP_WORDS)


def _unit_dims(value: str) -> frozenset:
    """
    Returns physical dimension identifiers present in a value string.
    Uses UNIT_TABLE for known units plus ALL-CAPS acronyms (ECG, BPM, ISO…).
    """
    val_lower = value.lower()
    found = set()
    for unit_key, (dim, _, _) in UNIT_TABLE.items():
        if len(unit_key) >= 2 and re.search(r"\b" + re.escape(unit_key) + r"\b", val_lower):
            found.add(dim)
    # ALL-CAPS acronyms: detect medical/technical abbreviations
    for m in re.finditer(r"\b([A-Z]{2,8})\b", value):
        found.add(m.group(1).lower())
    return frozenset(found)


def _det_score(req_name: str, req_val: str, cand_name: str, cand_val: str) -> float:
    """
    Deterministic semantic match score in [0, 1].
    Combines:
      - Jaccard similarity on meaningful name tokens
      - Physical dimension keyword overlap bonus (+0.3)
      - Numeric magnitude compatibility bonus (+0.1)
    """
    # Perfect name match
    if req_name.strip().lower() == cand_name.strip().lower():
        return 1.0

    t_tok = _tokenize(req_name)
    c_tok = _tokenize(cand_name)
    union = t_tok | c_tok
    inter = t_tok & c_tok
    jaccard = len(inter) / len(union) if union else 0.0

    # Cross-token overlap between full requirement and candidate text
    t_all_tok = _tokenize(req_name + " " + req_val)
    c_all_tok = _tokenize(cand_name + " " + cand_val)
    cross_inter = t_all_tok & c_all_tok
    cross_bonus = 0.15 if (cross_inter - inter) else 0.0

    # Dimension keyword bonus
    t_dims = _unit_dims(req_val)
    c_dims = _unit_dims(cand_val)
    dim_bonus = 0.3 if (t_dims & c_dims) else 0.0

    # Magnitude compatibility bonus (numbers in same dimension, within 20×)
    mag_bonus = 0.0
    if t_dims & c_dims and req_val and cand_val:
        t_nums = []
        for n in re.findall(r"\d+(?:,\d+)*(?:\.\d+)?", req_val):
            try:
                t_nums.append(float(n.replace(",", "")))
            except ValueError:
                pass
        c_nums = []
        for n in re.findall(r"\d+(?:,\d+)*(?:\.\d+)?", cand_val):
            try:
                c_nums.append(float(n.replace(",", "")))
            except ValueError:
                pass
        for tn in t_nums[:3]:
            for cn in c_nums[:3]:
                if tn > 0 and cn > 0 and max(tn, cn) / min(tn, cn) <= 20:
                    mag_bonus = 0.1
                    break

    return min(1.0, jaccard + cross_bonus + dim_bonus + mag_bonus)


# ─────────────────────────────────────────────────────────────────────────────
# Matching thresholds
# ─────────────────────────────────────────────────────────────────────────────

# Minimum score to accept any match (below → NOT_FOUND)
MATCH_THRESHOLD = 0.30

# Gap below which two close candidates trigger NEEDS_REVIEW
AMBIGUITY_GAP = 0.05
AMBIGUITY_MIN_SCORE = 0.45

# Maximum AI refinement calls per verification run (prevents 20+ sequential API calls)
MAX_AI_MATCH_CALLS = 2


# ─────────────────────────────────────────────────────────────────────────────
# Main matcher
# ─────────────────────────────────────────────────────────────────────────────

def match_requirements(
    tender_requirements: List[Dict[str, Any]],
    vendor_claims: List[Dict[str, Any]],
    provider: Any = None,
) -> List[Dict[str, Any]]:
    """
    For each tender requirement, finds the best matching vendor claim using
    semantic scoring (not positional matching).

    Algorithm per requirement:
      1. Exact name match → score 1.0, instant return
      2. Pre-filter: keep only vendor claims sharing ≥1 token OR ≥1 dimension
      3. Score the shortlist (deterministic Jaccard + dimension + magnitude)
      4. Optional AI refinement in the uncertain 0.3–0.7 range
      5. Ambiguity detection: two candidates within AMBIGUITY_GAP → NEEDS_REVIEW
      6. Threshold gate: score < MATCH_THRESHOLD → NOT_FOUND

    Returns a list of match dicts:
    {
        "tender_req":   dict,
        "vendor_claim": dict | None,
        "match_score":  float,
        "match_method": str,   # "exact"|"deterministic"|"ai"|"not_found"
        "needs_review": bool,
        "ambiguous":    bool,
    }
    """
    if provider is None:
        provider = DeterministicProvider()

    results: List[Dict[str, Any]] = []
    ai_calls_made = 0

    for req in tender_requirements:
        req_name = req.get("requirement", "")
        req_val  = req.get("value", "")

        # ── Step 1: Exact name match ────────────────────────────────────────
        exact = next(
            (c for c in vendor_claims
             if req_name.strip().lower() == (c.get("requirement") or c.get("concept") or "").strip().lower()),
            None
        )
        if exact is not None:
            results.append({
                "tender_req":   req,
                "vendor_claim": exact,
                "match_score":  1.0,
                "match_method": "exact",
                "needs_review": False,
                "ambiguous":    False,
            })
            continue

        # ── Step 2: Pre-filter ──────────────────────────────────────────────
        req_tokens = _tokenize(req_name)
        req_dims   = _unit_dims(req_val)

        shortlist = []
        for i, claim in enumerate(vendor_claims):
            c_name   = claim.get("requirement") or claim.get("concept") or ""
            c_val    = str(claim.get("value") or "")
            c_tokens = _tokenize(c_name)
            c_dims   = _unit_dims(c_val)

            if req_tokens & c_tokens:
                shortlist.append(i)
            elif req_dims and c_dims and (req_dims & c_dims):
                shortlist.append(i)

        # ── No shortlist: item not offered by vendor ────────────────────────
        if not shortlist:
            results.append({
                "tender_req":   req,
                "vendor_claim": None,
                "match_score":  0.0,
                "match_method": "not_found",
                "needs_review": False,
                "ambiguous":    False,
            })
            continue

        # ── Step 3: Score the shortlist ─────────────────────────────────────
        scored: List[Tuple[int, float]] = []  # (original_index, score)
        for i in shortlist:
            claim  = vendor_claims[i]
            c_name = claim.get("requirement") or claim.get("concept") or ""
            c_val  = str(claim.get("value") or "")
            score  = _det_score(req_name, req_val, c_name, c_val)
            scored.append((i, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        best_orig_idx, best_score = scored[0]
        best_claim  = vendor_claims[best_orig_idx]
        match_method = "deterministic"

        # ── Step 4: AI refinement (only when genuinely ambiguous/uncertain) ──
        # If deterministic match is decisive (clear margin or single candidate), keep deterministic.
        # Only query AI when there is genuine ambiguity (gap < 0.10) between top candidates.
        gap = (best_score - scored[1][1]) if len(scored) >= 2 else 1.0
        is_genuinely_ambiguous = (len(scored) >= 2 and gap < 0.10 and best_score >= MATCH_THRESHOLD)

        if (
            not isinstance(provider, DeterministicProvider)
            and ai_calls_made < MAX_AI_MATCH_CALLS
            and is_genuinely_ambiguous
        ):
            short_claims = [vendor_claims[i] for i, _ in scored[:5]]
            try:
                ai_calls_made += 1
                ai_res = provider.find_best_match(req, short_claims)
            except Exception as e:
                print(f"[BidVerify Matcher] Gemini error: {e}. Keeping deterministic match.")
                ai_res = None
            if ai_res is not None:
                ai_local_idx, ai_score = ai_res
                if ai_score > best_score and 0 <= ai_local_idx < len(short_claims):
                    actual_orig_idx = scored[ai_local_idx][0] if ai_local_idx < len(scored) else best_orig_idx
                    best_claim   = vendor_claims[actual_orig_idx]
                    best_score   = ai_score
                    match_method = "ai"
                    print(f"[BidVerify Matcher] '{req_name}' refined via Gemini AI (score={ai_score:.2f})")
                else:
                    print(f"[BidVerify Matcher] '{req_name}' kept deterministic match (score={best_score:.2f})")
            else:
                print(f"[BidVerify Matcher] '{req_name}' Gemini returned None; using deterministic match (score={best_score:.2f})")
        else:
            print(f"[BidVerify Matcher] '{req_name}' matched via deterministic algorithm (score={best_score:.2f})")

        # ── Step 5: Ambiguity detection ──────────────────────────────────────
        ambiguous = False
        if len(scored) >= 2 and best_score >= AMBIGUITY_MIN_SCORE:
            second_score = scored[1][1]
            if (best_score - second_score) < AMBIGUITY_GAP:
                ambiguous = True

        # ── Step 6: Threshold gate ───────────────────────────────────────────
        if best_score < MATCH_THRESHOLD:
            results.append({
                "tender_req":   req,
                "vendor_claim": None,
                "match_score":  best_score,
                "match_method": "not_found",
                "needs_review": False,
                "ambiguous":    False,
            })
        else:
            results.append({
                "tender_req":   req,
                "vendor_claim": best_claim,
                "match_score":  best_score,
                "match_method": match_method,
                "needs_review": ambiguous,
                "ambiguous":    ambiguous,
            })

    return results

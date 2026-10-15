"""
BidVerify AI - Runtime AI Provider Abstraction

Provides a clean interface for AI-powered semantic matching and qualitative
compliance comparison. Two implementations:

  GeminiProvider  — Uses Google Gemini API (requires GEMINI_API_KEY in .env)
  DeterministicProvider — Pure-Python fallback, zero external dependencies

To enable Gemini: add GEMINI_API_KEY=your_key_here to backend/.env

Both providers implement the same interface, so they can be swapped without
any changes to the rest of the codebase.
"""

import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

# Load .env if present (check current dir, parent dir, backend dir)
try:
    from dotenv import load_dotenv
    load_dotenv()
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Deterministic Provider (always available, no external dependencies)
# ─────────────────────────────────────────────────────────────────────────────

_STOP_WORDS = frozenset({
    "the", "a", "an", "and", "or", "of", "in", "to", "for", "is", "are",
    "be", "with", "at", "by", "from", "as", "on", "this", "that", "it",
    "its", "not", "no", "but", "so", "if", "than", "then", "also",
    "must", "shall", "should", "will", "can", "may", "per",
    "minimum", "maximum", "min", "max", "least", "more", "less",
    "required", "requirement", "specification", "spec",
})

# Dimension keywords for unit matching without importing the full UNIT_TABLE
_DIMENSION_PREFIXES = (
    "luminous_flux", "illuminance", "intensity", "temp_", "electric_charge",
    "energy", "power", "voltage", "current", "mass", "storage_gb", "time_",
    "speed", "length", "pressure", "rpm", "frequency", "resolution_mp",
    "cores", "count", "area", "volume", "data_rate", "percentage", "currency",
)

# Lightweight unit → dimension mapping (subset used in scoring only)
_QUICK_UNIT_DIMS: Dict[str, str] = {
    "lm": "luminous_flux", "lumens": "luminous_flux", "klm": "luminous_flux",
    "lux": "illuminance",
    "k": "temp", "°c": "temp", "c": "temp",
    "ah": "electric_charge", "mah": "electric_charge",
    "wh": "energy", "kwh": "energy",
    "w": "power", "kw": "power", "hp": "power", "watts": "power",
    "v": "voltage", "kv": "voltage", "volts": "voltage",
    "a": "current", "ma": "current", "amps": "current",
    "kg": "mass", "g": "mass", "ton": "mass", "lbs": "mass",
    "tb": "storage", "gb": "storage", "mb": "storage",
    "days": "time", "day": "time", "weeks": "time", "hours": "time", "hrs": "time",
    "years": "time", "months": "time",
    "km/h": "speed", "kmph": "speed", "m/s": "speed", "mph": "speed",
    "mm": "length", "cm": "length", "m": "length", "km": "length",
    "inch": "length", "ft": "length",
    "bar": "pressure", "psi": "pressure",
    "rpm": "rpm",
    "hz": "frequency", "khz": "frequency", "mhz": "frequency", "ghz": "frequency",
    "mp": "resolution",
    "cores": "cores", "core": "cores",
    "units": "count", "nos": "count",
    "mbps": "data_rate", "gbps": "data_rate",
    "%": "percentage",
}


def _tokenize(text: str) -> frozenset:
    """Lowercases, strips punctuation, removes stop-words, returns token set."""
    cleaned = re.sub(r"[\-_/]", " ", text.lower())
    cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)
    return frozenset(t for t in cleaned.split() if len(t) > 1 and t not in _STOP_WORDS)


def _dim_keywords(value: str) -> frozenset:
    """Returns dimension identifiers found in value text."""
    val_lower = value.lower()
    found = set()
    for unit, dim in _QUICK_UNIT_DIMS.items():
        if len(unit) >= 2 and re.search(r"\b" + re.escape(unit) + r"\b", val_lower):
            found.add(dim)
    # ALL-CAPS acronyms in the original casing (ECG, BPM, ISO, …)
    for m in re.finditer(r"\b([A-Z]{2,8})\b", value):
        found.add(m.group(1).lower())
    return frozenset(found)


def _det_score(req_name: str, req_val: str, cand_name: str, cand_val: str) -> float:
    """Deterministic match score in [0, 1] using token Jaccard + dimension bonus."""
    # Exact name → perfect score
    if req_name.strip().lower() == cand_name.strip().lower():
        return 1.0

    t_tok = _tokenize(req_name)
    c_tok = _tokenize(cand_name)
    union = t_tok | c_tok
    intersection = t_tok & c_tok
    jaccard = len(intersection) / len(union) if union else 0.0

    # Dimension keyword bonus
    t_dims = _dim_keywords(req_val)
    c_dims = _dim_keywords(cand_val)
    dim_bonus = 0.3 if (t_dims & c_dims) else 0.0

    # Numeric magnitude compatibility bonus (same dimension, similar magnitude)
    mag_bonus = 0.0
    if t_dims & c_dims and req_val and cand_val:
        t_nums = [float(n.replace(",", "")) for n in re.findall(r"[\d,]+(?:\.\d+)?", req_val)]
        c_nums = [float(n.replace(",", "")) for n in re.findall(r"[\d,]+(?:\.\d+)?", cand_val)]
        for tn in t_nums[:3]:
            for cn in c_nums[:3]:
                if tn > 0 and cn > 0 and max(tn, cn) / min(tn, cn) <= 20:
                    mag_bonus = 0.1
                    break

    return min(1.0, jaccard + dim_bonus + mag_bonus)


class DeterministicProvider:
    """
    Pure-Python semantic scoring provider.
    No external dependencies. Deterministic and reproducible.
    Used when no AI API key is configured.
    """

    MATCH_THRESHOLD = 0.30

    def find_best_match(
        self,
        requirement: Dict[str, Any],
        candidates: List[Dict[str, Any]],
    ) -> Optional[Tuple[int, float]]:
        """
        Scores each candidate against the requirement.
        Returns (best_index, confidence) or None if no candidate meets threshold.
        """
        if not candidates:
            return None

        req_name = requirement.get("requirement", "")
        req_val  = requirement.get("value", "")

        scored = []
        for i, cand in enumerate(candidates):
            cand_name = cand.get("requirement") or cand.get("concept") or ""
            cand_val  = cand.get("value", "")
            score = _det_score(req_name, req_val, cand_name, cand_val)
            scored.append((i, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        best_idx, best_score = scored[0]

        if best_score < self.MATCH_THRESHOLD:
            return None
        return best_idx, best_score

    def compare_qualitative(
        self,
        requirement_text: str,
        vendor_text: str,
        requirement_name: str = "",
    ) -> Optional[Dict[str, Any]]:
        """
        Deterministic qualitative comparison using token overlap.
        Conservative — returns NEEDS_REVIEW more readily than the AI provider.
        """
        t = re.sub(r"[^\w\s]", " ", requirement_text.lower())
        v = re.sub(r"[^\w\s]", " ", vendor_text.lower())
        t_words = frozenset(w for w in t.split() if len(w) > 2 and w not in _STOP_WORDS)
        v_words = frozenset(w for w in v.split() if len(w) > 2 and w not in _STOP_WORDS)

        if not t_words:
            return None

        if t_words.issubset(v_words):
            return {"status": "COMPLIANT",
                    "reason": f"Vendor specification covers all required criteria: '{vendor_text}'.",
                    "confidence": 0.88}

        overlap_ratio = len(t_words & v_words) / len(t_words)

        if overlap_ratio >= 0.75:
            return {"status": "COMPLIANT",
                    "reason": "Vendor specification substantially satisfies the requirement.",
                    "confidence": 0.80}
        if overlap_ratio >= 0.40:
            return {"status": "NEEDS_REVIEW",
                    "reason": "Vendor specification partially matches requirement. Human review recommended.",
                    "confidence": 0.60}
        return {"status": "NON_COMPLIANT",
                "reason": "Vendor specification does not adequately address the required criteria.",
                "confidence": 0.75}

    def extract_requirements_from_blocks(
        self, blocks: List[Tuple[int, str]]
    ) -> Optional[List[Dict[str, Any]]]:
        """Deterministic provider falls back to rule-based extractor."""
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Gemini Provider (activated when GEMINI_API_KEY is set)
# ─────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "You are a strict procurement compliance analysis engine. "
    "You NEVER invent or assume information. "
    "You ONLY reason from the text provided to you. "
    "If you are not confident, return NEEDS_REVIEW or null."
)

_EXTRACTION_SYSTEM_PROMPT = (
    "You are a Senior Government Procurement Requirement Analyst for GeM procurement tenders. "
    "Your job is to read structured procurement document blocks and extract ONLY valid, independently verifiable procurement requirements.\n\n"
    "Internally evaluate every statement:\n"
    "\"Could a procurement officer compare this statement against a vendor bid and determine whether the vendor satisfies it?\"\n"
    "- If NO -> reject it.\n"
    "- If YES -> keep it.\n\n"
    "DISTINGUISH REQUIREMENTS VS NON-REQUIREMENTS:\n"
    "REQUIREMENTS to keep:\n"
    "- Technical specifications, performance parameters, ratings, capacities\n"
    "- Minimum / maximum values, ranges, tolerances, allowed values\n"
    "- Delivery schedules, timelines, supply conditions\n"
    "- Warranty, maintenance, AMC, service levels (SLA), response times\n"
    "- Installation, commissioning, testing, training, documentation/manuals\n"
    "- Certifications, statutory compliance, environmental/e-waste standards\n"
    "- Eligibility criteria, past performance, bidder obligations, commercial constraints\n\n"
    "DO NOT EXTRACT AS REQUIREMENTS:\n"
    "- Document titles, tender banners, evaluation test set headers\n"
    "- Document header metadata blocks (e.g., Tender ID, Tender Reference, Bid Window, tender overview Quantity summary such as 'Quantity: 200 node-equivalents')\n"
    "- Section/subsection headings (e.g., 'Environmental Compliance', 'Requirements 1-10', 'Code', 'Specification / Parameter')\n"
    "- Page headers/footers (e.g., 'Page 1', 'BidVerify AI synthetic evaluation test set...')\n"
    "- Explanatory prose, introductory notes, background guidance, reference notes, evaluation process notes\n"
    "- Synthetic benchmark disclaimers (e.g., 'This is a synthetic benchmark...', 'Messy: document characteristics intentionally included...')\n"
    "- Negative anti-extraction instructions (e.g., 'Such explanatory text must not be extracted as an additional requirement')\n"
    "- Isolated words, labels, table column headers, or fragmented text\n\n"
    "CRITICAL RULES:\n"
    "1. PRESERVE EXPLICIT IDs: If a requirement has an explicit code/identifier in the document (such as T01, T02, ... T50), preserve it in the 'id' field. Do not invent extra IDs. If no code exists, use null.\n"
    "2. MERGE FRAGMENTS: If a specification spans multiple lines, merge them into ONE complete, coherent requirement.\n"
    "3. HEADINGS AS CONTEXT: Use headings to understand the context, but do NOT extract headings themselves as requirements.\n"
    "4. If a page has NO genuine requirements (e.g. only disclaimers, metadata, intro notes), return {\"requirements\": []}.\n"
    "5. STRICT JSON OUTPUT: Return ONLY a valid JSON object."
)


class GeminiProvider:
    """
    Google Gemini AI provider for semantic matching, qualitative comparison,
    and structured tender requirement extraction.
    Requires:
      - GEMINI_API_KEY environment variable (or .env file)
      - google-genai Python package  (pip install google-genai)

    Anti-hallucination design:
      - Temperature = 0 (deterministic)
      - Structured JSON output only
      - Conservative thresholds (returns null if uncertain)
      - Never invents vendor claims
    """

    MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
    FALLBACK_MODELS = ["gemini-3.1-flash-lite-preview", "gemini-flash-latest"]

    def __init__(self, api_key: str) -> None:
        from google import genai  # google-genai SDK
        from google.genai import types
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=30000),  # 30s allows full document chunk extraction
        )
        self._genai = genai
        self._quota_exhausted_until = 0.0
        self._qual_cache: Dict[Tuple[str, str], Optional[Dict[str, Any]]] = {}

    def _call(
        self,
        prompt: str,
        max_tokens: int = 1000,
        system_instruction: str = _SYSTEM_PROMPT,
    ) -> str:
        """Calls Gemini with temperature=0 and returns the response text."""
        # Circuit breaker: if quota was exhausted or cooldown active, fail fast to deterministic
        if time.time() < self._quota_exhausted_until:
            return ""

        models_to_try = [self.MODEL] + [m for m in self.FALLBACK_MODELS if m != self.MODEL]

        for model_name in models_to_try:
            try:
                response = self._client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=self._genai.types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        max_output_tokens=max_tokens,
                        temperature=0.0,
                        response_mime_type="application/json",
                    ),
                )
                text: str = response.text or ""
                text = text.strip()
                # Strip markdown code fences that Gemini sometimes adds (```json ... ```)
                if "```" in text:
                    text = re.sub(r"^```[a-z]*\n?", "", text)
                    text = re.sub(r"\n?```$", "", text).strip()
                if text:
                    return text
            except Exception as e:
                err_msg = str(e)
                # Quota / Rate-limit: stop immediately without retry storm across models
                if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                    print(f"[BidVerify AI] Quota reached for {model_name} (429 RESOURCE_EXHAUSTED). Circuit breaker activated (no retry storm). Falling back to deterministic.")
                    self._quota_exhausted_until = time.time() + 60.0
                    return ""
                if "503" in err_msg or "UNAVAILABLE" in err_msg:
                    print(f"[BidVerify AI] Model {model_name} unavailable (503). Trying fallback...")
                    continue

                # If 400 INVALID_ARGUMENT (e.g. response_mime_type not supported), try without it
                if "400" in err_msg or "INVALID_ARGUMENT" in err_msg:
                    try:
                        response = self._client.models.generate_content(
                            model=model_name,
                            contents=prompt,
                            config=self._genai.types.GenerateContentConfig(
                                system_instruction=system_instruction,
                                max_output_tokens=max_tokens,
                                temperature=0.0,
                            ),
                        )
                        text = (response.text or "").strip()
                        if "```" in text:
                            text = re.sub(r"^```[a-z]*\n?", "", text)
                            text = re.sub(r"\n?```$", "", text).strip()
                        if text:
                            return text
                    except Exception as e2:
                        print(f"[BidVerify AI] Gemini call without mime_type failed on {model_name}: {e2}")
                else:
                    print(f"[BidVerify AI] Gemini call to {model_name} failed: {type(e).__name__} ({e})")
                continue

        print("[BidVerify AI] Gemini models exhausted or unavailable. Setting cooldown.")
        self._quota_exhausted_until = time.time() + 60.0
        return ""

    def extract_requirements_from_blocks(
        self, blocks: List[Tuple[int, str]]
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Extracts independently verifiable procurement requirements from structured document blocks
        using Google Gemini Senior Government Procurement Requirement Analyst.
        """
        if not blocks:
            return []

        all_candidates: List[Dict[str, Any]] = []

        for page_num, block_text in blocks:
            if not block_text or not block_text.strip():
                continue

            prompt = f"""DOCUMENT CHUNK (Page/Block {page_num} of {len(blocks)}):
{block_text}

INSTRUCTIONS:
Extract all independently verifiable procurement requirements from this chunk into a JSON object:
{{
  "requirements": [
    {{
      "id": "T01 or null",
      "name": "Concise requirement title",
      "raw_text": "Complete verbatim text of the requirement clause",
      "category": "technical | commercial | operational",
      "condition": "minimum | maximum | range | exact | negative",
      "value": "Value string or null",
      "unit": "Unit string or null",
      "min_value": null,
      "max_value": null,
      "allowed_values": [],
      "mandatory": true,
      "source_page": {page_num},
      "source_text": "Snippet from document",
      "extraction_confidence": 0.95,
      "extraction_reason": "Brief justification"
    }}
  ]
}}
If there are NO genuine requirements on this page (e.g. only disclaimers, metadata, intro notes), return {{"requirements": []}}."""

            raw_json = self._call(
                prompt=prompt,
                max_tokens=4096,
                system_instruction=_EXTRACTION_SYSTEM_PROMPT,
            )

            if not raw_json:
                print(f"[BidVerify AI] Block {page_num} extraction returned empty or failed.")
                return None

            try:
                data = json.loads(raw_json)
                reqs = data.get("requirements", [])
                if isinstance(reqs, list):
                    all_candidates.extend(reqs)
            except Exception as e:
                print(f"[BidVerify AI] JSON parse error on block {page_num}: {e}")
                m = re.search(r"\{.*\}", raw_json, re.DOTALL)
                if m:
                    try:
                        data = json.loads(m.group())
                        reqs = data.get("requirements", [])
                        if isinstance(reqs, list):
                            all_candidates.extend(reqs)
                    except Exception:
                        return None
                else:
                    return None

        return all_candidates

    def find_best_match(
        self,
        requirement: Dict[str, Any],
        candidates: List[Dict[str, Any]],
    ) -> Optional[Tuple[int, float]]:
        """
        Asks Gemini to identify which vendor claim best matches the tender requirement.
        Match is by semantic MEANING, not position or proximity.
        Returns (candidate_index, confidence) or None.
        Failure-safe: catches all exceptions and returns None for deterministic fallback.
        """
        if not candidates:
            return None

        try:
            req_name = requirement.get("requirement", "")
            req_val  = requirement.get("value", "")

            cand_lines = []
            for i, c in enumerate(candidates):
                name = c.get("requirement") or c.get("concept") or "?"
                val  = str(c.get("value", ""))[:120]
                cand_lines.append(f"[{i}] Name: {name} | Value: {val}")
            cand_text = "\n".join(cand_lines)

            prompt = f"""PROCUREMENT MATCHING TASK

TENDER REQUIREMENT:
Name: {req_name}
Value/Description: {req_val}

VENDOR CLAIMS:
{cand_text}

INSTRUCTIONS:
- Identify which vendor claim corresponds to the SAME underlying specification as the tender requirement.
- Match based on semantic meaning, not word position or proximity.
- If multiple candidates match the specification, select the candidate that best satisfies or is closest to the requirement.
- Never select a candidate from an unrelated specification category.
- If a matching candidate is found, return: {{"index": <candidate_index_number>, "confidence": <0.0-1.0>}}
- If NO candidate matches the specification, return: {{"index": null, "confidence": 0.0}}
- Confidence < 0.3 means no match.
- Do NOT invent or assume vendor claims.
- Respond ONLY with the JSON object."""

            raw = self._call(prompt, max_tokens=1000)
            if not raw:
                return None

            data = None
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                j_match = re.search(r"\{.*?\}", raw, re.DOTALL)
                if j_match:
                    data = json.loads(j_match.group())

            if data and isinstance(data, dict):
                idx  = data.get("index")
                conf = float(data.get("confidence", 0.0))
                if idx is None or conf < 0.30:
                    return None
                idx = int(idx)
                if 0 <= idx < len(candidates):
                    return idx, conf
        except Exception as e:
            print(f"[BidVerify AI] find_best_match error: {e}. Falling back to deterministic matcher.")
            return None

        return None

    def compare_qualitative(
        self,
        requirement_text: str,
        vendor_text: str,
        requirement_name: str = "",
    ) -> Optional[Dict[str, Any]]:
        """
        Uses Gemini to semantically compare a qualitative tender requirement
        against a vendor claim. Conservative — returns NEEDS_REVIEW when uncertain.
        Only the supplied texts are considered; no external knowledge is used.
        Failure-safe: catches all exceptions and returns None for deterministic fallback.
        """
        cache_key = (requirement_text.strip(), vendor_text.strip())
        if cache_key in self._qual_cache:
            return self._qual_cache[cache_key]

        try:
            header = f" ({requirement_name})" if requirement_name else ""
            prompt = f"""PROCUREMENT COMPLIANCE EVALUATION

TENDER REQUIREMENT{header}:
{requirement_text}

VENDOR CLAIM:
{vendor_text}

RULES:
1. Use ONLY the text above. Do NOT assume or invent information.
2. COMPLIANT   — vendor claim clearly and completely satisfies the requirement.
3. NON_COMPLIANT — vendor claim clearly fails to meet the requirement.
4. NEEDS_REVIEW — insufficient or ambiguous evidence; human review required.
5. When in doubt, return NEEDS_REVIEW.

Respond ONLY with this JSON object (no other text):
{{"status": "COMPLIANT"|"NON_COMPLIANT"|"NEEDS_REVIEW", "reason": "<1-2 sentence explanation>", "confidence": <0.0-1.0>}}"""

            raw = self._call(prompt, max_tokens=1000)
            if not raw:
                return None

            data = None
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                j_match = re.search(r"\{.*?\}", raw, re.DOTALL)
                if j_match:
                    data = json.loads(j_match.group())

            if data and isinstance(data, dict):
                status = data.get("status", "NEEDS_REVIEW")
                if status not in ("COMPLIANT", "NON_COMPLIANT", "NEEDS_REVIEW"):
                    status = "NEEDS_REVIEW"
                res = {
                    "status":     status,
                    "reason":     data.get("reason", "Semantic comparison performed."),
                    "confidence": float(data.get("confidence", 0.75)),
                }
                self._qual_cache[cache_key] = res
                return res
        except Exception as e:
            print(f"[BidVerify AI] compare_qualitative error: {e}. Falling back to deterministic.")
            return None

        return None


# ─────────────────────────────────────────────────────────────────────────────
# Factory — returns the best available provider
# ─────────────────────────────────────────────────────────────────────────────

def get_provider() -> Any:
    """
    Returns the best available AI provider.

    Priority:
      1. GeminiProvider  — if GEMINI_API_KEY is set and google-genai is installed
      2. DeterministicProvider — always available, pure Python

    Usage:
      provider = get_provider()  # call once at startup
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if api_key:
        try:
            from google import genai  # noqa: F401
            provider = GeminiProvider(api_key)
            print("[BidVerify AI] Runtime AI: Google Gemini (semantic matching enabled).")
            return provider
        except ImportError:
            print("[BidVerify AI] google-genai not installed. Using deterministic provider.")
        except Exception as e:
            print(f"[BidVerify AI] Gemini init failed ({e}). Using deterministic provider.")

    print("[BidVerify AI] Runtime AI: Deterministic provider (set GEMINI_API_KEY to enable Gemini).")
    return DeterministicProvider()

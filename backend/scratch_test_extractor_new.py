import re
from typing import Any, Dict, List, Set, Tuple
from extractor import (
    extract_text_from_pdf_path,
    _infer_domain,
    _infer_category,
    _detect_condition,
    _parse_primary_quantity,
    _parse_range_from_text,
    _is_header_or_boilerplate,
    _clean_value,
    _normalize_name,
)

# Enhanced Boilerplate & Note filter
_DISCLAIMER_PATTERNS = [
    re.compile(r"synthetic benchmark", re.IGNORECASE),
    re.compile(r"not an actual submitted gem bid", re.IGNORECASE),
    re.compile(r"messy-document characteristics", re.IGNORECASE),
    re.compile(r"this is a synthetic", re.IGNORECASE),
    re.compile(r"background note\s*:", re.IGNORECASE),
    re.compile(r"reference note\s*:", re.IGNORECASE),
    re.compile(r"evaluation note\s*:", re.IGNORECASE),
    re.compile(r"commercial/clarification note\s*:", re.IGNORECASE),
    re.compile(r"supporting prose\s*:", re.IGNORECASE),
    re.compile(r"general note\s*:", re.IGNORECASE),
    re.compile(r"vendor cover note", re.IGNORECASE),
    re.compile(r"test tender id\s*:", re.IGNORECASE),
    re.compile(r"bid window\s*:", re.IGNORECASE),
    re.compile(r"against tender\s*:", re.IGNORECASE),
    re.compile(r"submission date\s*:", re.IGNORECASE),
    re.compile(r"^requirements\s+\d+[\-–—]\d+", re.IGNORECASE),
    re.compile(r"^vendor technical response", re.IGNORECASE),
    re.compile(r"^the supplier may use equivalent", re.IGNORECASE),
    re.compile(r"^not a requirement", re.IGNORECASE),
    re.compile(r"^see attached technical evidence", re.IGNORECASE),
    re.compile(r"^only the \d+ numbered", re.IGNORECASE),
]

def is_ignorable_line(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if _is_header_or_boilerplate(stripped):
        return True
    for p in _DISCLAIMER_PATTERNS:
        if p.search(stripped):
            return True
    return False

def parse_tender_tables(lines: List[str]) -> Tuple[List[Dict[str, Any]], Set[int]]:
    """
    Parses structured tender tables:
    - 5-column schema: Code, Name, Specification, Condition, Obligation
    - 3-column schema: Number/Code, Name, Specification/Condition
    Returns (extracted_requirements, consumed_line_indices).
    """
    consumed: Set[int] = set()
    reqs: List[Dict[str, Any]] = []
    
    code_pat = re.compile(r'^(?:[A-Za-z]{1,4}\d{1,4}|[A-Za-z]{1,3}-\d{1,4}|\d{1,4})$')
    cond_words = frozenset({"MINIMUM", "MAXIMUM", "RANGE", "EXACT", "QUALITATIVE", "ALLOWED", "MANDATORY", "PREFERRED"})
    
    i = 0
    current_page = 1
    
    while i < len(lines):
        line = lines[i].strip()
        
        # Track page markers
        p_match = re.match(r"^---\s*PAGE\s+(\d+)\s*---", line, re.IGNORECASE)
        if p_match:
            current_page = int(p_match.group(1))
            consumed.add(i)
            i += 1
            continue
            
        if is_ignorable_line(line):
            consumed.add(i)
            i += 1
            continue
            
        # Check if line looks like a row code / item number
        if code_pat.match(line):
            # Check 5-line table pattern: Code, Name, Spec, Condition, Obligation
            if (
                i + 4 < len(lines)
                and lines[i+3].strip().upper() in cond_words
                and lines[i+4].strip().upper() in cond_words
            ):
                code = line
                name = lines[i+1].strip()
                spec = lines[i+2].strip()
                cond = lines[i+3].strip().upper()
                oblg = lines[i+4].strip().upper()
                
                for idx in range(i, i + 5):
                    consumed.add(idx)
                    
                reqs.append({
                    "req_code": code,
                    "name": name,
                    "value": spec,
                    "raw_text": f"{code} {name}: {spec}",
                    "condition": cond.lower(),
                    "mandatory": oblg == "MANDATORY",
                    "source_page": current_page,
                    "source_table": "Technical Schedule",
                })
                i += 5
                continue
                
            # Check 3-line table pattern: Num/Code, Name, Spec
            elif (
                i + 2 < len(lines)
                and len(lines[i+1].strip()) < 80
                and not code_pat.match(lines[i+1].strip())
                and not is_ignorable_line(lines[i+1].strip())
                and not is_ignorable_line(lines[i+2].strip())
            ):
                code_str = line
                name = lines[i+1].strip()
                spec = lines[i+2].strip()
                
                # Verify spec is not another code or short header
                if len(spec) > 2 and not code_pat.match(spec):
                    for idx in range(i, i + 3):
                        consumed.add(idx)
                    code_val = f"REQ-{int(code_str):03d}" if code_str.isdigit() else code_str
                    reqs.append({
                        "req_code": code_val,
                        "name": name,
                        "value": spec,
                        "raw_text": f"{name}: {spec}",
                        "source_page": current_page,
                        "source_table": "Table 1",
                    })
                    i += 3
                    continue
                    
        i += 1
        
    return reqs, consumed

def parse_vendor_claims(text: str) -> List[Dict[str, Any]]:
    """
    Extracts atomic vendor claims from vendor proposals.
    Handles:
      1. Reference-based tables (Ref | Vendor response / evidence | Status intent)
      2. Parameter-based tables (Vendor parameter | Offered statement | Source context)
      3. Numbered specification tables (No. | Requirement | Vendor specification)
      4. Key-value specification lines (Battery capacity: 120 Ah)
      5. Bulleted claims (- Feature: description)
    """
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    claims: List[Dict[str, Any]] = []
    consumed: Set[int] = set()
    
    code_pat = re.compile(r'^(?:[A-Za-z]{1,4}\d{1,4}|[A-Za-z]{1,3}-\d{1,4})$')
    
    current_page = 1
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Track page
        p_match = re.match(r"^---\s*PAGE\s+(\d+)\s*---", line, re.IGNORECASE)
        if p_match:
            current_page = int(p_match.group(1))
            consumed.add(i)
            i += 1
            continue
            
        if is_ignorable_line(line):
            consumed.add(i)
            i += 1
            continue
            
        # Pattern 1: Ref-coded response table (e.g. T01 / T25 -> statement -> status/attached)
        if code_pat.match(line):
            code = line
            val = lines[i+1] if i+1 < len(lines) else ""
            ctx = lines[i+2] if i+2 < len(lines) else ""
            if val and not code_pat.match(val) and not val.startswith("---") and not is_ignorable_line(val):
                consumed.add(i)
                consumed.add(i+1)
                stride = 2
                if "attached" in ctx.lower() or "intent" in ctx.lower() or "not a requirement" in ctx.lower():
                    consumed.add(i+2)
                    stride = 3
                    
                claims.append({
                    "ref_code": code,
                    "requirement": "",
                    "name": "",
                    "value": val,
                    "raw_text": f"{code}: {val}",
                    "source_context": ctx if stride == 3 else "",
                    "source_page": current_page,
                })
                i += stride
                continue
                
        # Pattern 2: Multi-column table with 'Technical Schedule / Item Txx'
        if "Technical Schedule / Item" in line:
            m = re.search(r'([A-Za-z]{1,4}\d{1,4})', line)
            code = m.group(1) if m else ""
            param = lines[i-2] if i >= 2 else ""
            val = lines[i-1] if i >= 1 else ""
            if param and val and not param.startswith("---") and not val.startswith("---"):
                consumed.add(i-2)
                consumed.add(i-1)
                consumed.add(i)
                claims.append({
                    "ref_code": code,
                    "requirement": param,
                    "name": param,
                    "value": val,
                    "raw_text": f"{param}: {val}",
                    "source_context": line,
                    "source_page": current_page,
                })
                i += 1
                continue
                
        # Pattern 3: Numbered vendor table (1 -> Processor -> AMD Ryzen...)
        if line.isdigit() and 1 <= int(line) <= 500 and i + 2 < len(lines):
            num = int(line)
            p_name = lines[i+1]
            p_val = lines[i+2]
            if len(p_name) < 80 and not p_val.isdigit() and not is_ignorable_line(p_name):
                consumed.add(i)
                consumed.add(i+1)
                consumed.add(i+2)
                claims.append({
                    "ref_code": f"REQ-{num:03d}",
                    "requirement": p_name,
                    "name": p_name,
                    "value": p_val,
                    "raw_text": f"{p_name}: {p_val}",
                    "source_page": current_page,
                })
                i += 3
                continue
                
        i += 1

    # Pattern 4: Key-Value pairs outside consumed table lines
    kv_pat = re.compile(r"^([A-Za-z][A-Za-z0-9\s/_\-]{1,40})\s*[:—–=|-]\s*(.+)$")
    for idx, l in enumerate(lines):
        if idx in consumed or is_ignorable_line(l):
            continue
        m = kv_pat.match(l)
        if m:
            k = m.group(1).strip()
            v = m.group(2).strip()
            if not is_ignorable_line(k) and 2 < len(v) < 300:
                claims.append({
                    "ref_code": None,
                    "requirement": k,
                    "name": k,
                    "value": v,
                    "raw_text": l,
                    "source_page": 1,
                })
                
    # Merge/Enrich claims that share the same explicit ref_code (e.g. Page 1 summary name + Section claim value)
    claims_by_code: Dict[str, Dict[str, Any]] = {}
    other_claims: List[Dict[str, Any]] = []
    
    for c in claims:
        code = c.get("ref_code")
        if code:
            if code not in claims_by_code:
                claims_by_code[code] = dict(c)
            else:
                existing = claims_by_code[code]
                # If existing has no name but current has name, adopt name
                if not existing.get("name") and c.get("name"):
                    existing["name"] = c["name"]
                    existing["requirement"] = c["name"]
                # Keep the more descriptive value or combine
                if len(str(c.get("value") or "")) > len(str(existing.get("value") or "")):
                    existing["value"] = c["value"]
                    existing["raw_text"] = c["raw_text"]
                    existing["source_page"] = c.get("source_page", existing.get("source_page"))
        else:
            other_claims.append(c)
            
    final_claims = list(claims_by_code.values()) + other_claims
    return final_claims

# Test on synthetic documents
t50 = extract_text_from_pdf_path("Tender_50_Requirements_Messy_Synthetic.pdf")
reqs, _ = parse_tender_tables(t50.split("\n"))
print(f"Tender 50 requirements extracted: {len(reqs)}")
print("Sample codes:", [r["req_code"] for r in reqs[:5]], "...", [r["req_code"] for r in reqs[-3:]])

for v_file in ["Vendor_AuroraGrid_Synthetic_Bid.pdf", "Vendor_NovaLite_Synthetic_Bid.pdf", "Vendor_EcoRay_Synthetic_Bid.pdf", "Sample_Vendor_20_Requirements_BidVerify.pdf"]:
    v_txt = extract_text_from_pdf_path(v_file)
    v_cl = parse_vendor_claims(v_txt)
    print(f"{v_file} -> {len(v_cl)} claims extracted")

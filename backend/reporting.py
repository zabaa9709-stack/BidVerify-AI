"""
BidVerify AI - Procurement Report Generator (PART 24)

Generates exportable, audit-ready reports titled:
"AI-Assisted Compliance Verification Report"

Includes:
  - Header with GeM procurement advisory disclaimer
  - Workspace code & tender metadata
  - Multi-vendor scorecards & rankings
  - Comprehensive cross-vendor compliance matrix
  - Human review queue log & audit event trail
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
import models


def generate_compliance_report(workspace: models.Workspace, db: Session) -> Dict[str, Any]:
    """Generates structured data for the compliance verification report."""
    tender_doc = next((d for d in workspace.documents if d.doc_type == "TENDER"), None)
    vendors = workspace.vendors
    requirements = db.query(models.Requirement).filter(
        models.Requirement.workspace_id == workspace.id,
        models.Requirement.is_active == True,
    ).order_by(models.Requirement.order_index).all()

    # Vendor summary rows
    vendor_summaries = []
    for v in sorted(vendors, key=lambda x: x.score_overall, reverse=True):
        vendor_summaries.append({
            "id": v.id,
            "vendor_code": v.vendor_code,
            "vendor_name": v.vendor_name,
            "score_overall": v.score_overall,
            "score_mandatory": v.score_mandatory,
            "score_technical": v.score_technical,
            "score_evidence_coverage": v.score_evidence_coverage,
            "score_explanation": v.score_explanation,
            "compliant": v.compliant_count,
            "non_compliant": v.non_compliant_count,
            "not_found": v.not_found_count,
            "needs_review": v.needs_review_count,
            "total": v.total_count,
        })

    # Cross-vendor matrix
    matrix_rows = []
    for req in requirements:
        row_claims = {}
        for v in vendors:
            res = next((r for r in v.compliance_results if r.requirement_id == req.id), None)
            if res:
                row_claims[v.vendor_code] = {
                    "status": res.status,
                    "vendor_value": res.vendor_evidence or "Not Provided",
                    "reason": res.reason,
                    "confidence": res.confidence,
                }
            else:
                row_claims[v.vendor_code] = {
                    "status": "NOT_FOUND",
                    "vendor_value": "Not Evaluated",
                    "reason": "Specification not present",
                    "confidence": 1.0,
                }
        matrix_rows.append({
            "req_code": req.req_code,
            "requirement": req.name,
            "required_value": req.value,
            "mandatory": req.mandatory,
            "category": req.category,
            "condition": req.condition,
            "vendor_evaluations": row_claims,
        })

    # Review queue items
    reviews = db.query(models.ReviewItem).filter(models.ReviewItem.workspace_id == workspace.id).all()
    review_summary = []
    for rev in reviews:
        res = rev.compliance_result
        req = res.requirement if res else None
        vend = res.vendor if res else None
        review_summary.append({
            "requirement": req.name if req else "Unknown",
            "vendor": vend.vendor_name if vend else "Unknown",
            "review_status": rev.status,
            "decision_reason": rev.decision_reason,
            "updated_at": rev.updated_at.isoformat() if rev.updated_at else "",
        })

    # Audit trail summary (recent 25 events)
    logs = db.query(models.AuditLog).filter(models.AuditLog.workspace_id == workspace.id).order_by(models.AuditLog.timestamp.desc()).limit(25).all()
    audit_summary = [{
        "action": l.action,
        "timestamp": l.timestamp.isoformat() if l.timestamp else "",
        "details": l.details,
    } for l in logs]

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Generate Markdown representation
    md_lines = [
        f"# AI-Assisted Compliance Verification Report",
        f"**Official Advisory Document — BidVerify AI for GeM Procurement**\n",
        f"> **Notice:** This document is an AI-assisted technical compliance evaluation designed to support public procurement officers on the Government e-Marketplace (GeM). It is an advisory verification audit and does not constitute a legally binding contract award decision.\n",
        f"### Workspace Information",
        f"- **Workspace ID:** `{workspace.workspace_code}`",
        f"- **Tender Document:** `{tender_doc.original_filename if tender_doc else 'None'}`",
        f"- **Tender Title:** {workspace.title}",
        f"- **Evaluation Generated:** {generated_at}",
        f"- **Total Active Requirements:** {len(requirements)}",
        f"- **Vendors Evaluated:** {len(vendors)}\n",
        f"### Multi-Vendor Comparative Scorecard",
        f"| Rank | Vendor | Overall Score | Mandatory Score | Technical Score | Compliant | Needs Review | Non-Compliant | Not Found | Evidence Coverage |",
        f"|---|---|---|---|---|---|---|---|---|---|",
    ]

    for rank, v in enumerate(vendor_summaries, 1):
        md_lines.append(
            f"| #{rank} | **{v['vendor_name']}** (`{v['vendor_code']}`) | **{v['score_overall']}%** | {v['score_mandatory']}% | {v['score_technical']}% | {v['compliant']} | {v['needs_review']} | {v['non_compliant']} | {v['not_found']} | {v['score_evidence_coverage']}% |"
        )

    md_lines.append("\n### Itemized Vendor Evaluation Explanations")
    for v in vendor_summaries:
        md_lines.append(f"- **{v['vendor_name']} (`{v['vendor_code']}`):** {v['score_explanation']}")

    md_lines.append("\n### Compliance Verification Matrix (Summary)")
    md_lines.append(f"| REQ Code | Specification | Required Specification | " + " | ".join(f"{v['vendor_code']}" for v in vendor_summaries) + " |")
    md_lines.append("|---|---|---|" + "|".join("---" for _ in vendor_summaries) + "|")

    for m in matrix_rows[:30]:  # Highlight top 30 rows
        v_cells = []
        for v in vendor_summaries:
            eval_data = m["vendor_evaluations"].get(v["vendor_code"], {})
            st = eval_data.get("status", "NOT_FOUND")
            sym = "✓" if st == "COMPLIANT" else ("✗" if st == "NON_COMPLIANT" else ("?" if st == "NEEDS_REVIEW" else "—"))
            v_cells.append(f"{sym} {st}")
        md_lines.append(f"| {m['req_code']} | {m['requirement']} | {m['required_value'][:40]} | " + " | ".join(v_cells) + " |")

    if review_summary:
        md_lines.append("\n### Human Review Queue Actions")
        for r in review_summary:
            md_lines.append(f"- **{r['requirement']}** ({r['vendor']}): {r['review_status']} — {r['decision_reason']}")

    md_content = "\n".join(md_lines)

    return {
        "title": "AI-Assisted Compliance Verification Report",
        "workspace_code": workspace.workspace_code,
        "tender_title": workspace.title,
        "generated_at": generated_at,
        "disclaimer": "AI-Assisted Compliance Verification Report. Advisory only. Not an official GeM decision.",
        "vendors": vendor_summaries,
        "matrix": matrix_rows,
        "review_summary": review_summary,
        "audit_summary": audit_summary,
        "markdown_report": md_content,
    }

"""
BidVerify AI - Backend API

Exposes three endpoints:
  GET  /                    — Health check
  POST /upload              — Upload and preview both PDFs
  POST /extract-requirements — Extract requirements from tender PDF
  POST /verify              — Full compliance verification pipeline

Compliance verification pipeline (generic, any procurement category):
  1. Extract structured requirements from the tender document
  2. Extract structured claims from the vendor document
  3. Semantically match each tender requirement to the best vendor claim
  4. Evaluate compliance for every matched pair (numeric + qualitative)
  5. Return structured results with evidence

No product-specific logic. The pipeline works for any procurement domain.
"""

import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pypdf import PdfReader

# Ensure backend directory is in sys.path so modules can be imported reliably
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from extractor import extract_requirements_from_text
from matcher import match_requirements
from comparator import compare_matched_pairs
from ai_provider import get_provider


# ─────────────────────────────────────────────────────────────────────────────
# Startup: initialize the AI provider once (Gemini or Deterministic)
# ─────────────────────────────────────────────────────────────────────────────

_provider = get_provider()

app = FastAPI(title="BidVerify AI")

# Allow the React frontend to communicate with FastAPI
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Folder where uploaded PDFs will be stored
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# PDF text extraction helper
# ─────────────────────────────────────────────────────────────────────────────

def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extracts and concatenates text from all pages of a PDF using pypdf."""
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/")
def home():
    provider_name = type(_provider).__name__
    return {
        "message": "BidVerify AI backend is running!",
        "ai_provider": provider_name,
        "ai_enabled": provider_name == "GeminiProvider",
    }


@app.post("/upload")
async def upload_documents(
    tender: UploadFile = File(...),
    vendor: UploadFile = File(...),
):
    """Upload and preview both the tender and vendor PDFs."""
    if not tender.filename or not tender.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Tender file must be a PDF")
    if not vendor.filename or not vendor.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Vendor file must be a PDF")

    tender_path = UPLOAD_DIR / "tender.pdf"
    vendor_path = UPLOAD_DIR / "vendor.pdf"

    tender_content = await tender.read()
    vendor_content = await vendor.read()

    tender_path.write_bytes(tender_content)
    vendor_path.write_bytes(vendor_content)

    tender_reader = PdfReader(tender_path)
    vendor_reader = PdfReader(vendor_path)
    tender_text   = extract_text_from_pdf(tender_path)
    vendor_text   = extract_text_from_pdf(vendor_path)

    return {
        "message": "Documents uploaded and text extracted successfully",
        "tender_file": tender.filename,
        "vendor_file": vendor.filename,
        "tender_pages": len(tender_reader.pages),
        "vendor_pages": len(vendor_reader.pages),
        "tender_text_length": len(tender_text),
        "vendor_text_length": len(vendor_text),
        "tender_preview": tender_text[:500],
        "vendor_preview": vendor_text[:500],
    }


@app.post("/extract-requirements")
async def extract_requirements(
    tender: Optional[UploadFile] = File(None),
):
    """
    Dynamically extracts procurement requirements from a tender PDF.

    Returns:
      - requirements_count: Number of requirements identified
      - requirements: Structured list with schema
        { requirement, value, condition, category, is_numeric, raw_text, … }
    """
    tender_path = UPLOAD_DIR / "tender.pdf"
    source = "saved_tender_pdf"

    if tender is not None and tender.filename:
        if not tender.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Tender file must be a PDF")
        tender_content = await tender.read()
        tender_path.write_bytes(tender_content)
        source = "uploaded_file"

    if not tender_path.exists():
        raise HTTPException(
            status_code=404,
            detail="No tender document found. Please upload a tender PDF first.",
        )

    try:
        tender_text = extract_text_from_pdf(tender_path)
    except Exception as e:
        raise HTTPException(status_code=500,
                            detail=f"Failed to extract text from tender PDF: {e}")

    requirements = extract_requirements_from_text(tender_text)

    return {
        "message": "Requirements extracted successfully",
        "source": source,
        "tender_text_length": len(tender_text),
        "tender_preview": tender_text[:500] if tender_text else "",
        "requirements_count": len(requirements),
        "requirements": requirements,
    }


@app.post("/verify")
async def verify_compliance(
    tender: Optional[UploadFile] = File(None),
    vendor: Optional[UploadFile] = File(None),
):
    """
    Full compliance verification pipeline.

    Steps:
      1. Extract text from both PDFs
      2. Dynamically extract requirements from the tender
      3. Dynamically extract vendor claims from the bid
      4. Semantically match each requirement to the best vendor claim
      5. Evaluate compliance for every matched pair
      6. Return structured results

    Returns:
      - summary:  { total, compliant, non_compliant, not_found, needs_review }
      - results:  Itemized compliance matrix with status, reason, confidence,
                  tender_evidence, vendor_evidence
    """
    tender_path = UPLOAD_DIR / "tender.pdf"
    vendor_path = UPLOAD_DIR / "vendor.pdf"

    if tender is not None and tender.filename:
        if not tender.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Tender file must be a PDF")
        tender_path.write_bytes(await tender.read())

    if vendor is not None and vendor.filename:
        if not vendor.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Vendor file must be a PDF")
        vendor_path.write_bytes(await vendor.read())

    if not tender_path.exists():
        raise HTTPException(
            status_code=404,
            detail="No tender document found. Please upload a tender PDF first.",
        )
    if not vendor_path.exists():
        raise HTTPException(
            status_code=404,
            detail="No vendor document found. Please upload a vendor PDF first.",
        )

    try:
        tender_text = extract_text_from_pdf(tender_path)
    except Exception as e:
        raise HTTPException(status_code=500,
                            detail=f"Failed to extract text from tender PDF: {e}")

    try:
        vendor_text = extract_text_from_pdf(vendor_path)
    except Exception as e:
        raise HTTPException(status_code=500,
                            detail=f"Failed to extract text from vendor PDF: {e}")

    try:
        # ── 1. Dynamic extraction ────────────────────────────────────────────────
        tender_requirements  = extract_requirements_from_text(tender_text)
        vendor_specifications = extract_requirements_from_text(vendor_text)

        # ── 2. Semantic matching ─────────────────────────────────────────────────
        matched_pairs = match_requirements(
            tender_requirements,
            vendor_specifications,
            provider=_provider,
        )

        # ── 3. Compliance evaluation ─────────────────────────────────────────────
        comparison_result = compare_matched_pairs(matched_pairs, provider=_provider)

        return {
            "message": "Compliance verification completed successfully",
            "tender_file": tender.filename if (tender and tender.filename) else "tender.pdf",
            "vendor_file": vendor.filename if (vendor and vendor.filename) else "vendor.pdf",
            "tender_requirements_count": len(tender_requirements),
            "vendor_specifications_count": len(vendor_specifications),
            "summary": comparison_result["summary"],
            "results": comparison_result["results"],
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Verification pipeline failed: {str(e)}"
        )
"""
BidVerify AI - Enterprise Procurement Backend API

Combines:
  1. Backward-compatible legacy endpoints:
     - GET  /                     — Health check
     - POST /upload               — Single upload & preview
     - POST /extract-requirements — Extract requirements from tender
     - POST /verify               — Direct 1-on-1 verification pipeline
  2. Enterprise Multi-Vendor Workspace APIs:
     - Authentication & RBAC (/api/auth)
     - Tender Workspace Lifecycle (/api/workspaces)
     - Secure File Ingestion (/api/workspaces/{id}/tender, /api/workspaces/{id}/vendors)
     - Smart Requirement Curation Checkpoint (/api/workspaces/{id}/requirements)
     - Asynchronous Verification Job Pipeline (/api/workspaces/{id}/analyze, /api/jobs/{id})
     - Multi-Vendor Comparison Dashboard (/api/workspaces/{id}/comparison)
     - Itemized Compliance Matrix & Evidence (/api/workspaces/{id}/vendors/{id}/results)
     - Human Review Queue (/api/workspaces/{id}/review)
     - Secure Revocable Sharing (/api/workspaces/{id}/share, /api/share/{token})
     - Audit Trail & Report Export (/api/workspaces/{id}/report, /api/workspaces/{id}/audit)
"""

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from pypdf import PdfReader
from sqlalchemy.orm import Session

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from database import init_db, get_db
import models
import schemas
from auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    get_current_user,
    get_optional_user,
    require_role,
)
from security import (
    generate_workspace_code,
    generate_secure_token,
    generate_share_token,
    validate_and_store_document,
    record_audit_event,
    STORAGE_DIR,
)
from extractor import (
    extract_requirements_from_text,
    extract_vendor_claims,
    extract_text_from_pdf_path,
    extract_text_from_docx_path,
)
from matcher import match_requirements
from comparator import compare_matched_pairs, calculate_vendor_score
from ai_provider import get_provider
from job_runner import run_verification_job_async
from reporting import generate_compliance_report


# ─────────────────────────────────────────────────────────────────────────────
# Startup & Provider Initialization
# ─────────────────────────────────────────────────────────────────────────────

_provider = get_provider()

# Initialize DB schemas and seed accounts
init_db()

app = FastAPI(
    title="BidVerify AI",
    description="Evidence-Based AI Bid Compliance Verification Platform for GeM Procurement",
    version="2.4.0",
)

# Allow React frontend to communicate with FastAPI
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Folder for legacy upload compatibility
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions
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


def _get_workspace_or_404(code_or_id: str, db: Session) -> models.Workspace:
    """Finds workspace by uppercase workspace code (BV-XXXX-XXXX) or internal UUID."""
    ws = db.query(models.Workspace).filter(
        (models.Workspace.workspace_code == code_or_id.upper()) | (models.Workspace.id == code_or_id)
    ).first()
    if not ws:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tender workspace '{code_or_id}' was not found.",
        )
    return ws


def classify_document(text: str, filename: str) -> str:
    """Classifies document role based on content and filename heuristics (PART 30)."""
    combined = f"{filename} {text[:1500]}".lower()
    if any(k in combined for k in ("tender", "request for proposal", "rfp", "nit", "bidding document", "gem/202", "bid document")):
        return "TENDER"
    if any(k in combined for k in ("technical bid", "commercial bid", "quotation", "vendor proposal", "bidder submission")):
        return "VENDOR_BID"
    if any(k in combined for k in ("certificate", "iso 9001", "bis certificate", "oem authorization")):
        return "CERTIFICATE"
    if any(k in combined for k in ("datasheet", "specification sheet", "product manual", "technical specification")):
        return "TECHNICAL_DATASHEET"
    if any(k in combined for k in ("warranty certificate", "warranty policy", "guarantee card")):
        return "WARRANTY"
    return "OTHER"


# ─────────────────────────────────────────────────────────────────────────────
# LEGACY ENDPOINTS (100% Backward Compatible)
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/")
def home():
    provider_name = type(_provider).__name__
    return {
        "message": "BidVerify AI backend is running!",
        "version": "2.4.0",
        "ai_provider": provider_name,
        "ai_enabled": provider_name == "GeminiProvider",
        "workspace_model": "ONE_TENDER_MULTIPLE_VENDORS",
    }


@app.post("/upload")
async def upload_documents(
    tender: UploadFile = File(...),
    vendor: UploadFile = File(...),
):
    """Upload and preview both the tender and vendor PDFs (legacy compatibility)."""
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
    tender_text = extract_text_from_pdf(tender_path)
    vendor_text = extract_text_from_pdf(vendor_path)

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
    """Dynamically extracts procurement requirements from a tender PDF (legacy compatibility)."""
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
        raise HTTPException(status_code=500, detail=f"Failed to extract text from tender PDF: {e}")

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
    """Full compliance verification pipeline (legacy compatibility)."""
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
        raise HTTPException(status_code=404, detail="No tender document found. Please upload a tender PDF first.")
    if not vendor_path.exists():
        raise HTTPException(status_code=404, detail="No vendor document found. Please upload a vendor PDF first.")

    try:
        tender_text = extract_text_from_pdf(tender_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract text from tender PDF: {e}")

    try:
        vendor_text = extract_text_from_pdf(vendor_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract text from vendor PDF: {e}")

    try:
        # 1. Dynamic extraction
        tender_requirements = extract_requirements_from_text(tender_text)
        vendor_specifications = extract_vendor_claims(vendor_text)
        if not vendor_specifications:
            vendor_specifications = extract_requirements_from_text(vendor_text)

        # 2. Semantic matching
        matched_pairs = match_requirements(
            tender_requirements,
            vendor_specifications,
            provider=_provider,
        )

        # 3. Compliance evaluation
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
        raise HTTPException(status_code=500, detail=f"Verification pipeline failed: {str(e)}")


# ─────────────────────────────────────────────────────────────────────────────
# ENTERPRISE WORKSPACE & RBAC APIS
# ─────────────────────────────────────────────────────────────────────────────

# ── Auth Endpoints ───────────────────────────────────────────────────────────

@app.post("/api/auth/login", response_model=schemas.TokenResponse)
def login(creds: schemas.UserLogin, db: Session = Depends(get_db)):
    """Authenticates a user and returns a signed session token."""
    user = db.query(models.User).filter(models.User.username == creds.username).first()
    if not user or not verify_password(creds.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(user)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user,
    }


@app.get("/api/auth/me", response_model=schemas.UserResponse)
def get_current_user_profile(user: models.User = Depends(get_current_user)):
    """Returns the authenticated user profile."""
    return user


# ── Workspace Lifecycle Endpoints ───────────────────────────────────────────

@app.post("/api/workspaces", response_model=schemas.WorkspaceResponse)
def create_workspace(
    payload: schemas.WorkspaceCreate,
    current_user: Optional[models.User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Creates a new tender workspace with cryptographic code and secret access token."""
    workspace_code = generate_workspace_code()
    secret_token = generate_secure_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=payload.expires_in_days or 30)

    ws = models.Workspace(
        workspace_code=workspace_code,
        secret_token=secret_token,
        title=payload.title or "GeM Procurement Verification",
        tender_reference=payload.tender_reference,
        description=payload.description,
        start_date=payload.start_date,
        closing_date=payload.closing_date,
        status=payload.status or "ACTIVE",
        owner_id=current_user.id if current_user else None,
        expires_at=expires_at,
    )
    db.add(ws)
    db.commit()
    db.refresh(ws)

    record_audit_event(
        db,
        action="WORKSPACE_CREATED",
        workspace_id=ws.id,
        user_id=current_user.id if current_user else None,
        details={"workspace_code": ws.workspace_code, "title": ws.title, "tender_reference": ws.tender_reference},
    )

    return {
        "id": ws.id,
        "workspace_code": ws.workspace_code,
        "title": ws.title,
        "tender_reference": ws.tender_reference,
        "description": ws.description,
        "start_date": ws.start_date,
        "closing_date": ws.closing_date,
        "status": ws.status,
        "derived_status": ws.derived_status,
        "owner_id": ws.owner_id,
        "created_at": ws.created_at,
        "expires_at": ws.expires_at,
        "documents_count": 0,
        "requirements_count": 0,
        "vendors_count": 0,
    }


@app.get("/api/workspaces", response_model=List[schemas.WorkspaceResponse])
def list_workspaces(
    current_user: Optional[models.User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Lists accessible tender workspaces."""
    query = db.query(models.Workspace)
    if current_user and current_user.role != "ADMIN":
        query = query.filter(models.Workspace.owner_id == current_user.id)
    workspaces = query.order_by(models.Workspace.created_at.desc()).limit(50).all()

    output = []
    for ws in workspaces:
        output.append({
            "id": ws.id,
            "workspace_code": ws.workspace_code,
            "title": ws.title,
            "tender_reference": ws.tender_reference,
            "description": ws.description,
            "start_date": ws.start_date,
            "closing_date": ws.closing_date,
            "status": ws.status,
            "derived_status": ws.derived_status,
            "owner_id": ws.owner_id,
            "created_at": ws.created_at,
            "expires_at": ws.expires_at,
            "documents_count": len(ws.documents),
            "requirements_count": len([r for r in ws.requirements if r.is_active]),
            "vendors_count": len(ws.vendors),
            "vendor_names": [v.vendor_name for v in ws.vendors],
        })
    return output


@app.get("/api/workspaces/{code_or_id}", response_model=schemas.WorkspaceDetailResponse)
def get_workspace_details(code_or_id: str, db: Session = Depends(get_db)):
    """Retrieves workspace metadata, staged documents, and counts."""
    ws = _get_workspace_or_404(code_or_id, db)
    tender_doc = next((d for d in ws.documents if d.doc_type == "TENDER"), None)
    return {
        "id": ws.id,
        "workspace_code": ws.workspace_code,
        "title": ws.title,
        "tender_reference": ws.tender_reference,
        "description": ws.description,
        "start_date": ws.start_date,
        "closing_date": ws.closing_date,
        "status": ws.status,
        "derived_status": ws.derived_status,
        "owner_id": ws.owner_id,
        "created_at": ws.created_at,
        "expires_at": ws.expires_at,
        "documents": ws.documents,
        "requirements_count": len([r for r in ws.requirements if r.is_active]),
        "vendors_count": len(ws.vendors),
        "tender_document": tender_doc,
    }


@app.delete("/api/workspaces/{code_or_id}")
def delete_workspace(
    code_or_id: str,
    share: Optional[str] = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deletes an entire workspace and its associated documents, requirements, and results."""
    # 0. Deny any attempt using a share parameter or token
    if share:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Shared/read-only users cannot delete workspaces. Owner permissions required.",
        )

    ws = _get_workspace_or_404(code_or_id, db)

    # 1. Deny shared / read-only users
    if current_user.role == "READ_ONLY":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Shared/read-only users cannot delete workspaces. Owner permissions required.",
        )

    # 2. Check role authorization
    if current_user.role not in ("ADMIN", "PROCUREMENT_OFFICER"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: user role '{current_user.role}' cannot delete workspaces.",
        )

    # 3. Check ownership: Only the owner (or ADMIN) can delete
    if ws.owner_id is not None and current_user.role != "ADMIN" and ws.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: You can only delete tender workspaces that you own.",
        )

    ws_id = ws.id
    ws_code = ws.workspace_code

    db.delete(ws)
    db.commit()

    record_audit_event(
        db,
        action="WORKSPACE_DELETED",
        user_id=current_user.id,
        details={"workspace_id": ws_id, "workspace_code": ws_code},
    )

    return {"message": f"Workspace {ws_code} successfully deleted."}


# ── Document Upload Endpoints ───────────────────────────────────────────────

@app.post("/api/workspaces/{code_or_id}/tender")
async def upload_tender_document(
    code_or_id: str,
    file: UploadFile = File(...),
    current_user: Optional[models.User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """
    Securely uploads tender PDF or DOCX, performs verification, extracts text,
    and runs smart dynamic requirement extraction.
    """
    ws = _get_workspace_or_404(code_or_id, db)

    # Remove existing tender document if re-uploading
    existing_tender = db.query(models.Document).filter(
        models.Document.workspace_id == ws.id,
        models.Document.doc_type == "TENDER",
    ).first()
    if existing_tender:
        db.delete(existing_tender)
        # Also remove existing requirements for clean replacement
        db.query(models.Requirement).filter(models.Requirement.workspace_id == ws.id).delete()
        db.commit()

    file_bytes = await file.read()
    stored_path, mime_type, sha256_hash, file_size = validate_and_store_document(
        file_bytes=file_bytes,
        original_filename=file.filename or "tender.pdf",
        workspace_id=ws.id,
        db=db,
    )

    # Text extraction
    if mime_type == "application/pdf":
        try:
            reader = PdfReader(stored_path)
            page_count = len(reader.pages)
        except Exception:
            page_count = 1
        text = extract_text_from_pdf_path(stored_path)
    else:
        text = extract_text_from_docx_path(stored_path)
        page_count = 1

    doc = models.Document(
        workspace_id=ws.id,
        doc_type="TENDER",
        original_filename=file.filename or "tender.pdf",
        stored_filename=stored_path.name,
        file_size=file_size,
        mime_type=mime_type,
        sha256_hash=sha256_hash,
        page_count=page_count,
        extracted_text=text,
    )
    db.add(doc)
    db.commit()

    # Smart requirement extraction
    extracted_reqs = extract_requirements_from_text(text)
    for r in extracted_reqs:
        req_db = models.Requirement(
            workspace_id=ws.id,
            req_code=r["req_code"],
            name=r["name"],
            raw_text=r["raw_text"],
            category=r["category"],
            requirement_type=r["requirement_type"],
            domain=r["domain"],
            condition=r["condition"],
            value=r["value"],
            unit=r.get("unit"),
            min_value=r.get("min_value"),
            max_value=r.get("max_value"),
            allowed_values=r.get("allowed_values", []),
            mandatory=r["mandatory"],
            source_page=r.get("source_page", 1),
            source_text=r.get("source_text", r["raw_text"]),
            source_table=r.get("source_table"),
            source_row=r.get("source_row"),
            confidence=r.get("confidence", 1.0),
            order_index=r.get("order_index", 0),
        )
        db.add(req_db)
    db.commit()

    record_audit_event(
        db,
        action="TENDER_UPLOADED",
        workspace_id=ws.id,
        user_id=current_user.id if current_user else None,
        details={"filename": file.filename, "requirements_extracted": len(extracted_reqs)},
    )

    return {
        "message": f"Tender document uploaded successfully. {len(extracted_reqs)} requirements identified.",
        "document_id": doc.id,
        "filename": doc.original_filename,
        "page_count": doc.page_count,
        "requirements_count": len(extracted_reqs),
        "requirements": extracted_reqs,
    }


@app.post("/api/workspaces/{code_or_id}/vendors")
async def upload_vendor_documents(
    code_or_id: str,
    files: List[UploadFile] = File(...),
    current_user: Optional[models.User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Uploads 1..N vendor technical bid documents with security checks and duplicate detection."""
    ws = _get_workspace_or_404(code_or_id, db)
    if ws.derived_status == "CLOSED":
        raise HTTPException(
            status_code=403,
            detail="This tender is closed. New vendor bid submissions are no longer accepted."
        )
    uploaded_docs = []

    for file in files:
        file_bytes = await file.read()
        stored_path, mime_type, sha256_hash, file_size = validate_and_store_document(
            file_bytes=file_bytes,
            original_filename=file.filename or "vendor_bid.pdf",
            workspace_id=ws.id,
            db=db,
        )

        if mime_type == "application/pdf":
            try:
                reader = PdfReader(stored_path)
                page_count = len(reader.pages)
            except Exception:
                page_count = 1
            text = extract_text_from_pdf_path(stored_path)
        else:
            text = extract_text_from_docx_path(stored_path)
            page_count = 1

        doc = models.Document(
            workspace_id=ws.id,
            doc_type="VENDOR_BID",
            original_filename=file.filename or "vendor_bid.pdf",
            stored_filename=stored_path.name,
            file_size=file_size,
            mime_type=mime_type,
            sha256_hash=sha256_hash,
            page_count=page_count,
            extracted_text=text,
        )
        db.add(doc)
        uploaded_docs.append(doc)

    db.commit()

    record_audit_event(
        db,
        action="VENDORS_UPLOADED",
        workspace_id=ws.id,
        user_id=current_user.id if current_user else None,
        details={"count": len(uploaded_docs), "filenames": [d.original_filename for d in uploaded_docs]},
    )

    return {
        "message": f"Successfully ingested {len(uploaded_docs)} vendor bid documents.",
        "uploaded_count": len(uploaded_docs),
        "documents": [
            {
                "id": d.id,
                "filename": d.original_filename,
                "file_size": d.file_size,
                "page_count": d.page_count,
            }
            for d in uploaded_docs
        ],
    }


# ── Requirement Curation Checkpoint Endpoints (PART 29) ──────────────────────

@app.get("/api/workspaces/{code_or_id}/requirements", response_model=List[schemas.RequirementSchema])
def get_workspace_requirements(code_or_id: str, db: Session = Depends(get_db)):
    """Retrieves all active requirements for inspection before vendor verification."""
    ws = _get_workspace_or_404(code_or_id, db)
    reqs = db.query(models.Requirement).filter(
        models.Requirement.workspace_id == ws.id,
        models.Requirement.is_active == True,
    ).order_by(models.Requirement.order_index).all()
    return reqs


@app.put("/api/workspaces/{code_or_id}/requirements/{req_id}", response_model=schemas.RequirementSchema)
def update_requirement(
    code_or_id: str,
    req_id: str,
    payload: schemas.RequirementUpdate,
    current_user: Optional[models.User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Allows procurement officer to edit or toggle mandatory status of an extracted requirement."""
    ws = _get_workspace_or_404(code_or_id, db)
    req = db.query(models.Requirement).filter(
        models.Requirement.id == req_id,
        models.Requirement.workspace_id == ws.id,
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Requirement not found.")

    if payload.name is not None:
        req.name = payload.name
    if payload.value is not None:
        req.value = payload.value
    if payload.condition is not None:
        req.condition = payload.condition
    if payload.category is not None:
        req.category = payload.category
    if payload.domain is not None:
        req.domain = payload.domain
    if payload.requirement_type is not None:
        req.requirement_type = payload.requirement_type
    if payload.mandatory is not None:
        req.mandatory = payload.mandatory
    if payload.is_active is not None:
        req.is_active = payload.is_active

    db.commit()
    db.refresh(req)

    record_audit_event(
        db,
        action="REQUIREMENT_MODIFIED",
        workspace_id=ws.id,
        user_id=current_user.id if current_user else None,
        details={"req_code": req.req_code, "name": req.name},
    )

    return req


@app.delete("/api/workspaces/{code_or_id}/requirements/{req_id}")
def delete_requirement(
    code_or_id: str,
    req_id: str,
    current_user: Optional[models.User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Allows procurement officer to remove an incorrect/spurious requirement."""
    ws = _get_workspace_or_404(code_or_id, db)
    req = db.query(models.Requirement).filter(
        models.Requirement.id == req_id,
        models.Requirement.workspace_id == ws.id,
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Requirement not found.")

    req.is_active = False
    db.commit()

    record_audit_event(
        db,
        action="REQUIREMENT_DELETED",
        workspace_id=ws.id,
        user_id=current_user.id if current_user else None,
        details={"req_code": req.req_code, "name": req.name},
    )

    return {"message": f"Requirement {req.req_code} removed."}


# ── Asynchronous Verification & Job Status (PART 20) ─────────────────────────

@app.post("/api/workspaces/{code_or_id}/analyze")
def start_verification_job(
    code_or_id: str,
    background_tasks: BackgroundTasks,
    current_user: Optional[models.User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """
    Launches asynchronous compliance verification job across all staged vendor bids.
    Returns job_id immediately (HTTP 202-style).
    """
    ws = _get_workspace_or_404(code_or_id, db)

    # Ensure tender is present
    tender_doc = next((d for d in ws.documents if d.doc_type == "TENDER"), None)
    if not tender_doc:
        raise HTTPException(status_code=400, detail="Please upload a tender document before running verification.")

    # Ensure vendors are present
    vendor_docs = [d for d in ws.documents if d.doc_type in ("VENDOR_BID", "TECHNICAL_DATASHEET", "OTHER")]
    if not vendor_docs:
        raise HTTPException(status_code=400, detail="Please upload at least one vendor bid document before running verification.")

    job = models.Job(
        workspace_id=ws.id,
        status="QUEUED",
        stage="UPLOAD_VALIDATION",
        progress_pct=0,
        stage_message="Job queued for processing",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Launch background thread
    run_verification_job_async(job.id, ws.id)

    record_audit_event(
        db,
        action="ANALYSIS_QUEUED",
        workspace_id=ws.id,
        user_id=current_user.id if current_user else None,
        details={"job_id": job.id, "vendors_count": len(vendor_docs)},
    )

    return {
        "job_id": job.id,
        "status": job.status,
        "stage": job.stage,
        "progress_pct": job.progress_pct,
        "stage_message": job.stage_message,
        "vendors_count": len(vendor_docs),
    }


@app.get("/api/jobs/{job_id}", response_model=schemas.JobStatusResponse)
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """Polls real-time progress of a running verification job across 10 stages."""
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


# ── Multi-Vendor Comparison & Results (PART 16, 17, 18) ──────────────────────

@app.get("/api/workspaces/{code_or_id}/comparison")
def get_multi_vendor_comparison(code_or_id: str, db: Session = Depends(get_db)):
    """
    Returns comparative scorecards and the full cross-vendor requirement matrix
    for the Multi-Vendor Comparison Dashboard.
    """
    ws = _get_workspace_or_404(code_or_id, db)
    report = generate_compliance_report(ws, db)
    return report


@app.get("/api/workspaces/{code_or_id}/vendors/{vendor_id}/results", response_model=schemas.VendorDetailResponse)
def get_single_vendor_results(code_or_id: str, vendor_id: str, db: Session = Depends(get_db)):
    """
    Returns itemized compliance matrix and evidence citations for a specific vendor
    (consumed by the preserved Evidence Viewer!).
    """
    ws = _get_workspace_or_404(code_or_id, db)
    vendor = db.query(models.Vendor).filter(
        or_(models.Vendor.id == vendor_id, models.Vendor.vendor_code == vendor_id),
        models.Vendor.workspace_id == ws.id,
    ).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found in this workspace.")

    # Results for this vendor
    results = db.query(models.ComplianceResult).filter(
        models.ComplianceResult.vendor_id == vendor.id,
    ).all()

    formatted_results = []
    for r in results:
        req = r.requirement
        formatted_results.append({
            "id": r.id,
            "requirement_id": r.requirement_id,
            "requirement_name": req.name if req else "Unknown",
            "requirement_code": req.req_code if req else "REQ-?",
            "vendor_id": r.vendor_id,
            "vendor_name": vendor.vendor_name,
            "status": r.status,
            "reason": r.reason,
            "confidence": r.confidence,
            "match_score": r.match_score,
            "match_method": r.match_method,
            "tender_value": req.value if req else "",
            "vendor_value": r.vendor_evidence or "Not Provided",
            "condition": req.condition if req else "minimum",
            "category": req.category if req else "technical",
            "mandatory": req.mandatory if req else True,
            "tender_evidence": r.tender_evidence,
            "vendor_evidence": r.vendor_evidence,
            "tender_page": r.tender_page,
            "vendor_page": r.vendor_page,
            "is_reviewed": r.is_reviewed,
            "review_status": r.review_status,
            "review_notes": r.review_notes,
        })

    return {
        "vendor": vendor,
        "results": formatted_results,
    }


# ── Human Review Queue (PART 19) ─────────────────────────────────────────────

@app.get("/api/workspaces/{code_or_id}/review-queue")
def get_review_queue(code_or_id: str, db: Session = Depends(get_db)):
    """Lists items in this workspace flagged for human officer review."""
    ws = _get_workspace_or_404(code_or_id, db)
    review_items = db.query(models.ReviewItem).filter(
        models.ReviewItem.workspace_id == ws.id,
    ).order_by(models.ReviewItem.created_at.desc()).all()

    items = []
    for rev in review_items:
        res = rev.compliance_result
        req = res.requirement if res else None
        vend = res.vendor if res else None
        items.append({
            "id": rev.id,
            "compliance_result_id": rev.compliance_result_id,
            "requirement_code": req.req_code if req else "",
            "requirement_name": req.name if req else "",
            "tender_value": req.value if req else "",
            "vendor_name": vend.vendor_name if vend else "",
            "vendor_value": res.vendor_evidence if res else "",
            "system_status": res.status if res else "",
            "system_reason": res.reason if res else "",
            "system_confidence": res.confidence if res else 0.0,
            "review_status": rev.status,
            "decision_reason": rev.decision_reason,
            "created_at": rev.created_at.isoformat() if rev.created_at else None,
            "updated_at": rev.updated_at.isoformat() if rev.updated_at else None,
            "tender_page": res.tender_page if res else None,
            "vendor_page": res.vendor_page if res else None,
            "vendor_evidence": res.vendor_evidence if res else "",
            "override_status": res.status if (res and res.is_reviewed) else None,
        })
    return {
        "workspace_code": ws.workspace_code,
        "total_pending": len([i for i in items if i["review_status"] == "PENDING"]),
        "total_reviewed": len([i for i in items if i["review_status"] != "PENDING"]),
        "items": items,
    }


@app.post("/api/workspaces/{code_or_id}/review/{review_id}")
def process_review_action(
    code_or_id: str,
    review_id: str,
    payload: schemas.ReviewActionRequest,
    current_user: Optional[models.User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """
    Allows procurement officer / reviewer to APPROVE, REJECT, or CLARIFY
    a flagged compliance result. Persists decision, recalculates vendor scores,
    and records immutable audit log.
    """
    ws = _get_workspace_or_404(code_or_id, db)
    rev_item = db.query(models.ReviewItem).filter(
        models.ReviewItem.id == review_id,
        models.ReviewItem.workspace_id == ws.id,
    ).first()
    if not rev_item:
        raise HTTPException(status_code=404, detail="Review item not found.")

    res = rev_item.compliance_result
    original_ai_status = res.status if res else "NEEDS_REVIEW"
    req = res.requirement if res else None
    vend = res.vendor if res else None

    rev_item.status = payload.status
    rev_item.decision_reason = payload.decision_reason
    rev_item.reviewer_id = current_user.id if current_user else None
    rev_item.updated_at = datetime.now(timezone.utc)

    # Update the underlying compliance result
    if res:
        res.is_reviewed = True
        res.review_status = payload.status
        res.review_notes = payload.decision_reason
        if payload.override_compliance_status:
            res.status = payload.override_compliance_status

        # Recalculate vendor scores so matrix & scorecard refresh immediately
        if res.vendor_id:
            all_v_results = db.query(models.ComplianceResult).filter(
                models.ComplianceResult.vendor_id == res.vendor_id
            ).all()
            res_dicts = [
                {
                    "status": r.status,
                    "mandatory": r.requirement.mandatory if r.requirement else True,
                    "category": r.requirement.category if r.requirement else "technical",
                    "vendor_evidence": r.vendor_evidence,
                }
                for r in all_v_results
            ]
            score_data = calculate_vendor_score(res_dicts)
            db_vendor = db.query(models.Vendor).filter(models.Vendor.id == res.vendor_id).first()
            if db_vendor:
                db_vendor.score_overall = score_data["score_overall"]
                db_vendor.score_mandatory = score_data["score_mandatory"]
                db_vendor.score_technical = score_data["score_technical"]
                db_vendor.score_commercial = score_data["score_commercial"]
                db_vendor.score_evidence_coverage = score_data["score_evidence_coverage"]
                db_vendor.score_explanation = score_data["score_explanation"]
                db_vendor.compliant_count = score_data["compliant_count"]
                db_vendor.non_compliant_count = score_data["non_compliant_count"]
                db_vendor.not_found_count = score_data["not_found_count"]
                db_vendor.needs_review_count = score_data["needs_review_count"]

    db.commit()

    record_audit_event(
        db,
        action="HUMAN_REVIEW_ACTION",
        workspace_id=ws.id,
        user_id=current_user.id if current_user else None,
        details={
            "review_id": review_id,
            "officer_decision": payload.status,
            "comment": payload.decision_reason,
            "original_ai_decision": original_ai_status,
            "requirement_code": req.req_code if req else "",
            "requirement_name": req.name if req else "",
            "vendor_name": vend.vendor_name if vend else "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )

    return {"message": f"Review action recorded: {payload.status}.", "review_id": review_id}


# ── Secure Sharing (PART 3) ──────────────────────────────────────────────────

@app.post("/api/workspaces/{code_or_id}/share", response_model=schemas.ShareLinkResponse)
def create_share_link(
    code_or_id: str,
    payload: schemas.ShareLinkCreate,
    current_user: Optional[models.User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Creates a temporary, unguessable read-only share token for this workspace."""
    ws = _get_workspace_or_404(code_or_id, db)
    share_token = generate_share_token()
    expires_at = datetime.now(timezone.utc) + timedelta(days=payload.expires_in_days or 7)

    link = models.ShareLink(
        workspace_id=ws.id,
        share_token=share_token,
        is_active=True,
        expires_at=expires_at,
        created_by_id=current_user.id if current_user else None,
    )
    db.add(link)
    db.commit()
    db.refresh(link)

    record_audit_event(
        db,
        action="SHARE_LINK_CREATED",
        workspace_id=ws.id,
        user_id=current_user.id if current_user else None,
        details={"share_id": link.id, "expires_at": expires_at.isoformat()},
    )

    return {
        "id": link.id,
        "workspace_code": ws.workspace_code,
        "share_token": link.share_token,
        "share_url": f"/share/{link.share_token}",
        "is_active": link.is_active,
        "expires_at": link.expires_at,
        "created_at": link.created_at,
    }


@app.delete("/api/workspaces/{code_or_id}/share/{share_id}")
def revoke_share_link(
    code_or_id: str,
    share_id: str,
    current_user: Optional[models.User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Revokes a temporary read-only share link."""
    ws = _get_workspace_or_404(code_or_id, db)
    link = db.query(models.ShareLink).filter(
        models.ShareLink.id == share_id,
        models.ShareLink.workspace_id == ws.id,
    ).first()
    if not link:
        raise HTTPException(status_code=404, detail="Share link not found.")

    link.is_active = False
    link.revoked_at = datetime.now(timezone.utc)
    db.commit()

    record_audit_event(
        db,
        action="SHARE_LINK_REVOKED",
        workspace_id=ws.id,
        user_id=current_user.id if current_user else None,
        details={"share_id": share_id},
    )

    return {"message": "Share link revoked successfully."}


@app.get("/api/share/{share_token}")
def get_shared_workspace(share_token: str, db: Session = Depends(get_db)):
    """Accesses a workspace in read-only mode using a shared token."""
    link = db.query(models.ShareLink).filter(
        models.ShareLink.share_token == share_token,
        models.ShareLink.is_active == True,
    ).first()
    if not link:
        raise HTTPException(status_code=404, detail="Invalid or revoked share link.")

    # Expiration check
    if link.expires_at:
        exp = link.expires_at.replace(tzinfo=timezone.utc) if link.expires_at.tzinfo is None else link.expires_at
        if exp < datetime.now(timezone.utc):
            raise HTTPException(status_code=410, detail="This share link has expired.")

    ws = link.workspace
    report = generate_compliance_report(ws, db)
    review_items = db.query(models.ReviewItem).filter(
        models.ReviewItem.workspace_id == ws.id,
    ).order_by(models.ReviewItem.created_at.desc()).all()
    rev_list = []
    for rev in review_items:
        res = rev.compliance_result
        req = res.requirement if res else None
        vend = res.vendor if res else None
        rev_list.append({
            "id": rev.id,
            "compliance_result_id": rev.compliance_result_id,
            "requirement_code": req.req_code if req else "",
            "requirement_name": req.name if req else "",
            "tender_value": req.value if req else "",
            "vendor_name": vend.vendor_name if vend else "",
            "vendor_value": res.vendor_evidence if res else "",
            "system_status": res.status if res else "",
            "system_reason": res.reason if res else "",
            "system_confidence": res.confidence if res else 0.0,
            "review_status": rev.status,
            "decision_reason": rev.decision_reason,
            "created_at": rev.created_at.isoformat() if rev.created_at else None,
            "updated_at": rev.updated_at.isoformat() if rev.updated_at else None,
            "tender_page": res.tender_page if res else None,
            "vendor_page": res.vendor_page if res else None,
            "vendor_evidence": res.vendor_evidence if res else "",
            "override_status": res.status if (res and res.is_reviewed) else None,
        })
    return {
        "read_only": True,
        "workspace_code": ws.workspace_code,
        "title": ws.title,
        "report": report,
        "review_items": rev_list,
    }


# ── Report Export & Audit Log (PART 22, 24) ──────────────────────────────────

@app.get("/api/workspaces/{code_or_id}/report")
def export_compliance_report(code_or_id: str, db: Session = Depends(get_db)):
    """Generates official AI-Assisted Compliance Verification Report."""
    ws = _get_workspace_or_404(code_or_id, db)
    report = generate_compliance_report(ws, db)
    record_audit_event(
        db,
        action="REPORT_EXPORTED",
        workspace_id=ws.id,
        details={"title": ws.title},
    )
    return report


@app.get("/api/workspaces/{code_or_id}/audit", response_model=List[schemas.AuditLogResponse])
def get_workspace_audit_log(
    code_or_id: str,
    current_user: Optional[models.User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Retrieves immutable audit trail of events for this workspace."""
    ws = _get_workspace_or_404(code_or_id, db)
    logs = db.query(models.AuditLog).filter(
        models.AuditLog.workspace_id == ws.id,
    ).order_by(models.AuditLog.timestamp.desc()).limit(100).all()
    return logs
# BidVerify AI Backend v2.4.1 - LLM Requirement Analyst integrated
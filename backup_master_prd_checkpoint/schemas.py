"""
BidVerify AI - Pydantic Request & Response Schemas

Defines structured API contracts for all workspace, extraction, verification,
multi-vendor comparison, human review queue, and audit log endpoints.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ─────────────────────────────────────────────────────────────────────────────
# Auth Schemas
# ─────────────────────────────────────────────────────────────────────────────

class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    email: str
    role: str
    full_name: Optional[str] = None
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ─────────────────────────────────────────────────────────────────────────────
# Workspace Schemas
# ─────────────────────────────────────────────────────────────────────────────

class WorkspaceCreate(BaseModel):
    title: Optional[str] = "GeM Procurement Verification"
    tender_reference: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    closing_date: Optional[datetime] = None
    status: Optional[str] = "ACTIVE"
    expires_in_days: Optional[int] = 30


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    doc_type: str
    original_filename: str
    file_size: int
    mime_type: str
    page_count: int
    created_at: datetime


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_code: str
    title: str
    tender_reference: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    closing_date: Optional[datetime] = None
    status: str
    derived_status: Optional[str] = None
    owner_id: Optional[str] = None
    created_at: datetime
    expires_at: Optional[datetime] = None
    documents_count: Optional[int] = 0
    requirements_count: Optional[int] = 0
    vendors_count: Optional[int] = 0
    vendor_names: List[str] = []


class WorkspaceDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_code: str
    title: str
    tender_reference: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    closing_date: Optional[datetime] = None
    status: str
    derived_status: Optional[str] = None
    owner_id: Optional[str] = None
    created_at: datetime
    expires_at: Optional[datetime] = None
    documents: List[DocumentResponse] = []
    requirements_count: int = 0
    vendors_count: int = 0
    tender_document: Optional[DocumentResponse] = None


# ─────────────────────────────────────────────────────────────────────────────
# Requirement Schemas
# ─────────────────────────────────────────────────────────────────────────────

class RequirementSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    req_code: str
    name: str
    raw_text: str
    category: str
    requirement_type: str
    domain: str
    condition: str
    value: Optional[str] = None
    unit: Optional[str] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    allowed_values: List[str] = []
    mandatory: bool
    source_page: Optional[int] = None
    source_text: Optional[str] = None
    source_table: Optional[str] = None
    source_row: Optional[int] = None
    confidence: float = 1.0
    is_active: bool = True
    order_index: int = 0


class RequirementUpdate(BaseModel):
    name: Optional[str] = None
    value: Optional[str] = None
    condition: Optional[str] = None
    category: Optional[str] = None
    domain: Optional[str] = None
    requirement_type: Optional[str] = None
    mandatory: Optional[bool] = None
    is_active: Optional[bool] = None


class RequirementCreate(BaseModel):
    name: str
    value: str
    condition: str = "MINIMUM"
    category: str = "technical"
    domain: str = "TECHNICAL"
    requirement_type: str = "MANDATORY"
    mandatory: bool = True


class RequirementMergeRequest(BaseModel):
    target_req_id: str
    source_req_ids: List[str]
    merged_name: Optional[str] = None
    merged_value: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Compliance & Verification Schemas
# ─────────────────────────────────────────────────────────────────────────────

class ComplianceResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    requirement_id: str
    requirement_name: Optional[str] = None
    requirement_code: Optional[str] = None
    vendor_id: str
    vendor_name: Optional[str] = None
    status: str
    reason: str
    confidence: float
    match_score: float
    match_method: str
    tender_value: Optional[str] = None
    vendor_value: Optional[str] = None
    condition: Optional[str] = None
    category: Optional[str] = None
    mandatory: Optional[bool] = True
    tender_evidence: str
    vendor_evidence: str
    tender_page: Optional[int] = None
    vendor_page: Optional[int] = None
    is_reviewed: bool = False
    review_status: Optional[str] = None
    review_notes: Optional[str] = None


class VendorSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    vendor_code: str
    vendor_name: str
    score_overall: float
    score_mandatory: float
    score_technical: float
    score_commercial: float
    score_evidence_coverage: float
    score_explanation: str
    compliant_count: int
    non_compliant_count: int
    not_found_count: int
    needs_review_count: int
    total_count: int


class VendorDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    vendor: VendorSummary
    results: List[ComplianceResultResponse]


class CrossVendorRequirementRow(BaseModel):
    requirement_id: str
    req_code: str
    requirement_name: str
    tender_value: str
    condition: str
    category: str
    mandatory: bool
    vendor_claims: Dict[str, Dict[str, Any]]  # vendor_code -> {status, value, confidence, evidence}


class MultiVendorComparisonResponse(BaseModel):
    workspace_code: str
    title: str
    total_requirements: int
    mandatory_requirements: int
    vendors: List[VendorSummary]
    matrix: List[CrossVendorRequirementRow]


# ─────────────────────────────────────────────────────────────────────────────
# Human Review Schemas
# ─────────────────────────────────────────────────────────────────────────────

class ReviewActionRequest(BaseModel):
    status: str = Field(..., pattern="^(APPROVED|REJECTED|CLARIFICATION_REQUESTED)$")
    decision_reason: str
    override_compliance_status: Optional[str] = None  # COMPLIANT, NON_COMPLIANT, NEEDS_REVIEW


class ReviewItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    compliance_result_id: str
    requirement_name: Optional[str] = None
    vendor_name: Optional[str] = None
    status: str
    decision_reason: str
    created_at: datetime
    result: Optional[ComplianceResultResponse] = None


# ─────────────────────────────────────────────────────────────────────────────
# Sharing & Job Schemas
# ─────────────────────────────────────────────────────────────────────────────

class ShareLinkCreate(BaseModel):
    expires_in_days: Optional[int] = 7


class ShareLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_code: str
    share_token: str
    share_url: str
    is_active: bool
    expires_at: Optional[datetime] = None
    created_at: datetime


class JobStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    status: str
    stage: str
    progress_pct: int
    stage_message: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: Optional[str] = None
    user_id: Optional[str] = None
    action: str
    details: Dict[str, Any] = {}
    ip_address: Optional[str] = None
    timestamp: datetime

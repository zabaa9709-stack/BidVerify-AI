"""
BidVerify AI - Relational Database Models (SQLAlchemy)

Relational entities:
  - User
  - Workspace
  - Document
  - Requirement
  - Vendor
  - VendorClaim
  - ComplianceResult
  - ReviewItem
  - AuditLog
  - ShareLink
  - Job
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import relationship
from database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(64), unique=True, index=True, nullable=False)
    email = Column(String(128), unique=True, index=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(32), default="PROCUREMENT_OFFICER", nullable=False)  # ADMIN, PROCUREMENT_OFFICER, REVIEWER, READ_ONLY
    full_name = Column(String(128), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=_utc_now, nullable=False)

    workspaces = relationship("Workspace", back_populates="owner", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user")


class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_code = Column(String(24), unique=True, index=True, nullable=False)  # e.g. BV-7F4K-29QX
    secret_token = Column(String(64), unique=True, index=True, nullable=False)    # non-guessable private access token
    title = Column(String(256), default="Untitled Procurement Workspace", nullable=False)
    tender_reference = Column(String(128), nullable=True)                          # e.g. GEM/2026/B/882190
    description = Column(Text, nullable=True)
    start_date = Column(DateTime, nullable=True)
    closing_date = Column(DateTime, nullable=True)
    status = Column(String(32), default="ACTIVE", index=True, nullable=False)     # DRAFT, UPCOMING, ACTIVE, CLOSING_SOON, CLOSED, ARCHIVED
    owner_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    tender_metadata = Column(JSON, default=dict)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utc_now, nullable=False)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now, nullable=False)

    @property
    def derived_status(self) -> str:
        if self.status in ("ARCHIVED", "DRAFT"):
            return self.status
        now = datetime.now(timezone.utc)
        c_date = self.closing_date.replace(tzinfo=timezone.utc) if (self.closing_date and self.closing_date.tzinfo is None) else self.closing_date
        s_date = self.start_date.replace(tzinfo=timezone.utc) if (self.start_date and self.start_date.tzinfo is None) else self.start_date
        if c_date and now > c_date:
            return "CLOSED"
        if c_date and 0 <= (c_date - now).total_seconds() < 3 * 86400:
            return "CLOSING_SOON"
        if s_date and now < s_date:
            return "UPCOMING"
        return self.status or "ACTIVE"

    owner = relationship("User", back_populates="workspaces")
    documents = relationship("Document", back_populates="workspace", cascade="all, delete-orphan")
    requirements = relationship("Requirement", back_populates="workspace", cascade="all, delete-orphan")
    vendors = relationship("Vendor", back_populates="workspace", cascade="all, delete-orphan")
    compliance_results = relationship("ComplianceResult", back_populates="workspace", cascade="all, delete-orphan")
    review_items = relationship("ReviewItem", back_populates="workspace", cascade="all, delete-orphan")
    share_links = relationship("ShareLink", back_populates="workspace", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="workspace", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="workspace", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_workspace_code_status", "workspace_code", "status"),
    )


class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    doc_type = Column(String(32), default="TENDER", index=True, nullable=False)  # TENDER, VENDOR_BID, CERTIFICATE, TECHNICAL_DATASHEET, OTHER
    original_filename = Column(String(256), nullable=False)
    stored_filename = Column(String(256), nullable=False)
    file_size = Column(Integer, default=0, nullable=False)
    mime_type = Column(String(64), default="application/pdf", nullable=False)
    sha256_hash = Column(String(64), index=True, nullable=False)
    page_count = Column(Integer, default=0, nullable=False)
    extracted_text = Column(Text, default="", nullable=False)
    created_at = Column(DateTime, default=_utc_now, nullable=False)

    workspace = relationship("Workspace", back_populates="documents")
    vendor = relationship("Vendor", back_populates="document", uselist=False)

    __table_args__ = (
        Index("ix_doc_ws_hash", "workspace_id", "sha256_hash"),
    )


class Requirement(Base):
    __tablename__ = "requirements"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    req_code = Column(String(24), index=True, nullable=False)  # REQ-001
    name = Column(String(256), nullable=False)
    raw_text = Column(Text, default="", nullable=False)
    category = Column(String(32), default="technical", nullable=False)  # technical, commercial, operational
    requirement_type = Column(String(32), default="MANDATORY", nullable=False)  # MANDATORY, PREFERRED, OPTIONAL, INFORMATIONAL
    domain = Column(String(32), default="TECHNICAL", nullable=False)  # TECHNICAL, COMMERCIAL, ELIGIBILITY, LEGAL, DELIVERY, WARRANTY, CERTIFICATION, OTHER
    condition = Column(String(32), default="MINIMUM", nullable=False)  # MINIMUM, MAXIMUM, EXACT, RANGE, ALLOWED_VALUES, QUALITATIVE, NEGATIVE, NONE
    value = Column(Text, nullable=True)
    unit = Column(String(32), nullable=True)
    min_value = Column(Float, nullable=True)
    max_value = Column(Float, nullable=True)
    allowed_values = Column(JSON, default=list)
    mandatory = Column(Boolean, default=True, nullable=False)
    source_page = Column(Integer, nullable=True)
    source_text = Column(Text, default="", nullable=False)
    source_table = Column(String(64), nullable=True)
    source_row = Column(Integer, nullable=True)
    confidence = Column(Float, default=1.0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    order_index = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=_utc_now, nullable=False)

    workspace = relationship("Workspace", back_populates="requirements")
    compliance_results = relationship("ComplianceResult", back_populates="requirement", cascade="all, delete-orphan")


class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    vendor_code = Column(String(24), index=True, nullable=False)  # e.g. VEND-001
    vendor_name = Column(String(256), nullable=False)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    score_overall = Column(Float, default=0.0, nullable=False)
    score_mandatory = Column(Float, default=0.0, nullable=False)
    score_technical = Column(Float, default=0.0, nullable=False)
    score_commercial = Column(Float, default=0.0, nullable=False)
    score_evidence_coverage = Column(Float, default=0.0, nullable=False)
    score_explanation = Column(Text, default="", nullable=False)
    compliant_count = Column(Integer, default=0, nullable=False)
    non_compliant_count = Column(Integer, default=0, nullable=False)
    not_found_count = Column(Integer, default=0, nullable=False)
    needs_review_count = Column(Integer, default=0, nullable=False)
    total_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=_utc_now, nullable=False)

    workspace = relationship("Workspace", back_populates="vendors")
    document = relationship("Document", back_populates="vendor")
    claims = relationship("VendorClaim", back_populates="vendor", cascade="all, delete-orphan")
    compliance_results = relationship("ComplianceResult", back_populates="vendor", cascade="all, delete-orphan")


class VendorClaim(Base):
    __tablename__ = "vendor_claims"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    vendor_id = Column(String(36), ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False, index=True)
    requirement_name = Column(String(256), nullable=False)
    raw_text = Column(Text, default="", nullable=False)
    value = Column(Text, nullable=True)
    unit = Column(String(32), nullable=True)
    page_number = Column(Integer, nullable=True)
    confidence = Column(Float, default=1.0, nullable=False)

    vendor = relationship("Vendor", back_populates="claims")


class ComplianceResult(Base):
    __tablename__ = "compliance_results"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    vendor_id = Column(String(36), ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False, index=True)
    requirement_id = Column(String(36), ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(32), default="NEEDS_REVIEW", index=True, nullable=False)  # COMPLIANT, NON_COMPLIANT, NOT_FOUND, NEEDS_REVIEW
    reason = Column(Text, default="", nullable=False)
    confidence = Column(Float, default=0.0, nullable=False)
    match_score = Column(Float, default=0.0, nullable=False)
    match_method = Column(String(32), default="deterministic", nullable=False)  # exact, deterministic, ai, not_found
    tender_evidence = Column(Text, default="", nullable=False)
    vendor_evidence = Column(Text, default="", nullable=False)
    tender_page = Column(Integer, nullable=True)
    vendor_page = Column(Integer, nullable=True)
    is_reviewed = Column(Boolean, default=False, nullable=False)
    reviewed_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    review_status = Column(String(32), nullable=True)  # APPROVED, REJECTED, CLARIFIED
    review_notes = Column(Text, nullable=True)

    workspace = relationship("Workspace", back_populates="compliance_results")
    vendor = relationship("Vendor", back_populates="compliance_results")
    requirement = relationship("Requirement", back_populates="compliance_results")
    review_items = relationship("ReviewItem", back_populates="compliance_result", cascade="all, delete-orphan")


class ReviewItem(Base):
    __tablename__ = "review_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    compliance_result_id = Column(String(36), ForeignKey("compliance_results.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(32), default="PENDING", index=True, nullable=False)  # PENDING, APPROVED, REJECTED, CLARIFICATION_REQUESTED
    decision_reason = Column(Text, default="", nullable=False)
    reviewer_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=_utc_now, nullable=False)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now, nullable=False)

    workspace = relationship("Workspace", back_populates="review_items")
    compliance_result = relationship("ComplianceResult", back_populates="review_items")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(64), nullable=False)  # WORKSPACE_CREATED, TENDER_UPLOADED, VENDOR_UPLOADED, etc.
    details = Column(JSON, default=dict)
    ip_address = Column(String(45), nullable=True)
    timestamp = Column(DateTime, default=_utc_now, index=True, nullable=False)

    workspace = relationship("Workspace", back_populates="audit_logs")
    user = relationship("User", back_populates="audit_logs")


class ShareLink(Base):
    __tablename__ = "share_links"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    share_token = Column(String(64), unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    created_by_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=_utc_now, nullable=False)
    revoked_at = Column(DateTime, nullable=True)

    workspace = relationship("Workspace", back_populates="share_links")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    job_type = Column(String(32), default="MULTI_VENDOR_VERIFICATION", nullable=False)
    status = Column(String(32), default="QUEUED", index=True, nullable=False)  # QUEUED, PROCESSING, COMPLETED, FAILED, CANCELLED
    stage = Column(String(48), default="UPLOAD_VALIDATION", nullable=False)
    progress_pct = Column(Integer, default=0, nullable=False)
    stage_message = Column(String(256), default="Job queued for processing", nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utc_now, nullable=False)
    updated_at = Column(DateTime, default=_utc_now, onupdate=_utc_now, nullable=False)

    workspace = relationship("Workspace", back_populates="jobs")

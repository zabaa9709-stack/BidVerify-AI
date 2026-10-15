"""
BidVerify AI - Security, Document Ingestion & Verification Utilities

Implements:
  - Cryptographically random workspace identifiers (BV-XXXX-XXXX)
  - Non-guessable secret tokens & revocable share links
  - Defense-in-depth upload validation:
      * Magic bytes / signature check
      * MIME & extension validation
      * Configurable size limits & workspace quota
      * Path traversal prevention & safe UUID storage
      * Cryptographic SHA256 duplicate detection
      * Pluggable antivirus scanning interface
  - Audit logging helpers
"""

import hashlib
import io
import os
import re
import secrets
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
import models

# ─────────────────────────────────────────────────────────────────────────────
# Environment Configuration
# ─────────────────────────────────────────────────────────────────────────────

MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "25"))
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024
MAX_FILES_PER_WORKSPACE = int(os.getenv("MAX_FILES_PER_WORKSPACE", "25"))

# Isolated directory outside webroot
STORAGE_DIR = Path(os.getenv("DOCUMENT_STORAGE_DIR", "data/secure_uploads")).resolve()
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# Non-ambiguous alphanumeric character set for workspace codes (omits 0, O, 1, I)
WORKSPACE_CHARSET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


# ─────────────────────────────────────────────────────────────────────────────
# Random Identifiers & Tokens
# ─────────────────────────────────────────────────────────────────────────────

def generate_workspace_code() -> str:
    """Generates a human-friendly, cryptographically random workspace identifier.
    Example: BV-7F4K-29QX
    """
    part1 = "".join(secrets.choice(WORKSPACE_CHARSET) for _ in range(4))
    part2 = "".join(secrets.choice(WORKSPACE_CHARSET) for _ in range(4))
    return f"BV-{part1}-{part2}"


def generate_secure_token() -> str:
    """Generates a private, unguessable access token for workspace authorization."""
    return secrets.token_urlsafe(32)


def generate_share_token() -> str:
    """Generates an unguessable share link token."""
    return secrets.token_urlsafe(24)


def calculate_sha256(data: bytes) -> str:
    """Computes SHA-256 checksum of raw file bytes."""
    return hashlib.sha256(data).hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# Antivirus Scanner Interface (Pluggable for Enterprise / Gov)
# ─────────────────────────────────────────────────────────────────────────────

class AntivirusScanner:
    """Pluggable scanner interface. Ready for ClamAV / ICAP / Defender in production."""

    @staticmethod
    def scan_content(data: bytes) -> Tuple[bool, str]:
        """Scans binary content for malware/decompression bomb signatures.
        Returns: (is_clean: bool, threat_info: str)
        """
        # Basic heuristic: reject decompression bombs or suspicious binary signatures
        if len(data) > MAX_UPLOAD_SIZE_BYTES:
            return False, "File exceeds maximum size threshold."
        # Verify ZIP ratio if zip/docx
        if data.startswith(b"PK\x03\x04"):
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as zf:
                    total_uncompressed = sum(info.file_size for info in zf.infolist())
                    if total_uncompressed > 100 * 1024 * 1024:  # 100MB max uncompressed
                        return False, "Suspected compression bomb in document archive."
            except Exception:
                return False, "Malformed archive structure."
        return True, "Clean"


# ─────────────────────────────────────────────────────────────────────────────
# File Upload Validation & Storage
# ─────────────────────────────────────────────────────────────────────────────

def validate_and_store_document(
    file_bytes: bytes,
    original_filename: str,
    workspace_id: str,
    db: Session,
    expected_type: Optional[str] = None,
) -> Tuple[Path, str, str, int]:
    """
    Validates file format, magic bytes, file size, quota, and stores it securely.
    Returns: (stored_path, mime_type, sha256_hash, file_size)
    """
    # 1. File size check
    file_size = len(file_bytes)
    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )
    if file_size > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Uploaded file exceeds maximum limit of {MAX_UPLOAD_SIZE_MB}MB.",
        )

    # 2. Workspace file quota check
    existing_docs_count = db.query(models.Document).filter(models.Document.workspace_id == workspace_id).count()
    if existing_docs_count >= MAX_FILES_PER_WORKSPACE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Workspace document limit of {MAX_FILES_PER_WORKSPACE} files reached.",
        )

    # 3. Filename & Extension sanitization
    clean_name = Path(original_filename).name.strip()
    ext = clean_name.lower().split(".")[-1] if "." in clean_name else ""
    if ext not in ("pdf", "docx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type (.{ext}). Only PDF and DOCX files are allowed.",
        )

    # 4. Magic-byte signature verification
    mime_type = "application/octet-stream"
    if ext == "pdf":
        # PDF magic bytes (%PDF- within first 1024 bytes)
        if b"%PDF-" not in file_bytes[:1024]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid PDF file: Missing standard %PDF- file signature.",
            )
        mime_type = "application/pdf"
    elif ext == "docx":
        # DOCX is a zip archive containing [Content_Types].xml or word/
        if not file_bytes.startswith(b"PK\x03\x04"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid DOCX file: Missing valid PK archive signature.",
            )
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
                filenames = zf.namelist()
                if not any("word/" in fn or "[Content_Types].xml" in fn for fn in filenames):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Invalid DOCX file: Structure does not conform to Office Open XML standard.",
                    )
        except zipfile.BadZipFile:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Malformed or corrupt DOCX archive.",
            )
        mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    # 5. Antivirus scan
    is_clean, reason = AntivirusScanner.scan_content(file_bytes)
    if not is_clean:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Security verification failed: {reason}",
        )

    # 6. Compute hash
    sha256_hash = calculate_sha256(file_bytes)

    # 7. Check for duplicate upload in this workspace
    duplicate = db.query(models.Document).filter(
        models.Document.workspace_id == workspace_id,
        models.Document.sha256_hash == sha256_hash,
    ).first()
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Duplicate document detected: Exactly identical document has already been uploaded as '{duplicate.original_filename}'.",
        )

    # 8. Save under isolated server-generated UUID path (never user filename)
    safe_filename = f"{uuid.uuid4().hex}_{secrets.token_hex(4)}.{ext}"
    stored_path = STORAGE_DIR / safe_filename
    stored_path.write_bytes(file_bytes)

    return stored_path, mime_type, sha256_hash, file_size


# ─────────────────────────────────────────────────────────────────────────────
# Audit Trail Helper
# ─────────────────────────────────────────────────────────────────────────────

def record_audit_event(
    db: Session,
    action: str,
    workspace_id: Optional[str] = None,
    user_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> None:
    """Records an audit trail event without logging sensitive raw document contents."""
    try:
        log_entry = models.AuditLog(
            workspace_id=workspace_id,
            user_id=user_id,
            action=action,
            details=details or {},
            ip_address=ip_address,
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[BidVerify Audit] Error recording audit event {action}: {e}")

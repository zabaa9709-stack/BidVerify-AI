"""
BidVerify AI - Authentication & Role-Based Access Control (RBAC)

Implements:
  - Secure PBKDF2-HMAC-SHA256 password hashing (zero plaintext storage)
  - Cryptographic token generation & verification (HMAC-SHA256 signed bearer tokens)
  - Modular RBAC dependencies (ADMIN, PROCUREMENT_OFFICER, REVIEWER, READ_ONLY)
  - Extensible for institutional SSO/OAuth/OpenID integration
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from database import get_db
import models

# Secret key for token signing (override via environment variable)
AUTH_SECRET_KEY = os.getenv("AUTH_SECRET_KEY", "bidverify-secret-key-gem-compliance-2026-prod-gate")
TOKEN_EXPIRE_SECONDS = int(os.getenv("TOKEN_EXPIRE_SECONDS", "86400"))  # 24 hours

security_bearer = HTTPBearer(auto_error=False)


# ─────────────────────────────────────────────────────────────────────────────
# Secure Password Hashing (PBKDF2-HMAC-SHA256)
# ─────────────────────────────────────────────────────────────────────────────

def get_password_hash(password: str) -> str:
    """Generates a secure salt and computes PBKDF2-HMAC-SHA256 with 100,000 iterations."""
    salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    salt_hex = salt.hex()
    key_hex = key.hex()
    return f"pbkdf2_sha256$100000${salt_hex}${key_hex}"


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Verifies a plain password against the stored hash in constant time."""
    try:
        parts = password_hash.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        iterations = int(parts[1])
        salt = bytes.fromhex(parts[2])
        expected_key = bytes.fromhex(parts[3])
        computed_key = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(computed_key, expected_key)
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Cryptographic Token Management (Signed JSON Web Bearer Tokens)
# ─────────────────────────────────────────────────────────────────────────────

def create_access_token(user: models.User, expires_in: int = TOKEN_EXPIRE_SECONDS) -> str:
    """Creates a cryptographically signed HMAC-SHA256 session token."""
    now = int(time.time())
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "email": user.email,
        "iat": now,
        "exp": now + expires_in,
    }
    raw_payload = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    b64_payload = base64.urlsafe_b64encode(raw_payload).decode("utf-8").rstrip("=")
    signature = hmac.new(AUTH_SECRET_KEY.encode("utf-8"), b64_payload.encode("utf-8"), hashlib.sha256).digest()
    b64_sig = base64.urlsafe_b64encode(signature).decode("utf-8").rstrip("=")
    return f"{b64_payload}.{b64_sig}"


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Verifies signature and expiration of a signed token."""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        b64_payload, b64_sig = parts[0], parts[1]

        # Verify signature
        expected_sig = hmac.new(AUTH_SECRET_KEY.encode("utf-8"), b64_payload.encode("utf-8"), hashlib.sha256).digest()
        actual_sig = base64.urlsafe_b64decode(b64_sig + "=" * (-len(b64_sig) % 4))
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None

        # Decode payload
        raw_payload = base64.urlsafe_b64decode(b64_payload + "=" * (-len(b64_payload) % 4))
        data = json.loads(raw_payload.decode("utf-8"))

        # Check expiration
        if data.get("exp", 0) < int(time.time()):
            return None

        return data
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI Dependencies & RBAC
# ─────────────────────────────────────────────────────────────────────────────

def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
    db: Session = Depends(get_db),
) -> models.User:
    """Extracts and validates the authenticated user from the Authorization header."""
    if not auth or not auth.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token_data = decode_access_token(auth.credentials)
    if not token_data or "sub" not in token_data:
        # Check if credentials belong to an active temporary read-only ShareLink
        share_link = db.query(models.ShareLink).filter(
            models.ShareLink.share_token == auth.credentials,
            models.ShareLink.is_active == True,
        ).first()
        if share_link:
            if share_link.expires_at:
                exp = share_link.expires_at.replace(tzinfo=timezone.utc) if share_link.expires_at.tzinfo is None else share_link.expires_at
                if exp < datetime.now(timezone.utc):
                    raise HTTPException(
                        status_code=status.HTTP_410_GONE,
                        detail="This share link has expired.",
                    )
            return models.User(
                id=f"shared_{share_link.id}",
                username="shared_reader",
                role="READ_ONLY",
                email="shared@bidverify.gov.in",
                full_name="Shared Workspace User",
                is_active=True,
            )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = token_data["sub"]
    user = db.query(models.User).filter(models.User.id == user_id, models.User.is_active == True).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account no longer active or exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_optional_user(
    auth: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
    db: Session = Depends(get_db),
) -> Optional[models.User]:
    """Returns the user if valid token provided, else None without raising error."""
    if not auth or not auth.credentials:
        return None
    token_data = decode_access_token(auth.credentials)
    if not token_data or "sub" not in token_data:
        share_link = db.query(models.ShareLink).filter(
            models.ShareLink.share_token == auth.credentials,
            models.ShareLink.is_active == True,
        ).first()
        if share_link:
            return models.User(
                id=f"shared_{share_link.id}",
                username="shared_reader",
                role="READ_ONLY",
                email="shared@bidverify.gov.in",
                full_name="Shared Workspace User",
                is_active=True,
            )
        return None
    return db.query(models.User).filter(models.User.id == token_data["sub"], models.User.is_active == True).first()


def require_role(allowed_roles: List[str]):
    """Enforces role-based permissions (ADMIN, PROCUREMENT_OFFICER, REVIEWER, READ_ONLY)."""
    def _role_checker(user: models.User = Depends(get_current_user)) -> models.User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: user role '{user.role}' lacks required permissions ({', '.join(allowed_roles)}).",
            )
        return user
    return _role_checker

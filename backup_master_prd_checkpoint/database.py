"""
BidVerify AI - Database Configuration & Engine Management

Supports PostgreSQL (production target) with fallback to SQLite for zero-config local runs.
Relational models with parameterization, foreign keys, and indexes.
"""

import os
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# Base directory for SQLite data storage when PostgreSQL is not configured
BASE_DIR = Path(__file__).resolve().parent

# Target: PostgreSQL via environment variable, or fallback to SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

if not DATABASE_URL:
    db_path = BASE_DIR / "bidverify.db"
    DATABASE_URL = f"sqlite:///{db_path}"

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for yielding database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initializes database tables and default initial users."""
    import models  # Ensure models are imported before creating tables
    Base.metadata.create_all(bind=engine)
    _migrate_schema()
    _seed_initial_users()


def _migrate_schema() -> None:
    """Ensures newly added columns exist in existing SQLite databases."""
    from sqlalchemy import text
    with engine.connect() as conn:
        try:
            # Check existing columns in workspaces
            res = conn.execute(text("PRAGMA table_info(workspaces)")).fetchall()
            existing_cols = {row[1] for row in res}
            if "tender_reference" not in existing_cols:
                conn.execute(text("ALTER TABLE workspaces ADD COLUMN tender_reference VARCHAR(128)"))
            if "description" not in existing_cols:
                conn.execute(text("ALTER TABLE workspaces ADD COLUMN description TEXT"))
            if "start_date" not in existing_cols:
                conn.execute(text("ALTER TABLE workspaces ADD COLUMN start_date DATETIME"))
            if "closing_date" not in existing_cols:
                conn.execute(text("ALTER TABLE workspaces ADD COLUMN closing_date DATETIME"))
            conn.commit()
        except Exception as e:
            print(f"[BidVerify DB] Schema migration note: {e}")


def _seed_initial_users() -> None:
    """Seeds baseline RBAC accounts if no users exist."""
    from auth import get_password_hash
    import models

    db = SessionLocal()
    try:
        if db.query(models.User).count() == 0:
            # 1. Admin
            admin = models.User(
                username="admin",
                email="admin@bidverify.gov.in",
                password_hash=get_password_hash("Admin@BidVerify2026"),
                role="ADMIN",
                full_name="National Procurement Administrator",
            )
            # 2. Procurement Officer
            officer = models.User(
                username="officer",
                email="officer@bidverify.gov.in",
                password_hash=get_password_hash("Officer@BidVerify2026"),
                role="PROCUREMENT_OFFICER",
                full_name="Senior GeM Verification Officer",
            )
            # 3. Reviewer
            reviewer = models.User(
                username="reviewer",
                email="reviewer@bidverify.gov.in",
                password_hash=get_password_hash("Reviewer@BidVerify2026"),
                role="REVIEWER",
                full_name="Technical Compliance Reviewer",
            )
            # 4. Read Only Auditor
            auditor = models.User(
                username="auditor",
                email="auditor@bidverify.gov.in",
                password_hash=get_password_hash("Auditor@BidVerify2026"),
                role="READ_ONLY",
                full_name="Public Procurement Auditor",
            )
            db.add_all([admin, officer, reviewer, auditor])
            db.commit()
            print("[BidVerify DB] Initial RBAC users seeded successfully.")
    except Exception as e:
        db.rollback()
        print(f"[BidVerify DB] User seeding note: {e}")
    finally:
        db.close()

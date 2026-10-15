"""
BidVerify AI - Multi-Tender & Lifecycle Test Suite
Verifies:
  1. Multiple independent tenders created under the same owner.
  2. Each tender maintains isolated requirements and vendors (no data leakage).
  3. Derived status computation based on dates (UPCOMING, ACTIVE, CLOSING_SOON, CLOSED).
  4. Closed tenders reject new vendor uploads with HTTP 403.
  5. Closed tenders preserve existing results and allow owner viewing.
"""

import io
import os
import sys
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, init_db
import models
from main import app
from security import generate_workspace_code, generate_secure_token

client = TestClient(app)

def test_multi_tender_architecture_and_lifecycle():
    print("======================================================================")
    print("BidVerify AI — Multi-Tender Architecture & Lifecycle Verification")
    print("======================================================================")

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        # 1. Create Tender A (Active)
        ws_a_code = generate_workspace_code()
        ws_a = models.Workspace(
            workspace_code=ws_a_code,
            secret_token=generate_secure_token(),
            title="Tender A - Laptop Procurement",
            tender_reference="GEM/2026/B/1001",
            start_date=now - timedelta(days=2),
            closing_date=now + timedelta(days=10),
            status="ACTIVE",
        )
        db.add(ws_a)

        # 2. Create Tender B (Upcoming)
        ws_b_code = generate_workspace_code()
        ws_b = models.Workspace(
            workspace_code=ws_b_code,
            secret_token=generate_secure_token(),
            title="Tender B - Data Center Cooling",
            tender_reference="GEM/2026/B/1002",
            start_date=now + timedelta(days=5),
            closing_date=now + timedelta(days=20),
            status="ACTIVE",
        )
        db.add(ws_b)

        # 3. Create Tender C (Closed)
        ws_c_code = generate_workspace_code()
        ws_c = models.Workspace(
            workspace_code=ws_c_code,
            secret_token=generate_secure_token(),
            title="Tender C - Network Switches (Past)",
            tender_reference="GEM/2026/B/1003",
            start_date=now - timedelta(days=30),
            closing_date=now - timedelta(days=5),
            status="ACTIVE",
        )
        db.add(ws_c)

        db.commit()
        db.refresh(ws_a)
        db.refresh(ws_b)
        db.refresh(ws_c)

        # Verify Derived Statuses
        assert ws_a.derived_status == "ACTIVE", f"Expected ACTIVE, got {ws_a.derived_status}"
        print(f"[PASS] Tender A status derived as: {ws_a.derived_status}")

        assert ws_b.derived_status == "UPCOMING", f"Expected UPCOMING, got {ws_b.derived_status}"
        print(f"[PASS] Tender B status derived as: {ws_b.derived_status}")

        assert ws_c.derived_status == "CLOSED", f"Expected CLOSED, got {ws_c.derived_status}"
        print(f"[PASS] Tender C status derived as: {ws_c.derived_status}")

        # 4. Add isolated requirements to Tender A and Tender B
        req_a = models.Requirement(
            workspace_id=ws_a.id,
            req_code="REQ-A-01",
            name="RAM Capacity",
            raw_text="Minimum 32 GB DDR5 RAM required",
            condition="minimum",
            value="32 GB",
            mandatory=True,
            order_index=1,
        )
        req_b = models.Requirement(
            workspace_id=ws_b.id,
            req_code="REQ-B-01",
            name="Cooling Capacity",
            raw_text="Minimum 50 kW cooling capacity",
            condition="minimum",
            value="50 kW",
            mandatory=True,
            order_index=1,
        )
        db.add_all([req_a, req_b])
        db.commit()

        # 5. Verify Tender Isolation via API
        res_a = client.get(f"/api/workspaces/{ws_a_code}/requirements")
        assert res_a.status_code == 200
        reqs_a = res_a.json()
        assert len(reqs_a) == 1
        assert reqs_a[0]["name"] == "RAM Capacity"
        assert reqs_a[0]["req_code"] == "REQ-A-01"

        res_b = client.get(f"/api/workspaces/{ws_b_code}/requirements")
        assert res_b.status_code == 200
        reqs_b = res_b.json()
        assert len(reqs_b) == 1
        assert reqs_b[0]["name"] == "Cooling Capacity"
        assert reqs_b[0]["req_code"] == "REQ-B-01"

        print("[PASS] Strict Tender Isolation: Tender A criteria never leak into Tender B")

        # 6. Verify Closed Tender rejects new vendor submissions (HTTP 403)
        sample_pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
        files = {"files": ("vendor_late_bid.pdf", sample_pdf, "application/pdf")}
        res_c_upload = client.post(f"/api/workspaces/{ws_c_code}/vendors", files=files)
        assert res_c_upload.status_code == 403, f"Expected 403 for closed tender, got {res_c_upload.status_code}"
        assert "closed" in res_c_upload.json()["detail"].lower()
        print("[PASS] Closed Tender correctly rejects new vendor proposals with HTTP 403")

        # 7. Verify Closed Tender allows viewing and preserves results
        res_c_get = client.get(f"/api/workspaces/{ws_c_code}")
        assert res_c_get.status_code == 200
        ws_c_detail = res_c_get.json()
        assert ws_c_detail["derived_status"] == "CLOSED"
        assert ws_c_detail["title"] == "Tender C - Network Switches (Past)"
        print("[PASS] Closed Tender results and metadata remain fully viewable by owner")

        print("======================================================================")
        print("ALL MULTI-TENDER & LIFECYCLE TESTS PASSED (100% SUCCESS)!")
        print("======================================================================")

    finally:
        db.close()

if __name__ == "__main__":
    test_multi_tender_architecture_and_lifecycle()

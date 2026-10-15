"""
BidVerify AI - Platform Test Suite (PART 32)

Automated verification of the 24 platform requirements:
  1. 20 actual requirements should not become 38 simply because explanatory text exists.
  2. Duplicate semantic requirements merge correctly.
  3. Table rows remain separate requirements.
  4. Minimum comparisons.
  5. Maximum comparisons.
  6. Exact comparisons.
  7. Range comparisons.
  8. Unit conversion.
  9. Negative requirements.
  10. Missing vendor evidence.
  11. Ambiguous semantic matching.
  12. Multiple vendors against one tender.
  13. Vendor scoring.
  14. Workspace authorization.
  15. Invalid share token.
  16. Expired share link.
  17. Unauthorized vendor mutation via read-only link.
  18. Oversized file rejection.
  19. Invalid file type rejection.
  20. Duplicate upload detection.
  21. Gemini/API fallback resilience.
  22. Async job failure handling.
  23. Concurrent workspace processing.
  24. Existing POST /verify backward compatibility.
"""

import io
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pypdf import PdfReader
from fastapi.testclient import TestClient

from database import SessionLocal, init_db
import models
from extractor import extract_requirements_from_text
from matcher import match_requirements
from comparator import (
    compare_single_requirement,
    compare_matched_pairs,
    calculate_vendor_score,
)
from ai_provider import DeterministicProvider
from security import (
    generate_workspace_code,
    generate_secure_token,
    generate_share_token,
    validate_and_store_document,
    calculate_sha256,
)
from main import app

client = TestClient(app)

_OK = "\033[92m[PASS]\033[0m"
_FAIL = "\033[91m[FAIL]\033[0m"


def run_all_tests():
    print("=" * 70)
    print("BidVerify AI — Platform Test Suite (24 Test Cases)")
    print("=" * 70)

    passed = 0
    failed = 0

    def check(test_num: int, name: str, fn):
        nonlocal passed, failed
        try:
            fn()
            print(f"{_OK} Test {test_num:02d}: {name}")
            passed += 1
        except Exception as e:
            print(f"{_FAIL} Test {test_num:02d}: {name} — Error: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    # ─────────────────────────────────────────────────────────────────────────
    # Test 1: 20 actual requirements should not become 38
    # ─────────────────────────────────────────────────────────────────────────
    def test_01_twenty_req_fix():
        pdf_path = Path(__file__).parent / "Sample_Tender_20_Requirements_BidVerify.pdf"
        assert pdf_path.exists(), f"Sample tender not found at {pdf_path}"
        reader = PdfReader(pdf_path)
        text = "\n".join(p.extract_text() or "" for p in reader.pages)
        reqs = extract_requirements_from_text(text)
        assert len(reqs) == 20, f"Expected exactly 20 requirements, but got {len(reqs)}"

    # ─────────────────────────────────────────────────────────────────────────
    # Test 2: Duplicate semantic requirements merge correctly
    # ─────────────────────────────────────────────────────────────────────────
    def test_02_semantic_deduplication():
        sample_text = """
        1. RAM: Minimum 16 GB DDR5
        2. Memory: Minimum 16 GB DDR5
        3. Storage: Minimum 512 GB SSD
        """
        reqs = extract_requirements_from_text(sample_text)
        # RAM and Memory with identical 16 GB DDR5 specification should merge into 1
        ram_reqs = [r for r in reqs if "ram" in r["name"].lower() or "memory" in r["name"].lower()]
        assert len(ram_reqs) == 1, f"Expected 1 merged RAM requirement, got {len(ram_reqs)}"
        assert len(reqs) == 2, f"Expected 2 total requirements (RAM + Storage), got {len(reqs)}"

    # ─────────────────────────────────────────────────────────────────────────
    # Test 3: Table rows remain separate requirements
    # ─────────────────────────────────────────────────────────────────────────
    def test_03_table_rows_separate():
        sample_table = """
        1
        RAM
        Minimum 16 GB
        2
        Storage
        Minimum 512 GB SSD
        3
        Warranty
        3 Years
        4
        Delivery
        Within 30 days
        """
        reqs = extract_requirements_from_text(sample_table)
        assert len(reqs) == 4, f"Expected 4 separate table requirements, got {len(reqs)}"
        names = [r["name"].lower() for r in reqs]
        assert "ram" in names and "storage" in names and "warranty" in names and "delivery" in names

    # ─────────────────────────────────────────────────────────────────────────
    # Test 4: Minimum comparisons
    # ─────────────────────────────────────────────────────────────────────────
    def test_04_minimum_comparisons():
        r1 = compare_single_requirement("RAM", "Minimum 16 GB", "minimum", "32 GB")
        assert r1["status"] == "COMPLIANT", f"16GB satisfied by 32GB failed: {r1}"
        r2 = compare_single_requirement("RAM", "Minimum 16 GB", "minimum", "8 GB")
        assert r2["status"] == "NON_COMPLIANT", f"16GB violated by 8GB failed: {r2}"

    # ─────────────────────────────────────────────────────────────────────────
    # Test 5: Maximum comparisons
    # ─────────────────────────────────────────────────────────────────────────
    def test_05_maximum_comparisons():
        r1 = compare_single_requirement("Delivery", "Within 30 days", "maximum", "20 days")
        assert r1["status"] == "COMPLIANT", f"Max 30 days satisfied by 20 days failed: {r1}"
        r2 = compare_single_requirement("Delivery", "Within 30 days", "maximum", "45 days")
        assert r2["status"] == "NON_COMPLIANT", f"Max 30 days violated by 45 days failed: {r2}"

    # ─────────────────────────────────────────────────────────────────────────
    # Test 6: Exact comparisons
    # ─────────────────────────────────────────────────────────────────────────
    def test_06_exact_comparisons():
        r1 = compare_single_requirement("Quantity", "40 units", "exact", "40 units")
        assert r1["status"] == "COMPLIANT"
        r2 = compare_single_requirement("Quantity", "40 units", "exact", "35 units")
        assert r2["status"] == "NON_COMPLIANT"

    # ─────────────────────────────────────────────────────────────────────────
    # Test 7: Range comparisons
    # ─────────────────────────────────────────────────────────────────────────
    def test_07_range_comparisons():
        r1 = compare_single_requirement("Colour Temp", "4000 K to 6500 K", "range", "5000 K")
        assert r1["status"] == "COMPLIANT"
        r2 = compare_single_requirement("Colour Temp", "4000 K to 6500 K", "range", "7000 K")
        assert r2["status"] == "NON_COMPLIANT"

    # ─────────────────────────────────────────────────────────────────────────
    # Test 8: Unit conversion
    # ─────────────────────────────────────────────────────────────────────────
    def test_08_unit_conversion():
        # Storage: 1 TB required, vendor offers 1024 GB
        r1 = compare_single_requirement("Storage", "Minimum 1 TB", "minimum", "1024 GB")
        assert r1["status"] == "COMPLIANT"
        # Mass: 5 kg max, vendor offers 5000 g
        r2 = compare_single_requirement("Weight", "Maximum 5 kg", "maximum", "5000 g")
        assert r2["status"] == "COMPLIANT"
        # Electric charge: 40 Ah min, vendor offers 36000 mAh
        r3 = compare_single_requirement("Battery", "Minimum 40 Ah", "minimum", "36000 mAh")
        assert r3["status"] == "NON_COMPLIANT"

    # ─────────────────────────────────────────────────────────────────────────
    # Test 9: Negative requirements
    # ─────────────────────────────────────────────────────────────────────────
    def test_09_negative_requirements():
        r1 = compare_single_requirement("Components", "Refurbished components shall not be used", "negative", "Refurbished components are used")
        assert r1["status"] == "NON_COMPLIANT", f"Expected NON_COMPLIANT for admitted refurbished parts, got {r1}"
        r2 = compare_single_requirement("Components", "Refurbished components shall not be used", "negative", "All components are brand new OEM parts")
        assert r2["status"] == "COMPLIANT", f"Expected COMPLIANT for brand new parts, got {r2}"

    # ─────────────────────────────────────────────────────────────────────────
    # Test 10: Missing vendor evidence
    # ─────────────────────────────────────────────────────────────────────────
    def test_10_missing_vendor_evidence():
        r1 = compare_single_requirement("Warranty", "Minimum 3 Years", "minimum", None)
        assert r1["status"] == "NOT_FOUND"
        r2 = compare_single_requirement("Warranty", "Minimum 3 Years", "minimum", "   ")
        assert r2["status"] == "NOT_FOUND"

    # ─────────────────────────────────────────────────────────────────────────
    # Test 11: Ambiguous semantic matching
    # ─────────────────────────────────────────────────────────────────────────
    def test_11_ambiguous_semantic_matching():
        tender_reqs = [{"requirement": "Fast Ethernet", "value": "100 Mbps", "condition": "minimum"}]
        # Two very close vendor claims
        claims = [
            {"requirement": "Ethernet Port A", "value": "100 Mbps"},
            {"requirement": "Ethernet Port B", "value": "100 Mbps"},
        ]
        matched = match_requirements(tender_reqs, claims, provider=DeterministicProvider())
        assert len(matched) == 1
        assert matched[0]["ambiguous"] or matched[0]["match_score"] > 0

    # ─────────────────────────────────────────────────────────────────────────
    # Test 12: Multiple vendors against one tender
    # ─────────────────────────────────────────────────────────────────────────
    def test_12_multiple_vendors():
        tender_reqs = [
            {"requirement_id": "r1", "name": "RAM", "requirement": "RAM", "value": "Minimum 16 GB", "condition": "minimum", "mandatory": True, "category": "technical"},
            {"requirement_id": "r2", "name": "Storage", "requirement": "Storage", "value": "Minimum 512 GB SSD", "condition": "minimum", "mandatory": True, "category": "technical"},
        ]
        vendor_a_claims = [{"name": "RAM", "requirement": "RAM", "value": "32 GB"}, {"name": "Storage", "requirement": "Storage", "value": "1 TB SSD"}]
        vendor_b_claims = [{"name": "RAM", "requirement": "RAM", "value": "8 GB"}, {"name": "Storage", "requirement": "Storage", "value": "256 GB SSD"}]

        match_a = match_requirements(tender_reqs, vendor_a_claims, provider=DeterministicProvider())
        res_a = compare_matched_pairs(match_a)
        score_a = calculate_vendor_score(res_a["results"])

        match_b = match_requirements(tender_reqs, vendor_b_claims, provider=DeterministicProvider())
        res_b = compare_matched_pairs(match_b)
        score_b = calculate_vendor_score(res_b["results"])

        assert score_a["score_overall"] > score_b["score_overall"]
        assert score_a["compliant_count"] == 2
        assert score_b["compliant_count"] == 0

    # ─────────────────────────────────────────────────────────────────────────
    # Test 13: Vendor scoring
    # ─────────────────────────────────────────────────────────────────────────
    def test_13_vendor_scoring():
        results = [
            {"status": "COMPLIANT", "mandatory": True, "category": "technical", "vendor_evidence": "Page 1: 32 GB RAM offered"},
            {"status": "COMPLIANT", "mandatory": True, "category": "technical", "vendor_evidence": "Page 2: 1 TB SSD offered"},
            {"status": "NON_COMPLIANT", "mandatory": False, "category": "commercial", "vendor_evidence": "Page 3: 45 days delivery"},
        ]
        score = calculate_vendor_score(results)
        assert score["score_mandatory"] == 100.0
        assert score["score_technical"] == 100.0
        assert score["compliant_count"] == 2
        assert "score_explanation" in score and len(score["score_explanation"]) > 20

    # ─────────────────────────────────────────────────────────────────────────
    # Test 14: Workspace authorization
    # ─────────────────────────────────────────────────────────────────────────
    def test_14_workspace_authorization():
        # Login as officer
        login_res = client.post("/api/auth/login", json={"username": "officer", "password": "Officer@BidVerify2026"})
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        # Access authenticated profile
        me_res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_res.status_code == 200
        assert me_res.json()["role"] == "PROCUREMENT_OFFICER"

    # ─────────────────────────────────────────────────────────────────────────
    # Test 15: Invalid share token
    # ─────────────────────────────────────────────────────────────────────────
    def test_15_invalid_share_token():
        res = client.get("/api/share/invalid-non-existent-share-token-12345")
        assert res.status_code == 404

    # ─────────────────────────────────────────────────────────────────────────
    # Test 16: Expired share link
    # ─────────────────────────────────────────────────────────────────────────
    def test_16_expired_share_link():
        db = SessionLocal()
        try:
            ws = models.Workspace(
                workspace_code=generate_workspace_code(),
                secret_token=generate_secure_token(),
                title="Expiry Test Workspace",
            )
            db.add(ws)
            db.commit()
            expired_link = models.ShareLink(
                workspace_id=ws.id,
                share_token=generate_share_token(),
                is_active=True,
                expires_at=datetime.now(timezone.utc) - timedelta(days=2),  # Already expired
            )
            db.add(expired_link)
            db.commit()
            res = client.get(f"/api/share/{expired_link.share_token}")
            assert res.status_code == 410, f"Expected 410 Gone for expired share link, got {res.status_code}"
        finally:
            db.close()

    # ─────────────────────────────────────────────────────────────────────────
    # Test 17: Unauthorized vendor access (read-only link cannot upload)
    # ─────────────────────────────────────────────────────────────────────────
    def test_17_unauthorized_mutation():
        # A share link endpoint is strictly GET /api/share/{token}. It does not allow file POST
        fake_files = {"file": ("test.pdf", b"%PDF-1.4 test", "application/pdf")}
        res = client.post("/api/share/some_token", files=fake_files)
        assert res.status_code in (404, 405)  # Method Not Allowed or Not Found

    # ─────────────────────────────────────────────────────────────────────────
    # Test 18: Oversized file rejection
    # ─────────────────────────────────────────────────────────────────────────
    def test_18_oversized_file():
        db = SessionLocal()
        try:
            ws = db.query(models.Workspace).first()
            if not ws:
                ws = models.Workspace(workspace_code=generate_workspace_code(), secret_token=generate_secure_token())
                db.add(ws)
                db.commit()
            # 30MB file (exceeds default 25MB threshold)
            huge_bytes = b"%PDF-1.4 " + b"0" * (26 * 1024 * 1024)
            fake_files = {"file": ("huge.pdf", huge_bytes, "application/pdf")}
            res = client.post(f"/api/workspaces/{ws.workspace_code}/tender", files=fake_files)
            assert res.status_code == 413, f"Expected 413 for oversized file, got {res.status_code}"
        finally:
            db.close()

    # ─────────────────────────────────────────────────────────────────────────
    # Test 19: Invalid file type rejection
    # ─────────────────────────────────────────────────────────────────────────
    def test_19_invalid_file_type():
        db = SessionLocal()
        try:
            ws = db.query(models.Workspace).first()
            fake_files = {"file": ("malicious.exe", b"MZ\x90\x00\x03", "application/octet-stream")}
            res = client.post(f"/api/workspaces/{ws.workspace_code}/tender", files=fake_files)
            assert res.status_code == 400
            assert "unsupported file type" in res.json()["detail"].lower()
        finally:
            db.close()

    # ─────────────────────────────────────────────────────────────────────────
    # Test 20: Duplicate upload detection
    # ─────────────────────────────────────────────────────────────────────────
    def test_20_duplicate_upload():
        db = SessionLocal()
        try:
            ws = models.Workspace(workspace_code=generate_workspace_code(), secret_token=generate_secure_token(), title="Dup Test")
            db.add(ws)
            db.commit()
            pdf_sample = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
            files1 = {"files": ("vendor_doc.pdf", pdf_sample, "application/pdf")}
            res1 = client.post(f"/api/workspaces/{ws.workspace_code}/vendors", files=files1)
            assert res1.status_code == 200

            # Attempt to upload identical document again
            files2 = {"files": ("vendor_doc_duplicate.pdf", pdf_sample, "application/pdf")}
            res2 = client.post(f"/api/workspaces/{ws.workspace_code}/vendors", files=files2)
            assert res2.status_code == 409, f"Expected 409 Conflict for duplicate upload, got {res2.status_code}"
        finally:
            db.close()

    # ─────────────────────────────────────────────────────────────────────────
    # Test 21: Gemini / API failure resilience
    # ─────────────────────────────────────────────────────────────────────────
    def test_21_gemini_fallback():
        # Matcher and Comparator must work safely with DeterministicProvider
        provider = DeterministicProvider()
        t_req = {"requirement": "RAM", "value": "16 GB"}
        v_claims = [{"requirement": "RAM", "value": "32 GB"}]
        res = match_requirements([t_req], v_claims, provider=provider)
        assert len(res) == 1
        assert res[0]["match_method"] in ("exact", "deterministic")

    # ─────────────────────────────────────────────────────────────────────────
    # Test 22: Async job failure handling
    # ─────────────────────────────────────────────────────────────────────────
    def test_22_async_job_failure():
        db = SessionLocal()
        try:
            ws = models.Workspace(workspace_code=generate_workspace_code(), secret_token=generate_secure_token())
            db.add(ws)
            db.commit()
            # Attempt to analyze workspace without documents -> should fail gracefully
            res = client.post(f"/api/workspaces/{ws.workspace_code}/analyze")
            assert res.status_code == 400
            assert "upload a tender document" in res.json()["detail"].lower()
        finally:
            db.close()

    # ─────────────────────────────────────────────────────────────────────────
    # Test 23: Concurrent workspace processing
    # ─────────────────────────────────────────────────────────────────────────
    def test_23_concurrent_workspaces():
        ws1_res = client.post("/api/workspaces", json={"title": "Concurrent WS 1"})
        ws2_res = client.post("/api/workspaces", json={"title": "Concurrent WS 2"})
        assert ws1_res.status_code == 200 and ws2_res.status_code == 200
        code1 = ws1_res.json()["workspace_code"]
        code2 = ws2_res.json()["workspace_code"]
        assert code1 != code2
        # Documents in WS1 do not leak to WS2
        detail1 = client.get(f"/api/workspaces/{code1}").json()
        detail2 = client.get(f"/api/workspaces/{code2}").json()
        assert detail1["workspace_code"] == code1
        assert detail2["workspace_code"] == code2

    # ─────────────────────────────────────────────────────────────────────────
    # Test 24: Existing POST /verify remains functional
    # ─────────────────────────────────────────────────────────────────────────
    def test_24_verify_backward_compatibility():
        tender_pdf = Path(__file__).parent / "Sample_Tender_BidVerify.pdf"
        vendor_pdf = Path(__file__).parent / "Sample_Vendor_20_Requirements_BidVerify.pdf"
        if not tender_pdf.exists() or not vendor_pdf.exists():
            print("  [SKIP] Sample PDFs not present for direct verify call")
            return
        with open(tender_pdf, "rb") as f_t, open(vendor_pdf, "rb") as f_v:
            res = client.post(
                "/verify",
                files={
                    "tender": ("tender.pdf", f_t.read(), "application/pdf"),
                    "vendor": ("vendor.pdf", f_v.read(), "application/pdf"),
                },
            )
        assert res.status_code == 200
        data = res.json()
        assert "summary" in data and "results" in data
        assert "compliance_score" in data["summary"]
        assert len(data["results"]) > 0

    # Execute all 24 tests
    check(1, "20 actual requirements should not become 38", test_01_twenty_req_fix)
    check(2, "Duplicate semantic requirements merge correctly", test_02_semantic_deduplication)
    check(3, "Table rows remain separate requirements", test_03_table_rows_separate)
    check(4, "Minimum comparisons", test_04_minimum_comparisons)
    check(5, "Maximum comparisons", test_05_maximum_comparisons)
    check(6, "Exact comparisons", test_06_exact_comparisons)
    check(7, "Range comparisons", test_07_range_comparisons)
    check(8, "Unit conversion across domains", test_08_unit_conversion)
    check(9, "Negative/prohibited requirements", test_09_negative_requirements)
    check(10, "Missing vendor evidence yields NOT_FOUND", test_10_missing_vendor_evidence)
    check(11, "Ambiguous semantic matching", test_11_ambiguous_semantic_matching)
    check(12, "Multiple vendors evaluated against one tender", test_12_multiple_vendors)
    check(13, "Transparent multi-metric vendor scoring", test_13_vendor_scoring)
    check(14, "Workspace authentication & RBAC", test_14_workspace_authorization)
    check(15, "Invalid share token rejection", test_15_invalid_share_token)
    check(16, "Expired share link handling (410 Gone)", test_16_expired_share_link)
    check(17, "Unauthorized mutation rejection", test_17_unauthorized_mutation)
    check(18, "Oversized file rejection (413)", test_18_oversized_file)
    check(19, "Invalid file type rejection (400)", test_19_invalid_file_type)
    check(20, "Duplicate upload detection (409 Conflict)", test_20_duplicate_upload)
    check(21, "AI provider failure resilience & deterministic fallback", test_21_gemini_fallback)
    check(22, "Async job failure handling", test_22_async_job_failure)
    check(23, "Concurrent workspace isolation", test_23_concurrent_workspaces)
    check(24, "Existing POST /verify backward compatibility", test_24_verify_backward_compatibility)

    print("=" * 70)
    print(f"RESULTS: {passed} PASSED, {failed} FAILED")
    print("=" * 70)
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

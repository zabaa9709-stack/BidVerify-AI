import json
import os
import time
import requests

BASE_URL = "http://127.0.0.1:8000"

def run_e2e_live_test():
    print("=== LIVE SERVER E2E INTEGRATION TEST ===")
    
    # 1. Login as procurement officer
    res = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "officer", "password": "Officer@BidVerify2026"})
    assert res.status_code == 200, f"Login failed: {res.text}"
    auth_info = res.json()
    token = auth_info["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print(f"[OK] Logged in as officer. Role: {auth_info['user']['role']}. Token obtained.")

    # 2. Create Workspace
    ws_res = requests.post(
        f"{BASE_URL}/api/workspaces",
        json={
            "title": "Procurement of High-Performance Laptops & Workstations",
            "gem_bid_number": "GEM/2026/B/771100"
        },
        headers=headers
    )
    assert ws_res.status_code == 200, f"Create workspace failed: {ws_res.text}"
    ws = ws_res.json()
    ws_code = ws["workspace_code"]
    print(f"[OK] Created Workspace: Code={ws_code}, ID={ws['id']}, Title='{ws['title']}'")

    # 3. Upload Tender Document (Sample_Tender_20_Requirements_BidVerify.pdf)
    tender_file_path = os.path.join(os.path.dirname(__file__), "Sample_Tender_20_Requirements_BidVerify.pdf")
    with open(tender_file_path, "rb") as f:
        tender_res = requests.post(
            f"{BASE_URL}/api/workspaces/{ws_code}/tender",
            files={"file": ("Sample_Tender_20_Requirements_BidVerify.pdf", f, "application/pdf")},
            headers=headers
        )
    assert tender_res.status_code == 200, f"Tender upload failed: {tender_res.text}"
    tender_data = tender_res.json()
    print(f"[OK] Uploaded Tender: {tender_data['requirements_count']} requirements extracted!")
    assert tender_data['requirements_count'] == 20, f"Expected 20 requirements, got {tender_data['requirements_count']}"

    # 4. Upload Vendor Document (Sample_Vendor_20_Requirements_BidVerify.pdf)
    vendor_file_path = os.path.join(os.path.dirname(__file__), "Sample_Vendor_20_Requirements_BidVerify.pdf")
    with open(vendor_file_path, "rb") as f:
        vendor_res = requests.post(
            f"{BASE_URL}/api/workspaces/{ws_code}/vendors",
            files={"files": ("Vendor_Alpha_Bid.pdf", f, "application/pdf")},
            headers=headers
        )
    assert vendor_res.status_code == 200, f"Vendor upload failed: {vendor_res.text}"
    v_data = vendor_res.json()
    print(f"[OK] Uploaded Vendor bid: {len(v_data['documents'])} document(s) staged.")
    assert len(v_data['documents']) >= 1

    # 5. Trigger Multi-Vendor Verification Pipeline
    job_res = requests.post(f"{BASE_URL}/api/workspaces/{ws_code}/analyze", headers=headers)
    assert job_res.status_code == 200, f"Job trigger failed: {job_res.text}"
    job = job_res.json()
    job_id = job["job_id"]
    print(f"[OK] Verification job dispatched: ID={job_id}, Initial Stage={job['stage']}")

    # 6. Poll Job Completion through the 10 stages
    for _ in range(30):
        j_res = requests.get(f"{BASE_URL}/api/jobs/{job_id}", headers=headers)
        j_status = j_res.json()
        print(f"  -> Job Status: {j_status['status']}, Stage: {j_status['stage']} ({j_status['progress_pct']}%)")
        if j_status["status"] in ("COMPLETED", "FAILED"):
            break
        time.sleep(0.5)

    assert j_status["status"] == "COMPLETED", f"Job did not complete: {j_status.get('error_message')}"
    print("[OK] Multi-Vendor Pipeline completed successfully through all 10 stages!")

    # 7. Check Multi-Vendor Comparison Dashboard
    comp_res = requests.get(f"{BASE_URL}/api/workspaces/{ws_code}/comparison", headers=headers)
    assert comp_res.status_code == 200
    comparison = comp_res.json()
    vendors = comparison["vendors"]
    print(f"[OK] Retrieved Comparison: {len(vendors)} vendor(s) ranked.")
    for idx, v in enumerate(vendors, 1):
        print(f"    - Rank {idx}: {v['vendor_name']} | Overall: {v['score_overall']}% | Mandatory: {v['score_mandatory']}%")

    # 8. Check Cross-Vendor Matrix
    matrix_rows = comparison["matrix"]
    print(f"[OK] Cross-Vendor Matrix: {len(matrix_rows)} requirement rows across {len(vendors)} vendor(s).")
    assert len(matrix_rows) == 20, f"Expected 20 requirement rows in matrix, got {len(matrix_rows)}"

    # 9. Create Share Link
    share_res = requests.post(f"{BASE_URL}/api/workspaces/{ws_code}/share", json={"expires_in_hours": 24}, headers=headers)
    assert share_res.status_code == 200
    share = share_res.json()
    share_token = share["share_token"]
    print(f"[OK] Generated Share Link Token: {share_token} (URL: {share['share_url']})")

    # Access Read-Only Public Share endpoint (no Authorization header required)
    pub_res = requests.get(f"{BASE_URL}/api/share/{share_token}")
    assert pub_res.status_code == 200
    share_view = pub_res.json()
    print(f"[OK] Accessed Read-Only Share View: {share_view['title']} (Code: {share_view['workspace_code']})")
    assert share_view["read_only"] is True
    assert len(share_view["report"]["matrix"]) == 20

    # 10. Export AI-Assisted Compliance Verification Report
    rep_res = requests.get(f"{BASE_URL}/api/workspaces/{ws_code}/report", headers=headers)
    assert rep_res.status_code == 200
    report_data = rep_res.json()
    report_md = report_data["markdown_report"]
    assert "AI-Assisted Compliance Verification Report" in report_md
    assert "Official Advisory Document" in report_md
    print(f"[OK] Report Export Verified (Length: {len(report_md)} chars with official GeM disclaimer)")

    # 11. Test Human Review Queue items
    review_res = requests.get(f"{BASE_URL}/api/workspaces/{ws_code}/review-queue", headers=headers)
    assert review_res.status_code == 200
    review_data = review_res.json()
    print(f"[OK] Human Review Queue: {review_data['total_pending']} items pending review out of {len(review_data['items'])} flagged items.")

    # 12. Test Legacy POST /verify endpoint compatibility
    with open(tender_file_path, "rb") as ft, open(vendor_file_path, "rb") as fv:
        legacy_res = requests.post(
            f"{BASE_URL}/verify",
            files={
                "tender": ("tender.pdf", ft, "application/pdf"),
                "vendor": ("vendor.pdf", fv, "application/pdf")
            }
        )
    assert legacy_res.status_code == 200
    legacy_data = legacy_res.json()
    print(f"[OK] Legacy POST /verify: {legacy_data['summary']['total']} requirements evaluated, score: {legacy_data['summary']['compliance_score']}%")

    print("\n" + "=" * 70)
    print(">>> ALL 12 LIVE END-TO-END VERIFICATION CHECKS PASSED PERFECTLY! <<<")
    print("=" * 70)

if __name__ == "__main__":
    run_e2e_live_test()

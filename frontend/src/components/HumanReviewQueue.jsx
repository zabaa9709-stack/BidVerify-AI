import { useState } from "react"

export default function HumanReviewQueue({
  reviewItems,
  onProcessAction,
  isReadOnly = false,
}) {
  const [activeItem, setActiveItem] = useState(null)
  const [actionType, setActionType] = useState("APPROVED")
  const [decisionReason, setDecisionReason] = useState("")
  const [complianceOverride, setComplianceOverride] = useState("COMPLIANT")
  const [submitting, setSubmitting] = useState(false)

  const handleOpenAction = (item, action) => {
    setActiveItem(item)
    setActionType(action)
    setDecisionReason("")
    setComplianceOverride(action === "APPROVED" ? "COMPLIANT" : (action === "REJECTED" ? "NON_COMPLIANT" : "NEEDS_REVIEW"))
  }

  const handleSubmit = async () => {
    if (!activeItem) return
    setSubmitting(true)
    try {
      await onProcessAction(activeItem.id, {
        status: actionType,
        decision_reason: decisionReason || `Officer review action: ${actionType}`,
        override_compliance_status: complianceOverride,
      })
      setActiveItem(null)
    } finally {
      setSubmitting(false)
    }
  }

  const [queueTab, setQueueTab] = useState("pending") // "pending" | "history"

  const pendingItems = (reviewItems || []).filter((i) => i.review_status === "PENDING")
  const reviewedItems = (reviewItems || []).filter((i) => i.review_status !== "PENDING")

  return (
    <div className="review-queue-card card-interactive reveal-on-scroll">
      <div className="stage-banner">
        <div className="banner-left">
          <span className="gov-seal-icon">🔍</span>
          <div>
            <div className="stage-eyebrow">HUMAN-IN-THE-LOOP CHECKPOINT</div>
            <h2 className="stage-title">Flagged Ambiguities & Verification Audit</h2>
            <p className="stage-sub">
              These items were flagged by the AI engine due to ambiguous semantic matches, borderline tolerances, or partial vendor claims. Procurement officers have final authority to approve, reject, or request clarification.
            </p>
          </div>
        </div>
        <div className="checkpoint-counts" style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <div
            className={`count-stat-pill ${queueTab === "pending" ? "active" : ""}`}
            style={{ cursor: "pointer", border: queueTab === "pending" ? "2px solid var(--primary-blue)" : "1px solid var(--border-subtle)" }}
            onClick={() => setQueueTab("pending")}
          >
            <span className="count-label">Pending Review</span>
            <strong className="count-val orange">{pendingItems.length}</strong>
          </div>
          {reviewedItems.length > 0 && (
            <div
              className={`count-stat-pill ${queueTab === "history" ? "active" : ""}`}
              style={{ cursor: "pointer", border: queueTab === "history" ? "2px solid var(--primary-blue)" : "1px solid var(--border-subtle)" }}
              onClick={() => setQueueTab("history")}
            >
              <span className="count-label">Audit History</span>
              <strong className="count-val green">{reviewedItems.length}</strong>
            </div>
          )}
        </div>
      </div>

      {/* Tabs Header */}
      <div style={{ display: "flex", gap: 10, borderBottom: "1px solid var(--border-subtle)", padding: "10px 16px", background: "var(--bg-main)" }}>
        <button
          className={`tab-btn ${queueTab === "pending" ? "active" : ""}`}
          onClick={() => setQueueTab("pending")}
          style={{
            padding: "6px 14px",
            fontSize: 13,
            fontWeight: 600,
            borderRadius: 6,
            border: "none",
            background: queueTab === "pending" ? "var(--primary-blue)" : "transparent",
            color: queueTab === "pending" ? "#fff" : "var(--text-secondary)",
            cursor: "pointer",
          }}
        >
          Pending Review ({pendingItems.length})
        </button>
        <button
          className={`tab-btn ${queueTab === "history" ? "active" : ""}`}
          onClick={() => setQueueTab("history")}
          style={{
            padding: "6px 14px",
            fontSize: 13,
            fontWeight: 600,
            borderRadius: 6,
            border: "none",
            background: queueTab === "history" ? "var(--primary-blue)" : "transparent",
            color: queueTab === "history" ? "#fff" : "var(--text-secondary)",
            cursor: "pointer",
          }}
        >
          Officer Audit Trail ({reviewedItems.length})
        </button>
      </div>

      {queueTab === "pending" && (
        <>
          {pendingItems.length === 0 ? (
            <div className="review-empty-state">
              <div className="empty-check-icon">✓</div>
              <h3>All Criteria Decisively Verified</h3>
              <p>There are currently no ambiguous claims requiring human intervention.</p>
            </div>
          ) : (
            <div className="review-items-list">
              {pendingItems.map((item) => (
                <div key={item.id} className="review-item-card stagger-card-1">
                  <div className="review-card-header">
                    <div className="review-title-group">
                      <span className="req-code-badge">{item.requirement_code || "REQ"}</span>
                      <strong className="review-req-name">{item.requirement_name}</strong>
                      <span className="review-vendor-pill">{item.vendor_name}</span>
                    </div>
                    <div className="review-status-chip">
                      <span className="status-pill status-needs-review">NEEDS REVIEW</span>
                    </div>
                  </div>

                  <div className="review-claims-grid">
                    <div className="claim-box tender-claim">
                      <div className="claim-label">TENDER REQUIRED SPECIFICATION</div>
                      <div className="claim-text">{item.tender_value || "—"}</div>
                      {item.tender_page && (
                        <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>
                          Source: Tender Page {item.tender_page}
                        </div>
                      )}
                    </div>
                    <div className="claim-box vendor-claim">
                      <div className="claim-label">OFFERED VENDOR CLAIM</div>
                      <div className="claim-text">{item.vendor_value || "Not Mentioned"}</div>
                      {item.vendor_page && (
                        <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>
                          Source: Vendor Bid Page {item.vendor_page}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="system-flag-note">
                    <span className="flag-reason-label">System Reason:</span>
                    <span className="flag-reason-text">{item.system_reason}</span>
                    <span className="flag-conf">Confidence: {Math.round((item.system_confidence || 0.65) * 100)}%</span>
                  </div>

                  {!isReadOnly ? (
                    <div className="review-card-actions">
                      <button
                        className="primary-btn sm-btn btn-press approve-btn"
                        onClick={() => handleOpenAction(item, "APPROVED")}
                      >
                        ✓ Approve as Compliant
                      </button>
                      <button
                        className="secondary-btn sm-btn btn-press reject-btn"
                        onClick={() => handleOpenAction(item, "REJECTED")}
                      >
                        ✗ Reject Claim
                      </button>
                      <button
                        className="outline-btn sm-btn btn-press clarify-btn"
                        onClick={() => handleOpenAction(item, "CLARIFICATION_REQUESTED")}
                      >
                        ? Request Clarification
                      </button>
                    </div>
                  ) : (
                    <div style={{ marginTop: 10, fontSize: 12, color: "var(--text-muted)", fontStyle: "italic" }}>
                      🔒 Read-only audit mode — officer review actions disabled.
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {queueTab === "history" && (
        <div className="review-items-list" style={{ padding: 16 }}>
          {reviewedItems.length === 0 ? (
            <div className="review-empty-state">
              <p>No reviewed items recorded in audit trail yet.</p>
            </div>
          ) : (
            reviewedItems.map((item) => {
              const isApproved = item.review_status === "APPROVED"
              const isRejected = item.review_status === "REJECTED"
              return (
                <div
                  key={item.id}
                  className="review-item-card"
                  style={{
                    borderLeft: isApproved ? "4px solid var(--accent-green)" : (isRejected ? "4px solid var(--accent-red)" : "4px solid var(--accent-orange)"),
                    marginBottom: 12,
                  }}
                >
                  <div className="review-card-header">
                    <div className="review-title-group">
                      <span className="req-code-badge">{item.requirement_code || "REQ"}</span>
                      <strong className="review-req-name">{item.requirement_name}</strong>
                      <span className="review-vendor-pill">{item.vendor_name}</span>
                    </div>
                    <div>
                      <span className={`status-pill ${isApproved ? "status-compliant" : (isRejected ? "status-non-compliant" : "status-needs-review")}`}>
                        {item.review_status}
                      </span>
                    </div>
                  </div>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, margin: "10px 0", fontSize: 12 }}>
                    <div><strong>Tender Requirement:</strong> {item.tender_value || "—"}</div>
                    <div><strong>Vendor Claim:</strong> {item.vendor_value || "—"}</div>
                  </div>

                  <div style={{ background: "#f8fafc", padding: "8px 12px", borderRadius: 6, fontSize: 12, color: "var(--text-secondary)", border: "1px solid var(--border-subtle)" }}>
                    <div><strong>Original AI Decision:</strong> {item.system_status || "NEEDS_REVIEW"} ({item.system_reason})</div>
                    <div style={{ marginTop: 4 }}><strong>Officer Justification:</strong> {item.decision_reason || "Decision recorded by procurement officer"}</div>
                    <div style={{ marginTop: 4, fontSize: 11, color: "var(--text-muted)" }}>
                      Audit Timestamp: {item.updated_at ? new Date(item.updated_at).toLocaleString() : (item.created_at ? new Date(item.created_at).toLocaleString() : "Recently verified")}
                    </div>
                  </div>
                </div>
              )
            })
          )}
        </div>
      )}

      {/* Review Modal Dialog */}
      {activeItem && (
        <div className="modal-backdrop opening" onClick={() => setActiveItem(null)}>
          <div className="review-action-modal card-interactive" onClick={(e) => e.stopPropagation()}>
            <div className="modal-hdr">
              <h3>Confirm Officer Review Action</h3>
              <button className="alert-close btn-press" onClick={() => setActiveItem(null)}>✕</button>
            </div>
            <div className="modal-content-stack">
              <p>
                Action: <strong>{actionType}</strong> for requirement <strong>{activeItem.requirement_name}</strong> ({activeItem.vendor_name})
              </p>
              <div className="input-group">
                <label>Compliance Decision Override:</label>
                <select
                  value={complianceOverride}
                  onChange={(e) => setComplianceOverride(e.target.value)}
                  className="cell-edit-select"
                >
                  <option value="COMPLIANT">Mark as COMPLIANT</option>
                  <option value="NON_COMPLIANT">Mark as NON-COMPLIANT</option>
                  <option value="NEEDS_REVIEW">Keep as NEEDS REVIEW</option>
                </select>
              </div>
              <div className="input-group">
                <label>Justification Note (Saved in Audit Trail):</label>
                <textarea
                  rows={3}
                  value={decisionReason}
                  onChange={(e) => setDecisionReason(e.target.value)}
                  placeholder="State the officer's technical justification for this decision..."
                  className="cell-edit-textarea"
                />
              </div>
            </div>
            <div className="modal-ftr">
              <button className="secondary-btn btn-press" onClick={() => setActiveItem(null)}>
                Cancel
              </button>
              <button
                className="primary-btn btn-press"
                onClick={handleSubmit}
                disabled={submitting}
              >
                {submitting ? "Saving..." : "Commit Officer Decision"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

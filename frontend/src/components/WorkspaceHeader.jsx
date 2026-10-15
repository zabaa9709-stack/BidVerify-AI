import React from "react"

export default function WorkspaceHeader({
  workspace,
  onShareClick,
  onExportClick,
  onNewWorkspace,
  onDeleteWorkspace,
  isReadOnly,
  onBackToDirectory,
  activeStep,
}) {
  if (!workspace) return null

  const effectiveStatus = workspace.derived_status || workspace.status || "ACTIVE"
  const getStatusClass = (st) => {
    switch (st) {
      case "ACTIVE": return "status-compliant"
      case "CLOSING_SOON": return "status-needs-review"
      case "CLOSED": return "status-non-compliant"
      case "UPCOMING": return "status-not-found"
      default: return "status-not-found"
    }
  }

  return (
    <>
      <div className="workspace-header-bar card-interactive reveal-on-scroll">
        <div className="ws-meta-left">
          {onBackToDirectory && (
            <button
              className="action-btn btn-press"
              onClick={onBackToDirectory}
              title="Return to Tender Directory"
              style={{ marginRight: 6 }}
            >
              ← All Tenders
            </button>
          )}
          <div className="ws-code-chip">
            <span className="ws-code-label">TENDER ID</span>
            <strong className="ws-code-value">{workspace.workspace_code}</strong>
          </div>
          <div className="ws-title-block">
            <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <h2 className="ws-title">{workspace.title}</h2>
              {workspace.tender_reference && (
                <span className="nav-code-pill" style={{ fontSize: 12 }}>
                  Ref: {workspace.tender_reference}
                </span>
              )}
            </div>
            <div className="ws-sub-info">
              <span className={`status-pill ${getStatusClass(effectiveStatus)}`}>
                ● {effectiveStatus.replace("_", " ")}
              </span>
              {workspace.start_date && (
                <>
                  <span>•</span>
                  <span>Start: <strong>{new Date(workspace.start_date).toLocaleDateString()}</strong></span>
                </>
              )}
              {workspace.closing_date && (
                <>
                  <span>•</span>
                  <span>Closing: <strong>{new Date(workspace.closing_date).toLocaleDateString()}</strong></span>
                </>
              )}
            </div>
          </div>
        </div>

      <div className="ws-actions-right">
        <button
          className="secondary-btn btn-press sm-btn"
          onClick={onShareClick}
          title="Create secure read-only share link"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/>
            <polyline points="16 6 12 2 8 6"/>
            <line x1="12" y1="2" x2="12" y2="15"/>
          </svg>
          <span>Share Link</span>
        </button>

        <button
          className="secondary-btn btn-press sm-btn"
          onClick={onExportClick}
          title="Export AI-Assisted Compliance Verification Report"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
            <polyline points="7 10 12 15 17 10"/>
            <line x1="12" y1="15" x2="12" y2="3"/>
          </svg>
          <span>Export Report</span>
        </button>

        <button
          className="outline-btn btn-press sm-btn"
          onClick={onNewWorkspace}
          title="Create a new procurement workspace"
        >
          <span>+ New Tender</span>
        </button>

        {!isReadOnly && onDeleteWorkspace && (
          <button
            className="outline-btn btn-press sm-btn delete-ws-btn"
            style={{ borderColor: "#ef4444", color: "#ef4444" }}
            onClick={onDeleteWorkspace}
            title="Delete this tender workspace"
          >
            <span>🗑 Delete Tender</span>
          </button>
        )}
      </div>
    </div>

    {effectiveStatus === "CLOSED" && (
      <div className="alert-box alert-error" style={{ marginBottom: 20 }}>
        <div className="alert-icon">🔒</div>
        <div className="alert-body">
          <strong>Tender Submission Closed:</strong> This procurement tender closed on {workspace.closing_date ? new Date(workspace.closing_date).toLocaleDateString() : "the deadline"}. New vendor proposal submissions are disabled. Verified results and audit records are permanently retained for review.
        </div>
      </div>
    )}
  </>
  )
}

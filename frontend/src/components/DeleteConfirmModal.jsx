import React from "react"

export default function DeleteConfirmModal({
  isOpen,
  tender,
  onClose,
  onConfirm,
  isDeleting,
  error,
}) {
  if (!isOpen || !tender) return null

  return (
    <div className="modal-backdrop opening" onClick={onClose}>
      <div
        className="share-modal-card card-interactive"
        style={{ maxWidth: 540 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-hdr">
          <div className="hdr-title-lockup">
            <div
              className="brand-logo-badge"
              style={{
                width: 38,
                height: 38,
                borderRadius: 8,
                background: "rgba(239, 68, 68, 0.12)",
                color: "#ef4444",
                fontSize: 18,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              🗑️
            </div>
            <div>
              <h3 style={{ color: "#ef4444", margin: 0 }}>Delete Tender Workspace</h3>
              <p className="modal-sub" style={{ margin: "2px 0 0" }}>
                Confirm permanent removal of procurement workspace.
              </p>
            </div>
          </div>
          <button
            type="button"
            className="alert-close btn-press"
            onClick={onClose}
            disabled={isDeleting}
          >
            ✕
          </button>
        </div>

        <div className="modal-content-stack" style={{ padding: "16px 20px" }}>
          {error && (
            <div className="alert-box alert-error" style={{ marginBottom: 14 }}>
              <div className="alert-icon">⚠️</div>
              <div className="alert-body">
                <strong>Deletion Failed:</strong> {error}
              </div>
            </div>
          )}

          <div
            style={{
              background: "#fef2f2",
              border: "1px solid #fecaca",
              borderRadius: 8,
              padding: "12px 16px",
              marginBottom: 16,
            }}
          >
            <div style={{ fontSize: 13, color: "#991b1b", fontWeight: 700, marginBottom: 4 }}>
              {tender.title}
            </div>
            <div style={{ fontSize: 12, color: "#b91c1c" }}>
              ID: <strong>{tender.workspace_code}</strong>
              {tender.tender_reference && ` • Ref: ${tender.tender_reference}`}
            </div>
          </div>

          <p style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.5, margin: "0 0 10px" }}>
            This action is irreversible. The tender <strong>OWNER</strong> authority will verify ownership and permanently delete this workspace and all associated:
          </p>

          <ul
            style={{
              fontSize: 12.5,
              color: "var(--text-primary)",
              margin: 0,
              paddingLeft: 20,
              lineHeight: 1.8,
              background: "#f8fafc",
              border: "1px solid var(--border-subtle)",
              borderRadius: 8,
              padding: "10px 16px 10px 30px",
            }}
          >
            <li>Vendor bid submissions & uploaded technical documents</li>
            <li>Extracted tender requirements & curation history</li>
            <li>Side-by-side evidence citations & source page records</li>
            <li>Compliance verification results & evaluation findings</li>
            <li>Multi-vendor scores, rankings & comparative matrix</li>
            <li>Human review queue items & officer audit trail</li>
            <li>All tender workspace configuration & active share links</li>
          </ul>
        </div>

        <div
          className="modal-ftr"
          style={{
            padding: "14px 20px",
            borderTop: "1px solid var(--border-subtle)",
            display: "flex",
            justifyContent: "flex-end",
            gap: 10,
          }}
        >
          <button
            type="button"
            className="secondary-btn btn-press"
            onClick={onClose}
            disabled={isDeleting}
          >
            Cancel
          </button>
          <button
            type="button"
            className="primary-btn btn-press"
            style={{
              background: "#dc2626",
              borderColor: "#dc2626",
              color: "#fff",
            }}
            onClick={onConfirm}
            disabled={isDeleting}
          >
            {isDeleting ? "Deleting Workspace..." : "Confirm & Delete Tender"}
          </button>
        </div>
      </div>
    </div>
  )
}

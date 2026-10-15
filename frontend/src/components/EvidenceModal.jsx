import { useEffect, useState, useCallback } from "react"

export default function EvidenceModal({ item, onClose }) {
  const [isClosing, setIsClosing] = useState(false)

  const handleTriggerClose = useCallback(() => {
    setIsClosing(true)
    setTimeout(() => {
      onClose()
    }, 240)
  }, [onClose])

  // Allow closing with Escape key
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape") {
        handleTriggerClose()
      }
    }
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [handleTriggerClose])

  const getStatusColor = (status) => {
    switch (status) {
      case "COMPLIANT": return "status-compliant"
      case "NON_COMPLIANT": return "status-non-compliant"
      case "NOT_FOUND": return "status-not-found"
      case "NEEDS_REVIEW": return "status-needs-review"
      default: return ""
    }
  }

  return (
    <div
      className={`modal-backdrop ${isClosing ? "closing" : "opening"}`}
      onClick={handleTriggerClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="evidence-drawer-title"
    >
      <div
        className={`evidence-drawer ${isClosing ? "drawer-closing" : "drawer-opening"}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="drawer-header stagger-header">
          <div className="drawer-title-group">
            <span className="drawer-badge">AUDIT EVIDENCE VIEWER</span>
            <h2 id="evidence-drawer-title" className="drawer-title">{item.requirement}</h2>
            <div className="drawer-submeta">
              <span>Category: <strong>{item.category || "Technical"}</strong></span>
              <span>•</span>
              <span>Condition: <strong>{item.condition || "Mandatory"}</strong></span>
            </div>
          </div>
          <button
            className="drawer-close-btn btn-press micro-rotate"
            onClick={handleTriggerClose}
            title="Close panel"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        <div className="drawer-body">
          {/* Decision Summary Box */}
          <div className={`decision-callout ${getStatusColor(item.status)} stagger-card-1`}>
            <div className="decision-top">
              <span className="decision-label">EVALUATION DECISION</span>
              <span className="decision-status-pill status-pop">{item.status}</span>
            </div>
            <p className="decision-reason">{item.reason}</p>
            <div className="decision-confidence">
              <span>System Confidence:</span>
              <div className="confidence-meter-pill">
                <div
                  className="confidence-fill-line"
                  style={{
                    width: `${typeof item.confidence === "number" ? Math.round(item.confidence * 100) : 90}%`
                  }}
                />
                <strong>{typeof item.confidence === "number" ? `${Math.round(item.confidence * 100)}%` : item.confidence}</strong>
              </div>
            </div>
          </div>

          {/* Comparative Specifications */}
          <div className="evidence-grid">
            {/* Tender Side */}
            <div className="evidence-card tender-evidence-card stagger-card-2">
              <div className="evidence-card-header">
                <span className="source-tag tender-source">TENDER SPECIFICATION</span>
                <span className="evidence-status-tag">Required</span>
              </div>
              <div className="spec-val-highlight">
                {item.required_value}
              </div>
              <div className="raw-evidence-box">
                <div className="evidence-box-label">EXTRACTED DOCUMENT SNIPPET / CLAUSE</div>
                <pre className="evidence-pre">
                  {item.tender_evidence || item.required_value}
                </pre>
              </div>
            </div>

            {/* Vendor Side */}
            <div className="evidence-card vendor-evidence-card stagger-card-3">
              <div className="evidence-card-header">
                <span className="source-tag vendor-source">VENDOR TECHNICAL BID</span>
                <span className="evidence-status-tag">Offered</span>
              </div>
              <div className={`spec-val-highlight ${item.status === "NON_COMPLIANT" ? "val-flagged" : ""}`}>
                {item.vendor_value || "Not Mentioned"}
              </div>
              <div className="raw-evidence-box">
                <div className="evidence-box-label">EXTRACTED VENDOR CLAIM EVIDENCE</div>
                <pre className="evidence-pre">
                  {item.vendor_evidence || item.vendor_value || "No corresponding technical claim identified in vendor document."}
                </pre>
              </div>
            </div>
          </div>

          <div className="evidence-note stagger-card-4">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#64748b" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10"/>
              <line x1="12" y1="16" x2="12" y2="12"/>
              <line x1="12" y1="8" x2="12.01" y2="8"/>
            </svg>
            <span>
              Evidence Grounding: Every result links directly to normalized clauses extracted from the official tender and vendor PDF artifacts.
            </span>
          </div>
        </div>

        <div className="drawer-footer">
          <button className="primary-btn outline-btn btn-press" onClick={handleTriggerClose}>
            Close Evidence Panel
          </button>
        </div>
      </div>
    </div>
  )
}

import React, { useState } from "react"

export default function MultiVendorUpload({
  stagedFiles,
  onAddFiles,
  onRemoveFile,
  onStartAnalysis,
  analyzing,
  onBackToRequirements,
  requirementsCount = 0,
  isClosed = false,
}) {
  const [dragActive, setDragActive] = useState(false)

  const handleDrag = (e) => {
    if (isClosed) return
    e.preventDefault()
    e.stopPropagation()
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true)
    } else if (e.type === "dragleave") {
      setDragActive(false)
    }
  }

  const handleDrop = (e) => {
    if (isClosed) return
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      onAddFiles(Array.from(e.dataTransfer.files))
    }
  }

  const handleFileInput = (e) => {
    if (isClosed) return
    if (e.target.files && e.target.files.length > 0) {
      onAddFiles(Array.from(e.target.files))
    }
  }

  return (
    <div className="multi-vendor-stage card-interactive reveal-on-scroll">
      <div className="stage-banner">
        <div className="banner-left">
          <span className="gov-seal-icon">📑</span>
          <div>
            <div className="stage-eyebrow">STAGE 3: MULTI-VENDOR INGESTION (PART 6)</div>
            <h2 className="stage-title">Add Vendor Bid Documents (1..N)</h2>
            <p className="stage-sub">
              Upload technical proposals from all participating bidders. Every vendor will be evaluated independently against the <strong>{requirementsCount} curated tender criteria</strong>.
            </p>
          </div>
        </div>
      </div>

      {/* Multi-file Dropzone */}
      <div
        className={`multi-dropzone ${dragActive ? "drag-active" : ""}`}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
      >
        <div className="dropzone-inner">
          <div className="drop-icon-circle">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="17 8 12 3 7 8"/>
              <line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
          </div>
          <h3 className="drop-heading">
            {isClosed ? "🔒 Vendor Submissions Closed" : "Drag & drop vendor proposals here"}
          </h3>
          <p className="drop-instruction">
            {isClosed
              ? "This tender is officially closed. No additional vendor proposals can be submitted."
              : "Supports multiple PDF and DOCX files (Vendor A, Vendor B, Vendor C...)"}
          </p>
          {!isClosed && (
            <label className="primary-btn browse-btn btn-press">
              <span>Browse Files</span>
              <input
                type="file"
                multiple
                accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                onChange={handleFileInput}
                style={{ display: "none" }}
                disabled={analyzing || isClosed}
              />
            </label>
          )}
        </div>
      </div>

      {/* Staged Vendors List */}
      <div className="staged-vendors-section">
        <div className="staged-header">
          <h4 className="staged-title">Staged Vendor Technical Bids ({stagedFiles.length})</h4>
          <span className="staged-badge">Ready for Comparative Pipeline</span>
        </div>

        {stagedFiles.length === 0 ? (
          <div className="empty-vendors-hint">
            No vendor proposals staged yet. Upload at least one vendor bid document to begin analysis.
          </div>
        ) : (
          <div className="vendor-chips-grid">
            {stagedFiles.map((file, idx) => (
              <div key={idx} className="vendor-file-card stagger-card-1">
                <div className="v-card-icon">
                  <span className="v-num-badge">V{idx + 1}</span>
                </div>
                <div className="v-card-details">
                  <strong className="v-card-name" title={file.name}>
                    {file.name}
                  </strong>
                  <span className="v-card-size">
                    {(file.size / 1024 / 1024).toFixed(2)} MB • {file.name.endsWith(".docx") ? "DOCX" : "PDF"}
                  </span>
                </div>
                <button
                  className="v-card-remove-btn btn-press"
                  onClick={() => onRemoveFile(idx)}
                  disabled={analyzing}
                  title="Remove document"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="stage-footer-actions">
        <button
          className="secondary-btn btn-press"
          onClick={onBackToRequirements}
          disabled={analyzing}
        >
          ← Back to Requirements
        </button>

        <button
          className="primary-btn lg-btn btn-press run-all-btn"
          onClick={onStartAnalysis}
          disabled={stagedFiles.length === 0 || analyzing}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="5 3 19 12 5 21 5 3"/>
          </svg>
          <span>
            {analyzing
              ? "Running Verification Pipeline..."
              : `Analyze All ${stagedFiles.length} Vendor${stagedFiles.length > 1 ? "s" : ""} Against Tender`}
          </span>
        </button>
      </div>
    </div>
  )
}

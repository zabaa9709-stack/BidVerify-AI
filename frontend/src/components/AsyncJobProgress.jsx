import React from "react"

const PIPELINE_STAGES = [
  { id: "UPLOAD_VALIDATION", label: "Upload Validation", step: 1 },
  { id: "DOCUMENT_PARSING", label: "Document Parsing", step: 2 },
  { id: "TENDER_REQUIREMENT_EXTRACTION", label: "Tender Extraction", step: 3 },
  { id: "REQUIREMENT_NORMALIZATION", label: "Requirement Normalization", step: 4 },
  { id: "VENDOR_EXTRACTION", label: "Vendor Extraction", step: 5 },
  { id: "SEMANTIC_MATCHING", label: "Semantic Matching", step: 6 },
  { id: "COMPLIANCE_VERIFICATION", label: "Rule Verification", step: 7 },
  { id: "EVIDENCE_INDEXING", label: "Evidence Indexing", step: 8 },
  { id: "SCORE_CALCULATION", label: "Score Calculation", step: 9 },
  { id: "REPORT_GENERATION", label: "Report Generation", step: 10 },
]

export default function AsyncJobProgress({ jobStatus }) {
  const currentStage = jobStatus?.stage || "UPLOAD_VALIDATION"
  const progressPct = jobStatus?.progress_pct || 0
  const message = jobStatus?.stage_message || "Initializing verification engine..."

  // Current stage index (0-based)
  const currentStageIdx = PIPELINE_STAGES.findIndex((s) => s.id === currentStage)
  const activeIndex = currentStageIdx !== -1 ? currentStageIdx : 0

  return (
    <div className="async-job-panel card-interactive reveal-on-scroll">
      <div className="job-header">
        <div className="job-title-group">
          <div className="pulse-spinner-circle"></div>
          <div>
            <div className="job-eyebrow">ASYNC BACKGROUND PIPELINE (PART 20)</div>
            <h3 className="job-heading">Multi-Vendor Compliance Engine Running</h3>
          </div>
        </div>
        <div className="job-pct-badge">{progressPct}%</div>
      </div>

      {/* Main Progress Bar */}
      <div className="real-progress-bar-track">
        <div
          className="real-progress-bar-fill animated-bar-fill"
          style={{ width: `${Math.min(Math.max(progressPct, 5), 100)}%` }}
        />
      </div>

      {/* Stage Status Message */}
      <div className="job-stage-status">
        <span className="pulse-dot online"></span>
        <span className="job-status-text">{message}</span>
      </div>

      {/* 10 Real Stages Breadcrumb */}
      <div className="pipeline-stages-grid">
        {PIPELINE_STAGES.map((st, i) => {
          const isDone = i < activeIndex || jobStatus?.status === "COMPLETED"
          const isCurrent = i === activeIndex && jobStatus?.status !== "COMPLETED"
          return (
            <div
              key={st.id}
              className={`stage-step-pill ${isDone ? "step-done" : isCurrent ? "step-current" : "step-pending"}`}
            >
              <div className="step-num-bubble">
                {isDone ? "✓" : st.step}
              </div>
              <span className="step-label">{st.label}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

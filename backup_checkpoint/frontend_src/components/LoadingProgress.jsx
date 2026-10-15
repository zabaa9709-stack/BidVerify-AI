import { useEffect, useState } from "react"

const STAGES = [
  { id: "01", label: "Reading Tender Document" },
  { id: "02", label: "Extracting Procurement Requirements" },
  { id: "03", label: "Reading Vendor Technical Bid" },
  { id: "04", label: "Normalizing Specifications & Units" },
  { id: "05", label: "Comparing Compliance Clauses" },
  { id: "06", label: "Building Evidence Grounded Report" }
]

export default function LoadingProgress() {
  const [activeStage, setActiveStage] = useState(0)

  useEffect(() => {
    const timer = setInterval(() => {
      setActiveStage((prev) => {
        if (prev < STAGES.length - 1) {
          return prev + 1
        }
        return prev
      })
    }, 750)
    return () => clearInterval(timer)
  }, [])

  const progressPercent = Math.min(((activeStage + 0.5) / STAGES.length) * 100, 95)

  return (
    <div className="processing-stepper-panel animate-in">
      <div className="stepper-header">
        <div className="stepper-badge">
          <span className="pulse-dot"></span>
          <span>COMPLIANCE ENGINE PROCESSING</span>
        </div>
        <h3 className="stepper-heading">Verifying Bid Compliance</h3>
        <p className="stepper-subheading">
          Deterministic evaluation of tender specifications against vendor proposal
        </p>
      </div>

      {/* Progress Track */}
      <div className="stepper-progress-track">
        <div
          className="stepper-progress-bar"
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      {/* Stages Stepper */}
      <div className="stepper-stage-list">
        {STAGES.map((stage, idx) => {
          const isDone = idx < activeStage
          const isCurrent = idx === activeStage

          return (
            <div
              key={stage.id}
              className={`stepper-stage-item ${
                isDone ? "stage-done" : isCurrent ? "stage-active" : "stage-pending"
              }`}
            >
              <div className="stage-indicator">
                {isDone ? (
                  <svg className="stage-check-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12"/>
                  </svg>
                ) : isCurrent ? (
                  <span className="stage-spinner-ring"></span>
                ) : (
                  <span className="stage-num-text">{stage.id}</span>
                )}
              </div>
              <div className="stage-label-group">
                <span className="stage-step-tag">STAGE {stage.id}</span>
                <span className="stage-name">{stage.label}</span>
              </div>
              {isCurrent && (
                <div className="stage-active-pill">In Progress</div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

import { useState, useEffect } from "react"
import Navbar from "./components/Navbar"
import UploadCard from "./components/UploadCard"
import SummaryCard from "./components/SummaryCard"
import ComplianceTable from "./components/ComplianceTable"
import EvidenceModal from "./components/EvidenceModal"
import LoadingProgress from "./components/LoadingProgress"
import EmptyState from "./components/EmptyState"

function useCountUp(target, duration = 650) {
  const [count, setCount] = useState(0)

  useEffect(() => {
    if (typeof target !== "number" || isNaN(target) || target <= 0) {
      return
    }

    let startTime = null
    let animationFrameId
    const startVal = 0

    const step = (timestamp) => {
      if (!startTime) startTime = timestamp
      const elapsed = timestamp - startTime
      const progress = Math.min(elapsed / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      const current = Math.round(startVal + (target - startVal) * eased)
      setCount(current)

      if (progress < 1) {
        animationFrameId = requestAnimationFrame(step)
      } else {
        setCount(target)
      }
    }

    animationFrameId = requestAnimationFrame(step)
    return () => cancelAnimationFrame(animationFrameId)
  }, [target, duration])

  if (typeof target !== "number" || isNaN(target) || target <= 0) {
    return target
  }

  return count
}

function App() {
  const [activeTab, setActiveTab] = useState("dashboard")
  const [tenderFile, setTenderFile] = useState(null)
  const [vendorFile, setVendorFile] = useState(null)
  const [verifying, setVerifying] = useState(false)
  const [verificationResult, setVerificationResult] = useState(null)
  const [verificationTimestamp, setVerificationTimestamp] = useState("")
  const [errorMessage, setErrorMessage] = useState("")
  const [selectedEvidenceItem, setSelectedEvidenceItem] = useState(null)
  const [scrollProgress, setScrollProgress] = useState(0)

  // Scroll Progress Listener
  useEffect(() => {
    const handleScroll = () => {
      const totalScroll = document.documentElement.scrollHeight - window.innerHeight
      if (totalScroll > 0) {
        const currentProgress = (window.scrollY / totalScroll) * 100
        setScrollProgress(currentProgress)
      } else {
        setScrollProgress(0)
      }
    }

    window.addEventListener("scroll", handleScroll, { passive: true })
    return () => window.removeEventListener("scroll", handleScroll)
  }, [])

  // Scroll reveal trigger on tab switch / content change
  useEffect(() => {
    // Scroll to top smoothly on section change
    window.scrollTo({ top: 0, behavior: "smooth" })

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("revealed")
            observer.unobserve(entry.target)
          }
        })
      },
      { threshold: 0.1, rootMargin: "0px 0px -30px 0px" }
    )

    const timer = setTimeout(() => {
      const elements = document.querySelectorAll(".reveal-on-scroll")
      elements.forEach((el) => observer.observe(el))
    }, 50)

    return () => {
      clearTimeout(timer)
      observer.disconnect()
    }
  }, [activeTab, verificationResult])

  const verifyDocuments = async () => {
    if (!tenderFile || !vendorFile) {
      setErrorMessage("Please stage both the official Tender PDF and the Vendor Bid PDF before verifying.")
      return
    }

    setVerifying(true)
    setErrorMessage("")

    const formData = new FormData()
    formData.append("tender", tenderFile)
    formData.append("vendor", vendorFile)

    try {
      const response = await fetch("http://127.0.0.1:8000/verify", {
        method: "POST",
        body: formData,
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || "Compliance verification failed. Please verify the documents.")
      }

      setVerificationResult(data)
      setVerificationTimestamp(new Date().toLocaleDateString("en-IN", {
        day: "numeric",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      }))
      setActiveTab("results")
    } catch (error) {
      console.error("Verification error:", error)
      setErrorMessage(error.message || "Unable to connect to the compliance engine. Make sure the backend server is online.")
    } finally {
      setVerifying(false)
    }
  }

  // Animated telemetry numbers for dashboard
  const telemetryTotal = useCountUp(verificationResult?.summary?.total)
  const telemetryCompliant = useCountUp(verificationResult?.summary?.compliant)
  const telemetryNonCompliant = useCountUp(verificationResult?.summary?.non_compliant)
  const telemetryNeedsReview = useCountUp(verificationResult?.summary?.needs_review)

  // Animated compliance percentage for results view
  const rawRatio = verificationResult?.summary?.total
    ? Math.round((verificationResult.summary.compliant / verificationResult.summary.total) * 100)
    : 0
  const animatedRatio = useCountUp(rawRatio)

  return (
    <div className="enterprise-app">
      {/* Top Navigation with Scroll Progress */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        hasResults={Boolean(verificationResult)}
        scrollProgress={scrollProgress}
      />

      <main className="main-wrapper">
        {/* ========================================================================= */}
        {/* 1. DASHBOARD VIEW                                                        */}
        {/* ========================================================================= */}
        {activeTab === "dashboard" && (
          <div className="dashboard-view view-transition animate-in">
            {/* Hero Banner */}
            <section className="dashboard-hero reveal-on-scroll">
              <div className="hero-content">
                <div className="hero-tag interactive-hover">
                  <span className="gov-seal-icon">🏛️</span>
                  <span>NATIONAL PUBLIC PROCUREMENT INTELLIGENCE</span>
                </div>
                <h1 className="hero-heading">
                  Verify Every Bid.
                  <br />
                  <span className="hero-accent">With Evidence.</span>
                </h1>
                <p className="hero-subheading">
                  AI-powered compliance verification for GeM procurement. Compare complex tender requirements
                  against vendor technical proposals and identify compliance risks with mathematical and clause-level certainty.
                </p>
                <div className="hero-actions">
                  <button
                    className="primary-btn lg-btn btn-press"
                    onClick={() => setActiveTab("new_verification")}
                  >
                    <span>+ Start New Verification</span>
                  </button>
                  {verificationResult && (
                    <button
                      className="secondary-btn lg-btn btn-press"
                      onClick={() => setActiveTab("results")}
                    >
                      <span>View Current Results ({verificationResult.summary?.total || 0})</span>
                      <svg className="arrow-icon-shift" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="5" y1="12" x2="19" y2="12"/>
                        <polyline points="12 5 19 12 12 19"/>
                      </svg>
                    </button>
                  )}
                </div>
              </div>

              {/* KPI Quick Overview */}
              <div className="dashboard-kpi-panel card-interactive">
                <div className="kpi-panel-header">
                  <h3>Compliance Telemetry</h3>
                  <span className="telemetry-badge">
                    {verificationResult ? (
                      <>
                        <span className="pulse-dot online"></span>
                        Live Session
                      </>
                    ) : (
                      "No Active Run"
                    )}
                  </span>
                </div>

                <div className="kpi-stat-stack">
                  <div className="stat-row">
                    <span className="stat-lbl">Requirements Checked</span>
                    <strong className="stat-val">
                      {verificationResult?.summary ? telemetryTotal : "—"}
                    </strong>
                  </div>
                  <div className="stat-row">
                    <span className="stat-lbl">Compliant Criteria</span>
                    <strong className="stat-val green">
                      {verificationResult?.summary ? telemetryCompliant : "—"}
                    </strong>
                  </div>
                  <div className="stat-row">
                    <span className="stat-lbl">Non-Compliant Gaps</span>
                    <strong className="stat-val red">
                      {verificationResult?.summary ? telemetryNonCompliant : "—"}
                    </strong>
                  </div>
                  <div className="stat-row">
                    <span className="stat-lbl">Needs Human Review</span>
                    <strong className="stat-val orange">
                      {verificationResult?.summary ? telemetryNeedsReview : "—"}
                    </strong>
                  </div>
                </div>

                {!verificationResult && (
                  <div className="kpi-empty-hint">
                    Upload documents to calculate live compliance metrics.
                  </div>
                )}
              </div>
            </section>

            {/* Workflow Pipeline */}
            <section className="workflow-section reveal-on-scroll">
              <div className="section-title-wrap">
                <span className="section-eyebrow">SYSTEM ARCHITECTURE</span>
                <h2 className="section-title">End-to-End Verification Pipeline</h2>
                <p className="section-sub">
                  How BidVerify AI inspects multi-page GeM procurement documents and produces audit-ready compliance matrices.
                </p>
              </div>

              <div className="workflow-grid">
                <div className="workflow-card card-interactive stagger-card-1">
                  <div className="workflow-step-num">01</div>
                  <div className="workflow-icon micro-icon">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                      <polyline points="17 8 12 3 7 8"/>
                      <line x1="12" y1="3" x2="12" y2="15"/>
                    </svg>
                  </div>
                  <h4>Ingest Documents</h4>
                  <p>Accepts official GeM tender PDFs and vendor technical bids with multi-page text extraction.</p>
                </div>

                <div className="workflow-card card-interactive stagger-card-2">
                  <div className="workflow-step-num">02</div>
                  <div className="workflow-icon micro-icon">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="11" cy="11" r="8"/>
                      <line x1="21" y1="21" x2="16.65" y2="16.65"/>
                    </svg>
                  </div>
                  <h4>Dynamic Extraction</h4>
                  <p>Parses structured tables, flattened columns, and inline clauses into normalized specifications.</p>
                </div>

                <div className="workflow-card card-interactive stagger-card-3">
                  <div className="workflow-step-num">03</div>
                  <div className="workflow-icon micro-icon">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                      <path d="m9 12 2 2 4-4"/>
                    </svg>
                  </div>
                  <h4>Rule Comparison</h4>
                  <p>Deterministic evaluation of minimums, maximums, hardware protocols, and warranty thresholds.</p>
                </div>

                <div className="workflow-card card-interactive stagger-card-4">
                  <div className="workflow-step-num">04</div>
                  <div className="workflow-icon micro-icon">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                      <polyline points="14 2 14 8 20 8"/>
                      <line x1="16" y1="13" x2="8" y2="13"/>
                      <line x1="16" y1="17" x2="8" y2="17"/>
                    </svg>
                  </div>
                  <h4>Evidence Audit</h4>
                  <p>Comprehensive matrix linking every decision to source document clauses and confidence scores.</p>
                </div>
              </div>
            </section>
          </div>
        )}

        {/* ========================================================================= */}
        {/* 2. NEW VERIFICATION VIEW                                                 */}
        {/* ========================================================================= */}
        {activeTab === "new_verification" && (
          <div className="new-verification-view view-transition animate-in">
            <div className="page-header-row reveal-on-scroll">
              <div>
                <button
                  className="nav-breadcrumb-btn btn-press"
                  onClick={() => setActiveTab("dashboard")}
                >
                  ← Back to Dashboard
                </button>
                <h1 className="page-title">New Bid Verification</h1>
                <p className="page-subtitle">
                  Upload the tender document and vendor technical bid to begin automated compliance analysis.
                </p>
              </div>
              {verificationResult && (
                <button
                  className="secondary-btn btn-press"
                  onClick={() => setActiveTab("results")}
                >
                  <span>View Last Results</span>
                  <svg className="arrow-icon-shift" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="5" y1="12" x2="19" y2="12"/>
                    <polyline points="12 5 19 12 12 19"/>
                  </svg>
                </button>
              )}
            </div>

            {/* Document Upload Stage */}
            <div className="two-column-upload-grid reveal-on-scroll">
              <UploadCard
                id="tender-pdf-upload"
                title="Tender Document"
                subtitle="Official GeM procurement tender containing mandatory technical and commercial specifications."
                dropText="Drop tender PDF here or browse"
                file={tenderFile}
                onFileSelect={(file) => {
                  setTenderFile(file)
                  setErrorMessage("")
                }}
                onFileRemove={() => setTenderFile(null)}
                disabled={verifying}
              />

              <UploadCard
                id="vendor-pdf-upload"
                title="Vendor Technical Bid"
                subtitle="Vendor technical proposal, datasheet, or compliance schedule submitted for evaluation."
                dropText="Drop vendor bid PDF here or browse"
                file={vendorFile}
                onFileSelect={(file) => {
                  setVendorFile(file)
                  setErrorMessage("")
                }}
                onFileRemove={() => setVendorFile(null)}
                disabled={verifying}
              />
            </div>

            {/* Validation / Error Banner with Shake Animation */}
            {errorMessage && (
              <div className="alert-box alert-error error-shake animate-in">
                <div className="alert-icon">⚠️</div>
                <div className="alert-body">
                  <strong>Verification Warning:</strong> {errorMessage}
                </div>
                <button className="alert-close btn-press micro-rotate" onClick={() => setErrorMessage("")}>✕</button>
              </div>
            )}

            {/* Execution Panel */}
            <div className="verify-action-panel reveal-on-scroll">
              {verifying ? (
                <LoadingProgress />
              ) : (
                <div className="action-button-group">
                  <button
                    className="primary-btn verify-cta-btn btn-press"
                    onClick={verifyDocuments}
                    disabled={verifying}
                  >
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
                      <polygon points="5 3 19 12 5 21 5 3"/>
                    </svg>
                    <span>Verify Documents</span>
                  </button>
                  <span className="verify-cta-hint">
                    Deterministic compliance engine • No external data egress • Audit grounded
                  </span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* 3. VERIFICATION RESULTS VIEW                                             */}
        {/* ========================================================================= */}
        {activeTab === "results" && (
          <div className="results-view view-transition animate-in">
            {!verificationResult ? (
              <EmptyState onStartVerification={() => setActiveTab("new_verification")} />
            ) : (
              <>
                {/* Results Header */}
                <div className="results-top-header reveal-on-scroll">
                  <div className="header-titles">
                    <div className="results-status-chip success-indicator">
                      <span className="status-dot online pulse-dot"></span>
                      <span>ANALYSIS COMPLETE & VERIFIED</span>
                    </div>
                    <h1 className="results-main-title">Compliance Verification Results</h1>
                    <div className="results-meta-strip">
                      <span>Tender: <strong>{verificationResult.tender_file || "tender.pdf"}</strong></span>
                      <span className="meta-dot">•</span>
                      <span>Vendor: <strong>{verificationResult.vendor_file || "vendor.pdf"}</strong></span>
                      {verificationTimestamp && (
                        <>
                          <span className="meta-dot">•</span>
                          <span>Generated: <strong>{verificationTimestamp}</strong></span>
                        </>
                      )}
                    </div>
                  </div>

                  <div className="results-header-actions">
                    <button
                      className="secondary-btn btn-press"
                      onClick={() => setActiveTab("new_verification")}
                    >
                      <span>+ Verify Another Bid</span>
                    </button>
                  </div>
                </div>

                {/* KPI Summary Cards with Staggered Fade-in */}
                <div className="kpi-cards-row reveal-on-scroll">
                  <SummaryCard
                    type="total"
                    label="Total Requirements"
                    value={verificationResult.summary?.total}
                    description="Extracted procurement criteria"
                    icon={
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                        <line x1="16" y1="13" x2="8" y2="13"/>
                        <line x1="16" y1="17" x2="8" y2="17"/>
                      </svg>
                    }
                  />

                  <SummaryCard
                    type="compliant"
                    label="Compliant"
                    value={verificationResult.summary?.compliant}
                    description="Satisfies or exceeds criteria"
                    icon={
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="20 6 9 17 4 12"/>
                      </svg>
                    }
                  />

                  <SummaryCard
                    type="non-compliant"
                    label="Non-Compliant"
                    value={verificationResult.summary?.non_compliant}
                    description="Deficit or specification gap"
                    icon={
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#dc2626" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="18" y1="6" x2="6" y2="18"/>
                        <line x1="6" y1="6" x2="18" y2="18"/>
                      </svg>
                    }
                  />

                  <SummaryCard
                    type="not-found"
                    label="Not Found"
                    value={verificationResult.summary?.not_found}
                    description="Omitted from vendor bid"
                    icon={
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#64748b" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="5" y1="12" x2="19" y2="12"/>
                      </svg>
                    }
                  />

                  <SummaryCard
                    type="needs-review"
                    label="Needs Review"
                    value={verificationResult.summary?.needs_review}
                    description="Ambiguous or partial claims"
                    icon={
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#d97706" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <circle cx="12" cy="12" r="10"/>
                        <line x1="12" y1="8" x2="12" y2="12"/>
                        <line x1="12" y1="16" x2="12.01" y2="16"/>
                      </svg>
                    }
                  />
                </div>

                {/* Compliance Distribution Progress Bar */}
                {verificationResult.summary && verificationResult.summary.total > 0 && (
                  <div className="compliance-distribution-panel reveal-on-scroll card-interactive">
                    <div className="distribution-header">
                      <span className="dist-title">Compliance Ratio</span>
                      <span className="dist-rate">
                        <strong className="ratio-highlight">{animatedRatio}%</strong> Compliant Overall
                      </span>
                    </div>
                    <div className="distribution-bar">
                      <div
                        className="bar-segment compliant-seg"
                        style={{
                          width: `${(verificationResult.summary.compliant / verificationResult.summary.total) * 100}%`,
                        }}
                        title={`Compliant: ${verificationResult.summary.compliant}`}
                      />
                      <div
                        className="bar-segment non-compliant-seg"
                        style={{
                          width: `${(verificationResult.summary.non_compliant / verificationResult.summary.total) * 100}%`,
                        }}
                        title={`Non-Compliant: ${verificationResult.summary.non_compliant}`}
                      />
                      <div
                        className="bar-segment review-seg"
                        style={{
                          width: `${(verificationResult.summary.needs_review / verificationResult.summary.total) * 100}%`,
                        }}
                        title={`Needs Review: ${verificationResult.summary.needs_review}`}
                      />
                      <div
                        className="bar-segment not-found-seg"
                        style={{
                          width: `${(verificationResult.summary.not_found / verificationResult.summary.total) * 100}%`,
                        }}
                        title={`Not Found: ${verificationResult.summary.not_found}`}
                      />
                    </div>
                  </div>
                )}

                {/* Compliance Matrix Table */}
                <div className="reveal-on-scroll">
                  <ComplianceTable
                    results={verificationResult.results}
                    onViewEvidence={(item) => setSelectedEvidenceItem(item)}
                  />
                </div>
              </>
            )}
          </div>
        )}
      </main>

      {/* Audit Evidence Drawer / Modal */}
      {selectedEvidenceItem && (
        <EvidenceModal
          item={selectedEvidenceItem}
          onClose={() => setSelectedEvidenceItem(null)}
        />
      )}
    </div>
  )
}

export default App
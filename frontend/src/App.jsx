import { useState, useEffect, useCallback } from "react"
import Navbar from "./components/Navbar"
import UploadCard from "./components/UploadCard"
import SummaryCard from "./components/SummaryCard"
import ComplianceTable from "./components/ComplianceTable"
import EvidenceModal from "./components/EvidenceModal"
import LoadingProgress from "./components/LoadingProgress"
import EmptyState from "./components/EmptyState"
import WorkspaceHeader from "./components/WorkspaceHeader"
import RequirementReview from "./components/RequirementReview"
import MultiVendorUpload from "./components/MultiVendorUpload"
import AsyncJobProgress from "./components/AsyncJobProgress"
import VendorComparisonDashboard from "./components/VendorComparisonDashboard"
import HumanReviewQueue from "./components/HumanReviewQueue"
import ShareModal from "./components/ShareModal"
import TenderDirectory from "./components/TenderDirectory"
import DeleteConfirmModal from "./components/DeleteConfirmModal"
import CreateTenderModal from "./components/CreateTenderModal"

const API_BASE = "http://127.0.0.1:8000"

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
  // Navigation & Global UI
  const [activeTab, setActiveTab] = useState("dashboard") // "dashboard" | "workspace" | "new_verification" | "results"
  const [scrollProgress, setScrollProgress] = useState(0)
  const [errorMessage, setErrorMessage] = useState("")
  const [selectedEvidenceItem, setSelectedEvidenceItem] = useState(null)
  const [showShareModal, setShowShareModal] = useState(false)
  const [showCreateTenderModal, setShowCreateTenderModal] = useState(false)

  // Multi-Tender List & Directory State
  const [tendersList, setTendersList] = useState([])
  const [selectedTender, setSelectedTender] = useState(null)
  const [loadingTenders, setLoadingTenders] = useState(false)

  // Legacy 1-on-1 Verify State (Preserved)
  const [tenderFile, setTenderFile] = useState(null)
  const [vendorFile, setVendorFile] = useState(null)
  const [verifying, setVerifying] = useState(false)
  const [verificationResult, setVerificationResult] = useState(null)
  const [verificationTimestamp, setVerificationTimestamp] = useState("")

  // Active Tender Workspace Workflow State
  const [workspaceStep, setWorkspaceStep] = useState("upload_tender") // "upload_tender" | "curate_requirements" | "upload_vendors" | "analyzing" | "dashboard"
  const [workspaceTenderFile, setWorkspaceTenderFile] = useState(null)
  const [uploadingTender, setUploadingTender] = useState(false)
  const [workspaceRequirements, setWorkspaceRequirements] = useState([])
  const [stagedVendorFiles, setStagedVendorFiles] = useState([])
  const [activeJobStatus, setActiveJobStatus] = useState(null)
  const [comparisonReport, setComparisonReport] = useState(null)
  const [selectedVendorId, setSelectedVendorId] = useState(null)
  const [selectedVendorDetail, setSelectedVendorDetail] = useState(null)
  const [reviewQueueItems, setReviewQueueItems] = useState([])
  const [sharedViewData, setSharedViewData] = useState(null)
  const [dashboardSearchQuery, setDashboardSearchQuery] = useState("")
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deletingTender, setDeletingTender] = useState(false)
  const [deleteError, setDeleteError] = useState("")

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

  // Robust Scroll Reveal & Content Visibility Guarantee
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "smooth" })

    // Immediately mark elements revealed so nothing is ever invisible
    const revealAll = () => {
      const elements = document.querySelectorAll(".reveal-on-scroll")
      elements.forEach((el) => el.classList.add("revealed"))
    }

    revealAll()
    const timer = setTimeout(revealAll, 60)
    return () => clearTimeout(timer)
  }, [activeTab, selectedTender, workspaceStep, verificationResult])

  // Fetch all workspaces / tenders for current owner
  const fetchTenders = useCallback(async () => {
    setLoadingTenders(true)
    try {
      const res = await fetch(`${API_BASE}/api/workspaces`)
      if (res.ok) {
        const data = await res.json()
        setTendersList(data)
      }
    } catch (err) {
      console.warn("Could not fetch tenders list:", err)
    } finally {
      setLoadingTenders(false)
    }
  }, [])

  useEffect(() => {
    fetchTenders()
  }, [fetchTenders])

  // Get or bootstrap authenticated procurement officer session token
  const getAuthHeader = useCallback(async () => {
    let token = localStorage.getItem("bidverify_auth_token")
    if (!token) {
      try {
        const res = await fetch(`${API_BASE}/api/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username: "officer", password: "Officer@BidVerify2026" }),
        })
        if (res.ok) {
          const data = await res.json()
          if (data.access_token) {
            token = data.access_token
            localStorage.setItem("bidverify_auth_token", token)
          }
        }
      } catch (err) {
        console.warn("Auth token bootstrap note:", err)
      }
    }
    return token ? { Authorization: `Bearer ${token}` } : {}
  }, [])

  // Helper to remove any share query parameter from the browser URL bar
  const clearShareQuery = useCallback(() => {
    if (window.location.search) {
      const url = new URL(window.location.href)
      url.searchParams.delete("share")
      const newSearch = url.searchParams.toString() ? `?${url.searchParams.toString()}` : ""
      const cleanUrl = url.pathname + newSearch + (url.hash || "")
      window.history.pushState({}, "", cleanUrl)
    }
  }, [])

  // Select a tender to open its workspace
  const handleSelectTender = useCallback(async (tender) => {
    clearShareQuery()
    setSelectedTender(tender)
    setSelectedVendorId(null)
    setSelectedVendorDetail(null)
    setActiveTab("workspace")
    setErrorMessage("")

    if (tender?.workspace_code) {
      const url = new URL(window.location.href)
      url.searchParams.delete("share")
      url.searchParams.set("tender", tender.workspace_code)
      window.history.replaceState({}, "", url.pathname + "?" + url.searchParams.toString() + (url.hash || ""))
    }

    try {
      const res = await fetch(`${API_BASE}/api/workspaces/${tender.workspace_code}`)
      if (res.ok) {
        const details = await res.json()
        setSelectedTender(details)

        // Fetch requirements for this tender
        const reqRes = await fetch(`${API_BASE}/api/workspaces/${tender.workspace_code}/requirements`)
        if (reqRes.ok) {
          const reqs = await reqRes.json()
          setWorkspaceRequirements(reqs)

          // Check if comparison results exist
          if (details.vendors_count > 0) {
            const compRes = await fetch(`${API_BASE}/api/workspaces/${tender.workspace_code}/comparison`)
            if (compRes.ok) {
              const compData = await compRes.json()
              if (compData.vendors && compData.vendors.length > 0) {
                setComparisonReport(compData)
                try {
                  const revRes = await fetch(`${API_BASE}/api/workspaces/${tender.workspace_code}/review-queue`)
                  if (revRes.ok) {
                    const revData = await revRes.json()
                    setReviewQueueItems(revData.items || [])
                  }
                } catch (revErr) {
                  console.warn("Review queue fetch note:", revErr)
                }
                setWorkspaceStep("dashboard")
                return
              }
            }
          }

          if (reqs.length > 0) {
            setWorkspaceStep("upload_vendors")
          } else if (details.tender_document) {
            setWorkspaceStep("curate_requirements")
          } else {
            setWorkspaceStep("upload_tender")
          }
        } else {
          setWorkspaceStep("upload_tender")
        }
      }
    } catch (err) {
      console.error("Failed to load tender details:", err)
      setWorkspaceStep("upload_tender")
    }
  }, [clearShareQuery])

  // Explicitly navigate to Dashboard and clear any share/read-only workspace state
  const handleNavigateDashboard = useCallback(() => {
    clearShareQuery()
    setSharedViewData(null)
    setSelectedTender((prev) => (prev?.status === "READ_ONLY" ? null : prev))
    setActiveTab("dashboard")
    if (window.location.search) {
      const url = new URL(window.location.href)
      url.searchParams.delete("tender")
      url.searchParams.delete("workspace")
      const newSearch = url.searchParams.toString() ? `?${url.searchParams.toString()}` : ""
      window.history.pushState({}, "", url.pathname + newSearch + (url.hash || ""))
    }
  }, [clearShareQuery])

  // Centralized tab change handler for navbar and global navigation
  const handleTabChange = useCallback((tab) => {
    if (tab === "dashboard") {
      handleNavigateDashboard()
    } else {
      if (tab !== "workspace") {
        clearShareQuery()
        setSharedViewData(null)
        setSelectedTender((prev) => (prev?.status === "READ_ONLY" ? null : prev))
      }
      setActiveTab(tab)
    }
  }, [handleNavigateDashboard, clearShareQuery])

  // Load a shared tender by token
  const loadShareToken = useCallback(async (shareToken) => {
    try {
      const res = await fetch(`${API_BASE}/api/share/${shareToken}`)
      if (!res.ok) throw new Error("Invalid or expired share link.")
      const data = await res.json()
      setSharedViewData(data)
      setComparisonReport(data.report)
      if (data.review_items) {
        setReviewQueueItems(data.review_items)
      }
      setSelectedTender({
        workspace_code: data.workspace_code,
        title: data.title,
        status: "READ_ONLY",
      })
      setActiveTab("workspace")
      setWorkspaceStep("dashboard")
    } catch (err) {
      setErrorMessage(`Share link error: ${err.message}`)
      clearShareQuery()
      setActiveTab("dashboard")
    }
  }, [clearShareQuery])

  // Check URL query parameters on load (PART 3 & workspace restoration)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const shareToken = params.get("share")
    const tenderCode = params.get("tender") || params.get("workspace")
    if (shareToken) {
      loadShareToken(shareToken)
    } else if (tenderCode) {
      handleSelectTender({ workspace_code: tenderCode })
    }
  }, [loadShareToken, handleSelectTender])

  // Support browser Back/Forward navigation between shared view, tender workspace and dashboard
  useEffect(() => {
    const handlePopState = () => {
      const params = new URLSearchParams(window.location.search)
      const shareToken = params.get("share")
      const tenderCode = params.get("tender") || params.get("workspace")
      if (shareToken) {
        loadShareToken(shareToken)
      } else if (tenderCode) {
        handleSelectTender({ workspace_code: tenderCode })
      } else {
        setSharedViewData(null)
        setSelectedTender(null)
        setActiveTab("dashboard")
      }
    }

    window.addEventListener("popstate", handlePopState)
    return () => window.removeEventListener("popstate", handlePopState)
  }, [loadShareToken, handleSelectTender])

  // Create a new tender
  const handleCreateTender = async (payload) => {
    const res = await fetch(`${API_BASE}/api/workspaces`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
    const data = await res.json()
    if (!res.ok) {
      throw new Error(data.detail || "Failed to create tender workspace.")
    }
    clearShareQuery()
    await fetchTenders()
    handleSelectTender(data)
  }

  // Delete Tender confirmation modal opener and handler (PART 4)
  const handleOpenDeleteModal = (tender) => {
    setDeleteTarget(tender)
    setDeleteError("")
  }

  const handleConfirmDelete = async () => {
    if (!deleteTarget) return
    setDeletingTender(true)
    setDeleteError("")
    try {
      const authHeaders = await getAuthHeader()
      const res = await fetch(`${API_BASE}/api/workspaces/${deleteTarget.workspace_code}`, {
        method: "DELETE",
        headers: { ...authHeaders },
      })
      if (res.ok) {
        if (selectedTender?.workspace_code === deleteTarget.workspace_code) {
          setSelectedTender(null)
          setActiveTab("dashboard")
        }
        setDeleteTarget(null)
        await fetchTenders()
      } else {
        const errData = await res.json().catch(() => ({}))
        if (res.status === 403) {
          setDeleteError("Permission denied: Shared or read-only users cannot delete workspaces. Owner permissions required.")
        } else if (res.status === 401) {
          setDeleteError("Authentication session required. Please sign in as procurement officer or administrator.")
        } else {
          setDeleteError(errData.detail || "Unable to delete tender workspace. Please try again.")
        }
      }
    } catch (err) {
      setDeleteError("Network error: Could not reach the service to delete tender workspace.")
    } finally {
      setDeletingTender(false)
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // TENDER WORKSPACE WORKFLOW HANDLERS
  // ─────────────────────────────────────────────────────────────────────────

  // 1. Upload Tender Document & Extract Requirements (PART 29)
  const handleUploadWorkspaceTender = async (file) => {
    if (!file || !selectedTender) return
    setUploadingTender(true)
    setErrorMessage("")

    try {
      const formData = new FormData()
      formData.append("file", file)

      const res = await fetch(`${API_BASE}/api/workspaces/${selectedTender.workspace_code}/tender`, {
        method: "POST",
        body: formData,
      })

      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail || "Failed to upload tender document.")
      }

      setWorkspaceTenderFile(file)
      setWorkspaceRequirements(data.requirements || [])
      setWorkspaceStep("curate_requirements")
      fetchTenders()
    } catch (err) {
      console.error(err)
      setErrorMessage(err.message || "Tender upload failed.")
    } finally {
      setUploadingTender(false)
    }
  }

  // 2. Update requirement in Curation Checkpoint
  const handleUpdateRequirement = async (reqId, updates) => {
    if (!selectedTender) return
    try {
      const res = await fetch(
        `${API_BASE}/api/workspaces/${selectedTender.workspace_code}/requirements/${reqId}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(updates),
        }
      )
      if (res.ok) {
        const updated = await res.json()
        setWorkspaceRequirements((prev) =>
          prev.map((r) => (r.id === reqId ? { ...r, ...updated } : r))
        )
      }
    } catch (err) {
      console.error("Failed to update requirement:", err)
    }
  }

  // 3. Delete requirement in Curation Checkpoint
  const handleDeleteRequirement = async (reqId) => {
    if (!selectedTender) return
    try {
      const res = await fetch(
        `${API_BASE}/api/workspaces/${selectedTender.workspace_code}/requirements/${reqId}`,
        { method: "DELETE" }
      )
      if (res.ok) {
        setWorkspaceRequirements((prev) => prev.filter((r) => r.id !== reqId))
      }
    } catch (err) {
      console.error("Failed to delete requirement:", err)
    }
  }

  // 4. Staged Vendor Files Management
  const handleAddVendorFiles = (newFiles) => {
    setStagedVendorFiles((prev) => [...prev, ...newFiles])
    setErrorMessage("")
  }

  const handleRemoveVendorFile = (index) => {
    setStagedVendorFiles((prev) => prev.filter((_, i) => i !== index))
  }

  // 5. Run Asynchronous Multi-Vendor Analysis (PART 20 & 21)
  const handleStartMultiVendorAnalysis = async () => {
    if (!selectedTender || stagedVendorFiles.length === 0) {
      setErrorMessage("Please stage at least one vendor proposal.")
      return
    }

    setErrorMessage("")
    setWorkspaceStep("analyzing")

    try {
      // Step A: Upload all staged vendor bid documents
      const formData = new FormData()
      stagedVendorFiles.forEach((file) => {
        formData.append("files", file)
      })

      const uploadRes = await fetch(
        `${API_BASE}/api/workspaces/${selectedTender.workspace_code}/vendors`,
        { method: "POST", body: formData }
      )

      if (!uploadRes.ok) {
        const errData = await uploadRes.json()
        throw new Error(errData.detail || "Failed to upload vendor proposals.")
      }

      // Step B: Dispatch asynchronous evaluation job across all vendors
      const analyzeRes = await fetch(
        `${API_BASE}/api/workspaces/${selectedTender.workspace_code}/analyze`,
        { method: "POST" }
      )

      if (!analyzeRes.ok) {
        const errData = await analyzeRes.json()
        throw new Error(errData.detail || "Failed to dispatch verification pipeline.")
      }

      const jobData = await analyzeRes.json()
      setActiveJobStatus(jobData)

      // Step C: Poll job status until COMPLETED or FAILED
      pollJobProgress(jobData.job_id)
    } catch (err) {
      console.error("Multi-vendor verification error:", err)
      setErrorMessage(err.message || "Failed to complete multi-vendor verification.")
      setWorkspaceStep("upload_vendors")
    }
  }

  // 6. Polling loop for asynchronous background job
  const pollJobProgress = (jobId) => {
    const pollInterval = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/api/jobs/${jobId}`)
        if (!res.ok) return

        const status = await res.json()
        setActiveJobStatus(status)

        if (status.status === "COMPLETED") {
          clearInterval(pollInterval)
          fetchMultiVendorResults(selectedTender.workspace_code)
        } else if (status.status === "FAILED") {
          clearInterval(pollInterval)
          setErrorMessage(`Verification pipeline error: ${status.error_message || "Unknown error"}`)
          setWorkspaceStep("upload_vendors")
        }
      } catch (err) {
        console.error("Error polling job status:", err)
      }
    }, 800)
  }

  // 7. Load Multi-Vendor Comparison Dashboard Data
  const fetchMultiVendorResults = async (workspaceCode) => {
    try {
      const compRes = await fetch(`${API_BASE}/api/workspaces/${workspaceCode}/comparison`)
      if (compRes.ok) {
        const compData = await compRes.json()
        setComparisonReport(compData)
      }

      const revRes = await fetch(`${API_BASE}/api/workspaces/${workspaceCode}/review-queue`)
      if (revRes.ok) {
        const revData = await revRes.json()
        setReviewQueueItems(revData.items || [])
      }

      setWorkspaceStep("dashboard")
      fetchTenders()
    } catch (err) {
      console.error("Failed to load multi-vendor comparison:", err)
      setErrorMessage("Could not retrieve verification results.")
    }
  }

  // 8. Drill down into single vendor results
  const handleSelectVendor = async (vendorId) => {
    setSelectedVendorId(vendorId)
    if (!selectedTender) return

    try {
      const res = await fetch(
        `${API_BASE}/api/workspaces/${selectedTender.workspace_code}/vendors/${vendorId}/results`
      )
      if (res.ok) {
        const detail = await res.json()
        setSelectedVendorDetail(detail)
      }
    } catch (err) {
      console.error("Failed to load vendor results:", err)
    }
  }

  // 9. Process human review action (PART 19)
  const handleProcessReviewAction = async (reviewId, actionPayload) => {
    if (!selectedTender) return
    try {
      const res = await fetch(
        `${API_BASE}/api/workspaces/${selectedTender.workspace_code}/review/${reviewId}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(actionPayload),
        }
      )
      if (res.ok) {
        setReviewQueueItems((prev) =>
          prev.map((item) =>
            item.id === reviewId
              ? { ...item, review_status: actionPayload.status, decision_reason: actionPayload.decision_reason }
              : item
          )
        )
        if (selectedTender) {
          fetchMultiVendorResults(selectedTender.workspace_code)
        }
      }
    } catch (err) {
      console.error("Failed to record review action:", err)
    }
  }

  // Create temporary read-only share link (PART 3)
  const handleCreateShareLink = async (expiresInDays = 7) => {
    if (!selectedTender) return
    const res = await fetch(
      `${API_BASE}/api/workspaces/${selectedTender.workspace_code}/share`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expires_in_days: expiresInDays }),
      }
    )
    if (!res.ok) throw new Error("Failed to create share link.")
    return await res.json()
  }

  // Export official report (PART 24)
  const handleExportReport = async () => {
    if (!selectedTender) return
    try {
      const res = await fetch(
        `${API_BASE}/api/workspaces/${selectedTender.workspace_code}/report`
      )
      const data = await res.json()
      const blob = new Blob([data.markdown_report], { type: "text/markdown;charset=utf-8;" })
      const url = URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url
      link.setAttribute(
        "download",
        `BidVerify_Compliance_Report_${selectedTender.workspace_code}.md`
      )
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
    } catch (err) {
      console.error("Report export failed:", err)
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // LEGACY 1-ON-1 VERIFICATION (Preserved)
  // ─────────────────────────────────────────────────────────────────────────
  const verifyDocumentsLegacy = async () => {
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
      const response = await fetch(`${API_BASE}/verify`, {
        method: "POST",
        body: formData,
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || "Compliance verification failed.")
      }

      setVerificationResult(data)
      setVerificationTimestamp(
        new Date().toLocaleDateString("en-IN", {
          day: "numeric",
          month: "short",
          year: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        })
      )
      setActiveTab("results")
    } catch (error) {
      console.error("Verification error:", error)
      setErrorMessage(error.message || "Unable to connect to the compliance engine.")
    } finally {
      setVerifying(false)
    }
  }

  // Telemetry counts for dashboard
  const totalTendersCount = tendersList.length
  const activeTendersCount = tendersList.filter((t) => (t.derived_status || t.status) === "ACTIVE").length
  const closingSoonCount = tendersList.filter((t) => (t.derived_status || t.status) === "CLOSING_SOON").length
  const closedTendersCount = tendersList.filter((t) => (t.derived_status || t.status) === "CLOSED").length
  const totalVendorsCount = tendersList.reduce((acc, t) => acc + (t.vendors_count || 0), 0)

  // Animated telemetry numbers
  const animatedTenders = useCountUp(totalTendersCount)
  const animatedActive = useCountUp(activeTendersCount)
  const animatedVendors = useCountUp(totalVendorsCount)
  const telemetryTotal = useCountUp(verificationResult?.summary?.total)

  return (
    <div className="enterprise-app">
      {/* Top Navigation */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={handleTabChange}
        hasResults={Boolean(verificationResult)}
        workspace={selectedTender}
        scrollProgress={scrollProgress}
      />

      <main className="main-wrapper">
        {/* Error Notification Banner */}
        {errorMessage && (
          <div className="alert-box alert-error error-shake animate-in">
            <div className="alert-icon">⚠️</div>
            <div className="alert-body">
              <strong>System Notice:</strong> {errorMessage}
            </div>
            <button className="alert-close btn-press" onClick={() => setErrorMessage("")}>
              ✕
            </button>
          </div>
        )}

        {/* ========================================================================= */}
        {/* 1. DASHBOARD VIEW (Phase 1 & Phase 22)                                    */}
        {/* ========================================================================= */}
        {activeTab === "dashboard" && (
          <div className="dashboard-view view-transition animate-in">
            {/* Hero Section */}
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
                  against multiple vendor proposals independently, evaluate clauses deterministically, and identify procurement risks with mathematical certainty.
                </p>
                <div className="hero-actions">
                  <button
                    className="primary-btn lg-btn btn-press"
                    onClick={() => setShowCreateTenderModal(true)}
                  >
                    <span>+ Create New Tender</span>
                  </button>
                  <button
                    className="secondary-btn lg-btn btn-press"
                    onClick={() => {
                      clearShareQuery()
                      setSelectedTender(null)
                      setActiveTab("workspace")
                    }}
                  >
                    <span>Browse All Tenders ({totalTendersCount})</span>
                  </button>
                  <button
                    className="secondary-btn lg-btn btn-press"
                    onClick={() => handleTabChange("new_verification")}
                  >
                    <span>Quick 1-on-1 Verify</span>
                  </button>
                </div>
              </div>

              {/* KPI Telemetry Panel */}
              <div className="dashboard-kpi-panel card-interactive">
                <div className="kpi-panel-header">
                  <h3>Compliance Telemetry</h3>
                  <span className="telemetry-badge">
                    <span className="pulse-dot online"></span> Live SPV v2.4
                  </span>
                </div>

                <div className="kpi-stat-stack">
                  <div className="stat-row">
                    <span className="stat-lbl">Total Tenders Managed</span>
                    <strong className="stat-val">{animatedTenders}</strong>
                  </div>
                  <div className="stat-row">
                    <span className="stat-lbl">Active Tenders</span>
                    <strong className="stat-val green">{animatedActive}</strong>
                  </div>
                  {closingSoonCount > 0 && (
                    <div className="stat-row">
                      <span className="stat-lbl">Closing Soon (&lt; 3 Days)</span>
                      <strong className="stat-val orange">{closingSoonCount}</strong>
                    </div>
                  )}
                  <div className="stat-row">
                    <span className="stat-lbl">Total Vendors Evaluated</span>
                    <strong className="stat-val blue">{animatedVendors}</strong>
                  </div>
                  {closedTendersCount > 0 && (
                    <div className="stat-row">
                      <span className="stat-lbl">Closed Tenders</span>
                      <strong className="stat-val red">{closedTendersCount}</strong>
                    </div>
                  )}
                </div>
              </div>
            </section>

            {/* Recent Tenders Section on Dashboard */}
            <section className="workflow-section reveal-on-scroll">
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 20, flexWrap: "wrap", gap: 14 }}>
                <div>
                  <span className="section-eyebrow">ACTIVE WORKSPACES</span>
                  <h2 className="section-title">Recent Procurement Tenders</h2>
                  <p className="section-sub">Tender evaluation workspaces currently active or recently evaluated.</p>
                </div>
                <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                  {/* Dashboard Search Bar (PART 3) */}
                  <div className="search-box interactive-search" style={{ minWidth: 280 }}>
                    <svg className="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <circle cx="11" cy="11" r="8"/>
                      <line x1="21" y1="21" x2="16.65" y2="16.65"/>
                    </svg>
                    <input
                      type="text"
                      placeholder="Search title, ID, GeM code, vendor..."
                      value={dashboardSearchQuery}
                      onChange={(e) => setDashboardSearchQuery(e.target.value)}
                    />
                    {dashboardSearchQuery && (
                      <button className="clear-search" onClick={() => setDashboardSearchQuery("")}>✕</button>
                    )}
                  </div>

                  <button
                    className="outline-btn btn-press sm-btn"
                    onClick={() => {
                      clearShareQuery()
                      setSelectedTender(null)
                      setActiveTab("workspace")
                    }}
                  >
                    View All Tenders →
                  </button>
                  <button
                    className="primary-btn btn-press sm-btn"
                    onClick={() => setShowCreateTenderModal(true)}
                  >
                    + New Tender
                  </button>
                </div>
              </div>

              {tendersList.length === 0 ? (
                <div className="empty-state-panel">
                  <div className="empty-state-icon" style={{ fontSize: 36 }}>📋</div>
                  <h3 className="empty-title">No Tenders Created Yet</h3>
                  <p className="empty-desc">
                    Create your first procurement tender workspace to begin extracting specifications and evaluating multi-vendor proposals.
                  </p>
                  <button
                    className="primary-btn btn-press"
                    onClick={() => setShowCreateTenderModal(true)}
                  >
                    + Create Your First Tender
                  </button>
                </div>
              ) : tendersList.filter((t) => {
                  if (!dashboardSearchQuery.trim()) return true
                  const q = dashboardSearchQuery.toLowerCase().trim()
                  const matchTitle = t.title?.toLowerCase().includes(q)
                  const matchId = t.id?.toLowerCase().includes(q)
                  const matchCode = t.workspace_code?.toLowerCase().includes(q)
                  const matchRef = t.tender_reference?.toLowerCase().includes(q)
                  const matchVendor = Array.isArray(t.vendor_names) && t.vendor_names.some((v) => v?.toLowerCase().includes(q))
                  return matchTitle || matchId || matchCode || matchRef || matchVendor
                }).length === 0 ? (
                <div className="empty-state-panel" style={{ margin: "20px auto" }}>
                  <div className="empty-state-icon" style={{ fontSize: 36 }}>🔍</div>
                  <h3 className="empty-title">No tenders found</h3>
                  <p className="empty-desc">
                    No procurement workspaces match "{dashboardSearchQuery}". Try searching by tender title, ID, GeM reference, or vendor name.
                  </p>
                  <button
                    className="secondary-btn sm-btn btn-press"
                    onClick={() => setDashboardSearchQuery("")}
                  >
                    Clear Search
                  </button>
                </div>
              ) : (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 18 }}>
                  {tendersList
                    .filter((t) => {
                      if (!dashboardSearchQuery.trim()) return true
                      const q = dashboardSearchQuery.toLowerCase().trim()
                      const matchTitle = t.title?.toLowerCase().includes(q)
                      const matchId = t.id?.toLowerCase().includes(q)
                      const matchCode = t.workspace_code?.toLowerCase().includes(q)
                      const matchRef = t.tender_reference?.toLowerCase().includes(q)
                      const matchVendor = Array.isArray(t.vendor_names) && t.vendor_names.some((v) => v?.toLowerCase().includes(q))
                      return matchTitle || matchId || matchCode || matchRef || matchVendor
                    })
                    .slice(0, dashboardSearchQuery ? undefined : 4)
                    .map((t) => {
                      const st = t.derived_status || t.status || "ACTIVE"
                      return (
                        <div
                          key={t.id || t.workspace_code}
                          className="workflow-card card-interactive"
                          style={{ display: "flex", flexDirection: "column", justifyContent: "space-between" }}
                        >
                          <div>
                            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                              <span className="nav-code-pill" style={{ margin: 0 }}>{t.workspace_code}</span>
                              <span className={`status-pill ${st === 'ACTIVE' ? 'status-compliant' : (st === 'CLOSED' ? 'status-non-compliant' : 'status-needs-review')}`}>
                                ● {st.replace('_', ' ')}
                              </span>
                            </div>
                            <h4 style={{ fontSize: 16, marginBottom: 4 }}>{t.title}</h4>
                            {t.tender_reference && (
                              <div style={{ fontSize: 12, color: "var(--primary-blue)", fontWeight: 600, marginBottom: 6 }}>
                                Ref: {t.tender_reference}
                              </div>
                            )}
                            <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 12 }}>
                              Closing: <strong>{t.closing_date ? new Date(t.closing_date).toLocaleDateString() : "—"}</strong>
                            </div>
                          </div>

                          <div style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: 10, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                            <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                              {t.requirements_count || 0} Criteria • {t.vendors_count || 0} Vendors
                            </span>
                            <button
                              className="primary-btn btn-press sm-btn"
                              onClick={() => handleSelectTender(t)}
                            >
                              Open →
                            </button>
                          </div>
                        </div>
                      )
                    })}
                </div>
              )}
            </section>

            {/* 4-Step Verification Workflow Overview */}
            <section className="workflow-section reveal-on-scroll" style={{ marginTop: 40 }}>
              <div className="section-title-wrap">
                <span className="section-eyebrow">STANDARDIZED METHODOLOGY</span>
                <h2 className="section-title">Evidence-Based Verification Pipeline</h2>
                <p className="section-sub">How BidVerify AI guarantees mathematical accuracy for public procurement evaluation.</p>
              </div>

              <div className="workflow-grid">
                <div className="workflow-card card-interactive">
                  <div className="workflow-step-num">01</div>
                  <div className="workflow-icon micro-icon">📄</div>
                  <h4>Tender Ingestion</h4>
                  <p>Parses official GeM PDF/DOCX tenders. Reconstructs tables and extracts criteria without category hardcoding.</p>
                </div>

                <div className="workflow-card card-interactive">
                  <div className="workflow-step-num">02</div>
                  <div className="workflow-icon micro-icon">🔍</div>
                  <h4>Curation Checkpoint</h4>
                  <p>Officer reviews normalized criteria. Modifies parameters, toggles mandatory flags, and deletes false positives.</p>
                </div>

                <div className="workflow-card card-interactive">
                  <div className="workflow-step-num">03</div>
                  <div className="workflow-icon micro-icon">🏢</div>
                  <h4>Multi-Vendor Staging</h4>
                  <p>Stages 1..N vendor proposals. Evaluates all vendors independently against identical tender requirements.</p>
                </div>

                <div className="workflow-card card-interactive">
                  <div className="workflow-step-num">04</div>
                  <div className="workflow-icon micro-icon">⚖️</div>
                  <h4>Deterministic Engine</h4>
                  <p>Numeric, range, exact, and negative constraints verified deterministically with side-by-side page citations.</p>
                </div>
              </div>
            </section>
          </div>
        )}

        {/* ========================================================================= */}
        {/* 2. TENDER WORKSPACE VIEW (Multi-Tender Directory + Detail)                */}
        {/* ========================================================================= */}
        {activeTab === "workspace" && (
          <div className="workspace-main-container view-transition animate-in">
            {/* If no specific tender is selected, show the Multi-Tender Directory */}
            {!selectedTender ? (
              <TenderDirectory
                tenders={tendersList}
                onSelectTender={handleSelectTender}
                onCreateTenderClick={() => setShowCreateTenderModal(true)}
                onDeleteTender={handleOpenDeleteModal}
              />
            ) : (
              /* Specific Tender Workspace Workflow */
              <div>
                {/* Workspace Header */}
                <WorkspaceHeader
                  workspace={selectedTender}
                  onShareClick={() => setShowShareModal(true)}
                  onExportClick={handleExportReport}
                  onNewWorkspace={() => setShowCreateTenderModal(true)}
                  onDeleteWorkspace={() => handleOpenDeleteModal(selectedTender)}
                  isReadOnly={Boolean(sharedViewData || selectedTender?.status === "READ_ONLY")}
                  onBackToDirectory={() => {
                    clearShareQuery()
                    setSharedViewData(null)
                    setSelectedTender(null)
                    setSelectedVendorId(null)
                    setSelectedVendorDetail(null)
                    if (window.location.search) {
                      const url = new URL(window.location.href)
                      url.searchParams.delete("tender")
                      url.searchParams.delete("workspace")
                      const newSearch = url.searchParams.toString() ? `?${url.searchParams.toString()}` : ""
                      window.history.pushState({}, "", url.pathname + newSearch + (url.hash || ""))
                    }
                    fetchTenders()
                  }}
                  activeStep={workspaceStep}
                />

                {/* Step 1: Upload Tender Document */}
                {workspaceStep === "upload_tender" && (
                  <div className="upload-tender-step reveal-on-scroll">
                    <div className="page-header-row">
                      <div>
                        <h1 className="page-title">Upload Tender Document</h1>
                        <p className="page-subtitle">
                          Upload the official GeM procurement tender containing technical specifications, mandatory conditions, and commercial terms.
                        </p>
                      </div>
                    </div>

                    <div className="single-upload-container">
                      <UploadCard
                        id="ws-tender-pdf-upload"
                        title="Official Tender PDF or DOCX"
                        subtitle="Document structure, tables, and clauses will be extracted automatically without hardcoded domain logic."
                        dropText="Drop tender document here or browse"
                        file={workspaceTenderFile}
                        onFileSelect={handleUploadWorkspaceTender}
                        onFileRemove={() => setWorkspaceTenderFile(null)}
                        disabled={uploadingTender}
                      />
                    </div>

                    {uploadingTender && (
                      <div className="loading-state-container" style={{ marginTop: 24 }}>
                        <LoadingProgress message="Analyzing tender structure, tables, and clauses..." />
                      </div>
                    )}
                  </div>
                )}

                {/* Step 2: Human-in-the-Loop Requirement Review Checkpoint (PART 29) */}
                {workspaceStep === "curate_requirements" && (
                  <RequirementReview
                    requirements={workspaceRequirements}
                    onUpdateRequirement={handleUpdateRequirement}
                    onDeleteRequirement={handleDeleteRequirement}
                    onProceedToVendors={() => setWorkspaceStep("upload_vendors")}
                    onBackToTender={() => setWorkspaceStep("upload_tender")}
                  />
                )}

                {/* Step 3: Multi-Vendor Bid Upload (PART 6) */}
                {workspaceStep === "upload_vendors" && (
                  <MultiVendorUpload
                    stagedFiles={stagedVendorFiles}
                    onAddFiles={handleAddVendorFiles}
                    onRemoveFile={handleRemoveVendorFile}
                    onStartAnalysis={handleStartMultiVendorAnalysis}
                    analyzing={false}
                    onBackToRequirements={() => setWorkspaceStep("curate_requirements")}
                    requirementsCount={workspaceRequirements.length}
                    isClosed={Boolean(selectedTender.derived_status === "CLOSED" || selectedTender.status === "CLOSED")}
                  />
                )}

                {/* Step 4: Asynchronous Real-Stage Pipeline Progress (PART 20) */}
                {workspaceStep === "analyzing" && (
                  <AsyncJobProgress jobStatus={activeJobStatus} />
                )}

                {/* Step 5: Comparative Intelligence & Multi-Vendor Dashboard (PART 11, 12, 16, 17, 18, 19) */}
                {workspaceStep === "dashboard" && comparisonReport && (
                  <div className="comparison-views-stack">
                    {/* Multi-Vendor Comparison Dashboard & Cross-Vendor Matrix */}
                    <VendorComparisonDashboard
                      comparisonData={comparisonReport}
                      onSelectVendor={handleSelectVendor}
                      selectedVendorId={selectedVendorId}
                    />

                    {/* Selected Vendor Itemized Matrix with Evidence Viewer */}
                    {selectedVendorDetail && (
                      <div className="vendor-matrix-drilldown reveal-on-scroll">
                        <div className="drilldown-header">
                          <div className="drilldown-title-lockup">
                            <span className="drilldown-tag">VENDOR DETAIL MATRIX</span>
                            <h3>
                              {selectedVendorDetail.vendor.vendor_name} ({selectedVendorDetail.vendor.vendor_code})
                            </h3>
                          </div>
                          <div className="drilldown-score-badge">
                            Score: <strong>{selectedVendorDetail.vendor.score_overall}%</strong>
                          </div>
                        </div>

                        <ComplianceTable
                          results={selectedVendorDetail.results}
                          onViewEvidence={(item) => setSelectedEvidenceItem(item)}
                        />
                      </div>
                    )}

                    {/* Human Review Queue (PART 19) */}
                    <HumanReviewQueue
                      reviewItems={reviewQueueItems}
                      onProcessAction={handleProcessReviewAction}
                      isReadOnly={Boolean(sharedViewData || selectedTender?.status === "READ_ONLY")}
                    />
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ========================================================================= */}
        {/* 3. QUICK 1-ON-1 VERIFY VIEW (Phase 2 & Phase 22)                          */}
        {/* ========================================================================= */}
        {activeTab === "new_verification" && (
          <div className="new-verification-view view-transition animate-in">
            <div className="page-header-row reveal-on-scroll">
              <div>
                <button
                  className="nav-breadcrumb-btn btn-press"
                  onClick={handleNavigateDashboard}
                >
                  ← Back to Dashboard
                </button>
                <h1 className="page-title">Quick 1-on-1 Bid Verification</h1>
                <p className="page-subtitle">
                  Direct evaluation of one tender against one vendor proposal using the compliance pipeline.
                </p>
              </div>
            </div>

            <div className="two-column-upload-grid reveal-on-scroll">
              <UploadCard
                id="tender-pdf-upload"
                title="Tender Document"
                subtitle="Official GeM procurement tender containing technical and commercial criteria."
                dropText="Drop tender PDF or DOCX here or browse"
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
                subtitle="Vendor technical proposal or compliance schedule submitted for evaluation."
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

            <div className="verify-action-panel reveal-on-scroll">
              {verifying ? (
                <LoadingProgress message="Comparing tender requirements against vendor specifications..." />
              ) : (
                <div className="action-button-group">
                  <button
                    className="primary-btn verify-cta-btn btn-press"
                    onClick={verifyDocumentsLegacy}
                    disabled={verifying || !tenderFile || !vendorFile}
                  >
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
                      <polygon points="5 3 19 12 5 21 5 3"/>
                    </svg>
                    <span>Verify Documents</span>
                  </button>
                  <span className="verify-cta-hint">Both documents must be staged before initiating evaluation</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ========================================================================= */}
        {/* 4. VERIFICATION RESULTS VIEW (Phase 2 & Phase 22)                         */}
        {/* ========================================================================= */}
        {activeTab === "results" && verificationResult && (
          <div className="results-view view-transition animate-in">
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
            </div>

            <div className="kpi-cards-row reveal-on-scroll">
              <SummaryCard
                type="total"
                label="Total Requirements"
                value={verificationResult.summary?.total}
                description="Extracted procurement criteria"
                icon={<span style={{ fontSize: "18px" }}>📋</span>}
              />
              <SummaryCard
                type="compliant"
                label="Compliant"
                value={verificationResult.summary?.compliant}
                description="Satisfies or exceeds criteria"
                icon={<span style={{ fontSize: "18px" }}>✓</span>}
              />
              <SummaryCard
                type="non-compliant"
                label="Non-Compliant"
                value={verificationResult.summary?.non_compliant}
                description="Deficit or specification gap"
                icon={<span style={{ fontSize: "18px" }}>✗</span>}
              />
              <SummaryCard
                type="not-found"
                label="Not Found"
                value={verificationResult.summary?.not_found}
                description="Omitted from vendor bid"
                icon={<span style={{ fontSize: "18px" }}>—</span>}
              />
              <SummaryCard
                type="needs-review"
                label="Needs Review"
                value={verificationResult.summary?.needs_review}
                description="Ambiguous or partial claims"
                icon={<span style={{ fontSize: "18px" }}>?</span>}
              />
            </div>

            <div className="reveal-on-scroll">
              <ComplianceTable
                results={verificationResult.results}
                onViewEvidence={(item) => setSelectedEvidenceItem(item)}
              />
            </div>
          </div>
        )}
      </main>

      {/* Audit Evidence Drawer / Modal (Preserved!) */}
      {selectedEvidenceItem && (
        <EvidenceModal
          item={selectedEvidenceItem}
          onClose={() => setSelectedEvidenceItem(null)}
        />
      )}

      {/* Secure Share Modal (PART 3) */}
      {showShareModal && selectedTender && (
        <ShareModal
          workspace={selectedTender}
          onClose={() => setShowShareModal(false)}
          onCreateShareLink={handleCreateShareLink}
        />
      )}

      {/* Create Tender Modal (NEW) */}
      <CreateTenderModal
        isOpen={showCreateTenderModal}
        onClose={() => setShowCreateTenderModal(false)}
        onCreate={handleCreateTender}
      />

      {/* Delete Tender Confirmation Modal (PART 4) */}
      <DeleteConfirmModal
        isOpen={Boolean(deleteTarget)}
        tender={deleteTarget}
        onClose={() => {
          setDeleteTarget(null)
          setDeleteError("")
        }}
        onConfirm={handleConfirmDelete}
        isDeleting={deletingTender}
        error={deleteError}
      />
    </div>
  )
}

export default App
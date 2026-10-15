import React, { useState } from "react"

export default function TenderDirectory({
  tenders,
  onSelectTender,
  onCreateTenderClick,
  onDeleteTender,
}) {
  const [filterStatus, setFilterStatus] = useState("ALL")
  const [searchQuery, setSearchQuery] = useState("")

  const getEffectiveStatus = (t) => t.derived_status || t.status || "ACTIVE"

  const filteredTenders = (tenders || []).filter((t) => {
    const st = getEffectiveStatus(t)
    if (filterStatus !== "ALL" && st !== filterStatus) {
      return false
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      const matchTitle = t.title?.toLowerCase().includes(q)
      const matchRef = t.tender_reference?.toLowerCase().includes(q)
      const matchCode = t.workspace_code?.toLowerCase().includes(q)
      return matchTitle || matchRef || matchCode
    }
    return true
  })

  const getStatusBadge = (st) => {
    switch (st) {
      case "ACTIVE":
        return <span className="status-pill status-compliant">● Active</span>
      case "CLOSING_SOON":
        return <span className="status-pill status-needs-review">⚠️ Closing Soon</span>
      case "CLOSED":
        return <span className="status-pill status-non-compliant">🔒 Closed</span>
      case "UPCOMING":
        return <span className="status-pill status-not-found">⏳ Upcoming</span>
      case "DRAFT":
        return <span className="status-pill status-not-found">📝 Draft</span>
      default:
        return <span className="status-pill status-not-found">● {st}</span>
    }
  }

  return (
    <div className="tender-directory-view animate-in">
      {/* Directory Header Bar */}
      <div className="page-header-row" style={{ alignItems: "center" }}>
        <div>
          <h1 className="page-title">Procurement Tender Workspaces</h1>
          <p className="page-subtitle">
            Manage multiple independent tender workspaces. Each tender maintains isolated criteria, vendor proposals, evaluation scores, and audit trails.
          </p>
        </div>
        <button
          className="primary-btn btn-press"
          onClick={onCreateTenderClick}
        >
          <span>+ Create New Tender</span>
        </button>
      </div>

      {/* Filter and Search Bar */}
      <div
        className="card-interactive"
        style={{
          background: "#fff",
          border: "1px solid var(--border-subtle)",
          borderRadius: 12,
          padding: "16px 20px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 14,
          marginBottom: 24,
        }}
      >
        <div className="filter-pill-group">
          {["ALL", "ACTIVE", "CLOSING_SOON", "UPCOMING", "CLOSED", "DRAFT"].map((st) => (
            <button
              key={st}
              className={`filter-btn ${filterStatus === st ? "active" : ""}`}
              onClick={() => setFilterStatus(st)}
            >
              {st === "ALL" ? "All Tenders" : st.replace("_", " ")}
            </button>
          ))}
        </div>

        <div className="search-box interactive-search" style={{ minWidth: 260 }}>
          <svg className="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8"/>
            <line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <input
            type="text"
            placeholder="Search by title, GeM ref, or code..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          {searchQuery && (
            <button className="clear-search" onClick={() => setSearchQuery("")}>✕</button>
          )}
        </div>
      </div>

      {/* Tenders Grid */}
      {filteredTenders.length === 0 ? (
        <div className="empty-state-panel" style={{ margin: "20px auto" }}>
          <div className="empty-state-icon" style={{ fontSize: 38 }}>📋</div>
          <h3 className="empty-title">
            {searchQuery || filterStatus !== "ALL" ? "No matching tenders found" : "No Tenders Created Yet"}
          </h3>
          <p className="empty-desc">
            {searchQuery || filterStatus !== "ALL"
              ? "Try adjusting your search terms or filter selection."
              : "Initialize your first procurement tender workspace to begin evaluating vendor bids."}
          </p>
          <button className="primary-btn btn-press" onClick={onCreateTenderClick}>
            + Create New Tender
          </button>
        </div>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))",
            gap: 20,
          }}
        >
          {filteredTenders.map((tender) => {
            const st = getEffectiveStatus(tender)
            return (
              <div
                key={tender.id || tender.workspace_code}
                className="workflow-card card-interactive"
                style={{ display: "flex", flexDirection: "column", justifyContent: "space-between" }}
              >
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span className="nav-code-pill" style={{ fontSize: 12, margin: 0 }}>
                        {tender.workspace_code}
                      </span>
                      {getStatusBadge(st)}
                    </div>
                    {onDeleteTender && (
                      <button
                        type="button"
                        className="action-btn remove-btn btn-press"
                        style={{ padding: "3px 8px", fontSize: 11 }}
                        onClick={(e) => {
                          e.stopPropagation()
                          onDeleteTender(tender)
                        }}
                        title="Delete Tender"
                      >
                        Delete
                      </button>
                    )}
                  </div>

                  <h3
                    style={{
                      fontSize: 17,
                      fontWeight: 700,
                      color: "var(--primary-navy)",
                      marginBottom: 6,
                      lineHeight: 1.35,
                    }}
                  >
                    {tender.title}
                  </h3>

                  {tender.tender_reference && (
                    <div style={{ fontSize: 12, color: "var(--primary-blue)", fontWeight: 600, marginBottom: 8 }}>
                      GeM Ref: {tender.tender_reference}
                    </div>
                  )}

                  {tender.description && (
                    <p
                      style={{
                        fontSize: 13,
                        color: "var(--text-secondary)",
                        lineHeight: 1.45,
                        marginBottom: 14,
                        display: "-webkit-box",
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: "vertical",
                        overflow: "hidden",
                      }}
                    >
                      {tender.description}
                    </p>
                  )}

                  {/* Date Metadata */}
                  <div
                    style={{
                      background: "#f8fafc",
                      border: "1px solid var(--border-subtle)",
                      borderRadius: 8,
                      padding: "8px 12px",
                      fontSize: 12,
                      color: "var(--text-muted)",
                      display: "flex",
                      justifyContent: "space-between",
                      marginBottom: 16,
                    }}
                  >
                    <div>
                      Start: <strong style={{ color: "var(--text-main)" }}>
                        {tender.start_date ? new Date(tender.start_date).toLocaleDateString() : "—"}
                      </strong>
                    </div>
                    <div>
                      Closing: <strong style={{ color: st === "CLOSED" ? "var(--status-non-compliant-text)" : "var(--text-main)" }}>
                        {tender.closing_date ? new Date(tender.closing_date).toLocaleDateString() : "—"}
                      </strong>
                    </div>
                  </div>
                </div>

                {/* Footer with Counts & Open Button */}
                <div
                  style={{
                    borderTop: "1px solid var(--border-subtle)",
                    paddingTop: 12,
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                    <span style={{ marginRight: 10 }}>
                      📋 <strong>{tender.requirements_count || 0}</strong> Criteria
                    </span>
                    <span>
                      🏢 <strong>{tender.vendors_count || 0}</strong> Vendors
                    </span>
                  </div>

                  <button
                    className="primary-btn btn-press sm-btn"
                    onClick={() => onSelectTender(tender)}
                  >
                    <span>Manage Tender →</span>
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

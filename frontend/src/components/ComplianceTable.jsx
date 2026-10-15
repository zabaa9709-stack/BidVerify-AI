import { useState } from "react"

export default function ComplianceTable({ results, onViewEvidence }) {
  const [filter, setFilter] = useState("ALL")
  const [searchTerm, setSearchTerm] = useState("")

  const renderStatusBadge = (status) => {
    switch (status) {
      case "COMPLIANT":
        return (
          <span className="status-pill status-compliant status-pop">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
            COMPLIANT
          </span>
        )
      case "NON_COMPLIANT":
        return (
          <span className="status-pill status-non-compliant status-pop">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
            NON-COMPLIANT
          </span>
        )
      case "NOT_FOUND":
        return (
          <span className="status-pill status-not-found status-pop">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
              <line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
            NOT FOUND
          </span>
        )
      case "NEEDS_REVIEW":
        return (
          <span className="status-pill status-needs-review status-pop">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10"/>
              <line x1="12" y1="8" x2="12" y2="12"/>
              <line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            NEEDS REVIEW
          </span>
        )
      default:
        return <span className="status-pill">{status}</span>
    }
  }

  const formatConfidence = (conf, matchScore) => {
    const rawVal = typeof matchScore === "number" ? matchScore : (typeof conf === "number" ? conf : null)
    if (rawVal !== null) {
      const pct = Math.round(rawVal <= 1.0 ? rawVal * 100 : rawVal)
      const colorClass = pct >= 85 ? "high" : pct >= 70 ? "light-green" : pct >= 50 ? "warning-red" : "low"
      return (
        <div className="conf-block" title={`Matching confidence: ${pct}%`}>
          <div className="conf-bar-track">
            <div
              className={`conf-bar-fill animated-bar-fill ${colorClass}`}
              style={{ width: `${pct}%` }}
            />
          </div>
          <span className="conf-text">{pct}%</span>
        </div>
      )
    }
    return <span className="conf-text">{conf || "—"}</span>
  }

  const filteredResults = (results || []).filter((item) => {
    const matchesFilter = filter === "ALL" || item.status === filter
    const matchesSearch =
      !searchTerm ||
      item.requirement.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (item.required_value && item.required_value.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (item.vendor_value && item.vendor_value.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (item.reason && item.reason.toLowerCase().includes(searchTerm.toLowerCase()))
    return matchesFilter && matchesSearch
  })

  return (
    <div className="matrix-card">
      <div className="matrix-toolbar">
        <div className="toolbar-left">
          <div className="table-heading-group">
            <h3 className="matrix-title">Compliance Verification Matrix</h3>
            <span className="matrix-badge">{results?.length || 0} Criteria Evaluated</span>
          </div>
        </div>

        <div className="toolbar-right">
          {/* Search Filter */}
          <div className="search-box interactive-search">
            <svg className="search-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#64748b" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8"/>
              <line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            <input
              type="text"
              placeholder="Search specifications..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
            {searchTerm && (
              <button className="clear-search btn-press" onClick={() => setSearchTerm("")}>✕</button>
            )}
          </div>

          {/* Status Filter Tabs */}
          <div className="filter-pill-group" role="tablist" aria-label="Compliance Status Filters">
            <button
              className={`filter-btn btn-press ${filter === "ALL" ? "active" : ""}`}
              onClick={() => setFilter("ALL")}
            >
              All ({results?.length || 0})
            </button>
            <button
              className={`filter-btn btn-press ${filter === "COMPLIANT" ? "active" : ""}`}
              onClick={() => setFilter("COMPLIANT")}
            >
              Compliant ({results?.filter((r) => r.status === "COMPLIANT").length || 0})
            </button>
            <button
              className={`filter-btn btn-press ${filter === "NON_COMPLIANT" ? "active" : ""}`}
              onClick={() => setFilter("NON_COMPLIANT")}
            >
              Non-Compliant ({results?.filter((r) => r.status === "NON_COMPLIANT").length || 0})
            </button>
            <button
              className={`filter-btn btn-press ${filter === "NOT_FOUND" ? "active" : ""}`}
              onClick={() => setFilter("NOT_FOUND")}
            >
              Not Found ({results?.filter((r) => r.status === "NOT_FOUND").length || 0})
            </button>
            <button
              className={`filter-btn btn-press ${filter === "NEEDS_REVIEW" ? "active" : ""}`}
              onClick={() => setFilter("NEEDS_REVIEW")}
            >
              Needs Review ({results?.filter((r) => r.status === "NEEDS_REVIEW").length || 0})
            </button>
          </div>
        </div>
      </div>

      <div className="table-responsive-wrapper">
        <table className="compliance-data-table">
          <thead>
            <tr>
              <th style={{ width: "18%" }}>Requirement</th>
              <th style={{ width: "10%" }}>Category</th>
              <th style={{ width: "21%" }}>Tender Required</th>
              <th style={{ width: "21%" }}>Vendor Offered</th>
              <th style={{ width: "12%" }}>Status</th>
              <th style={{ width: "8%" }}>Confidence</th>
              <th style={{ width: "10%", textAlign: "right" }}>Evidence</th>
            </tr>
          </thead>
          <tbody>
            {filteredResults.length === 0 ? (
              <tr>
                <td colSpan={7} className="empty-table-cell animate-in">
                  <div className="table-no-matches">
                    <span>No specifications match the selected filter criteria.</span>
                  </div>
                </td>
              </tr>
            ) : (
              filteredResults.map((item, idx) => (
                <tr
                  key={`${item.requirement}-${idx}`}
                  className={`table-row row-status-${item.status?.toLowerCase()} animate-row-stagger`}
                  style={{ "--row-idx": Math.min(idx, 20) }}
                >
                  {/* Requirement Name */}
                  <td className="cell-req">
                    <span className="req-name-text">{item.requirement}</span>
                    {item.condition && (
                      <span className="cond-tag">Condition: {item.condition}</span>
                    )}
                  </td>

                  {/* Category */}
                  <td className="cell-cat">
                    <span className={`cat-pill cat-${item.category?.toLowerCase() || "tech"}`}>
                      {item.category || "Technical"}
                    </span>
                  </td>

                  {/* Required Value */}
                  <td className="cell-value cell-tender">
                    <div className="value-box tender-box" title={item.required_value}>
                      {item.required_value}
                    </div>
                  </td>

                  {/* Vendor Value */}
                  <td className="cell-value cell-vendor">
                    <div
                      className={`value-box vendor-box ${item.status === "NON_COMPLIANT" ? "val-mismatch" : ""}`}
                      title={item.vendor_value}
                    >
                      {item.vendor_value}
                    </div>
                    {item.reason && (
                      <div className="reason-micro-preview" title={item.reason}>
                        {item.reason}
                      </div>
                    )}
                  </td>

                  {/* Status Badge */}
                  <td className="cell-status">
                    {renderStatusBadge(item.status)}
                  </td>

                  {/* Confidence */}
                  <td className="cell-conf">
                    {formatConfidence(item.confidence, item.match_score ?? item.semantic_match_confidence)}
                  </td>

                  {/* Evidence Action */}
                  <td className="cell-action">
                    <button
                      type="button"
                      className="evidence-link-btn btn-press"
                      onClick={() => onViewEvidence(item)}
                      title="Inspect tender & vendor source evidence"
                    >
                      <span>Evidence</span>
                      <svg className="arrow-icon-shift" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="5" y1="12" x2="19" y2="12"/>
                        <polyline points="12 5 19 12 12 19"/>
                      </svg>
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

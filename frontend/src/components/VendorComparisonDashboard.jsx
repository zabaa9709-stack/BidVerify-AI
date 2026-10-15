import { useState } from "react"

export default function VendorComparisonDashboard({
  comparisonData,
  onSelectVendor,
  selectedVendorId,
}) {
  const [activeSubTab, setActiveSubTab] = useState("scorecards") // "scorecards" | "cross_matrix"
  const [sortBy, setSortBy] = useState("score_overall") // "score_overall" | "score_mandatory" | "score_technical" | "score_evidence_coverage"
  const [sortAsc, setSortAsc] = useState(false)
  const [searchTerm, setSearchTerm] = useState("")

  if (!comparisonData || !comparisonData.vendors || comparisonData.vendors.length === 0) {
    return null
  }

  const vendors = [...comparisonData.vendors].sort((a, b) => {
    const valA = a[sortBy] ?? 0
    const valB = b[sortBy] ?? 0
    return sortAsc ? valA - valB : valB - valA
  })

  const matrix = comparisonData.matrix || []

  const handleSort = (field) => {
    if (sortBy === field) {
      setSortAsc(!sortAsc)
    } else {
      setSortBy(field)
      setSortAsc(false)
    }
  }

  const filteredMatrix = matrix.filter((row) => {
    if (!searchTerm) return true
    const term = searchTerm.toLowerCase()
    return (
      row.requirement.toLowerCase().includes(term) ||
      row.req_code.toLowerCase().includes(term) ||
      (row.required_value && row.required_value.toLowerCase().includes(term))
    )
  })

  return (
    <div className="comparison-dashboard-card card-interactive reveal-on-scroll">
      {/* Dashboard Top Navigation */}
      <div className="comp-dashboard-header">
        <div className="header-left">
          <div className="comp-tag">MULTI-VENDOR BENCHMARK (PART 16 & 17)</div>
          <h2 className="comp-title">Comparative Procurement Intelligence</h2>
          <p className="comp-sub">
            Evaluating <strong>{vendors.length} vendor bids</strong> against {comparisonData.matrix?.length || 0} normalized criteria with clause-level evidence grounding.
          </p>
        </div>

        <div className="comp-tabs-group">
          <button
            className={`comp-nav-tab ${activeSubTab === "scorecards" ? "active" : ""}`}
            onClick={() => setActiveSubTab("scorecards")}
          >
            📊 Vendor Scorecards ({vendors.length})
          </button>
          <button
            className={`comp-nav-tab ${activeSubTab === "cross_matrix" ? "active" : ""}`}
            onClick={() => setActiveSubTab("cross_matrix")}
          >
            📑 Cross-Vendor Matrix ({matrix.length})
          </button>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* 1. VENDOR SCORECARDS TABLE (PART 16)                                */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      {activeSubTab === "scorecards" && (
        <div className="scorecards-view animate-in">
          <div className="matrix-toolbar">
            <span className="matrix-badge">
              Sorted by: <strong>{sortBy.replace("score_", "").replace("_", " ").toUpperCase()}</strong> ({sortAsc ? "Ascending" : "Descending"})
            </span>
            <span className="hint-pill">💡 Click any vendor row to inspect itemized evidence matrix</span>
          </div>

          <div className="table-responsive-wrapper">
            <table className="compliance-grid-table vendor-rank-table">
              <thead>
                <tr>
                  <th style={{ width: "70px" }}>Rank</th>
                  <th style={{ minWidth: "220px" }}>Vendor Proposal</th>
                  <th
                    className="sortable-th"
                    onClick={() => handleSort("score_overall")}
                    style={{ width: "130px" }}
                  >
                    Overall Score {sortBy === "score_overall" ? (sortAsc ? "↑" : "↓") : ""}
                  </th>
                  <th
                    className="sortable-th"
                    onClick={() => handleSort("score_mandatory")}
                    style={{ width: "130px" }}
                  >
                    Mandatory {sortBy === "score_mandatory" ? (sortAsc ? "↑" : "↓") : ""}
                  </th>
                  <th
                    className="sortable-th"
                    onClick={() => handleSort("score_technical")}
                    style={{ width: "130px" }}
                  >
                    Technical {sortBy === "score_technical" ? (sortAsc ? "↑" : "↓") : ""}
                  </th>
                  <th
                    className="sortable-th"
                    onClick={() => handleSort("score_evidence_coverage")}
                    style={{ width: "140px" }}
                  >
                    Evidence {sortBy === "score_evidence_coverage" ? (sortAsc ? "↑" : "↓") : ""}
                  </th>
                  <th style={{ width: "100px" }}>Compliant</th>
                  <th style={{ width: "100px" }}>Review</th>
                  <th style={{ width: "110px" }}>Non-Compliant</th>
                  <th style={{ width: "100px" }}>Not Found</th>
                  <th style={{ width: "120px", textAlign: "right" }}>Inspect</th>
                </tr>
              </thead>
              <tbody>
                {vendors.map((v, idx) => {
                  const isSelected = selectedVendorId === v.id
                  return (
                    <tr
                      key={v.id || idx}
                      className={`table-row-hover ${isSelected ? "selected-vendor-row" : ""}`}
                      onClick={() => onSelectVendor(v.id)}
                    >
                      <td>
                        <span className={`rank-badge ${idx === 0 ? "rank-gold" : idx === 1 ? "rank-silver" : idx === 2 ? "rank-bronze" : ""}`}>
                          #{idx + 1}
                        </span>
                      </td>

                      <td>
                        <div className="vendor-name-group">
                          <strong className="vendor-name-text">{v.vendor_name}</strong>
                          <span className="vendor-code-text">{v.vendor_code}</span>
                        </div>
                      </td>

                      <td>
                        <div className="score-cell">
                          <strong className={`score-large ${v.score_overall >= 80 ? "green" : v.score_overall >= 60 ? "orange" : "red"}`}>
                            {v.score_overall}%
                          </strong>
                        </div>
                      </td>

                      <td>
                        <span className={`subscore-pill ${v.score_mandatory === 100 ? "status-compliant" : "status-non-compliant"}`}>
                          {v.score_mandatory}%
                        </span>
                      </td>

                      <td>
                        <span className="subscore-pill">
                          {v.score_technical}%
                        </span>
                      </td>

                      <td>
                        <div className="conf-block" title={`Evidence Coverage: ${v.score_evidence_coverage}%`}>
                          <div className="conf-bar-track">
                            <div
                              className={`conf-bar-fill animated-bar-fill ${v.score_evidence_coverage >= 85 ? "high" : v.score_evidence_coverage >= 70 ? "light-green" : v.score_evidence_coverage >= 50 ? "warning-red" : "low"}`}
                              style={{ width: `${v.score_evidence_coverage}%` }}
                            />
                          </div>
                          <span className="conf-text">{v.score_evidence_coverage}%</span>
                        </div>
                      </td>

                      <td>
                        <span className="count-tag green">✓ {v.compliant}</span>
                      </td>

                      <td>
                        <span className="count-tag orange">? {v.needs_review}</span>
                      </td>

                      <td>
                        <span className="count-tag red">✗ {v.non_compliant}</span>
                      </td>

                      <td>
                        <span className="count-tag gray">— {v.not_found}</span>
                      </td>

                      <td style={{ textAlign: "right" }}>
                        <button
                          className={`inspect-btn btn-press sm-btn ${isSelected ? "primary-btn" : "secondary-btn"}`}
                          onClick={(e) => {
                            e.stopPropagation()
                            onSelectVendor(v.id)
                          }}
                        >
                          {isSelected ? "Active View" : "View Matrix →"}
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ─────────────────────────────────────────────────────────────────── */}
      {/* 2. CROSS-VENDOR REQUIREMENT MATRIX (PART 17)                        */}
      {/* ─────────────────────────────────────────────────────────────────── */}
      {activeSubTab === "cross_matrix" && (
        <div className="cross-matrix-view animate-in">
          <div className="matrix-toolbar">
            <div className="toolbar-left">
              <span className="matrix-badge">Cross-Vendor Specification Grid</span>
            </div>
            <div className="toolbar-right">
              <div className="search-box interactive-search">
                <svg className="search-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#64748b" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="11" cy="11" r="8"/>
                  <line x1="21" y1="21" x2="16.65" y2="16.65"/>
                </svg>
                <input
                  type="text"
                  placeholder="Filter matrix requirements..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="search-input"
                />
                {searchTerm && (
                  <button className="clear-search-btn" onClick={() => setSearchTerm("")}>✕</button>
                )}
              </div>
            </div>
          </div>

          <div className="table-responsive-wrapper">
            <table className="compliance-grid-table cross-matrix-table">
              <thead>
                <tr>
                  <th style={{ width: "90px" }}>Code</th>
                  <th style={{ width: "180px" }}>Requirement</th>
                  <th style={{ minWidth: "220px" }}>Required Specification</th>
                  {vendors.map((v) => (
                    <th key={v.vendor_code} style={{ minWidth: "160px" }}>
                      <div className="th-vendor-hdr">
                        <strong>{v.vendor_name}</strong>
                        <span className="v-th-code">{v.vendor_code}</span>
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredMatrix.map((row) => (
                  <tr key={row.req_code} className="table-row-hover">
                    <td>
                      <span className="req-code-badge">{row.req_code}</span>
                    </td>
                    <td>
                      <strong className="param-name">{row.requirement}</strong>
                      {row.mandatory && <span className="mand-star" title="Mandatory Requirement"> ★</span>}
                    </td>
                    <td>
                      <span className="param-value">{row.required_value}</span>
                    </td>
                    {vendors.map((v) => {
                      const evalData = row.vendor_evaluations?.[v.vendor_code] || {}
                      const st = evalData.status || "NOT_FOUND"
                      const isComp = st === "COMPLIANT"
                      const isNon = st === "NON_COMPLIANT"
                      const isRev = st === "NEEDS_REVIEW"
                      return (
                        <td key={v.vendor_code} className="matrix-cell">
                          <div className={`matrix-status-chip ${isComp ? "cell-comp" : isNon ? "cell-non" : isRev ? "cell-rev" : "cell-not"}`}>
                            <span className="cell-icon">
                              {isComp ? "✓" : isNon ? "✗" : isRev ? "?" : "—"}
                            </span>
                            <span className="cell-status-label">{st}</span>
                          </div>
                          {evalData.vendor_value && evalData.vendor_value !== "Not Provided" && (
                            <div className="cell-snippet" title={evalData.vendor_value}>
                              {evalData.vendor_value}
                            </div>
                          )}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

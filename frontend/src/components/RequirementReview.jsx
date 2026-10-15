import { useState } from "react"

export default function RequirementReview({
  requirements,
  onUpdateRequirement,
  onDeleteRequirement,
  onProceedToVendors,
  onBackToTender,
}) {
  const [editingId, setEditingId] = useState(null)
  const [editName, setEditName] = useState("")
  const [editValue, setEditValue] = useState("")
  const [editCondition, setEditCondition] = useState("minimum")
  const [filter, setFilter] = useState("ALL")
  const [searchTerm, setSearchTerm] = useState("")

  const startEdit = (req) => {
    setEditingId(req.id)
    setEditName(req.name)
    setEditValue(req.value || "")
    setEditCondition(req.condition || "minimum")
  }

  const saveEdit = (id) => {
    onUpdateRequirement(id, {
      name: editName,
      value: editValue,
      condition: editCondition,
    })
    setEditingId(null)
  }

  const toggleMandatory = (req) => {
    onUpdateRequirement(req.id, {
      mandatory: !req.mandatory,
      requirement_type: !req.mandatory ? "MANDATORY" : "PREFERRED",
    })
  }

  const filteredRequirements = (requirements || []).filter((r) => {
    if (r.is_active === false) return false
    const matchesFilter =
      filter === "ALL" ||
      (filter === "MANDATORY" && r.mandatory) ||
      (filter === "PREFERRED" && !r.mandatory) ||
      (filter === "TECHNICAL" && (r.category === "technical" || r.domain === "TECHNICAL")) ||
      (filter === "COMMERCIAL" && (r.category === "commercial" || r.domain === "COMMERCIAL"))
    const matchesSearch =
      !searchTerm ||
      r.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (r.value && r.value.toLowerCase().includes(searchTerm.toLowerCase())) ||
      r.req_code.toLowerCase().includes(searchTerm.toLowerCase())
    return matchesFilter && matchesSearch
  })

  const activeCount = (requirements || []).filter((r) => r.is_active !== false).length
  const mandatoryCount = (requirements || []).filter((r) => r.is_active !== false && r.mandatory).length

  return (
    <div className="requirement-review-card card-interactive reveal-on-scroll">
      {/* Checkpoint Header */}
      <div className="review-checkpoint-banner">
        <div className="banner-left">
          <span className="gov-seal-icon">⚖️</span>
          <div>
            <div className="checkpoint-tag">HUMAN-IN-THE-LOOP CHECKPOINT (PART 29)</div>
            <h2 className="checkpoint-title">Tender Requirement Curation</h2>
            <p className="checkpoint-sub">
              Review and verify the AI-extracted specifications before vendor proposals are analyzed. You may edit, toggle mandatory criteria, or delete spurious rows.
            </p>
          </div>
        </div>
        <div className="checkpoint-counts">
          <div className="count-stat-pill">
            <span className="count-label">Detected Criteria</span>
            <strong className="count-val">{activeCount}</strong>
          </div>
          <div className="count-stat-pill">
            <span className="count-label">Mandatory</span>
            <strong className="count-val mandatory-color">{mandatoryCount}</strong>
          </div>
        </div>
      </div>

      {/* Toolbar */}
      <div className="matrix-toolbar">
        <div className="toolbar-left">
          <div className="filter-pill-group">
            <button
              className={`filter-pill ${filter === "ALL" ? "active" : ""}`}
              onClick={() => setFilter("ALL")}
            >
              All ({activeCount})
            </button>
            <button
              className={`filter-pill ${filter === "MANDATORY" ? "active" : ""}`}
              onClick={() => setFilter("MANDATORY")}
            >
              Mandatory ({mandatoryCount})
            </button>
            <button
              className={`filter-pill ${filter === "PREFERRED" ? "active" : ""}`}
              onClick={() => setFilter("PREFERRED")}
            >
              Preferred ({activeCount - mandatoryCount})
            </button>
          </div>
        </div>

        <div className="toolbar-right">
          <div className="search-box interactive-search">
            <svg className="search-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#64748b" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8"/>
              <line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            <input
              type="text"
              placeholder="Search extracted criteria..."
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

      {/* Requirements Table */}
      <div className="table-responsive-wrapper">
        <table className="compliance-grid-table">
          <thead>
            <tr>
              <th style={{ width: "100px" }}>Code</th>
              <th style={{ width: "220px" }}>Specification / Parameter</th>
              <th>Required Tender Specification</th>
              <th style={{ width: "130px" }}>Condition</th>
              <th style={{ width: "130px" }}>Obligation</th>
              <th style={{ width: "120px", textAlign: "right" }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredRequirements.map((req) => {
              const isEditing = editingId === req.id
              return (
                <tr key={req.id} className="table-row-hover">
                  <td>
                    <span className="req-code-badge">{req.req_code}</span>
                  </td>

                  <td>
                    {isEditing ? (
                      <input
                        type="text"
                        className="cell-edit-input"
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                      />
                    ) : (
                      <strong className="param-name">{req.name}</strong>
                    )}
                  </td>

                  <td>
                    {isEditing ? (
                      <textarea
                        className="cell-edit-textarea"
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        rows={2}
                      />
                    ) : (
                      <span className="param-value">{req.value}</span>
                    )}
                  </td>

                  <td>
                    {isEditing ? (
                      <select
                        className="cell-edit-select"
                        value={editCondition}
                        onChange={(e) => setEditCondition(e.target.value)}
                      >
                        <option value="minimum">MINIMUM</option>
                        <option value="maximum">MAXIMUM</option>
                        <option value="exact">EXACT</option>
                        <option value="range">RANGE</option>
                        <option value="negative">NEGATIVE</option>
                      </select>
                    ) : (
                      <span className="condition-pill">{req.condition?.toUpperCase() || "MINIMUM"}</span>
                    )}
                  </td>

                  <td>
                    <button
                      className={`mandatory-toggle-btn ${req.mandatory ? "mand-active" : "pref-active"}`}
                      onClick={() => toggleMandatory(req)}
                      title="Click to toggle between Mandatory and Preferred"
                    >
                      {req.mandatory ? "★ MANDATORY" : "☆ PREFERRED"}
                    </button>
                  </td>

                  <td style={{ textAlign: "right" }}>
                    <div className="action-row-buttons">
                      {isEditing ? (
                        <>
                          <button
                            className="save-action-btn btn-press"
                            onClick={() => saveEdit(req.id)}
                            title="Save changes"
                          >
                            ✓ Save
                          </button>
                          <button
                            className="cancel-action-btn btn-press"
                            onClick={() => setEditingId(null)}
                            title="Cancel"
                          >
                            ✕
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            className="edit-action-btn btn-press"
                            onClick={() => startEdit(req)}
                            title="Edit specification"
                          >
                            ✎
                          </button>
                          <button
                            className="delete-action-btn btn-press"
                            onClick={() => onDeleteRequirement(req.id)}
                            title="Delete spurious requirement"
                          >
                            🗑
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Checkpoint Footer Actions */}
      <div className="checkpoint-footer-actions">
        <button className="secondary-btn btn-press" onClick={onBackToTender}>
          ← Re-upload Tender
        </button>

        <div className="proceed-box">
          <span className="curation-verified-note">
            ✓ Curation Checkpoint: {activeCount} requirements verified by human officer
          </span>
          <button className="primary-btn lg-btn btn-press" onClick={onProceedToVendors}>
            <span>Proceed to Vendor Bids ({activeCount} Criteria) →</span>
          </button>
        </div>
      </div>
    </div>
  )
}

import React, { useState } from "react"

export default function CreateTenderModal({ isOpen, onClose, onCreate }) {
  const today = new Date().toISOString().split("T")[0]
  const defaultClose = new Date(Date.now() + 10 * 24 * 60 * 60 * 1000).toISOString().split("T")[0]

  const [title, setTitle] = useState("")
  const [tenderRef, setTenderRef] = useState("")
  const [startDate, setStartDate] = useState(today)
  const [closingDate, setClosingDate] = useState(defaultClose)
  const [description, setDescription] = useState("")
  const [initialStatus, setInitialStatus] = useState("ACTIVE")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [formError, setFormError] = useState("")

  if (!isOpen) return null

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!title.trim()) {
      setFormError("Tender title is required.")
      return
    }

    setIsSubmitting(true)
    setFormError("")

    try {
      await onCreate({
        title: title.trim(),
        tender_reference: tenderRef.trim() || null,
        start_date: startDate ? new Date(startDate).toISOString() : null,
        closing_date: closingDate ? new Date(closingDate).toISOString() : null,
        description: description.trim() || null,
        status: initialStatus,
      })
      // Reset
      setTitle("")
      setTenderRef("")
      setDescription("")
      onClose()
    } catch (err) {
      setFormError(err.message || "Failed to create tender.")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="modal-backdrop opening" onClick={onClose}>
      <div
        className="share-modal-card card-interactive"
        style={{ maxWidth: 580 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-hdr">
          <div className="hdr-title-lockup">
            <div className="brand-logo-badge" style={{ width: 34, height: 34, borderRadius: 8 }}>
              📋
            </div>
            <div>
              <h3 style={{ fontSize: 18, color: "var(--primary-navy)" }}>Create Procurement Tender</h3>
              <p className="modal-sub">Initialize an independent GeM procurement workspace</p>
            </div>
          </div>
          <button className="drawer-close-btn" onClick={onClose}>✕</button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-content-stack" style={{ padding: "20px 24px" }}>
            {formError && (
              <div className="alert-box alert-error" style={{ padding: "8px 12px", marginBottom: 8, fontSize: 13 }}>
                ⚠️ {formError}
              </div>
            )}

            <div className="input-group">
              <label htmlFor="tender-title">Tender Title *</label>
              <input
                id="tender-title"
                type="text"
                className="cell-edit-input"
                placeholder="e.g. Procurement of High-Performance Laptops & Workstations"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
              />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
              <div className="input-group">
                <label htmlFor="tender-ref">GeM Bid / Tender Reference</label>
                <input
                  id="tender-ref"
                  type="text"
                  className="cell-edit-input"
                  placeholder="e.g. GEM/2026/B/882190"
                  value={tenderRef}
                  onChange={(e) => setTenderRef(e.target.value)}
                />
              </div>

              <div className="input-group">
                <label htmlFor="tender-status">Initial Lifecycle Status</label>
                <select
                  id="tender-status"
                  className="cell-edit-select"
                  value={initialStatus}
                  onChange={(e) => setInitialStatus(e.target.value)}
                >
                  <option value="ACTIVE">Active (Accepting Bids)</option>
                  <option value="DRAFT">Draft</option>
                </select>
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
              <div className="input-group">
                <label htmlFor="tender-start">Start Date</label>
                <input
                  id="tender-start"
                  type="date"
                  className="cell-edit-input"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                />
              </div>

              <div className="input-group">
                <label htmlFor="tender-closing">Closing Deadline Date</label>
                <input
                  id="tender-closing"
                  type="date"
                  className="cell-edit-input"
                  value={closingDate}
                  onChange={(e) => setClosingDate(e.target.value)}
                />
              </div>
            </div>

            <div className="input-group">
              <label htmlFor="tender-desc">Procurement Scope / Description</label>
              <textarea
                id="tender-desc"
                className="cell-edit-textarea"
                rows={3}
                placeholder="Scope of supply, eligibility terms, warranty, and technical guidelines..."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
          </div>

          <div className="modal-ftr">
            <button
              type="button"
              className="outline-btn btn-press"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="primary-btn btn-press"
              disabled={isSubmitting}
            >
              {isSubmitting ? "Creating..." : "Create Tender Workspace"}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

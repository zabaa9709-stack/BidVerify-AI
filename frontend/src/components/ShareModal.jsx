import { useState } from "react"

export default function ShareModal({
  workspace,
  onClose,
  onCreateShareLink,
}) {
  const [days, setDays] = useState(7)
  const [createdLink, setCreatedLink] = useState(null)
  const [loading, setLoading] = useState(false)
  const [copied, setCopied] = useState(false)

  const handleGenerate = async () => {
    setLoading(true)
    try {
      const res = await onCreateShareLink(days)
      setCreatedLink(res)
    } finally {
      setLoading(false)
    }
  }

  const handleCopy = () => {
    if (!createdLink) return
    const fullUrl = `${window.location.origin}/?share=${createdLink.share_token}`
    navigator.clipboard.writeText(fullUrl)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="modal-backdrop opening" onClick={onClose}>
      <div className="share-modal-card card-interactive" onClick={(e) => e.stopPropagation()}>
        <div className="modal-hdr">
          <div className="hdr-title-lockup">
            <span className="gov-seal-icon">🔗</span>
            <div>
              <h3>Secure Read-Only Sharing</h3>
              <p className="modal-sub">Generate a temporary, non-guessable link to share this verification.</p>
            </div>
          </div>
          <button className="alert-close btn-press" onClick={onClose}>✕</button>
        </div>

        <div className="modal-body-pad">
          <div className="share-info-banner">
            <strong>Security Notice (PART 3):</strong>
            <p>Shared links provide read-only access to evaluation scores and evidence matrices. Recipients cannot upload, modify, or delete tender data. Links can be revoked by the owner at any time.</p>
          </div>

          {!createdLink ? (
            <div className="create-share-flow">
              <div className="input-group">
                <label>Link Expiration Period:</label>
                <select
                  value={days}
                  onChange={(e) => setDays(Number(e.target.value))}
                  className="cell-edit-select"
                >
                  <option value={1}>1 Day</option>
                  <option value={7}>7 Days (Standard)</option>
                  <option value={14}>14 Days</option>
                  <option value={30}>30 Days</option>
                </select>
              </div>

              <button
                className="primary-btn btn-press full-width-btn"
                onClick={handleGenerate}
                disabled={loading}
              >
                {loading ? "Generating Secure Token..." : "Generate Read-Only Share Link"}
              </button>
            </div>
          ) : (
            <div className="share-link-result animate-in">
              <label>Copyable Share Link:</label>
              <div className="link-copy-row">
                <input
                  type="text"
                  readOnly
                  value={`${window.location.origin}/?share=${createdLink.share_token}`}
                  className="share-link-input"
                />
                <button
                  className={`copy-btn btn-press ${copied ? "copied" : "primary-btn"}`}
                  onClick={handleCopy}
                >
                  {copied ? "✓ Copied!" : "Copy"}
                </button>
              </div>

              <div className="share-meta-row">
                <span>Expires: <strong>{new Date(createdLink.expires_at).toLocaleDateString()}</strong></span>
                <span>•</span>
                <span className="status-compliant-text">Active & Unguessable</span>
              </div>
            </div>
          )}
        </div>

        <div className="modal-ftr">
          <button className="secondary-btn btn-press" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  )
}

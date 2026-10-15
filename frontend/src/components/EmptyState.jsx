export default function EmptyState({ onStartVerification }) {
  return (
    <div className="empty-state-panel">
      <div className="empty-state-icon">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
          <line x1="16" y1="13" x2="8" y2="13"/>
          <line x1="16" y1="17" x2="8" y2="17"/>
          <polyline points="10 9 9 9 8 9"/>
        </svg>
      </div>
      <h3 className="empty-title">No verification results yet</h3>
      <p className="empty-desc">
        Upload an official GeM tender document and vendor technical bid to begin automated compliance analysis.
      </p>
      <button className="primary-btn" onClick={onStartVerification}>
        + Start New Verification
      </button>
    </div>
  )
}

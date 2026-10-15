export default function Navbar({ activeTab, setActiveTab, hasResults, scrollProgress = 0 }) {
  return (
    <header className="gov-navbar">
      {/* Scroll Progress Bar at very top of header */}
      <div
        className="nav-scroll-progress"
        style={{ width: `${Math.min(Math.max(scrollProgress, 0), 100)}%` }}
        aria-hidden="true"
      />

      <div className="nav-container">
        <div className="nav-left">
          <div
            className="brand-lockup interactive-hover"
            onClick={() => setActiveTab("dashboard")}
            role="button"
            tabIndex={0}
          >
            <div className="brand-logo-badge">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                <path d="m9 12 2 2 4-4"/>
              </svg>
            </div>
            <div>
              <div className="brand-title">BidVerify <span className="brand-ai">AI</span></div>
              <div className="brand-subtitle">GeM Bid Compliance Intelligence</div>
            </div>
          </div>

          <nav className="nav-links" aria-label="Main Navigation">
            <button
              className={`nav-tab ${activeTab === "dashboard" ? "active" : ""}`}
              onClick={() => setActiveTab("dashboard")}
            >
              <span>Dashboard</span>
              {activeTab === "dashboard" && <span className="nav-tab-indicator" />}
            </button>
            <button
              className={`nav-tab ${activeTab === "new_verification" ? "active" : ""}`}
              onClick={() => setActiveTab("new_verification")}
            >
              <span>New Verification</span>
              {activeTab === "new_verification" && <span className="nav-tab-indicator" />}
            </button>
            {hasResults && (
              <button
                className={`nav-tab results-tab ${activeTab === "results" ? "active" : ""}`}
                onClick={() => setActiveTab("results")}
              >
                <span>Verification Results</span>
                {activeTab === "results" && <span className="nav-tab-indicator" />}
              </button>
            )}
          </nav>
        </div>

        <div className="nav-right">
          <div className="sys-status-badge interactive-hover">
            <span className="status-dot online pulse-dot"></span>
            <span className="status-text">Backend Online</span>
          </div>
          <div className="portal-tag">GeM SPV v2.4</div>
        </div>
      </div>
    </header>
  )
}

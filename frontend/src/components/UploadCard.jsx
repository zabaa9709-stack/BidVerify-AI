import { useState } from "react"

export default function UploadCard({
  id,
  title,
  subtitle,
  dropText,
  file,
  onFileSelect,
  onFileRemove,
  disabled
}) {
  const [isDragging, setIsDragging] = useState(false)

  const formatFileSize = (bytes) => {
    if (!bytes && bytes !== 0) return ""
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
  }

  const handleDragOver = (e) => {
    e.preventDefault()
    if (!disabled) setIsDragging(true)
  }

  const handleDragLeave = (e) => {
    e.preventDefault()
    setIsDragging(false)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setIsDragging(false)
    if (disabled) return
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0]
      const ext = droppedFile.name.toLowerCase().split('.').pop()
      if (['pdf', 'docx'].includes(ext) || droppedFile.type.includes("pdf") || droppedFile.type.includes("word")) {
        onFileSelect(droppedFile)
      }
    }
  }

  const fileExt = file ? file.name.split('.').pop().toUpperCase() : "PDF"

  return (
    <div
      className={`doc-upload-card ${isDragging ? "dragging" : ""} ${file ? "has-file" : ""} card-interactive`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      <input
        type="file"
        id={id}
        accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        hidden
        disabled={disabled}
        onChange={(e) => {
          if (e.target.files && e.target.files[0]) {
            onFileSelect(e.target.files[0])
          }
        }}
      />

      <div className="doc-card-header">
        <div className="doc-type-icon micro-icon">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/>
            <polyline points="14 2 14 8 20 8"/>
            <path d="M10 12v6"/>
            <path d="m13 15-3-3-3 3"/>
          </svg>
        </div>
        <div>
          <h3 className="doc-card-title">{title}</h3>
          <p className="doc-card-sub">{subtitle}</p>
        </div>
      </div>

      {!file ? (
        <div className="dropzone-area">
          <div className="dropzone-icon pulse-on-hover">
            <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="17 8 12 3 7 8"/>
              <line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
          </div>
          <p className="dropzone-prompt">{dropText}</p>
          <span className="dropzone-hint">Format accepted: PDF or DOCX up to 25MB</span>
          <label htmlFor={id} className="browse-button btn-press">
            Browse Document
          </label>
        </div>
      ) : (
        <div className="selected-file-panel animate-file-staged">
          <div className="file-info-row">
            <div className="file-badge badge-pop">{fileExt}</div>
            <div className="file-meta">
              <div className="file-name-text slide-in-text" title={file.name}>
                {file.name}
              </div>
              <div className="file-size-text">
                {formatFileSize(file.size)} • Document ready for verification
              </div>
            </div>
            <div className="file-actions">
              <label htmlFor={id} className="action-btn change-btn btn-press" title="Replace file">
                Change
              </label>
              {onFileRemove && (
                <button
                  type="button"
                  className="action-btn remove-btn btn-press"
                  onClick={onFileRemove}
                  title="Remove file"
                  disabled={disabled}
                >
                  ✕
                </button>
              )}
            </div>
          </div>
          <div className="upload-success-indicator success-pop">
            <svg className="check-pop-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
            <span>Document verified and staged for analysis</span>
          </div>
        </div>
      )}
    </div>
  )
}

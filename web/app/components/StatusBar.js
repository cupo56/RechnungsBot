'use client';

// page.js renders this unconditionally, with a progress bar tied to `loading`,
// and no color class on the dot for non-error/non-loading states. provision/
// credit-note only render it once status.text is set, never show a progress
// bar, and do apply a "success" color class as the neutral-state fallback.
// Both behaviors are preserved exactly via props rather than picking one.
export default function StatusBar({ status, loading = false, showProgress = false, alwaysVisible = false, neutralDotClass = '', style }) {
  if (!alwaysVisible && !status.text) return null;

  return (
    <div className="status-bar" id={alwaysVisible ? 'status-bar' : undefined} style={style}>
      <div className={`status-dot ${status.type === 'error' ? 'error' : status.type === 'loading' ? 'loading' : neutralDotClass}`}></div>
      <span className="status-text">{status.text}</span>
      {status.detail && (
        <span className="status-detail">Technisch: {status.detail}</span>
      )}
      {showProgress && loading && (
        <div className="progress-bar-container">
          <div className="progress-bar-fill"></div>
        </div>
      )}
    </div>
  );
}

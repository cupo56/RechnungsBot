'use client';

export default function ComparePage() {
  return (
    <div className="app-container">
      <header className="app-header">
        <div className="header-content">
          <h1 className="header-title">🔍 VergleichsBot</h1>
          <p className="header-subtitle">Vergleicht eine alte Excel-Liste mit einer neuen und markiert Änderungen.</p>
        </div>
      </header>
      
      <div className="empty-state">
        <div className="empty-state-icon">🚧</div>
        <h2 style={{ marginBottom: 12 }}>Befindet sich im Aufbau</h2>
        <p className="empty-state-text">
          Die Funktionalität für den Excel-Vergleich wird in Kürze in der Web-Version verfügbar sein.
        </p>
      </div>
    </div>
  );
}

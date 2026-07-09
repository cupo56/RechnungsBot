'use client';

export default function DropZone({
  loading, loadedFiles, itemCount, dragOver,
  onDragOver, onDragLeave, onDrop, onBrowse, onFileChange, fileInputRef,
  removeFile,
}) {
  return (
    <>
      {/* ── Drop Zone ── */}
      <div
        id="drop-zone"
        className={`drop-zone ${dragOver ? 'drag-over' : ''} ${loadedFiles.length > 0 ? 'loaded' : ''}`}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        onClick={onBrowse}
      >
        <span className="drop-zone-icon">
          {loading ? <span className="spinner"></span> : loadedFiles.length > 0 ? '✅' : '📂'}
        </span>
        <p className="drop-zone-text">
          {loading
            ? 'Datei(en) werden eingelesen…'
            : loadedFiles.length > 0
              ? `${loadedFiles.length} Datei(en) · ${itemCount} Positionen geladen — weitere Dateien hier ablegen`
              : 'Excel- oder PDF-Datei(en) hierher ziehen oder klicken zum Auswählen'
          }
        </p>
        {loadedFiles.length === 0 && !loading && (
          <p className="drop-zone-hint">Unterstützt: .xlsx, .xls, .pdf (auch mehrere gleichzeitig)</p>
        )}
        <input
          ref={fileInputRef}
          type="file"
          accept=".xlsx,.xls,.pdf"
          multiple
          onChange={onFileChange}
          id="file-input"
        />
      </div>

      {/* ── Loaded Files List ── */}
      {loadedFiles.length > 0 && (
        <div className="loaded-files-list" id="loaded-files-list">
          {loadedFiles.map(f => (
            <div key={f.id} className={`loaded-file-row ${f.status === 'error' ? 'error' : ''}`}>
              <span className="loaded-file-name">{f.name}</span>
              <span className="loaded-file-count">
                {f.status === 'error'
                  ? f.error
                  : f.isOwnInvoice
                    ? `📄 Importierte Rechnung · ${f.count} Positionen`
                    : f.format
                      ? `${f.count} Positionen · Format: ${f.format}`
                      : `${f.count} Positionen`}
              </span>
              <button className="loaded-file-remove" onClick={() => removeFile(f.id)} title="Datei entfernen">🗑</button>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

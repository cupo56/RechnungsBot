'use client';

import { useState, useCallback } from 'react';
import { apiHeaders } from '../utils/apiAuth';
import { useToast } from '../utils/useToast';
import Toast from '../components/Toast';
import StatusBar from '../components/StatusBar';
import { Link as LinkIcon, RotateCcw, Download, ClipboardList, Package, CheckCircle2 } from 'lucide-react';

// Anders als beim Haupt-Upload (web/app/page.js, ein File pro Request) werden
// hier BEIDE Dateien in einem einzigen Request an /api/order/apply gesendet,
// daher halbiertes Pro-Datei-Limit: Vercel's Request-Body-Limit liegt bei
// ~4.5 MB, Base64 bläht die Rohgröße jeder Datei um ~33% auf, macht bei zwei
// kombinierten Dateien ~4.5 MB in Summe.
const MAX_SIZE = 1.6 * 1024 * 1024;

async function fileToBase64(file) {
  const buffer = await file.arrayBuffer();
  return btoa(Array.from(new Uint8Array(buffer), (b) => String.fromCharCode(b)).join(''));
}

function UploadBox({ icon: Icon, title, hint, filename, onFileChange, inputId }) {
  return (
    <div
      className={`drop-zone ${filename ? 'loaded' : ''}`}
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => e.preventDefault()}
    >
      <label htmlFor={inputId} style={{ cursor: 'pointer', display: 'block' }}>
        <span className="drop-zone-icon">
          {filename ? <CheckCircle2 size={40} strokeWidth={1.5} /> : <Icon size={40} strokeWidth={1.5} />}
        </span>
        <p className="drop-zone-text">{filename ? `${title}: ${filename}` : title}</p>
        {!filename && <p className="drop-zone-hint">{hint}</p>}
      </label>
      <input id={inputId} type="file" accept=".xlsx" onChange={onFileChange} />
    </div>
  );
}

export default function OrderPage() {
  const [sourceFile, setSourceFile] = useState(null);
  const [targetFile, setTargetFile] = useState(null);
  const [result, setResult] = useState(null);
  const [applying, setApplying] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [status, setStatus] = useState({ text: '', type: 'idle' });
  const [toast, setToast] = useToast();

  const handleFileChange = useCallback(
    (setFile) => async (e) => {
      const file = e.target.files?.[0];
      e.target.value = '';
      if (!file) return;
      if (!/\.xlsx$/i.test(file.name)) {
        setToast({ text: `❌ ${file.name}: nur .xlsx unterstützt`, type: 'error' });
        return;
      }
      if (file.size > MAX_SIZE) {
        setToast({ text: `❌ Datei zu groß (max. ${(MAX_SIZE / 1024 / 1024).toFixed(1)} MB)`, type: 'error' });
        return;
      }
      const base64 = await fileToBase64(file);
      setFile({ filename: file.name, base64 });
      setResult(null);
      setStatus({ text: '', type: 'idle' });
    },
    [setToast]
  );

  const handleApply = useCallback(async () => {
    if (!sourceFile || !targetFile) return;
    setApplying(true);
    setStatus({ text: 'Order-Mengen werden abgeglichen…', type: 'loading' });
    try {
      const resp = await fetch('/api/order/apply', {
        method: 'POST',
        headers: apiHeaders(),
        body: JSON.stringify({
          source_filename: sourceFile.filename,
          source_file_base64: sourceFile.base64,
          target_filename: targetFile.filename,
          target_file_base64: targetFile.base64,
        }),
      });
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({ error: `HTTP ${resp.status}` }));
        throw new Error(errData.error || `Fehler ${resp.status}`);
      }
      const data = await resp.json();
      setResult(data);
      const parts = [`✓ ${data.n_matched} gefunden`];
      if (data.n_not_found) parts.push(`⚠️ ${data.n_not_found} nicht gefunden`);
      setStatus({ text: parts.join('  ·  '), type: data.n_not_found ? 'error' : 'success' });
    } catch (err) {
      setStatus({ text: `Fehler: ${err.message}`, type: 'error' });
      setToast({ text: `❌ ${err.message}`, type: 'error' });
    } finally {
      setApplying(false);
    }
  }, [sourceFile, targetFile, setToast]);

  const handleExport = useCallback(async () => {
    if (!result) return;
    setExporting(true);
    try {
      const resp = await fetch('/api/order/export', {
        method: 'POST',
        headers: apiHeaders(),
        body: JSON.stringify({ headers: result.headers, rows: result.rows }),
      });
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({ error: `HTTP ${resp.status}` }));
        throw new Error(errData.error || `Fehler ${resp.status}`);
      }
      const data = await resp.json();
      const link = document.createElement('a');
      link.href = `data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,${data.xlsx_base64}`;
      link.download = data.filename || 'Order-Ergebnis.xlsx';
      link.click();
      setToast({ text: '✅ Excel-Datei exportiert', type: 'success' });
    } catch (err) {
      setToast({ text: `❌ ${err.message}`, type: 'error' });
    } finally {
      setExporting(false);
    }
  }, [result, setToast]);

  const handleReset = useCallback(() => {
    setSourceFile(null);
    setTargetFile(null);
    setResult(null);
    setStatus({ text: '', type: 'idle' });
  }, []);

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="header-content">
          <h1 className="header-title"><LinkIcon size={26} strokeWidth={2} className="header-title-icon" /> OrderBot</h1>
          <p className="header-subtitle">Bestellmengen per EAN in eine Ziel-Liste übernehmen</p>
        </div>
        <div className="header-actions">
          {(sourceFile || targetFile || result) && (
            <button className="btn btn-secondary" onClick={handleReset}>
              <RotateCcw size={16} strokeWidth={2} /> Neue Order-Prüfung
            </button>
          )}
        </div>
      </header>

      <div className="panels-row">
        <UploadBox
          icon={ClipboardList}
          title="Bestellliste laden"
          hint="EAN + Order-Menge  (.xlsx)"
          filename={sourceFile?.filename}
          inputId="order-source-input"
          onFileChange={handleFileChange(setSourceFile)}
        />
        <UploadBox
          icon={Package}
          title="Ziel-Liste laden"
          hint="mit EAN-Spalte  (.xlsx)"
          filename={targetFile?.filename}
          inputId="order-target-input"
          onFileChange={handleFileChange(setTargetFile)}
        />
      </div>

      <div style={{ textAlign: 'center', margin: '8px 0 24px' }}>
        <button
          className="btn btn-primary btn-lg"
          disabled={!sourceFile || !targetFile || applying}
          onClick={handleApply}
        >
          <LinkIcon size={18} strokeWidth={2} /> {applying ? 'Wird abgeglichen…' : 'Order anwenden'}
        </button>
      </div>

      <StatusBar status={status} neutralDotClass="success" />

      {result && (
        <div className="table-section">
          <div className="table-toolbar">
            <div className="table-toolbar-left">
              <strong>Ergebnis</strong>
            </div>
            <button className="btn btn-primary btn-sm" disabled={exporting} onClick={handleExport}>
              <Download size={16} strokeWidth={2} /> {exporting ? 'Exportiere…' : 'Als Excel exportieren'}
            </button>
          </div>
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  {result.headers.map((h, i) => (
                    <th key={i} className={i === result.headers.length - 1 ? 'text-center' : ''}>
                      {h || '—'}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.rows.map((row, ri) => {
                  const orderValue = row[row.length - 1];
                  const notFound = orderValue === 'Nicht gefunden';
                  return (
                    <tr key={ri}>
                      {row.map((cell, ci) => {
                        const isLast = ci === row.length - 1;
                        return (
                          <td
                            key={ci}
                            className={isLast ? 'text-center' : ''}
                            style={
                              isLast
                                ? { color: notFound ? 'var(--danger-500)' : 'var(--success-600)', fontWeight: 600 }
                                : undefined
                            }
                          >
                            {cell === null || cell === undefined ? '' : String(cell)}
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <Toast toast={toast} onDismiss={() => setToast(null)} />
    </div>
  );
}

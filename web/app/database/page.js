'use client';

import { useState, useEffect, useCallback } from 'react';

// ─── Constants ───────────────────────────────────────────
const CONFIG_KEY = 'rechnungsbot_config';

const DEFAULT_CONFIG = {
  db_enabled: false,
};

const DOC_TYPES = {
  'alle': 'Alle Dokumente',
  'rechnung': '📄 Rechnungen',
  'lieferschein': '📦 Lieferscheine',
  'provision': '💰 Provisionsrechnungen',
  'gutschrift': '🧾 Gutschriften',
};

const DOC_TYPE_LABELS = {
  'rechnung': '📄 Rechnung',
  'lieferschein': '📦 Lieferschein',
  'provision': '💰 Provision',
  'gutschrift': '🧾 Gutschrift',
};

// ─── Helpers ─────────────────────────────────────────────
function loadConfig() {
  try {
    const stored = localStorage.getItem(CONFIG_KEY);
    if (stored) {
      const parsed = JSON.parse(stored);
      // Migration: eine ältere Version speicherte den API-Key im Klartext in
      // localStorage. Falls noch vorhanden, sofort entfernen und persistieren,
      // statt nur zukünftige Speicherungen zu vermeiden.
      if ('db_api_key' in parsed || 'db_api_url' in parsed) {
        delete parsed.db_api_key;
        delete parsed.db_api_url;
        try { localStorage.setItem(CONFIG_KEY, JSON.stringify(parsed)); } catch { /* ignore */ }
      }
      return { ...DEFAULT_CONFIG, ...parsed };
    }
  } catch { /* ignore */ }
  return { ...DEFAULT_CONFIG };
}

function saveConfig(cfg) {
  try {
    const stored = loadConfig();
    localStorage.setItem(CONFIG_KEY, JSON.stringify({ ...stored, ...cfg }));
  } catch { /* ignore */ }
}

function formatNumber(val) {
  const num = parseFloat(val) || 0;
  return num.toLocaleString('de-AT', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// ─── Main Page Component ─────────────────────────────────
export default function DatabasePage() {
  // --- State: Config ---
  const [config, setConfig] = useState(DEFAULT_CONFIG);
  const [settingsVisible, setSettingsVisible] = useState(false);
  
  // --- State: Data ---
  const [invoices, setInvoices] = useState([]);
  const [search, setSearch] = useState('');
  const [docFilter, setDocFilter] = useState('alle');
  
  // --- State: UI ---
  const [status, setStatus] = useState({ text: '⏳ Prüfe Konfiguration…', type: 'loading' });
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState(null);

  // ─── Auto-hide toast ──────────────────────────────────
  useEffect(() => {
    if (toast) {
      const t = setTimeout(() => setToast(null), 4000);
      return () => clearTimeout(t);
    }
  }, [toast]);

  // ─── Initialize ───────────────────────────────────────
  useEffect(() => {
    const cfg = loadConfig();
    setConfig(cfg);
    testConnectionAndLoad();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ─── API Calls ────────────────────────────────────────
  // URL und API-Key werden ausschließlich serverseitig (DB_API_URL/DB_API_KEY)
  // verwaltet — der Client schickt und speichert keine Zugangsdaten mehr.
  const callApi = async (action, data = {}) => {
    const res = await fetch('/api/database', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, ...data }),
    });
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    return res.json();
  };

  const testConnectionAndLoad = async () => {
    setStatus({ text: '⏳ Verbindung wird getestet…', type: 'loading' });
    try {
      const res = await callApi('test');
      if (res.success) {
        setStatus({ text: `✅ Verbunden — ${res.message || 'OK'}`, type: 'success' });
        if (!config.db_enabled) {
          saveConfig({ db_enabled: true });
          setConfig(prev => ({ ...prev, db_enabled: true }));
        }
        loadInvoices();
      } else {
        setStatus({ text: `❌ Fehler: ${res.message}`, type: 'error' });
      }
    } catch (err) {
      setStatus({ text: `❌ Verbindungsfehler: ${err.message}`, type: 'error' });
    }
  };

  const loadInvoices = async () => {
    setLoading(true);
    try {
      const data = {};
      if (search.trim()) data.search = search.trim();
      if (docFilter !== 'alle') data.doc_type = docFilter;

      const res = await callApi('list', data);
      if (res.success) {
        setInvoices(res.invoices || []);
      } else {
        setToast({ text: `❌ Fehler beim Laden: ${res.message}`, type: 'error' });
      }
    } catch (err) {
      setToast({ text: `❌ Fehler beim Laden: ${err.message}`, type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const downloadPdf = async (invoiceId, defaultFilename) => {
    setToast({ text: '⏳ PDF wird geladen…', type: 'success' });
    try {
      const res = await callApi('get_pdf', { invoice_id: invoiceId });
      if (res.success && res.pdf_data) {
        const link = document.createElement('a');
        link.href = `data:application/pdf;base64,${res.pdf_data}`;
        link.download = res.pdf_filename || defaultFilename || 'dokument.pdf';
        link.click();
        setToast({ text: `✅ PDF heruntergeladen: ${link.download}`, type: 'success' });
      } else {
        setToast({ text: `❌ Fehler: ${res.message || 'PDF nicht gefunden'}`, type: 'error' });
      }
    } catch (err) {
      setToast({ text: `❌ Fehler beim Download: ${err.message}`, type: 'error' });
    }
  };

  const deleteInvoice = async (invoiceId, number, customer) => {
    if (!confirm(`Soll das Dokument '${number}' (Kunde: ${customer}) wirklich aus der Datenbank gelöscht werden?\n\nDieser Vorgang kann nicht rückgängig gemacht werden.`)) {
      return;
    }
    
    setLoading(true);
    try {
      const res = await callApi('delete', { invoice_id: invoiceId });
      if (res.success) {
        setToast({ text: `🗑 Dokument gelöscht.`, type: 'success' });
        loadInvoices();
      } else {
        setToast({ text: `❌ Fehler beim Löschen: ${res.message}`, type: 'error' });
      }
    } catch (err) {
      setToast({ text: `❌ Fehler beim Löschen: ${err.message}`, type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const initDatabase = async () => {
    setStatus({ text: '⏳ Initialisiere Datenbank…', type: 'loading' });
    try {
      const resInit = await callApi('init');
      if (!resInit.success && !resInit.message?.includes('existiert bereits')) {
        setStatus({ text: `❌ Initialisierung fehlgeschlagen: ${resInit.message}`, type: 'error' });
        return;
      }
      setToast({ text: '✅ Datenbank initialisiert.', type: 'success' });
      testConnectionAndLoad();
    } catch (err) {
      setStatus({ text: `❌ Verbindungsfehler: ${err.message}`, type: 'error' });
    }
  };

  // ─── Render ───────────────────────────────────────────
  return (
    <div className="app-container">
      {/* ── Header ── */}
      <header className="app-header" id="app-header">
        <div className="header-content">
          <h1 className="header-title">🗄️ Datenbank</h1>
          <p className="header-subtitle">Alle erstellten Dokumente – in der World4You-Datenbank gespeichert</p>
        </div>
      </header>

      {/* ── Connection Bar ── */}
      <div className="status-bar" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div className={`status-dot ${status.type === 'error' ? 'error' : status.type === 'warning' ? 'error' : status.type === 'loading' ? 'loading' : 'success'}`}></div>
          <span className="status-text" style={{ color: status.type === 'error' || status.type === 'warning' ? '#C0392B' : status.type === 'success' ? '#1A7F3C' : '#64748B' }}>
            {status.text}
          </span>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-secondary btn-sm" onClick={() => loadInvoices()} disabled={loading}>
            ↻ Aktualisieren
          </button>
          <button className="btn btn-secondary btn-sm" onClick={() => testConnectionAndLoad()} disabled={loading}>
            🔌 Verbindung testen
          </button>
          <button className="btn btn-secondary btn-sm" onClick={() => setSettingsVisible(!settingsVisible)}>
            ⚙ API-Einstellungen
          </button>
        </div>
      </div>

      {/* ── Settings Panel ── */}
      {settingsVisible && (
        <div className="panel" style={{ marginBottom: 16 }}>
          <h2 className="panel-title">API-Einstellungen (World4You)</h2>

          <div style={{ backgroundColor: '#EFF6FF', border: '1px solid #BFDBFE', borderRadius: 8, padding: '10px 14px', marginBottom: 12, fontSize: 13, color: '#1E40AF' }}>
            ℹ️ <strong>API-URL</strong> und <strong>API-Key</strong> werden ausschließlich aus den serverseitigen
            Umgebungsvariablen <code>DB_API_URL</code> / <code>DB_API_KEY</code> gelesen (Vercel Environment
            Variables oder <code>.env.local</code>) — der Browser speichert oder verschickt keine Zugangsdaten mehr.
          </div>

          <p className="text-muted" style={{ fontSize: 13, marginBottom: 16 }}>
            Die PHP-Dateien müssen auf deinen World4You-Webspace hochgeladen werden. Beim ersten Einrichten
            (oder nach einem Schema-Update) einmalig initialisieren:
          </p>

          <button className="btn btn-primary" onClick={initDatabase}>
            🔧 Datenbank initialisieren
          </button>
        </div>
      )}

      {/* ── Search Bar ── */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 16, alignItems: 'center' }}>
        <input 
          className="form-input" 
          style={{ maxWidth: 300 }} 
          placeholder="Suche nach Nummer oder Kunde..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && loadInvoices()}
        />
        <select 
          className="form-input" 
          style={{ maxWidth: 200 }} 
          value={docFilter} 
          onChange={e => setDocFilter(e.target.value)}
        >
          {Object.entries(DOC_TYPES).map(([key, label]) => (
            <option key={key} value={key}>{label}</option>
          ))}
        </select>
        <button className="btn btn-primary" onClick={() => loadInvoices()}>
          🔍 Suchen
        </button>
        <span className="text-muted" style={{ marginLeft: 'auto', fontSize: 13 }}>
          {invoices.length} Dokument{invoices.length !== 1 ? 'e' : ''} gefunden
        </span>
      </div>

      {/* ── Data Table ── */}
      <div className="table-section" style={{ marginBottom: 0 }}>
        <div className="table-wrapper" style={{ maxHeight: '500px' }}>
          {invoices.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">🗄️</div>
              <p className="empty-state-text">
                {loading ? 'Lade Daten...' : 'Keine Dokumente im Archiv gefunden.'}
              </p>
            </div>
          ) : (
            <table className="data-table">
              <thead style={{ position: 'sticky', top: 0, backgroundColor: '#F8FAFC', zIndex: 1 }}>
                <tr>
                  <th>Rechnungs-Nr.</th>
                  <th>Datum</th>
                  <th>Typ</th>
                  <th>Kunde</th>
                  <th className="text-right">Netto €</th>
                  <th className="text-right">Brutto €</th>
                  <th className="text-center">Pos.</th>
                  <th>Dateiname</th>
                  <th className="text-center">Aktionen</th>
                </tr>
              </thead>
              <tbody>
                {invoices.map((inv, idx) => {
                  const docLabel = DOC_TYPE_LABELS[inv.document_type] || inv.document_type;
                  return (
                    <tr key={inv.id} className={idx % 2 === 0 ? 'even-row' : ''}>
                      <td>{inv.invoice_number}</td>
                      <td>{inv.invoice_date}</td>
                      <td>{docLabel}</td>
                      <td style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={inv.customer_name}>
                        {inv.customer_name}
                      </td>
                      <td className="text-right">{formatNumber(inv.total_netto)}</td>
                      <td className="text-right">{formatNumber(inv.total_brutto)}</td>
                      <td className="text-center">{inv.item_count}</td>
                      <td style={{ maxWidth: 150, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={inv.pdf_filename}>
                        {inv.pdf_filename}
                      </td>
                      <td className="text-center">
                        <div style={{ display: 'flex', gap: 6, justifyContent: 'center' }}>
                          <button 
                            className="btn btn-secondary btn-sm" 
                            style={{ padding: '4px 8px' }}
                            title="PDF Herunterladen"
                            onClick={() => downloadPdf(inv.id, inv.pdf_filename)}
                          >
                            📥
                          </button>
                          <button 
                            className="btn btn-icon btn-sm" 
                            style={{ color: '#C0392B', borderColor: '#FECACA', backgroundColor: '#FEE2E2' }}
                            title="Dokument löschen"
                            onClick={() => deleteInvoice(inv.id, inv.invoice_number, inv.customer_name)}
                          >
                            🗑
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* ── Toast ── */}
      {toast && (
        <div className={`toast ${toast.type === 'error' ? 'toast-error' : 'toast-success'}`}
          onClick={() => setToast(null)}>
          {toast.text}
        </div>
      )}
    </div>
  );
}

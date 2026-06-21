'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { saveInvoiceToDb } from '../utils/db';

// ─── Constants ───────────────────────────────────────────
const CONFIG_KEY = 'rechnungsbot_config';

const DEFAULT_CONFIG = {
  last_credit_note_number: '',
  default_credit_note_ust_enabled: true,
  default_credit_note_ust_percent: 20.0,
  default_credit_note_girocode_enabled: true,
  last_credit_note_recipient: { name: '', street: '', plz_city: '', country: '', phone: '', vat: '' },
  credit_note_customer_templates: {},
};

// ─── Helpers ─────────────────────────────────────────────
function loadConfig() {
  try {
    const stored = localStorage.getItem(CONFIG_KEY);
    if (stored) {
      return { ...DEFAULT_CONFIG, ...JSON.parse(stored) };
    }
  } catch { /* ignore */ }
  return { ...DEFAULT_CONFIG };
}

function saveConfig(cfg) {
  try {
    localStorage.setItem(CONFIG_KEY, JSON.stringify(cfg));
  } catch { /* ignore */ }
}

function formatCurrency(val) {
  return val.toLocaleString('de-AT', { style: 'currency', currency: 'EUR' });
}

function formatNumber(val) {
  return val.toLocaleString('de-AT', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function todayStr() {
  const d = new Date();
  return `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}.${d.getFullYear()}`;
}

// ─── Main Page Component ─────────────────────────────────
export default function CreditNotePage() {
  // --- State: Config / Settings ---
  const [config, setConfig] = useState(DEFAULT_CONFIG);
  const [invoiceNr, setInvoiceNr] = useState('');
  const [invoiceDate, setInvoiceDate] = useState(todayStr());
  const [ustEnabled, setUstEnabled] = useState(true);
  const [ustPercent, setUstPercent] = useState('20.0');
  const [girocodeEnabled, setGirocodeEnabled] = useState(true);

  // --- State: Customer ---
  const [custName, setCustName] = useState('');
  const [custStreet, setCustStreet] = useState('');
  const [custPlz, setCustPlz] = useState('');
  const [custCountry, setCustCountry] = useState('');
  const [custPhone, setCustPhone] = useState('');
  const [custVat, setCustVat] = useState('');
  const [selectedTemplate, setSelectedTemplate] = useState('');

  // --- State: Items ---
  const [items, setItems] = useState([]);
  
  // --- State: Item Input ---
  const [itemRef, setItemRef] = useState('');
  const [itemDescr, setItemDescr] = useState('');
  const [itemNetto, setItemNetto] = useState('');

  // --- State: UI ---
  const [status, setStatus] = useState({ text: '', type: 'idle' });
  const [generating, setGenerating] = useState(false);
  const [toast, setToast] = useState(null);
  const [editCell, setEditCell] = useState(null); // { rowIdx, field }
  const [editValue, setEditValue] = useState('');

  const editInputRef = useRef(null);

  // ─── Load config from localStorage on mount ───────────
  useEffect(() => {
    const fullCfg = loadConfig();
    const cfg = { ...DEFAULT_CONFIG, ...fullCfg };
    setConfig(fullCfg);
    setInvoiceNr(cfg.last_credit_note_number || '');
    setUstEnabled(cfg.default_credit_note_ust_enabled);
    setUstPercent(String(cfg.default_credit_note_ust_percent));
    setGirocodeEnabled(cfg.default_credit_note_girocode_enabled);
    
    const cust = cfg.last_credit_note_recipient || {};
    setCustName(cust.name || '');
    setCustStreet(cust.street || '');
    setCustPlz(cust.plz_city || '');
    setCustCountry(cust.country || '');
    setCustPhone(cust.phone || '');
    setCustVat(cust.vat || '');
  }, []);

  // ─── Focus edit input when cell editing starts ────────
  useEffect(() => {
    if (editCell && editInputRef.current) {
      editInputRef.current.focus();
      editInputRef.current.select();
    }
  }, [editCell]);

  // ─── Auto-hide toast ──────────────────────────────────
  useEffect(() => {
    if (toast) {
      const t = setTimeout(() => setToast(null), 4000);
      return () => clearTimeout(t);
    }
  }, [toast]);

  // ─── Computed totals ──────────────────────────────────
  const totalNetto = items.reduce((sum, it) => sum + it.net_amount, 0);
  const ustPct = ustEnabled ? (parseFloat(ustPercent.replace(',', '.')) || 0) : 0;
  const totalUst = totalNetto * ustPct / 100;
  const totalBrutto = totalNetto + totalUst;

  // ─── Save config to localStorage ──────────────────────
  const persistConfig = useCallback(() => {
    const newCfg = {
      ...config,
      last_credit_note_number: invoiceNr,
      default_credit_note_ust_enabled: ustEnabled,
      default_credit_note_ust_percent: parseFloat(ustPercent.replace(',', '.')) || 20,
      default_credit_note_girocode_enabled: girocodeEnabled,
      last_credit_note_recipient: {
        name: custName,
        street: custStreet,
        plz_city: custPlz,
        country: custCountry,
        phone: custPhone,
        vat: custVat,
      },
    };
    setConfig(newCfg);
    saveConfig(newCfg);
  }, [config, invoiceNr, ustEnabled, ustPercent, girocodeEnabled, custName, custStreet, custPlz, custCountry, custPhone, custVat]);

  // ─── Reset Session ────────────────────────────────────
  const resetSession = () => {
    setItems([]);
    setStatus({ text: '', type: 'idle' });
  };

  // ─── Add Item ─────────────────────────────────────────
  const addItem = () => {
    let ref = itemRef.trim();
    if (ref && !ref.toLowerCase().startsWith('rechnung')) {
      ref = `Rechnung ${ref}`;
    }
    const descr = itemDescr.trim();
    const nettoText = itemNetto.trim().replace(',', '.');
    
    const netto = parseFloat(nettoText);
    if (isNaN(netto) || netto <= 0) {
      setToast({ text: '⚠️ Bitte einen gültigen Netto-Betrag eingeben (>0).', type: 'error' });
      return;
    }

    setItems(prev => [...prev, { reference: ref, description: descr, net_amount: netto }]);
    setItemRef('');
    setItemDescr('');
    setItemNetto('');
  };

  // ─── Delete Item ──────────────────────────────────────
  const deleteItem = (idx) => {
    const item = items[idx];
    const label = item.description || item.reference || 'diese Position';
    if (confirm(`Soll die Position „${label}“ wirklich entfernt werden?`)) {
      setItems(prev => prev.filter((_, i) => i !== idx));
    }
  };

  // ─── Cell Editing ─────────────────────────────────────
  const EDITABLE_FIELDS = {
    reference: { key: 'reference', type: 'str' },
    description: { key: 'description', type: 'str' },
    netto: { key: 'net_amount', type: 'float' },
  };

  const startEdit = (rowIdx, field) => {
    const item = items[rowIdx];
    const { key, type } = EDITABLE_FIELDS[field];
    let val = item[key];
    if (type === 'float') val = formatNumber(val);
    else val = String(val);
    setEditCell({ rowIdx, field });
    setEditValue(val);
  };

  const commitEdit = () => {
    if (!editCell) return;
    const { rowIdx, field } = editCell;
    const { key, type } = EDITABLE_FIELDS[field];
    let raw = editValue.trim();

    setItems(prev => prev.map((it, i) => {
      if (i !== rowIdx) return it;
      const updated = { ...it };
      if (type === 'float') {
        const v = parseFloat(raw.replace(',', '.'));
        if (isNaN(v) || v <= 0) return it;
        updated[key] = v;
      } else {
        if (key === 'reference' && raw && !raw.toLowerCase().startsWith('rechnung')) {
          raw = `Rechnung ${raw}`;
        }
        updated[key] = raw;
      }
      return updated;
    }));
    setEditCell(null);
  };

  const cancelEdit = () => setEditCell(null);

  // ─── Template Management ──────────────────────────────
  const templates = config.credit_note_customer_templates || {};
  const templateNames = Object.keys(templates);

  const onTemplateSelect = (name) => {
    setSelectedTemplate(name);
    const tpl = templates[name] || {};
    setCustName(tpl.name || '');
    setCustStreet(tpl.street || '');
    setCustPlz(tpl.plz_city || '');
    setCustCountry(tpl.country || '');
    setCustPhone(tpl.phone || '');
    setCustVat(tpl.vat || '');
  };

  const saveTemplate = () => {
    const name = prompt('Name für diese Vorlage:', custName.trim());
    if (!name?.trim()) return;
    const newTemplates = {
      ...templates,
      [name.trim()]: { 
        name: custName, 
        street: custStreet, 
        plz_city: custPlz, 
        country: custCountry, 
        phone: custPhone,
        vat: custVat 
      },
    };
    const newCfg = { ...config, credit_note_customer_templates: newTemplates };
    setConfig(newCfg);
    saveConfig(newCfg);
    setSelectedTemplate(name.trim());
    setToast({ text: `💾 Vorlage '${name.trim()}' gespeichert`, type: 'success' });
  };

  const deleteTemplate = () => {
    if (!selectedTemplate) return;
    if (!confirm(`Vorlage '${selectedTemplate}' wirklich löschen?`)) return;
    const newTemplates = { ...templates };
    delete newTemplates[selectedTemplate];
    const newCfg = { ...config, credit_note_customer_templates: newTemplates };
    setConfig(newCfg);
    saveConfig(newCfg);
    setSelectedTemplate('');
    setToast({ text: `🗑 Vorlage gelöscht`, type: 'success' });
  };

  // ─── Generate Invoice ─────────────────────────────────
  const generateInvoice = async () => {
    if (!items.length) {
      setToast({ text: '⚠️ Bitte zuerst Positionen hinzufügen.', type: 'error' });
      return;
    }
    if (!invoiceNr.trim()) {
      setToast({ text: '⚠️ Bitte die Rechnungsnummer eingeben, zu der die Gutschrift gehört.', type: 'error' });
      return;
    }
    if (!invoiceDate.trim()) {
      setToast({ text: '⚠️ Bitte ein Datum eingeben.', type: 'error' });
      return;
    }
    if (!custName.trim()) {
      setToast({ text: '⚠️ Bitte den Firmennamen des Empfängers eingeben.', type: 'error' });
      return;
    }

    const invoiceData = {
      number: invoiceNr.trim(),
      date: invoiceDate.trim(),
      ust_enabled: ustEnabled,
      ust_percent: ustPct,
      girocode_enabled: girocodeEnabled,
    };

    const customerData = {
      name: custName.trim(),
      street: custStreet.trim(),
      plz_city: custPlz.trim(),
      country: custCountry.trim(),
      phone: custPhone.trim(),
      vat: custVat.trim(),
    };

    setGenerating(true);
    setStatus({ text: 'Gutschrift wird erstellt…', type: 'loading' });

    try {
      const resp = await fetch('/api/credit-note', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          items,
          invoice_data: invoiceData,
          customer_data: customerData,
        }),
      });

      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({ error: `HTTP ${resp.status}` }));
        const genErr = new Error(errData.error || `Fehler ${resp.status}`);
        genErr.detail = errData.detail;
        throw genErr;
      }

      const data = await resp.json();

      if (data.pdf) {
        const link = document.createElement('a');
        link.href = `data:application/pdf;base64,${data.pdf}`;
        link.download = data.filename || `Gutschrift_${invoiceNr.replace('/', '_')}.pdf`;
        link.click();
        
        // ── Background DB Upload ──
        saveInvoiceToDb({
          config,
          invoiceData,
          customerData,
          totals: { netto: totalNetto, brutto: totalBrutto },
          itemCount: items.length,
          docType: 'gutschrift',
          pdfBase64: data.pdf,
          pdfFilename: link.download
        });
      }

      setStatus({ text: `✅ Gutschrift erstellt!`, type: 'success' });
      setToast({ text: `✅ Gutschrift erstellt!`, type: 'success' });

      persistConfig();
    } catch (err) {
      setStatus({ text: `Fehler: ${err.message}`, type: 'error', detail: err.detail });
      setToast({ text: `❌ ${err.message}`, type: 'error' });
    } finally {
      setGenerating(false);
    }
  };

  // ─── Render ───────────────────────────────────────────
  return (
    <div className="app-container">
      {/* ── Header ── */}
      <header className="app-header" id="app-header">
        <div className="header-content">
          <h1 className="header-title">↩️ Gutschriften</h1>
          <p className="header-subtitle">Stornierungen und Gutschriften für Kunden erstellen</p>
        </div>
        <div className="header-actions">
          {items.length > 0 && (
            <button className="btn btn-secondary" onClick={resetSession}>
              ↺ Neue Gutschrift
            </button>
          )}
        </div>
      </header>

      {/* ── Settings + Customer Panels ── */}
      <div className="panels-row">
        {/* Settings Panel */}
        <div className="panel" id="panel-settings">
          <h2 className="panel-title">
            <span className="panel-title-icon">⚙️</span> Einstellungen
          </h2>

          <div className="form-group" style={{ gridTemplateColumns: '180px 1fr' }}>
            <label className="form-label" htmlFor="invoiceNr">Rechnung Nr. (Gutschrift zu):</label>
            <input id="invoiceNr" className="form-input" value={invoiceNr}
              onChange={e => setInvoiceNr(e.target.value)} />
          </div>

          <div className="form-group" style={{ gridTemplateColumns: '180px 1fr' }}>
            <label className="form-label" htmlFor="invoiceDate">Datum:</label>
            <input id="invoiceDate" className="form-input" value={invoiceDate}
              onChange={e => setInvoiceDate(e.target.value)} />
          </div>

          <div className="checkbox-group" style={{ marginTop: 12 }}>
            <label className="checkbox-label">
              <input type="checkbox" className="checkbox-input" checked={ustEnabled}
                onChange={e => setUstEnabled(e.target.checked)} id="chk-ust" />
              USt. berechnen
            </label>
            <div className="inline-field">
              <input className="form-input form-input-sm" value={ustPercent}
                onChange={e => setUstPercent(e.target.value)} disabled={!ustEnabled} id="ust-percent" />
              <span className="field-suffix">%</span>
            </div>
          </div>

          <div className="checkbox-group">
            <label className="checkbox-label">
              <input type="checkbox" className="checkbox-input" checked={girocodeEnabled}
                onChange={e => setGirocodeEnabled(e.target.checked)} id="chk-girocode" />
              QR-Code (GiroCode)
            </label>
          </div>
        </div>

        {/* Customer Panel */}
        <div className="panel" id="panel-customer">
          <h2 className="panel-title">
            <span className="panel-title-icon">👤</span> Empfänger
          </h2>

          <div className="template-row">
            <label>Vorlage:</label>
            <select className="template-select" value={selectedTemplate}
              onChange={e => onTemplateSelect(e.target.value)} id="template-select">
              <option value="">— Vorlage wählen —</option>
              {templateNames.map(n => <option key={n} value={n}>{n}</option>)}
            </select>
            <button className="btn btn-secondary btn-sm" onClick={saveTemplate} title="Speichern">💾</button>
            <button className="btn btn-icon btn-sm" onClick={deleteTemplate} title="Löschen">🗑</button>
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="custName">Firma:</label>
            <input id="custName" className="form-input" value={custName}
              onChange={e => setCustName(e.target.value)} />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="custStreet">Straße:</label>
            <input id="custStreet" className="form-input" value={custStreet}
              onChange={e => setCustStreet(e.target.value)} />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="custPlz">PLZ / Ort:</label>
            <input id="custPlz" className="form-input" value={custPlz}
              onChange={e => setCustPlz(e.target.value)} />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="custCountry">Land:</label>
            <input id="custCountry" className="form-input" value={custCountry}
              onChange={e => setCustCountry(e.target.value)} />
          </div>
          
          <div className="form-group">
            <label className="form-label" htmlFor="custPhone">Telefon:</label>
            <input id="custPhone" className="form-input" value={custPhone}
              onChange={e => setCustPhone(e.target.value)} />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="custVat">UID-Nr.:</label>
            <input id="custVat" className="form-input" value={custVat}
              onChange={e => setCustVat(e.target.value)} />
          </div>
        </div>
      </div>

      {/* ── Add Item & Positions Table ── */}
      <div className="panels-row">
        {/* Entry Box */}
        <div className="panel" style={{ height: 'fit-content' }}>
          <h2 className="panel-title">
            <span className="panel-title-icon">➕</span> Position hinzufügen
          </h2>

          <div className="form-group">
            <label className="form-label" htmlFor="itemRef">Referenz (Rechnungsnr.):</label>
            <input id="itemRef" className="form-input" value={itemRef}
              onChange={e => setItemRef(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && addItem()} />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="itemDescr">Beschreibung:</label>
            <input id="itemDescr" className="form-input" value={itemDescr}
              onChange={e => setItemDescr(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && addItem()} />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="itemNetto">Netto-Betrag (€):</label>
            <input id="itemNetto" className="form-input form-input-sm" value={itemNetto}
              onChange={e => setItemNetto(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && addItem()} />
          </div>

          <button className="btn btn-primary" onClick={addItem} style={{ width: '100%', marginTop: 12, justifyContent: 'center' }}>
            Position hinzufügen
          </button>
        </div>

        {/* Table Area */}
        <div className="table-section" style={{ marginBottom: 0 }}>
          <div className="table-toolbar">
            <span className="table-toolbar-hint">
              Klick auf Referenz, Beschreibung oder Netto, um die Position zu bearbeiten.
            </span>
          </div>

          <div className="table-wrapper" style={{ maxHeight: '350px' }}>
            {items.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-icon">📋</div>
                <p className="empty-state-text">Noch keine Positionen erfasst.</p>
              </div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th style={{ width: 140 }}>Referenz</th>
                    <th>Beschreibung</th>
                    <th className="text-right" style={{ width: 100 }}>Netto</th>
                    <th className="text-right" style={{ width: 100 }}>Brutto</th>
                    <th className="text-center" style={{ width: 44 }}></th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item, idx) => {
                    const isEditing = (field) => editCell?.rowIdx === idx && editCell?.field === field;
                    const netto = item.net_amount;
                    const brutto = netto * (1 + ustPct / 100);

                    return (
                      <tr key={idx}>
                        <td className="editable" onClick={() => startEdit(idx, 'reference')}>
                          {isEditing('reference') ? (
                            <input ref={editInputRef} className="cell-edit-input" value={editValue}
                              onChange={e => setEditValue(e.target.value)}
                              onBlur={commitEdit}
                              onKeyDown={e => { if (e.key === 'Enter') commitEdit(); if (e.key === 'Escape') cancelEdit(); }} />
                          ) : item.reference}
                        </td>
                        <td className="editable" onClick={() => startEdit(idx, 'description')}>
                          {isEditing('description') ? (
                            <input ref={editInputRef} className="cell-edit-input" value={editValue}
                              onChange={e => setEditValue(e.target.value)}
                              onBlur={commitEdit}
                              onKeyDown={e => { if (e.key === 'Enter') commitEdit(); if (e.key === 'Escape') cancelEdit(); }} />
                          ) : item.description}
                        </td>
                        <td className="text-right editable" onClick={() => startEdit(idx, 'netto')}>
                          {isEditing('netto') ? (
                            <input ref={editInputRef} className="cell-edit-input" value={editValue}
                              onChange={e => setEditValue(e.target.value)}
                              onBlur={commitEdit}
                              onKeyDown={e => { if (e.key === 'Enter') commitEdit(); if (e.key === 'Escape') cancelEdit(); }}
                              style={{ textAlign: 'right' }} />
                          ) : `€ ${formatNumber(netto)}`}
                        </td>
                        <td className="text-right">{`€ ${formatNumber(brutto)}`}</td>
                        <td className="text-center">
                          <button className="table-delete-btn" onClick={() => deleteItem(idx)} title="Position entfernen">🗑</button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>

          {items.length > 0 && (
            <div className="table-footer">
              <span className="text-muted">{items.length} Positionen</span>
              <div className="table-total">
                {ustEnabled ? (
                  <>
                    Netto: {formatCurrency(totalNetto)} &nbsp;·&nbsp;
                    USt. {ustPct}%: {formatCurrency(totalUst)} &nbsp;·&nbsp;
                    <strong>Brutto: {formatCurrency(totalBrutto)}</strong>
                  </>
                ) : (
                  <>Gesamtsumme Netto: {formatCurrency(totalNetto)}</>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Action Bar ── */}
      <div className="action-bar" style={{ marginTop: 24 }}>
        <button
          className="btn btn-primary btn-lg"
          onClick={generateInvoice}
          disabled={generating || !items.length}
        >
          {generating ? <span className="spinner"></span> : '🧾'} Gutschrift erstellen
        </button>
      </div>

      {/* ── Status Bar ── */}
      {status.text && (
        <div className="status-bar" style={{ marginTop: 24 }}>
          <div className={`status-dot ${status.type === 'error' ? 'error' : status.type === 'loading' ? 'loading' : 'success'}`}></div>
          <span className="status-text">{status.text}</span>
          {status.detail && (
            <span className="status-detail">Technisch: {status.detail}</span>
          )}
        </div>
      )}

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

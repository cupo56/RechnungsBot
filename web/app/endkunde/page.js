'use client';

import { useState, useCallback, useEffect } from 'react';
import { saveInvoiceToDb } from '../utils/db';
import { apiHeaders } from '../utils/apiAuth';
import { loadConfig as loadConfigBase, saveConfig } from '../utils/config';
import { todayStr } from '../utils/format';
import { useToast } from '../utils/useToast';
import { useCustomerTemplates } from '../utils/useCustomerTemplates';
import { useManualInvoiceItemsEditor } from '../utils/useManualInvoiceItemsEditor';
import Toast from '../components/Toast';
import TemplateSelector from '../components/TemplateSelector';
import StatusBar from '../components/StatusBar';
import ManualInvoiceItemsPanel from '../components/ManualInvoiceItemsPanel';

// ─── Constants ───────────────────────────────────────────
// last_invoice_number / last_invoice_year are intentionally the SAME config
// keys page.js uses (both read/write the shared 'rechnungsbot_config'
// localStorage object, see utils/config.js) — Endkunden-Rechnungen count in
// the same running invoice number sequence as normal invoices, not a
// separate counter like /provision's last_provision_number.
const DEFAULT_CONFIG = {
  last_invoice_number: 1,
  last_invoice_year: 2026,
  default_endkunde_ust_enabled: false,
  default_endkunde_ust_percent: 20.0,
  default_endkunde_girocode_enabled: true,
  default_endkunde_delivery_note: false,
  default_endkunde_weight: '',
  default_endkunde_delivery_note_text: '',
  last_endkunde_customer: { name: '', street: '', plz_city: '', country: '' },
  endkunde_customer_templates: {},
};

const loadConfig = () => loadConfigBase(DEFAULT_CONFIG);

// Endkunden-Rechnungen/-Lieferscheine sind Kaufland-Marktplatzverkäufe und
// bereits bezahlt — dieser Hinweis ersetzt (Rechnung) bzw. ergänzt
// (Lieferschein) den Standard-Fußtext, damit niemand fälschlich noch einmal
// überweist.
const KAUFLAND_PAYMENT_NOTE = 'Leistungsdatum ist gleich dem Rechnungsdatum.\nDer Rechnungsbetrag wurde bereits über Kaufland beglichen.\nBitte überweisen Sie keinen Betrag an das unten stehende Konto.';

// ─── Main Page Component ─────────────────────────────────
export default function EndkundePage() {
  // --- State: Config / Settings ---
  const [config, setConfig] = useState(DEFAULT_CONFIG);
  const [invoiceNr, setInvoiceNr] = useState('');
  const [invoiceDate, setInvoiceDate] = useState(todayStr());
  const [ustEnabled, setUstEnabled] = useState(false);
  const [ustPercent, setUstPercent] = useState('20.0');
  const [girocodeEnabled, setGirocodeEnabled] = useState(true);
  const [deliveryNote, setDeliveryNote] = useState(false);
  const [weight, setWeight] = useState('');
  const [deliveryNoteText, setDeliveryNoteText] = useState('');

  // --- State: Customer ---
  const [custName, setCustName] = useState('');
  const [custStreet, setCustStreet] = useState('');
  const [custPlz, setCustPlz] = useState('');
  const [custCountry, setCustCountry] = useState('');

  // --- State: Items ---
  const [items, setItems] = useState([]);

  // --- State: UI ---
  const [status, setStatus] = useState({ text: '', type: 'idle' });
  const [generating, setGenerating] = useState(false);
  const [toast, setToast] = useToast();

  // ─── Load config from localStorage on mount ───────────
  useEffect(() => {
    const fullCfg = loadConfig();
    const cfg = { ...DEFAULT_CONFIG, ...fullCfg };
    setConfig(fullCfg);
    setInvoiceNr(`${cfg.last_invoice_number}/${cfg.last_invoice_year}`);
    setUstEnabled(cfg.default_endkunde_ust_enabled);
    setUstPercent(String(cfg.default_endkunde_ust_percent));
    setGirocodeEnabled(cfg.default_endkunde_girocode_enabled);
    setDeliveryNote(cfg.default_endkunde_delivery_note);
    setWeight(cfg.default_endkunde_weight);
    setDeliveryNoteText(cfg.default_endkunde_delivery_note_text);

    const cust = cfg.last_endkunde_customer || {};
    setCustName(cust.name || '');
    setCustStreet(cust.street || '');
    setCustPlz(cust.plz_city || '');
    setCustCountry(cust.country || '');
  }, []);

  // ─── Computed totals ──────────────────────────────────
  const totalNetto = items.reduce((sum, it) => sum + it.quantity * it.unit_price, 0);
  const ustPct = ustEnabled ? (parseFloat(ustPercent.replace(',', '.')) || 0) : 0;
  const totalUst = totalNetto * ustPct / 100;
  const totalBrutto = totalNetto + totalUst;

  // ─── Save config to localStorage ──────────────────────
  const persistConfig = useCallback((incrementNr = false) => {
    let nr = 1, year = new Date().getFullYear();
    try {
      const parts = invoiceNr.split('/');
      nr = parseInt(parts[0]) || 1;
      year = parts[1] ? parseInt(parts[1]) : new Date().getFullYear();
    } catch { /* ignore */ }

    const newCfg = {
      ...config,
      last_invoice_number: incrementNr ? nr + 1 : nr,
      last_invoice_year: year,
      default_endkunde_ust_enabled: ustEnabled,
      default_endkunde_ust_percent: parseFloat(ustPercent.replace(',', '.')) || 20,
      default_endkunde_girocode_enabled: girocodeEnabled,
      default_endkunde_delivery_note: deliveryNote,
      default_endkunde_weight: weight,
      default_endkunde_delivery_note_text: deliveryNoteText,
      last_endkunde_customer: {
        name: custName,
        street: custStreet,
        plz_city: custPlz,
        country: custCountry,
      },
    };
    setConfig(newCfg);
    saveConfig(newCfg);
    if (incrementNr) {
      setInvoiceNr(`${nr + 1}/${year}`);
    }
  }, [config, invoiceNr, ustEnabled, ustPercent, girocodeEnabled, deliveryNote, weight, deliveryNoteText, custName, custStreet, custPlz, custCountry]);

  // ─── Reset Session ────────────────────────────────────
  const resetSession = () => {
    setItems([]);
    setStatus({ text: '', type: 'idle' });
  };

  // ─── Item Editing (entry box + inline cell editing) ───
  const itemsEditor = useManualInvoiceItemsEditor({ items, setItems, setToast });

  // ─── Template Management ──────────────────────────────
  const {
    templateNames, selectedTemplate, onTemplateSelect, saveTemplate, deleteTemplate,
  } = useCustomerTemplates({
    config,
    setConfig,
    templatesKey: 'endkunde_customer_templates',
    getFields: () => ({ name: custName, street: custStreet, plz_city: custPlz, country: custCountry }),
    applyTemplate: (tpl) => {
      setCustName(tpl.name || '');
      setCustStreet(tpl.street || '');
      setCustPlz(tpl.plz_city || '');
      setCustCountry(tpl.country || '');
    },
    setToast,
  });

  // ─── Generate Invoice / Delivery Note ──────────────────
  const generateInvoice = async (mode = 'invoice') => {
    if (!items.length) {
      setToast({ text: '⚠️ Bitte zuerst Positionen hinzufügen.', type: 'error' });
      return;
    }
    if (!invoiceNr.trim()) {
      setToast({ text: '⚠️ Bitte eine Rechnungsnummer eingeben.', type: 'error' });
      return;
    }
    if (!invoiceDate.trim()) {
      setToast({ text: '⚠️ Bitte ein Rechnungsdatum eingeben.', type: 'error' });
      return;
    }

    const invoiceItems = items.map(it => ({
      ean: it.ean, product: it.product, quantity: it.quantity, unit_price: it.unit_price,
    }));

    const invoiceData = {
      number: invoiceNr.trim(),
      date: invoiceDate.trim(),
      ust_enabled: ustEnabled,
      ust_percent: ustPct,
      girocode_enabled: girocodeEnabled,
      weight: weight.trim(),
      // Eigene Lieferschein-Notiz (falls ausgefüllt) bleibt erhalten, der
      // Kaufland-Hinweis wird immer angehängt.
      delivery_note_text: deliveryNoteText.trim()
        ? `${deliveryNoteText.trim()}\n${KAUFLAND_PAYMENT_NOTE}`
        : KAUFLAND_PAYMENT_NOTE,
      // invoice_note_text ersetzt in invoice.py den kompletten Fußtext-Block
      // (inkl. eu_text_enabled, das dadurch nicht mehr greift) — passend, da
      // der Standard-Fußtext (EU-Freistellung / Mahnspesen-Hinweis) für
      // bereits über Kaufland bezahlte Endkunden-Rechnungen nicht passt.
      invoice_note_text: KAUFLAND_PAYMENT_NOTE,
    };

    const customerData = {
      name: custName.trim(),
      street: custStreet.trim(),
      plz_city: custPlz.trim(),
      country: custCountry.trim(),
    };

    setGenerating(true);
    setStatus({ text: mode === 'delivery_only' ? 'Lieferschein wird erstellt…' : 'Rechnung wird erstellt…', type: 'loading' });

    try {
      const resp = await fetch('/api/generate', {
        method: 'POST',
        headers: apiHeaders(),
        body: JSON.stringify({
          mode,
          items: invoiceItems,
          invoice_data: invoiceData,
          customer_data: customerData,
          create_delivery_note: deliveryNote,
        }),
      });

      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({ error: `HTTP ${resp.status}` }));
        const genErr = new Error(errData.error || `Fehler ${resp.status}`);
        genErr.detail = errData.detail;
        throw genErr;
      }

      const data = await resp.json();

      if (data.invoice_pdf) {
        const link = document.createElement('a');
        link.href = `data:application/pdf;base64,${data.invoice_pdf}`;
        link.download = data.invoice_filename || `Rechnung_${invoiceNr.replace('/', '_')}.pdf`;
        link.click();
      }

      if (data.delivery_pdf) {
        const link = document.createElement('a');
        link.href = `data:application/pdf;base64,${data.delivery_pdf}`;
        link.download = data.delivery_filename || `Lieferschein_${invoiceNr.replace('/', '_')}.pdf`;
        setTimeout(() => link.click(), 500); // slight delay for double download
      }

      if (data.invoice_pdf && mode !== 'delivery_only') {
        saveInvoiceToDb({
          config,
          invoiceData,
          customerData,
          totals: { netto: totalNetto, brutto: totalBrutto },
          itemCount: invoiceItems.length,
          docType: 'rechnung',
          pdfBase64: data.invoice_pdf,
          pdfFilename: data.invoice_filename || `Rechnung_${invoiceNr.replace('/', '_')}.pdf`,
        });
      }
      if (data.delivery_pdf) {
        saveInvoiceToDb({
          config,
          invoiceData,
          customerData,
          totals: { netto: 0, brutto: 0 },
          itemCount: invoiceItems.length,
          docType: 'lieferschein',
          pdfBase64: data.delivery_pdf,
          pdfFilename: data.delivery_filename || `Lieferschein_${invoiceNr.replace('/', '_')}.pdf`,
        });
      }

      const msg = mode === 'delivery_only' ? 'Lieferschein erstellt!' : 'Rechnung erstellt!';
      setStatus({ text: `✅ ${msg}`, type: 'success' });
      setToast({ text: `✅ ${msg}`, type: 'success' });

      if (mode === 'invoice') {
        persistConfig(true);
      }
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
          <h1 className="header-title">🧍 Endkunden-Rechnung</h1>
          <p className="header-subtitle">Rechnungen für Endkunden (z.B. Kaufland-Marktplatz) manuell erfassen</p>
        </div>
        <div className="header-actions">
          {items.length > 0 && (
            <button className="btn btn-secondary" onClick={resetSession}>
              ↺ Neue Endkunden-Rechnung
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

          <div className="form-group">
            <label className="form-label" htmlFor="invoiceNr">Rechnungsnr.:</label>
            <input id="invoiceNr" className="form-input" value={invoiceNr}
              onChange={e => setInvoiceNr(e.target.value)} />
          </div>

          <div className="form-group">
            <label className="form-label" htmlFor="invoiceDate">Datum:</label>
            <input id="invoiceDate" className="form-input" value={invoiceDate}
              onChange={e => setInvoiceDate(e.target.value)} />
          </div>

          <div className="checkbox-group">
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
              <input type="checkbox" className="checkbox-input" checked={deliveryNote}
                onChange={e => setDeliveryNote(e.target.checked)} id="chk-delivery" />
              Lieferschein erstellen
            </label>
            <div className="inline-field">
              <input className="form-input form-input-sm" value={weight}
                onChange={e => setWeight(e.target.value)} disabled={!deliveryNote} id="weight" />
              <span className="field-suffix">kg</span>
            </div>
          </div>

          <div className="form-group full-width" style={{ marginTop: 6 }}>
            <label className="form-label">Lieferschein-Notiz:</label>
            <textarea className="form-textarea" value={deliveryNoteText}
              onChange={e => setDeliveryNoteText(e.target.value)} disabled={!deliveryNote}
              rows={2} id="delivery-note-text" />
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

          <TemplateSelector
            templateNames={templateNames}
            selectedTemplate={selectedTemplate}
            onSelect={onTemplateSelect}
            onSave={saveTemplate}
            onDelete={deleteTemplate}
          />

          <div className="form-group">
            <label className="form-label" htmlFor="custName">Name:</label>
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
        </div>
      </div>

      {/* ── Add Item & Positions Table ── */}
      <ManualInvoiceItemsPanel
        items={items}
        {...itemsEditor}
        ustEnabled={ustEnabled}
        ustPct={ustPct}
        totalNetto={totalNetto}
        totalUst={totalUst}
        totalBrutto={totalBrutto}
      />

      {/* ── Action Bar ── */}
      <div className="action-bar" style={{ marginTop: 24 }}>
        <button
          className="btn btn-primary btn-lg"
          onClick={() => generateInvoice('invoice')}
          disabled={generating || !items.length}
        >
          {generating ? <span className="spinner"></span> : '📄'} Rechnung erstellen
        </button>
        <button
          className="btn btn-secondary"
          onClick={() => generateInvoice('delivery_only')}
          disabled={generating || !items.length}
        >
          📦 Nur Lieferschein
        </button>
      </div>

      {/* ── Status Bar ── */}
      <StatusBar status={status} neutralDotClass="success" style={{ marginTop: 24 }} />

      {/* ── Toast ── */}
      <Toast toast={toast} onDismiss={() => setToast(null)} />
    </div>
  );
}

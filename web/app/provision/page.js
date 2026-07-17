'use client';

import { useState, useCallback, useEffect } from 'react';
import { loadConfig as loadConfigBase, saveConfig } from '../utils/config';
import { todayStr } from '../utils/format';
import { useToast } from '../utils/useToast';
import { useCustomerTemplates } from '../utils/useCustomerTemplates';
import { useSimpleItemsEditor } from '../utils/useSimpleItemsEditor';
import { submitDocument } from '../utils/submitDocument';
import Toast from '../components/Toast';
import TemplateSelector from '../components/TemplateSelector';
import StatusBar from '../components/StatusBar';
import SimpleItemsPanel from '../components/SimpleItemsPanel';

// ─── Constants ───────────────────────────────────────────
const DEFAULT_CONFIG = {
  last_provision_number: 1,
  last_provision_year: 2026,
  db_enabled: true,
  default_provision_ust_enabled: true,
  default_provision_ust_percent: 20.0,
  default_provision_girocode_enabled: true,
  last_provision_recipient: { name: '', street: '', plz_city: '', country: '', vat: '' },
  provision_customer_templates: {},
};

const loadConfig = () => loadConfigBase(DEFAULT_CONFIG);

// ─── Main Page Component ─────────────────────────────────
export default function ProvisionPage() {
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
  const [custVat, setCustVat] = useState('');

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
    setInvoiceNr(`${cfg.last_provision_number}/${cfg.last_provision_year}`);
    setUstEnabled(cfg.default_provision_ust_enabled);
    setUstPercent(String(cfg.default_provision_ust_percent));
    setGirocodeEnabled(cfg.default_provision_girocode_enabled);
    
    const cust = cfg.last_provision_recipient || {};
    setCustName(cust.name || '');
    setCustStreet(cust.street || '');
    setCustPlz(cust.plz_city || '');
    setCustCountry(cust.country || '');
    setCustVat(cust.vat || '');
  }, []);

  // ─── Computed totals ──────────────────────────────────
  const totalNetto = items.reduce((sum, it) => sum + it.net_amount, 0);
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
      last_provision_number: incrementNr ? nr + 1 : nr,
      last_provision_year: year,
      default_provision_ust_enabled: ustEnabled,
      default_provision_ust_percent: parseFloat(ustPercent.replace(',', '.')) || 20,
      default_provision_girocode_enabled: girocodeEnabled,
      last_provision_recipient: {
        name: custName,
        street: custStreet,
        plz_city: custPlz,
        country: custCountry,
        vat: custVat,
      },
    };
    setConfig(newCfg);
    saveConfig(newCfg);
    if (incrementNr) {
      setInvoiceNr(`${nr + 1}/${year}`);
    }
  }, [config, invoiceNr, ustEnabled, ustPercent, girocodeEnabled, custName, custStreet, custPlz, custCountry, custVat]);

  // ─── Reset Session ────────────────────────────────────
  const resetSession = () => {
    setItems([]);
    setStatus({ text: '', type: 'idle' });
  };

  // ─── Item Editing (entry box + inline cell editing) ───
  const itemsEditor = useSimpleItemsEditor({
    items,
    setItems,
    setToast,
    refKeyword: 'rechn',
    refPrefix: (raw) => `Rechn.Nr.${raw}`,
    getItemLabel: (item) => item?.description || '',
  });

  // ─── Template Management ──────────────────────────────
  const {
    templateNames, selectedTemplate, onTemplateSelect, saveTemplate, deleteTemplate,
  } = useCustomerTemplates({
    config,
    setConfig,
    templatesKey: 'provision_customer_templates',
    getFields: () => ({ name: custName, street: custStreet, plz_city: custPlz, country: custCountry, vat: custVat }),
    applyTemplate: (tpl) => {
      setCustName(tpl.name || '');
      setCustStreet(tpl.street || '');
      setCustPlz(tpl.plz_city || '');
      setCustCountry(tpl.country || '');
      setCustVat(tpl.vat || '');
    },
    setToast,
  });

  // ─── Generate Invoice ─────────────────────────────────
  const generateInvoice = async () => {
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
      vat: custVat.trim(),
    };

    setGenerating(true);
    setStatus({ text: 'Provisionsrechnung wird erstellt…', type: 'loading' });

    try {
      await submitDocument({
        endpoint: '/api/provision',
        items,
        invoiceData,
        customerData,
        docType: 'provision',
        defaultFilenamePrefix: 'Provisionsrechnung',
        invoiceNr,
        config,
        totals: { netto: totalNetto, brutto: totalBrutto },
      });

      setStatus({ text: `✅ Provisionsrechnung erstellt!`, type: 'success' });
      setToast({ text: `✅ Provisionsrechnung erstellt!`, type: 'success' });

      persistConfig(true);
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
          <h1 className="header-title">💰 Provisionsrechnung</h1>
          <p className="header-subtitle">Provisionsrechnungen für Vermittlungsgeschäfte manuell erfassen und generieren</p>
        </div>
        <div className="header-actions">
          {items.length > 0 && (
            <button className="btn btn-secondary" onClick={resetSession}>
              ↺ Neue Provisionsrechnung
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
            <label className="form-label" htmlFor="custVat">VAT-Nr.:</label>
            <input id="custVat" className="form-input" value={custVat}
              onChange={e => setCustVat(e.target.value)} />
          </div>
        </div>
      </div>

      {/* ── Add Item & Positions Table ── */}
      <SimpleItemsPanel
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
          onClick={generateInvoice}
          disabled={generating || !items.length}
        >
          {generating ? <span className="spinner"></span> : '📑'} Provisionsrechnung erstellen
        </button>
      </div>

      {/* ── Status Bar ── */}
      <StatusBar status={status} neutralDotClass="success" style={{ marginTop: 24 }} />

      {/* ── Toast ── */}
      <Toast toast={toast} onDismiss={() => setToast(null)} />
    </div>
  );
}

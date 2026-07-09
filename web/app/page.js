'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { saveInvoiceToDb } from './utils/db';
import { apiHeaders } from './utils/apiAuth';

// ─── Constants ───────────────────────────────────────────
const CONFIG_KEY = 'rechnungsbot_config';

const DEFAULT_CONFIG = {
  last_invoice_number: 1,
  last_invoice_year: 2026,
  default_markup: 0.0,
  default_ust_enabled: false,
  default_ust_percent: 20.0,
  default_create_delivery_note: false,
  default_is_export: false,
  default_girocode_enabled: true,
  default_eu_text_enabled: true,
  default_weight: '',
  default_delivery_note_text: '',
  default_invoice_note_text: '',
  last_customer: { name: '', street: '', plz_city: '', country: '', vat: '' },
  customer_templates: {},
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
export default function Home() {
  // --- State: Config / Settings ---
  const [config, setConfig] = useState(DEFAULT_CONFIG);
  const [invoiceNr, setInvoiceNr] = useState('');
  const [invoiceDate, setInvoiceDate] = useState(todayStr());
  const [markup, setMarkup] = useState('0.0');
  const [ustEnabled, setUstEnabled] = useState(false);
  const [ustPercent, setUstPercent] = useState('20.0');
  const [deliveryNote, setDeliveryNote] = useState(false);
  const [weight, setWeight] = useState('');
  const [deliveryNoteText, setDeliveryNoteText] = useState('');
  const [invoiceNoteText, setInvoiceNoteText] = useState('');
  const [isExport, setIsExport] = useState(false);
  const [girocodeEnabled, setGirocodeEnabled] = useState(true);
  const [euTextEnabled, setEuTextEnabled] = useState(true);

  // --- State: Customer ---
  const [custName, setCustName] = useState('');
  const [custStreet, setCustStreet] = useState('');
  const [custPlz, setCustPlz] = useState('');
  const [custCountry, setCustCountry] = useState('');
  const [custVat, setCustVat] = useState('');
  const [selectedTemplate, setSelectedTemplate] = useState('');

  // --- State: Items & File ---
  const [items, setItems] = useState([]);
  const [loadedFiles, setLoadedFiles] = useState([]); // [{ id, name, count, status: 'ok'|'error', error? }]
  const [dragOver, setDragOver] = useState(false);

  // --- State: UI ---
  const [status, setStatus] = useState({ text: 'Bereit — Excel- oder PDF-Datei(en) laden um zu beginnen.', type: 'idle' });
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [toast, setToast] = useState(null);
  const [editCell, setEditCell] = useState(null); // { rowIdx, field }
  const [editValue, setEditValue] = useState('');
  const [selectAllIndiv, setSelectAllIndiv] = useState(false);

  const fileInputRef = useRef(null);
  const editInputRef = useRef(null);

  // ─── Load config from localStorage on mount ───────────
  useEffect(() => {
    const cfg = loadConfig();
    setConfig(cfg);
    setInvoiceNr(`${cfg.last_invoice_number}/${cfg.last_invoice_year}`);
    setMarkup(String(cfg.default_markup));
    setUstEnabled(cfg.default_ust_enabled);
    setUstPercent(String(cfg.default_ust_percent));
    setDeliveryNote(cfg.default_create_delivery_note);
    setWeight(cfg.default_weight);
    setDeliveryNoteText(cfg.default_delivery_note_text);
    setInvoiceNoteText(cfg.default_invoice_note_text);
    setIsExport(cfg.default_is_export);
    setGirocodeEnabled(cfg.default_girocode_enabled);
    setEuTextEnabled(cfg.default_eu_text_enabled);
    const cust = cfg.last_customer || {};
    setCustName(cust.name || '');
    setCustStreet(cust.street || '');
    setCustPlz(cust.plz_city || '');
    setCustCountry(cust.country || '');
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

  // ─── Markup factor ────────────────────────────────────
  const getMarkupFactor = useCallback(() => {
    try {
      return 1 + parseFloat(markup.replace(',', '.')) / 100;
    } catch {
      return 1.0;
    }
  }, [markup]);

  // ─── Effective values for an item ─────────────────────
  const getEffective = useCallback((item, markupFactor) => {
    if (item.individual) {
      const ean = item.custom_ean ?? item.ean;
      const qty = item.custom_quantity ?? item.quantity;
      const product = item.custom_product ?? item.product;
      const unit = item.custom_unit_price ?? (item.source_price * markupFactor);
      return { ean, qty, product, unit };
    }
    return {
      ean: item.ean,
      qty: item.quantity,
      product: item.product,
      unit: item.source_price * markupFactor,
    };
  }, []);

  // ─── Computed totals ──────────────────────────────────
  const mf = getMarkupFactor();
  const totalNetto = items.reduce((sum, it) => {
    const { qty, unit } = getEffective(it, mf);
    return sum + qty * unit;
  }, 0);
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
      default_markup: parseFloat(markup.replace(',', '.')) || 0,
      default_ust_enabled: ustEnabled,
      default_ust_percent: parseFloat(ustPercent.replace(',', '.')) || 20,
      default_create_delivery_note: deliveryNote,
      default_is_export: isExport,
      default_girocode_enabled: girocodeEnabled,
      default_eu_text_enabled: euTextEnabled,
      default_weight: weight,
      default_delivery_note_text: deliveryNoteText,
      default_invoice_note_text: invoiceNoteText,
      last_customer: {
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
  }, [config, invoiceNr, markup, ustEnabled, ustPercent, deliveryNote, isExport, girocodeEnabled, euTextEnabled, weight, deliveryNoteText, invoiceNoteText, custName, custStreet, custPlz, custCountry, custVat]);

  // ─── File Upload / Parse ──────────────────────────────
  const parseOneFile = useCallback(async (file) => {
    // Files are sent as base64 inside a JSON body (not multipart/form-data):
    // Vercel's edge WAF blocks multipart uploads with a 403 for some PDFs
    // whose compressed binary stream happens to match an attack pattern
    // (see git history — this was already hit and fixed once before).
    // Base64 inflates the raw file size by ~33%, and Vercel's request body
    // limit is ~4.5 MB, so the raw file must stay well under that.
    const MAX_SIZE = 3.3 * 1024 * 1024; // ~3.3 MB raw → ~4.4 MB as base64+JSON
    if (file.size > MAX_SIZE) {
      throw new Error(`Datei ist zu groß (max. ${(MAX_SIZE / 1024 / 1024).toFixed(1)} MB). Aktuell: ${(file.size / 1024 / 1024).toFixed(2)} MB`);
    }

    const buffer = await file.arrayBuffer();
    const base64 = btoa(Array.from(new Uint8Array(buffer), b => String.fromCharCode(b)).join(''));

    const resp = await fetch('/api/parse', {
      method: 'POST',
      headers: apiHeaders(),
      body: JSON.stringify({ filename: file.name, file_base64: base64 }),
    });
    if (!resp.ok) {
      const errData = await resp.json().catch(() => ({ error: `HTTP ${resp.status}` }));
      const uploadErr = new Error(errData.error || `Fehler ${resp.status}`);
      uploadErr.detail = errData.detail;
      throw uploadErr;
    }
    const data = await resp.json();
    return {
      items: data.items || [],
      isOwnInvoice: data.invoice_type === 'own_invoice',
      invoiceData: data.invoice_data || null,
      customerData: data.customer_data || null,
    };
  }, []);

  const handleFilesUpload = useCallback(async (fileList) => {
    const files = Array.from(fileList || []);
    if (!files.length) return;

    const valid = [];
    for (const file of files) {
      const name = file.name.toLowerCase();
      if (name.endsWith('.xlsx') || name.endsWith('.xls') || name.endsWith('.pdf')) {
        valid.push(file);
      } else {
        setToast({ text: `❌ ${file.name}: nicht unterstütztes Format`, type: 'error' });
      }
    }
    if (!valid.length) return;

    setLoading(true);
    let okCount = 0;
    let errCount = 0;
    let addedItemCount = 0;
    let ownInvoiceNr = null;

    for (let i = 0; i < valid.length; i++) {
      const file = valid[i];
      setStatus({ text: `Datei ${i + 1} von ${valid.length} wird eingelesen… (${file.name})`, type: 'loading' });

      const fileId = crypto.randomUUID();
      try {
        const result = await parseOneFile(file);
        const tagged = result.items.map(it => {
          const base = { ...it, _fileId: fileId };
          if (result.isOwnInvoice) {
            // Preise aus importierter Rechnung fixieren (Aufschlag hat keinen Effekt)
            return {
              ...base,
              individual: true,
              custom_quantity: it.quantity,
              custom_ean: it.ean,
              custom_product: it.product,
              custom_unit_price: it.source_price,
            };
          }
          return base;
        });
        setItems(prev => [...prev, ...tagged]);
        setLoadedFiles(prev => [...prev, { id: fileId, name: file.name, count: tagged.length, status: 'ok', isOwnInvoice: result.isOwnInvoice }]);
        okCount += 1;
        addedItemCount += tagged.length;

        // Formularfelder aus importierter Rechnung befüllen
        if (result.isOwnInvoice && result.invoiceData) {
          const inv = result.invoiceData;
          const cust = result.customerData || {};
          if (inv.number) setInvoiceNr(inv.number);
          if (inv.date) setInvoiceDate(inv.date);
          setMarkup('0.0');
          setUstEnabled(inv.ust_enabled ?? false);
          setUstPercent(String(inv.ust_percent ?? 20.0));
          setIsExport(inv.is_export ?? false);
          setEuTextEnabled(inv.eu_text_enabled ?? true);
          setInvoiceNoteText(inv.invoice_note_text || '');
          if (cust.name) setCustName(cust.name);
          if (cust.street) setCustStreet(cust.street);
          if (cust.plz_city) setCustPlz(cust.plz_city);
          if (cust.country) setCustCountry(cust.country);
          if (cust.vat) setCustVat(cust.vat);
          ownInvoiceNr = inv.number || file.name;
        }
      } catch (err) {
        setLoadedFiles(prev => [...prev, { id: fileId, name: file.name, count: 0, status: 'error', error: err.message }]);
        errCount += 1;
      }
    }

    setLoading(false);
    if (errCount === 0) {
      if (ownInvoiceNr) {
        setStatus({ text: `Rechnung ${ownInvoiceNr} importiert — ${addedItemCount} Positionen geladen. Felder wurden automatisch befüllt.`, type: 'success' });
        setToast({ text: `📄 Rechnung ${ownInvoiceNr} importiert — Felder befüllt`, type: 'success' });
      } else {
        setStatus({ text: `${addedItemCount} Positionen aus ${okCount} Datei(en) geladen.`, type: 'success' });
        setToast({ text: `✅ ${okCount} Datei(en) geladen (${addedItemCount} Positionen)`, type: 'success' });
      }
    } else {
      const allFailed = okCount === 0;
      setStatus({ text: `${okCount} von ${valid.length} Dateien geladen — ${errCount} fehlgeschlagen.`, type: allFailed ? 'error' : 'success' });
      setToast({ text: `⚠️ ${okCount} von ${valid.length} Dateien geladen — ${errCount} fehlgeschlagen`, type: 'error' });
    }
  }, [parseOneFile]);

  // ─── Drag & Drop ──────────────────────────────────────
  const onDragOver = (e) => { e.preventDefault(); setDragOver(true); };
  const onDragLeave = () => setDragOver(false);
  const onDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer?.files?.length) handleFilesUpload(e.dataTransfer.files);
  };
  const onBrowse = () => fileInputRef.current?.click();
  const onFileChange = (e) => {
    if (e.target.files?.length) handleFilesUpload(e.target.files);
    e.target.value = '';
  };

  // ─── Reset Session ────────────────────────────────────
  const resetSession = () => {
    setItems([]);
    setLoadedFiles([]);
    setSelectAllIndiv(false);
    setStatus({ text: 'Bereit — Excel- oder PDF-Datei(en) laden um zu beginnen.', type: 'idle' });
  };

  // ─── Remove a loaded file (and its items) ─────────────
  const removeFile = (fileId) => {
    setLoadedFiles(prev => prev.filter(f => f.id !== fileId));
    setItems(prev => prev.filter(it => it._fileId !== fileId));
  };

  // ─── Individual Toggle ────────────────────────────────
  const toggleIndividual = (idx) => {
    setItems(prev => prev.map((it, i) => {
      if (i !== idx) return it;
      if (it.manual) return it;
      if (it.individual) {
        return { ...it, individual: false };
      }
      return {
        ...it,
        individual: true,
        custom_quantity: it.custom_quantity ?? it.quantity,
        custom_ean: it.custom_ean ?? it.ean,
        custom_product: it.custom_product ?? it.product,
        custom_unit_price: it.custom_unit_price ?? Math.round(it.source_price * mf * 100) / 100,
      };
    }));
  };

  // ─── Select All Individual ────────────────────────────
  const toggleSelectAllIndiv = () => {
    const enable = !selectAllIndiv;
    setSelectAllIndiv(enable);
    setItems(prev => prev.map(it => {
      if (it.manual) return it;
      if (enable) {
        return {
          ...it,
          individual: true,
          custom_quantity: it.custom_quantity ?? it.quantity,
          custom_ean: it.custom_ean ?? it.ean,
          custom_product: it.custom_product ?? it.product,
          custom_unit_price: it.custom_unit_price ?? Math.round(it.source_price * mf * 100) / 100,
        };
      }
      return { ...it, individual: false };
    }));
  };

  // ─── Delete Item ──────────────────────────────────────
  const deleteItem = (idx) => {
    const name = items[idx]?.custom_product || items[idx]?.product || '';
    if (confirm(`Soll die Position „${name}" wirklich entfernt werden?`)) {
      setItems(prev => prev.filter((_, i) => i !== idx));
    }
  };

  // ─── Add Manual Row ───────────────────────────────────
  const addManualRow = () => {
    setItems(prev => [...prev, {
      ean: '', product: 'Neue Position', quantity: 1, source_price: 0.0,
      individual: true, manual: true,
      custom_quantity: 1, custom_ean: '', custom_product: 'Neue Position', custom_unit_price: 0.0,
    }]);
  };

  // ─── Cell Editing ─────────────────────────────────────
  const EDITABLE_FIELDS = {
    qty: { key: 'custom_quantity', type: 'int' },
    ean: { key: 'custom_ean', type: 'str' },
    product: { key: 'custom_product', type: 'str' },
    unit: { key: 'custom_unit_price', type: 'float' },
  };

  const startEdit = (rowIdx, field) => {
    const item = items[rowIdx];
    if (!item.individual) return;
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
    const raw = editValue.trim();

    setItems(prev => prev.map((it, i) => {
      if (i !== rowIdx) return it;
      const updated = { ...it };
      if (type === 'int') {
        const v = parseInt(raw.replace(',', '.')) || 0;
        if (v <= 0) return it;
        updated[key] = v;
      } else if (type === 'float') {
        const v = parseFloat(raw.replace(',', '.'));
        if (isNaN(v) || v < 0) return it;
        updated[key] = v;
      } else {
        if (key === 'custom_product' && !raw) return it;
        updated[key] = raw;
      }
      return updated;
    }));
    setEditCell(null);
  };

  const cancelEdit = () => setEditCell(null);

  // ─── Template Management ──────────────────────────────
  const templates = config.customer_templates || {};
  const templateNames = Object.keys(templates);

  const onTemplateSelect = (name) => {
    setSelectedTemplate(name);
    const tpl = templates[name] || {};
    setCustName(tpl.name || '');
    setCustStreet(tpl.street || '');
    setCustPlz(tpl.plz_city || '');
    setCustCountry(tpl.country || '');
    setCustVat(tpl.vat || '');
  };

  const saveTemplate = () => {
    const name = prompt('Name für diese Vorlage:', custName.trim());
    if (!name?.trim()) return;
    const newTemplates = {
      ...templates,
      [name.trim()]: { name: custName, street: custStreet, plz_city: custPlz, country: custCountry, vat: custVat },
    };
    const newCfg = { ...config, customer_templates: newTemplates };
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
    const newCfg = { ...config, customer_templates: newTemplates };
    setConfig(newCfg);
    saveConfig(newCfg);
    setSelectedTemplate('');
    setToast({ text: `🗑 Vorlage gelöscht`, type: 'success' });
  };

  // ─── Generate Invoice ─────────────────────────────────
  const generateInvoice = async (mode = 'invoice') => {
    if (!items.length) {
      setToast({ text: '⚠️ Bitte zuerst eine Excel-Datei laden.', type: 'error' });
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
      setToast({ text: '⚠️ Bitte den Firmennamen des Kunden eingeben.', type: 'error' });
      return;
    }

    const invoiceItems = items.map(it => {
      const { ean, qty, product, unit } = getEffective(it, mf);
      return { ean, product, quantity: qty, unit_price: unit };
    });

    const invoiceData = {
      number: invoiceNr.trim(),
      date: invoiceDate.trim(),
      markup_factor: mf,
      ust_enabled: ustEnabled,
      ust_percent: ustPct,
      is_export: isExport,
      girocode_enabled: girocodeEnabled,
      eu_text_enabled: euTextEnabled,
      weight: weight.trim(),
      delivery_note_text: deliveryNoteText.trim(),
      invoice_note_text: invoiceNoteText.trim(),
    };

    const customerData = {
      name: custName.trim(),
      street: custStreet.trim(),
      plz_city: custPlz.trim(),
      country: custCountry.trim(),
      vat: custVat.trim(),
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

      // Download invoice PDF
      if (data.invoice_pdf) {
        const link = document.createElement('a');
        link.href = `data:application/pdf;base64,${data.invoice_pdf}`;
        link.download = data.invoice_filename || `Rechnung_${invoiceNr.replace('/', '_')}.pdf`;
        link.click();
      }

      // Download delivery note PDF
      if (data.delivery_pdf) {
        const link = document.createElement('a');
        link.href = `data:application/pdf;base64,${data.delivery_pdf}`;
        link.download = data.delivery_filename || `Lieferschein_${invoiceNr.replace('/', '_')}.pdf`;
        setTimeout(() => link.click(), 500); // slight delay for double download
      }

      // ── Background DB Upload ──
      if (data.invoice_pdf && mode !== 'delivery_only') {
        saveInvoiceToDb({
          config,
          invoiceData,
          customerData,
          totals: { netto: totalNetto, brutto: totalBrutto },
          itemCount: invoiceItems.length,
          docType: 'rechnung',
          pdfBase64: data.invoice_pdf,
          pdfFilename: data.invoice_filename || `Rechnung_${invoiceNr.replace('/', '_')}.pdf`
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
          pdfFilename: data.delivery_filename || `Lieferschein_${invoiceNr.replace('/', '_')}.pdf`
        });
      }

      const msg = mode === 'delivery_only' ? 'Lieferschein erstellt!' : 'Rechnung erstellt!';
      setStatus({ text: `✅ ${msg}`, type: 'success' });
      setToast({ text: `✅ ${msg}`, type: 'success' });

      // Increment invoice number if we created an invoice
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
          <h1 className="header-title">📄 RechnungsBot</h1>
          <p className="header-subtitle">Handelsagentur Adis Sefer — Rechnungen & Lieferscheine automatisch erstellen</p>
        </div>
        <div className="header-actions">
          {loadedFiles.length > 0 && (
            <button className="btn btn-secondary" onClick={resetSession} id="btn-reset">
              ↺ Alles zurücksetzen
            </button>
          )}
        </div>
      </header>

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
              ? `${loadedFiles.length} Datei(en) · ${items.length} Positionen geladen — weitere Dateien hier ablegen`
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
                {f.status === 'error' ? f.error : f.isOwnInvoice ? `📄 Importierte Rechnung · ${f.count} Positionen` : `${f.count} Positionen`}
              </span>
              <button className="loaded-file-remove" onClick={() => removeFile(f.id)} title="Datei entfernen">🗑</button>
            </div>
          ))}
        </div>
      )}

      {/* ── Settings + Customer Panels ── */}
      <div className="panels-row">
        {/* Settings Panel */}
        <div className="panel" id="panel-settings">
          <h2 className="panel-title">
            <span className="panel-title-icon">⚙️</span> Rechnungseinstellungen
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

          <div className="form-group">
            <label className="form-label" htmlFor="markup">Aufschlag %:</label>
            <input id="markup" className="form-input form-input-sm" value={markup}
              onChange={e => setMarkup(e.target.value)} />
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
              <input type="checkbox" className="checkbox-input" checked={isExport}
                onChange={e => setIsExport(e.target.checked)} id="chk-export" />
              Export-Rechnung
            </label>
          </div>

          <div className="checkbox-group">
            <label className="checkbox-label">
              <input type="checkbox" className="checkbox-input" checked={girocodeEnabled}
                onChange={e => setGirocodeEnabled(e.target.checked)} id="chk-girocode" />
              QR-Code
            </label>
          </div>

          <div className="checkbox-group">
            <label className="checkbox-label" title="Steuerfreie, innergemeinschaftliche Lieferung gem. Artikel 6 UStG.">
              <input type="checkbox" className="checkbox-input" checked={euTextEnabled}
                onChange={e => setEuTextEnabled(e.target.checked)} id="chk-eu-text" />
              EU-Lieferungshinweis
            </label>
          </div>

          <div className="form-group full-width" style={{ marginTop: 6 }}>
            <label className="form-label">Rechnungs-Notiz:</label>
            <textarea className="form-textarea" value={invoiceNoteText}
              onChange={e => setInvoiceNoteText(e.target.value)} rows={2} id="invoice-note-text" />
          </div>
        </div>

        {/* Customer Panel */}
        <div className="panel" id="panel-customer">
          <h2 className="panel-title">
            <span className="panel-title-icon">👤</span> Kundenadresse
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
            <label className="form-label" htmlFor="custVat">VAT-Nr.:</label>
            <input id="custVat" className="form-input" value={custVat}
              onChange={e => setCustVat(e.target.value)} />
          </div>
        </div>
      </div>

      {/* ── Positions Table ── */}
      <div className="table-section" id="table-section">
        <div className="table-toolbar">
          <div className="table-toolbar-left">
            <label className="checkbox-label">
              <input type="checkbox" className="checkbox-input" checked={selectAllIndiv}
                onChange={toggleSelectAllIndiv} id="chk-select-all-indiv" />
              Alle individuell bearbeiten
            </label>
            <span className="table-toolbar-hint">
              „Indiv.&quot; ankreuzen um Stk., EAN, Produktname und Einzelpreis manuell zu bearbeiten (Klick auf Zelle).
            </span>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={addManualRow} id="btn-add-row">
            ➕ Neue Zeile
          </button>
        </div>

        <div className="table-wrapper">
          {items.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">📋</div>
              <p className="empty-state-text">Noch keine Positionen geladen. Bitte oben eine Datei hochladen.</p>
            </div>
          ) : (
            <table className="data-table" id="data-table">
              <thead>
                <tr>
                  <th className="text-center" style={{ width: 55 }}>Stk.</th>
                  <th style={{ width: 130 }}>EAN</th>
                  <th>Produkt</th>
                  <th className="text-center" style={{ width: 60 }}>Indiv.</th>
                  <th className="text-right" style={{ width: 120 }}>Einzelpreis €</th>
                  <th className="text-right" style={{ width: 120 }}>Gesamtpreis €</th>
                  {ustEnabled && <th className="text-center" style={{ width: 60 }}>USt.</th>}
                  <th className="text-center" style={{ width: 44 }}></th>
                </tr>
              </thead>
              <tbody>
                {items.map((item, idx) => {
                  const { ean, qty, product, unit } = getEffective(item, mf);
                  const total = qty * unit;
                  const isEditing = (field) => editCell?.rowIdx === idx && editCell?.field === field;

                  return (
                    <tr key={idx}>
                      <td className={`text-center ${item.individual ? 'editable' : ''}`}
                        onClick={() => item.individual && startEdit(idx, 'qty')}>
                        {isEditing('qty') ? (
                          <input ref={editInputRef} className="cell-edit-input" value={editValue}
                            onChange={e => setEditValue(e.target.value)}
                            onBlur={commitEdit}
                            onKeyDown={e => { if (e.key === 'Enter') commitEdit(); if (e.key === 'Escape') cancelEdit(); }}
                            style={{ width: 45, textAlign: 'center' }} />
                        ) : qty}
                      </td>
                      <td className={item.individual ? 'editable' : ''}
                        onClick={() => item.individual && startEdit(idx, 'ean')}>
                        {isEditing('ean') ? (
                          <input ref={editInputRef} className="cell-edit-input" value={editValue}
                            onChange={e => setEditValue(e.target.value)}
                            onBlur={commitEdit}
                            onKeyDown={e => { if (e.key === 'Enter') commitEdit(); if (e.key === 'Escape') cancelEdit(); }} />
                        ) : ean}
                      </td>
                      <td className={item.individual ? 'editable' : ''}
                        onClick={() => item.individual && startEdit(idx, 'product')}>
                        {isEditing('product') ? (
                          <input ref={editInputRef} className="cell-edit-input" value={editValue}
                            onChange={e => setEditValue(e.target.value)}
                            onBlur={commitEdit}
                            onKeyDown={e => { if (e.key === 'Enter') commitEdit(); if (e.key === 'Escape') cancelEdit(); }} />
                        ) : product}
                      </td>
                      <td className="text-center">
                        <input type="checkbox" className="table-checkbox" checked={!!item.individual}
                          onChange={() => toggleIndividual(idx)} disabled={item.manual} />
                      </td>
                      <td className={`text-right ${item.individual ? 'editable' : ''}`}
                        onClick={() => item.individual && startEdit(idx, 'unit')}>
                        {isEditing('unit') ? (
                          <input ref={editInputRef} className="cell-edit-input" value={editValue}
                            onChange={e => setEditValue(e.target.value)}
                            onBlur={commitEdit}
                            onKeyDown={e => { if (e.key === 'Enter') commitEdit(); if (e.key === 'Escape') cancelEdit(); }}
                            style={{ textAlign: 'right' }} />
                        ) : `€ ${formatNumber(unit)}`}
                      </td>
                      <td className="text-right">{`€ ${formatNumber(total)}`}</td>
                      {ustEnabled && <td className="text-center">{ustPct}%</td>}
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

      {/* ── Action Bar ── */}
      <div className="action-bar" id="action-bar">
        <button
          className="btn btn-primary btn-lg"
          onClick={() => generateInvoice('invoice')}
          disabled={generating || !items.length}
          id="btn-create-invoice"
        >
          {generating ? <span className="spinner"></span> : '📄'} Rechnung erstellen
        </button>
        <button
          className="btn btn-secondary"
          onClick={() => generateInvoice('delivery_only')}
          disabled={generating || !items.length}
          id="btn-create-delivery"
        >
          📦 Nur Lieferschein
        </button>
      </div>

      {/* ── Status Bar ── */}
      <div className="status-bar" id="status-bar">
        <div className={`status-dot ${status.type === 'error' ? 'error' : status.type === 'loading' ? 'loading' : ''}`}></div>
        <span className="status-text">{status.text}</span>
        {status.detail && (
          <span className="status-detail">Technisch: {status.detail}</span>
        )}
        {loading && (
          <div className="progress-bar-container">
            <div className="progress-bar-fill"></div>
          </div>
        )}
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

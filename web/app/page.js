'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { saveInvoiceToDb } from './utils/db';
import { apiHeaders } from './utils/apiAuth';
import { loadConfig as loadConfigBase, saveConfig } from './utils/config';
import { formatNumber, todayStr } from './utils/format';
import { useToast } from './utils/useToast';
import { useCustomerTemplates } from './utils/useCustomerTemplates';
import Toast from './components/Toast';
import StatusBar from './components/StatusBar';
import DropZone from './components/DropZone';
import SettingsPanel from './components/SettingsPanel';
import CustomerPanel from './components/CustomerPanel';
import ItemsTable from './components/ItemsTable';

// ─── Constants ───────────────────────────────────────────
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

const loadConfig = () => loadConfigBase(DEFAULT_CONFIG);

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

  // --- State: Items & File ---
  const [items, setItems] = useState([]);
  const [loadedFiles, setLoadedFiles] = useState([]); // [{ id, name, count, status: 'ok'|'error', error? }]
  const [dragOver, setDragOver] = useState(false);

  // --- State: UI ---
  const [status, setStatus] = useState({ text: 'Bereit — Excel- oder PDF-Datei(en) laden um zu beginnen.', type: 'idle' });
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [toast, setToast] = useToast();
  const [editCell, setEditCell] = useState(null); // { rowIdx, field }
  const [editValue, setEditValue] = useState('');
  const [selectAllIndiv, setSelectAllIndiv] = useState(false);
  const [showOriginal, setShowOriginal] = useState(false);

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
      parseReport: data.parse_report || null,
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
        setLoadedFiles(prev => [...prev, {
          id: fileId,
          name: file.name,
          count: tagged.length,
          status: 'ok',
          isOwnInvoice: result.isOwnInvoice,
          format: result.parseReport?.format || null,
        }]);
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
  }, [parseOneFile, setToast]);

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
  const {
    templateNames, selectedTemplate, onTemplateSelect, saveTemplate, deleteTemplate,
  } = useCustomerTemplates({
    config,
    setConfig,
    templatesKey: 'customer_templates',
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
  // Plausibilität am aktuell gültigen Preis prüfen (inkl. manueller Korrektur
  // über "Individuell"), nicht am unveränderlichen geparsten source_price —
  // sonst bleibt eine Zeile für immer als "verdächtig" markiert, selbst
  // nachdem der Preis korrigiert wurde.
  const warningsCount = items.filter(it => !it.manual && (getEffective(it, mf).unit <= 0 || getEffective(it, mf).unit > 500)).length;

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

      <DropZone
        loading={loading}
        loadedFiles={loadedFiles}
        itemCount={items.length}
        dragOver={dragOver}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        onBrowse={onBrowse}
        onFileChange={onFileChange}
        fileInputRef={fileInputRef}
        removeFile={removeFile}
      />

      {/* ── Settings + Customer Panels ── */}
      <div className="panels-row">
        <SettingsPanel
          invoiceNr={invoiceNr} setInvoiceNr={setInvoiceNr}
          invoiceDate={invoiceDate} setInvoiceDate={setInvoiceDate}
          markup={markup} setMarkup={setMarkup}
          ustEnabled={ustEnabled} setUstEnabled={setUstEnabled}
          ustPercent={ustPercent} setUstPercent={setUstPercent}
          deliveryNote={deliveryNote} setDeliveryNote={setDeliveryNote}
          weight={weight} setWeight={setWeight}
          deliveryNoteText={deliveryNoteText} setDeliveryNoteText={setDeliveryNoteText}
          isExport={isExport} setIsExport={setIsExport}
          girocodeEnabled={girocodeEnabled} setGirocodeEnabled={setGirocodeEnabled}
          euTextEnabled={euTextEnabled} setEuTextEnabled={setEuTextEnabled}
          invoiceNoteText={invoiceNoteText} setInvoiceNoteText={setInvoiceNoteText}
        />

        <CustomerPanel
          templateNames={templateNames}
          selectedTemplate={selectedTemplate}
          onTemplateSelect={onTemplateSelect}
          saveTemplate={saveTemplate}
          deleteTemplate={deleteTemplate}
          custName={custName} setCustName={setCustName}
          custStreet={custStreet} setCustStreet={setCustStreet}
          custPlz={custPlz} setCustPlz={setCustPlz}
          custCountry={custCountry} setCustCountry={setCustCountry}
          custVat={custVat} setCustVat={setCustVat}
        />
      </div>

      {/* ── Positions Table ── */}
      <ItemsTable
        items={items} mf={mf} getEffective={getEffective}
        ustEnabled={ustEnabled} ustPct={ustPct}
        totalNetto={totalNetto} totalUst={totalUst} totalBrutto={totalBrutto}
        warningsCount={warningsCount}
        selectAllIndiv={selectAllIndiv} toggleSelectAllIndiv={toggleSelectAllIndiv}
        showOriginal={showOriginal} setShowOriginal={setShowOriginal}
        addManualRow={addManualRow}
        editCell={editCell} editValue={editValue} setEditValue={setEditValue} editInputRef={editInputRef}
        startEdit={startEdit} commitEdit={commitEdit} cancelEdit={cancelEdit}
        toggleIndividual={toggleIndividual} deleteItem={deleteItem}
      />

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
      <StatusBar status={status} loading={loading} showProgress alwaysVisible />

      {/* ── Toast ── */}
      <Toast toast={toast} onDismiss={() => setToast(null)} />
    </div>
  );
}

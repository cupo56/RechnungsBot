# Endkunden-Rechnung (Web-App) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new `/endkunde` page to the web app where the user manually enters line items (Stk./EAN/Produkt/Einzelpreis) and generates a normal-looking invoice/delivery note PDF for private end customers, without Excel import, VAT number, or company name — sharing the same invoice number counter as the main `/` invoice page.

**Architecture:** Pure frontend addition. One new hook (`useManualInvoiceItemsEditor`) manages the manual line-item state and inline cell editing (four fields: ean/product/quantity/unit_price), one new component (`ManualInvoiceItemsPanel`) renders the entry form + editable table, and one new page (`endkunde/page.js`) wires everything together and calls the **existing, unmodified** `/api/generate` and `/api/database` endpoints. A new nav entry links to the page.

**Tech Stack:** Next.js 16 App Router, React 19, plain CSS classes from `web/app/globals.css` (no new styles needed — reusing existing `panel`/`data-table`/`btn` classes), no test framework in this project (`npm run lint` / `npm run build` are the available automated checks).

**Reference spec:** `docs/superpowers/specs/2026-07-17-endkunden-rechnung-design.md`

---

## File Structure

- Create: `web/app/utils/useManualInvoiceItemsEditor.js` — manual item state (add/edit/delete), analogous to `web/app/utils/useSimpleItemsEditor.js` but with `ean`/`product`/`quantity`/`unit_price` fields instead of `reference`/`description`/`net_amount`.
- Create: `web/app/components/ManualInvoiceItemsPanel.js` — entry box + editable positions table, analogous to `web/app/components/SimpleItemsPanel.js` but with the normal-invoice column set (Stk./EAN/Produkt/Einzelpreis/Gesamtpreis).
- Create: `web/app/endkunde/page.js` — the page itself, modeled on `web/app/provision/page.js` (manual entry, own settings/customer panels) combined with `web/app/page.js`'s two-PDF `generateInvoice` logic (`mode: 'invoice' | 'delivery_only'`).
- Modify: `web/components/Navigation.js:9-15` — add the `/endkunde` nav link.

No backend files are touched. `/api/generate` (`web/api/index.py:134-177`) already defaults every field this page won't send (`markup_factor` unused by generators, `is_export` defaults `False`, `eu_text_enabled` defaults `True` but is only read when `is_export` is `True`).

---

### Task 1: Manual items editor hook

**Files:**
- Create: `web/app/utils/useManualInvoiceItemsEditor.js`

- [ ] **Step 1: Write the hook**

```js
'use client';

import { useState, useRef, useEffect } from 'react';
import { formatNumber } from './format';

// Manual line-item editor for the /endkunde page: unlike useSimpleItemsEditor
// (reference/description/netto, used by provision/credit-note), items here
// carry the same four fields as a normal invoice row (ean/product/quantity/
// unit_price) so the generated PDF looks like a regular Rechnung even though
// every position is typed in by hand. There is no imported-vs-individual
// distinction to track — every row is always editable.
const EDITABLE_FIELDS = {
  qty: { key: 'quantity', type: 'int' },
  ean: { key: 'ean', type: 'str' },
  product: { key: 'product', type: 'str' },
  unit: { key: 'unit_price', type: 'float' },
};

export function useManualInvoiceItemsEditor({ items, setItems, setToast }) {
  const [itemEan, setItemEan] = useState('');
  const [itemProduct, setItemProduct] = useState('');
  const [itemQty, setItemQty] = useState('');
  const [itemUnitPrice, setItemUnitPrice] = useState('');
  const [editCell, setEditCell] = useState(null); // { rowIdx, field }
  const [editValue, setEditValue] = useState('');
  const editInputRef = useRef(null);

  // ─── Focus edit input when cell editing starts ────────
  useEffect(() => {
    if (editCell && editInputRef.current) {
      editInputRef.current.focus();
      editInputRef.current.select();
    }
  }, [editCell]);

  const addItem = () => {
    const ean = itemEan.trim();
    const product = itemProduct.trim();
    if (!product) {
      setToast({ text: '⚠️ Bitte eine Produktbezeichnung eingeben.', type: 'error' });
      return;
    }

    const qtyText = itemQty.trim();
    const qty = qtyText ? parseInt(qtyText.replace(',', '.'), 10) : 1;
    if (isNaN(qty) || qty <= 0) {
      setToast({ text: '⚠️ Bitte eine gültige Stückzahl eingeben (>0).', type: 'error' });
      return;
    }

    const priceText = itemUnitPrice.trim().replace(',', '.');
    const unitPrice = parseFloat(priceText);
    if (priceText === '' || isNaN(unitPrice) || unitPrice < 0) {
      setToast({ text: '⚠️ Bitte einen gültigen Einzelpreis eingeben (>= 0).', type: 'error' });
      return;
    }

    setItems(prev => [...prev, { ean, product, quantity: qty, unit_price: unitPrice }]);
    setItemEan('');
    setItemProduct('');
    setItemQty('');
    setItemUnitPrice('');
  };

  const deleteItem = (idx) => {
    const label = items[idx]?.product || '';
    if (confirm(`Soll die Position „${label}“ wirklich entfernt werden?`)) {
      setItems(prev => prev.filter((_, i) => i !== idx));
    }
  };

  const startEdit = (rowIdx, field) => {
    const item = items[rowIdx];
    const { key, type } = EDITABLE_FIELDS[field];
    const val = type === 'float' ? formatNumber(item[key]) : String(item[key]);
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
        const v = parseInt(raw.replace(',', '.'), 10);
        if (isNaN(v) || v <= 0) return it;
        updated[key] = v;
      } else if (type === 'float') {
        const v = parseFloat(raw.replace(',', '.'));
        if (isNaN(v) || v < 0) return it;
        updated[key] = v;
      } else {
        if (key === 'product' && !raw) return it;
        updated[key] = raw;
      }
      return updated;
    }));
    setEditCell(null);
  };

  const cancelEdit = () => setEditCell(null);

  return {
    itemEan, setItemEan, itemProduct, setItemProduct, itemQty, setItemQty, itemUnitPrice, setItemUnitPrice,
    addItem, deleteItem,
    editCell, editValue, setEditValue, editInputRef,
    startEdit, commitEdit, cancelEdit,
  };
}
```

- [ ] **Step 2: Lint the new file**

Run (from `web/`): `npx eslint app/utils/useManualInvoiceItemsEditor.js`
Expected: no output (no errors/warnings).

- [ ] **Step 3: Commit**

```bash
git add web/app/utils/useManualInvoiceItemsEditor.js
git commit -m "feat: add manual invoice items editor hook for Endkunden page"
```

---

### Task 2: Manual items panel component

**Files:**
- Create: `web/app/components/ManualInvoiceItemsPanel.js`

- [ ] **Step 1: Write the component**

```js
'use client';

import { formatNumber, formatCurrency } from '../utils/format';

// "Add item + editable positions table" UI for /endkunde — same visual shape
// as the normal invoice's item table (Stk./EAN/Produkt/Einzelpreis/Gesamtpreis)
// but every row is entered and edited by hand, so unlike ItemsTable there is
// no "Individuell" toggle or "Originaldaten" comparison against imported data.
export default function ManualInvoiceItemsPanel({
  items,
  itemEan, setItemEan, itemProduct, setItemProduct, itemQty, setItemQty, itemUnitPrice, setItemUnitPrice, addItem,
  editCell, editValue, setEditValue, editInputRef, startEdit, commitEdit, cancelEdit, deleteItem,
  ustEnabled, ustPct, totalNetto, totalUst, totalBrutto,
}) {
  const isEditing = (idx, field) => editCell?.rowIdx === idx && editCell?.field === field;

  return (
    <div className="panels-row">
      {/* Entry Box */}
      <div className="panel" style={{ height: 'fit-content' }}>
        <h2 className="panel-title">
          <span className="panel-title-icon">➕</span> Position hinzufügen
        </h2>

        <div className="form-group">
          <label className="form-label" htmlFor="itemQty">Stk.:</label>
          <input id="itemQty" className="form-input form-input-sm" value={itemQty}
            onChange={e => setItemQty(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && addItem()} />
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="itemEan">EAN (optional):</label>
          <input id="itemEan" className="form-input" value={itemEan}
            onChange={e => setItemEan(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && addItem()} />
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="itemProduct">Produkt:</label>
          <input id="itemProduct" className="form-input" value={itemProduct}
            onChange={e => setItemProduct(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && addItem()} />
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="itemUnitPrice">Einzelpreis € (netto):</label>
          <input id="itemUnitPrice" className="form-input form-input-sm" value={itemUnitPrice}
            onChange={e => setItemUnitPrice(e.target.value)}
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
            Klick auf Stk., EAN, Produkt oder Einzelpreis, um die Position zu bearbeiten.
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
                  <th className="text-center" style={{ width: 55 }}>Stk.</th>
                  <th style={{ width: 130 }}>EAN</th>
                  <th>Produkt</th>
                  <th className="text-right" style={{ width: 110 }}>Einzelpreis €</th>
                  <th className="text-right" style={{ width: 110 }}>Gesamtpreis €</th>
                  {ustEnabled && <th className="text-center" style={{ width: 60 }}>USt.</th>}
                  <th className="text-center" style={{ width: 44 }}></th>
                </tr>
              </thead>
              <tbody>
                {items.map((item, idx) => {
                  const total = item.quantity * item.unit_price;

                  return (
                    <tr key={idx}>
                      <td className="text-center editable" onClick={() => startEdit(idx, 'qty')}>
                        {isEditing(idx, 'qty') ? (
                          <input ref={editInputRef} className="cell-edit-input" value={editValue}
                            onChange={e => setEditValue(e.target.value)}
                            onBlur={commitEdit}
                            onKeyDown={e => { if (e.key === 'Enter') commitEdit(); if (e.key === 'Escape') cancelEdit(); }}
                            style={{ width: 45, textAlign: 'center' }} />
                        ) : item.quantity}
                      </td>
                      <td className="editable" onClick={() => startEdit(idx, 'ean')}>
                        {isEditing(idx, 'ean') ? (
                          <input ref={editInputRef} className="cell-edit-input" value={editValue}
                            onChange={e => setEditValue(e.target.value)}
                            onBlur={commitEdit}
                            onKeyDown={e => { if (e.key === 'Enter') commitEdit(); if (e.key === 'Escape') cancelEdit(); }} />
                        ) : item.ean}
                      </td>
                      <td className="editable" onClick={() => startEdit(idx, 'product')}>
                        {isEditing(idx, 'product') ? (
                          <input ref={editInputRef} className="cell-edit-input" value={editValue}
                            onChange={e => setEditValue(e.target.value)}
                            onBlur={commitEdit}
                            onKeyDown={e => { if (e.key === 'Enter') commitEdit(); if (e.key === 'Escape') cancelEdit(); }} />
                        ) : item.product}
                      </td>
                      <td className="text-right editable" onClick={() => startEdit(idx, 'unit')}>
                        {isEditing(idx, 'unit') ? (
                          <input ref={editInputRef} className="cell-edit-input" value={editValue}
                            onChange={e => setEditValue(e.target.value)}
                            onBlur={commitEdit}
                            onKeyDown={e => { if (e.key === 'Enter') commitEdit(); if (e.key === 'Escape') cancelEdit(); }}
                            style={{ textAlign: 'right' }} />
                        ) : `€ ${formatNumber(item.unit_price)}`}
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
    </div>
  );
}
```

- [ ] **Step 2: Lint the new file**

Run (from `web/`): `npx eslint app/components/ManualInvoiceItemsPanel.js`
Expected: no output (no errors/warnings).

- [ ] **Step 3: Commit**

```bash
git add web/app/components/ManualInvoiceItemsPanel.js
git commit -m "feat: add ManualInvoiceItemsPanel component for Endkunden page"
```

---

### Task 3: The `/endkunde` page

**Files:**
- Create: `web/app/endkunde/page.js`

- [ ] **Step 1: Write the page**

```js
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
      delivery_note_text: deliveryNoteText.trim(),
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
```

- [ ] **Step 2: Lint the new file**

Run (from `web/`): `npx eslint app/endkunde/page.js`
Expected: no output (no errors/warnings).

- [ ] **Step 3: Commit**

```bash
git add web/app/endkunde/page.js
git commit -m "feat: add /endkunde page for manual end-customer invoices"
```

---

### Task 4: Navigation link

**Files:**
- Modify: `web/components/Navigation.js:9-15`

- [ ] **Step 1: Add the nav entry**

In `web/components/Navigation.js`, change:

```js
  const links = [
    { href: '/', label: '📄 Rechnung', desc: 'Rechnungen & Lieferscheine' },
    { href: '/compare', label: '🔍 Vergleich', desc: 'Excel-Listen abgleichen' },
    { href: '/provision', label: '💰 Provision', desc: 'Abrechnung erstellen' },
    { href: '/credit-note', label: '↩️ Gutschrift', desc: 'Stornos & Gutschriften' },
    { href: '/database', label: '🗄️ Datenbank', desc: 'Archiv & Suche' },
  ];
```

to:

```js
  const links = [
    { href: '/', label: '📄 Rechnung', desc: 'Rechnungen & Lieferscheine' },
    { href: '/compare', label: '🔍 Vergleich', desc: 'Excel-Listen abgleichen' },
    { href: '/provision', label: '💰 Provision', desc: 'Abrechnung erstellen' },
    { href: '/credit-note', label: '↩️ Gutschrift', desc: 'Stornos & Gutschriften' },
    { href: '/endkunde', label: '🧍 Endkunde', desc: 'Rechnung für Endkunden manuell erstellen' },
    { href: '/database', label: '🗄️ Datenbank', desc: 'Archiv & Suche' },
  ];
```

- [ ] **Step 2: Lint the modified file**

Run (from `web/`): `npx eslint components/Navigation.js`
Expected: no output (no errors/warnings).

- [ ] **Step 3: Commit**

```bash
git add web/components/Navigation.js
git commit -m "feat: add Endkunde nav link"
```

---

### Task 5: Full-project build check

**Files:** none (verification only)

- [ ] **Step 1: Run the production build**

Run (from `web/`): `npm run build`
Expected: build completes successfully, `/endkunde` listed among the generated routes, no type/JSX/import errors. (This is the strongest automated check available — the project has no test suite, and `next build` compiles and prerenders every page, catching broken imports, undefined components, and JSX mistakes across all four new/changed files at once.)

- [ ] **Step 2: Run the full-project lint**

Run (from `web/`): `npm run lint`
Expected: no errors (pre-existing warnings elsewhere in the repo, if any, are not this plan's concern — only confirm nothing new was introduced in the four changed files).

---

### Task 6: Manual browser verification (human)

**Files:** none — this task cannot be done by an agent without browser tooling; hand off to the user.

This project has no automated tests (see `CLAUDE.md`), and generating a real PDF requires the Python backend (`/api/generate`, `/api/database`) running alongside Next.js, which `npm run dev` alone does not provide — use `vercel dev` from `web/` (the Vercel CLI is already installed per this project's tooling) so the `api/index.py` Flask routes are served too. Then walk through the checklist from the spec (`docs/superpowers/specs/2026-07-17-endkunden-rechnung-design.md`, "Testing" section):

- [ ] Open `/endkunde`, add several positions (with EAN, without EAN, with comma- and dot-decimal prices) → table shows correct row totals and correct summed total.
- [ ] Click a table cell (Stk./EAN/Produkt/Einzelpreis) → becomes editable; Enter commits, Escape discards.
- [ ] Generate a Rechnung with all customer fields empty → PDF is still generated without error.
- [ ] Generate a Rechnung with only a name (no address) → PDF shows no blank address lines.
- [ ] Note the invoice number shown on `/`, create a Rechnung on `/endkunde`, then revisit `/` → the counter advanced on both pages in sync.
- [ ] Enable "Lieferschein erstellen", fill in kg + Notiz, click "Rechnung erstellen" → two PDFs download (invoice + delivery note).
- [ ] Click "Nur Lieferschein" → only one PDF downloads, and the invoice-number counter does **not** advance.
- [ ] Save a customer template, reload the page, select it → fields repopulate; confirm it does **not** appear in the customer-template dropdown on `/` (separate `endkunde_customer_templates` key).
- [ ] Check `/database` afterward → the created documents appear under the existing "Rechnung"/"Lieferschein" categories, not a new category.

---

## Self-Review Notes

- **Spec coverage:** shared invoice counter (Task 3, `DEFAULT_CONFIG`/`persistConfig`), reduced settings panel (Task 3 render), optional customer fields with no VAT (Task 3 render + validation), full Stk./EAN/Produkt/Einzelpreis/Gesamtpreis table with always-editable rows (Tasks 1–2), two-button invoice/delivery-note generation via unmodified `/api/generate` (Task 3 `generateInvoice`), nav entry (Task 4), archive categories unchanged (`docType: 'rechnung'/'lieferschein'` in Task 3) — all covered.
- **Type/name consistency checked:** hook return keys (`itemEan`, `setItemEan`, `itemProduct`, `setItemProduct`, `itemQty`, `setItemQty`, `itemUnitPrice`, `setItemUnitPrice`, `addItem`, `deleteItem`, `editCell`, `editValue`, `setEditValue`, `editInputRef`, `startEdit`, `commitEdit`, `cancelEdit`) match the props destructured in `ManualInvoiceItemsPanel` exactly, and match the `{...itemsEditor}` spread in `endkunde/page.js`. Item object shape `{ ean, product, quantity, unit_price }` is used consistently across the hook, the panel, and the `/api/generate` payload mapping.

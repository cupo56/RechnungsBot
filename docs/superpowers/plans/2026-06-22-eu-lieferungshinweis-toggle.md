# EU-Lieferungshinweis Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a checkbox to the web app's invoice page that lets the user turn the "Steuerfreie, innergemeinschaftliche Lieferung gem. Artikel 6 UStG." footer line on/off per invoice, defaulting to on (today's fixed behavior).

**Architecture:** One new boolean piece of state in `web/app/page.js`, persisted in the existing localStorage config blob and sent as one new key (`eu_text_enabled`) inside the existing `invoice_data` payload to `/api/generate`. `src/pdf/invoice.py`'s `_draw_footer` reads that key (default `True`) and conditionally skips drawing the line, collapsing the gap so the remaining two lines shift up.

**Tech Stack:** Next.js/React (frontend), Python/ReportLab (PDF backend), no test framework in this repo — verification is manual (CLAUDE.md confirms "There are no automated tests in this project").

Reference spec: `docs/superpowers/specs/2026-06-22-eu-lieferungshinweis-toggle-design.md`

---

### Task 1: Frontend state, config persistence, and payload

**Files:**
- Modify: `web/app/page.js:17` (DEFAULT_CONFIG)
- Modify: `web/app/page.js:69` (state hooks)
- Modify: `web/app/page.js:109` (mount effect)
- Modify: `web/app/page.js:188` (persistConfig)
- Modify: `web/app/page.js:205` (persistConfig dependency array)
- Modify: `web/app/page.js:442` (invoiceData payload)
- Modify: `web/app/page.js:656-662` (checkbox JSX)

- [ ] **Step 1: Add the config default**

In `web/app/page.js`, the `DEFAULT_CONFIG` object currently has:

```js
  default_is_export: false,
  default_girocode_enabled: true,
```

Change to:

```js
  default_is_export: false,
  default_girocode_enabled: true,
  default_eu_text_enabled: true,
```

- [ ] **Step 2: Add the React state hook**

Currently:

```js
  const [isExport, setIsExport] = useState(false);
  const [girocodeEnabled, setGirocodeEnabled] = useState(true);
```

Change to:

```js
  const [isExport, setIsExport] = useState(false);
  const [girocodeEnabled, setGirocodeEnabled] = useState(true);
  const [euTextEnabled, setEuTextEnabled] = useState(true);
```

- [ ] **Step 3: Load it from config on mount**

Currently:

```js
    setIsExport(cfg.default_is_export);
    setGirocodeEnabled(cfg.default_girocode_enabled);
```

Change to:

```js
    setIsExport(cfg.default_is_export);
    setGirocodeEnabled(cfg.default_girocode_enabled);
    setEuTextEnabled(cfg.default_eu_text_enabled);
```

- [ ] **Step 4: Persist it back to config**

Currently, inside `persistConfig`'s `newCfg` object:

```js
      default_is_export: isExport,
      default_girocode_enabled: girocodeEnabled,
```

Change to:

```js
      default_is_export: isExport,
      default_girocode_enabled: girocodeEnabled,
      default_eu_text_enabled: euTextEnabled,
```

And the `useCallback` dependency array right below currently ends with:

```js
  }, [config, invoiceNr, markup, ustEnabled, ustPercent, deliveryNote, isExport, girocodeEnabled, weight, deliveryNoteText, invoiceNoteText, custName, custStreet, custPlz, custCountry, custVat]);
```

Change to:

```js
  }, [config, invoiceNr, markup, ustEnabled, ustPercent, deliveryNote, isExport, girocodeEnabled, euTextEnabled, weight, deliveryNoteText, invoiceNoteText, custName, custStreet, custPlz, custCountry, custVat]);
```

- [ ] **Step 5: Send it in the invoice_data payload**

Currently:

```js
    const invoiceData = {
      number: invoiceNr.trim(),
      date: invoiceDate.trim(),
      markup_factor: mf,
      ust_enabled: ustEnabled,
      ust_percent: ustPct,
      is_export: isExport,
      girocode_enabled: girocodeEnabled,
      weight: weight.trim(),
      delivery_note_text: deliveryNoteText.trim(),
      invoice_note_text: invoiceNoteText.trim(),
    };
```

Change to:

```js
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
```

- [ ] **Step 6: Add the checkbox to the settings panel**

Currently:

```jsx
          <div className="checkbox-group">
            <label className="checkbox-label">
              <input type="checkbox" className="checkbox-input" checked={girocodeEnabled}
                onChange={e => setGirocodeEnabled(e.target.checked)} id="chk-girocode" />
              QR-Code
            </label>
          </div>

          <div className="form-group full-width" style={{ marginTop: 6 }}>
            <label className="form-label">Rechnungs-Notiz:</label>
```

Change to:

```jsx
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
```

- [ ] **Step 7: Commit**

```bash
git add web/app/page.js
git commit -m "feat: add EU-Lieferungshinweis toggle to invoice settings"
```

---

### Task 2: Backend footer logic

**Files:**
- Modify: `src/pdf/invoice.py:423-431` (`_draw_footer`)

- [ ] **Step 1: Make the Art.-6-UStG line conditional**

Currently:

```python
        elif self.inv.get("is_export", False):
            c.drawString(COL_EAN, y, FOOTER.get("delivery_terms", "Lieferbedinungen: EXW 1230 Wien, Mellergasse 4-02"))
            y -= 8 * mm
        else:
            c.drawString(COL_EAN, y, FOOTER.get("eu_text_1", "Steuerfreie, innergemeinschaftliche Lieferung gem. Artikel 6 UStG."))
            y -= 12 * mm
            c.drawString(COL_EAN, y, FOOTER.get("eu_text_2", "Leistungsdatum ist gleich dem Rechnungsdatum"))
            y -= 5 * mm
            c.drawString(COL_EAN, y, FOOTER.get("eu_text_3", "Beim Zahlungsverzug sind sämtliche Mahn.-und Inkassospesen zu ersetzen.Gerichtsstand ist Wien."))
            y -= 8 * mm
```

Change to:

```python
        elif self.inv.get("is_export", False):
            c.drawString(COL_EAN, y, FOOTER.get("delivery_terms", "Lieferbedinungen: EXW 1230 Wien, Mellergasse 4-02"))
            y -= 8 * mm
        else:
            if self.inv.get("eu_text_enabled", True):
                c.drawString(COL_EAN, y, FOOTER.get("eu_text_1", "Steuerfreie, innergemeinschaftliche Lieferung gem. Artikel 6 UStG."))
                y -= 12 * mm
            c.drawString(COL_EAN, y, FOOTER.get("eu_text_2", "Leistungsdatum ist gleich dem Rechnungsdatum"))
            y -= 5 * mm
            c.drawString(COL_EAN, y, FOOTER.get("eu_text_3", "Beim Zahlungsverzug sind sämtliche Mahn.-und Inkassospesen zu ersetzen.Gerichtsstand ist Wien."))
            y -= 8 * mm
```

- [ ] **Step 2: Commit**

```bash
git add src/pdf/invoice.py
git commit -m "feat: make Art.-6-UStG footer line conditional on eu_text_enabled"
```

---

### Task 3: Manual verification

There is no test suite in this project (per `CLAUDE.md`). Verify by running the web app locally and generating two invoices.

**Files:** none (verification only)

- [ ] **Step 1: Start the web app dev server**

```bash
cd web && npm run dev
```

Expected: server starts on `http://localhost:3000` (Next.js dev output, no errors).

- [ ] **Step 2: Generate an invoice with the checkbox checked (default)**

In the browser: load any Excel file, fill in invoice number/date/customer name, leave the new "EU-Lieferungshinweis" checkbox checked (default), click "Rechnung erstellen". Open the resulting PDF.

Expected: footer shows all three lines, starting with "Steuerfreie, innergemeinschaftliche Lieferung gem. Artikel 6 UStG." — identical to pre-change output.

- [ ] **Step 3: Generate an invoice with the checkbox unchecked**

Uncheck "EU-Lieferungshinweis", generate again (new invoice number).

Expected: footer shows only two lines ("Leistungsdatum ist gleich dem Rechnungsdatum" / "Beim Zahlungsverzug...") starting at the position the first line used to occupy — no leftover blank gap.

- [ ] **Step 4: Confirm export/custom-note invoices are unaffected**

Check "Export-Rechnung" (or fill in "Rechnungs-Notiz"), generate an invoice with the new checkbox in either state.

Expected: footer shows the export/custom text exactly as before — the new checkbox has no visible effect in these modes (matches spec).

- [ ] **Step 5: Confirm config persistence**

Refresh the page after generating at least one invoice with the checkbox unchecked.

Expected: the "EU-Lieferungshinweis" checkbox keeps the last-used state (loaded from `localStorage`'s `default_eu_text_enabled`).

---

## Done

After all three tasks are checked off, the feature is complete: the desktop app, provision page, and credit-note page are unaffected; the web app's main invoice flow has a working per-invoice toggle.

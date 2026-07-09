'use client';

export default function SettingsPanel({
  invoiceNr, setInvoiceNr,
  invoiceDate, setInvoiceDate,
  markup, setMarkup,
  ustEnabled, setUstEnabled,
  ustPercent, setUstPercent,
  deliveryNote, setDeliveryNote,
  weight, setWeight,
  deliveryNoteText, setDeliveryNoteText,
  isExport, setIsExport,
  girocodeEnabled, setGirocodeEnabled,
  euTextEnabled, setEuTextEnabled,
  invoiceNoteText, setInvoiceNoteText,
}) {
  return (
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
  );
}

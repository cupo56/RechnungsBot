'use client';

import TemplateSelector from './TemplateSelector';

export default function CustomerPanel({
  templateNames, selectedTemplate, onTemplateSelect, saveTemplate, deleteTemplate,
  custName, setCustName,
  custStreet, setCustStreet,
  custPlz, setCustPlz,
  custCountry, setCustCountry,
  custVat, setCustVat,
}) {
  return (
    <div className="panel" id="panel-customer">
      <h2 className="panel-title">
        <span className="panel-title-icon">👤</span> Kundenadresse
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
  );
}

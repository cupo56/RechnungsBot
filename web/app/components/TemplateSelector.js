'use client';

export default function TemplateSelector({ templateNames, selectedTemplate, onSelect, onSave, onDelete }) {
  return (
    <div className="template-row">
      <label>Vorlage:</label>
      <select className="template-select" value={selectedTemplate}
        onChange={e => onSelect(e.target.value)} id="template-select">
        <option value="">— Vorlage wählen —</option>
        {templateNames.map(n => <option key={n} value={n}>{n}</option>)}
      </select>
      <button className="btn btn-secondary btn-sm" onClick={onSave} title="Speichern">💾</button>
      <button className="btn btn-icon btn-sm" onClick={onDelete} title="Löschen">🗑</button>
    </div>
  );
}

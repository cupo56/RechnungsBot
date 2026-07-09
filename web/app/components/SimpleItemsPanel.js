'use client';

import { formatNumber, formatCurrency } from '../utils/format';

// Shared "add item + editable positions table" UI for provision/page.js and
// credit-note/page.js (byte-identical JSX in both before this extraction).
export default function SimpleItemsPanel({
  items,
  itemRef, setItemRef, itemDescr, setItemDescr, itemNetto, setItemNetto, addItem,
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
                  const netto = item.net_amount;
                  const brutto = netto * (1 + ustPct / 100);

                  return (
                    <tr key={idx}>
                      <td className="editable" onClick={() => startEdit(idx, 'reference')}>
                        {isEditing(idx, 'reference') ? (
                          <input ref={editInputRef} className="cell-edit-input" value={editValue}
                            onChange={e => setEditValue(e.target.value)}
                            onBlur={commitEdit}
                            onKeyDown={e => { if (e.key === 'Enter') commitEdit(); if (e.key === 'Escape') cancelEdit(); }} />
                        ) : item.reference}
                      </td>
                      <td className="editable" onClick={() => startEdit(idx, 'description')}>
                        {isEditing(idx, 'description') ? (
                          <input ref={editInputRef} className="cell-edit-input" value={editValue}
                            onChange={e => setEditValue(e.target.value)}
                            onBlur={commitEdit}
                            onKeyDown={e => { if (e.key === 'Enter') commitEdit(); if (e.key === 'Escape') cancelEdit(); }} />
                        ) : item.description}
                      </td>
                      <td className="text-right editable" onClick={() => startEdit(idx, 'netto')}>
                        {isEditing(idx, 'netto') ? (
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
  );
}

'use client';

import { formatCurrency, formatNumber } from '../utils/format';

export default function ItemsTable({
  items, mf, getEffective,
  ustEnabled, ustPct, totalNetto, totalUst, totalBrutto,
  warningsCount,
  selectAllIndiv, toggleSelectAllIndiv,
  showOriginal, setShowOriginal,
  addManualRow,
  editCell, editValue, setEditValue, editInputRef,
  startEdit, commitEdit, cancelEdit,
  toggleIndividual, deleteItem,
}) {
  return (
    <>
      {warningsCount > 0 && (
        <div className="toast-error" style={{ position: 'relative', marginBottom: '16px', borderRadius: '4px', padding: '12px' }}>
          ⚠️ {warningsCount} Position(en) haben einen verdächtigen Preis (0 € oder &gt; 500 €). Bitte prüfe diese Positionen manuell.
        </div>
      )}
      <div className="table-section" id="table-section">
        <div className="table-toolbar">
          <div className="table-toolbar-left" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
              <label className="checkbox-label">
                <input type="checkbox" className="checkbox-input" checked={selectAllIndiv}
                  onChange={toggleSelectAllIndiv} id="chk-select-all-indiv" />
                Alle individuell bearbeiten
              </label>
              <label className="checkbox-label" title="Originaldaten aus der eingelesenen Datei unter den bearbeiteten Werten einblenden">
                <input type="checkbox" className="checkbox-input" checked={showOriginal}
                  onChange={e => setShowOriginal(e.target.checked)} />
                Originaldaten einblenden
              </label>
            </div>
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
                  const isWarning = !item.manual && (unit <= 0 || unit > 500);

                  return (
                    <tr key={idx} className={isWarning ? 'row-warning' : ''}>
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
                        {showOriginal && !item.manual && product !== item.product && (
                          <span className="original-data" title={item.product}>Orig: {item.product}</span>
                        )}
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
                        ) : (
                          <>
                            € {formatNumber(unit)}
                            {isWarning && <span className="warning-icon" title="Verdächtiger Originalpreis">⚠️</span>}
                          </>
                        )}
                        {showOriginal && !item.manual && Math.round(unit * 100) !== Math.round(item.source_price * 100) && (
                          <span className="original-data" title="Preis aus der Quelldatei, vor Aufschlag">Orig (vor Aufschlag): € {formatNumber(item.source_price)}</span>
                        )}
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
    </>
  );
}

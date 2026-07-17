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

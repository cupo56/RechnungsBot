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

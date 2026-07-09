'use client';

import { useState, useRef, useEffect } from 'react';
import { formatNumber } from './format';

// Shared "manual line items with inline cell editing" logic, used by
// provision/page.js and credit-note/page.js (page.js has its own, unrelated
// editing model for imported Excel/PDF rows with individual-price overrides).
//
// refKeyword/refPrefix let each page keep its own reference-number
// convention (provision: "rechn" -> "Rechn.Nr.X", credit-note: "rechnung" ->
// "Rechnung X"). getItemLabel lets each page keep its own delete-confirmation
// fallback text.
const EDITABLE_FIELDS = {
  reference: { key: 'reference', type: 'str' },
  description: { key: 'description', type: 'str' },
  netto: { key: 'net_amount', type: 'float' },
};

export function useSimpleItemsEditor({ items, setItems, setToast, refKeyword, refPrefix, getItemLabel }) {
  const [itemRef, setItemRef] = useState('');
  const [itemDescr, setItemDescr] = useState('');
  const [itemNetto, setItemNetto] = useState('');
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

  const applyRefPrefix = (raw) => (raw && !raw.toLowerCase().startsWith(refKeyword) ? refPrefix(raw) : raw);

  const addItem = () => {
    const ref = applyRefPrefix(itemRef.trim());
    const descr = itemDescr.trim();
    const nettoText = itemNetto.trim().replace(',', '.');

    if (!descr) {
      setToast({ text: '⚠️ Bitte eine Beschreibung eingeben.', type: 'error' });
      return;
    }

    const netto = parseFloat(nettoText);
    if (isNaN(netto) || netto <= 0) {
      setToast({ text: '⚠️ Bitte einen gültigen Netto-Betrag eingeben (>0).', type: 'error' });
      return;
    }

    setItems(prev => [...prev, { reference: ref, description: descr, net_amount: netto }]);
    setItemRef('');
    setItemDescr('');
    setItemNetto('');
  };

  const deleteItem = (idx) => {
    const label = getItemLabel(items[idx]);
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
    let raw = editValue.trim();

    setItems(prev => prev.map((it, i) => {
      if (i !== rowIdx) return it;
      const updated = { ...it };
      if (type === 'float') {
        const v = parseFloat(raw.replace(',', '.'));
        if (isNaN(v) || v <= 0) return it;
        updated[key] = v;
      } else {
        if (key === 'description' && !raw) return it;
        if (key === 'reference') raw = applyRefPrefix(raw);
        updated[key] = raw;
      }
      return updated;
    }));
    setEditCell(null);
  };

  const cancelEdit = () => setEditCell(null);

  return {
    itemRef, setItemRef, itemDescr, setItemDescr, itemNetto, setItemNetto,
    addItem, deleteItem,
    editCell, editValue, setEditValue, editInputRef,
    startEdit, commitEdit, cancelEdit,
  };
}

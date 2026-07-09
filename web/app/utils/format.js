export function formatCurrency(val) {
  return val.toLocaleString('de-AT', { style: 'currency', currency: 'EUR' });
}

export function formatNumber(val) {
  return val.toLocaleString('de-AT', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function todayStr() {
  const d = new Date();
  return `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}.${d.getFullYear()}`;
}

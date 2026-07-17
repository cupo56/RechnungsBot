/**
 * Hilfsfunktionen für die Datenbank (World4You API)
 */

export async function saveInvoiceToDb({
  config,
  invoiceData,
  customerData,
  totals, // { netto, brutto }
  itemCount,
  docType, // 'rechnung', 'lieferschein', 'provision', 'gutschrift'
  isEndkunde = false, // zusätzliches Filter-Flag fürs Archiv, document_type bleibt unverändert
  pdfBase64,
  pdfFilename
}) {
  if (!config?.db_enabled) {
    return; // DB nicht konfiguriert
  }

  const payload = {
    action: 'save',

    invoice_number: invoiceData.number || '',
    invoice_date: invoiceData.date || '',
    document_type: docType,
    is_endkunde: isEndkunde ? 1 : 0,
    customer_name: customerData.name || '',
    customer_street: customerData.street || '',
    customer_plz: customerData.plz_city || '',
    customer_country: customerData.country || '',
    customer_vat: customerData.vat || '',
    
    total_netto: totals.netto || 0,
    total_brutto: totals.brutto || 0,
    ust_percent: invoiceData.ust_enabled ? (invoiceData.ust_percent || 0) : 0,
    item_count: itemCount || 0,
    is_export: invoiceData.is_export ? 1 : 0,
    
    pdf_filename: pdfFilename,
    pdf_data: pdfBase64,
  };

  try {
    const res = await fetch('/api/database', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    
    if (!res.ok) {
      console.error('DB Upload Failed: HTTP', res.status);
      return false;
    }
    
    const data = await res.json();
    if (!data.success) {
      console.error('DB Upload Failed:', data.message);
      return false;
    }
    
    return true;
  } catch (err) {
    console.error('DB Upload Exception:', err);
    return false;
  }
}

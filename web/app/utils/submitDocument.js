'use client';

import { apiHeaders } from './apiAuth';
import { saveInvoiceToDb } from './db';

// Shared fetch -> error-handling -> PDF-download -> DB-save skeleton, used by
// provision/page.js and credit-note/page.js. page.js has its own version
// (handles two PDFs, a "mode" param, and conditional persistConfig) and is
// left as-is rather than forced into this shape.
export async function submitDocument({ endpoint, items, invoiceData, customerData, docType, defaultFilenamePrefix, invoiceNr, config, totals }) {
  const resp = await fetch(endpoint, {
    method: 'POST',
    headers: apiHeaders(),
    body: JSON.stringify({ items, invoice_data: invoiceData, customer_data: customerData }),
  });

  if (!resp.ok) {
    const errData = await resp.json().catch(() => ({ error: `HTTP ${resp.status}` }));
    const err = new Error(errData.error || `Fehler ${resp.status}`);
    err.detail = errData.detail;
    throw err;
  }

  const data = await resp.json();

  if (data.pdf) {
    const link = document.createElement('a');
    link.href = `data:application/pdf;base64,${data.pdf}`;
    link.download = data.filename || `${defaultFilenamePrefix}_${invoiceNr.replace('/', '_')}.pdf`;
    link.click();

    saveInvoiceToDb({
      config,
      invoiceData,
      customerData,
      totals,
      itemCount: items.length,
      docType,
      pdfBase64: data.pdf,
      pdfFilename: link.download,
    });
  }

  return data;
}

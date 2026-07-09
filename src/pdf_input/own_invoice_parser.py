"""
own_invoice_parser – Erkennung und Parsing eigener Rechnungen (Stub).

Dieses Modul wird von web/api/index.py importiert, um hochgeladene PDFs
darauf zu prüfen, ob sie eine *eigene* Rechnung (im Gegensatz zu einer
Lieferantenrechnung) darstellen, und diese ggf. zu parsen.

Status: STUB – die eigentliche Logik muss noch implementiert werden.
         Bis dahin gibt is_own_invoice() immer False zurück, sodass der
         normale Lieferanten-Parser-Pfad genutzt wird.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def is_own_invoice(pdf_path: str) -> bool:
    """Prüft, ob das PDF eine eigene Rechnung ist.

    Returns
    -------
    bool
        ``True`` wenn das PDF als eigene Rechnung erkannt wurde,
        ``False`` sonst.

    .. note::
        Stub-Implementierung – gibt immer ``False`` zurück.
        Muss mit der tatsächlichen Erkennungslogik ersetzt werden.
    """
    logger.debug(
        "is_own_invoice aufgerufen für '%s' – Stub gibt False zurück", pdf_path
    )
    return False


def parse_own_invoice(pdf_path: str) -> dict[str, Any]:
    """Parst eine eigene Rechnung und gibt die extrahierten Daten zurück.

    Returns
    -------
    dict
        Erwartete Schlüssel:
        - ``items``: Liste von Dicts mit ean, product, quantity, source_price
        - ``invoice_data``: Dict mit Rechnungsmetadaten
        - ``customer_data``: Dict mit Kundendaten

    Raises
    ------
    NotImplementedError
        Solange die eigentliche Parsing-Logik noch nicht implementiert ist.
    """
    raise NotImplementedError(
        f"parse_own_invoice ist noch nicht implementiert. "
        f"PDF: {pdf_path}"
    )

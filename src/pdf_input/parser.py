"""
PDF-Parser für RechnungsBot.
Liest Lieferanten-PDFs (CIPO-Format) ein und extrahiert bestellte Positionen.
Gibt die gleiche Dict-Struktur wie parse_excel() zurück, ohne EAN.
"""

import re
import pdfplumber

_RE_WHITESPACE = re.compile(r'\s{2,}')

# Passt auf Zeilen im Format: "<Produktname-Teil> <Preis> <Menge> piece ..."
# Preis: Ganzzahl (70) oder europäisches Dezimal (115,00 / 94,50)
# Greedy (.*) findet den LÄNGSTEN gültigen Produktnamen-Teil
_RE_DATA_LINE = re.compile(
    r'^(.*)\s+(\d+(?:,\d{1,2})?)\s+(\d+)\s+piece\b',
    re.IGNORECASE,
)

# Keywords zur Erkennung der Produkt-Tabellen-Kopfzeile
_HEADER_KEYWORDS = ("unit price", "quantity", "mennyiség", "egységár")


def _is_product_table(table: list[list]) -> bool:
    """Prüft ob eine Tabelle die Produktliste enthält (anhand der Kopfzeile)."""
    if not table or not table[0]:
        return False
    header_text = " ".join(str(c).lower() for c in table[0] if c)
    hits = sum(1 for kw in _HEADER_KEYWORDS if kw in header_text)
    return hits >= 2  # mind. 2 Keywords → Produkttabelle


def _cell_float(value: str) -> float:
    """Wandelt europäische Zahlenformate (z.B. '115,00', '70') in float um."""
    text = str(value).strip()
    text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return 0.0


def _clean(text: str) -> str:
    return _RE_WHITESPACE.sub(" ", text.replace("\n", " ")).strip()


def _parse_data_cell(cell_text: str) -> list[dict]:
    """
    Parst den Inhalt der zusammengeführten Produkt-Datenzelle.

    Jede Zeile ist entweder:
      - Eine Produkt-Zeile:   "<Name-Teil> <Preis> <Menge> piece ..."
      - Eine Fortsetzungs-Zeile: "<Rest des Namens>"  (kein piece-Pattern)
    """
    items = []
    name_parts: list[str] = []
    price_str = "0"
    qty = 0

    def _flush():
        if qty <= 0:
            return
        full_name = _clean(" ".join(name_parts))
        if full_name:
            items.append({
                "ean":          "",
                "product":      full_name,
                "quantity":     qty,
                "source_price": _cell_float(price_str),
            })

    for raw_line in cell_text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue

        m = _RE_DATA_LINE.match(line)
        if m:
            _flush()
            name_parts = [m.group(1).strip()] if m.group(1).strip() else []
            price_str  = m.group(2)
            qty        = int(m.group(3))
        elif qty > 0:
            # Fortsetzungs-Zeile: Teil des Produktnamens der in nächste Zeile umbricht
            name_parts.append(line)

    _flush()
    return items


def parse_pdf(filepath: str) -> list[dict]:
    """
    Liest eine Lieferanten-PDF-Datei (CIPO-Format) und gibt bestellte Positionen zurück.

    Returns:
        list[dict]: Liste von Positionen mit Schlüsseln:
            - ean (str): Leer — PDFs enthalten keine EAN-Codes
            - product (str): Produktname (bereinigt)
            - quantity (int): Bestellmenge
            - source_price (float): Einkaufspreis aus der Quelldatei
    """
    items = []

    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if not _is_product_table(table):
                    continue
                # Datenzelle: alle Zeilen ab Index 1
                for row in table[1:]:
                    cell_text = " ".join(str(c) for c in row if c)
                    if cell_text.strip():
                        items.extend(_parse_data_cell(cell_text))

    if not items:
        raise ValueError(
            "Keine Positionen gefunden.\n"
            "Das PDF muss eine Tabelle mit 'Unit Price' und 'Quantity' enthalten."
        )

    items.sort(key=lambda x: x["product"].lower())
    return items

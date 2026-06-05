"""
PDF-Parser für RechnungsBot.
Liest Lieferanten-PDFs ein und extrahiert bestellte Positionen.
Unterstützt CIPO-Format (Daten in Tabellenzellen) und MATIVA-Format (Daten im Fließtext).
Gibt die gleiche Dict-Struktur wie parse_excel() zurück.
"""

import re
import pdfplumber

_RE_WHITESPACE = re.compile(r'\s{2,}')

# CIPO-Format: "<Produktname-Teil> <Preis> <Menge> piece ..."
_RE_DATA_LINE = re.compile(
    r'^(.*)\s+(\d+(?:,\d{1,2})?)\s+(\d+)\s+piece\b',
    re.IGNORECASE,
)

# MATIVA-Format Zeile 1: "1. GU32016 GUESS SEDUCTIVE FOR WOMEN 360,00 PCS 4,11 0,00 0,00 4,11"
_RE_MATIVA_LINE1 = re.compile(
    r'^\d+\.\s+\S+\s+(.+?)\s+(\d+),00\s+PCS\s+([\d,]+)\s+0,00\s+0,00\s+[\d,]+\s*$',
    re.IGNORECASE,
)

# MATIVA-Format Zeile 2: "085715320162 FRAG MIST 250ML IP 1.479,60 0,00 0,00 1.479,60"
_RE_MATIVA_LINE2 = re.compile(
    r'^(\d{12,14})\s+(.+?)\s+[\d.]+,\d{2}\s+0,00\s+0,00\s+[\d.]+,\d{2}\s*$'
)

# MATIVA-Format CT-Zeile: "CT: 33079000" (Zolltarifnummer, wird übersprungen)
_RE_CT_LINE = re.compile(r'^CT:\s*\d+\s*$')

# Keywords zur Erkennung der Produkt-Tabellen-Kopfzeile (CIPO)
_HEADER_KEYWORDS = ("unit price", "quantity", "mennyiség", "egységár")


def _is_product_table(table: list[list]) -> bool:
    if not table or not table[0]:
        return False
    header_text = " ".join(str(c).lower() for c in table[0] if c)
    hits = sum(1 for kw in _HEADER_KEYWORDS if kw in header_text)
    return hits >= 2


def _cell_float(value: str) -> float:
    text = str(value).strip().replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return 0.0


def _clean(text: str) -> str:
    return _RE_WHITESPACE.sub(" ", text.replace("\n", " ")).strip()


def _parse_data_cell(cell_text: str) -> list[dict]:
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
            name_parts.append(line)

    _flush()
    return items


def _parse_cipo(filepath: str) -> list[dict]:
    """CIPO-Format: Produktdaten befinden sich in Tabellenzellen."""
    items = []
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                if not _is_product_table(table):
                    continue
                for row in table[1:]:
                    cell_text = " ".join(str(c) for c in row if c)
                    if cell_text.strip():
                        items.extend(_parse_data_cell(cell_text))
    return items


def _parse_mativa(filepath: str) -> list[dict]:
    """MATIVA-Format: Produktdaten befinden sich im Fließtext, nicht in Tabellenzellen."""
    all_lines: list[str] = []
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                all_lines.extend(text.split("\n"))

    items = []
    i = 0
    while i < len(all_lines):
        m1 = _RE_MATIVA_LINE1.match(all_lines[i].strip())
        if not m1:
            i += 1
            continue

        desc_part1 = m1.group(1).strip()
        qty        = int(m1.group(2))
        unit_price = _cell_float(m1.group(3))
        i += 1

        ean = ""
        desc_part2 = ""
        if i < len(all_lines):
            m2 = _RE_MATIVA_LINE2.match(all_lines[i].strip())
            if m2:
                ean        = m2.group(1)
                desc_part2 = m2.group(2).strip()
                i += 1
                if i < len(all_lines) and _RE_CT_LINE.match(all_lines[i].strip()):
                    i += 1

        product = _clean(f"{desc_part1} {desc_part2}" if desc_part2 else desc_part1)
        items.append({
            "ean":          ean,
            "product":      product,
            "quantity":     qty,
            "source_price": unit_price,
        })

    return items


def parse_pdf(filepath: str) -> list[dict]:
    """
    Liest eine Lieferanten-PDF-Datei und gibt bestellte Positionen zurück.
    Versucht zuerst das CIPO-Format (Tabellenzellen), dann das MATIVA-Format (Fließtext).

    Returns:
        list[dict]: Liste von Positionen mit Schlüsseln:
            - ean (str): EAN-Code (leer wenn nicht vorhanden)
            - product (str): Produktname (bereinigt)
            - quantity (int): Bestellmenge
            - source_price (float): Einkaufspreis aus der Quelldatei
    """
    items = _parse_cipo(filepath)

    if not items:
        items = _parse_mativa(filepath)

    if not items:
        raise ValueError(
            "Keine Positionen gefunden.\n"
            "Das PDF muss eine Tabelle mit 'Unit Price' und 'Quantity' enthalten."
        )

    items.sort(key=lambda x: x["product"].lower())
    return items

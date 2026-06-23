"""
PDF-Parser für RechnungsBot.
Liest Lieferanten-PDFs ein und extrahiert bestellte Positionen.
Unterstützt CIPO-Format, ALINA-Rechnungsformat und ALINA-Bestellformat
(jeweils Daten in Tabellenzellen) sowie MATIVA-Format, FCT-Format,
PWV-Format und ZNZ-Format (jeweils Daten im Fließtext).
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

# FCT-Format ("Purchase Order Confirmation" von F.C.T. B.V.) Artikelzeile:
# "DKNY 24/7 Edp Spray 50 ml UG 48 12,80 614,40"
# Gruppen: Beschreibung, Menge, Einzelpreis (Gesamtpreis wird verworfen)
_RE_FCT_LINE = re.compile(
    r'^(.+?)\s+(?:[a-zA-Z]{1,8}\s+)?(\d+(?:[,.]\d+)?)\s+(?:€\s*)?([\d.,]+)\s+(?:€\s*)?[\d.,]+.*$'
)

# FCT-Format EAN-Zeile (eigene Zeile nach der Artikelzeile, ggf. nach Umbruchzeilen)
_RE_FCT_EAN = re.compile(r'^\d{8,14}$')

# PWV-Format (Parfumeriewarenvertriebs GmbH) Artikelzeile:
# "1 056L2850301 La Vie est Belle EdP Vapo 30ml 7 STK 32,07 224,49"
# Gruppen: Beschreibung, Menge, Einzelpreis (Gesamtpreis wird verworfen)
_RE_PWV_LINE = re.compile(
    r'^\d+\s+\S+\s+(.+?)\s+(\d+)\s+STK\s+([\d.,]+)\s+[\d.,]+\s*$'
)

# PWV-Format EAN-Zeile (eigene Zeile nach der Artikelzeile, ggf. nach Umbruchzeilen)
_RE_PWV_EAN = re.compile(r'^EAN\s+(\d{12,14})\s*$')

# ZNZ-Format (ZNZ ELECTRONICS, s.r.o.) Artikelzeile:
# "1 100130496 Armaf Club de Nuit Intense Man Perfumed Deostick 75 g (man)"
# Gruppen: Artikelnummer (verworfen), Beschreibung
_RE_ZNZ_ITEM = re.compile(r'^\d+\s+\S+\s+(.+)$')

# ZNZ-Format Datenzeile (eigene Zeile nach der Artikelzeile, ggf. nach Umbruchzeilen):
# "4,00 ks 7,33 29,32 0 33072000 0 29,32"
# Beträge ab 1.000 werden mit Leerzeichen als Tausendertrennzeichen notiert,
# z.B. "48,00 ks 25,80 1 238,40 0 33030090 0 1 238,40".
# Gruppen: Menge, Einzelpreis, Zolltarifnummer (8-stellig, optional)
# Dienstleistungspositionen (z.B. "Transport") haben keine Zolltarifnummer
# und werden anhand der fehlenden Gruppe 3 übersprungen.
_ZNZ_AMOUNT = r'\d{1,3}(?:[ .]\d{3})*,\d{2}'
_RE_ZNZ_DATA = re.compile(
    r'^(\d+),\d{2}\s+ks\s+(' + _ZNZ_AMOUNT + r')\s+' + _ZNZ_AMOUNT
    + r'\s+\d+\s+(?:(\d{8})\s+)?\d+\s+' + _ZNZ_AMOUNT + r'\s*$',
    re.IGNORECASE,
)

# Keywords zur Erkennung der Produkt-Tabellen-Kopfzeile (CIPO)
_HEADER_KEYWORDS = ("unit price", "quantity", "mennyiség", "egységár")


def _is_product_table(table: list[list]) -> bool:
    if not table or not table[0]:
        return False
    header_text = " ".join(str(c).lower() for c in table[0] if c)
    hits = sum(1 for kw in _HEADER_KEYWORDS if kw in header_text)
    return hits >= 2


def _cell_float(value: str) -> float:
    text = str(value).strip().replace(" ", "").replace(",", ".")
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


def _row_cells(row: list) -> list[str]:
    """Reduziert eine Tabellenzeile auf ihre nicht-leeren Zellen (als Strings).

    pdfplumber erzeugt bei vielen Gitterlinien zahlreiche leere/None-Spalten —
    nach dem Filtern bleibt nur noch die tatsächlich befüllte Spaltenanzahl übrig,
    anhand der sich Datenzeilen robust von Kopf-/Fortsetzungszeilen unterscheiden lassen.
    """
    return [str(c).strip() for c in row if c is not None and str(c).strip() != ""]


def _is_ean_like(token: str) -> bool:
    return token.isdigit() and 8 <= len(token) <= 14


def _parse_alina_invoice(filepath: str) -> list[dict]:
    """ALINA/FCT-Rechnungsformat ("Invoice ARGxxxx..."): Produktdaten in
    Tabellenzellen, eine Zeile pro Position:
        Pos. | EAN Code | Description | Quantity | Unit Price | Disc.% | Amount
    Mehrzeilige Beschreibungen liegen bereits als "\\n" innerhalb der
    Description-Zelle vor. Zusätzliche "Shp.No. ..."-Zeilen (eigene,
    sonst leere Tabellenzeile) werden ignoriert.
    """
    items = []
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    cells = _row_cells(row)
                    if len(cells) != 7:
                        continue
                    pos, ean, desc, qty, price, _disc, _amount = cells
                    if not (pos.isdigit() and _is_ean_like(ean) and qty.isdigit()):
                        continue
                    items.append({
                        "ean":          ean,
                        "product":      _clean(desc),
                        "quantity":     int(qty),
                        "source_price": _cell_float(price),
                    })
    return items


def _parse_alina_po(filepath: str) -> list[dict]:
    """ALINA-Bestellformat ("BESTELLUNG EBxxxx..."): Produktdaten in
    Tabellenzellen, eine Zeile pro Position:
        Nr. | EAN Code | Beschreibung | Menge | EK-Preis | Betrag
    Die "Nr."-Spalte enthält denselben Code wie "EAN Code", nur über zwei
    Zeilen umgebrochen — sie wird verworfen, die volle EAN-Spalte verwendet.
    Zusätzliche Beschreibungszeilen stehen in eigenen, sonst leeren
    Tabellenzeilen (eine einzige nicht-leere Zelle) und werden an die
    vorherige Position angehängt.
    """
    items = []
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    cells = _row_cells(row)
                    if len(cells) == 1 and items:
                        items[-1]["product"] = _clean(f'{items[-1]["product"]} {cells[0]}')
                        continue
                    if len(cells) != 6:
                        continue
                    _nr, ean, desc, menge, ek_preis, _betrag = cells
                    if not (_is_ean_like(ean) and menge.isdigit()):
                        continue
                    items.append({
                        "ean":          ean,
                        "product":      _clean(desc),
                        "quantity":     int(menge),
                        "source_price": _cell_float(ek_preis),
                    })
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


def _parse_fct(filepath: str) -> list[dict]:
    """FCT-Format: Produktdaten befinden sich im Fließtext, EAN folgt in eigener Zeile.

    Beispiel:
        DKNY 24/7 Edp Spray 50 ml UG 48 12,80 614,40
        085715950451

    Mehrzeilige Produktnamen werden über Fortsetzungszeilen bis zur EAN-Zeile gesammelt:
        Narciso Rodriguez Musc Noir Rose For Her Edp 100 ml UG 100 47,13 4.713,00
        Spray
        3423222055547
    """
    all_lines: list[str] = []
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                all_lines.extend(text.split("\n"))

    items = []
    i = 0
    while i < len(all_lines):
        m = _RE_FCT_LINE.match(all_lines[i].strip())
        if not m:
            i += 1
            continue

        desc_parts = [m.group(1).strip()]
        qty_str = m.group(2)
        qty = int(float(qty_str.replace(',', '.')))
        unit_price = _cell_float(m.group(3))
        i += 1

        ean = ""
        while i < len(all_lines):
            cont = all_lines[i].strip()
            if _RE_FCT_EAN.match(cont):
                ean = cont
                i += 1
                break
            if not cont or _RE_FCT_LINE.match(cont):
                break
            desc_parts.append(cont)
            i += 1

        items.append({
            "ean":          ean,
            "product":      _clean(" ".join(desc_parts)),
            "quantity":     qty,
            "source_price": unit_price,
        })

    return items


def _parse_pwv(filepath: str) -> list[dict]:
    """PWV-Format (Parfumeriewarenvertriebs GmbH): Produktdaten im Fließtext,
    EAN folgt in eigener Zeile mit 'EAN'-Präfix.

    Beispiel:
        1 056L2850301 La Vie est Belle EdP Vapo 30ml 7 STK 32,07 224,49
        EAN 3605532612690

    Mehrzeilige Produktnamen werden über Fortsetzungszeilen bis zur EAN-Zeile gesammelt:
        5 052LE3108 Acqua di Gio p.H. Profondo EdP 4 STK 43,57 174,28
        50ml
        EAN 3614273953856
    """
    all_lines: list[str] = []
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                all_lines.extend(text.split("\n"))

    items = []
    i = 0
    while i < len(all_lines):
        m = _RE_PWV_LINE.match(all_lines[i].strip())
        if not m:
            i += 1
            continue

        desc_parts = [m.group(1).strip()]
        qty        = int(m.group(2))
        unit_price = _cell_float(m.group(3))
        i += 1

        ean = ""
        while i < len(all_lines):
            cont = all_lines[i].strip()
            m_ean = _RE_PWV_EAN.match(cont)
            if m_ean:
                ean = m_ean.group(1)
                i += 1
                break
            if not cont or _RE_PWV_LINE.match(cont):
                break
            desc_parts.append(cont)
            i += 1

        items.append({
            "ean":          ean,
            "product":      _clean(" ".join(desc_parts)),
            "quantity":     qty,
            "source_price": unit_price,
        })

    return items


def _parse_znz(filepath: str) -> list[dict]:
    """ZNZ-Format (ZNZ ELECTRONICS, s.r.o.): Artikelzeile + Datenzeile im Fließtext.

    Beispiel:
        1 100130496 Armaf Club de Nuit Intense Man Perfumed Deostick 75 g (man)
        4,00 ks 7,33 29,32 0 33072000 0 29,32

    Die Positionstabelle beginnt erst nach der Kopfzeile mit "Quantity" und
    "Unit Price" und endet bei "Invoice total" – nur in diesem Bereich wird
    nach Artikel-/Datenzeilen gesucht, um Fließtext aus Adress- und
    Kopfblöcken nicht versehentlich als Position zu erkennen.
    """
    all_lines: list[str] = []
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                all_lines.extend(text.split("\n"))

    items = []
    in_table = False
    i = 0
    while i < len(all_lines):
        line = all_lines[i].strip()

        if not in_table:
            if "Quantity" in line and "Unit Price" in line:
                in_table = True
            i += 1
            continue

        if line.startswith("Invoice total"):
            in_table = False
            i += 1
            continue

        m_item = _RE_ZNZ_ITEM.match(line)
        if not m_item:
            i += 1
            continue

        desc_parts = [m_item.group(1).strip()]
        i += 1

        m_data = None
        while i < len(all_lines):
            cont = all_lines[i].strip()
            m_data = _RE_ZNZ_DATA.match(cont)
            if m_data:
                i += 1
                break
            if not cont or _RE_ZNZ_ITEM.match(cont) or cont.startswith("Invoice total"):
                break
            desc_parts.append(cont)
            i += 1

        if m_data and m_data.group(3):
            items.append({
                "ean":          "",
                "product":      _clean(" ".join(desc_parts)),
                "quantity":     int(m_data.group(1)),
                "source_price": _cell_float(m_data.group(2)),
            })

    return items


def parse_pdf(filepath: str) -> list[dict]:
    """
    Liest eine Lieferanten-PDF-Datei und gibt bestellte Positionen zurück.
    Versucht zuerst die Tabellenzellen-Formate (CIPO, ALINA-Rechnung,
    ALINA-Bestellung), dann die Fließtext-Formate (MATIVA, ZNZ, FCT, PWV).

    ZNZ wird vor FCT/PWV versucht, obwohl es zuletzt entdeckt wurde: FCT und
    PWV erkennen Datenzeilen anhand generischer, nicht auf einen Tabellen-
    bereich beschränkter Regex-Muster, die auch auf ZNZ-Datenzeilen passen
    (z.B. "6,00 ks 15,75 94,50 0 33030010 0 94,50" wird sonst fälschlich als
    FCT-Position mit Menge/Preis aus den falschen Spalten gelesen). ZNZ
    grenzt seinen Suchbereich über die Tabellenkopf- ("Quantity"/"Unit
    Price") und Endmarkierung ("Invoice total") ein und muss daher zuerst
    geprüft werden, damit es bei ZNZ-Dateien nicht von der falsch
    matchenden FCT-Regex überdeckt wird.

    Returns:
        list[dict]: Liste von Positionen mit Schlüsseln:
            - ean (str): EAN-Code (leer wenn nicht vorhanden)
            - product (str): Produktname (bereinigt)
            - quantity (int): Bestellmenge
            - source_price (float): Einkaufspreis aus der Quelldatei
    """
    items = _parse_cipo(filepath)

    if not items:
        items = _parse_alina_invoice(filepath)

    if not items:
        items = _parse_alina_po(filepath)

    if not items:
        items = _parse_mativa(filepath)

    if not items:
        items = _parse_znz(filepath)

    if not items:
        items = _parse_fct(filepath)

    if not items:
        items = _parse_pwv(filepath)

    if not items:
        raise ValueError(
            "Keine Positionen gefunden.\n"
            "Das PDF muss eine Tabelle mit 'Unit Price' und 'Quantity' enthalten."
        )

    items.sort(key=lambda x: x["product"].lower())
    return items

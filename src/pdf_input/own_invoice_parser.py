"""
Parser für RechnungsBot-eigene Rechnungs-PDFs.
Ermöglicht den Re-Import einer bereits exportierten Rechnung zum Nachbearbeiten.
"""

import re
import pdfplumber

from src.config import COMPANY, FOOTER

# ── Regex-Muster für Metadaten ─────────────────────────────────────────────────

_RE_INV_NR   = re.compile(r'Rechnung\s+Nr\.(\S+)')
_RE_INV_DATE = re.compile(r'Rechnungsdatum:\s*(\d{1,2}\.\d{1,2}\.\d{4})')
_RE_VAT_LINE = re.compile(r'VAT:\s*(.+)$', re.IGNORECASE)
_RE_PAGE_NO  = re.compile(r'Seite\s+\d+', re.IGNORECASE)
_RE_UST_LINE = re.compile(r'\bUst\.\s+€\s*[\d ]+,\d{2}\s+(\d+)%')

# ── Spalten-X-Grenzen in Punkten (1 mm = 2.8346 pt) ──────────────────────────
# Entsprechen den Spalten-Konstanten in InvoiceGenerator:
#   MARGIN_LEFT = 20 mm = 56.7 pt
#   COL_EAN     = 32 mm = 90.7 pt  → obere Grenze Stk.-Spalte
#   COL_PRODUCT = 54 mm = 153 pt   → obere Grenze EAN-Spalte, Beginn Produkt-Spalte
#   _X_EAN_MAX = 150 pt (3 pt Puffer unter COL_PRODUCT, damit Produkt-Wörter
#   die direkt bei x≈153 pt beginnen –- z.B. "Y.S.L." –- nicht ausgeschlossen werden)
#   COL_EP_R    = 145 mm = 411 pt  → Preise beginnen links davon
_X_STK_MAX   = 91   # rechte Grenze Stk.-Spalte
_X_EAN_MAX   = 150  # rechte Grenze EAN-Spalte / linke Grenze Produkt-Spalte
_X_PRICE_MIN = 360  # linke Grenze Preisspalten (etwas links von _ep_euro_x)

# Maximaler y-Abstand (in pt) zwischen Hauptzeile und Fortsetzungszeile (~8.8 mm)
# Zeilenumbrüche im Produkt: 3.5 mm ≈ 10 pt zwischen Zeilen
# Nächste Tabellenzeile: mind. 17 pt (6 mm ROW_HEIGHT) → 25 pt liegt sicher dazwischen
_Y_CONT_MAX = 25

# Bekannte Standard-Footer-Texte (für Notiz-Extraktion)
_KNOWN_FOOTER: set[str] = {t for t in (
    FOOTER.get("eu_text_1", ""),
    FOOTER.get("eu_text_2", ""),
    FOOTER.get("eu_text_3", ""),
    FOOTER.get("delivery_terms", ""),
    FOOTER.get("export_de_1", ""),
    FOOTER.get("export_de_2", ""),
    FOOTER.get("export_en_1", ""),
    FOOTER.get("export_en_2", ""),
    FOOTER.get("bank_1", ""),
    FOOTER.get("bank_2", ""),
    FOOTER.get("bank_3", ""),
    FOOTER.get("footer_right_1", ""),
    FOOTER.get("footer_right_3", ""),
    "SEPA-Überweisung via Banking-App",
) if t}


def _parse_amount(s: str) -> float:
    """Wandelt deutsches Zahlenformat um: '1 234,56' → 1234.56"""
    return float(s.replace(" ", "").replace(",", "."))


def is_own_invoice(filepath: str) -> bool:
    """Gibt True zurück, wenn das PDF eine RechnungsBot-Rechnung ist."""
    try:
        with pdfplumber.open(filepath) as pdf:
            if not pdf.pages:
                return False
            text = pdf.pages[0].extract_text() or ""
        return (
            COMPANY["name"] in text
            and "Rechnung Nr." in text
            and "Rechnungsdatum:" in text
        )
    except Exception:
        return False


def _extract_items_positional(filepath: str) -> list[dict]:
    """
    Extrahiert Tabellenzeilen seitenweise anhand von X/Y-Koordinaten.

    Verarbeitet jede Seite separat – dadurch gibt es keine seiten­übergreifende
    Kontamination durch Bankfooter oder Seitenköpfe der Folgeseite.
    Produktname-Fortsetzungszeilen werden nur akzeptiert, wenn ihr y-Abstand
    zur Hauptzeile ≤ _Y_CONT_MAX pt beträgt (entspricht dem Zeilenabstand
    bei umgebrochenem Produktnamen, aber weniger als ROW_HEIGHT zur nächsten
    Tabellenzeile).
    """
    items: list[dict] = []

    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            words = page.extract_words(x_tolerance=3, y_tolerance=3)
            if not words:
                continue

            # Wörter nach y-Position gruppieren (2-pt-Raster für Robustheit)
            buckets: dict[int, list] = {}
            for w in words:
                key = round(w["top"] / 2) * 2
                buckets.setdefault(key, []).append(w)

            last_main_y: int | None = None  # y der letzten echten Item-Zeile (diese Seite)

            for y_key in sorted(buckets.keys()):
                row = sorted(buckets[y_key], key=lambda w: w["x0"])

                # Menge: reine Ziffernfolge in der Stk.-Spalte
                qty: int | None = None
                for w in row:
                    if w["x0"] < _X_STK_MAX and w["text"].isdigit():
                        qty = int(w["text"])
                        break

                # Preis vorhanden: "€"-Zeichen in der Preisspalte
                has_price = any(
                    "€" in w["text"] and w["x0"] >= _X_PRICE_MIN
                    for w in row
                )

                if qty is not None and has_price:
                    # ── Tabellenzeile ────────────────────────────────────
                    # EAN: 8–14-stellige Ziffernfolge in der EAN-Spalte
                    ean = ""
                    for w in row:
                        if (
                            _X_STK_MAX <= w["x0"] < _X_EAN_MAX
                            and w["text"].isdigit()
                            and 8 <= len(w["text"]) <= 14
                        ):
                            ean = w["text"]
                            break

                    # Produkt: Wörter ausschließlich in der Produktspalte
                    product_words = [
                        w["text"]
                        for w in row
                        if _X_EAN_MAX <= w["x0"] < _X_PRICE_MIN
                        and not (w["text"].isdigit() and 8 <= len(w["text"]) <= 14)
                    ]
                    product = " ".join(product_words).strip()

                    # Einzelpreis: Zahl nach dem ersten "€" in der Preisspalte
                    unit_price = 0.0
                    past_euro = False
                    for w in row:
                        if w["x0"] < _X_PRICE_MIN:
                            continue
                        text = w["text"]
                        if "€" in text:
                            past_euro = True
                            # Fallback: falls "€" und Betrag zusammen extrahiert wurden
                            remainder = text.replace("€", "").strip()
                            if remainder:
                                try:
                                    unit_price = _parse_amount(remainder)
                                    past_euro = False  # schon erledigt
                                except ValueError:
                                    pass
                            continue
                        if past_euro:
                            try:
                                unit_price = _parse_amount(text)
                            except ValueError:
                                pass
                            break

                    if product:
                        items.append({
                            "ean":          ean,
                            "product":      product,
                            "quantity":     qty,
                            "source_price": unit_price,
                        })
                        last_main_y = y_key

                elif (
                    items
                    and last_main_y is not None
                    and (y_key - last_main_y) <= _Y_CONT_MAX
                ):
                    # ── Mögliche Produktname-Fortsetzungszeile ───────────
                    cont_words = [
                        w["text"]
                        for w in row
                        if _X_EAN_MAX <= w["x0"] < _X_PRICE_MIN
                    ]
                    if cont_words:
                        items[-1]["product"] += " " + " ".join(cont_words)

    return items


def parse_own_invoice(filepath: str) -> dict:
    """
    Parst eine RechnungsBot-Rechnung und gibt alle Felder zurück.

    Returns:
        dict mit:
            items: list[{ean, product, quantity, source_price}]
            invoice_data: dict
            customer_data: dict
    """
    # Alle Zeilen als flache Liste (für Metadaten-Extraktion)
    all_lines: list[str] = []
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                all_lines.extend(text.split("\n"))

    invoice_data: dict = {
        "number":            "",
        "date":              "",
        "ust_enabled":       False,
        "ust_percent":       20.0,
        "is_export":         False,
        "eu_text_enabled":   True,
        "girocode_enabled":  True,
        "invoice_note_text": "",
    }
    customer_data: dict = {
        "name":     "",
        "street":   "",
        "plz_city": "",
        "country":  "",
        "vat":      "",
    }

    # ── Schritt 1: Metadaten aus Fließtext ─────────────────────────────────────
    in_address  = False
    address_done = False
    addr_field  = 0

    for line in all_lines:
        stripped = line.strip()

        if not invoice_data["number"]:
            m = _RE_INV_NR.search(stripped)
            if m:
                invoice_data["number"] = m.group(1).strip()

        if not invoice_data["date"]:
            m = _RE_INV_DATE.search(stripped)
            if m:
                invoice_data["date"] = m.group(1).strip()

        if stripped == "EXPORT":
            invoice_data["is_export"] = True

        m = _RE_UST_LINE.search(stripped)
        if m:
            pct = int(m.group(1))
            if pct > 0:
                invoice_data["ust_enabled"] = True
                invoice_data["ust_percent"] = float(pct)

        # Adressblock: beginnt nach "An"
        if stripped == "An" and not address_done:
            in_address  = True
            addr_field  = 0
            continue

        if in_address and not address_done:
            if not stripped:
                continue
            if "Rechnung Nr." in stripped:
                in_address   = False
                address_done = True
                continue
            m_vat = _RE_VAT_LINE.search(stripped)
            if m_vat:
                customer_data["vat"] = m_vat.group(1).strip()
                in_address   = False
                address_done = True
                continue
            clean = _RE_PAGE_NO.sub("", stripped).strip()
            if not clean:
                continue
            if addr_field == 0:
                customer_data["name"] = clean
            elif addr_field == 1:
                customer_data["street"] = clean
            elif addr_field == 2:
                customer_data["plz_city"] = clean
            elif addr_field == 3:
                customer_data["country"] = clean
            addr_field += 1

    full_text = "\n".join(all_lines)
    eu_text_1 = FOOTER.get("eu_text_1", "")
    invoice_data["eu_text_enabled"] = bool(eu_text_1 and eu_text_1 in full_text)

    # ── Schritt 2: Positionen seitenweise mit X/Y-Koordinaten extrahieren ──────
    items = _extract_items_positional(filepath)

    # ── Schritt 3: Rechnungsnotiz extrahieren ───────────────────────────────────
    note_lines: list[str] = []
    after_summary = False
    bank_marker   = FOOTER.get("bank_1", "ERSTE BANK")

    for line in all_lines:
        stripped = line.strip()
        if "Gesamtsumme Brutto" in stripped:
            after_summary = True
            continue
        if not after_summary or not stripped:
            continue
        if bank_marker and bank_marker in stripped:
            break
        is_known = any(
            stripped == kf or (len(kf) > 10 and kf in stripped)
            for kf in _KNOWN_FOOTER
        )
        if not is_known:
            note_lines.append(stripped)

    invoice_data["invoice_note_text"] = "\n".join(note_lines)

    return {
        "items":         items,
        "invoice_data":  invoice_data,
        "customer_data": customer_data,
    }

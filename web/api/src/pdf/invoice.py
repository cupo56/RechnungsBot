"""
PDF-Rechnungsgenerator für RechnungsBot.
Erstellt professionelle PDF-Rechnungen im Layout der Handelsagentur Adis Sefer.
"""

import math
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics

from src.config import COMPANY, FOOTER
from src.pdf.common import (
    PAGE_W, PAGE_H, MARGIN_LEFT, MARGIN_RIGHT, MARGIN_TOP, MARGIN_BOTTOM,
    FONT_SIZE_NORMAL, FONT_SIZE_SMALL, FONT_SIZE_HEADER, FONT_SIZE_TITLE,
    ROW_HEIGHT, register_fonts, truncate_text, draw_bank_footer,
)

# Tabellen-Spalten (X-Positionen) — rechnungsspezifisch
COL_STK_C   = MARGIN_LEFT + 5 * mm
COL_EAN     = MARGIN_LEFT + 12 * mm
COL_PRODUCT = MARGIN_LEFT + 34 * mm
COL_EP_R    = 145 * mm
COL_GP_R    = 173 * mm
COL_UST_C   = MARGIN_RIGHT - 6 * mm

COL_SUMMARY_L = 110 * mm


def _format_amount(val):
    """Formatiert nur die Zahl eines Betrags, z.B. '7 411,07'."""
    return f"{val:,.2f}".replace(",", " ").replace(".", ",")


def _format_currency(val):
    """Formatiert einen Betrag als Währung z.B. '€ 7 411,07'."""
    return f"€ {_format_amount(val)}"


class InvoiceGenerator:
    """Generiert eine PDF-Rechnung."""

    def __init__(self, items, invoice_data, customer_data, output_path):
        """
        Args:
            items: Liste von dicts mit ean, product, quantity, unit_price
            invoice_data: dict mit number, date, markup_factor, ust_enabled, ust_percent
            customer_data: dict mit name, street, plz_city, country, vat
            output_path: Pfad für die PDF-Datei
        """
        self.items = items
        self.inv = invoice_data
        self.cust = customer_data
        self.output_path = output_path
        self.page_num = 0
        self.c = None

    def generate(self):
        """Erstellt die PDF-Rechnung und speichert sie."""
        register_fonts()

        self.c = canvas.Canvas(self.output_path, pagesize=A4)
        self.c.setTitle(f"Rechnung {self.inv['number']}")

        self.page_num = 0
        self._row_counter = 0
        # Gesamtwerte einmalig berechnen (werden von _draw_summary und _draw_girocode genutzt)
        ust_pct = self.inv.get("ust_percent", 0) if self.inv.get("ust_enabled", False) else 0
        self._total_netto = sum(item["quantity"] * item["unit_price"] for item in self.items)
        self._total_qty   = sum(item["quantity"] for item in self.items)
        self._total_ust   = ust_pct
        self._total_brutto = self._total_netto * (1 + ust_pct / 100)

        # Linksbündige Ausrichtung der Beträge in Einzelpreis-/Gesamtpreis-Spalte:
        # Das €-Zeichen steht in jeder Zeile an derselben X-Position (untereinander
        # ausgerichtet), die Zahl folgt linksbündig danach. Die X-Position wird so
        # gewählt, dass der breiteste Betrag noch am rechten Spaltenrand endet.
        euro_gap = pdfmetrics.stringWidth("€ ", "Arial", FONT_SIZE_SMALL)
        max_ep_w = max((pdfmetrics.stringWidth(_format_amount(item["unit_price"]), "Arial", FONT_SIZE_SMALL)
                        for item in self.items), default=0)
        max_gp_w = max((pdfmetrics.stringWidth(_format_amount(item["quantity"] * item["unit_price"]), "Arial", FONT_SIZE_SMALL)
                        for item in self.items), default=0)
        self._ep_euro_x = COL_EP_R - euro_gap - max_ep_w
        self._gp_euro_x = COL_GP_R - euro_gap - max_gp_w
        total_pages = self._estimate_total_pages()

        self._start_new_page()
        y = self._draw_page_header(total_pages)

        # Tabellenüberschriften
        y = self._draw_table_header(y)

        # Positionen zeichnen
        for i, item in enumerate(self.items):
            is_last = (i == len(self.items) - 1)
            
            # Für das letzte Element reservieren wir Platz für Zusammenfassung und Footer (~75mm)
            if is_last:
                min_y = MARGIN_BOTTOM + 75 * mm
            else:
                min_y = MARGIN_BOTTOM + 10 * mm
                
            if y - ROW_HEIGHT < min_y:
                # Rahmen für aktuelle Seite schließen
                self._draw_table_borders(y)
                # Neue Seite
                self._start_new_page()
                y = self._draw_page_header(total_pages)
                y = self._draw_table_header(y)

            y = self._draw_item_row(y, item)

        # Rahmen um die gesamte Tabelle (oder den Rest auf dieser Seite) zeichnen
        self._draw_table_borders(y)

        # Zusammenfassung und Footer
        y = self._draw_summary(y)
        self._draw_footer(y)

        self.c.save()
        return self.output_path

    def _calculate_header_height(self):
        """Berechnet die tatsächliche Kopfzeilenhöhe anhand der Kundendaten."""
        # Firmenblock: Name + 6 Zeilen + Abstand = 30.5 mm
        h = 4.5 + 6 * 4.0 + 2.0
        # Empfänger: "An" + Kundenname
        h += 4.5 + 4.0
        for field in ("street", "plz_city", "country"):
            if self.cust.get(field, "").strip():
                h += 4.0
        if self.cust.get("vat", "").strip():
            h += 4.0
        h += 32.0  # Abstand nach Adresse (an manuellen Wert 32mm angepasst)
        h += 6.0   # Rechnungsnummer / Datum
        h += 20.0  # Export-Slot (an manuellen Wert 20mm angepasst)
        # Tabellenüberschriften (_draw_table_header): 2 mm gap + 4 mm + ROW_HEIGHT
        h += 2.0 + 4.0 + 6.0
        return h * mm

    def _estimate_total_pages(self):
        """Schätzt die Gesamtseitenzahl."""
        n = len(self.items)
        if n == 0:
            return 1

        usable = PAGE_H - 15 * mm - MARGIN_BOTTOM - self._calculate_header_height()
        rows_per_page = max(1, int(usable / ROW_HEIGHT))
        # generate() reserviert 75 mm für Summary + Footer beim letzten Element
        rows_last_page = max(1, int((usable - 75 * mm) / ROW_HEIGHT))

        if n <= rows_last_page:
            return 1
        return 1 + math.ceil((n - rows_last_page) / rows_per_page)

    def _start_new_page(self):
        """Startet eine neue Seite."""
        if self.page_num > 0:
            self.c.showPage()
        self.page_num += 1

    def _draw_page_header(self, total_pages=1):
        """Zeichnet den Seitenkopf mit Firmen- und Kundendaten. Gibt Y-Position nach Header zurück."""
        c = self.c
        y = MARGIN_TOP

        # --- Firmendaten (rechts oben) ---
        c.setFont("Arial-Bold", FONT_SIZE_HEADER)
        c.drawRightString(MARGIN_RIGHT, y, COMPANY["name"])
        y -= 4.5 * mm

        c.setFont("Arial", FONT_SIZE_NORMAL)
        for line in [
            COMPANY["street"], 
            COMPANY["city"], 
            COMPANY["phone"], 
            COMPANY["email"], 
            COMPANY["atu"], 
            COMPANY["eori"]
        ]:
            c.drawRightString(MARGIN_RIGHT, y, line)
            y -= 4 * mm

        y -= 2 * mm

        # --- Empfänger (links) ---
        c.setFont("Arial", FONT_SIZE_NORMAL)
        c.drawString(MARGIN_LEFT, y, "An")
        y -= 4.5 * mm

        c.setFont("Arial-Bold", FONT_SIZE_NORMAL)
        c.drawString(MARGIN_LEFT, y, self.cust.get("name", ""))

        # Seitenzahl rechts
        c.setFont("Arial", FONT_SIZE_NORMAL)
        c.drawString(COL_EP_R, y, f"Seite {self.page_num}")
        y -= 4 * mm

        c.setFont("Arial", FONT_SIZE_NORMAL)
        for line in [
            self.cust.get("street", ""),
            self.cust.get("plz_city", ""),
            self.cust.get("country", ""),
        ]:
            if line.strip():
                c.drawString(MARGIN_LEFT, y, line)
                y -= 4 * mm

        vat = self.cust.get("vat", "")
        if vat.strip():
            c.drawString(MARGIN_LEFT, y, f"VAT: {vat}")
            y -= 4 * mm

        y -= 32 * mm # Abstand vor Rechnungsnummer

        # --- Rechnungsnummer & Datum ---
        c.setFont("Arial-Bold", FONT_SIZE_TITLE)
        c.drawString(MARGIN_LEFT, y, f"Rechnung Nr.{self.inv['number']}")
        c.setFont("Arial", FONT_SIZE_NORMAL)
        c.drawRightString(MARGIN_RIGHT, y, f"Rechnungsdatum: {self.inv['date']}")
        y -= 6 * mm

        # --- EXPORT-Label ---
        if self.inv.get("is_export", False):
            c.setFont("Arial-Bold", FONT_SIZE_TITLE)
            c.drawCentredString(PAGE_W / 2, y, "EXPORT")
        y -= 20 * mm # 2 Absätze extra Abstand

        footer_y = draw_bank_footer(self.c)
        if self.inv.get("girocode_enabled", True):
            self._draw_girocode_in_footer(footer_y)

        return y

    def _draw_table_borders(self, end_y):
        """Zeichnet einen Rahmen um die Tabelle auf der aktuellen Seite."""
        if hasattr(self, 'current_table_start_y'):
            c = self.c
            c.setStrokeColorRGB(0.0, 0.0, 0.0)
            c.setLineWidth(0.5)
            height = self.current_table_start_y - end_y
            c.rect(MARGIN_LEFT, end_y, MARGIN_RIGHT - MARGIN_LEFT, height, fill=0, stroke=1)

    def _draw_table_header(self, y):
        """Zeichnet die Tabellenüberschriften."""
        c = self.c

        # Etwas mehr Abstand nach oben
        y -= 2 * mm

        # Grauer Hintergrund für Kopfzeile
        c.setFillColorRGB(0.85, 0.85, 0.85)
        c.rect(MARGIN_LEFT, y - 4 * mm, MARGIN_RIGHT - MARGIN_LEFT, 9.5 * mm, fill=1, stroke=0)
        c.setFillColorRGB(0, 0, 0)
        
        self.current_table_start_y = y + 5.5 * mm

        # Obere Trennlinie (wird auch vom äußeren Rahmen überzeichnet)
        c.setStrokeColorRGB(0.0, 0.0, 0.0)
        c.setLineWidth(0.5)
        c.line(MARGIN_LEFT, y + 5.5 * mm, MARGIN_RIGHT, y + 5.5 * mm)

        c.setFont("Arial-Bold", FONT_SIZE_SMALL)
        c.drawCentredString(COL_STK_C, y, "Stk.")
        c.drawCentredString((COL_EAN + COL_PRODUCT) / 2, y, "EAN")
        c.drawCentredString((COL_PRODUCT + COL_EP_R - 15 * mm) / 2, y, "Produkt")

        # Gestapelte Preise
        c.drawRightString(COL_EP_R, y + 2 * mm, "Einzelpreis")
        c.drawRightString(COL_EP_R, y - 1.5 * mm, "(Netto)")

        c.drawRightString(COL_GP_R, y + 2 * mm, "Gesamtpreis")
        c.drawRightString(COL_GP_R, y - 1.5 * mm, "(Netto)")

        if self.inv.get("ust_enabled", False):
            c.drawCentredString(COL_UST_C, y, "Ust.")

        # Untere Trennlinie des Headers
        y -= 4 * mm
        c.setLineWidth(0.5)
        c.line(MARGIN_LEFT, y, MARGIN_RIGHT, y)
        y -= ROW_HEIGHT

        return y

    def _draw_item_row(self, y, item):
        """Zeichnet eine Positionszeile."""
        c = self.c

        if self._row_counter % 2 == 1:
            c.setFillColorRGB(0.94, 0.94, 0.94)
            c.rect(MARGIN_LEFT, y - 1.5 * mm, MARGIN_RIGHT - MARGIN_LEFT, ROW_HEIGHT, fill=1, stroke=0)
            c.setFillColorRGB(0, 0, 0)

        self._row_counter += 1

        c.setFont("Arial", FONT_SIZE_SMALL)

        quantity = item["quantity"]
        unit_price = item["unit_price"]
        total_price = quantity * unit_price
        ust_val = self.inv.get("ust_percent", 0) if self.inv.get("ust_enabled", False) else 0

        c.drawCentredString(COL_STK_C, y, str(quantity))
        c.drawCentredString((COL_EAN + COL_PRODUCT) / 2, y, str(item["ean"]))

        # Produktname kürzen wenn nötig
        max_product_width = COL_EP_R - COL_PRODUCT - 15 * mm
        product_text = truncate_text(item["product"], "Arial", FONT_SIZE_SMALL, max_product_width)
        c.drawString(COL_PRODUCT, y, product_text)

        self._draw_amount_left(self._ep_euro_x, y, unit_price)
        self._draw_amount_left(self._gp_euro_x, y, total_price)
        if self.inv.get("ust_enabled", False):
            c.drawCentredString(COL_UST_C, y, f"{int(ust_val)}%")

        y -= ROW_HEIGHT
        return y

    def _draw_amount_left(self, euro_x, y, val):
        """Zeichnet einen Betrag linksbündig: '€' an fester X-Position (über alle
        Zeilen ausgerichtet), die Zahl folgt direkt linksbündig danach."""
        c = self.c
        c.drawString(euro_x, y, "€")
        amount_x = euro_x + pdfmetrics.stringWidth("€ ", "Arial", FONT_SIZE_SMALL)
        c.drawString(amount_x, y, _format_amount(val))

    def _draw_summary(self, y):
        """Zeichnet die Zusammenfassung (Netto, USt., Brutto)."""
        c = self.c

        netto          = self._total_netto
        ust_percent    = self._total_ust
        ust_amount     = netto * ust_percent / 100
        brutto         = self._total_brutto
        total_quantity = self._total_qty

        y -= 4 * mm
        c.setFont("Arial", FONT_SIZE_NORMAL)
        c.drawCentredString(COL_STK_C, y, str(total_quantity))

        c.setFont("Arial-Bold", FONT_SIZE_NORMAL)
        
        SUMMARY_LABEL_R = COL_GP_R - 25 * mm

        # Netto
        c.drawRightString(SUMMARY_LABEL_R, y, "Netto")
        c.drawRightString(COL_GP_R, y, _format_currency(netto))
        y -= 5 * mm

        # USt.
        c.drawRightString(SUMMARY_LABEL_R, y, "Ust.")
        c.drawRightString(COL_GP_R, y, _format_currency(ust_amount))
        c.drawCentredString(COL_UST_C, y, f"{int(ust_percent)}%")
        y -= 5 * mm

        # Linie über Brutto
        c.setStrokeColorRGB(0.0, 0.0, 0.0)
        c.setLineWidth(1.0)
        line_start_x = SUMMARY_LABEL_R - pdfmetrics.stringWidth("Gesamtsumme Brutto", "Arial-Bold", FONT_SIZE_NORMAL) - 5 * mm
        c.line(line_start_x, y + 3 * mm, MARGIN_RIGHT, y + 3 * mm)

        # Brutto
        c.setFont("Arial-Bold", FONT_SIZE_NORMAL)
        c.drawRightString(SUMMARY_LABEL_R, y, "Gesamtsumme Brutto")
        c.drawRightString(COL_GP_R, y, _format_currency(brutto))
        y -= 8 * mm

        return y

    def _draw_girocode_in_footer(self, footer_y):
        """Platziert den GiroCode verkleinert mittig zwischen Bankdaten und Firmen-/Steuerdaten
        in der Fußzeile (auf Höhe von draw_bank_footer)."""
        try:
            from src.pdf.girocode import generate_epc_qr

            amount = self._total_brutto

            iban = FOOTER.get("iban", "AT532011182010592702")
            bic = FOOTER.get("bic", "GIBAATWWXXX")
            reference = f"Rechnung {self.inv['number']}"

            buf = generate_epc_qr(iban, bic, COMPANY["name"], amount, reference)
            qr_img = ImageReader(buf)

            # Lücke zwischen rechtem Rand der Bankdaten (links) und linkem Rand
            # der Firmen-/Steuerdaten (rechts) ermitteln, QR-Code dort zentrieren
            left_w = max(
                pdfmetrics.stringWidth(FOOTER["bank_1"], "Arial", FONT_SIZE_NORMAL),
                pdfmetrics.stringWidth(FOOTER["bank_2"], "Arial", FONT_SIZE_NORMAL),
                pdfmetrics.stringWidth(FOOTER["bank_3"], "Arial", FONT_SIZE_NORMAL),
            )
            right_w = max(
                pdfmetrics.stringWidth(FOOTER["footer_right_1"], "Arial-Bold", FONT_SIZE_TITLE),
                pdfmetrics.stringWidth(FOOTER["footer_right_2"], "Arial", FONT_SIZE_NORMAL),
                pdfmetrics.stringWidth(FOOTER["footer_right_3"], "Arial", FONT_SIZE_NORMAL),
            )
            gap_left  = MARGIN_LEFT + left_w
            gap_right = MARGIN_RIGHT - right_w
            center_x  = (gap_left + gap_right) / 2

            size = 16 * mm
            qr_x = center_x - size / 2
            qr_y = (footer_y + 4 * mm) - size / 2  # vertikal mittig zur 3-zeiligen Fußzeile
            self.c.drawImage(qr_img, qr_x, qr_y, size, size)
        except Exception as e:
            print(f"[RechnungsBot] GiroCode konnte nicht erzeugt werden: {e}")

    def _draw_footer(self, y):
        """Zeichnet Lieferbedingungen oder Export-Texte."""
        c = self.c

        y -= 10 * mm

        c.setFont("Arial", FONT_SIZE_NORMAL)
        custom_text = self.inv.get("invoice_note_text", "").strip()
        if custom_text:
            for line in custom_text.splitlines():
                if line.strip():
                    c.drawString(COL_EAN, y, line.strip())
                    y -= 6 * mm
        elif self.inv.get("is_export", False):
            c.drawString(COL_EAN, y, FOOTER.get("delivery_terms", "Lieferbedinungen: EXW 1230 Wien, Mellergasse 4-02"))
            y -= 8 * mm
        else:
            if self.inv.get("eu_text_enabled", True):
                c.drawString(COL_EAN, y, FOOTER.get("eu_text_1", "Steuerfreie, innergemeinschaftliche Lieferung gem. Artikel 6 UStG."))
                y -= 12 * mm
            c.drawString(COL_EAN, y, FOOTER.get("eu_text_2", "Leistungsdatum ist gleich dem Rechnungsdatum"))
            y -= 5 * mm
            c.drawString(COL_EAN, y, FOOTER.get("eu_text_3", "Beim Zahlungsverzug sind sämtliche Mahn.-und Inkassospesen zu ersetzen.Gerichtsstand ist Wien."))
            y -= 8 * mm

        return y


def generate_invoice(items, invoice_data, customer_data, output_path):
    """
    Erstellt eine PDF-Rechnung.

    Args:
        items: Liste von dicts mit ean, product, quantity, unit_price
        invoice_data: dict mit number, date, markup_factor, ust_enabled, ust_percent
        customer_data: dict mit name, street, plz_city, country, vat
        output_path: Dateipfad für das PDF

    Returns:
        str: Pfad zur erstellten PDF-Datei
    """
    generator = InvoiceGenerator(items, invoice_data, customer_data, output_path)
    return generator.generate()

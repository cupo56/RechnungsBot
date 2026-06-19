"""
PDF-Provisionsrechnungsgenerator für RechnungsBot.
Erstellt professionelle PDF-Provisionsrechnungen im Layout der Handelsagentur Adis Sefer.
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

# Tabellen-Spalten (X-Positionen) — provisionsrechnungsspezifisch
COL_MENGE_C  = MARGIN_LEFT + 6 * mm
COL_BESCHR_L = MARGIN_LEFT + 14 * mm
COL_BESCHR_R = 134 * mm
COL_EP_R     = 150 * mm
COL_GP_R     = 173 * mm
COL_UST_C    = MARGIN_RIGHT - 6 * mm

COL_SUMMARY_L = 110 * mm

NOTE_TEXT = "Provisionsverrechnung für unten angeführte Rechnungen"


def _format_amount(val):
    """Formatiert nur die Zahl eines Betrags, z.B. '7 366,00'."""
    return f"{val:,.2f}".replace(",", " ").replace(".", ",")


def _format_currency(val):
    """Formatiert einen Betrag als Währung z.B. '€ 7 366,00'."""
    return f"€ {_format_amount(val)}"


class CommissionInvoiceGenerator:
    """Generiert eine PDF-Provisionsrechnung."""

    def __init__(self, items, invoice_data, customer_data, output_path):
        """
        Args:
            items: Liste von dicts mit reference, description, net_amount
            invoice_data: dict mit number, date, ust_enabled, ust_percent, girocode_enabled
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
        """Erstellt die PDF-Provisionsrechnung und speichert sie."""
        register_fonts()

        self.c = canvas.Canvas(self.output_path, pagesize=A4)
        self.c.setTitle(f"Rechnung {self.inv['number']}")

        self.page_num = 0
        self._row_counter = 0

        ust_pct = self.inv.get("ust_percent", 0) if self.inv.get("ust_enabled", False) else 0
        self._total_netto  = sum(item["net_amount"] for item in self.items)
        self._total_ust    = ust_pct
        self._total_brutto = self._total_netto * (1 + ust_pct / 100)

        # Linksbündige Ausrichtung der Beträge — siehe InvoiceGenerator._draw_amount_left
        euro_gap = pdfmetrics.stringWidth("€ ", "Arial", FONT_SIZE_SMALL)
        max_ep_w = max((pdfmetrics.stringWidth(_format_amount(item["net_amount"]), "Arial", FONT_SIZE_SMALL)
                        for item in self.items), default=0)
        max_gp_w = max((pdfmetrics.stringWidth(_format_amount(item["net_amount"] * (1 + ust_pct / 100)), "Arial", FONT_SIZE_SMALL)
                        for item in self.items), default=0)
        self._ep_euro_x = COL_EP_R - euro_gap - max_ep_w
        self._gp_euro_x = COL_GP_R - euro_gap - max_gp_w

        total_pages = self._estimate_total_pages()

        self._start_new_page()
        y = self._draw_page_header(total_pages)
        y = self._draw_table_header(y)

        for i, item in enumerate(self.items):
            is_last = (i == len(self.items) - 1)

            # Für das letzte Element Platz für Zusammenfassung und Footer reservieren (~75mm)
            if is_last:
                min_y = MARGIN_BOTTOM + 75 * mm
            else:
                min_y = MARGIN_BOTTOM + 10 * mm

            if y - ROW_HEIGHT < min_y:
                self._draw_table_borders(y)
                self._start_new_page()
                y = self._draw_page_header(total_pages)
                y = self._draw_table_header(y)

            y = self._draw_item_row(y, item)

        self._draw_table_borders(y)

        y = self._draw_summary(y)
        self._draw_footer(y)

        self.c.save()
        return self.output_path

    def _calculate_header_height(self):
        """Berechnet die tatsächliche Kopfzeilenhöhe anhand der Kundendaten.
        Die Hinweiszeile erscheint nur auf Seite 1, wird hier aber pauschal
        mitgerechnet — das hält die Schätzung konservativ und verhindert,
        dass die Tabelle auf Folgeseiten über den reservierten Bereich hinausläuft."""
        h = 4.5 + 6 * 4.0 + 2.0
        h += 4.5 + 4.0
        for field in ("street", "plz_city", "country"):
            if self.cust.get(field, "").strip():
                h += 4.0
        if self.cust.get("vat", "").strip():
            h += 4.0
        h += 18.0   # Abstand nach Adresse
        h += 6.0 + 2 * 6.0   # Rechnungsnummer / Datum + zusätzlicher Abstand (2 Absätze)
        h += 6.0   # Hinweiszeile "Provisionsverrechnung für unten angeführte Rechnungen"
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
            COMPANY["eori"],
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

        y -= 18 * mm

        # --- Rechnungsnummer & Datum ---
        c.setFont("Arial-Bold", FONT_SIZE_TITLE)
        c.drawString(MARGIN_LEFT, y, f"Rechnung Nr.{self.inv['number']}")
        c.setFont("Arial", FONT_SIZE_NORMAL)
        c.drawRightString(MARGIN_RIGHT, y, f"Rechnungsdatum: {self.inv['date']}")
        y -= 6 * mm + 2 * ROW_HEIGHT

        if self.page_num == 1:
            c.setFont("Arial-Bold", FONT_SIZE_SMALL + 2)
            c.drawCentredString(PAGE_W / 2, y, NOTE_TEXT)
            y -= ROW_HEIGHT

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

        y -= 2 * mm

        # Grauer Hintergrund für Kopfzeile
        c.setFillColorRGB(0.85, 0.85, 0.85)
        c.rect(MARGIN_LEFT, y - 4 * mm, MARGIN_RIGHT - MARGIN_LEFT, 9.5 * mm, fill=1, stroke=0)
        c.setFillColorRGB(0, 0, 0)

        self.current_table_start_y = y + 5.5 * mm

        c.setStrokeColorRGB(0.0, 0.0, 0.0)
        c.setLineWidth(0.5)
        c.line(MARGIN_LEFT, y + 5.5 * mm, MARGIN_RIGHT, y + 5.5 * mm)

        c.setFont("Arial-Bold", FONT_SIZE_SMALL)
        c.drawCentredString(COL_MENGE_C, y, "Menge")
        c.drawCentredString((COL_BESCHR_L + COL_BESCHR_R) / 2, y, "Beschreibung")

        c.drawRightString(COL_EP_R, y + 2 * mm, "Einzelpreis")
        c.drawRightString(COL_EP_R, y - 1.5 * mm, "(Netto)")

        c.drawRightString(COL_GP_R, y + 2 * mm, "Gesamtpreis")
        c.drawRightString(COL_GP_R, y - 1.5 * mm, "(Brutto)")

        if self.inv.get("ust_enabled", False):
            c.drawCentredString(COL_UST_C, y, "Ust.")

        y -= 4 * mm
        c.setLineWidth(0.5)
        c.line(MARGIN_LEFT, y, MARGIN_RIGHT, y)
        y -= ROW_HEIGHT

        return y

    def _draw_item_row(self, y, item):
        """Zeichnet eine Positionszeile (Referenz links, Beschreibung rechts in der Spalte)."""
        c = self.c

        if self._row_counter % 2 == 1:
            c.setFillColorRGB(0.94, 0.94, 0.94)
            c.rect(MARGIN_LEFT, y - 1.5 * mm, MARGIN_RIGHT - MARGIN_LEFT, ROW_HEIGHT, fill=1, stroke=0)
            c.setFillColorRGB(0, 0, 0)

        self._row_counter += 1

        c.setFont("Arial", FONT_SIZE_SMALL)

        net_amount = item["net_amount"]
        ust_val = self.inv.get("ust_percent", 0) if self.inv.get("ust_enabled", False) else 0
        gross_amount = net_amount * (1 + ust_val / 100)

        c.drawCentredString(COL_MENGE_C, y, "1")

        col_width = COL_BESCHR_R - COL_BESCHR_L
        desc_x = COL_BESCHR_L + col_width * 0.5
        reference = item.get("reference", "").strip()
        description = item.get("description", "").strip()
        if reference:
            ref_text = truncate_text(reference, "Arial", FONT_SIZE_SMALL, col_width * 0.45)
            c.drawString(COL_BESCHR_L, y, ref_text)
        if description:
            desc_text = truncate_text(description, "Arial", FONT_SIZE_SMALL, COL_BESCHR_R - desc_x)
            c.drawString(desc_x, y, desc_text)

        self._draw_amount_left(self._ep_euro_x, y, net_amount)
        self._draw_amount_left(self._gp_euro_x, y, gross_amount)
        if self.inv.get("ust_enabled", False):
            c.drawCentredString(COL_UST_C, y, f"{int(ust_val)}%")

        y -= ROW_HEIGHT
        return y

    def _draw_amount_left(self, euro_x, y, val):
        """Zeichnet einen Betrag linksbündig: '€' an fester X-Position
        (über alle Zeilen ausgerichtet), die Zahl folgt direkt linksbündig danach."""
        c = self.c
        c.drawString(euro_x, y, "€")
        amount_x = euro_x + pdfmetrics.stringWidth("€ ", "Arial", FONT_SIZE_SMALL)
        c.drawString(amount_x, y, _format_amount(val))

    def _draw_summary(self, y):
        """Zeichnet die Zusammenfassung (Netto, USt., Brutto)."""
        c = self.c

        netto       = self._total_netto
        ust_percent = self._total_ust
        ust_amount  = netto * ust_percent / 100
        brutto      = self._total_brutto

        y -= 4 * mm
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
            qr_y = (footer_y + 4 * mm) - size / 2
            self.c.drawImage(qr_img, qr_x, qr_y, size, size)
        except Exception as e:
            print(f"[RechnungsBot] GiroCode konnte nicht erzeugt werden: {e}")

    def _draw_footer(self, y):
        """Zeichnet die Fußzeilen-Hinweistexte (Leistungsdatum, Mahnspesen/Gerichtsstand)
        fix am unteren Seitenrand, mit einem Absatz Abstand zur Bankverbindung
        (draw_bank_footer, oberste Zeile bei MARGIN_BOTTOM + 3 mm)."""
        c = self.c

        bank_top = MARGIN_BOTTOM + 3 * mm
        line2_y = bank_top + 3 * ROW_HEIGHT
        line1_y = line2_y + 5 * mm

        c.setFont("Arial", FONT_SIZE_NORMAL)
        c.drawString(MARGIN_LEFT, line1_y, FOOTER.get("eu_text_2", "Leistungsdatum ist gleich dem Rechnungsdatum"))
        c.drawString(MARGIN_LEFT, line2_y, FOOTER.get("eu_text_3", "Beim Zahlungsverzug sind sämtliche Mahn.-und Inkassospesen zu ersetzen.Gerichtsstand ist Wien."))

        return y


def generate_commission_invoice(items, invoice_data, customer_data, output_path):
    """
    Erstellt eine PDF-Provisionsrechnung.

    Args:
        items: Liste von dicts mit reference, description, net_amount
        invoice_data: dict mit number, date, ust_enabled, ust_percent, girocode_enabled
        customer_data: dict mit name, street, plz_city, country, vat
        output_path: Dateipfad für das PDF

    Returns:
        str: Pfad zur erstellten PDF-Datei
    """
    generator = CommissionInvoiceGenerator(items, invoice_data, customer_data, output_path)
    return generator.generate()

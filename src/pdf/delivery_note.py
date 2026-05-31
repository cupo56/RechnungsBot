"""
PDF-Lieferscheingenerator für RechnungsBot.
Erstellt professionelle PDF-Lieferscheine.
"""

import math
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics

from src.config import COMPANY, FOOTER
from src.pdf.common import (
    PAGE_W, PAGE_H, MARGIN_LEFT, MARGIN_RIGHT, MARGIN_TOP, MARGIN_BOTTOM,
    FONT_SIZE_NORMAL, FONT_SIZE_SMALL, FONT_SIZE_HEADER, FONT_SIZE_TITLE,
    ROW_HEIGHT, register_fonts, truncate_text, draw_bank_footer,
)

# Tabellen-Spalten (X-Positionen) — lieferscheinspezifisch
COL_EAN     = MARGIN_LEFT + 4 * mm
COL_PRODUCT = MARGIN_LEFT + 26 * mm
COL_QTY_R   = MARGIN_RIGHT - 4 * mm


class DeliveryNoteGenerator:
    """Generiert einen PDF-Lieferschein."""

    def __init__(self, items, invoice_data, customer_data, output_path):
        """
        Args:
            items: Liste von dicts mit ean, product, quantity
            invoice_data: dict mit number, date, ust_enabled, weight
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
        """Erstellt den PDF-Lieferschein und speichert ihn."""
        register_fonts()

        self.c = canvas.Canvas(self.output_path, pagesize=A4)
        self.c.setTitle(f"Lieferschein {self.inv['number']}")

        self.page_num = 0
        self._row_counter = 0
        total_pages = self._estimate_total_pages()

        # Erste Seite starten
        self._start_new_page()
        y = self._draw_page_header(total_pages)

        # Tabellenüberschriften
        y = self._draw_table_header(y)

        # Positionen zeichnen
        for i, item in enumerate(self.items):
            is_last = (i == len(self.items) - 1)
            
            # Platz für Footer auf letzter Seite reservieren (~50mm)
            if is_last:
                min_y = MARGIN_BOTTOM + 50 * mm
            else:
                min_y = MARGIN_BOTTOM + 10 * mm
                
            if y - ROW_HEIGHT < min_y:
                self._draw_table_borders(y)
                # Neue Seite
                self._start_new_page()
                y = self._draw_page_header(total_pages)
                y = self._draw_table_header(y)

            y = self._draw_item_row(y, item)

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
        h += 4.0   # Abstand nach Adresse
        h += 8.0   # Export-Slot (immer reserviert)
        h += 6.0   # Lieferschein-Titel / Datum
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
        # generate() reserviert 50 mm für Summary + Footer beim letzten Element
        rows_last_page = max(1, int((usable - 50 * mm) / ROW_HEIGHT))

        if n <= rows_last_page:
            return 1
        return 1 + math.ceil((n - rows_last_page) / rows_per_page)

    def _start_new_page(self):
        """Startet eine neue Seite."""
        if self.page_num > 0:
            self.c.showPage()
        self.page_num += 1

    def _draw_page_header(self, total_pages=1):
        """Zeichnet den Seitenkopf mit Firmen- und Kundendaten."""
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
        c.drawRightString(MARGIN_RIGHT - 20 * mm, y, f"Seite {self.page_num}")
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

        y -= 4 * mm

        # --- EXPORT-Label ---
        if not self.inv.get("ust_enabled", False):
            c.setFont("Arial", 12)
            c.drawCentredString(PAGE_W / 2, y, "EXPORT")
        y -= 8 * mm

        # --- Lieferschein-Info & Datum ---
        c.setFont("Arial", FONT_SIZE_TITLE)
        c.drawString(MARGIN_LEFT, y, f"Lieferschein Zu Rechnung Nr.{self.inv['number']}")
        c.setFont("Arial", FONT_SIZE_TITLE)
        c.drawRightString(MARGIN_RIGHT, y, f"Datum: {self.inv['date']}")
        y -= 6 * mm

        draw_bank_footer(self.c)

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
        c.rect(MARGIN_LEFT, y - 4 * mm, MARGIN_RIGHT - MARGIN_LEFT, 7 * mm, fill=1, stroke=0)
        c.setFillColorRGB(0, 0, 0)
        
        self.current_table_start_y = y + 3 * mm

        # Obere Trennlinie
        c.setStrokeColorRGB(0.0, 0.0, 0.0)
        c.setLineWidth(0.5)
        c.line(MARGIN_LEFT, y + 3 * mm, MARGIN_RIGHT, y + 3 * mm)

        c.setFont("Arial-Bold", FONT_SIZE_SMALL)
        c.drawCentredString((COL_EAN + COL_PRODUCT) / 2, y - 1 * mm, "EAN")
        c.drawCentredString((COL_PRODUCT + COL_QTY_R - 20 * mm) / 2, y - 1 * mm, "Artikel")
        c.drawRightString(COL_QTY_R, y - 1 * mm, "Liefermenge")

        # Untere Trennlinie
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

        c.drawCentredString((COL_EAN + COL_PRODUCT) / 2, y, str(item["ean"]))

        # Produktname kürzen wenn nötig
        max_product_width = COL_QTY_R - COL_PRODUCT - 20 * mm
        product_text = truncate_text(item["product"], "Arial", FONT_SIZE_SMALL, max_product_width)
        c.drawString(COL_PRODUCT, y, product_text)

        c.drawRightString(COL_QTY_R - 5 * mm, y, str(quantity))

        y -= ROW_HEIGHT
        return y

    def _draw_summary(self, y):
        """Zeichnet die Zusammenfassung der Liefermenge."""
        c = self.c

        # Gesamtmenge berechnen
        total_quantity = sum(item["quantity"] for item in self.items)

        # Untere Linie der Tabelle
        # c.setStrokeColorRGB(0.0, 0.0, 0.0)
        # c.setLineWidth(0.5)
        # c.line(MARGIN_LEFT, y + 4 * mm, MARGIN_RIGHT, y + 4 * mm)

        y -= 6 * mm
        c.setFont("Arial", FONT_SIZE_NORMAL)
        c.drawRightString(COL_QTY_R - 5 * mm, y, str(total_quantity))
        
        y -= 10 * mm

        return y

    def _draw_footer(self, y):
        """Zeichnet Lieferbedingungen, Paletten- und Gewichtsinfos."""
        c = self.c

        c.setFont("Arial", FONT_SIZE_NORMAL)
        c.drawString(MARGIN_LEFT, y, FOOTER.get("delivery_terms", "Lieferbedinungen: EXW"))
        y -= 10 * mm

        custom_text = self.inv.get("delivery_note_text", "").strip()
        if custom_text:
            for line in custom_text.splitlines():
                if line.strip():
                    c.drawString(MARGIN_LEFT, y, line.strip())
                    y -= 6 * mm
        else:
            c.drawString(MARGIN_LEFT, y, f"Auf Pallete mit Rechnung {self.inv.get('number', '')}")
            y -= 6 * mm
            weight = self.inv.get("weight", "")
            if weight:
                c.drawString(MARGIN_LEFT, y, f"Gewicht Netto {weight}kg")

        return y


def generate_delivery_note(items, invoice_data, customer_data, output_path):
    """
    Erstellt einen PDF-Lieferschein.

    Args:
        items: Liste von dicts mit ean, product, quantity
        invoice_data: dict mit number, date, ust_enabled, weight
        customer_data: dict mit name, street, plz_city, country, vat
        output_path: Dateipfad für das PDF

    Returns:
        str: Pfad zur erstellten PDF-Datei
    """
    generator = DeliveryNoteGenerator(items, invoice_data, customer_data, output_path)
    return generator.generate()

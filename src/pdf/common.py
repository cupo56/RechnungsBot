"""
Gemeinsame Konstanten und Hilfsfunktionen für PDF-Generatoren.
"""

import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from src.config import FOOTER

# --- Seitenlayout-Konstanten (A4: 210mm x 297mm) ---
PAGE_W, PAGE_H = A4  # in Punkten (595.27, 841.89)

MARGIN_LEFT   = 20 * mm
MARGIN_RIGHT  = 190 * mm
MARGIN_TOP    = PAGE_H - 15 * mm
MARGIN_BOTTOM = 20 * mm

# Schriftgrößen
FONT_SIZE_NORMAL = 9
FONT_SIZE_SMALL  = 6
FONT_SIZE_HEADER = 10
FONT_SIZE_TITLE  = 11

ROW_HEIGHT = 6.0 * mm

_font_registered = False


def register_fonts():
    """Registriert Arial-Schriftarten für PDF-Erzeugung (einmalig)."""
    global _font_registered
    if _font_registered:
        return
    font_dir = r"C:\Windows\Fonts"
    try:
        pdfmetrics.registerFont(TTFont("Arial",      os.path.join(font_dir, "arial.ttf")))
        pdfmetrics.registerFont(TTFont("Arial-Bold", os.path.join(font_dir, "arialbd.ttf")))
        _font_registered = True
    except Exception:
        pdfmetrics.registerFontFamily("Arial", normal="Helvetica", bold="Helvetica-Bold")
        _font_registered = True


def truncate_text(text, font_name, font_size, max_width):
    """Kürzt Text mit '…' wenn er breiter als max_width ist."""
    if pdfmetrics.stringWidth(text, font_name, font_size) <= max_width:
        return text
    # Binäre Suche: O(log n) statt O(n) stringWidth-Aufrufe
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if pdfmetrics.stringWidth(text[:mid] + "...", font_name, font_size) <= max_width:
            lo = mid
        else:
            hi = mid - 1
    return (text[:lo].rstrip() + "...") if lo > 0 else "..."


def draw_bank_footer(c):
    """Zeichnet die Bankverbindung am unteren Rand der aktuellen Seite."""
    y = MARGIN_BOTTOM - 5 * mm

    c.setFont("Arial", FONT_SIZE_NORMAL)
    c.drawString(MARGIN_LEFT, y + 8 * mm, FOOTER["bank_1"])
    c.drawString(MARGIN_LEFT, y + 4 * mm, FOOTER["bank_2"])
    c.drawString(MARGIN_LEFT, y,          FOOTER["bank_3"])

    c.setFont("Arial-Bold", FONT_SIZE_TITLE)
    c.drawRightString(MARGIN_RIGHT, y + 8 * mm, FOOTER["footer_right_1"])

    c.setFont("Arial", FONT_SIZE_NORMAL)
    c.drawRightString(MARGIN_RIGHT, y + 4 * mm, FOOTER["footer_right_2"])

    footer3 = FOOTER["footer_right_3"]
    if "ATU" in footer3 and "Steuer" in footer3:
        parts      = footer3.split(" Steuer")
        text_atu   = parts[0]
        text_rest  = " Steuer" + parts[1]
        total_w    = pdfmetrics.stringWidth(text_atu + text_rest, "Arial", FONT_SIZE_NORMAL)
        start_x    = MARGIN_RIGHT - total_w
        atu_w      = pdfmetrics.stringWidth(text_atu, "Arial", FONT_SIZE_NORMAL)
        c.drawString(start_x, y, text_atu)
        c.setLineWidth(0.5)
        c.line(start_x, y - 1 * mm, start_x + atu_w, y - 1 * mm)
        c.drawString(start_x + atu_w, y, text_rest)
    else:
        c.drawRightString(MARGIN_RIGHT, y, footer3)

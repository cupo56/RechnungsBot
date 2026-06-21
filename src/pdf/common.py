"""
Gemeinsame Konstanten und Hilfsfunktionen für PDF-Generatoren.
"""

import os
import platform
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
FONT_SIZE_SMALL  = 7
FONT_SIZE_HEADER = 10
FONT_SIZE_TITLE  = 11

ROW_HEIGHT = 6.0 * mm

_font_registered = False


def _find_arial_paths():
    """Gibt (normal_pfad, bold_pfad) zurück, oder (None, None) wenn nicht gefunden."""
    system = platform.system()
    if system == "Windows":
        d = r"C:\Windows\Fonts"
        return os.path.join(d, "arial.ttf"), os.path.join(d, "arialbd.ttf")
    if system == "Darwin":
        candidates = [
            ("/System/Library/Fonts/Supplemental/Arial.ttf",      "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
            ("/Library/Fonts/Arial.ttf",                           "/Library/Fonts/Arial Bold.ttf"),
            ("/Library/Fonts/Arial.ttf",                           "/Library/Fonts/Arial_Bold.ttf"),
        ]
        for normal, bold in candidates:
            if os.path.exists(normal) and os.path.exists(bold):
                return normal, bold
    return None, None


def register_fonts():
    """Registriert Arial-Schriftarten für PDF-Erzeugung (einmalig)."""
    global _font_registered
    if _font_registered:
        return
    normal_path, bold_path = _find_arial_paths()
    try:
        if not (normal_path and os.path.exists(normal_path) and
                bold_path  and os.path.exists(bold_path)):
            raise FileNotFoundError("Arial TTF nicht gefunden")
        pdfmetrics.registerFont(TTFont("Arial",      normal_path))
        pdfmetrics.registerFont(TTFont("Arial-Bold", bold_path))
    except Exception:
        # Helvetica (eingebaut) unter den Namen "Arial"/"Arial-Bold" registrieren,
        # damit alle setFont("Arial", …)-Aufrufe weiterhin funktionieren.
        # Muss über echte Font-Objekte mit passendem .fontName laufen, nicht über
        # einen direkten Eintrag in pdfmetrics._fonts: pdfdoc.getInternalFontName()
        # registriert Fonts beim PDF-Schreiben unter ihrem eigenen .fontName
        # (z.B. "Helvetica-Bold"), nicht unter dem Dict-Key ("Arial-Bold") –
        # sonst schlägt das Rendern mit "Font 'Arial-Bold' not known!" fehl.
        pdfmetrics.registerFont(pdfmetrics.Font("Arial",      "Helvetica",      "WinAnsiEncoding"))
        pdfmetrics.registerFont(pdfmetrics.Font("Arial-Bold", "Helvetica-Bold", "WinAnsiEncoding"))
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

    return y

"""Export von Rechnungspositionen als bearbeitbare Excel-Tabelle.

Dient dem Sonderfall, dass Preise pro Position manuell auf einen ausgemachten
Betrag gesetzt werden müssen, statt über den prozentualen Aufschlag berechnet
zu werden.
"""

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

_HEADERS    = ("Stk.", "EAN", "Produkt", "Einzelpreis €", "Gesamtpreis €")
_COL_WIDTHS = (8, 16, 50, 16, 16)


def export_items_to_excel(rows, output_path):
    """Schreibt Rechnungspositionen in eine bearbeitbare .xlsx-Datei.

    `rows` ist eine Liste von (menge, ean, produkt, einzelpreis)-Tupeln.
    Die Spalte "Gesamtpreis €" wird als Formel (Menge * Einzelpreis) angelegt,
    sodass manuell angepasste Einzelpreise automatisch neu summiert werden.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Positionen"

    bold = Font(bold=True)
    for col, header in enumerate(_HEADERS, start=1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = bold
        cell.alignment = Alignment(horizontal="center")

    for row_idx, (quantity, ean, product, unit_price) in enumerate(rows, start=2):
        ws.cell(row=row_idx, column=1, value=quantity)
        ws.cell(row=row_idx, column=2, value=ean)
        ws.cell(row=row_idx, column=3, value=product)
        ws.cell(row=row_idx, column=4, value=round(unit_price, 2)).number_format = "#,##0.00"
        ws.cell(row=row_idx, column=5,
                value=f"=A{row_idx}*D{row_idx}").number_format = "#,##0.00"

    for col, width in enumerate(_COL_WIDTHS, start=1):
        ws.column_dimensions[get_column_letter(col)].width = width

    ws.freeze_panes = "A2"
    wb.save(output_path)

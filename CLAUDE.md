# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RechnungsBot is a German-language invoice and delivery note generator for "Handelsagentur Adis Sefer" (an Austrian trading agency). It reads product orders from Excel files and generates professional PDF invoices and delivery notes.

## Commands

```bash
# Run the application (use venv Python)
.venv\Scripts\python.exe main.py

# Install dependencies
.venv\Scripts\python.exe -m pip install -r requirements.txt

# Build standalone .exe (always clean-build to avoid stale cache)
Remove-Item -Recurse -Force build, dist
.venv\Scripts\python.exe -m PyInstaller RechnungsBot.spec --noconfirm
```

> **Important**: The system `python` command points to a bare Python 3.14 install that lacks all dependencies. Always use `.venv\Scripts\python.exe` explicitly.

There are no automated tests in this project.

## Architecture

The app has five layers:

**Entry point**: `main.py` creates an instance of `RechnungsBot` (from `src/gui.py`) and calls `.run()`.

**GUI** (`src/gui.py`): Single `RechnungsBot` class built with Tkinter + ttk (native `vista` theme on Windows — see "Theme Choice" below). Handles drag-and-drop Excel loading (via `tkinterdnd2`), settings persistence, customer template management, and the invoice generation workflow. Both Excel loading and PDF generation run in background threads to keep the UI responsive.

**Excel parsing** (`src/excel/parser.py`): `parse_excel(filepath)` auto-detects column headers (EAN, product, price, order quantity) from any superfeed-format Excel file. `shorten_product_name()` applies domain-specific abbreviation logic for perfume product names (removes gender suffixes, converts French fragrance terms like "Eau de Parfum" → "EdP"). All regex patterns are pre-compiled as module-level constants (`_RE_GENDER`, `_RE_COVER`, `_RE_WHITESPACE`, `_FRAGRANCE_REPLACEMENTS`) for performance.

**PDF generation** (`src/pdf/invoice.py`, `src/pdf/delivery_note.py`): `InvoiceGenerator` and `DeliveryNoteGenerator` use ReportLab canvas to render A4 PDFs directly. Both support multi-page layout with automatic page breaking. Invoices show a full item table (quantity, EAN, product, net unit price, net total) plus a netto/USt/brutto summary. Delivery notes show a simplified table plus weight/pallet info. Shared utilities (constants, `register_fonts`, `truncate_text`, `draw_bank_footer`) live in `src/pdf/common.py`.

**GiroCode / QR-Code** (`src/pdf/girocode.py`): `generate_epc_qr()` generates an EPC-compliant SEPA GiroCode QR as a PNG (in-memory `BytesIO`). The QR payload follows the EPC069-12 standard (BCD header, BIC, IBAN, amount, reference). `InvoiceGenerator._draw_girocode()` embeds the QR image into the invoice PDF below the footer text with the caption "SEPA-Überweisung via Banking-App". Toggled via `girocode_enabled` in `invoice_data` (default `True`); GUI exposes this as a "QR-Code" checkbox. Failures print a warning but do not crash generation.

**Config** (`src/config.py`): Static company data (hardcoded for Handelsagentur Adis Sefer) and footer templates. `load_config()` / `save_config()` persist runtime state (last invoice number, defaults, customer templates) to `rechnungsbot_config.json` in the working directory. `load_config()` uses `copy.deepcopy(DEFAULTS)` to guarantee full isolation of nested defaults.

## GUI Structure

The main window (`src/gui.py`) is divided into these sections (top → bottom):

| Section | Method | Description |
|---|---|---|
| Header | `_create_widgets` | Title + subtitle; "↺ Neue Excel laden" reset button (top-right, disabled until file loaded) |
| Drop zone | `_create_file_section` | Canvas-based drag-and-drop area; click to browse |
| Settings + Customer | `_create_settings_section` / `_create_customer_section` | Two-column layout |
| Action button | `_create_action_section` | "Rechnung erstellen" button (bottom-anchored) |
| Positions table | `_create_table_section` | Treeview with alternating row colors |
| Status bar | `_create_status_bar` | Status text + progress bar + "✕ Abbrechen" cancel button |

### Settings fields (left panel)

Row 0: Rechnungsnr. · Row 1: Datum · Row 2: Aufschlag % · Row 3: USt. (with % field) · Row 4: Lieferschein erstellen (with kg field) · Row 5: Lieferschein-Notiz (multiline `tk.Text`, 2 rows) · Row 6: Export-Rechnung · Row 7: QR-Code

## Key Implementation Details

- **Theme choice**: `_setup_styles()` uses ttk's native `vista` theme on Windows (OS-rendered, no image compositing). The project previously used `sv_ttk` ("Sun Valley"), but that theme draws every widget from PNG images — Tk's PNG compositing is slow enough that the window visibly lagged behind the cursor by seconds when dragging or resizing. Don't reintroduce `sv_ttk` (or other PNG/image-based ttk themes) without verifying window drag/resize stays smooth on real Windows hardware.
- **Fonts**: Arial is loaded from `C:\Windows\Fonts` (Windows-specific hardcoded path). Falls back to Helvetica if not found. PDF generation will degrade visually on non-Windows systems.
- **Currency formatting**: German locale throughout — dots as thousands separators, commas as decimal points (e.g., `€ 1 234,56`).
- **Markup & VAT**: Markup % is applied to source prices from Excel. VAT (default 20% Austrian rate) is optional and toggled per invoice. The summary section always shows the netto/USt/brutto breakdown when VAT is enabled.
- **Invoice numbering**: Auto-increments from `last_invoice_number` in config. Only incremented when an invoice is actually created (`_save_current_config(increment_nr=True)`); saving a customer template does not advance the counter.
- **Export invoices**: Toggle changes the footer text from EU VAT declarations to an export/customs declaration.
- **PDF output**: Files are saved via a save dialog and auto-opened with `os.startfile()` after generation. PDF generation runs in a background thread (`_on_pdf_complete` / `_on_pdf_error` callbacks via `root.after`).
- **Markup factor**: The `invoice_data` dict key is `markup_factor` (a multiplier, e.g. `1.15` for 15%). Items already carry the final `unit_price`; `markup_factor` is stored for reference only and never re-read inside the generators.
- **Customer templates**: Stored as named entries in `rechnungsbot_config.json` under `customer_templates`. Survive session resets.
- **GiroCode (SEPA QR-Code)**: Optional per-invoice toggle (`girocode_enabled`, default `True`). EPC-compliant QR code printed at bottom-left of the last invoice page. IBAN/BIC sourced from `FOOTER["iban"]` / `FOOTER["bic"]` in `src/config.py`. Brutto amount (netto + USt.) encoded in payload.
- **Delivery note footer text** (`delivery_note_text` in `invoice_data`): Free-text field in the GUI. If non-empty, its lines replace the default "Auf Pallete mit Rechnung …" / "Gewicht Netto …kg" lines in the delivery note footer. Persisted as `default_delivery_note_text` in config.
- **Markup field debounce**: Changes to "Aufschlag %" trigger `_populate_table()` only after 300 ms of inactivity (`_markup_debounce_id` + `root.after`) to avoid re-rendering on every keystroke.

## PDF Table Styling

Both `InvoiceGenerator` and `DeliveryNoteGenerator` share the same visual conventions. Common layout constants and utilities are in `src/pdf/common.py`; column positions specific to each document type are defined locally in each module.

- **Table border**: `setLineWidth(0.5)` — thin outer rect around the entire table
- **Header separator lines**: `setLineWidth(0.5)` — top and bottom lines of the grey header row
- **Zebra striping**: every odd row (index 1, 3, 5 …) gets a light grey fill `RGB(0.94, 0.94, 0.94)` drawn before the text
- **Column header alignment**: all headers centered with `drawCentredString` — Stk., EAN, Produkt/Artikel, Einzelpreis, Gesamtpreis, Ust.
- **EAN data cells**: centered with `drawCentredString` at the midpoint `(COL_EAN + COL_PRODUCT) / 2`
- **Row counter** (`self._row_counter`): initialized to `0` in `generate()`, incremented in `_draw_item_row()` — persists across page breaks so striping is continuous

## Page Count Estimation

Both generators use `_calculate_header_height()` + `_estimate_total_pages()` to print "Seite X von Y". Header height is computed from the actual customer fields that will be rendered (street, PLZ/Ort, Land, VAT — each only counted if non-empty). The last page reserves `75 mm` (invoice) or `50 mm` (delivery note) for the summary/footer block, matching the `min_y` check in `generate()`. Page count: `1 + ceil((n − rows_last_page) / rows_per_page)`.

## Excel Loading & Cancellation

Loading runs in a background thread. A `_load_token` (int) guards against race conditions:

- Each `_load_file()` call increments `_load_token` and captures the current value as `token`
- `_on_load_complete()` and `_on_load_error()` both check `token != self._load_token` and bail if stale
- The "✕ Abbrechen" button in the status bar calls `_cancel_load()`, which increments `_load_token` and resets the UI immediately — the thread still runs to completion but its result is discarded
- The "↺ Neue Excel laden" button (top-right) calls `_reset_session()`: clears items/table/drop-zone, increments `_load_token`, disables itself — customer templates and settings are untouched

## Drag & Drop

- `tkinterdnd2` is required. If the import fails, `HAS_DND = False` and the drop registration is skipped (click-to-browse still works).
- **Drop target is the root window** (not the canvas). Registering on `tk.Canvas` is unreliable on Windows — the OS rejects the drop before `_on_drop` is called.
- `<<DragEnter>>` returns `event.action` to signal acceptance to Windows and triggers the hover highlight.
- `_on_drop` path parsing: `event.data.strip()` first, then extracts the first path from Tk's `{braces}` format (used when path contains spaces); falls back to `split()[0]` for brace-free multi-file drops.

## Build Notes

- PyInstaller spec: `RechnungsBot.spec` — single-file exe, no console window, UPX compression enabled.
- `tkinterdnd2` DLLs are bundled via `datas` in the spec (auto-detected from the installed package path).
- Hidden imports: `tkinterdnd2`, `qrcode`, `qrcode.image.pil`, `PIL`, `PIL.Image`, `PIL.PngImagePlugin`.
- `qrcode[pil]` must be installed in the venv before building, otherwise the QR module is missing from the exe.
- Output: `dist\RechnungsBot.exe` (~22 MB). No installer needed — copy the exe next to `rechnungsbot_config.json`.
- Always delete `build\` and `dist\` before rebuilding to avoid stale cache issues.

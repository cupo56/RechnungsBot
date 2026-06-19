"""
RechnungsBot – Hauptprogramm mit GUI.
"""

import os
import sys
import subprocess
import datetime
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

from src.config import load_config, save_config
from src.excel.parser import parse_excel
from src.excel.exporter import export_items_to_excel
from src.pdf_input.parser import parse_pdf
from src.pdf.invoice import generate_invoice
from src.pdf.delivery_note import generate_delivery_note
from src.compare.gui_tab import VergleichsTab
from src.provision.gui_tab import ProvisionTab

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    HAS_DND = True
except ImportError:
    HAS_DND = False

_TABLE_DISPLAY_LIMIT = 500

# Spalten der Positionstabelle, die im Indiv.-Modus pro Zeile bearbeitbar sind:
# Spalten-ID -> (Schlüssel im items-Dict für den Override-Wert, Werttyp)
_EDITABLE_COLUMNS = {
    "stk":         ("custom_quantity",   int),
    "ean":         ("custom_ean",        str),
    "produkt":     ("custom_product",    str),
    "einzelpreis": ("custom_unit_price", float),
}

_BLUE      = "#1B6EC2"
_BLUE_DK   = "#155599"
_BLUE_DIS  = "#9BBFE0"
_GREEN     = "#1A7F3C"
_RED       = "#C0392B"
_MUTED     = "#64748B"
_DASH_CLR  = "#90BEF5"
_DROP_BG   = "#EBF3FF"
_DROP_OK   = "#F0FDF4"
_ROW_EVEN  = "#F5F7FA"


class RechnungsBot:
    """Hauptanwendung für die Rechnungserstellung."""

    def __init__(self):
        self.root = None
        global HAS_DND
        if HAS_DND:
            try:
                self.root = TkinterDnD.Tk()
            except Exception as e:
                print(f"Warnung: TkinterDnD konnte nicht geladen werden ({e}). Drag & Drop wird deaktiviert.")
                HAS_DND = False
                
        if self.root is None:
            self.root = tk.Tk()

        self.root.title("HandelsAgent – Handelsagentur Adis Sefer")
        self.root.geometry("980x920")
        self.root.minsize(860, 820)

        try:
            self.root.iconbitmap(default="")
        except Exception:
            pass

        self.items = []
        self.loaded_file = None
        self.config = load_config()
        self._load_token = 0
        self._markup_debounce_id = None
        self._cell_edit = None

        # Drop-Zone Zustand
        self._hovering   = False
        self._drop_bg    = _DROP_BG
        self._drop_icon  = "📂"
        self._drop_text  = "Excel- oder PDF-Datei hierher ziehen  oder  klicken zum Auswählen"
        self._drop_color = _MUTED

        self._setup_styles()
        self._create_widgets()
        self._load_config_to_gui()

    # ──────────────────────────────────────────────────────────────
    # Styles
    # ──────────────────────────────────────────────────────────────

    def _setup_styles(self):
        s = ttk.Style()
        if sys.platform == "win32":
            # 'vista': natives, vom Betriebssystem gerendertes Windows-Theme.
            # sv_ttk zeichnet jedes Widget aus PNG-Grafiken zusammen, was Tk beim
            # Compositing so stark ausbremst, dass das Fenster beim Verschieben
            # und Skalieren spürbar hinter dem Mauszeiger zurückbleibt.
            try:
                s.theme_use("vista")
            except tk.TclError:
                s.theme_use("clam")
            self.root.configure(bg="#fafafa")
        elif sys.platform == "darwin":
            # Natives 'aqua'-Theme behandelt Dark Mode korrekt.
            self.root.configure(bg="white")
        else:
            try:
                s.theme_use("clam")
            except tk.TclError:
                pass
            self.root.configure(bg="white")

        s.configure("Title.TLabel",   font=("Segoe UI", 18, "bold"))
        s.configure("Sub.TLabel",     font=("Segoe UI", 10), foreground=_MUTED)
        s.configure("Header.TLabel",  font=("Segoe UI", 10, "bold"))
        s.configure("Treeview",       font=("Segoe UI", 10), rowheight=28)
        s.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        s.map("Treeview",
              background=[("selected", "#DBEAFE")],
              foreground=[("selected", "#1E293B")])

    # ──────────────────────────────────────────────────────────────
    # Layout
    # ──────────────────────────────────────────────────────────────

    def _create_widgets(self):
        self._create_status_bar()

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self._tab_rechnung = ttk.Frame(self.notebook)
        self.notebook.add(self._tab_rechnung, text="  📄  RechnungsBot  ")

        tab_vergleich = ttk.Frame(self.notebook)
        self.notebook.add(tab_vergleich, text="  🔍  VergleichsBot  ")
        VergleichsTab(tab_vergleich)

        tab_provision = ttk.Frame(self.notebook)
        self.notebook.add(tab_provision, text="  💰  Provisionsrechnung  ")
        ProvisionTab(tab_provision)

        main = ttk.Frame(self._tab_rechnung, padding=(16, 12, 16, 4))
        main.pack(fill=tk.BOTH, expand=True)

        # Header
        hdr = ttk.Frame(main)
        hdr.pack(fill=tk.X, pady=(0, 8))
        self.btn_reset = tk.Button(
            hdr,
            text="↺  Neue Datei laden",
            font=("Segoe UI", 9),
            bg="#F1F5F9", fg="#1E293B",
            activebackground="#E2E8F0", activeforeground="#1E293B",
            relief="flat", bd=0, padx=10, pady=5,
            cursor="hand2",
            command=self._reset_session,
            state="disabled",
        )
        self.btn_reset.pack(side=tk.RIGHT, anchor=tk.NE)
        ttk.Label(hdr, text="RechnungsBot", style="Title.TLabel").pack(anchor=tk.W)
        ttk.Label(hdr,
                  text="Handelsagentur Adis Sefer — Rechnungen & Lieferscheine automatisch erstellen",
                  style="Sub.TLabel").pack(anchor=tk.W)
        ttk.Separator(main).pack(fill=tk.X, pady=(6, 10))

        self._create_file_section(main)

        mid = ttk.Frame(main)
        mid.pack(fill=tk.X, pady=(8, 0))
        mid.columnconfigure(0, weight=1)
        mid.columnconfigure(1, weight=1)
        self._create_settings_section(mid)
        self._create_customer_section(mid)

        self._create_action_section(main)
        self._create_table_section(main)

    # ──────────────────────────────────────────────────────────────
    # Drop-Zone
    # ──────────────────────────────────────────────────────────────

    def _create_file_section(self, parent):
        self.drop_canvas = tk.Canvas(
            parent, height=88, highlightthickness=0, cursor="hand2"
        )
        self.drop_canvas.pack(fill=tk.X)

        # Persistente Canvas-Items erstellen (werden nie gelöscht, nur aktualisiert)
        c = self.drop_canvas
        self._drop_bg_id     = c.create_rectangle(0, 0, 1, 1, fill=self._drop_bg, outline="")
        self._drop_border_id = c.create_rectangle(4, 4, 1, 1, fill="",
                                                   outline=_DASH_CLR, width=2, dash=(9, 5))
        self._drop_icon_id   = c.create_text(0, 0, text=self._drop_icon,
                                              font=("Segoe UI", 20), fill=self._drop_color)
        self._drop_text_id   = c.create_text(0, 0, text=self._drop_text,
                                              font=("Segoe UI", 10), fill=self._drop_color)

        self.drop_canvas.bind("<Configure>", lambda e: self._redraw_drop())
        self.drop_canvas.bind("<Button-1>",  lambda e: self._browse_file())
        self.drop_canvas.bind("<Enter>",     lambda e: self._set_hover(True))
        self.drop_canvas.bind("<Leave>",     lambda e: self._set_hover(False))

        if HAS_DND:
            # Root-Fenster als Drop-Target: zuverlässiger als Canvas auf Windows
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind("<<Drop>>",      self._on_drop)
            self.root.dnd_bind("<<DragEnter>>", self._on_drag_enter)
            self.root.dnd_bind("<<DragLeave>>", lambda e: self._set_hover(False))

    def _redraw_drop(self):
        c = self.drop_canvas
        w, h = c.winfo_width(), c.winfo_height()
        if w < 20:
            return
        # Positionen und Eigenschaften der bestehenden Items aktualisieren
        c.coords(self._drop_bg_id, 0, 0, w, h)
        c.itemconfig(self._drop_bg_id, fill=self._drop_bg)
        border = _BLUE if self._hovering else _DASH_CLR
        c.coords(self._drop_border_id, 4, 4, w - 4, h - 4)
        c.itemconfig(self._drop_border_id, outline=border)
        c.coords(self._drop_icon_id, w // 2, h // 2 - 14)
        c.itemconfig(self._drop_icon_id, text=self._drop_icon, fill=self._drop_color)
        c.coords(self._drop_text_id, w // 2, h // 2 + 16)
        c.itemconfig(self._drop_text_id, text=self._drop_text, fill=self._drop_color)

    def _set_hover(self, on: bool):
        self._hovering = on
        self._redraw_drop()

    def _browse_file(self):
        path = filedialog.askopenfilename(
            title="Datei auswählen",
            filetypes=[
                ("Unterstützte Dateien", "*.xlsx *.xls *.pdf"),
                ("Excel-Dateien", "*.xlsx *.xls"),
                ("PDF-Dateien", "*.pdf"),
                ("Alle Dateien", "*.*"),
            ],
        )
        if path:
            self._load_file(path)

    def _on_drag_enter(self, event):
        if self.notebook.index(self.notebook.select()) == 0:
            self._set_hover(True)
        return event.action

    def _on_drop(self, event):
        if self.notebook.index(self.notebook.select()) != 0:
            return
        raw = event.data.strip()
        # Tk wraps paths with spaces in {braces}; extract the first path only
        if raw.startswith("{"):
            try:
                path = raw[1:raw.index("}")]
            except ValueError:
                path = raw[1:]
        else:
            # No braces: single path or space-separated multiple paths → take first
            path = raw.split()[0] if raw else ""
        path = path.strip()
        if path.lower().endswith((".xlsx", ".xls", ".pdf")):
            self._load_file(path)
        else:
            self._set_status("Bitte eine Excel- (.xlsx) oder PDF-Datei laden.", error=True)

    def _load_file(self, filepath):
        self._load_token += 1
        token = self._load_token
        is_pdf = filepath.lower().endswith(".pdf")
        status_msg = "PDF wird eingelesen…" if is_pdf else "Excel wird eingelesen…"
        self._set_status(status_msg)
        self._show_progress(True)
        self._drop_icon  = "⏳"
        self._drop_text  = "Datei wird geladen…"
        self._drop_color = _MUTED
        self._drop_bg    = _DROP_BG
        self._redraw_drop()

        def _thread():
            try:
                items = parse_pdf(filepath) if is_pdf else parse_excel(filepath)
                self.root.after(0, lambda: self._on_load_complete(filepath, items, token))
            except ValueError as e:
                msg = str(e)
                self.root.after(0, lambda: self._on_load_error(msg, True, token))
            except Exception as e:
                msg = str(e)
                self.root.after(0, lambda: self._on_load_error(msg, False, token))

        threading.Thread(target=_thread, daemon=True).start()

    def _on_load_complete(self, filepath, items, token):
        if token != self._load_token:
            return
        self._show_progress(False)
        self.items = items
        self.var_select_all_individual.set(False)
        self.loaded_file = filepath
        name = os.path.basename(filepath)
        self._drop_icon  = "✅"
        self._drop_text  = f"{name}   ·   {len(items)} Positionen geladen"
        self._drop_color = _GREEN
        self._drop_bg    = _DROP_OK
        self._redraw_drop()
        self._populate_table()
        self._set_status(f"{len(items)} Positionen aus '{name}' geladen.")
        self.btn_reset.configure(state="normal")

    def _reset_session(self):
        self.items = []
        self.var_select_all_individual.set(False)
        self.loaded_file = None
        self._load_token += 1
        self._drop_icon  = "📂"
        self._drop_text  = "Excel- oder PDF-Datei hierher ziehen  oder  klicken zum Auswählen"
        self._drop_color = _MUTED
        self._drop_bg    = _DROP_BG
        self._redraw_drop()
        self.tree.delete(*self.tree.get_children())
        self.total_label.configure(text="")
        self.btn_reset.configure(state="disabled")
        self._set_status("Bereit – Excel-Datei laden um zu beginnen.")

    def _on_load_error(self, error_msg, is_value_error, token):
        if token != self._load_token:
            return
        self._show_progress(False)
        self._drop_icon  = "📂"
        self._drop_text  = "Excel- oder PDF-Datei hierher ziehen  oder  klicken zum Auswählen"
        self._drop_color = _MUTED
        self._drop_bg    = _DROP_BG
        self._redraw_drop()
        title = "Fehler beim Einlesen" if is_value_error else "Fehler"
        msg   = error_msg if is_value_error else f"Unerwarteter Fehler:\n{error_msg}"
        messagebox.showerror(title, msg)
        self._set_status("Fehler beim Einlesen der Datei.", error=True)

    # ──────────────────────────────────────────────────────────────
    # Einstellungen
    # ──────────────────────────────────────────────────────────────

    def _create_settings_section(self, parent):
        frame = ttk.LabelFrame(parent, text="  Rechnungseinstellungen  ", padding=(12, 10))
        frame.grid(row=0, column=0, sticky=tk.NSEW, padx=(0, 5), pady=(0, 6))
        frame.columnconfigure(1, weight=1)

        def entry_row(label, var, row, width=16):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky=tk.W, pady=3)
            e = ttk.Entry(frame, textvariable=var, width=width)
            e.grid(row=row, column=1, sticky=tk.W, padx=(8, 0), pady=3)
            return e

        self.var_invoice_nr = tk.StringVar()
        entry_row("Rechnungsnr.:", self.var_invoice_nr, 0)

        self.var_date = tk.StringVar(value=datetime.date.today().strftime("%d.%m.%Y"))
        entry_row("Datum:", self.var_date, 1)

        self.var_markup = tk.StringVar(value="0.0")
        entry_row("Aufschlag %:", self.var_markup, 2)
        self.var_markup.trace_add("write", lambda *_: self._on_markup_changed())

        # USt.
        self.var_ust_enabled = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, text="USt. berechnen",
                        variable=self.var_ust_enabled,
                        command=self._on_ust_toggled).grid(row=3, column=0, sticky=tk.W, pady=3)
        ust_row = ttk.Frame(frame)
        ust_row.grid(row=3, column=1, sticky=tk.W, padx=(8, 0), pady=3)
        self.var_ust_percent = tk.StringVar(value="20.0")
        self.ust_entry = ttk.Entry(ust_row, textvariable=self.var_ust_percent,
                                   width=7, state="disabled")
        self.ust_entry.pack(side=tk.LEFT)
        ttk.Label(ust_row, text=" %").pack(side=tk.LEFT)

        # Lieferschein
        self.var_delivery_note = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, text="Lieferschein erstellen",
                        variable=self.var_delivery_note,
                        command=self._on_delivery_toggled).grid(row=4, column=0, sticky=tk.W, pady=3)
        dlv_row = ttk.Frame(frame)
        dlv_row.grid(row=4, column=1, sticky=tk.W, padx=(8, 0), pady=3)
        self.var_weight = tk.StringVar(value="")
        self.weight_entry = ttk.Entry(dlv_row, textvariable=self.var_weight,
                                      width=7, state="disabled")
        self.weight_entry.pack(side=tk.LEFT)
        ttk.Label(dlv_row, text=" kg").pack(side=tk.LEFT)

        # Lieferschein-Notiztext
        ttk.Label(frame, text="Lieferschein-Notiz:").grid(row=5, column=0, sticky=tk.NW, pady=(4, 0))
        self.delivery_note_text = tk.Text(
            frame, height=2, width=28, state="disabled",
            font=("Segoe UI", 9), relief="solid", bd=1, wrap="word",
        )
        self.delivery_note_text.grid(row=5, column=1, sticky=tk.EW, padx=(8, 0), pady=(4, 2))

        # Export
        self.var_is_export = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, text="Export-Rechnung",
                        variable=self.var_is_export).grid(row=6, column=0, sticky=tk.W, pady=3)

        # GiroCode QR-Code
        self.var_girocode_enabled = tk.BooleanVar(value=True)
        ttk.Checkbutton(frame, text="QR-Code",
                        variable=self.var_girocode_enabled).grid(row=7, column=0, sticky=tk.W, pady=3)

        # Rechnungs-Notiztext (ersetzt bei Eingabe den Standard-Footer-Text der Rechnung)
        ttk.Label(frame, text="Rechnungs-Notiz:").grid(row=8, column=0, sticky=tk.NW, pady=(4, 0))
        self.invoice_note_text = tk.Text(
            frame, height=2, width=28,
            font=("Segoe UI", 9), relief="solid", bd=1, wrap="word",
        )
        self.invoice_note_text.grid(row=8, column=1, sticky=tk.EW, padx=(8, 0), pady=(4, 2))

    def _on_delivery_toggled(self):
        state = "normal" if self.var_delivery_note.get() else "disabled"
        self.weight_entry.configure(state=state)
        self.delivery_note_text.configure(state=state)

    def _on_ust_toggled(self):
        self.ust_entry.configure(
            state="normal" if self.var_ust_enabled.get() else "disabled")
        self._update_total_label()

    def _on_markup_changed(self):
        if self._markup_debounce_id is not None:
            self.root.after_cancel(self._markup_debounce_id)
        self._markup_debounce_id = self.root.after(300, self._apply_markup_change)

    def _apply_markup_change(self):
        self._markup_debounce_id = None
        if self.items:
            self._populate_table()

    # ──────────────────────────────────────────────────────────────
    # Kundendaten
    # ──────────────────────────────────────────────────────────────

    def _create_customer_section(self, parent):
        frame = ttk.LabelFrame(parent, text="  Kundenadresse  ", padding=(12, 10))
        frame.grid(row=0, column=1, sticky=tk.NSEW, padx=(5, 0), pady=(0, 6))
        frame.columnconfigure(1, weight=1)

        # Vorlagen-Leiste
        tpl = ttk.Frame(frame)
        tpl.grid(row=0, column=0, columnspan=2, sticky=tk.EW, pady=(0, 8))
        ttk.Label(tpl, text="Vorlage:").pack(side=tk.LEFT)
        self.var_template = tk.StringVar()
        self.cb_templates = ttk.Combobox(tpl, textvariable=self.var_template,
                                         state="readonly", width=17)
        self.cb_templates.pack(side=tk.LEFT, padx=(5, 4))
        self.cb_templates.bind("<<ComboboxSelected>>", self._on_template_selected)
        ttk.Button(tpl, text="💾 Speichern",
                   command=self._save_template, width=12).pack(side=tk.LEFT, padx=(0, 3))
        ttk.Button(tpl, text="🗑", command=self._delete_template, width=3).pack(side=tk.LEFT)

        for i, (lbl, var_name) in enumerate([
            ("Firma:",     "var_cust_name"),
            ("Straße:",    "var_cust_street"),
            ("PLZ / Ort:", "var_cust_plz"),
            ("Land:",      "var_cust_country"),
            ("VAT-Nr.:",   "var_cust_vat"),
        ]):
            ttk.Label(frame, text=lbl).grid(row=i + 1, column=0, sticky=tk.W, pady=3)
            var = tk.StringVar()
            setattr(self, var_name, var)
            ttk.Entry(frame, textvariable=var).grid(
                row=i + 1, column=1, sticky=tk.EW, padx=(8, 0), pady=3)

    def _update_template_combobox(self):
        names = list(self.config.get("customer_templates", {}).keys())
        self.cb_templates["values"] = names
        if self.var_template.get() not in names:
            self.var_template.set("")

    def _on_template_selected(self, _=None):
        name = self.var_template.get()
        tpl  = self.config.get("customer_templates", {}).get(name, {})
        self.var_cust_name.set(tpl.get("name", ""))
        self.var_cust_street.set(tpl.get("street", ""))
        self.var_cust_plz.set(tpl.get("plz_city", ""))
        self.var_cust_country.set(tpl.get("country", ""))
        self.var_cust_vat.set(tpl.get("vat", ""))

    def _save_template(self):
        tpl_name = simpledialog.askstring(
            "Vorlage speichern", "Name für diese Vorlage:",
            initialvalue=self.var_cust_name.get().strip(), parent=self.root)
        if not tpl_name or not tpl_name.strip():
            return
        tpl_name = tpl_name.strip()
        self.config.setdefault("customer_templates", {})[tpl_name] = {
            "name":     self.var_cust_name.get().strip(),
            "street":   self.var_cust_street.get().strip(),
            "plz_city": self.var_cust_plz.get().strip(),
            "country":  self.var_cust_country.get().strip(),
            "vat":      self.var_cust_vat.get().strip(),
        }
        self._save_current_config()
        self._update_template_combobox()
        self.var_template.set(tpl_name)
        self._set_status(f"Vorlage '{tpl_name}' gespeichert.")

    def _delete_template(self):
        name = self.var_template.get()
        if not name:
            messagebox.showwarning("Keine Vorlage", "Bitte zuerst eine Vorlage auswählen.")
            return
        if messagebox.askyesno("Löschen", f"Vorlage '{name}' wirklich löschen?"):
            self.config.get("customer_templates", {}).pop(name, None)
            self._save_current_config()
            self._update_template_combobox()
            self.var_template.set("")
            self._set_status(f"Vorlage '{name}' gelöscht.")

    # ──────────────────────────────────────────────────────────────
    # Positionstabelle
    # ──────────────────────────────────────────────────────────────

    def _create_table_section(self, parent):
        total_row = ttk.Frame(parent)
        total_row.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 2))
        self.total_label = ttk.Label(total_row, text="", style="Header.TLabel")
        self.total_label.pack(side=tk.RIGHT, padx=4)

        self.btn_add_row = ttk.Button(
            total_row, text="➕ Neue Zeile hinzufügen", command=self._add_manual_row,
        )
        self.btn_add_row.pack(side=tk.LEFT, padx=4)

        frame = ttk.LabelFrame(parent, text="  Positionen  ", padding=(6, 6))
        frame.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        self.var_select_all_individual = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            frame, text="Alle Positionen individuell bearbeiten",
            variable=self.var_select_all_individual,
            command=self._on_select_all_individual_toggled,
        ).pack(anchor=tk.W)

        ttk.Label(
            frame,
            text="„Indiv.“ ankreuzen, um Stk., EAN, Produktname und Einzelpreis dieser Position "
                 "manuell zu bearbeiten (Klick auf die jeweilige Zelle). Mit 🗑 lässt sich "
                 "eine Position entfernen.",
            foreground=_MUTED, font=("Segoe UI", 8), wraplength=600, justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(0, 4))

        cols = ("stk", "ean", "produkt", "indiv", "einzelpreis", "gesamtpreis", "delete")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings",
                                 height=12, selectmode="browse")

        self.tree.heading("stk",         text="Stk.",           anchor=tk.CENTER)
        self.tree.heading("ean",         text="EAN",            anchor=tk.W)
        self.tree.heading("produkt",     text="Produkt",        anchor=tk.W)
        self.tree.heading("indiv",       text="Indiv.",         anchor=tk.CENTER)
        self.tree.heading("einzelpreis", text="Einzelpreis €",  anchor=tk.E)
        self.tree.heading("gesamtpreis", text="Gesamtpreis €",  anchor=tk.E)
        self.tree.heading("delete",      text="",               anchor=tk.CENTER)

        self.tree.column("stk",         width=50,  anchor=tk.CENTER, minwidth=40,  stretch=False)
        self.tree.column("ean",         width=120, anchor=tk.W,      minwidth=100, stretch=False)
        self.tree.column("produkt",     width=0,   anchor=tk.W,      minwidth=160)
        self.tree.column("indiv",       width=55,  anchor=tk.CENTER, minwidth=50,  stretch=False)
        self.tree.column("einzelpreis", width=105, anchor=tk.E,      minwidth=90,  stretch=False)
        self.tree.column("gesamtpreis", width=115, anchor=tk.E,      minwidth=90,  stretch=False)
        self.tree.column("delete",      width=36,  anchor=tk.CENTER, minwidth=36,  stretch=False)

        self.tree.tag_configure("even", background=_ROW_EVEN)
        self.tree.bind("<Button-1>", self._on_tree_click)

        sb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

    def _populate_table(self):
        self._cancel_cell_edit()
        self.tree.delete(*self.tree.get_children())
        markup = self._get_markup_factor()
        for i, item in enumerate(self.items[:_TABLE_DISPLAY_LIMIT]):
            ean, qty, product, unit = self._effective_values(item, markup)
            total = qty * unit
            checkbox = "☑" if item.get("individual") else "☐"
            self.tree.insert("", tk.END, values=(
                qty, ean, product, checkbox,
                f"{unit:.2f}", f"{total:.2f}", "🗑",
            ), tags=("even",) if i % 2 == 0 else ())
        self._update_total_label()

    def _effective_values(self, item, markup):
        if item.get("individual"):
            ean     = item.get("custom_ean", item["ean"])
            qty     = item.get("custom_quantity", item["quantity"])
            product = item.get("custom_product", item["product"])
            unit    = item.get("custom_unit_price")
            if unit is None:
                unit = item["source_price"] * markup
            return ean, qty, product, unit
        return item["ean"], item["quantity"], item["product"], item["source_price"] * markup

    def _on_tree_click(self, event):
        if self.tree.identify_region(event.x, event.y) != "cell":
            return
        # Offene Zelleneditierung zuerst übernehmen — das baut die Tabelle neu auf
        # (neue Zeilen-IDs), daher muss row_id erst danach ermittelt werden.
        self._commit_cell_edit()
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return
        col_id = self._column_id_at(event.x)
        if col_id is None:
            return
        index = self.tree.index(row_id)
        item  = self.items[index]

        if col_id == "indiv":
            self._toggle_individual(row_id)
        elif col_id == "delete":
            self._delete_item(row_id)
        elif col_id in _EDITABLE_COLUMNS and item.get("individual"):
            self._start_cell_edit(row_id, col_id)

    def _column_id_at(self, x):
        col = self.tree.identify_column(x)
        try:
            idx = int(col[1:]) - 1
        except ValueError:
            return None
        cols = self.tree["columns"]
        return cols[idx] if 0 <= idx < len(cols) else None

    def _toggle_individual(self, row_id):
        self._commit_cell_edit()
        index = self.tree.index(row_id)
        item  = self.items[index]
        if item.get("manual"):
            return  # manuell hinzugefügte Zeilen bleiben immer individuell editierbar
        if item.get("individual"):
            item["individual"] = False
        else:
            self._activate_individual(item, self._get_markup_factor())
        self._populate_table()

    def _add_manual_row(self):
        """Fügt eine leere, manuell editierbare Position am Ende der Tabelle hinzu."""
        self._commit_cell_edit()
        item = {
            "ean":               "",
            "product":           "Neue Position",
            "quantity":          1,
            "source_price":      0.0,
            "individual":        True,
            "manual":            True,
            "custom_quantity":   1,
            "custom_ean":        "",
            "custom_product":    "Neue Position",
            "custom_unit_price": 0.0,
        }
        self.items.append(item)
        self._populate_table()

        children = self.tree.get_children()
        if children:
            row_id = children[-1]
            self.tree.see(row_id)
            self._start_cell_edit(row_id, "produkt")

    def _activate_individual(self, item, markup):
        item["individual"] = True
        item.setdefault("custom_quantity", item["quantity"])
        item.setdefault("custom_ean", item["ean"])
        item.setdefault("custom_product", item["product"])
        item.setdefault("custom_unit_price", round(item["source_price"] * markup, 2))

    def _on_select_all_individual_toggled(self):
        self._commit_cell_edit()
        enable = self.var_select_all_individual.get()
        markup = self._get_markup_factor()
        for item in self.items:
            if item.get("manual"):
                continue  # manuell hinzugefügte Zeilen bleiben immer individuell editierbar
            if enable:
                self._activate_individual(item, markup)
            else:
                item["individual"] = False
        self._populate_table()

    def _delete_item(self, row_id):
        self._commit_cell_edit()
        index = self.tree.index(row_id)
        item  = self.items[index]
        name  = item.get("custom_product", item["product"])
        if not messagebox.askyesno("Position entfernen",
                                   f"Soll die Position „{name}“ wirklich entfernt werden?"):
            return
        del self.items[index]
        self._populate_table()

    def _start_cell_edit(self, row_id, col_id):
        self._commit_cell_edit()
        bbox = self.tree.bbox(row_id, col_id)
        if not bbox:
            return
        x, y, width, height = bbox
        index = self.tree.index(row_id)
        field_key, value_type = _EDITABLE_COLUMNS[col_id]
        current = self.items[index][field_key]

        if value_type is float:
            text, justify = f"{current:.2f}".replace(".", ","), tk.RIGHT
        elif value_type is int:
            text, justify = str(current), tk.CENTER
        else:
            text, justify = str(current), tk.LEFT

        var   = tk.StringVar(value=text)
        entry = ttk.Entry(self.tree, textvariable=var, justify=justify)
        entry.place(x=x, y=y, width=width, height=height)
        entry.focus_set()
        entry.select_range(0, tk.END)

        self._cell_edit = (index, field_key, value_type, entry, var)
        entry.bind("<Return>",   lambda e: self._commit_cell_edit())
        entry.bind("<KP_Enter>", lambda e: self._commit_cell_edit())
        entry.bind("<Escape>",   lambda e: self._cancel_cell_edit())
        entry.bind("<FocusOut>", lambda e: self._commit_cell_edit())

    def _commit_cell_edit(self):
        if not self._cell_edit:
            return
        index, field_key, value_type, entry, var = self._cell_edit
        self._cell_edit = None
        raw = var.get().strip()
        entry.destroy()

        if value_type is str:
            if field_key == "custom_product" and not raw:
                messagebox.showwarning("Ungültiger Wert", "Der Produktname darf nicht leer sein.")
                return
            self.items[index][field_key] = raw
        elif value_type is int:
            try:
                value = int(float(raw.replace(",", ".")))
            except ValueError:
                messagebox.showwarning("Ungültiger Wert", f"'{raw}' ist keine gültige Stückzahl.")
                return
            if value <= 0:
                messagebox.showwarning("Ungültiger Wert", "Die Stückzahl muss größer als 0 sein.")
                return
            self.items[index][field_key] = value
        else:
            try:
                value = float(raw.replace(",", "."))
            except ValueError:
                messagebox.showwarning("Ungültiger Preis", f"'{raw}' ist kein gültiger Preis.")
                return
            if value < 0:
                messagebox.showwarning("Ungültiger Preis", "Der Preis darf nicht negativ sein.")
                return
            self.items[index][field_key] = value

        self._populate_table()

    def _cancel_cell_edit(self):
        if not self._cell_edit:
            return
        _, _, _, entry, _ = self._cell_edit
        self._cell_edit = None
        entry.destroy()

    def _update_total_label(self):
        markup = self._get_markup_factor()
        netto  = sum(qty * unit for _, qty, _, unit in
                     (self._effective_values(it, markup) for it in self.items))
        n = len(self.items)
        prefix = f"Zeige {_TABLE_DISPLAY_LIMIT} von {n}  ·  " if n > _TABLE_DISPLAY_LIMIT else ""
        if self.var_ust_enabled.get():
            try:
                pct = float(self.var_ust_percent.get().replace(",", "."))
            except ValueError:
                pct = 0
            ust = netto * pct / 100
            self.total_label.configure(
                text=f"{prefix}Netto: {netto:,.2f} €    USt. {pct:.0f}%: {ust:,.2f} €"
                     f"    Brutto: {netto + ust:,.2f} €"
            )
        else:
            self.total_label.configure(
                text=f"{prefix}Gesamtsumme Netto: {netto:,.2f} €" if (netto or prefix) else "")

    def _get_markup_factor(self):
        try:
            return 1 + float(self.var_markup.get().replace(",", ".")) / 100
        except ValueError:
            return 1.0

    # ──────────────────────────────────────────────────────────────
    # Aktions-Button
    # ──────────────────────────────────────────────────────────────

    def _create_action_section(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=(4, 0), side=tk.BOTTOM)

        btn_row = ttk.Frame(frame)
        btn_row.pack(pady=6)

        self.btn_create = tk.Button(
            btn_row,
            text="   📄  Rechnung erstellen   ",
            font=("Segoe UI", 12, "bold"),
            bg=_BLUE, fg="#FFFFFF",
            activebackground=_BLUE_DK, activeforeground="#FFFFFF",
            relief="flat", bd=0,
            padx=20, pady=11,
            cursor="hand2",
            command=self._create_invoice,
        )
        self.btn_create.pack(side=tk.LEFT)

        self.btn_export_excel = tk.Button(
            btn_row,
            text="   📊  Als Excel exportieren   ",
            font=("Segoe UI", 10),
            bg="#F1F5F9", fg="#1E293B",
            activebackground="#E2E8F0", activeforeground="#1E293B",
            relief="flat", bd=0,
            padx=14, pady=11,
            cursor="hand2",
            command=self._export_excel,
        )
        self.btn_export_excel.pack(side=tk.LEFT, padx=(10, 0))

        self.btn_delivery_note_only = tk.Button(
            btn_row,
            text="   📦  Nur Lieferschein erstellen   ",
            font=("Segoe UI", 10),
            bg="#F1F5F9", fg="#1E293B",
            activebackground="#E2E8F0", activeforeground="#1E293B",
            relief="flat", bd=0,
            padx=14, pady=11,
            cursor="hand2",
            command=self._create_delivery_note_only,
        )
        self.btn_delivery_note_only.pack(side=tk.LEFT, padx=(10, 0))

    def _collect_invoice_data(self):
        """Liest und validiert die GUI-Felder. Gibt (invoice_items, invoice_data,
        customer_data) zurück oder None, wenn die Validierung fehlschlägt
        (eine Warnmeldung wird dabei bereits angezeigt)."""
        if not self.items:
            messagebox.showwarning("Keine Daten", "Bitte zuerst eine Excel-Datei laden.")
            return None

        invoice_nr = self.var_invoice_nr.get().strip()
        if not invoice_nr:
            messagebox.showwarning("Rechnungsnummer fehlt", "Bitte eine Rechnungsnummer eingeben.")
            return None

        invoice_date = self.var_date.get().strip()
        if not invoice_date:
            messagebox.showwarning("Datum fehlt", "Bitte ein Rechnungsdatum eingeben.")
            return None

        cust_name = self.var_cust_name.get().strip()
        if not cust_name:
            messagebox.showwarning("Kunde fehlt", "Bitte den Firmennamen des Kunden eingeben.")
            return None

        markup        = self._get_markup_factor()
        invoice_items = []
        for it in self.items:
            ean, qty, product, unit = self._effective_values(it, markup)
            invoice_items.append({"ean": ean, "product": product,
                                  "quantity": qty, "unit_price": unit})

        ust_enabled = self.var_ust_enabled.get()
        try:
            ust_percent = float(self.var_ust_percent.get().replace(",", ".")) if ust_enabled else 0
        except ValueError:
            ust_percent = 0

        invoice_data = {
            "number":               invoice_nr,
            "date":                 invoice_date,
            "markup_factor":        markup,
            "ust_enabled":          ust_enabled,
            "ust_percent":          ust_percent,
            "is_export":            self.var_is_export.get(),
            "girocode_enabled":     self.var_girocode_enabled.get(),
            "weight":               self.var_weight.get().strip(),
            "delivery_note_text":   self.delivery_note_text.get("1.0", tk.END).strip(),
            "invoice_note_text":    self.invoice_note_text.get("1.0", tk.END).strip(),
        }
        customer_data = {
            "name":     cust_name,
            "street":   self.var_cust_street.get().strip(),
            "plz_city": self.var_cust_plz.get().strip(),
            "country":  self.var_cust_country.get().strip(),
            "vat":      self.var_cust_vat.get().strip(),
        }
        return invoice_items, invoice_data, customer_data

    def _create_invoice(self):
        collected = self._collect_invoice_data()
        if collected is None:
            return
        invoice_items, invoice_data, customer_data = collected
        invoice_nr = invoice_data["number"]

        default_name = f"Rechnung_{invoice_nr.replace('/', '_')}.pdf"
        output_path  = filedialog.asksaveasfilename(
            title="Rechnung speichern als",
            defaultextension=".pdf",
            filetypes=[("PDF-Dateien", "*.pdf")],
            initialfile=default_name,
        )
        if not output_path:
            return

        # Lieferschein-Pfad im Main-Thread bestimmen
        dlv_path = None
        if self.var_delivery_note.get():
            d, f = os.path.dirname(output_path), os.path.basename(output_path)
            dlv_name = (f.replace("Rechnung_", "Lieferschein_", 1)
                        if f.startswith("Rechnung_") else f"Lieferschein_{f}")
            dlv_path = os.path.join(d, dlv_name)

        self._set_status("Rechnung wird erstellt…")
        self._show_progress(True, show_cancel=False)
        self.btn_create.configure(state="disabled", bg=_BLUE_DIS, cursor="arrow")
        self.btn_delivery_note_only.configure(state="disabled")

        def _thread():
            try:
                generate_invoice(invoice_items, invoice_data, customer_data, output_path)
                if dlv_path:
                    generate_delivery_note(invoice_items, invoice_data, customer_data, dlv_path)
                self.root.after(0, lambda: self._on_pdf_complete(output_path, dlv_path))
            except Exception as e:
                err = str(e)
                self.root.after(0, lambda: self._on_pdf_error(err))

        threading.Thread(target=_thread, daemon=True).start()

    def _on_pdf_complete(self, output_path, dlv_path):
        self._show_progress(False)
        self.btn_create.configure(state="normal", bg=_BLUE, cursor="hand2")
        self.btn_delivery_note_only.configure(state="normal")
        msg = f"Rechnung gespeichert: {os.path.basename(output_path)}"
        if dlv_path:
            msg += f" | Lieferschein: {os.path.basename(dlv_path)}"
        self._save_current_config(increment_nr=True)
        self._set_status(msg)
        messagebox.showinfo("Erfolgreich erstellt", f"Erfolgreich erstellt:\n\n{msg}")
        self._open_file(output_path)
        if dlv_path:
            self._open_file(dlv_path)

    def _create_delivery_note_only(self):
        collected = self._collect_invoice_data()
        if collected is None:
            return
        invoice_items, invoice_data, customer_data = collected
        invoice_nr = invoice_data["number"]

        default_name = f"Lieferschein_{invoice_nr.replace('/', '_')}.pdf"
        output_path  = filedialog.asksaveasfilename(
            title="Lieferschein speichern als",
            defaultextension=".pdf",
            filetypes=[("PDF-Dateien", "*.pdf")],
            initialfile=default_name,
        )
        if not output_path:
            return

        self._set_status("Lieferschein wird erstellt…")
        self._show_progress(True, show_cancel=False)
        self.btn_create.configure(state="disabled", bg=_BLUE_DIS, cursor="arrow")
        self.btn_delivery_note_only.configure(state="disabled")

        def _thread():
            try:
                generate_delivery_note(invoice_items, invoice_data, customer_data, output_path)
                self.root.after(0, lambda: self._on_delivery_note_complete(output_path))
            except Exception as e:
                err = str(e)
                self.root.after(0, lambda: self._on_delivery_note_error(err))

        threading.Thread(target=_thread, daemon=True).start()

    def _on_delivery_note_complete(self, output_path):
        self._show_progress(False)
        self.btn_create.configure(state="normal", bg=_BLUE, cursor="hand2")
        self.btn_delivery_note_only.configure(state="normal")
        msg = f"Lieferschein gespeichert: {os.path.basename(output_path)}"
        self._set_status(msg)
        messagebox.showinfo("Erfolgreich erstellt", f"Erfolgreich erstellt:\n\n{msg}")
        self._open_file(output_path)

    def _on_delivery_note_error(self, error_msg):
        self._show_progress(False)
        self.btn_create.configure(state="normal", bg=_BLUE, cursor="hand2")
        self.btn_delivery_note_only.configure(state="normal")
        messagebox.showerror("Fehler", f"Fehler bei der Lieferschein-Erstellung:\n\n{error_msg}")
        self._set_status("Fehler bei der Erstellung.", error=True)

    def _open_file(self, filepath):
        if sys.platform == "win32":
            os.startfile(filepath)
        elif sys.platform == "darwin":
            subprocess.call(["open", filepath])
        else:
            subprocess.call(["xdg-open", filepath])

    def _on_pdf_error(self, error_msg):
        self._show_progress(False)
        self.btn_create.configure(state="normal", bg=_BLUE, cursor="hand2")
        self.btn_delivery_note_only.configure(state="normal")
        messagebox.showerror("Fehler", f"Fehler bei der Rechnungserstellung:\n\n{error_msg}")
        self._set_status("Fehler bei der Erstellung.", error=True)

    def _export_excel(self):
        if not self.items:
            messagebox.showwarning("Keine Daten", "Bitte zuerst eine Excel-Datei laden.")
            return

        invoice_nr   = self.var_invoice_nr.get().strip()
        default_name = f"Rechnung_{invoice_nr.replace('/', '_')}.xlsx" if invoice_nr else "Rechnung.xlsx"
        output_path  = filedialog.asksaveasfilename(
            title="Positionen als Excel exportieren",
            defaultextension=".xlsx",
            filetypes=[("Excel-Dateien", "*.xlsx")],
            initialfile=default_name,
        )
        if not output_path:
            return

        markup = self._get_markup_factor()
        invoice_items = []
        for it in self.items:
            ean, qty, product, unit = self._effective_values(it, markup)
            invoice_items.append({"ean": ean, "product": product,
                                  "quantity": qty, "unit_price": unit})

        ust_enabled = self.var_ust_enabled.get()
        try:
            ust_percent = float(self.var_ust_percent.get().replace(",", ".")) if ust_enabled else 0
        except ValueError:
            ust_percent = 0

        invoice_data = {
            "number":      invoice_nr,
            "date":        self.var_date.get().strip(),
            "ust_enabled": ust_enabled,
            "ust_percent": ust_percent,
            "is_export":   self.var_is_export.get(),
        }
        customer_data = {
            "name":     self.var_cust_name.get().strip(),
            "street":   self.var_cust_street.get().strip(),
            "plz_city": self.var_cust_plz.get().strip(),
            "country":  self.var_cust_country.get().strip(),
            "vat":      self.var_cust_vat.get().strip(),
        }

        self._set_status("Excel-Datei wird erstellt…")
        self._show_progress(True, show_cancel=False)
        self.btn_export_excel.configure(state="disabled", cursor="arrow")

        def _thread():
            try:
                export_items_to_excel(invoice_items, invoice_data, customer_data, output_path)
                self.root.after(0, lambda: self._on_excel_complete(output_path))
            except Exception as e:
                err = str(e)
                self.root.after(0, lambda: self._on_excel_error(err))

        threading.Thread(target=_thread, daemon=True).start()

    def _on_excel_complete(self, output_path):
        self._show_progress(False)
        self.btn_export_excel.configure(state="normal", cursor="hand2")
        msg = f"Excel-Datei gespeichert: {os.path.basename(output_path)}"
        self._set_status(msg)
        self._open_file(output_path)

    def _on_excel_error(self, error_msg):
        self._show_progress(False)
        self.btn_export_excel.configure(state="normal", cursor="hand2")
        messagebox.showerror("Fehler", f"Fehler beim Excel-Export:\n\n{error_msg}")
        self._set_status("Fehler beim Excel-Export.", error=True)

    # ──────────────────────────────────────────────────────────────
    # Statusleiste
    # ──────────────────────────────────────────────────────────────

    def _create_status_bar(self):
        # Bar zuerst packen (side=BOTTOM → ganz unten),
        # dann Separator (erscheint knapp darüber).
        bar = ttk.Frame(self.root)
        bar.pack(fill=tk.X, side=tk.BOTTOM)

        sep = ttk.Separator(self.root)
        sep.pack(fill=tk.X, side=tk.BOTTOM)

        self._dot = ttk.Label(bar, text="●", foreground=_MUTED,
                              font=("Segoe UI", 9))
        self._dot.pack(side=tk.LEFT, padx=(10, 2), pady=3)

        self.status_label = ttk.Label(
            bar,
            text="Bereit – Excel-Datei laden um zu beginnen.",
            font=("Segoe UI", 9), foreground=_MUTED,
        )
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=3)

        self.progress_bar_widget = ttk.Progressbar(
            bar, mode="indeterminate", length=160)
        self.cancel_btn = ttk.Button(
            bar, text="✕ Abbrechen", command=self._cancel_load, width=12)

    def _show_progress(self, show: bool, show_cancel: bool = True):
        if show:
            if show_cancel:
                self.cancel_btn.pack(side=tk.RIGHT, padx=(0, 4), pady=3)
            self.progress_bar_widget.pack(side=tk.RIGHT, padx=(0, 6), pady=3)
            self.progress_bar_widget.start(15)
        else:
            self.progress_bar_widget.stop()
            self.progress_bar_widget.pack_forget()
            self.cancel_btn.pack_forget()

    def _cancel_load(self):
        self._load_token += 1  # laufender Thread ignoriert sein Ergebnis
        self._show_progress(False)
        self._drop_icon  = "📂"
        self._drop_text  = "Excel- oder PDF-Datei hierher ziehen  oder  klicken zum Auswählen"
        self._drop_color = _MUTED
        self._drop_bg    = _DROP_BG
        self._redraw_drop()
        self._set_status("Ladevorgang abgebrochen.")

    def _set_status(self, text: str, error: bool = False):
        color = _RED if error else _MUTED
        self.status_label.configure(text=text, foreground=color)
        self._dot.configure(foreground=color)

    # ──────────────────────────────────────────────────────────────
    # Konfiguration
    # ──────────────────────────────────────────────────────────────

    def _load_config_to_gui(self):
        cfg  = self.config
        nr   = cfg.get("last_invoice_number", 1)
        year = cfg.get("last_invoice_year", datetime.date.today().year)
        self.var_invoice_nr.set(f"{nr}/{year}")
        self.var_markup.set(str(cfg.get("default_markup", 0.0)))
        self.var_ust_enabled.set(cfg.get("default_ust_enabled", False))
        self.var_ust_percent.set(str(cfg.get("default_ust_percent", 20.0)))
        self._on_ust_toggled()
        self.var_delivery_note.set(cfg.get("default_create_delivery_note", False))
        self.var_weight.set(cfg.get("default_weight", ""))
        saved_dlv_text = cfg.get("default_delivery_note_text", "")
        if saved_dlv_text:
            self.delivery_note_text.configure(state="normal")
            self.delivery_note_text.insert("1.0", saved_dlv_text)
        self._on_delivery_toggled()
        saved_invoice_note = cfg.get("default_invoice_note_text", "")
        if saved_invoice_note:
            self.invoice_note_text.insert("1.0", saved_invoice_note)
        self.var_is_export.set(cfg.get("default_is_export", False))
        self.var_girocode_enabled.set(cfg.get("default_girocode_enabled", True))
        cust = cfg.get("last_customer", {})
        self.var_cust_name.set(cust.get("name", ""))
        self.var_cust_street.set(cust.get("street", ""))
        self.var_cust_plz.set(cust.get("plz_city", ""))
        self.var_cust_country.set(cust.get("country", ""))
        self.var_cust_vat.set(cust.get("vat", ""))
        self._update_template_combobox()

    def _save_current_config(self, increment_nr: bool = False):
        nr_text = self.var_invoice_nr.get().strip()
        try:
            parts = nr_text.split("/") if "/" in nr_text else [nr_text]
            nr    = int(parts[0])
            year  = int(parts[1]) if len(parts) > 1 else datetime.date.today().year
        except (ValueError, IndexError):
            nr, year = 1, datetime.date.today().year

        try:
            markup = float(self.var_markup.get().replace(",", "."))
        except ValueError:
            markup = 0.0

        try:
            ust_pct = float(self.var_ust_percent.get().replace(",", "."))
        except ValueError:
            ust_pct = 20.0

        save_config({
            "last_invoice_number":          nr + 1 if increment_nr else nr,
            "last_invoice_year":            year,
            "default_markup":               markup,
            "default_ust_enabled":          self.var_ust_enabled.get(),
            "default_ust_percent":          ust_pct,
            "default_create_delivery_note": self.var_delivery_note.get(),
            "default_is_export":            self.var_is_export.get(),
            "default_girocode_enabled":     self.var_girocode_enabled.get(),
            "default_weight":               self.var_weight.get().strip(),
            "default_delivery_note_text":   self.delivery_note_text.get("1.0", tk.END).strip(),
            "default_invoice_note_text":    self.invoice_note_text.get("1.0", tk.END).strip(),
            "last_customer": {
                "name":     self.var_cust_name.get().strip(),
                "street":   self.var_cust_street.get().strip(),
                "plz_city": self.var_cust_plz.get().strip(),
                "country":  self.var_cust_country.get().strip(),
                "vat":      self.var_cust_vat.get().strip(),
            },
            "customer_templates": self.config.get("customer_templates", {}),
        })

    def run(self):
        self.root.mainloop()


def main():
    app = RechnungsBot()
    app.run()


if __name__ == "__main__":
    main()

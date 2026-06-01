"""
RechnungsBot – Hauptprogramm mit GUI.
"""

import os
import datetime
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

from src.config import load_config, save_config
from src.excel.parser import parse_excel
from src.pdf_input.parser import parse_pdf
from src.pdf.invoice import generate_invoice
from src.pdf.delivery_note import generate_delivery_note
from src.compare.gui_tab import VergleichsTab

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    HAS_DND = True
except ImportError:
    HAS_DND = False

_TABLE_DISPLAY_LIMIT = 500

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
        if HAS_DND:
            self.root = TkinterDnD.Tk()
        else:
            self.root = tk.Tk()

        self.root.title("RechnungsBot – Handelsagentur Adis Sefer")
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
        try:
            import sv_ttk
            sv_ttk.set_theme("light")
        except ImportError:
            pass

        s = ttk.Style()
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
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 20:
            return
        # Hintergrund
        c.create_rectangle(0, 0, w, h, fill=self._drop_bg, outline="")
        # Gestrichelter Rahmen
        border = _BLUE if self._hovering else _DASH_CLR
        c.create_rectangle(4, 4, w - 4, h - 4,
                           fill="", outline=border, width=2, dash=(9, 5))
        # Icon
        c.create_text(w // 2, h // 2 - 14,
                      text=self._drop_icon, font=("Segoe UI", 20),
                      fill=self._drop_color)
        # Text
        c.create_text(w // 2, h // 2 + 16,
                      text=self._drop_text, font=("Segoe UI", 10),
                      fill=self._drop_color)

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
                self.root.after(0, lambda: self._on_load_error(str(e), True, token))
            except Exception as e:
                self.root.after(0, lambda: self._on_load_error(str(e), False, token))

        threading.Thread(target=_thread, daemon=True).start()

    def _on_load_complete(self, filepath, items, token):
        if token != self._load_token:
            return
        self._show_progress(False)
        self.items = items
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
        frame = ttk.LabelFrame(parent, text="  Positionen  ", padding=(6, 6))
        frame.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        cols = ("stk", "ean", "produkt", "einzelpreis", "gesamtpreis")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings",
                                 height=12, selectmode="browse")

        self.tree.heading("stk",         text="Stk.",          anchor=tk.CENTER)
        self.tree.heading("ean",         text="EAN",           anchor=tk.W)
        self.tree.heading("produkt",     text="Produkt",       anchor=tk.W)
        self.tree.heading("einzelpreis", text="Einzelpreis €", anchor=tk.E)
        self.tree.heading("gesamtpreis", text="Gesamtpreis €", anchor=tk.E)

        self.tree.column("stk",         width=50,  anchor=tk.CENTER, minwidth=40,  stretch=False)
        self.tree.column("ean",         width=135, anchor=tk.W,      minwidth=100, stretch=False)
        self.tree.column("produkt",     width=0,   anchor=tk.W,      minwidth=200)
        self.tree.column("einzelpreis", width=115, anchor=tk.E,      minwidth=90,  stretch=False)
        self.tree.column("gesamtpreis", width=125, anchor=tk.E,      minwidth=90,  stretch=False)

        self.tree.tag_configure("even", background=_ROW_EVEN)

        sb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        total_row = ttk.Frame(parent)
        total_row.pack(fill=tk.X, pady=(0, 2))
        self.total_label = ttk.Label(total_row, text="", style="Header.TLabel")
        self.total_label.pack(side=tk.RIGHT, padx=4)

    def _populate_table(self):
        self.tree.delete(*self.tree.get_children())
        markup = self._get_markup_factor()
        for i, item in enumerate(self.items[:_TABLE_DISPLAY_LIMIT]):
            unit  = item["source_price"] * markup
            total = item["quantity"] * unit
            self.tree.insert("", tk.END, values=(
                item["quantity"], item["ean"], item["product"],
                f"{unit:.2f}", f"{total:.2f}",
            ), tags=("even",) if i % 2 == 0 else ())
        self._update_total_label()

    def _update_total_label(self):
        markup = self._get_markup_factor()
        netto  = sum(it["quantity"] * it["source_price"] * markup for it in self.items)
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

        self.btn_create = tk.Button(
            frame,
            text="   📄  Rechnung erstellen   ",
            font=("Segoe UI", 12, "bold"),
            bg=_BLUE, fg="#FFFFFF",
            activebackground=_BLUE_DK, activeforeground="#FFFFFF",
            relief="flat", bd=0,
            padx=20, pady=11,
            cursor="hand2",
            command=self._create_invoice,
        )
        self.btn_create.pack(pady=6)

    def _create_invoice(self):
        if not self.items:
            messagebox.showwarning("Keine Daten", "Bitte zuerst eine Excel-Datei laden.")
            return

        invoice_nr = self.var_invoice_nr.get().strip()
        if not invoice_nr:
            messagebox.showwarning("Rechnungsnummer fehlt", "Bitte eine Rechnungsnummer eingeben.")
            return

        invoice_date = self.var_date.get().strip()
        if not invoice_date:
            messagebox.showwarning("Datum fehlt", "Bitte ein Rechnungsdatum eingeben.")
            return

        cust_name = self.var_cust_name.get().strip()
        if not cust_name:
            messagebox.showwarning("Kunde fehlt", "Bitte den Firmennamen des Kunden eingeben.")
            return

        default_name = f"Rechnung_{invoice_nr.replace('/', '_')}.pdf"
        output_path  = filedialog.asksaveasfilename(
            title="Rechnung speichern als",
            defaultextension=".pdf",
            filetypes=[("PDF-Dateien", "*.pdf")],
            initialfile=default_name,
        )
        if not output_path:
            return

        # Alle GUI-Daten vor dem Thread-Start auslesen
        markup        = self._get_markup_factor()
        invoice_items = [
            {"ean": it["ean"], "product": it["product"],
             "quantity": it["quantity"], "unit_price": it["source_price"] * markup}
            for it in self.items
        ]

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
        }
        customer_data = {
            "name":     cust_name,
            "street":   self.var_cust_street.get().strip(),
            "plz_city": self.var_cust_plz.get().strip(),
            "country":  self.var_cust_country.get().strip(),
            "vat":      self.var_cust_vat.get().strip(),
        }

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
        msg = f"Rechnung gespeichert: {os.path.basename(output_path)}"
        if dlv_path:
            msg += f" | Lieferschein: {os.path.basename(dlv_path)}"
        self._save_current_config(increment_nr=True)
        self._set_status(msg)
        messagebox.showinfo("Erfolgreich erstellt", f"Erfolgreich erstellt:\n\n{msg}")
        os.startfile(output_path)
        if dlv_path:
            os.startfile(dlv_path)

    def _on_pdf_error(self, error_msg):
        self._show_progress(False)
        self.btn_create.configure(state="normal", bg=_BLUE, cursor="hand2")
        messagebox.showerror("Fehler", f"Fehler bei der Rechnungserstellung:\n\n{error_msg}")
        self._set_status("Fehler bei der Erstellung.", error=True)

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

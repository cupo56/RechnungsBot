"""
Provisionsrechnung – GUI-Tab zur manuellen Erfassung und Erstellung von Provisionsrechnungen.
"""

import os
import sys
import subprocess
import datetime
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

from src.config import load_config, save_config
from src.pdf.commission_invoice import generate_commission_invoice

_BLUE     = "#1B6EC2"
_BLUE_DK  = "#155599"
_BLUE_DIS = "#9BBFE0"
_GREEN    = "#1A7F3C"
_RED      = "#C0392B"
_MUTED    = "#64748B"

# Spalten der Positionstabelle, die per Klick auf die Zelle bearbeitbar sind:
# Spalten-ID -> (Schlüssel im items-Dict, Werttyp)
_EDITABLE_COLUMNS = {
    "reference":   ("reference", str),
    "description": ("description", str),
    "netto":       ("net_amount", float),
}


def _format_amount(val):
    """Formatiert nur die Zahl eines Betrags, z.B. '7 366,00'."""
    return f"{val:,.2f}".replace(",", " ").replace(".", ",")


class ProvisionTab:
    """Haupt-Widget für den Provisionsrechnung-Tab."""

    def __init__(self, parent):
        self._items = []
        self._cell_edit = None
        self.config = load_config()

        frame = ttk.Frame(parent, padding=(16, 12, 16, 4))
        frame.pack(fill=tk.BOTH, expand=True)

        # Header
        hdr = ttk.Frame(frame)
        hdr.pack(fill=tk.X, pady=(0, 8))
        self.btn_reset = tk.Button(
            hdr,
            text="↺  Neue Provisionsrechnung",
            font=("Segoe UI", 9),
            bg="#F1F5F9", fg="#1E293B",
            activebackground="#E2E8F0", activeforeground="#1E293B",
            relief="flat", bd=0, padx=10, pady=5,
            cursor="hand2",
            command=self._reset_session,
        )
        self.btn_reset.pack(side=tk.RIGHT, anchor=tk.NE)
        ttk.Label(hdr, text="Provisionsrechnung", style="Title.TLabel").pack(anchor=tk.W)
        ttk.Label(
            hdr,
            text="Provisionsrechnungen für Vermittlungsgeschäfte erstellen — Positionen manuell eintragen",
            style="Sub.TLabel",
        ).pack(anchor=tk.W)
        ttk.Separator(frame).pack(fill=tk.X, pady=(6, 10))

        body = ttk.Frame(frame)
        body.pack(fill=tk.BOTH, expand=True)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)

        # ──────────────────────────────────────────────────────────
        # Linke Spalte: Einstellungen + Empfänger
        # ──────────────────────────────────────────────────────────
        left = ttk.Frame(body)
        left.grid(row=0, column=0, sticky=tk.NSEW, padx=(0, 8))

        cfg = self.config

        settings = ttk.LabelFrame(left, text="  Einstellungen  ", padding=(10, 8))
        settings.pack(fill=tk.X, pady=(0, 8))
        settings.columnconfigure(1, weight=1)

        nr   = cfg.get("last_provision_number", 1)
        year = cfg.get("last_provision_year", datetime.date.today().year)
        self.var_nr   = tk.StringVar(value=f"{nr}/{year}")
        self.var_date = tk.StringVar(value=datetime.date.today().strftime("%d.%m.%Y"))

        ttk.Label(settings, text="Rechnungsnr.:").grid(row=0, column=0, sticky=tk.W, pady=3)
        ttk.Entry(settings, textvariable=self.var_nr, width=14).grid(row=0, column=1, sticky=tk.W, pady=3, padx=(8, 0))

        ttk.Label(settings, text="Datum:").grid(row=1, column=0, sticky=tk.W, pady=3)
        ttk.Entry(settings, textvariable=self.var_date, width=14).grid(row=1, column=1, sticky=tk.W, pady=3, padx=(8, 0))

        self.var_ust_enabled = tk.BooleanVar(value=cfg.get("default_provision_ust_enabled", True))
        self.var_ust_percent = tk.StringVar(value=str(cfg.get("default_provision_ust_percent", 20.0)))
        ust_row = ttk.Frame(settings)
        ust_row.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=3)
        ttk.Checkbutton(ust_row, text="USt.", variable=self.var_ust_enabled).pack(side=tk.LEFT)
        ttk.Entry(ust_row, textvariable=self.var_ust_percent, width=6).pack(side=tk.LEFT, padx=(8, 2))
        ttk.Label(ust_row, text="%").pack(side=tk.LEFT)

        self.var_girocode_enabled = tk.BooleanVar(value=cfg.get("default_provision_girocode_enabled", True))
        ttk.Checkbutton(settings, text="QR-Code (GiroCode)", variable=self.var_girocode_enabled).grid(
            row=3, column=0, columnspan=2, sticky=tk.W, pady=3)

        cust = ttk.LabelFrame(left, text="  Empfänger  ", padding=(10, 8))
        cust.pack(fill=tk.X)
        cust.columnconfigure(1, weight=1)

        # Vorlagen-Leiste
        tpl = ttk.Frame(cust)
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

        recipient = cfg.get("last_provision_recipient", {})
        self.var_cust_name    = tk.StringVar(value=recipient.get("name", ""))
        self.var_cust_street  = tk.StringVar(value=recipient.get("street", ""))
        self.var_cust_plz     = tk.StringVar(value=recipient.get("plz_city", ""))
        self.var_cust_country = tk.StringVar(value=recipient.get("country", ""))
        self.var_cust_vat     = tk.StringVar(value=recipient.get("vat", ""))

        def cust_row(label, var, row):
            ttk.Label(cust, text=label).grid(row=row, column=0, sticky=tk.W, pady=3)
            ttk.Entry(cust, textvariable=var).grid(row=row, column=1, sticky=tk.EW, pady=3, padx=(8, 0))

        cust_row("Firma:", self.var_cust_name, 1)
        cust_row("Straße:", self.var_cust_street, 2)
        cust_row("PLZ/Ort:", self.var_cust_plz, 3)
        cust_row("Land:", self.var_cust_country, 4)
        cust_row("VAT-Nr.:", self.var_cust_vat, 5)

        # ──────────────────────────────────────────────────────────
        # Rechte Spalte: Positionserfassung
        # ──────────────────────────────────────────────────────────
        right = ttk.Frame(body)
        right.grid(row=0, column=1, sticky=tk.NSEW, padx=(8, 0))

        entry_box = ttk.LabelFrame(right, text="  Position hinzufügen  ", padding=(10, 8))
        entry_box.pack(fill=tk.X)
        entry_box.columnconfigure(1, weight=1)

        self.var_item_ref   = tk.StringVar()
        self.var_item_descr = tk.StringVar()
        self.var_item_netto = tk.StringVar()

        ttk.Label(entry_box, text="Referenz (Rechnungsnr.):").grid(row=0, column=0, sticky=tk.W, pady=3)
        ttk.Entry(entry_box, textvariable=self.var_item_ref).grid(row=0, column=1, sticky=tk.EW, pady=3, padx=(8, 0))

        ttk.Label(entry_box, text="Beschreibung:").grid(row=1, column=0, sticky=tk.W, pady=3)
        ttk.Entry(entry_box, textvariable=self.var_item_descr).grid(row=1, column=1, sticky=tk.EW, pady=3, padx=(8, 0))

        ttk.Label(entry_box, text="Netto-Betrag (€):").grid(row=2, column=0, sticky=tk.W, pady=3)
        ttk.Entry(entry_box, textvariable=self.var_item_netto, width=14).grid(row=2, column=1, sticky=tk.W, pady=3, padx=(8, 0))

        self.btn_add = tk.Button(
            entry_box,
            text="+  Position hinzufügen",
            font=("Segoe UI", 9, "bold"),
            bg=_BLUE, fg="#FFFFFF",
            activebackground=_BLUE_DK, activeforeground="#FFFFFF",
            relief="flat", bd=0, padx=12, pady=6,
            cursor="hand2",
            command=self._add_item,
        )
        self.btn_add.grid(row=3, column=0, columnspan=2, pady=(8, 0))

        tbl = ttk.LabelFrame(right, text="  Positionen  ", padding=(6, 6))
        tbl.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        ttk.Label(
            tbl,
            text="Klick auf Referenz, Beschreibung oder Netto, um die Position zu bearbeiten. "
                 "Mit 🗑 lässt sich eine Position entfernen.",
            foreground=_MUTED, font=("Segoe UI", 8), wraplength=320, justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(0, 4))

        cols = ("reference", "description", "netto", "brutto", "delete")
        self.tree = ttk.Treeview(tbl, columns=cols, show="headings", height=8, selectmode="browse")
        self.tree.heading("reference",   text="Referenz",     anchor=tk.W)
        self.tree.heading("description", text="Beschreibung", anchor=tk.W)
        self.tree.heading("netto",       text="Netto",        anchor=tk.E)
        self.tree.heading("brutto",      text="Brutto",       anchor=tk.E)
        self.tree.heading("delete",      text="",             anchor=tk.CENTER)
        self.tree.column("reference",   width=120, anchor=tk.W, minwidth=80)
        self.tree.column("description", width=140, anchor=tk.W, minwidth=80)
        self.tree.column("netto",       width=85,  anchor=tk.E, minwidth=70, stretch=False)
        self.tree.column("brutto",      width=85,  anchor=tk.E, minwidth=70, stretch=False)
        self.tree.column("delete",      width=36,  anchor=tk.CENTER, minwidth=36, stretch=False)
        self.tree.bind("<Button-1>", self._on_tree_click)

        sb = ttk.Scrollbar(tbl, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        self.summary_label = ttk.Label(right, text="", font=("Segoe UI", 10, "bold"))
        self.summary_label.pack(anchor=tk.E, pady=(8, 0))

        # ──────────────────────────────────────────────────────────
        # Aktionsbereich
        # ──────────────────────────────────────────────────────────
        ttk.Separator(frame).pack(fill=tk.X, pady=(10, 8))
        action = ttk.Frame(frame)
        action.pack(fill=tk.X)
        self.btn_create = tk.Button(
            action,
            text="   📑  Provisionsrechnung erstellen   ",
            font=("Segoe UI", 12, "bold"),
            bg=_BLUE_DIS, fg="#FFFFFF",
            activebackground=_BLUE_DK, activeforeground="#FFFFFF",
            relief="flat", bd=0,
            padx=20, pady=11,
            cursor="arrow",
            command=self._create_invoice,
            state="disabled",
        )
        self.btn_create.pack()

        self.status_label = ttk.Label(frame, text="", style="Sub.TLabel")
        self.status_label.pack(anchor=tk.W, pady=(6, 0))

        self.var_ust_enabled.trace_add("write", lambda *_: self._on_ust_changed())
        self.var_ust_percent.trace_add("write", lambda *_: self._on_ust_changed())

        self._refresh_summary()
        self._update_template_combobox()

    # ──────────────────────────────────────────────────────────────
    # Positionsverwaltung
    # ──────────────────────────────────────────────────────────────

    def _current_ust_percent(self):
        if not self.var_ust_enabled.get():
            return 0.0
        try:
            return float(self.var_ust_percent.get().replace(",", "."))
        except ValueError:
            return 0.0

    def _on_ust_changed(self):
        self._refresh_table()
        self._refresh_summary()

    def _add_item(self):
        ref = self.var_item_ref.get().strip()
        if ref and not ref.lower().startswith("rechn"):
            ref = f"Rechn.Nr.{ref}"
        descr = self.var_item_descr.get().strip()
        netto_text = self.var_item_netto.get().strip().replace(",", ".")

        if not descr:
            messagebox.showwarning("Beschreibung fehlt", "Bitte eine Beschreibung eingeben.")
            return
        try:
            netto = float(netto_text)
        except ValueError:
            messagebox.showwarning("Ungültiger Betrag", "Bitte einen gültigen Netto-Betrag eingeben.")
            return
        if netto <= 0:
            messagebox.showwarning("Ungültiger Betrag", "Der Netto-Betrag muss größer als 0 sein.")
            return

        self._items.append({"reference": ref, "description": descr, "net_amount": netto})
        self.var_item_ref.set("")
        self.var_item_descr.set("")
        self.var_item_netto.set("")
        self._refresh_table()
        self._refresh_summary()
        self._refresh_create_button()

    def _refresh_table(self):
        self._cancel_cell_edit()
        self.tree.delete(*self.tree.get_children())
        ust_pct = self._current_ust_percent()
        for item in self._items:
            netto = item["net_amount"]
            brutto = netto * (1 + ust_pct / 100)
            self.tree.insert("", tk.END, values=(
                item["reference"],
                item["description"],
                f"€ {_format_amount(netto)}",
                f"€ {_format_amount(brutto)}",
                "🗑",
            ))

    def _refresh_summary(self):
        if not self._items:
            self.summary_label.configure(text="")
            return
        netto = sum(i["net_amount"] for i in self._items)
        ust_pct = self._current_ust_percent()
        ust_amount = netto * ust_pct / 100
        brutto = netto + ust_amount
        self.summary_label.configure(
            text=(f"Netto: € {_format_amount(netto)}   ·   "
                  f"Ust.: € {_format_amount(ust_amount)}   ·   "
                  f"Brutto: € {_format_amount(brutto)}")
        )

    def _refresh_create_button(self):
        if self._items:
            self.btn_create.configure(state="normal", bg=_BLUE, cursor="hand2")
        else:
            self.btn_create.configure(state="disabled", bg=_BLUE_DIS, cursor="arrow")

    def _reset_session(self):
        self._items = []
        self._refresh_table()
        self._refresh_summary()
        self._refresh_create_button()
        self.status_label.configure(text="")

    # ──────────────────────────────────────────────────────────────
    # Zellen-Bearbeitung
    # ──────────────────────────────────────────────────────────────

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
        if col_id == "delete":
            self._delete_item(row_id)
        elif col_id in _EDITABLE_COLUMNS:
            self._start_cell_edit(row_id, col_id)

    def _delete_item(self, row_id):
        index = self.tree.index(row_id)
        item = self._items[index]
        if not messagebox.askyesno("Position entfernen",
                                    f"Soll die Position „{item['description']}“ wirklich entfernt werden?"):
            return
        del self._items[index]
        self._refresh_table()
        self._refresh_summary()
        self._refresh_create_button()

    def _column_id_at(self, x):
        col = self.tree.identify_column(x)
        try:
            idx = int(col[1:]) - 1
        except ValueError:
            return None
        cols = self.tree["columns"]
        return cols[idx] if 0 <= idx < len(cols) else None

    def _start_cell_edit(self, row_id, col_id):
        self._commit_cell_edit()
        bbox = self.tree.bbox(row_id, col_id)
        if not bbox:
            return
        x, y, width, height = bbox
        index = self.tree.index(row_id)
        field_key, value_type = _EDITABLE_COLUMNS[col_id]
        current = self._items[index][field_key]

        if value_type is float:
            text, justify = f"{current:.2f}".replace(".", ","), tk.RIGHT
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

        if value_type is float:
            try:
                value = float(raw.replace(",", "."))
            except ValueError:
                messagebox.showwarning("Ungültiger Betrag", f"'{raw}' ist kein gültiger Betrag.")
                return
            if value <= 0:
                messagebox.showwarning("Ungültiger Betrag", "Der Netto-Betrag muss größer als 0 sein.")
                return
            self._items[index][field_key] = value
        else:
            if field_key == "description" and not raw:
                messagebox.showwarning("Beschreibung fehlt", "Die Beschreibung darf nicht leer sein.")
                return
            if field_key == "reference" and raw and not raw.lower().startswith("rechn"):
                raw = f"Rechn.Nr.{raw}"
            self._items[index][field_key] = raw

        self._refresh_table()
        self._refresh_summary()

    def _cancel_cell_edit(self):
        if not self._cell_edit:
            return
        _, _, _, entry, _ = self._cell_edit
        self._cell_edit = None
        entry.destroy()

    # ──────────────────────────────────────────────────────────────
    # Empfänger-Vorlagen
    # ──────────────────────────────────────────────────────────────

    def _update_template_combobox(self):
        names = list(self.config.get("provision_customer_templates", {}).keys())
        self.cb_templates["values"] = names
        if self.var_template.get() not in names:
            self.var_template.set("")

    def _on_template_selected(self, _=None):
        name = self.var_template.get()
        tpl  = self.config.get("provision_customer_templates", {}).get(name, {})
        self.var_cust_name.set(tpl.get("name", ""))
        self.var_cust_street.set(tpl.get("street", ""))
        self.var_cust_plz.set(tpl.get("plz_city", ""))
        self.var_cust_country.set(tpl.get("country", ""))
        self.var_cust_vat.set(tpl.get("vat", ""))

    def _save_template(self):
        tpl_name = simpledialog.askstring(
            "Vorlage speichern", "Name für diese Vorlage:",
            initialvalue=self.var_cust_name.get().strip(), parent=self.tree.winfo_toplevel())
        if not tpl_name or not tpl_name.strip():
            return
        tpl_name = tpl_name.strip()
        templates = self.config.setdefault("provision_customer_templates", {})
        templates[tpl_name] = {
            "name":     self.var_cust_name.get().strip(),
            "street":   self.var_cust_street.get().strip(),
            "plz_city": self.var_cust_plz.get().strip(),
            "country":  self.var_cust_country.get().strip(),
            "vat":      self.var_cust_vat.get().strip(),
        }
        save_config({"provision_customer_templates": templates})
        self._update_template_combobox()
        self.var_template.set(tpl_name)
        self.status_label.configure(text=f"Vorlage '{tpl_name}' gespeichert.", foreground=_GREEN)

    def _delete_template(self):
        name = self.var_template.get()
        if not name:
            messagebox.showwarning("Keine Vorlage", "Bitte zuerst eine Vorlage auswählen.")
            return
        if messagebox.askyesno("Löschen", f"Vorlage '{name}' wirklich löschen?"):
            templates = self.config.get("provision_customer_templates", {})
            templates.pop(name, None)
            save_config({"provision_customer_templates": templates})
            self._update_template_combobox()
            self.var_template.set("")
            self.status_label.configure(text=f"Vorlage '{name}' gelöscht.", foreground=_GREEN)

    # ──────────────────────────────────────────────────────────────
    # PDF-Erstellung
    # ──────────────────────────────────────────────────────────────

    def _create_invoice(self):
        if not self._items:
            return

        invoice_nr = self.var_nr.get().strip()
        if not invoice_nr:
            messagebox.showwarning("Rechnungsnummer fehlt", "Bitte eine Rechnungsnummer eingeben.")
            return

        invoice_date = self.var_date.get().strip()
        if not invoice_date:
            messagebox.showwarning("Datum fehlt", "Bitte ein Rechnungsdatum eingeben.")
            return

        cust_name = self.var_cust_name.get().strip()
        if not cust_name:
            messagebox.showwarning("Empfänger fehlt", "Bitte den Firmennamen des Empfängers eingeben.")
            return

        ust_enabled = self.var_ust_enabled.get()
        try:
            ust_percent = float(self.var_ust_percent.get().replace(",", ".")) if ust_enabled else 0
        except ValueError:
            ust_percent = 0

        invoice_data = {
            "number":           invoice_nr,
            "date":             invoice_date,
            "ust_enabled":      ust_enabled,
            "ust_percent":      ust_percent,
            "girocode_enabled": self.var_girocode_enabled.get(),
        }
        customer_data = {
            "name":     cust_name,
            "street":   self.var_cust_street.get().strip(),
            "plz_city": self.var_cust_plz.get().strip(),
            "country":  self.var_cust_country.get().strip(),
            "vat":      self.var_cust_vat.get().strip(),
        }
        items = list(self._items)

        default_name = f"Provisionsrechnung_{invoice_nr.replace('/', '_')}.pdf"
        output_path = filedialog.asksaveasfilename(
            title="Provisionsrechnung speichern als",
            defaultextension=".pdf",
            filetypes=[("PDF-Dateien", "*.pdf")],
            initialfile=default_name,
        )
        if not output_path:
            return

        self.status_label.configure(text="Provisionsrechnung wird erstellt…", foreground=_MUTED)
        self.btn_create.configure(state="disabled", bg=_BLUE_DIS, cursor="arrow")

        def _thread():
            try:
                generate_commission_invoice(items, invoice_data, customer_data, output_path)
                self.tree.after(0, lambda: self._on_pdf_complete(output_path, invoice_nr, customer_data))
            except Exception as e:
                err = str(e)
                self.tree.after(0, lambda: self._on_pdf_error(err))

        threading.Thread(target=_thread, daemon=True).start()

    def _on_pdf_complete(self, output_path, invoice_nr, customer_data):
        self.btn_create.configure(state="normal", bg=_BLUE, cursor="hand2")
        msg = f"Provisionsrechnung gespeichert: {os.path.basename(output_path)}"
        self.status_label.configure(text=msg, foreground=_GREEN)
        self._save_current_config(invoice_nr, customer_data, increment_nr=True)
        messagebox.showinfo("Erfolgreich erstellt", f"Erfolgreich erstellt:\n\n{msg}")
        self._open_file(output_path)

    def _on_pdf_error(self, error_msg):
        self.btn_create.configure(state="normal", bg=_BLUE, cursor="hand2")
        self.status_label.configure(text="Fehler bei der Erstellung.", foreground=_RED)
        messagebox.showerror("Fehler", f"Fehler bei der Provisionsrechnung-Erstellung:\n\n{error_msg}")

    def _open_file(self, filepath):
        if sys.platform == "win32":
            os.startfile(filepath)
        elif sys.platform == "darwin":
            subprocess.call(["open", filepath])
        else:
            subprocess.call(["xdg-open", filepath])

    # ──────────────────────────────────────────────────────────────
    # Konfiguration
    # ──────────────────────────────────────────────────────────────

    def _save_current_config(self, invoice_nr, customer_data, increment_nr=False):
        try:
            parts = invoice_nr.split("/") if "/" in invoice_nr else [invoice_nr]
            nr   = int(parts[0])
            year = int(parts[1]) if len(parts) > 1 else datetime.date.today().year
        except (ValueError, IndexError):
            nr, year = 1, datetime.date.today().year

        try:
            ust_pct = float(self.var_ust_percent.get().replace(",", "."))
        except ValueError:
            ust_pct = 20.0

        new_nr = nr + 1 if increment_nr else nr
        save_config({
            "last_provision_number":              new_nr,
            "last_provision_year":                year,
            "default_provision_ust_enabled":      self.var_ust_enabled.get(),
            "default_provision_ust_percent":      ust_pct,
            "default_provision_girocode_enabled": self.var_girocode_enabled.get(),
            "last_provision_recipient":           dict(customer_data),
            "provision_customer_templates":       self.config.get("provision_customer_templates", {}),
        })
        self.var_nr.set(f"{new_nr}/{year}")

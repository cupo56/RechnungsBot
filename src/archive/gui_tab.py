"""
Archiv-Tab für RechnungsBot.
Zeigt alle in der Datenbank gespeicherten Rechnungen und ermöglicht
Suche, PDF-Download und Verwaltung der API-Einstellungen.
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from src.config import load_config, save_config
from src.database import (
    is_configured, test_connection, init_database,
    get_all_invoices, get_invoice_pdf, delete_invoice,
)

_BLUE      = "#1B6EC2"
_BLUE_DK   = "#155599"
_GREEN     = "#1A7F3C"
_RED       = "#C0392B"
_MUTED     = "#64748B"
_ROW_EVEN  = "#F5F7FA"

_DOC_TYPES = {
    "alle":         "Alle Dokumente",
    "rechnung":     "📄 Rechnungen",
    "lieferschein": "📦 Lieferscheine",
    "provision":    "💰 Provisionsrechnungen",
    "gutschrift":   "🧾 Gutschriften",
}

_DOC_TYPE_LABELS = {
    "rechnung":     "📄 Rechnung",
    "lieferschein": "📦 Lieferschein",
    "provision":    "💰 Provision",
    "gutschrift":   "🧾 Gutschrift",
}


class ArchiveTab:
    """GUI-Tab für das Rechnungsarchiv (Datenbankanbindung über PHP-API)."""

    def __init__(self, parent):
        self.parent = parent
        self.config = load_config()
        self._invoices = []       # Geladene Rechnungsliste (ohne PDF-Blob)
        self._settings_visible = False
        self._loaded = False      # Lazy-load: Erst beim ersten Tab-Wechsel laden

        self._build_ui()

    # ──────────────────────────────────────────────────────────────
    # UI aufbauen
    # ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        main = ttk.Frame(self.parent, padding=(16, 12, 16, 4))
        main.pack(fill=tk.BOTH, expand=True)
        self._main_frame = main

        # Header
        hdr = ttk.Frame(main)
        hdr.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(hdr, text="Datenbank",
                  font=("Segoe UI", 18, "bold")).pack(anchor=tk.W)
        ttk.Label(hdr,
                  text="Alle erstellten Dokumente – in der World4You-Datenbank gespeichert",
                  font=("Segoe UI", 10), foreground=_MUTED).pack(anchor=tk.W)
        self._sep1 = ttk.Separator(main)
        self._sep1.pack(fill=tk.X, pady=(6, 10))

        # ── Verbindungsstatus + Settings-Toggle ──
        conn_frame = ttk.Frame(main)
        conn_frame.pack(fill=tk.X, pady=(0, 6))
        self._conn_frame = conn_frame

        self.lbl_status = ttk.Label(conn_frame, text="⏳ Prüfe Verbindung…",
                                     font=("Segoe UI", 10))
        self.lbl_status.pack(side=tk.LEFT)

        self.btn_toggle_settings = ttk.Button(
            conn_frame, text="⚙ API-Einstellungen",
            command=self._toggle_settings, width=18)
        self.btn_toggle_settings.pack(side=tk.RIGHT, padx=(6, 0))

        self.btn_test = ttk.Button(
            conn_frame, text="🔌 Verbindung testen",
            command=self._test_connection, width=20)
        self.btn_test.pack(side=tk.RIGHT, padx=(6, 0))

        self.btn_refresh = ttk.Button(
            conn_frame, text="↻ Aktualisieren",
            command=self._refresh_invoices, width=14)
        self.btn_refresh.pack(side=tk.RIGHT, padx=(6, 0))

        # ── Settings-Bereich (ein-/ausklappbar) ──
        self.settings_frame = ttk.LabelFrame(main, text="  API-Einstellungen (World4You)  ",
                                              padding=(12, 10))
        # Wird erst bei Toggle eingeblendet
        self._build_settings_fields()

        # ── Suchleiste ──
        search_frame = ttk.Frame(main)
        search_frame.pack(fill=tk.X, pady=(4, 6))
        self._search_frame = search_frame

        ttk.Label(search_frame, text="Suche:").pack(side=tk.LEFT)
        self.var_search = tk.StringVar()
        self.entry_search = ttk.Entry(search_frame, textvariable=self.var_search, width=30)
        self.entry_search.pack(side=tk.LEFT, padx=(6, 6))
        self.entry_search.bind("<Return>", lambda e: self._refresh_invoices())

        self.var_doc_filter = tk.StringVar(value="alle")
        self.cb_filter = ttk.Combobox(
            search_frame, textvariable=self.var_doc_filter,
            values=list(_DOC_TYPES.values()), state="readonly", width=22)
        self.cb_filter.current(0)
        self.cb_filter.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_search = ttk.Button(
            search_frame, text="🔍 Suchen", command=self._refresh_invoices, width=10)
        self.btn_search.pack(side=tk.LEFT)

        self.lbl_count = ttk.Label(search_frame, text="",
                                    font=("Segoe UI", 9), foreground=_MUTED)
        self.lbl_count.pack(side=tk.RIGHT, padx=4)

        # ── Rechnungstabelle ──
        table_frame = ttk.LabelFrame(main, text="  Archivierte Dokumente  ",
                                      padding=(6, 6))
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        cols = ("nr", "datum", "typ", "kunde", "netto", "brutto", "positionen", "datei")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings",
                                  height=14, selectmode="browse")

        self.tree.heading("nr",          text="Rechnungs-Nr.",  anchor=tk.W)
        self.tree.heading("datum",       text="Datum",          anchor=tk.W)
        self.tree.heading("typ",         text="Typ",            anchor=tk.W)
        self.tree.heading("kunde",       text="Kunde",          anchor=tk.W)
        self.tree.heading("netto",       text="Netto €",        anchor=tk.E)
        self.tree.heading("brutto",      text="Brutto €",       anchor=tk.E)
        self.tree.heading("positionen",  text="Pos.",           anchor=tk.CENTER)
        self.tree.heading("datei",       text="Dateiname",      anchor=tk.W)

        self.tree.column("nr",         width=110, minwidth=80,  stretch=False)
        self.tree.column("datum",      width=90,  minwidth=75,  stretch=False)
        self.tree.column("typ",        width=110, minwidth=90,  stretch=False)
        self.tree.column("kunde",      width=0,   minwidth=120)
        self.tree.column("netto",      width=100, minwidth=80,  stretch=False, anchor=tk.E)
        self.tree.column("brutto",     width=100, minwidth=80,  stretch=False, anchor=tk.E)
        self.tree.column("positionen", width=50,  minwidth=40,  stretch=False, anchor=tk.CENTER)
        self.tree.column("datei",      width=170, minwidth=120, stretch=False)

        self.tree.tag_configure("even", background=_ROW_EVEN)

        sb = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        # ── Aktions-Buttons (unter der Tabelle) ──
        action_frame = ttk.Frame(main)
        action_frame.pack(fill=tk.X, pady=(4, 2))

        self.btn_download = tk.Button(
            action_frame, text="   📥  PDF herunterladen   ",
            font=("Segoe UI", 10, "bold"),
            bg=_BLUE, fg="#FFFFFF",
            activebackground=_BLUE_DK, activeforeground="#FFFFFF",
            relief="flat", bd=0, padx=14, pady=8,
            cursor="hand2",
            command=self._download_pdf,
        )
        self.btn_download.pack(side=tk.LEFT)

        self.btn_delete = tk.Button(
            action_frame, text="   🗑  Löschen   ",
            font=("Segoe UI", 10),
            bg="#FEE2E2", fg=_RED,
            activebackground="#FECACA", activeforeground=_RED,
            relief="flat", bd=0, padx=14, pady=8,
            cursor="hand2",
            command=self._delete_selected,
        )
        self.btn_delete.pack(side=tk.LEFT, padx=(10, 0))

    def _build_settings_fields(self):
        """Baut die API-Einstellungsfelder innerhalb von self.settings_frame."""
        f = self.settings_frame
        f.columnconfigure(1, weight=1)

        cfg = self.config

        ttk.Label(f, text="API-URL:",
                  font=("Segoe UI", 9)).grid(row=0, column=0, sticky=tk.W, pady=3)
        self.var_api_url = tk.StringVar(value=cfg.get("db_api_url", ""))
        ttk.Entry(f, textvariable=self.var_api_url, width=50).grid(
            row=0, column=1, sticky=tk.EW, padx=(8, 0), pady=3)

        ttk.Label(f, text="API-Key:",
                  font=("Segoe UI", 9)).grid(row=1, column=0, sticky=tk.W, pady=3)
        self.var_api_key = tk.StringVar(value=cfg.get("db_api_key", ""))
        ttk.Entry(f, textvariable=self.var_api_key, width=50, show="•").grid(
            row=1, column=1, sticky=tk.EW, padx=(8, 0), pady=3)

        ttk.Label(f,
                  text="Die PHP-Dateien (server/) müssen auf deinen World4You-Webspace "
                       "hochgeladen werden.\n"
                       "Beispiel API-URL: https://deinedomain.at/rechnungsbot",
                  font=("Segoe UI", 8), foreground=_MUTED,
                  wraplength=400, justify=tk.LEFT,
                  ).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(4, 2))

        btn_row = ttk.Frame(f)
        btn_row.grid(row=3, column=0, columnspan=2, pady=(8, 2))

        self.btn_save_settings = tk.Button(
            btn_row, text="   💾  Speichern & Verbinden   ",
            font=("Segoe UI", 10, "bold"),
            bg=_GREEN, fg="#FFFFFF",
            activebackground="#15803D", activeforeground="#FFFFFF",
            relief="flat", bd=0, padx=12, pady=6,
            cursor="hand2",
            command=self._save_settings,
        )
        self.btn_save_settings.pack(side=tk.LEFT)

    # ──────────────────────────────────────────────────────────────
    # Settings ein-/ausklappen
    # ──────────────────────────────────────────────────────────────

    def _toggle_settings(self):
        if self._settings_visible:
            self.settings_frame.pack_forget()
            self._settings_visible = False
        else:
            # Direkt nach dem Verbindungsstatus einfügen
            self.settings_frame.pack(fill=tk.X, pady=(0, 6),
                                      after=self._conn_frame)
            self._settings_visible = True

    def _save_settings(self):
        """Speichert die API-Einstellungen und initialisiert die Datenbank."""
        api_url = self.var_api_url.get().strip().rstrip("/")
        api_key = self.var_api_key.get().strip()

        if not api_url:
            messagebox.showwarning("API-URL fehlt",
                                    "Bitte die API-URL eingeben (z.B. https://deinedomain.at/rechnungsbot)")
            return

        if not api_key:
            messagebox.showwarning("API-Key fehlt",
                                    "Bitte den API-Key eingeben.")
            return

        db_cfg = {
            "db_api_url": api_url,
            "db_api_key": api_key,
            "db_enabled": True,
        }

        # In globale Config und File schreiben
        self.config.update(db_cfg)
        save_config(db_cfg)

        self.lbl_status.configure(text="⏳ Verbindung wird getestet…", foreground=_MUTED)

        def _thread():
            success, msg = test_connection(self.config)
            if success:
                ok, init_msg = init_database(self.config)
                if not ok:
                    self.parent.after(0, lambda: self._on_settings_saved(False, init_msg))
                    return
            self.parent.after(0, lambda: self._on_settings_saved(success, msg))

        threading.Thread(target=_thread, daemon=True).start()

    def _on_settings_saved(self, success, msg):
        if success:
            self.lbl_status.configure(
                text=f"✅ Verbunden — {msg}", foreground=_GREEN)
            self._refresh_invoices()
            # Settings zuklappen nach Erfolg
            if self._settings_visible:
                self._toggle_settings()
        else:
            self.lbl_status.configure(
                text=f"❌ Fehler: {msg}", foreground=_RED)

    # ──────────────────────────────────────────────────────────────
    # Verbindungstest
    # ──────────────────────────────────────────────────────────────

    def _test_connection(self):
        self.config = load_config()
        if not is_configured(self.config):
            self.lbl_status.configure(
                text="⚠ API nicht konfiguriert — klicke auf ⚙ API-Einstellungen",
                foreground="#D97706")
            return

        self.lbl_status.configure(text="⏳ Verbindung wird getestet…", foreground=_MUTED)

        def _thread():
            success, msg = test_connection(self.config)
            self.parent.after(0, lambda: self._on_test_complete(success, msg))

        threading.Thread(target=_thread, daemon=True).start()

    def _on_test_complete(self, success, msg):
        if success:
            self.lbl_status.configure(
                text="✅ Verbindung OK", foreground=_GREEN)
        else:
            self.lbl_status.configure(
                text=f"❌ {msg}", foreground=_RED)

    # ──────────────────────────────────────────────────────────────
    # Rechnungsliste laden
    # ──────────────────────────────────────────────────────────────

    def load_if_needed(self):
        """Wird vom Hauptfenster beim Tab-Wechsel aufgerufen (lazy load)."""
        if not self._loaded:
            self._loaded = True
            self.config = load_config()  # Frische Config laden
            if is_configured(self.config):
                self._refresh_invoices()
                self._test_connection()
            else:
                self.lbl_status.configure(
                    text="⚠ Keine API konfiguriert — "
                         "klicke auf ⚙ API-Einstellungen",
                    foreground="#D97706")

    def _refresh_invoices(self):
        """Lädt die Rechnungsliste aus der Datenbank (in einem Hintergrund-Thread)."""
        self.config = load_config()
        if not is_configured(self.config):
            self.lbl_status.configure(
                text="⚠ Keine API konfiguriert", foreground="#D97706")
            return

        search = self.var_search.get().strip() or None

        # Dokumenttyp-Filter auslesen
        filter_display = self.var_doc_filter.get()
        doc_type = None
        for key, label in _DOC_TYPES.items():
            if label == filter_display:
                doc_type = key
                break

        def _thread():
            invoices = get_all_invoices(self.config, search=search, doc_type=doc_type)
            self.parent.after(0, lambda: self._on_invoices_loaded(invoices))

        threading.Thread(target=_thread, daemon=True).start()

    def _on_invoices_loaded(self, invoices):
        self._invoices = invoices
        self.tree.delete(*self.tree.get_children())

        for i, inv in enumerate(invoices):
            netto = inv.get("total_netto", 0) or 0
            brutto = inv.get("total_brutto", 0) or 0
            doc_label = _DOC_TYPE_LABELS.get(
                inv.get("document_type", ""), inv.get("document_type", ""))

            self.tree.insert("", tk.END, iid=str(inv["id"]), values=(
                inv.get("invoice_number", ""),
                inv.get("invoice_date", ""),
                doc_label,
                inv.get("customer_name", ""),
                f"{float(netto):,.2f}".replace(",", " ").replace(".", ","),
                f"{float(brutto):,.2f}".replace(",", " ").replace(".", ","),
                inv.get("item_count", 0),
                inv.get("pdf_filename", ""),
            ), tags=("even",) if i % 2 == 0 else ())

        count = len(invoices)
        self.lbl_count.configure(text=f"{count} Dokument{'e' if count != 1 else ''} gefunden")

    # ──────────────────────────────────────────────────────────────
    # PDF herunterladen
    # ──────────────────────────────────────────────────────────────

    def _download_pdf(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Keine Auswahl",
                                    "Bitte ein Dokument in der Tabelle auswählen.")
            return

        invoice_id = int(sel[0])
        # Dateiname aus der Tabelle auslesen
        values = self.tree.item(sel[0], "values")
        default_name = values[7] if len(values) > 7 else "dokument.pdf"

        output_path = filedialog.asksaveasfilename(
            title="PDF speichern als",
            defaultextension=".pdf",
            filetypes=[("PDF-Dateien", "*.pdf")],
            initialfile=default_name,
        )
        if not output_path:
            return

        def _thread():
            result = get_invoice_pdf(self.config, invoice_id)
            self.parent.after(0, lambda: self._on_pdf_downloaded(result, output_path))

        threading.Thread(target=_thread, daemon=True).start()

    def _on_pdf_downloaded(self, result, output_path):
        if result is None:
            messagebox.showerror("Fehler", "PDF konnte nicht aus der Datenbank geladen werden.")
            return

        pdf_data, _ = result
        try:
            with open(output_path, "wb") as f:
                f.write(pdf_data)
            messagebox.showinfo("Erfolg", f"PDF gespeichert:\n{os.path.basename(output_path)}")
            # Datei öffnen
            if sys.platform == "win32":
                os.startfile(output_path)
            elif sys.platform == "darwin":
                import subprocess
                subprocess.call(["open", output_path])
            else:
                import subprocess
                subprocess.call(["xdg-open", output_path])
        except IOError as e:
            messagebox.showerror("Fehler", f"PDF konnte nicht gespeichert werden:\n{e}")

    # ──────────────────────────────────────────────────────────────
    # Löschen
    # ──────────────────────────────────────────────────────────────

    def _delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Keine Auswahl",
                                    "Bitte ein Dokument in der Tabelle auswählen.")
            return

        invoice_id = int(sel[0])
        values = self.tree.item(sel[0], "values")
        nr = values[0] if values else "?"
        kunde = values[3] if len(values) > 3 else "?"

        if not messagebox.askyesno(
            "Löschen bestätigen",
            f"Soll das Dokument '{nr}' (Kunde: {kunde}) wirklich "
            f"aus der Datenbank gelöscht werden?\n\n"
            f"Dieser Vorgang kann nicht rückgängig gemacht werden."
        ):
            return

        def _thread():
            success, msg = delete_invoice(self.config, invoice_id)
            self.parent.after(0, lambda: self._on_delete_complete(success, msg))

        threading.Thread(target=_thread, daemon=True).start()

    def _on_delete_complete(self, success, msg):
        if success:
            self._refresh_invoices()
        else:
            messagebox.showerror("Fehler", f"Löschen fehlgeschlagen:\n{msg}")

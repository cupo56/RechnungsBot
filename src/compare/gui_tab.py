"""
VergleichsBot – GUI-Tab für den Waren-Abgleich.
"""

import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from src.compare.parser import parse_file
from src.compare.comparator import compare

_BLUE    = "#1B6EC2"
_GREEN   = "#16a34a"
_RED     = "#dc2626"
_MUTED   = "#64748B"
_DROP_BG = "#EBF3FF"
_DROP_OK = "#F0FDF4"
_DASH    = "#90BEF5"

_FILETYPES = [
    ("Excel & PDF", "*.xlsx *.xls *.pdf"),
    ("Excel-Dateien", "*.xlsx *.xls"),
    ("PDF-Dateien", "*.pdf"),
    ("Alle Dateien", "*.*"),
]

_STATUS_SORT = {"FEHLT": 0, "FALSCHE_MENGE": 1, "NICHT_BESTELLT": 2, "OK": 3}
_STATUS_TAG  = {"OK": "ok", "FEHLT": "fehlt", "FALSCHE_MENGE": "menge", "NICHT_BESTELLT": "extra"}
_STATUS_LBL  = {"OK": "✓ OK", "FEHLT": "✗ FEHLT", "FALSCHE_MENGE": "⚠ MENGE", "NICHT_BESTELLT": "+ EXTRA"}


class VergleichsTab:
    """Haupt-Widget für den VergleichsBot-Tab."""

    def __init__(self, parent):
        self._order_items    = None
        self._delivery_items = None

        frame = ttk.Frame(parent, padding=(16, 12, 16, 4))
        frame.pack(fill=tk.BOTH, expand=True)

        # Header
        hdr = ttk.Frame(frame)
        hdr.pack(fill=tk.X, pady=(0, 8))
        self.btn_reset = tk.Button(
            hdr,
            text="↺  Neuer Vergleich",
            font=("Segoe UI", 9),
            bg="#F1F5F9", fg="#1E293B",
            activebackground="#E2E8F0", activeforeground="#1E293B",
            relief="flat", bd=0, padx=10, pady=5,
            cursor="hand2",
            command=self._reset_session,
            state="disabled",
        )
        self.btn_reset.pack(side=tk.RIGHT, anchor=tk.NE)
        ttk.Label(hdr, text="VergleichsBot", style="Title.TLabel").pack(anchor=tk.W)
        ttk.Label(
            hdr,
            text="Bestellung und Lieferung vergleichen — erkennt fehlende und falsche Positionen",
            style="Sub.TLabel",
        ).pack(anchor=tk.W)
        ttk.Separator(frame).pack(fill=tk.X, pady=(6, 10))

        # Zwei Upload-Zonen nebeneinander
        zones = ttk.Frame(frame)
        zones.pack(fill=tk.X, pady=(0, 8))
        zones.columnconfigure(0, weight=1)
        zones.columnconfigure(1, weight=1)

        self._zone_order = _UploadZone(
            zones,
            title="BESTELLUNG",
            hint="Bestelldatei laden  (Excel oder PDF)",
            on_loaded=self._on_order_loaded,
        )
        self._zone_order.frame.grid(row=0, column=0, sticky=tk.NSEW, padx=(0, 6))

        self._zone_delivery = _UploadZone(
            zones,
            title="LIEFERUNG",
            hint="Lieferschein laden  (Excel oder PDF)",
            on_loaded=self._on_delivery_loaded,
        )
        self._zone_delivery.frame.grid(row=0, column=1, sticky=tk.NSEW, padx=(6, 0))

        # Vergleichen-Button
        btn_row = ttk.Frame(frame)
        btn_row.pack(pady=(4, 8))
        self.btn_compare = tk.Button(
            btn_row,
            text="   🔍  Vergleichen starten   ",
            font=("Segoe UI", 12, "bold"),
            bg="#9BBFE0", fg="#FFFFFF",
            activebackground="#155599", activeforeground="#FFFFFF",
            relief="flat", bd=0,
            padx=20, pady=11,
            cursor="arrow",
            command=self._run_compare,
            state="disabled",
        )
        self.btn_compare.pack()

        ttk.Separator(frame).pack(fill=tk.X, pady=(0, 8))

        # Zusammenfassung
        self.summary_label = ttk.Label(frame, text="", font=("Segoe UI", 10, "bold"))
        self.summary_label.pack(anchor=tk.W, pady=(0, 4))

        # Ergebnis-Tabelle
        tbl = ttk.LabelFrame(frame, text="  Vergleichsergebnis  ", padding=(6, 6))
        tbl.pack(fill=tk.BOTH, expand=True)

        cols = ("identifier", "product", "ordered", "delivered", "status")
        self.tree = ttk.Treeview(tbl, columns=cols, show="headings", height=15, selectmode="browse")

        self.tree.heading("identifier", text="EAN / SKU",  anchor=tk.W)
        self.tree.heading("product",    text="Produkt",    anchor=tk.W)
        self.tree.heading("ordered",    text="Bestellt",   anchor=tk.CENTER)
        self.tree.heading("delivered",  text="Geliefert",  anchor=tk.CENTER)
        self.tree.heading("status",     text="Status",     anchor=tk.CENTER)

        self.tree.column("identifier", width=145, anchor=tk.W,      minwidth=100, stretch=False)
        self.tree.column("product",    width=0,   anchor=tk.W,      minwidth=200)
        self.tree.column("ordered",    width=90,  anchor=tk.CENTER,  minwidth=70,  stretch=False)
        self.tree.column("delivered",  width=90,  anchor=tk.CENTER,  minwidth=70,  stretch=False)
        self.tree.column("status",     width=110, anchor=tk.CENTER,  minwidth=90,  stretch=False)

        self.tree.tag_configure("ok",    background="#dcfce7", foreground="#14532d")
        self.tree.tag_configure("fehlt", background="#fee2e2", foreground="#7f1d1d")
        self.tree.tag_configure("menge", background="#ffedd5", foreground="#7c2d12")
        self.tree.tag_configure("extra", background="#fef9c3", foreground="#713f12")

        sb = ttk.Scrollbar(tbl, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

    # ──────────────────────────────────────────────────────────────
    # Callbacks von den Upload-Zonen
    # ──────────────────────────────────────────────────────────────

    def _on_order_loaded(self, items):
        self._order_items = items
        self.btn_reset.configure(state="normal")
        self._refresh_btn()

    def _on_delivery_loaded(self, items):
        self._delivery_items = items
        self.btn_reset.configure(state="normal")
        self._refresh_btn()

    def _refresh_btn(self):
        ready = self._order_items is not None and self._delivery_items is not None
        if ready:
            self.btn_compare.configure(state="normal", bg=_BLUE, cursor="hand2")
        else:
            self.btn_compare.configure(state="disabled", bg="#9BBFE0", cursor="arrow")

    def _reset_session(self):
        self._order_items    = None
        self._delivery_items = None
        self._zone_order.reset()
        self._zone_delivery.reset()
        self.btn_compare.configure(state="disabled", bg="#9BBFE0", cursor="arrow")
        self.btn_reset.configure(state="disabled")
        self.summary_label.configure(text="")
        self.tree.delete(*self.tree.get_children())

    # ──────────────────────────────────────────────────────────────
    # Vergleich ausführen
    # ──────────────────────────────────────────────────────────────

    def _run_compare(self):
        if self._order_items is None or self._delivery_items is None:
            return
        results = compare(self._order_items, self._delivery_items)
        self._populate(results)

    def _populate(self, results):
        self.tree.delete(*self.tree.get_children())

        n_ok = n_fehlt = n_menge = n_extra = 0

        for r in sorted(results, key=lambda x: _STATUS_SORT.get(x["status"], 9)):
            s = r["status"]
            if s == "OK":
                n_ok    += 1
            elif s == "FEHLT":
                n_fehlt += 1
            elif s == "FALSCHE_MENGE":
                n_menge += 1
            else:
                n_extra += 1

            self.tree.insert("", tk.END, values=(
                r["identifier"],
                r["product"],
                r["ordered_qty"]   if r["ordered_qty"]   > 0 else "—",
                r["delivered_qty"] if r["delivered_qty"]  > 0 else "—",
                _STATUS_LBL.get(s, s),
            ), tags=(_STATUS_TAG.get(s, ""),))

        parts = []
        if n_ok:    parts.append(f"✓ {n_ok} OK")
        if n_fehlt: parts.append(f"✗ {n_fehlt} Fehlend")
        if n_menge: parts.append(f"⚠ {n_menge} Falsche Menge")
        if n_extra: parts.append(f"+ {n_extra} Nicht bestellt")

        self.summary_label.configure(
            text="  ·  ".join(parts) if parts else "Keine Positionen gefunden.",
            foreground=_RED if (n_fehlt or n_menge) else _GREEN,
        )


# ──────────────────────────────────────────────────────────────────────────────
# Interne Hilfsklasse: klickbare Upload-Zone
# ──────────────────────────────────────────────────────────────────────────────

class _UploadZone:
    """Canvas-basierte Upload-Zone mit Klick-zum-Durchsuchen."""

    def __init__(self, parent, title, hint, on_loaded):
        self._hint      = hint
        self._on_loaded = on_loaded   # callback(items)
        self._token     = 0
        self._hovering  = False

        self._icon  = "📂"
        self._text  = hint
        self._color = _MUTED
        self._bg    = _DROP_BG

        icon = "📋" if "BESTELLUNG" in title else "📦"
        self.frame = ttk.LabelFrame(parent, text=f"  {icon}  {title}  ", padding=(4, 4))

        self.canvas = tk.Canvas(self.frame, height=82, highlightthickness=0, cursor="hand2")
        self.canvas.pack(fill=tk.X)

        # Persistente Canvas-Items erstellen (werden nie gelöscht, nur aktualisiert)
        c = self.canvas
        self._bg_item     = c.create_rectangle(0, 0, 1, 1, fill=self._bg, outline="")
        self._border_item = c.create_rectangle(4, 4, 1, 1, fill="",
                                                outline=_DASH, width=2, dash=(9, 5))
        self._icon_item   = c.create_text(0, 0, text=self._icon,
                                           font=("Segoe UI", 18), fill=self._color)
        self._text_item   = c.create_text(0, 0, text=self._text,
                                           font=("Segoe UI", 9), fill=self._color)

        self.canvas.bind("<Configure>", lambda e: self._redraw())
        self.canvas.bind("<Button-1>",  lambda e: self._browse())
        self.canvas.bind("<Enter>",     lambda e: self._set_hover(True))
        self.canvas.bind("<Leave>",     lambda e: self._set_hover(False))

        self._info = ttk.Label(self.frame, text="", font=("Segoe UI", 8), foreground=_MUTED)
        self._info.pack(anchor=tk.W, pady=(2, 0))

    def _redraw(self):
        c = self.canvas
        w, h = c.winfo_width(), c.winfo_height()
        if w < 20:
            return
        # Positionen und Eigenschaften der bestehenden Items aktualisieren
        c.coords(self._bg_item, 0, 0, w, h)
        c.itemconfig(self._bg_item, fill=self._bg)
        border = _BLUE if self._hovering else _DASH
        c.coords(self._border_item, 4, 4, w - 4, h - 4)
        c.itemconfig(self._border_item, outline=border)
        c.coords(self._icon_item, w // 2, h // 2 - 13)
        c.itemconfig(self._icon_item, text=self._icon, fill=self._color)
        c.coords(self._text_item, w // 2, h // 2 + 14)
        c.itemconfig(self._text_item, text=self._text, fill=self._color)

    def _set_hover(self, on):
        self._hovering = on
        self._redraw()

    def _browse(self):
        path = filedialog.askopenfilename(
            title=f"Datei auswählen",
            filetypes=_FILETYPES,
        )
        if path:
            self._load(path)

    def _load(self, filepath):
        self._token += 1
        token = self._token
        self._icon  = "⏳"
        self._text  = "Datei wird geladen…"
        self._color = _MUTED
        self._bg    = _DROP_BG
        self._info.configure(text="")
        self._redraw()

        def _thread():
            try:
                items = parse_file(filepath)
                self.canvas.after(0, lambda: self._done(filepath, items, token))
            except Exception as exc:
                err = str(exc)
                self.canvas.after(0, lambda: self._error(err, token))

        threading.Thread(target=_thread, daemon=True).start()

    def _done(self, filepath, items, token):
        if token != self._token:
            return
        self._icon  = "✅"
        self._text  = f"{len(items)} Positionen geladen"
        self._color = _GREEN
        self._bg    = _DROP_OK
        self._info.configure(text=os.path.basename(filepath), foreground=_MUTED)
        self._redraw()
        self._on_loaded(items)

    def _error(self, msg, token):
        if token != self._token:
            return
        self._icon  = "📂"
        self._text  = self._hint
        self._color = _MUTED
        self._bg    = _DROP_BG
        self._info.configure(text="")
        self._redraw()
        messagebox.showerror("Fehler beim Einlesen", msg)

    def reset(self):
        """Setzt die Zone auf den Ausgangszustand zurück."""
        self._token += 1
        self._icon  = "📂"
        self._text  = self._hint
        self._color = _MUTED
        self._bg    = _DROP_BG
        self._hovering = False
        self._info.configure(text="")
        self._redraw()

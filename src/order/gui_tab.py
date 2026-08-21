"""
OrderBot – GUI-Tab: matched eine Bestellliste (EAN + Order-Menge) gegen
eine Ziel-Liste (beliebige Spalten + EAN) und hängt eine Order-Spalte an.
"""

import os
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from src.order.parser import parse_order_source
from src.order.matcher import read_target_list, apply_order_column
from src.order.exporter import export_order_result
from src.widgets.upload_zone import UploadZone

_BLUE    = "#1B6EC2"
_BLUE_DIS = "#9BBFE0"
_GREEN   = "#16a34a"
_RED     = "#dc2626"
_MUTED   = "#64748B"

_EXCEL_FILETYPES = [
    ("Excel-Dateien", "*.xlsx *.xls"),
    ("Alle Dateien", "*.*"),
]


class OrderTab:
    """Haupt-Widget für den OrderBot-Tab."""

    def __init__(self, parent):
        self._order_lookup = None   # dict[ean, qty], von parse_order_source()
        self._target       = None   # TargetList, von read_target_list()
        self._result       = None   # OrderResult, von apply_order_column()

        frame = ttk.Frame(parent, padding=(16, 12, 16, 4))
        frame.pack(fill=tk.BOTH, expand=True)

        hdr = ttk.Frame(frame)
        hdr.pack(fill=tk.X, pady=(0, 8))
        self.btn_reset = tk.Button(
            hdr,
            text="↺  Neue Order-Prüfung",
            font=("Segoe UI", 9),
            bg="#F1F5F9", fg="#1E293B",
            activebackground="#E2E8F0", activeforeground="#1E293B",
            relief="flat", bd=0, padx=10, pady=5,
            cursor="hand2",
            command=self._reset_session,
            state="disabled",
        )
        self.btn_reset.pack(side=tk.RIGHT, anchor=tk.NE)
        ttk.Label(hdr, text="OrderBot", style="Title.TLabel").pack(anchor=tk.W)
        ttk.Label(
            hdr,
            text="Bestellmengen per EAN in eine Ziel-Liste übernehmen",
            style="Sub.TLabel",
        ).pack(anchor=tk.W)
        ttk.Separator(frame).pack(fill=tk.X, pady=(6, 10))

        zones = ttk.Frame(frame)
        zones.pack(fill=tk.X, pady=(0, 8))
        zones.columnconfigure(0, weight=1)
        zones.columnconfigure(1, weight=1)

        self._zone_source = UploadZone(
            zones,
            title="BESTELLLISTE",
            hint="Bestellliste laden  (EAN + Order-Menge)",
            on_loaded=self._on_source_loaded,
            parse_fn=parse_order_source,
            filetypes=_EXCEL_FILETYPES,
            icon="📋",
        )
        self._zone_source.frame.grid(row=0, column=0, sticky=tk.NSEW, padx=(0, 6))

        self._zone_target = UploadZone(
            zones,
            title="ZIEL-LISTE",
            hint="Ziel-Liste laden  (mit EAN-Spalte)",
            on_loaded=self._on_target_loaded,
            parse_fn=read_target_list,
            filetypes=_EXCEL_FILETYPES,
            icon="📦",
        )
        self._zone_target.frame.grid(row=0, column=1, sticky=tk.NSEW, padx=(6, 0))

        btn_row = ttk.Frame(frame)
        btn_row.pack(pady=(4, 8))
        self.btn_apply = tk.Button(
            btn_row,
            text="   🔗  Order anwenden   ",
            font=("Segoe UI", 12, "bold"),
            bg=_BLUE_DIS, fg="#FFFFFF",
            activebackground="#155599", activeforeground="#FFFFFF",
            relief="flat", bd=0,
            padx=20, pady=11,
            cursor="arrow",
            command=self._run_apply,
            state="disabled",
        )
        self.btn_apply.pack()

        ttk.Separator(frame).pack(fill=tk.X, pady=(0, 8))

        self.summary_label = ttk.Label(frame, text="", font=("Segoe UI", 10, "bold"))
        self.summary_label.pack(anchor=tk.W, pady=(0, 4))

        tbl = ttk.LabelFrame(frame, text="  Ergebnis  ", padding=(6, 6))
        tbl.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(tbl, columns=(), show="headings", height=15, selectmode="browse")
        self.tree.tag_configure("found", background="#dcfce7", foreground="#14532d")
        self.tree.tag_configure("notfound", background="#f1f5f9", foreground="#64748B")

        sb = ttk.Scrollbar(tbl, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        export_row = ttk.Frame(frame)
        export_row.pack(fill=tk.X, pady=(8, 0))
        self.btn_export = tk.Button(
            export_row,
            text="💾  Als Excel exportieren",
            font=("Segoe UI", 10),
            bg=_BLUE_DIS, fg="#FFFFFF",
            activebackground="#155599", activeforeground="#FFFFFF",
            relief="flat", bd=0, padx=14, pady=8,
            cursor="arrow",
            command=self._export,
            state="disabled",
        )
        self.btn_export.pack(side=tk.RIGHT)

    # ──────────────────────────────────────────────────────────────
    # Callbacks von den Upload-Zonen
    # ──────────────────────────────────────────────────────────────

    def _on_source_loaded(self, order_lookup):
        self._order_lookup = order_lookup
        self.btn_reset.configure(state="normal")
        self._refresh_apply_btn()

    def _on_target_loaded(self, target):
        self._target = target
        self.btn_reset.configure(state="normal")
        self._refresh_apply_btn()

    def _refresh_apply_btn(self):
        ready = self._order_lookup is not None and self._target is not None
        if ready:
            self.btn_apply.configure(state="normal", bg=_BLUE, cursor="hand2")
        else:
            self.btn_apply.configure(state="disabled", bg=_BLUE_DIS, cursor="arrow")

    def _reset_session(self):
        self._order_lookup = None
        self._target       = None
        self._result       = None
        self._zone_source.reset()
        self._zone_target.reset()
        self.btn_apply.configure(state="disabled", bg=_BLUE_DIS, cursor="arrow")
        self.btn_export.configure(state="disabled", bg=_BLUE_DIS, cursor="arrow")
        self.btn_reset.configure(state="disabled")
        self.summary_label.configure(text="")
        self.tree["columns"] = ()
        self.tree.delete(*self.tree.get_children())

    # ──────────────────────────────────────────────────────────────
    # Order anwenden
    # ──────────────────────────────────────────────────────────────

    def _run_apply(self):
        if self._order_lookup is None or self._target is None:
            return
        result = apply_order_column(self._target, self._order_lookup)
        self._populate(result)

    def _build_columns(self, headers):
        col_ids = [f"col{i}" for i in range(len(headers))]
        self.tree["columns"] = col_ids
        for col_id, header in zip(col_ids, headers):
            self.tree.heading(col_id, text=header or "—", anchor=tk.W)
            self.tree.column(col_id, width=130, anchor=tk.W, minwidth=60, stretch=True)
        order_col_id = col_ids[-1]
        self.tree.heading(order_col_id, anchor=tk.CENTER)
        self.tree.column(order_col_id, width=110, anchor=tk.CENTER, minwidth=90, stretch=False)
        return col_ids

    def _populate(self, result):
        self._build_columns(result.headers)
        self.tree.delete(*self.tree.get_children())

        for row in result.rows:
            tag = "notfound" if row[-1] == "Nicht gefunden" else "found"
            values = ["" if v is None else v for v in row]
            self.tree.insert("", tk.END, values=values, tags=(tag,))

        parts = [f"✓ {result.n_matched} gefunden"]
        if result.n_not_found:
            parts.append(f"⚠ {result.n_not_found} nicht gefunden")
        self.summary_label.configure(
            text="  ·  ".join(parts),
            foreground=_RED if result.n_not_found else _GREEN,
        )

        self._result = result
        self.btn_export.configure(state="normal", bg=_BLUE, cursor="hand2")

    # ──────────────────────────────────────────────────────────────
    # Export
    # ──────────────────────────────────────────────────────────────

    def _export(self):
        if self._result is None:
            return
        output_path = filedialog.asksaveasfilename(
            title="Order-Ergebnis speichern",
            defaultextension=".xlsx",
            filetypes=[("Excel-Datei", "*.xlsx")],
            initialfile="Order-Ergebnis.xlsx",
        )
        if not output_path:
            return
        try:
            export_order_result(self._result.headers, self._result.rows, output_path)
        except Exception as exc:
            messagebox.showerror("Fehler beim Export", str(exc))
            return
        self._open_file(output_path)

    def _open_file(self, filepath):
        if sys.platform == "win32":
            os.startfile(filepath)
        elif sys.platform == "darwin":
            subprocess.call(["open", filepath])
        else:
            subprocess.call(["xdg-open", filepath])

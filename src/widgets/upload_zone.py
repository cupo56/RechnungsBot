"""
Wiederverwendbare Canvas-basierte Upload-Zone (klickbar) für Datei-Uploads.
Wird von mehreren Tabs verwendet (VergleichsBot, OrderBot, …); die
eigentliche Parse-Logik wird per parse_fn injiziert.
"""

import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

_BLUE    = "#1B6EC2"
_GREEN   = "#16a34a"
_MUTED   = "#64748B"
_DROP_BG = "#EBF3FF"
_DROP_OK = "#F0FDF4"
_DASH    = "#90BEF5"

_DEFAULT_FILETYPES = [
    ("Excel & PDF", "*.xlsx *.xls *.pdf"),
    ("Excel-Dateien", "*.xlsx *.xls"),
    ("PDF-Dateien", "*.pdf"),
    ("Alle Dateien", "*.*"),
]


class UploadZone:
    """Canvas-basierte Upload-Zone mit Klick-zum-Durchsuchen.

    parse_fn(filepath) wird in einem Hintergrund-Thread aufgerufen; das
    Ergebnis (muss len() unterstützen) wird per on_loaded(items) an den
    aufrufenden Tab gemeldet.
    """

    def __init__(self, parent, title, hint, on_loaded, parse_fn, filetypes=None, icon="📂"):
        self._hint      = hint
        self._on_loaded = on_loaded
        self._parse_fn  = parse_fn
        self._filetypes = filetypes or _DEFAULT_FILETYPES
        self._token     = 0
        self._hovering  = False

        self._icon  = icon
        self._text  = hint
        self._color = _MUTED
        self._bg    = _DROP_BG

        self.frame = ttk.LabelFrame(parent, text=f"  {icon}  {title}  ", padding=(4, 4))

        self.canvas = tk.Canvas(self.frame, height=82, highlightthickness=0, cursor="hand2")
        self.canvas.pack(fill=tk.X)

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
            title="Datei auswählen",
            filetypes=self._filetypes,
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
                items = self._parse_fn(filepath)
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

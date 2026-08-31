# Order-Tab (EAN-basierter Order-Merge) — Design

Datum: 2026-08-21
Branch: `feature/order-tab`

## Zweck

Neuer Notebook-Tab "OrderBot", in dem der Nutzer zwei Excel-Listen hochlädt:

1. **Bestellliste** — enthält pro Zeile eine EAN und eine bestellte Menge
   (Spalte "Order"/"Menge"/…).
2. **Ziel-Liste** — ein beliebiger Produktkatalog/Lagerbestand mit einer
   EAN-Spalte, aber ohne Order-Mengen.

Das Feature durchsucht die Ziel-Liste EAN-für-EAN in der Bestellliste und
hängt eine neue Spalte `Order` an, die die bestellte Menge aus der ersten
Liste einträgt. Ergebnis wird im Tab angezeigt und kann als neue `.xlsx`
exportiert werden.

## UI-Layout

Zwei Drop-Zonen nebeneinander (wie beim bestehenden VergleichsBot-Tab):

```
┌──────────────────────────┐  ┌──────────────────────────┐
│      BESTELLLISTE        │  │        ZIEL-LISTE         │
│   (EAN + Order-Menge)    │  │   (EAN, beliebige Spalten) │
└──────────────────────────┘  └──────────────────────────┘

         [ 🔗  Order anwenden ]

┌────────────────────────────────────────────────────────┐
│  Ergebnis: Original-Spalten der Ziel-Liste + "Order"     │
└────────────────────────────────────────────────────────┘

         [ 💾  Als Excel exportieren ]
```

Tab-Titel: `  🔗  OrderBot  `, eingehängt zwischen VergleichsBot und
Provisionsrechnung im Notebook (`src/gui.py`).

## Komponenten

### `src/order/parser.py`

```
parse_order_source(filepath) -> dict[str, int]
```

- Liest die Bestellliste (`.xlsx`/`.xls`), erkennt EAN- und
  Order/Mengen-Spalte per Keyword-Set (wiederverwendet die bestehenden
  `_EAN_KW` / `_QUANTITY_KW` Sets aus `src/compare/parser.py`, die
  "order"/"bestellmenge"/"menge" bereits abdecken).
- Summiert Mengen pro (normalisierter) EAN, falls dieselbe EAN mehrfach
  vorkommt.
- Zeilen ohne EAN oder mit Menge ≤ 0 werden übersprungen (kein Beitrag zum
  Lookup, da ausschließlich per EAN gematcht wird).
- Wirft `ValueError` mit deutscher Meldung, wenn keine EAN- oder
  Mengen-Spalte erkannt wird oder die Datei keine gültigen Zeilen enthält.

### `src/order/matcher.py`

```
read_target_list(filepath) -> TargetList        # headers, rows, __len__ = Zeilenzahl
apply_order_column(target: TargetList, order_lookup: dict[str, int]) -> OrderResult
```

- `read_target_list()` liest die Ziel-Liste **vollständig** (alle
  Original-Spalten, alle Zeilen) via openpyxl, erkennt die Header-Zeile und
  die EAN-Spalte (Suche wie in den bestehenden Parsern, erste 20 Zeilen).
  Wird direkt beim Hochladen der Ziel-Liste-Zone aufgerufen (nicht erst bei
  "Order anwenden"), damit Fehler (keine EAN-Spalte, leere Datei) sofort
  sichtbar werden und die Upload-Zone eine korrekte Zeilenzahl anzeigen kann
  (`TargetList` implementiert `__len__` = Anzahl Datenzeilen, analog zu
  einem `dict`, damit die bestehende `_UploadZone`-Erfolgsmeldung
  `f"{len(items)} Positionen geladen"` unverändert weiterfunktioniert).
- `apply_order_column()` iteriert über die bereits eingelesenen Zeilen: EAN
  normalisieren, in `order_lookup` nachschlagen. Treffer → Menge; kein
  Treffer → String `"Nicht gefunden"`.
- `OrderResult` (dataclass): `headers: list[str]`, `rows: list[list]`
  (Original-Werte + Order-Wert angehängt), `n_matched: int`,
  `n_not_found: int`.
- EAN-Normalisierung als kleine geteilte Hilfsfunktion (z. B.
  `src/order/_ean.py` oder Modulfunktion in `parser.py`, von `matcher.py`
  importiert): Float-EANs wie `401234500000.0` → `"401234500000"`,
  Strip/String-Cast sonst.
- Wirft `ValueError`, wenn keine EAN-Spalte erkannt wird oder die Datei leer
  ist.

### `src/order/exporter.py`

```
export_order_result(headers, rows, output_path)
```

- Schreibt `headers`/`rows` in eine neue `.xlsx` via openpyxl `Workbook`.
- Header-Zeile im Haus-Stil (fett, graue Füllung — analog
  `src/excel/exporter.py` `_HEADER_FILL`/`_BOLD`), Spaltenbreiten grob an
  Inhalt angepasst, `freeze_panes` unter der Header-Zeile.
- Original-Formatierung der Ziel-Liste wird **nicht** übernommen — nur
  Werte, konsistent mit dem bestehenden Excel-Export im Projekt.

### `src/order/gui_tab.py` — `OrderTab`

- Zwei Upload-Zonen (siehe UI-Layout), jeweils mit eigener `parse_fn`:
  - Bestellliste-Zone → `parse_order_source` → Ergebnis (`dict`) in
    `self._order_lookup` gespeichert.
  - Ziel-Liste-Zone → `read_target_list` → Ergebnis (`TargetList`) in
    `self._target` gespeichert (bereits vollständig eingelesen, siehe
    `src/order/matcher.py`).
- Button "🔗 Order anwenden": aktiv sobald beide Zonen geladen sind. Startet
  Hintergrund-Thread, der `apply_order_column(self._target,
  self._order_lookup)` aufruft (reine In-Memory-Verarbeitung, kein
  erneutes Dateilesen).
- Ergebnis-Treeview: Spalten dynamisch aus `OrderResult.headers` aufgebaut
  (im Gegensatz zum VergleichsBot mit festen Spalten). Order-Spalte farblich
  hervorgehoben: grün = gefunden, grau/neutral = "Nicht gefunden".
  Zusammenfassung analog VergleichsBot (`"✓ N gefunden · ⚠ M nicht
  gefunden"`).
- Button "💾 Als Excel exportieren": aktiv sobald Ergebnis vorhanden. Öffnet
  `filedialog.asksaveasfilename`, ruft `export_order_result()`, danach
  `os.startfile()` — gleiches Muster wie `src/provision/gui_tab.py` /
  `src/credit_note/gui_tab.py`.
- Reset-Button ("↺ Neue Order-Prüfung") wie bei VergleichsTab.

### Refactor: `_UploadZone` extrahieren

`_UploadZone` in `src/compare/gui_tab.py` ist aktuell fest an
`parse_file()` aus `src.compare.parser` gekoppelt (Modul-Import, direkter
Aufruf in `_load()`). Für den Order-Tab werden zwei unterschiedliche
Parse-Funktionen benötigt (eine je Zone), daher:

- `_UploadZone` wird nach `src/widgets/upload_zone.py` verschoben und um
  einen Konstruktor-Parameter `parse_fn: Callable[[str], Any]` erweitert
  (ersetzt den hart codierten `parse_file`-Aufruf).
- `src/compare/gui_tab.py` importiert die verschobene Klasse und übergibt
  `parse_fn=parse_file` — reiner Wiring-Change, kein Verhaltensunterschied.
- `src/order/gui_tab.py` nutzt dieselbe Klasse für beide Zonen: einmal mit
  `parse_fn=parse_order_source` (Bestellliste-Zone), einmal mit
  `parse_fn=read_target_list` (Ziel-Liste-Zone). Beide Rückgabewerte
  (`dict`, `TargetList`) unterstützen `len()`, sodass die bestehende
  `_UploadZone`-Erfolgsmeldung unverändert bleibt.

## Datenfluss

1. Bestellliste hochladen → Hintergrund-Thread → `parse_order_source()` →
   `dict[ean, qty]` in `self._order_lookup`.
2. Ziel-Liste hochladen → Hintergrund-Thread → `read_target_list()` →
   `TargetList` in `self._target`.
3. Beide vorhanden → Button "Order anwenden" aktiv.
4. Klick → Hintergrund-Thread → `apply_order_column(self._target,
   self._order_lookup)` → `OrderResult`.
5. `OrderResult` → Treeview befüllen (dynamische Spalten) + Zusammenfassung.
6. Export-Button aktiv → Speichern-Dialog → `export_order_result()` →
   `os.startfile()`.

## Matching-Regeln

- Ausschließlich per EAN (kein SKU/Produktname-Fallback).
- Mehrfache EANs in der Bestellliste werden summiert.
- Mehrfache EANs in der Ziel-Liste werden unabhängig behandelt — jede Zeile
  bekommt denselben nachgeschlagenen Wert (kein Aufteilen der Menge).
- Kein Treffer → `"Nicht gefunden"` (String) in der Order-Spalte.

## Fehlerbehandlung

- Fehlende EAN-Spalte, fehlende Order/Mengen-Spalte (nur Bestellliste),
  leere Datei, keine gültigen Zeilen → `ValueError` mit deutscher Meldung,
  angezeigt via `messagebox.showerror` (gleiches Muster wie
  `src/compare/gui_tab.py` `_UploadZone._error`).
- Kein PDF-Support für diesen Tab (nur `.xlsx`/`.xls` als Input) — Anfrage
  bezog sich ausschließlich auf Excel-Tabellen.

## Testing

Kein automatisiertes Test-Setup im Projekt (siehe `CLAUDE.md`). Manuelle
Verifikation nach Implementierung mit echten Bestell-/Ziel-Excel-Dateien:
Treffer, fehlende EANs, doppelte EANs in beiden Listen, Excel-Export öffnen
und Inhalt prüfen.

## Out of Scope

- Kein PDF-Input für diesen Tab.
- Keine Unterstützung für mehr als 2 Listen (bewusst auf genau 2 Listen
  begrenzt, siehe Design-Entscheidung).
- Keine Übernahme der Original-Formatierung/Styles der Ziel-Liste beim
  Export — nur Werte.

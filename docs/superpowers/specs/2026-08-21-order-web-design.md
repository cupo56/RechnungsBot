# OrderBot Web-Seite — Design

Datum: 2026-08-21
Betrifft: `web/` (separate Next.js/Flask-App, unabhängig von der Tkinter-Desktop-App)

## Zweck

Die Desktop-App (`feature/order-tab`-Branch, bereits fertig und reviewed) hat einen
"OrderBot"-Tab: Bestellliste (EAN + Order-Menge) gegen eine Ziel-Liste (beliebige
Spalten + EAN) matchen, Order-Spalte anhängen, Ergebnis als Excel exportieren.

Diese Spec überträgt dasselbe Feature auf die separate Web-App unter `web/`
(Next.js-Frontend + Flask-Backend, auf Vercel deploybar), damit es per
Browser-Preview getestet werden kann. Die Web-App ist komplett unabhängig von
der Tkinter-App — sie hat eigene Seiten pro Feature (`compare`, `provision`,
`credit-note`, `endkunde`, `database`) und einen eigenen Flask-Backend-Prozess
(`web/api/index.py`), der Funktionen aus `src/` (Python) wiederverwendet.

**Wichtig:** `web/vercel.json`s `buildCommand` kopiert bei jedem Vercel-Build
automatisch das aktuelle Repo-Root-`src/` nach `web/api/src/`
(`cp -r ../src ./api/src`). Die bereits gebauten Module `src/order/parser.py`,
`src/order/matcher.py`, `src/order/exporter.py` sind also ohne manuellen
Sync-Schritt im Flask-Backend verfügbar. `src/order/gui_tab.py` und
`src/widgets/upload_zone.py` (Tkinter-spezifisch) werden vom Flask-Backend
nicht importiert.

## Architektur

**Backend** — zwei neue Flask-Routen in `web/api/index.py`, im selben Stil wie
die bestehenden `/api/parse`, `/api/generate`, `/api/provision`,
`/api/credit-note` (JSON+Base64-Datei-Transport statt multipart — siehe
Kommentar in `index.py` zu Vercels WAF; Bearer-Shared-Secret-Auth via
`_API_SHARED_SECRET`, bereits global vor jeder Route geprüft):

1. `POST /api/order/apply`
   - Body: `{source_filename, source_file_base64, target_filename, target_file_base64}`
   - Beide Dateien in Temp-Dateien schreiben, dann:
     `parse_order_source(source_path)` → `order_lookup`
     `read_target_list(target_path)` → `target`
     `apply_order_column(target, order_lookup)` → `OrderResult`
   - Response: `{headers, rows, n_matched, n_not_found}` — `rows`-Zellwerte
     werden über eine kleine `_json_safe(value)`-Hilfsfunktion geschickt
     (datetime/date → ISO-String, sonst unverändert), damit `jsonify` nicht an
     nicht-serialisierbaren Excel-Zellwerten (z. B. Datumsfeldern) scheitert.
   - Fehlerbehandlung: `ValueError` (z. B. keine EAN-Spalte gefunden) → 400 mit
     der deutschen Fehlermeldung aus der Exception, sonstige Exceptions →
     generische deutsche Fehlermeldung + `detail` (gleiches Muster wie
     `/api/parse`). Temp-Dateien werden in einem `finally`-Block gelöscht.

2. `POST /api/order/export`
   - Body: `{headers, rows}` (das von `/api/order/apply` gelieferte Ergebnis,
     unverändert zurückgeschickt)
   - Ruft `export_order_result(headers, rows, tmp_path)`, liest die Datei
     zurück, Base64-kodiert.
   - Response: `{xlsx_base64, filename: "Order-Ergebnis.xlsx"}`
   - Temp-Datei wird in einem `finally`-Block gelöscht.

Beide Routen importieren die benötigten `src.order.*`-Funktionen lokal
innerhalb der Route-Funktion (gleiche Konvention wie bestehende Routen, z. B.
`from src.pdf_input.own_invoice_parser import ...` in `/api/parse`).

**Frontend** — neue Seite `web/app/order/page.js`, Client-Component
(`'use client'`), eigenständig (keine gemeinsamen Hooks wie
`useCustomerTemplates` nötig, da kein Kunden-/Konfigurationsbezug):

- Header-Block im bestehenden Stil (`.app-container`, `.app-header`,
  `.header-title`, `.header-subtitle`) — Titel "🔗 OrderBot", Subtitle
  "Bestellmengen per EAN in eine Ziel-Liste übernehmen" (identisch zum
  Desktop-Tab).
- Zwei Drop-Zonen nebeneinander (bestehende `.drop-zone`/`.drop-zone-icon`/
  `.drop-zone-text`/`.drop-zone-hint`/`.drop-zone.loaded`-Klassen aus
  `globals.css`, gleiches Muster wie die Datei-Upload-Logik in `page.js`:
  `FileReader`/`ArrayBuffer` → Base64 client-seitig, kein serverseitiger aber
  **kein sofortiges Parsen** pro Datei). Jede Zone hält lokal
  `{filename, file_base64}` im State.
- "🔗 Order anwenden"-Button: aktiv sobald beide Dateien im State sind. Ein
  `fetch('/api/order/apply', ...)`-Call (mit `apiHeaders()` aus
  `utils/apiAuth.js`) mit beiden Dateien. Bei Erfolg: Ergebnis-State
  `{headers, rows, n_matched, n_not_found}` setzen. Bei Fehler: Fehlermeldung
  über den bestehenden `useToast`-Hook anzeigen.
- Ergebnis-Tabelle: `.table-section`/`.table-wrapper`/`.data-table` (gleiche
  Klassen wie die bestehende Positionstabelle), Spalten dynamisch aus
  `headers` gerendert. Order-Spalte (letzte Spalte) farblich markiert:
  gefunden → `--success-600`-Textfarbe, "Nicht gefunden" → `--danger-500`
  bzw. neutral (bestehende CSS-Variablen, keine neuen Farben einführen).
  Zusammenfassung über der Tabelle: "✓ N gefunden" / "⚠ M nicht gefunden"
  (identischer Text wie Desktop).
- "💾 Als Excel exportieren"-Button: aktiv sobald ein Ergebnis vorhanden ist.
  Ruft `/api/order/export` mit `{headers, rows}`, erhält `xlsx_base64`, löst
  Download über denselben `data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,...`
  + `<a download>`-Trick aus, der bereits für PDF-Downloads in `page.js`
  verwendet wird (Zeilen um 539–551).
- "↺ Neue Order-Prüfung"-Button: setzt beide Datei-States, Ergebnis-State und
  Toast zurück (mirrors Desktop-Reset).

**Navigation** — `web/components/Navigation.js`: neuer Eintrag
`{ href: '/order', label: '🔗 Order', desc: 'Bestellmengen per EAN übernehmen' }`,
positioniert zwischen `/compare` ("🔍 Vergleich") und `/provision`
("💰 Provision") — spiegelt die Tab-Reihenfolge der Desktop-App.

## Abweichungen vom Desktop-OrderBot (bewusst, bereits abgestimmt)

- **Kein sofortiges Parsen pro Datei beim Hochladen.** Am Desktop parst jede
  Upload-Zone die Datei sofort (Hintergrund-Thread) und zeigt "N Positionen
  geladen" oder einen Fehler an. Für die Web-Version werden beide Dateien nur
  client-seitig zwischengespeichert; Validierungsfehler (z. B. keine
  EAN-Spalte) werden erst beim Klick auf "Order anwenden" sichtbar. Grund:
  1 API-Call statt 3 separate Endpunkte — einfacher für einen ersten Web-MVP.
- **Kein `os.startfile()`/plattformspezifisches Öffnen** — im Browser läuft
  der Download über den bestehenden `data:...;base64` + `<a download>`-Trick,
  wie bei den PDF-Exports in `page.js`.
- Matching-Logik, EAN-Normalisierung, "Nicht gefunden"-Sentinel (`NOT_FOUND`
  aus `src/order/matcher.py`) und Excel-Export-Stil sind identisch zur
  Desktop-Version — reine Wiederverwendung der bereits reviewten
  `src/order/{parser,matcher,exporter}.py`-Module, keine Logik-Duplikation.

## Fehlerbehandlung

Identisch zum bestehenden `/api/parse`-Muster: `ValueError` aus den
`src.order`-Modulen (z. B. "Konnte keine EAN-Spalte... erkennen") wird 1:1 als
400-Fehlermeldung durchgereicht; unerwartete Exceptions ergeben eine
generische deutsche Fehlermeldung mit technischem `detail`-Feld (das Frontend
zeigt laut bestehendem Muster ggf. nur die freundliche Meldung an).

## Testing

Kein automatisiertes Test-Setup in diesem Repo (auch für die Web-App nicht
vorhanden). Verifikation: lokal `vercel dev` bzw. direkter Funktionsaufruf der
neuen Flask-Routen mit einem kleinen Python-Skript, danach Vercel-Preview-Deploy
und manueller Test durch den Nutzer im Browser.

## Out of Scope

- Keine Änderungen an der Tkinter-Desktop-App in diesem Schritt (die ist
  bereits fertig, siehe `2026-08-21-order-tab-design.md`).
- Keine Portierung der sofortigen Pro-Datei-Validierung (siehe Abweichungen
  oben) — kann bei Bedarf als Folge-Iteration ergänzt werden.
- Keine Anpassung der `web/api/src/`-Sync-Strategie — der bestehende
  Build-Command-Mechanismus reicht aus.

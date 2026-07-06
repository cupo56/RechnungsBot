# Analyse: `web/`-App (Stand 2026-06-24)

Next.js 16 (App Router) Frontend + Flask-Backend (Python, als Vercel Function über `api/index.py`).
Vier aktive Seiten (Rechnung, Provision, Gutschrift, Datenbank) plus ein Stub für „Vergleich". Die
PDF-/Excel-Logik in `web/api/src/` ist eine Kopie von `../src` (Root), synchronisiert per
`postinstall`-Skript bzw. `buildCommand`.

## Sicherheit (wichtigster Punkt)

1. **Offener SSRF-Proxy in `app/api/database/route.js`.**
   Die Route nimmt `api_url` direkt vom Client entgegen und macht damit einen serverseitigen
   `fetch()` — ungeprüft, gegen jede beliebige URL. Wer die Vercel-URL kennt, kann den Server als
   Proxy missbrauchen, um beliebige Hosts (auch interne Adressen) anzusprechen.
   → Mindestens auf eine Allowlist beschränken, idealerweise `api_url` serverseitig per Env-Var
   statt clientseitig konfigurieren.

2. **Keine Authentifizierung auf irgendeiner API-Route**
   (`/api/parse`, `/api/generate`, `/api/provision`, `/api/credit-note`, `/api/database`). Wer die
   Vercel-URL kennt, kann beliebig Rechnungen erzeugen oder die DB-Proxy-Route missbrauchen — kein
   Login, kein serverseitiger API-Key-Check.

3. **`db_api_key` liegt im Klartext in `localStorage`** und wird bei jedem Request im JSON-Body
   mitgeschickt (statt z. B. als Header). Anfällig für Diebstahl per XSS; das Passwortfeld in der
   UI ändert daran nichts.

4. **Fehlerdetails (`detail`) werden an den Client durchgereicht** (`api/index.py`) — interne
   Exception-Messages/Pfade landen im Frontend statt nur in Server-Logs.

## Code-Qualität / Duplizierung

5. **`loadConfig` / `saveConfig` / `formatCurrency` / `formatNumber` / `todayStr` sind identisch
   kopiert** in `app/page.js`, `app/provision/page.js` und `app/credit-note/page.js` (je
   ~600–950 Zeilen Dateien). Klarste Verbesserung: Auslagern nach `app/utils/config.js` und
   `app/utils/format.js`.

6. **`app/page.js` ist eine 947-Zeilen-Monolith-Komponente** — State, Parsing, Tabelle, Settings,
   Customer-Panel, Templates alles in einer Funktion. Aufteilen in Hooks (`useInvoiceConfig`,
   `useItemsTable`) und Unterkomponenten (`SettingsPanel`, `CustomerPanel`, `ItemsTable`) würde die
   Wartbarkeit deutlich verbessern, ohne Verhalten zu ändern.

7. **`/compare` ist nur ein „im Aufbau"-Stub** (22 Zeilen). Falls nicht mehr aktuell geplant,
   könnte der Nav-Link raus — sonst wäre das die naheliegende nächste Seite zum Fertigstellen,
   analog zum bereits vorhandenen Python-Modul `src/compare/`.

## Robustheit / Betrieb

8. **Kein Limit auf Upload-Größe** beim Base64-JSON-Upload (`/api/parse`) — große Excel-/PDF-Dateien
   könnten an Vercels Body-Size-Limit (Standard 4.5 MB) scheitern, ohne dass die UI das vorab prüft
   oder eine klare Fehlermeldung zeigt.

9. **`maxDuration: 30` in `vercel.json`** für PDF-Generierung — bei sehr großen Bestellungen
   (viele hundert Positionen, mehrseitige PDFs mit ReportLab) potenziell knapp. Mit Fluid Compute
   sind inzwischen bis 300 s ohne Mehrkosten möglich — lohnt sich hochzusetzen.

10. **`web/api/src` ist eine Kopie von `../src`**, synchronisiert nur über `postinstall` /
    `buildCommand`. Wer lokal an `src/` arbeitet und `npm run dev` nicht neu ausführt, debuggt
    gegen eine veraltete Kopie — leicht zu übersehen.

## Empfehlung für den nächsten Schritt

- Risikoarm zuerst: Punkt 5 (Config/Format-Duplizierung auslagern) — kein Verhaltensrisiko.
- Danach Punkt 1 (SSRF-Proxy absichern) — sicherheitsrelevant und mit klarer Lösung (Allowlist
  oder Server-Env-Var).

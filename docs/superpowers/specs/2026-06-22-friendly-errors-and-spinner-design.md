# Freundliche Fehlermeldungen + Spinner-Konsistenz (Web-App)

Datum: 2026-06-22

## Problem

Bei unerwarteten Backend-Fehlern (Programmfehler, keine Validierungsfehler) zeigt die
Web-App aktuell den rohen Python-Exception-Text 1:1 im Status/Toast an, z.B.
`Unerwarteter Fehler: No module named 'src'`. Das ist für Endnutzer unverständlich.

Gleichzeitig will der Projektinhaber (technischer Laie, debuggt aber selbst mit
Unterstützung) den technischen Fehler weiterhin sehen können, um Probleme zu
analysieren — er soll nur nicht die einzige Information sein, die der Nutzer bekommt.

Zusätzlich: Der Excel/PDF-Upload zeigt während des Ladens ein statisches ⏳-Emoji,
während der "Rechnung erstellen"-Button einen echten animierten Spinner
(`<span className="spinner">`) verwendet. Inkonsistent.

## Scope

Betroffen: die vier Flask-Routen in `web/api/index.py` (`/api/parse`, `/api/generate`,
`/api/provision`, `/api/credit-note`) und die zugehörigen Frontend-Seiten
(`web/app/page.js`, `web/app/credit-note/page.js`, `web/app/provision/page.js`).

**Out of scope:** `web/app/database/page.js` und die zugehörige PHP-Backend-Route
(`/api/database` → `server/api.php`). Andere Response-Struktur (PHP, nicht Flask),
und Änderungen am PHP-Server erfordern ein manuelles Re-Upload zu World4You, das hier
nicht automatisiert ist. Bleibt für eine spätere Iteration.

## Design

### Backend (`web/api/index.py`)

Neue kleine Helper-Funktion:

```python
def _error_response(friendly, status=500, detail=None):
    body = {"error": friendly}
    if detail:
        body["detail"] = detail
    return jsonify(body), status
```

Pro Route:

- **`/api/parse`**: Der bestehende `except ValueError` Zweig (Spaltenerkennung,
  "Keine Positionen gefunden" etc.) bleibt unverändert — die Meldungen sind bereits
  spezifisch und verständlich, kein technischer Zusatz nötig.
  Der `except Exception` Zweig (aktuell `"Unerwarteter Fehler: {e}"`, Status 500)
  wird zu:
  `_error_response("Die Datei konnte nicht eingelesen werden. Bitte prüfe das Dateiformat oder versuche es erneut.", detail=str(e))`

- **`/api/generate`**: `excel`/`pdf_input`-Parser werden hier nicht mehr aufgerufen,
  d.h. alle Exceptions in dieser Route sind unerwartet (keine ValueError-Sonderfälle
  in `invoice.py`/`delivery_note.py`). `except Exception` wird zu:
  `_error_response("Beim Erstellen der Rechnung/des Lieferscheins ist ein Fehler aufgetreten.", detail=str(e))`

- **`/api/provision`**: analog:
  `_error_response("Beim Erstellen der Provisionsrechnung ist ein Fehler aufgetreten.", detail=str(e))`

- **`/api/credit-note`**: analog:
  `_error_response("Beim Erstellen der Gutschrift ist ein Fehler aufgetreten.", detail=str(e))`

Response-Form bei unerwarteten Fehlern künftig:
`{"error": "<freundlicher Satz>", "detail": "<technischer Text, z.B. 'KeyError: date'>"}`

Bei erwarteten Fehlern (400, ValueError) bleibt die Form `{"error": "<text>"}` wie bisher
(kein `detail`-Feld).

### Frontend (alle drei Seiten: `page.js`, `credit-note/page.js`, `provision/page.js`)

1. **Fehler-Objekt mit Detail anreichern.** Überall, wo aktuell
   `throw new Error(errData.error || ...)` steht, wird zusätzlich `detail` an das
   Error-Objekt gehängt, bevor es geworfen wird:
   ```js
   const err = new Error(errData.error || `Fehler ${resp.status}`);
   err.detail = errData.detail;
   throw err;
   ```

2. **Catch-Blöcke** setzen `detail` zusätzlich in den Status:
   ```js
   } catch (err) {
     setStatus({ text: `Fehler: ${err.message}`, type: 'error', detail: err.detail });
     setToast({ text: `❌ ${err.message}`, type: 'error' });
   }
   ```
   Der Toast zeigt weiterhin nur die freundliche Kurzfassung (bleibt unverändert,
   4-Sekunden-Anzeige ist zu kurz für technische Details).

3. **Statusleiste** rendert die zweite Zeile nur, wenn `status.detail` gesetzt ist:
   ```jsx
   <span className="status-text">{status.text}</span>
   {status.detail && (
     <span className="status-detail">Technisch: {status.detail}</span>
   )}
   ```
   Betrifft die drei `status-bar`-Blöcke in `page.js` (~Zeile 856-864),
   `credit-note/page.js` (~Zeile 612-615) und `provision/page.js` (~Zeile 611-614).

4. **Neue CSS-Klasse** `.status-detail` in `web/app/globals.css`, direkt nach der
   bestehenden `.status-bar`-Regel:
   ```css
   .status-detail {
     font-size: 0.7rem;
     color: var(--text-muted);
     flex-basis: 100%;
     margin-top: 2px;
   }
   ```
   `.status-bar` ist `display: flex` ohne `flex-wrap`; dafür muss `.status-bar`
   zusätzlich `flex-wrap: wrap` bekommen, damit `.status-detail` (mit
   `flex-basis: 100%`) in eine neue Zeile umbricht, statt den Platz neben
   `status-text` zu beanspruchen.

### Spinner-Konsistenz (Bonus)

In `page.js`, Drop-Zone-Icon (~Zeile 562-564): das statische `⏳` durch den gleichen
`<span className="spinner">` ersetzen, der auch beim "Rechnung erstellen"-Button
verwendet wird, wenn `loading === true`:
```jsx
<span className="drop-zone-icon">
  {loading ? <span className="spinner"></span> : loadedFile ? '✅' : '📂'}
</span>
```

## Out of scope / nicht Teil dieser Iteration

- `database/page.js` (PHP-Backend, andere Response-Struktur)
- Inline-Feldvalidierung (rote Rahmen pro Feld) — war ursprünglich auch als Idee im
  Raum, aber nicht Teil dieser konkreten Anfrage
- Format-Validierung (z.B. numerische Range-Checks bei "Aufschlag %")

## Testing

- Lokal: Flask-Test-Client gegen `/api/generate` mit fehlendem Pflichtfeld aufrufen,
  prüfen dass Response `{"error": "...", "detail": "..."}` enthält.
- Lokal: `/api/parse` mit kaputter Excel-Datei (führt zu echtem Crash, nicht
  ValueError) aufrufen, prüfen dass `detail` gesetzt ist und `error` generisch/freundlich
  ist; mit Excel ohne "Order"-Spalte aufrufen, prüfen dass `error` weiterhin die
  spezifische Meldung ist und `detail` fehlt.
- Browser: einen Fehler manuell auslösen (z.B. Server kurz neu deployen während
  Request läuft, oder ungültige Daten senden) und prüfen, dass Statusleiste beide
  Zeilen zeigt.
- Browser: Excel-Upload beobachten, Spinner dreht sich statt statischem Emoji.

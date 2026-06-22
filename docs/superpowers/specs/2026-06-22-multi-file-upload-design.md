# Mehrere Excel-/PDF-Dateien hochladen (Web-App)

Datum: 2026-06-22

## Problem

Aktuell kann auf der Rechnungs-Seite der Web-App (`web/app/page.js`) nur eine einzelne
Excel- oder PDF-Datei pro Sitzung geladen werden (`handleFileUpload`, `loadedFile`-State).
Wird eine zweite Datei hochgeladen, ersetzt sie die erste vollständig
(`setItems(parsed)`). Der Nutzer will Positionen aus mehreren Lieferanten-Dateien
(Excel und/oder PDF, beliebig gemischt) in einer Sitzung sammeln, um daraus eine
gemeinsame Rechnung zu erstellen.

## Scope

Betroffen: `web/app/page.js` (Upload-Flow, State, Drop-Zone-UI, Datei-Liste).

**Out of scope:**
- Backend (`web/api/index.py`, `/api/parse`) — bleibt unverändert, wird weiterhin pro
  Datei einzeln aufgerufen.
- Desktop-App (`src/gui.py`) — bekommt dasselbe Verhalten in einem separaten,
  nachfolgenden Schritt (eigene Spec).
- Zusammenführen gleicher Positionen (gleiche EAN aus zwei Dateien): bleibt bewusst
  getrennt, jede Datei liefert ihre Positionen als eigene Zeilen.
- Rechnungs-/Lieferschein-Generierung (`/api/generate`, `/api/provision`,
  `/api/credit-note`) — verarbeitet weiterhin eine flache Item-Liste, unabhängig von der
  Anzahl der Quelldateien.

## Design

### Datenmodell

- Jedes geparste Item bekommt ein zusätzliches Feld `_fileId` (string, z.B. via
  `crypto.randomUUID()`), das die Quelldatei markiert.
- Manuell hinzugefügte Zeilen (`addManualRow`) bekommen kein `_fileId` (`undefined`) und
  sind von der dateiweisen Entfernung nicht betroffen.
- Neuer State `loadedFiles` ersetzt den bisherigen einzelnen `loadedFile`-String:
  ```js
  // { id, name, count, status: 'ok' | 'error', error? }
  const [loadedFiles, setLoadedFiles] = useState([]);
  ```

### Upload-Flow

`handleFileUpload(file)` wird zu `handleFilesUpload(fileList)` (nimmt ein Array/FileList
entgegen):

1. Dateityp-Filter wie bisher (`.xlsx`, `.xls`, `.pdf`) — ungültige Dateien werden
   sofort übersprungen und per Toast gemeldet, ohne den restlichen Ablauf zu stoppen.
2. Für jede gültige Datei sequenziell (nicht parallel, um Status-Updates "Datei X von
   Y" sauber anzeigen zu können):
   - Status: `Datei {i} von {n} wird eingelesen… ({file.name})`
   - `POST /api/parse` wie bisher (unverändert).
   - Erfolg: Items mit neuem `_fileId` taggen, an `items` anhängen; Eintrag
     `{ id, name: file.name, count: parsed.length, status: 'ok' }` an `loadedFiles`
     anhängen.
   - Fehler: kein Item übernehmen; Eintrag
     `{ id, name: file.name, count: 0, status: 'error', error: message }` an
     `loadedFiles` anhängen; weiter mit der nächsten Datei (kein Abbruch).
3. Abschluss-Toast fasst zusammen, z.B. `✅ 4 Dateien geladen (18 Positionen)` bzw. bei
   Teil-Fehlern `⚠️ 3 von 4 Dateien geladen — 1 fehlgeschlagen`.
4. `setLoading(false)` erst nach Verarbeitung aller Dateien.

Da `items` weiterhin angehängt (statt ersetzt) wird, funktioniert ein erneuter Drop/Klick
nach dem ersten Upload genauso wie der erste — es kommen einfach weitere Positionen und
ein weiterer `loadedFiles`-Eintrag hinzu.

### Drop-Zone

- `<input type="file" multiple accept=".xlsx,.xls,.pdf">`
- `onDrop`: `e.dataTransfer.files` als Array übernehmen (`Array.from(...)`) statt nur
  `[0]`, an `handleFilesUpload` übergeben.
- `onFileChange`: `Array.from(e.target.files)` an `handleFilesUpload` übergeben.
- Solange `items.length === 0` zeigt die Zone den bisherigen Hinweistext
  ("Excel- oder PDF-Datei(en) hierher ziehen…", Text leicht angepasst auf Plural).
- Nach dem ersten erfolgreichen Upload bleibt die Zone aktiv und nimmt weitere Drops an
  (kompakter Zustand wie bisher bei `loaded`, aber Text zeigt Gesamtzahl:
  `{n} Dateien · {items.length} Positionen geladen — weitere Dateien hier ablegen`).
- Der bisherige Reset-Button "↺ Neue Datei laden" wird zu "↺ Alles zurücksetzen"
  (Funktion `resetSession` leert `items` **und** `loadedFiles`).

### Datei-Liste UI

Neue kleine Liste unterhalb der Drop-Zone, nur sichtbar wenn `loadedFiles.length > 0`:

```jsx
<div className="loaded-files-list">
  {loadedFiles.map(f => (
    <div key={f.id} className={`loaded-file-row ${f.status === 'error' ? 'error' : ''}`}>
      <span className="loaded-file-name">{f.name}</span>
      <span className="loaded-file-count">
        {f.status === 'error' ? f.error : `${f.count} Positionen`}
      </span>
      <button className="loaded-file-remove" onClick={() => removeFile(f.id)} title="Datei entfernen">🗑</button>
    </div>
  ))}
</div>
```

`removeFile(fileId)`:
```js
const removeFile = (fileId) => {
  setLoadedFiles(prev => prev.filter(f => f.id !== fileId));
  setItems(prev => prev.filter(it => it._fileId !== fileId));
};
```

Fehlerhafte Einträge (`status: 'error'`) lassen sich genauso per 🗑 aus der Liste
entfernen (sie haben sowieso keine zugehörigen Items).

### Rechnungserstellung

Unverändert. `generateInvoice` baut `invoiceItems` weiterhin explizit als
`{ ean, product, quantity: qty, unit_price: unit }` — `_fileId` wird dabei nicht
übernommen und taucht im an `/api/generate` gesendeten Payload nicht auf.

## Testing

Keine automatisierten Tests im Projekt. Manuelle Verifikation lokal (`npm run dev` in
`web/`):
- Zwei Excel-Dateien nacheinander per Klick-Dialog (Mehrfachauswahl) laden → beide
  Positionsmengen erscheinen in der Tabelle, Datei-Liste zeigt beide Einträge.
- Mehrere Dateien gleichzeitig per Drag & Drop ablegen → alle werden sequenziell
  verarbeitet, Status zeigt Fortschritt "Datei X von Y".
- Eine gültige Excel-Datei + eine PDF-Datei mit unbekanntem Format mischen → die gültige
  Datei wird trotzdem geladen, die fehlerhafte erscheint in der Liste mit Fehlertext statt
  den ganzen Vorgang abzubrechen.
- Eine Datei aus der Liste entfernen → nur ihre Positionen verschwinden aus der Tabelle,
  übrige Dateien/Positionen bleiben erhalten.
- Manuell hinzugefügte Zeile (➕ Neue Zeile) bleibt nach Entfernen einer Datei erhalten.
- Rechnung aus den zusammengeführten Positionen erstellen → PDF enthält alle Positionen
  aus allen geladenen Dateien.

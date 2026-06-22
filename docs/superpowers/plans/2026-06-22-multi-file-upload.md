# Multi-File Upload Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the web app's invoice page accept multiple Excel/PDF files (via drag & drop or the file dialog) in one session, merge their parsed positions into the existing items table, and show a small per-file list (with item counts and a remove button) so a combined invoice can be built from several supplier files.

**Architecture:** `web/app/page.js` gains a `loadedFiles` state array (replacing the single `loadedFile` string) and a `handleFilesUpload(fileList)` function that calls the existing, unmodified `/api/parse` endpoint once per file, sequentially, tagging each returned item with a `_fileId` so a whole file's items can be removed later. The drop zone and file `<input>` get `multiple` support; a new list below the drop zone renders one row per loaded file.

**Tech Stack:** Next.js/React (frontend only — no backend or Python changes). No test framework in this repo — verification is manual (CLAUDE.md confirms "There are no automated tests in this project").

Reference spec: `docs/superpowers/specs/2026-06-22-multi-file-upload-design.md`

---

### Task 1: Upload logic & state

**Files:**
- Modify: `web/app/page.js:82-84` (state hooks)
- Modify: `web/app/page.js:87` (initial status text)
- Modify: `web/app/page.js:211-246` (`handleFileUpload`)
- Modify: `web/app/page.js:248-262` (drag & drop handlers)
- Modify: `web/app/page.js:264-270` (`resetSession`)

- [ ] **Step 1: Replace the `loadedFile` state with `loadedFiles`**

Currently:

```js
  // --- State: Items & File ---
  const [items, setItems] = useState([]);
  const [loadedFile, setLoadedFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
```

Change to:

```js
  // --- State: Items & File ---
  const [items, setItems] = useState([]);
  const [loadedFiles, setLoadedFiles] = useState([]); // [{ id, name, count, status: 'ok'|'error', error? }]
  const [dragOver, setDragOver] = useState(false);
```

- [ ] **Step 2: Update the initial status text to plural (for consistency with the new `resetSession` text)**

Currently:

```js
  const [status, setStatus] = useState({ text: 'Bereit — Excel-Datei laden um zu beginnen.', type: 'idle' });
```

Change to:

```js
  const [status, setStatus] = useState({ text: 'Bereit — Excel- oder PDF-Datei(en) laden um zu beginnen.', type: 'idle' });
```

- [ ] **Step 3: Replace `handleFileUpload` with `parseOneFile` + `handleFilesUpload`**

Currently:

```js
  // ─── File Upload / Parse ──────────────────────────────
  const handleFileUpload = useCallback(async (file) => {
    if (!file) return;
    const ext = file.name.toLowerCase();
    if (!ext.endsWith('.xlsx') && !ext.endsWith('.xls') && !ext.endsWith('.pdf')) {
      setStatus({ text: 'Bitte eine Excel- (.xlsx) oder PDF-Datei laden.', type: 'error' });
      return;
    }

    setLoading(true);
    setStatus({ text: `${file.name} wird eingelesen…`, type: 'loading' });

    try {
      const formData = new FormData();
      formData.append('file', file);

      const resp = await fetch('/api/parse', { method: 'POST', body: formData });
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({ error: `HTTP ${resp.status}` }));
        const uploadErr = new Error(errData.error || `Fehler ${resp.status}`);
        uploadErr.detail = errData.detail;
        throw uploadErr;
      }
      const data = await resp.json();
      const parsed = data.items || [];
      setItems(parsed);
      setLoadedFile(file.name);
      setStatus({ text: `${parsed.length} Positionen aus '${file.name}' geladen.`, type: 'success' });
      setToast({ text: `✅ ${parsed.length} Positionen geladen`, type: 'success' });
    } catch (err) {
      setStatus({ text: `Fehler: ${err.message}`, type: 'error', detail: err.detail });
      setToast({ text: `❌ ${err.message}`, type: 'error' });
    } finally {
      setLoading(false);
    }
  }, []);
```

Change to:

```js
  // ─── File Upload / Parse ──────────────────────────────
  const parseOneFile = useCallback(async (file) => {
    const formData = new FormData();
    formData.append('file', file);

    const resp = await fetch('/api/parse', { method: 'POST', body: formData });
    if (!resp.ok) {
      const errData = await resp.json().catch(() => ({ error: `HTTP ${resp.status}` }));
      const uploadErr = new Error(errData.error || `Fehler ${resp.status}`);
      uploadErr.detail = errData.detail;
      throw uploadErr;
    }
    const data = await resp.json();
    return data.items || [];
  }, []);

  const handleFilesUpload = useCallback(async (fileList) => {
    const files = Array.from(fileList || []);
    if (!files.length) return;

    const valid = [];
    for (const file of files) {
      const name = file.name.toLowerCase();
      if (name.endsWith('.xlsx') || name.endsWith('.xls') || name.endsWith('.pdf')) {
        valid.push(file);
      } else {
        setToast({ text: `❌ ${file.name}: nicht unterstütztes Format`, type: 'error' });
      }
    }
    if (!valid.length) return;

    setLoading(true);
    let okCount = 0;
    let errCount = 0;
    let addedItemCount = 0;

    for (let i = 0; i < valid.length; i++) {
      const file = valid[i];
      setStatus({ text: `Datei ${i + 1} von ${valid.length} wird eingelesen… (${file.name})`, type: 'loading' });

      const fileId = crypto.randomUUID();
      try {
        const parsed = await parseOneFile(file);
        const tagged = parsed.map(it => ({ ...it, _fileId: fileId }));
        setItems(prev => [...prev, ...tagged]);
        setLoadedFiles(prev => [...prev, { id: fileId, name: file.name, count: tagged.length, status: 'ok' }]);
        okCount += 1;
        addedItemCount += tagged.length;
      } catch (err) {
        setLoadedFiles(prev => [...prev, { id: fileId, name: file.name, count: 0, status: 'error', error: err.message }]);
        errCount += 1;
      }
    }

    setLoading(false);
    if (errCount === 0) {
      setStatus({ text: `${addedItemCount} Positionen aus ${okCount} Datei(en) geladen.`, type: 'success' });
      setToast({ text: `✅ ${okCount} Datei(en) geladen (${addedItemCount} Positionen)`, type: 'success' });
    } else {
      const allFailed = okCount === 0;
      setStatus({ text: `${okCount} von ${valid.length} Dateien geladen — ${errCount} fehlgeschlagen.`, type: allFailed ? 'error' : 'success' });
      setToast({ text: `⚠️ ${okCount} von ${valid.length} Dateien geladen — ${errCount} fehlgeschlagen`, type: 'error' });
    }
  }, [parseOneFile]);
```

- [ ] **Step 3: Update drag & drop / file-input handlers to pass through multiple files**

Currently:

```js
  // ─── Drag & Drop ──────────────────────────────────────
  const onDragOver = (e) => { e.preventDefault(); setDragOver(true); };
  const onDragLeave = () => setDragOver(false);
  const onDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer?.files?.[0];
    if (file) handleFileUpload(file);
  };
  const onBrowse = () => fileInputRef.current?.click();
  const onFileChange = (e) => {
    const file = e.target.files?.[0];
    if (file) handleFileUpload(file);
    e.target.value = '';
  };
```

Change to:

```js
  // ─── Drag & Drop ──────────────────────────────────────
  const onDragOver = (e) => { e.preventDefault(); setDragOver(true); };
  const onDragLeave = () => setDragOver(false);
  const onDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer?.files?.length) handleFilesUpload(e.dataTransfer.files);
  };
  const onBrowse = () => fileInputRef.current?.click();
  const onFileChange = (e) => {
    if (e.target.files?.length) handleFilesUpload(e.target.files);
    e.target.value = '';
  };
```

- [ ] **Step 4: Update `resetSession` and add `removeFile`**

Currently:

```js
  // ─── Reset Session ────────────────────────────────────
  const resetSession = () => {
    setItems([]);
    setLoadedFile(null);
    setSelectAllIndiv(false);
    setStatus({ text: 'Bereit — Excel-Datei laden um zu beginnen.', type: 'idle' });
  };
```

Change to:

```js
  // ─── Reset Session ────────────────────────────────────
  const resetSession = () => {
    setItems([]);
    setLoadedFiles([]);
    setSelectAllIndiv(false);
    setStatus({ text: 'Bereit — Excel- oder PDF-Datei(en) laden um zu beginnen.', type: 'idle' });
  };

  // ─── Remove a loaded file (and its items) ─────────────
  const removeFile = (fileId) => {
    setLoadedFiles(prev => prev.filter(f => f.id !== fileId));
    setItems(prev => prev.filter(it => it._fileId !== fileId));
  };
```

- [ ] **Step 5: Commit**

```bash
git add web/app/page.js
git commit -m "feat: support uploading multiple Excel/PDF files at once"
```

---

### Task 2: Drop zone & loaded-files list UI

**Files:**
- Modify: `web/app/page.js:554-558` (header reset button)
- Modify: `web/app/page.js:562-592` (drop zone JSX)

- [ ] **Step 1: Update the header reset button**

Currently:

```jsx
        <div className="header-actions">
          {loadedFile && (
            <button className="btn btn-secondary" onClick={resetSession} id="btn-reset">
              ↺ Neue Datei laden
            </button>
          )}
        </div>
```

Change to:

```jsx
        <div className="header-actions">
          {loadedFiles.length > 0 && (
            <button className="btn btn-secondary" onClick={resetSession} id="btn-reset">
              ↺ Alles zurücksetzen
            </button>
          )}
        </div>
```

- [ ] **Step 2: Update the drop zone to support multiple files and show the file list**

Currently:

```jsx
      {/* ── Drop Zone ── */}
      <div
        id="drop-zone"
        className={`drop-zone ${dragOver ? 'drag-over' : ''} ${loadedFile ? 'loaded' : ''}`}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        onClick={onBrowse}
      >
        <span className="drop-zone-icon">
          {loading ? <span className="spinner"></span> : loadedFile ? '✅' : '📂'}
        </span>
        <p className="drop-zone-text">
          {loading
            ? 'Datei wird geladen…'
            : loadedFile
              ? `${loadedFile} · ${items.length} Positionen geladen`
              : 'Excel- oder PDF-Datei hierher ziehen oder klicken zum Auswählen'
          }
        </p>
        {!loadedFile && !loading && (
          <p className="drop-zone-hint">Unterstützt: .xlsx, .xls, .pdf</p>
        )}
        <input
          ref={fileInputRef}
          type="file"
          accept=".xlsx,.xls,.pdf"
          onChange={onFileChange}
          id="file-input"
        />
      </div>
```

Change to:

```jsx
      {/* ── Drop Zone ── */}
      <div
        id="drop-zone"
        className={`drop-zone ${dragOver ? 'drag-over' : ''} ${loadedFiles.length > 0 ? 'loaded' : ''}`}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        onClick={onBrowse}
      >
        <span className="drop-zone-icon">
          {loading ? <span className="spinner"></span> : loadedFiles.length > 0 ? '✅' : '📂'}
        </span>
        <p className="drop-zone-text">
          {loading
            ? 'Datei(en) werden eingelesen…'
            : loadedFiles.length > 0
              ? `${loadedFiles.length} Datei(en) · ${items.length} Positionen geladen — weitere Dateien hier ablegen`
              : 'Excel- oder PDF-Datei(en) hierher ziehen oder klicken zum Auswählen'
          }
        </p>
        {loadedFiles.length === 0 && !loading && (
          <p className="drop-zone-hint">Unterstützt: .xlsx, .xls, .pdf (auch mehrere gleichzeitig)</p>
        )}
        <input
          ref={fileInputRef}
          type="file"
          accept=".xlsx,.xls,.pdf"
          multiple
          onChange={onFileChange}
          id="file-input"
        />
      </div>

      {/* ── Loaded Files List ── */}
      {loadedFiles.length > 0 && (
        <div className="loaded-files-list" id="loaded-files-list">
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
      )}
```

- [ ] **Step 3: Commit**

```bash
git add web/app/page.js
git commit -m "feat: show loaded-files list with per-file removal"
```

---

### Task 3: Styling for the loaded-files list

**Files:**
- Modify: `web/app/globals.css:329-332` (right after the hidden file input rule)

- [ ] **Step 1: Add CSS for the new list**

Currently:

```css
/* Hidden file input */
.drop-zone input[type="file"] {
  display: none;
}
```

Change to:

```css
/* Hidden file input */
.drop-zone input[type="file"] {
  display: none;
}

/* ── Loaded Files List ────────────────────────────────── */
.loaded-files-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: -8px;
  margin-bottom: 24px;
}

.loaded-file-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 14px;
  background: var(--bg-card);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  font-size: 0.85rem;
}

.loaded-file-row.error {
  border-color: var(--danger-500);
  background: var(--danger-50);
}

.loaded-file-name {
  font-weight: 500;
  color: var(--text-primary);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.loaded-file-count {
  color: var(--text-muted);
  white-space: nowrap;
}

.loaded-file-row.error .loaded-file-count {
  color: var(--danger-600);
}

.loaded-file-remove {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 0.9rem;
  padding: 2px 4px;
  border-radius: var(--radius-md);
  transition: background var(--transition-fast);
}

.loaded-file-remove:hover {
  background: var(--gray-100);
}
```

- [ ] **Step 2: Commit**

```bash
git add web/app/globals.css
git commit -m "style: add loaded-files list styling"
```

---

### Task 4: Manual verification

There is no test suite in this project (per `CLAUDE.md`). Verify by running the web app locally.

**Files:** none (verification only)

- [ ] **Step 1: Start the web app dev server**

```bash
cd web && npm run dev
```

Expected: server starts on `http://localhost:3000` (Next.js dev output, no errors).

- [ ] **Step 2: Load two Excel files via the click-to-browse dialog (multi-select)**

In the browser: click the drop zone, in the OS file dialog select two different `.xlsx` files at once (Ctrl/Cmd-click), confirm.

Expected: status shows "Datei 1 von 2…" then "Datei 2 von 2…" while loading, then a success toast. The items table shows the combined positions from both files. The loaded-files list below the drop zone shows two rows, each with the correct file name and position count. The drop zone itself shows "2 Datei(en) · N Positionen geladen — weitere Dateien hier ablegen".

- [ ] **Step 3: Drag & drop multiple files at once**

Select two files in Finder/Explorer, drag both onto the drop zone simultaneously.

Expected: both get added as two more rows in the loaded-files list, their items appended to the table (now 4 file rows total, items from all 4 files visible).

- [ ] **Step 4: Mix a valid file with an unparseable one**

Upload one valid `.xlsx` together with a `.pdf` that has no recognizable supplier format (or any file that previously triggered `"Keine Positionen gefunden..."`).

Expected: the valid file's items are still added to the table; the loaded-files list shows an extra row in red/error styling with the error message instead of a position count; the toast says e.g. "⚠️ 1 von 2 Dateien geladen — 1 fehlgeschlagen". The valid file's positions remain visible regardless.

- [ ] **Step 5: Remove one file**

Click the 🗑 button on one of the successfully loaded file rows.

Expected: that row disappears from the loaded-files list, and exactly its positions disappear from the items table — all other files' positions remain. The error-row file can also be removed the same way.

- [ ] **Step 6: Manual row survives file removal**

Click "➕ Neue Zeile" to add a manual row, then remove one of the uploaded files.

Expected: the manually added row is still present in the table after the file removal.

- [ ] **Step 7: Reset clears everything**

Click "↺ Alles zurücksetzen" in the header.

Expected: items table is empty, loaded-files list disappears, drop zone returns to its initial empty-state text ("Excel- oder PDF-Datei(en) hierher ziehen oder klicken zum Auswählen").

- [ ] **Step 8: Generate an invoice from merged positions**

Load two files again, fill in invoice number/date/customer name, click "Rechnung erstellen".

Expected: the generated PDF contains all positions from both files (spot-check item count and a product from each source file).

---

## Done

After all four tasks are checked off: the web app's invoice page accepts multiple Excel/PDF files in one session, merges their positions while tracking origin per item, lets the user remove a whole file's positions at once, and generates a single combined invoice — all via the existing, unmodified `/api/parse` and `/api/generate` endpoints.

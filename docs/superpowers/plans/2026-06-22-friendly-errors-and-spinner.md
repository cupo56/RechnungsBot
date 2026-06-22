# Friendly Errors + Spinner Consistency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unexpected backend errors in the web app show a friendly explanation to the
user plus a small, always-visible technical detail line for the project owner to
read; the Excel/PDF upload spinner matches the existing animated spinner used by the
"Rechnung erstellen" button.

**Architecture:** `web/api/index.py` (Flask) gains a small `_error_response(friendly,
status, detail)` helper. The four routes' `except Exception` branches use it to
return `{"error": "<friendly>", "detail": "<technical>"}` instead of the raw
exception string. Three Next.js pages (`page.js`, `credit-note/page.js`,
`provision/page.js`) attach `detail` to the thrown `Error` object and render it as a
second, smaller line in the existing status bar. No new dependencies, no new files.

**Tech Stack:** Flask (Python), Next.js App Router (React), existing CSS in
`web/app/globals.css`. No test framework exists in this project (per
`CLAUDE.md`: "There are no automated tests") — verification steps use the Flask
test client directly (`app.test_client()`) and `curl` against the deployed app,
the same approach already used earlier in this session.

**Out of scope:** `web/app/database/page.js` and `server/api.php` (PHP backend,
different response shape — see spec).

Spec: `docs/superpowers/specs/2026-06-22-friendly-errors-and-spinner-design.md`

---

### Task 1: Backend helper + `/api/parse`

**Files:**
- Modify: `web/api/index.py:1-62`

- [ ] **Step 1: Add the `_error_response` helper**

Insert right after the `app = Flask(__name__)` line (currently line 16):

```python
app = Flask(__name__)


def _error_response(friendly, status=500, detail=None):
    body = {"error": friendly}
    if detail:
        body["detail"] = detail
    return jsonify(body), status
```

- [ ] **Step 2: Update `/api/parse`'s generic exception branch**

In `parse_file()`, the existing block:

```python
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Unerwarteter Fehler: {e}"}), 500
```

becomes:

```python
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _error_response(
            "Die Datei konnte nicht eingelesen werden. Bitte prüfe das Dateiformat oder versuche es erneut.",
            detail=str(e),
        )
```

(The `except ValueError` branch is unchanged — those messages are already specific
and user-friendly, e.g. "Fehlende Spalten: ...".)

- [ ] **Step 3: Verify with the Flask test client**

Run from `web/api/`:

```bash
python3 -c "
import sys, os
sys.path.insert(0, os.getcwd())
import index as appmod
client = appmod.app.test_client()

# Trigger the generic-exception branch: upload a .xlsx that isn't a real zip/xlsx file
import io
data = {'file': (io.BytesIO(b'not a real excel file'), 'broken.xlsx')}
resp = client.post('/api/parse', data=data, content_type='multipart/form-data')
print(resp.status_code, resp.get_json())
"
```

Expected: status `500`, JSON has both `error` (the friendly sentence) and `detail`
(something like `File is not a zip file`).

- [ ] **Step 4: Verify the ValueError branch is untouched**

```bash
python3 -c "
import sys, os, openpyxl
sys.path.insert(0, os.getcwd())
wb = openpyxl.Workbook()
wb.active.append(['Not', 'A', 'Valid', 'Header'])
wb.save('/tmp/no_order_col.xlsx')
import index as appmod
client = appmod.app.test_client()
with open('/tmp/no_order_col.xlsx', 'rb') as f:
    resp = client.post('/api/parse', data={'file': (f, 'no_order_col.xlsx')}, content_type='multipart/form-data')
print(resp.status_code, resp.get_json())
"
```

Expected: status `400`, JSON is `{"error": "Konnte die Spaltenüberschriften nicht erkennen.\nDie Excel-Datei muss mindestens eine Spalte mit 'Order' enthalten."}` — no `detail` key.

- [ ] **Step 5: Commit**

```bash
git add web/api/index.py
git commit -m "feat: split friendly/technical error text in /api/parse"
```

---

### Task 2: `/api/generate`, `/api/provision`, `/api/credit-note`

**Files:**
- Modify: `web/api/index.py` (the three remaining `except Exception` blocks)

- [ ] **Step 1: Update `/api/generate`**

In `generate_invoice()`, replace:

```python
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

with:

```python
    except Exception as e:
        return _error_response(
            "Beim Erstellen der Rechnung/des Lieferscheins ist ein Fehler aufgetreten.",
            detail=str(e),
        )
```

- [ ] **Step 2: Update `/api/provision`**

In `generate_provision()`, replace:

```python
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

with:

```python
    except Exception as e:
        return _error_response(
            "Beim Erstellen der Provisionsrechnung ist ein Fehler aufgetreten.",
            detail=str(e),
        )
```

- [ ] **Step 3: Update `/api/credit-note`**

In `generate_credit_note()`, replace:

```python
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

with:

```python
    except Exception as e:
        return _error_response(
            "Beim Erstellen der Gutschrift ist ein Fehler aufgetreten.",
            detail=str(e),
        )
```

- [ ] **Step 4: Verify all three with the Flask test client**

```bash
cd web/api && python3 -c "
import sys, os
sys.path.insert(0, os.getcwd())
import index as appmod
client = appmod.app.test_client()

# Missing 'date' in invoice_data triggers a KeyError inside generate_invoice()
resp = client.post('/api/generate', json={
    'mode': 'invoice',
    'items': [{'ean':'123','product':'Test','quantity':1,'source_price':1.0,'unit_price':1.0}],
    'invoice_data': {'number': '1/2026'},  # no 'date' -> KeyError
    'customer_data': {'name': 'Test'},
    'create_delivery_note': False,
})
print('generate:', resp.status_code, resp.get_json())

resp = client.post('/api/provision', json={
    'items': [],
    'invoice_data': {'number': '1/2026'},
    'customer_data': {'name': 'Test'},
})
print('provision:', resp.status_code, resp.get_json())

resp = client.post('/api/credit-note', json={
    'items': [],
    'invoice_data': {'number': '1/2026'},
    'customer_data': {'name': 'Test'},
})
print('credit-note:', resp.status_code, resp.get_json())
"
```

Expected: all three print status `500` with a JSON body containing both `error`
(the German friendly sentence for that route) and `detail` (the raw exception text,
e.g. `'date'` for the KeyError).

- [ ] **Step 5: Commit**

```bash
git add web/api/index.py
git commit -m "feat: split friendly/technical error text in generate/provision/credit-note routes"
```

---

### Task 3: CSS for the technical detail line

**Files:**
- Modify: `web/app/globals.css:693-704`

- [ ] **Step 1: Add `flex-wrap` to `.status-bar` and a new `.status-detail` rule**

Current:

```css
/* ── Status Bar ────────────────────────────────────────── */
.status-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 20px;
  background: var(--bg-card);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  font-size: 0.8rem;
  color: var(--text-muted);
}
```

New:

```css
/* ── Status Bar ────────────────────────────────────────── */
.status-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  padding: 10px 20px;
  background: var(--bg-card);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  font-size: 0.8rem;
  color: var(--text-muted);
}

.status-detail {
  font-size: 0.7rem;
  color: var(--text-muted);
  flex-basis: 100%;
  margin-top: 2px;
}
```

- [ ] **Step 2: Visual sanity check**

Run `npm run dev` in `web/`, open `http://localhost:3000`, open devtools, and in the
console run:

```js
document.querySelector('.status-bar').insertAdjacentHTML(
  'beforeend',
  '<span class="status-detail">Technisch: TestError: something broke</span>'
);
```

Expected: a small grey line appears below the existing status text, on its own row,
not squeezed next to it.

- [ ] **Step 3: Commit**

```bash
git add web/app/globals.css
git commit -m "style: add .status-detail line for technical error text"
```

---

### Task 4: `web/app/page.js` — upload + generate error handling, spinner

**Files:**
- Modify: `web/app/page.js:208-240` (`handleFileUpload`)
- Modify: `web/app/page.js:410-533` (`generateInvoice`)
- Modify: `web/app/page.js:562-564` (drop-zone icon)
- Modify: `web/app/page.js:856-864` (status bar JSX)

- [ ] **Step 1: Update `handleFileUpload`'s error handling**

Current (around line 223-236):

```js
      const resp = await fetch('/api/parse', { method: 'POST', body: formData });
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({ error: `HTTP ${resp.status}` }));
        throw new Error(errData.error || `Fehler ${resp.status}`);
      }
      const data = await resp.json();
      const parsed = data.items || [];
      setItems(parsed);
      setLoadedFile(file.name);
      setStatus({ text: `${parsed.length} Positionen aus '${file.name}' geladen.`, type: 'success' });
      setToast({ text: `✅ ${parsed.length} Positionen geladen`, type: 'success' });
    } catch (err) {
      setStatus({ text: `Fehler: ${err.message}`, type: 'error' });
      setToast({ text: `❌ ${err.message}`, type: 'error' });
    } finally {
      setLoading(false);
    }
```

New:

```js
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
```

- [ ] **Step 2: Update `generateInvoice`'s error handling**

Current (around line 470-472 and 527-529):

```js
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({ error: `HTTP ${resp.status}` }));
        throw new Error(errData.error || `Fehler ${resp.status}`);
      }
```

```js
    } catch (err) {
      setStatus({ text: `Fehler: ${err.message}`, type: 'error' });
      setToast({ text: `❌ ${err.message}`, type: 'error' });
    } finally {
      setGenerating(false);
    }
```

New:

```js
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({ error: `HTTP ${resp.status}` }));
        const genErr = new Error(errData.error || `Fehler ${resp.status}`);
        genErr.detail = errData.detail;
        throw genErr;
      }
```

```js
    } catch (err) {
      setStatus({ text: `Fehler: ${err.message}`, type: 'error', detail: err.detail });
      setToast({ text: `❌ ${err.message}`, type: 'error' });
    } finally {
      setGenerating(false);
    }
```

- [ ] **Step 3: Render the detail line in the status bar**

Current (around line 856-864):

```jsx
      <div className="status-bar" id="status-bar">
        <div className={`status-dot ${status.type === 'error' ? 'error' : status.type === 'loading' ? 'loading' : ''}`}></div>
        <span className="status-text">{status.text}</span>
        {loading && (
          <div className="progress-bar-container">
            <div className="progress-bar-fill"></div>
          </div>
        )}
      </div>
```

New:

```jsx
      <div className="status-bar" id="status-bar">
        <div className={`status-dot ${status.type === 'error' ? 'error' : status.type === 'loading' ? 'loading' : ''}`}></div>
        <span className="status-text">{status.text}</span>
        {status.detail && (
          <span className="status-detail">Technisch: {status.detail}</span>
        )}
        {loading && (
          <div className="progress-bar-container">
            <div className="progress-bar-fill"></div>
          </div>
        )}
      </div>
```

- [ ] **Step 4: Swap the static upload icon for the animated spinner**

Current (around line 562-564):

```jsx
        <span className="drop-zone-icon">
          {loading ? '⏳' : loadedFile ? '✅' : '📂'}
        </span>
```

New:

```jsx
        <span className="drop-zone-icon">
          {loading ? <span className="spinner"></span> : loadedFile ? '✅' : '📂'}
        </span>
```

- [ ] **Step 5: Manual browser check**

Run `npm run dev` in `web/`, open the app, upload a valid `.xlsx` and confirm:
1. The drop-zone shows the same spinning animation as the "Rechnung erstellen"
   button shows when generating.
2. Trigger a real error (e.g. stop the Flask dev server / break network temporarily,
   or upload a corrupt file) and confirm the status bar shows a friendly top line
   and a smaller grey "Technisch: ..." line underneath.

- [ ] **Step 6: Commit**

```bash
git add web/app/page.js
git commit -m "feat: show friendly+technical error detail and unify upload spinner on main page"
```

---

### Task 5: `web/app/credit-note/page.js`

**Files:**
- Modify: `web/app/credit-note/page.js:274-359` (`generateInvoice`)
- Modify: `web/app/credit-note/page.js:612-615` (status bar JSX)

- [ ] **Step 1: Update the error handling**

Current (around line 323-326 and 353-358):

```js
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({ error: `HTTP ${resp.status}` }));
        throw new Error(errData.error || `Fehler ${resp.status}`);
      }
```

```js
    } catch (err) {
      setStatus({ text: `Fehler: ${err.message}`, type: 'error' });
      setToast({ text: `❌ ${err.message}`, type: 'error' });
    } finally {
      setGenerating(false);
    }
```

New:

```js
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({ error: `HTTP ${resp.status}` }));
        const genErr = new Error(errData.error || `Fehler ${resp.status}`);
        genErr.detail = errData.detail;
        throw genErr;
      }
```

```js
    } catch (err) {
      setStatus({ text: `Fehler: ${err.message}`, type: 'error', detail: err.detail });
      setToast({ text: `❌ ${err.message}`, type: 'error' });
    } finally {
      setGenerating(false);
    }
```

- [ ] **Step 2: Render the detail line**

Current (around line 612-615):

```jsx
        <div className="status-bar" style={{ marginTop: 24 }}>
          <div className={`status-dot ${status.type === 'error' ? 'error' : status.type === 'loading' ? 'loading' : 'success'}`}></div>
          <span className="status-text">{status.text}</span>
        </div>
```

New:

```jsx
        <div className="status-bar" style={{ marginTop: 24 }}>
          <div className={`status-dot ${status.type === 'error' ? 'error' : status.type === 'loading' ? 'loading' : 'success'}`}></div>
          <span className="status-text">{status.text}</span>
          {status.detail && (
            <span className="status-detail">Technisch: {status.detail}</span>
          )}
        </div>
```

- [ ] **Step 3: Manual browser check**

Trigger a credit-note generation error (e.g. temporarily rename
`web/api/src/pdf/credit_note.py`'s `generate_credit_note` function locally to break
the import, run `npm run dev`, attempt to create a credit note, confirm both lines
show, then rename the function back) — or just trust Task 2's backend test-client
verification and confirm visually in the browser after deploying (Task 7).

- [ ] **Step 4: Commit**

```bash
git add web/app/credit-note/page.js
git commit -m "feat: show friendly+technical error detail on credit-note page"
```

---

### Task 6: `web/app/provision/page.js`

**Files:**
- Modify: `web/app/provision/page.js:280-364` (`generateInvoice`)
- Modify: `web/app/provision/page.js:611-614` (status bar JSX)

- [ ] **Step 1: Update the error handling**

Current (around line 328-331 and 358-363):

```js
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({ error: `HTTP ${resp.status}` }));
        throw new Error(errData.error || `Fehler ${resp.status}`);
      }
```

```js
    } catch (err) {
      setStatus({ text: `Fehler: ${err.message}`, type: 'error' });
      setToast({ text: `❌ ${err.message}`, type: 'error' });
    } finally {
      setGenerating(false);
    }
```

New:

```js
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({ error: `HTTP ${resp.status}` }));
        const genErr = new Error(errData.error || `Fehler ${resp.status}`);
        genErr.detail = errData.detail;
        throw genErr;
      }
```

```js
    } catch (err) {
      setStatus({ text: `Fehler: ${err.message}`, type: 'error', detail: err.detail });
      setToast({ text: `❌ ${err.message}`, type: 'error' });
    } finally {
      setGenerating(false);
    }
```

- [ ] **Step 2: Render the detail line**

Current (around line 611-614):

```jsx
        <div className="status-bar" style={{ marginTop: 24 }}>
          <div className={`status-dot ${status.type === 'error' ? 'error' : status.type === 'loading' ? 'loading' : 'success'}`}></div>
          <span className="status-text">{status.text}</span>
        </div>
```

New:

```jsx
        <div className="status-bar" style={{ marginTop: 24 }}>
          <div className={`status-dot ${status.type === 'error' ? 'error' : status.type === 'loading' ? 'loading' : 'success'}`}></div>
          <span className="status-text">{status.text}</span>
          {status.detail && (
            <span className="status-detail">Technisch: {status.detail}</span>
          )}
        </div>
```

- [ ] **Step 3: Commit**

```bash
git add web/app/provision/page.js
git commit -m "feat: show friendly+technical error detail on provision page"
```

---

### Task 7: Deploy and verify end-to-end on production

**Files:** none (deployment + manual verification only)

- [ ] **Step 1: Trigger a deployment**

```bash
curl -s -i -X POST "https://api.vercel.com/v1/integrations/deploy/prj_lJhN9yBrGtZG8h8vAtB11JozH1Wg/R9JHtAWoME"
```

Expected: `HTTP/2 201` with a JSON body containing a `job.id`.

- [ ] **Step 2: Poll until the new code is live**

```bash
for i in $(seq 1 20); do
  resp=$(curl -s -o /tmp/verify_gen.json -w "%{http_code}" -X POST "https://web-psi-ten-68.vercel.app/api/generate" \
    -H "Content-Type: application/json" \
    -d '{"mode":"invoice","items":[{"ean":"1","product":"x","quantity":1,"source_price":1,"unit_price":1}],"invoice_data":{"number":"1/2026"},"customer_data":{"name":"Test"},"create_delivery_note":false}')
  body=$(cat /tmp/verify_gen.json)
  echo "attempt $i: HTTP $resp body=$body"
  if echo "$body" | grep -q '"detail"'; then break; fi
  sleep 15
done
```

Expected: eventually a response with both `"error"` and `"detail"` keys (this
request intentionally omits `date` to trigger the `KeyError` path).

- [ ] **Step 3: Ask the project owner to verify in the browser**

Confirm with the user: open the live app, upload an Excel/PDF file (spinner should
animate the same as the generate button), then trigger any error and check that the
status bar shows a friendly sentence plus a smaller "Technisch: ..." line.

No commit for this task — it's verification only.

# EU-Lieferungshinweis als Checkbox (Web-App)

Datum: 2026-06-22

## Problem

Auf der Rechnungs-Seite der Web-App (`web/app/page.js`) wird im PDF (`src/pdf/invoice.py`,
`_draw_footer`) standardmäßig immer der Satz "Steuerfreie, innergemeinschaftliche Lieferung
gem. Artikel 6 UStG." gedruckt — sofern keine Export-Rechnung und keine eigene
Rechnungs-Notiz gesetzt ist. Der Nutzer möchte diesen Satz individuell pro Rechnung
ein-/ausschalten können, statt dass er immer fix drauf ist.

## Scope

Betroffen: `web/app/page.js` (neue Checkbox + Config-Persistenz) und `src/pdf/invoice.py`
(`_draw_footer`).

**Out of scope:**
- Desktop-App (`src/gui.py`) — bekommt keine neue Checkbox, behält aktuelles Verhalten
  (Default `True`) bei, da sie das neue Feld nie im `invoice_data`-Dict mitsendet.
- `web/api/src/pdf/invoice.py` — ist nur eine Build-Zeit-Kopie von `src/pdf/invoice.py`
  (`cp -r ../src ./api/src` im Vercel-Build), wird nicht direkt editiert.
- Provision- und Gutschrift-Seiten — verwenden den Satz nicht.
- Die anderen beiden Zeilen im Default-Footer ("Leistungsdatum ist gleich dem
  Rechnungsdatum" / "Beim Zahlungsverzug...") bleiben immer sichtbar, unabhängig von der
  neuen Checkbox.

## Design

### Frontend (`web/app/page.js`)

- Neuer State: `const [euTextEnabled, setEuTextEnabled] = useState(true);`
- `DEFAULT_CONFIG`: neuer Key `default_eu_text_enabled: true`
- Mount-Effect: `setEuTextEnabled(cfg.default_eu_text_enabled);`
- `persistConfig`: `default_eu_text_enabled: euTextEnabled` in `newCfg` und im
  `useCallback`-Dependency-Array ergänzen
- `invoiceData`-Objekt (vor dem `fetch('/api/generate', ...)`-Call): neuer Key
  `eu_text_enabled: euTextEnabled`
- Neue Checkbox im Settings-Panel, direkt nach "QR-Code"-Checkbox:

```jsx
<div className="checkbox-group">
  <label className="checkbox-label" title="Steuerfreie, innergemeinschaftliche Lieferung gem. Artikel 6 UStG.">
    <input type="checkbox" className="checkbox-input" checked={euTextEnabled}
      onChange={e => setEuTextEnabled(e.target.checked)} id="chk-eu-text" />
    EU-Lieferungshinweis
  </label>
</div>
```

### Backend (`src/pdf/invoice.py`, `_draw_footer`)

Im `else`-Zweig (kein Export, keine eigene Notiz) wird die erste Zeile nur noch bedingt
gezeichnet. Bei deaktivierter Checkbox rutschen die übrigen zwei Zeilen nach oben (keine
Lücke):

```python
else:
    if self.inv.get("eu_text_enabled", True):
        c.drawString(COL_EAN, y, FOOTER.get("eu_text_1", "Steuerfreie, innergemeinschaftliche Lieferung gem. Artikel 6 UStG."))
        y -= 12 * mm
    c.drawString(COL_EAN, y, FOOTER.get("eu_text_2", "Leistungsdatum ist gleich dem Rechnungsdatum"))
    y -= 5 * mm
    c.drawString(COL_EAN, y, FOOTER.get("eu_text_3", "Beim Zahlungsverzug sind sämtliche Mahn.-und Inkassospesen zu ersetzen.Gerichtsstand ist Wien."))
    y -= 8 * mm
```

Default `True` via `.get(..., True)` stellt sicher, dass alle Aufrufer, die das Feld nicht
mitsenden (Desktop-App), exakt das bisherige Verhalten beibehalten.

## Testing

Keine automatisierten Tests im Projekt. Manuelle Verifikation: Web-App lokal starten,
Rechnung einmal mit aktivierter und einmal mit deaktivierter Checkbox erzeugen, PDF-Footer
visuell prüfen (Zeile weg + kein Lücken-Artefakt bei deaktiviert).

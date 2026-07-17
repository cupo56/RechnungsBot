# Endkunden-Rechnung (Web-App)

Datum: 2026-07-17

## Problem

Bisher gibt es in der Web-App zwei Wege, eine Rechnung zu erstellen:

- `/` — normale Rechnung, Positionen kommen aus einer hochgeladenen Excel-/PDF-Datei
  (`web/app/page.js`).
- `/provision` und `/credit-note` — Positionen werden manuell erfasst, aber im simplen
  Referenz/Beschreibung/Netto-Format (`SimpleItemsPanel`), das keine Stückzahl/EAN kennt
  und optisch nicht wie eine normale Rechnung aussieht.

Der Nutzer verkauft auch über Kaufland (Marktplatz) an Privatkunden und legt die Rechnung
dem Paket bei. Dafür braucht er eine Rechnung, die aussieht wie die normale Rechnung
(Stk./EAN/Produkt/Einzelpreis/Gesamtpreis), aber ohne Excel-Import — er trägt die
Positionen selbst ein. Der Empfänger ist eine Privatperson, keine Firma (kein Firmenname/
VAT-Nr. nötig, teils auch gar keine Adressdaten).

## Scope

Neue Seite `/endkunde` in der Web-App. Betroffen:

- Neue Datei `web/app/endkunde/page.js`
- Neue Datei `web/app/utils/useManualInvoiceItemsEditor.js` (Positions-Logik)
- Neue Datei `web/app/components/ManualInvoiceItemsPanel.js` (Eingabe + Tabelle)
- `web/components/Navigation.js` — neuer Menüpunkt

**Out of scope / unverändert:**

- Backend (`web/api/index.py`, `/api/generate`, `/api/database`) — keine Änderungen
  nötig. Alle benötigten Felder haben in `invoice.py`/`delivery_note.py` bereits
  sinnvolle Defaults (leerer Kundenname, `is_export=False`, `markup_factor` wird von den
  Generatoren ohnehin nie gelesen).
- `web/app/database/page.js` — Endkunden-Rechnungen laufen unter den bestehenden
  Archiv-Kategorien „Rechnung"/„Lieferschein" mit, keine neue Kategorie.
- Desktop-App (`src/`) — nicht betroffen.
- Excel-/PDF-Import — bewusst nicht Teil dieser Seite.

## Design

### Rechnungsnummer (geteilter Zähler)

`/endkunde` verwendet denselben `localStorage`-Key `rechnungsbot_config` wie alle
anderen Seiten (`web/app/utils/config.js`) und liest/schreibt dieselben Felder
`last_invoice_number` / `last_invoice_year` wie `page.js`. Es gibt **keinen eigenen
Zähler** (anders als `last_provision_number` bei Provisionsrechnungen) — eine auf
`/endkunde` erstellte Rechnung erhöht denselben Zähler, den auch `/` benutzt, und beide
Seiten sehen den jeweils aktuellen Stand.

`DEFAULT_CONFIG` auf `/endkunde` enthält daher `last_invoice_number: 1,
last_invoice_year: 2026` als Fallback (gleiche Defaults wie `page.js`), plus eigene
Felder für die Endkunden-spezifischen Defaults (siehe unten) und einen eigenen
Vorlagen-Key `endkunde_customer_templates` (getrennt von `customer_templates`, da
Endkunden-Adressen ein anderes Feld-Set haben — kein `vat`).

### Einstellungen-Panel (reduziert)

Neues, eigenes Panel auf der Seite (kein bestehendes `SettingsPanel` wiederverwendet,
da die Feldmenge kleiner ist):

- Rechnungsnr. (Pflichtfeld)
- Datum (Pflichtfeld)
- USt. berechnen (Checkbox + %-Feld), Default: `false` / `20.0` (wie `page.js`)
- Lieferschein erstellen (Checkbox) + kg-Feld + Lieferschein-Notiz (Textarea),
  Default: `false` / `''` / `''`
- QR-Code / GiroCode (Checkbox), Default: `true`

Kein Aufschlag-%, kein Export-Toggle, kein EU-Lieferungshinweis, keine Rechnungs-Notiz
(Skalierbarkeit: falls später gewünscht, einfach ergänzbar, aber nicht Teil dieser
Iteration).

### Kunden-Panel

Neues, eigenes Panel (nicht `CustomerPanel`, da andere Feldbeschriftung/-menge):

- **Name** (Label „Name" statt „Firma") — **optional**, keine Pflichtfeld-Validierung
- Straße — optional
- PLZ / Ort — optional
- Land — optional
- **Kein VAT-Nr.-Feld**

Alle Felder sind bewusst optional: der Nutzer entscheidet selbst, ob und was er
einträgt (z.B. nur Vorname, oder komplett leer, falls die Rechnung nur als Beleg im
Paket liegt und die Versandadresse separat drauf ist). `invoice.py`/`delivery_note.py`
rendern leere Kundendaten bereits sauber (leere Zeilen werden bei der Header-Höhen-
Berechnung ausgelassen).

Template-Verwaltung über das bestehende `TemplateSelector`-Component und den
bestehenden `useCustomerTemplates`-Hook, mit `templatesKey: 'endkunde_customer_templates'`
und `getFields`/`applyTemplate` für `{ name, street, plz_city, country }` (kein `vat`).

### Positionen

Neuer Hook `useManualInvoiceItemsEditor` (analog zu `useSimpleItemsEditor`, aber mit
vier Feldern statt drei) verwaltet:

- Eingabe-States: `itemEan`, `itemProduct`, `itemQty`, `itemUnitPrice`
- `addItem()`: validiert `product` (Pflicht, nicht leer), `quantity` (Pflicht, ganzzahlig
  > 0, Default beim Leerlassen: `1`), `unit_price` (Pflicht, Zahl ≥ 0). `ean` ist frei/
  optional (String, auch leer erlaubt). Bei Erfolg: neues Item
  `{ ean, product, quantity, unit_price }` an `items` anhängen, Eingabefelder leeren.
- Inline-Zell-Editing (`startEdit`/`commitEdit`/`cancelEdit`) für alle vier Felder,
  jede Zeile ist immer editierbar (kein „Individuell"-Toggle nötig, da es keine
  Ursprungsdaten aus einem Import gibt, die man umschalten könnte).
- `deleteItem(idx)` mit Bestätigungsdialog (Produktname als Label).

Neue Komponente `ManualInvoiceItemsPanel` (angelehnt an `ItemsTable`, aber ohne
„Indiv."-Spalte und ohne „Originaldaten einblenden"):

Eingabebox (links) mit den vier Feldern + „Position hinzufügen"-Button.

Tabelle (rechts) mit Spalten:

| Stk. | EAN | Produkt | Einzelpreis € | Gesamtpreis € | USt. (falls aktiv) | 🗑 |

`Gesamtpreis` wird clientseitig aus `quantity * unit_price` berechnet (nicht editierbar).
Fußzeile zeigt Summen wie in `ItemsTable`/`SimpleItemsPanel` (Netto / USt. / Brutto bzw.
nur Netto, je nach `ustEnabled`).

### Rechnungserstellung

Zwei Buttons wie auf `/` (`page.js`):

- „Rechnung erstellen" → `mode: 'invoice'`
- „Nur Lieferschein" → `mode: 'delivery_only'`

Beide rufen `POST /api/generate` direkt auf (wie `page.js`, nicht über das generische
`submitDocument`-Util, da dieses keine zwei PDFs / kein `mode` unterstützt). Payload:

```js
{
  mode,
  items: items.map(it => ({ ean: it.ean, product: it.product, quantity: it.quantity, unit_price: it.unit_price })),
  invoice_data: {
    number: invoiceNr.trim(),
    date: invoiceDate.trim(),
    ust_enabled: ustEnabled,
    ust_percent: ustPct,
    girocode_enabled: girocodeEnabled,
    weight: weight.trim(),
    delivery_note_text: deliveryNoteText.trim(),
  },
  customer_data: {
    name: custName.trim(),
    street: custStreet.trim(),
    plz_city: custPlz.trim(),
    country: custCountry.trim(),
  },
  create_delivery_note: deliveryNote,
}
```

Kein `markup_factor`, `is_export`, `eu_text_enabled` im Payload — die Backend-Generatoren
verwenden für alle drei bereits unschädliche Defaults (`is_export` default `False`,
`markup_factor` wird nie gelesen).

Validierung vor dem Absenden (analog `page.js`, aber ohne Kundennamen-Pflicht):

- mindestens eine Position vorhanden
- Rechnungsnr. nicht leer
- Datum nicht leer
- (kein Pflichtfeld für Kundendaten)

Nach Erfolg:

- PDF(s) herunterladen (wie `page.js`, ggf. zwei Downloads mit `setTimeout`-Versatz)
- `saveInvoiceToDb` mit `docType: 'rechnung'` bzw. `'lieferschein'` (gleiche Kategorien
  wie die normale Rechnung — taucht im Archiv zusammen mit den `/`-Rechnungen auf)
- `persistConfig(true)` nur bei `mode === 'invoice'` — erhöht den geteilten
  `last_invoice_number`-Zähler, exakt wie in `page.js`

### Navigation

Neuer Eintrag in `web/components/Navigation.js`:

```js
{ href: '/endkunde', label: '🧍 Endkunde', desc: 'Rechnung für Endkunden manuell erstellen' }
```

Position in der Liste: nach `/provision`/`/credit-note`, vor `/database`.

## Testing

Keine automatisierten Tests im Projekt. Manuelle Verifikation lokal (`npm run dev` in
`web/`):

- `/endkunde` öffnen, mehrere Positionen mit EAN, ohne EAN, mit Dezimal-Preis (Komma und
  Punkt) hinzufügen → Tabelle zeigt korrekte Gesamtpreise, Summe stimmt.
- Zelle in der Tabelle anklicken (Stk./EAN/Produkt/Einzelpreis) → editierbar, Enter
  übernimmt, Escape verwirft.
- Rechnung ohne jegliche Kundendaten erstellen (alle Felder leer) → PDF wird trotzdem
  generiert, ohne Fehler.
- Rechnung mit nur Namen (keine Adresse) erstellen → PDF zeigt nur die vorhandenen
  Zeilen, keine leeren Adresszeilen.
- Rechnungsnummer auf `/` prüfen, dann auf `/endkunde` eine Rechnung erstellen, dann
  wieder auf `/` wechseln → Zähler ist auf beiden Seiten synchron weitergezählt.
- „Lieferschein erstellen" aktivieren, kg + Notiz ausfüllen, „Rechnung erstellen"
  klicken → zwei PDFs werden heruntergeladen (Rechnung + Lieferschein).
- „Nur Lieferschein" klicken → nur ein PDF, Zähler wird nicht erhöht.
- Kundenvorlage speichern, Seite neu laden, Vorlage auswählen → Felder werden befüllt;
  Vorlage erscheint nicht in den normalen Kundenvorlagen auf `/` (getrennter Key).
- Nach Erstellung im Archiv (`/database`) prüfen → Rechnung erscheint unter der
  Kategorie „Rechnung" (nicht als eigene Kategorie).

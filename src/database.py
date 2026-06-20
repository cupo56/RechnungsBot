"""
Datenbankmodul für RechnungsBot.
Kommuniziert über eine PHP-REST-API mit der MySQL-Datenbank auf World4You,
da World4You keinen direkten externen MySQL-Zugriff erlaubt.
"""

import os
import json
import base64
import urllib.request
import urllib.error
import urllib.parse
import ssl


# ── Konfiguration ──────────────────────────────────────────────

def is_configured(config):
    """Prüft ob die API-URL und der API-Key konfiguriert sind."""
    return bool(config.get("db_api_url") and config.get("db_api_key"))


def _api_url(config):
    """Gibt die Basis-URL der PHP-API zurück."""
    url = config.get("db_api_url", "").rstrip("/")
    return url


def _api_key(config):
    """Gibt den API-Key zurück."""
    return config.get("db_api_key", "")


# ── HTTP-Helfer ────────────────────────────────────────────────

def _post_json(config, action, data=None):
    """Sendet einen POST-Request an die PHP-API.

    Args:
        config: App-Konfiguration mit db_api_url und db_api_key.
        action: API-Aktion (z.B. 'test', 'init', 'save', 'list', 'get_pdf', 'delete').
        data: Optionales dict mit zusätzlichen Daten.

    Returns:
        dict: JSON-Antwort der API.

    Raises:
        ConnectionError: Bei Netzwerk-/API-Fehlern.
    """
    url = _api_url(config)
    if not url:
        raise ConnectionError("Keine API-URL konfiguriert.")

    payload = {"action": action, "api_key": _api_key(config)}
    if data:
        payload.update(data)

    json_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url + "/api.php",
        data=json_data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise ConnectionError(f"API-Fehler (HTTP {e.code}): {body}") from e
    except urllib.error.URLError as e:
        raise ConnectionError(f"Verbindung zur API fehlgeschlagen: {e.reason}") from e
    except json.JSONDecodeError as e:
        raise ConnectionError(f"Ungültige API-Antwort (kein JSON): {e}") from e


# ── API-Funktionen ─────────────────────────────────────────────

def test_connection(config):
    """Testet die Verbindung zur API und Datenbank.

    Returns:
        tuple[bool, str]: (Erfolg, Nachricht)
    """
    try:
        result = _post_json(config, "test")
        if result.get("success"):
            return True, result.get("message", "Verbindung erfolgreich!")
        return False, result.get("message", "Unbekannter Fehler")
    except ConnectionError as e:
        return False, str(e)


def init_database(config):
    """Erstellt die Tabelle 'invoices' falls sie nicht existiert.

    Returns:
        tuple[bool, str]: (Erfolg, Nachricht)
    """
    try:
        result = _post_json(config, "init")
        if result.get("success"):
            return True, result.get("message", "Datenbank initialisiert.")
        return False, result.get("message", "Initialisierung fehlgeschlagen.")
    except ConnectionError as e:
        return False, str(e)


def save_invoice(config, invoice_data, customer_data, pdf_path,
                 total_netto=0.0, total_brutto=0.0,
                 item_count=0, doc_type="rechnung"):
    """Speichert eine Rechnung (mit PDF) in der Datenbank.

    Args:
        config: App-Konfiguration.
        invoice_data: dict mit number, date, ust_percent, is_export, …
        customer_data: dict mit name, street, plz_city, country, vat.
        pdf_path: Absoluter Pfad zur PDF-Datei.
        total_netto: Nettosumme.
        total_brutto: Bruttosumme.
        item_count: Anzahl der Positionen.
        doc_type: 'rechnung', 'lieferschein', 'provision' oder 'gutschrift'.

    Returns:
        tuple[bool, str]: (Erfolg, Nachricht)
    """
    if not is_configured(config):
        return False, "API ist nicht konfiguriert."

    if not os.path.isfile(pdf_path):
        return False, f"PDF-Datei nicht gefunden: {pdf_path}"

    try:
        with open(pdf_path, "rb") as f:
            pdf_data = base64.b64encode(f.read()).decode("ascii")
    except IOError as e:
        return False, f"PDF konnte nicht gelesen werden: {e}"

    ust_pct = 0.0
    if invoice_data.get("ust_enabled"):
        try:
            ust_pct = float(invoice_data.get("ust_percent", 0))
        except (ValueError, TypeError):
            ust_pct = 0.0

    data = {
        "invoice_number":  str(invoice_data.get("number", "")),
        "invoice_date":    str(invoice_data.get("date", "")),
        "document_type":   doc_type,
        "customer_name":   customer_data.get("name", ""),
        "customer_street": customer_data.get("street", ""),
        "customer_plz":    customer_data.get("plz_city", ""),
        "customer_country": customer_data.get("country", ""),
        "customer_vat":    customer_data.get("vat", ""),
        "total_netto":     round(total_netto, 2),
        "total_brutto":    round(total_brutto, 2),
        "ust_percent":     round(ust_pct, 2),
        "item_count":      item_count,
        "is_export":       1 if invoice_data.get("is_export") else 0,
        "pdf_filename":    os.path.basename(pdf_path),
        "pdf_data":        pdf_data,  # Base64-kodiert
    }

    try:
        result = _post_json(config, "save", data)
        if result.get("success"):
            return True, result.get("message", "Erfolgreich gespeichert.")
        return False, result.get("message", "Speichern fehlgeschlagen.")
    except ConnectionError as e:
        return False, str(e)


def get_all_invoices(config, search=None, doc_type=None):
    """Holt alle Rechnungen (ohne PDF-Blob) aus der Datenbank.

    Args:
        config: App-Konfiguration.
        search: Optionaler Suchtext.
        doc_type: Optionaler Dokumenttyp-Filter.

    Returns:
        list[dict]: Liste von Rechnungs-Metadaten.
    """
    data = {}
    if search:
        data["search"] = search
    if doc_type and doc_type != "alle":
        data["doc_type"] = doc_type

    try:
        result = _post_json(config, "list", data)
        if result.get("success"):
            return result.get("invoices", [])
        return []
    except ConnectionError as e:
        print(f"[RechnungsBot DB] Fehler beim Abrufen: {e}")
        return []


def get_invoice_pdf(config, invoice_id):
    """Holt die PDF-Daten und den Dateinamen für eine bestimmte Rechnung.

    Returns:
        tuple[bytes, str] | None: (PDF-Daten, Dateiname) oder None bei Fehler.
    """
    try:
        result = _post_json(config, "get_pdf", {"invoice_id": invoice_id})
        if result.get("success"):
            pdf_b64 = result.get("pdf_data", "")
            filename = result.get("pdf_filename", "dokument.pdf")
            return base64.b64decode(pdf_b64), filename
        return None
    except ConnectionError as e:
        print(f"[RechnungsBot DB] Fehler beim PDF-Abruf: {e}")
        return None


def delete_invoice(config, invoice_id):
    """Löscht eine Rechnung aus der Datenbank.

    Returns:
        tuple[bool, str]: (Erfolg, Nachricht)
    """
    try:
        result = _post_json(config, "delete", {"invoice_id": invoice_id})
        if result.get("success"):
            return True, result.get("message", "Eintrag gelöscht.")
        return False, result.get("message", "Löschen fehlgeschlagen.")
    except ConnectionError as e:
        return False, str(e)


def get_invoice_count(config):
    """Gibt die Gesamtanzahl der gespeicherten Rechnungen zurück."""
    try:
        result = _post_json(config, "count")
        if result.get("success"):
            return result.get("count", 0)
        return 0
    except ConnectionError:
        return 0

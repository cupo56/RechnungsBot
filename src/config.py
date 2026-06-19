"""
Konfigurationsmodul für RechnungsBot.
Verwaltet Firmendaten, Standardwerte und persistente Einstellungen.
"""

import copy
import json
import os
import sys


def get_app_dir():
    """Gibt das Verzeichnis für App-Daten zurück (neben der .exe oder im Projektordner)."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    # config.py is now in src/, so go one level up
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


CONFIG_FILE = os.path.join(get_app_dir(), "rechnungsbot_config.json")

# Feste Firmendaten
COMPANY = {
    "name": "Handelsagentur Adis Sefer",
    "street": "Waltenhofengasse 1/2305",
    "city": "A-1100, Wien",
    "phone": "Mobil: +4369911970865",
    "email": "E-Mail: adissefer@hotmail.com",
    "atu": "ATU71933303",
    "eori": "EORI NR: ATEOS1000108541",
}

# Feste Fußzeile
FOOTER = {
    "delivery_terms": "Lieferbedinungen: EXW 1230 Wien, Mellergasse 4-02",
    "export_de_1": "Der Exporteur der in diesem Dokument genannten Produkte erklärt,",
    "export_de_2": "dass diese Produkte, sofern nicht ausdrücklich anders angegeben, EU-Präferenzursprung haben.",
    "export_en_1": "The exporter of the products covered by this document declares that, except where otherwise clearly indicated,",
    "export_en_2": "these products are of EU preferential origin.",
    "bank_1": "ERSTE BANK",
    "bank_2": "BLZ: 20111, Kontonummer: 82010592702",
    "bank_3": "IBAN: AT532011182010592702, BIC:GIBAATWWXXX",
    "iban": "AT532011182010592702",
    "bic": "GIBAATWWXXX",
    "footer_right_1": "Handelsagentur Adis Sefer",
    "footer_right_2": "",
    "footer_right_3": "ATU 71933303 Steuer Nr.314/9616",
    "eu_text_1": "Steuerfreie, innergemeinschaftliche Lieferung gem. Artikel 6 UStG.",
    "eu_text_2": "Leistungsdatum ist gleich dem Rechnungsdatum",
    "eu_text_3": "Beim Zahlungsverzug sind sämtliche Mahn.-und Inkassospesen zu ersetzen.Gerichtsstand ist Wien.",
}

# Standardwerte für Benutzereinstellungen
DEFAULTS = {
    "last_invoice_number": 1,
    "last_invoice_year": 2026,
    "default_markup": 0.0,
    "default_ust_enabled": False,
    "default_ust_percent": 20.0,
    "default_create_delivery_note": False,
    "default_is_export": False,
    "default_girocode_enabled": True,
    "default_weight": "",
    "default_delivery_note_text": "",
    "default_invoice_note_text": "",
    "last_customer": {
        "name": "",
        "street": "",
        "plz_city": "",
        "country": "",
        "vat": "",
    },
    "customer_templates": {},
    "last_provision_number": 1,
    "last_provision_year": 2026,
    "default_provision_ust_enabled": True,
    "default_provision_ust_percent": 20.0,
    "default_provision_girocode_enabled": True,
    "last_provision_recipient": {
        "name": "",
        "street": "",
        "plz_city": "",
        "country": "",
        "vat": "",
    },
    "provision_customer_templates": {},
    "last_credit_note_number": "",
    "default_credit_note_ust_enabled": True,
    "default_credit_note_ust_percent": 20.0,
    "default_credit_note_girocode_enabled": True,
    "last_credit_note_recipient": {
        "name": "",
        "street": "",
        "plz_city": "",
        "country": "",
        "phone": "",
        "vat": "",
    },
    "credit_note_customer_templates": {},
}


def load_config():
    """Lädt gespeicherte Einstellungen aus der JSON-Datei."""
    config = copy.deepcopy(DEFAULTS)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            # Nur bekannte Schlüssel übernehmen
            for key in DEFAULTS:
                if key in saved:
                    config[key] = saved[key]
        except (json.JSONDecodeError, IOError):
            pass  # Bei Fehler Standardwerte verwenden
    return config


def save_config(config):
    """Speichert Benutzereinstellungen in die JSON-Datei.

    Führt mit den bereits gespeicherten Werten zusammen, statt die Datei voll zu
    überschreiben — so können verschiedene Programmteile (z.B. RechnungsBot-Tab
    und Provisionsrechnung-Tab) jeweils nur ihre eigenen Schlüssel aktualisieren,
    ohne die Einstellungen des jeweils anderen zu löschen.
    """
    merged = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                merged = json.load(f)
        except (json.JSONDecodeError, IOError):
            merged = {}
    merged.update(config)
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(merged, f, indent=2, ensure_ascii=False)
    except IOError as e:
        print(f"Warnung: Einstellungen konnten nicht gespeichert werden: {e}")

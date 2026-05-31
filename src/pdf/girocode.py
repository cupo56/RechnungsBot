"""
EPC QR-Code (GiroCode) Generator für SEPA-Überweisungen.
Standard: European Payments Council – EPC069-12 Version 1.0
"""
import io


def generate_epc_qr(iban: str, bic: str, name: str, amount: float, reference: str) -> io.BytesIO:
    """
    Erstellt einen EPC-konformen GiroCode als PNG (BytesIO).

    Args:
        iban: IBAN des Empfängers (z.B. "AT532011182010592702")
        bic: BIC des Empfängers (z.B. "GIBAATWWXXX")
        name: Name des Empfängers (max. 70 Zeichen)
        amount: Zahlungsbetrag in EUR (> 0)
        reference: Verwendungszweck / Rechnungsnummer (max. 140 Zeichen)

    Returns:
        BytesIO mit PNG-Daten des QR-Codes
    """
    import qrcode

    payload = "\n".join([
        "BCD",              # Service Tag
        "002",              # Version
        "1",                # Zeichensatz: UTF-8
        "SCT",              # SEPA Credit Transfer
        bic,                # BIC
        name[:70],          # Empfängername
        iban,               # IBAN
        f"EUR{amount:.2f}", # Betrag
        "",                 # Purpose Code (leer)
        "",                 # Strukturierte Referenz (leer)
        reference[:140],    # Unstrukturierter Verwendungszweck
    ])

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=1,
    )
    qr.add_data(payload.encode("utf-8"))
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

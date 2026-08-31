from flask import Flask, request, jsonify
import sys
import os
import json
import base64
import datetime
import hmac
import tempfile
import uuid

# Add the project root to sys.path so 'src' can be imported
current_dir = os.path.dirname(os.path.abspath(__file__))
if os.path.exists(os.path.join(current_dir, 'src')):
    sys.path.append(current_dir)
else:
    sys.path.append(os.path.abspath(os.path.join(current_dir, '..', '..')))

app = Flask(__name__)

# Shared-secret gate for all routes in this app. The same value is exposed to
# the browser via NEXT_PUBLIC_API_SHARED_SECRET (see web/app/utils/apiAuth.js),
# so this does not stop an attacker willing to read the client bundle — it
# only blocks direct/automated hits against the bare API URL.
_API_SHARED_SECRET = os.environ.get("NEXT_PUBLIC_API_SHARED_SECRET")

# Vercel sets VERCEL_ENV to "production" | "preview" | "development".
# Locally (no VERCEL_ENV at all) counts as non-production too.
_IS_PRODUCTION = os.environ.get("VERCEL_ENV") == "production"


def _error_response(friendly, status=500, detail=None):
    body = {"error": friendly}
    if detail:
        # Always log server-side (visible via `vercel logs`) so debugging
        # doesn't rely on what's shown to the client.
        print(f"[error] {friendly} | detail: {detail}", file=sys.stderr)
        # str(exception) can contain server-internal info (e.g. the temp-file
        # paths used for generated PDFs) - only expose it to the client
        # outside production, where it's genuinely just a debugging aid.
        if not _IS_PRODUCTION:
            body["detail"] = detail
    return jsonify(body), status


def _json_safe(value):
    # openpyxl can yield datetime/date/time objects for date-formatted Excel
    # cells; jsonify() can't serialize those directly.
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    return value


@app.before_request
def _require_shared_secret():
    if not _API_SHARED_SECRET:
        return _error_response(
            "NEXT_PUBLIC_API_SHARED_SECRET ist serverseitig nicht konfiguriert.",
            status=500,
        )
    auth_header = request.headers.get("Authorization", "")
    provided = auth_header[7:] if auth_header.startswith("Bearer ") else ""
    if not provided or not hmac.compare_digest(provided, _API_SHARED_SECRET):
        return _error_response("Nicht autorisiert.", status=401)

# --- PARSE ---
@app.route('/api/parse', methods=['POST'])
def parse_file():
    # JSON+base64 instead of multipart/form-data: Vercel's edge WAF blocks
    # multipart uploads with a 403 for some PDFs whose compressed binary
    # stream happens to match an attack pattern (long backslash-byte runs).
    # Base64 inside a JSON body avoids the raw multipart body scan.
    payload = request.json or {}
    filename = payload.get("filename", "")
    file_base64 = payload.get("file_base64")
    if not filename or not file_base64:
        return jsonify({"error": "Keine Datei hochgeladen."}), 400

    # Save to temp file
    ext = os.path.splitext(filename)[1].lower()
    fd, temp_path = tempfile.mkstemp(suffix=ext)
    os.close(fd)

    try:
        with open(temp_path, "wb") as f:
            f.write(base64.b64decode(file_base64))

        if ext == ".pdf":
            from src.pdf_input.own_invoice_parser import is_own_invoice, parse_own_invoice
            if is_own_invoice(temp_path):
                parsed = parse_own_invoice(temp_path)
                items_out = [
                    {
                        "ean": str(it.get("ean", "")),
                        "product": str(it.get("product", "")),
                        "quantity": int(it.get("quantity", 0)),
                        "source_price": float(it.get("source_price", 0.0)),
                    }
                    for it in parsed["items"]
                ]
                return jsonify({
                    "invoice_type": "own_invoice",
                    "items": items_out,
                    "invoice_data": parsed["invoice_data"],
                    "customer_data": parsed["customer_data"],
                })
            from src.pdf_input.parser import parse_pdf_with_format
            items, detected_format = parse_pdf_with_format(temp_path)
        else:
            from src.excel.parser import parse_excel_with_sheet
            items, detected_format = parse_excel_with_sheet(temp_path)

        result = []
        for item in items:
            result.append({
                "ean": str(item.get("ean", "")),
                "product": str(item.get("product", "")),
                "quantity": int(item.get("quantity", 0)),
                "source_price": float(item.get("source_price", 0.0)),
            })

        return jsonify({
            "items": result,
            "parse_report": {
                "format": detected_format,
                "count": len(result),
            },
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _error_response(
            "Die Datei konnte nicht eingelesen werden. Bitte prüfe das Dateiformat oder versuche es erneut.",
            detail=str(e),
        )
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass


# --- GENERATE ---
@app.route('/api/generate', methods=['POST'])
def generate_invoice():
    payload = request.json
    mode = payload.get("mode", "invoice")
    items = payload.get("items", [])
    invoice_data = payload.get("invoice_data", {})
    customer_data = payload.get("customer_data", {})
    create_delivery_note = payload.get("create_delivery_note", False)

    from src.pdf.invoice import generate_invoice as _generate_invoice
    from src.pdf.delivery_note import generate_delivery_note

    invoice_path = os.path.join(tempfile.gettempdir(), f"inv_{uuid.uuid4().hex}.pdf")
    delivery_path = os.path.join(tempfile.gettempdir(), f"del_{uuid.uuid4().hex}.pdf")

    result = {}

    try:
        if mode != "delivery_only":
            _generate_invoice(items, invoice_data, customer_data, invoice_path)
            with open(invoice_path, "rb") as f:
                result["invoice_pdf"] = base64.b64encode(f.read()).decode("ascii")
            result["invoice_filename"] = f"Rechnung_{invoice_data.get('number', '').replace('/', '_')}.pdf"

        if mode == "delivery_only" or create_delivery_note:
            generate_delivery_note(items, invoice_data, customer_data, delivery_path)
            with open(delivery_path, "rb") as f:
                result["delivery_pdf"] = base64.b64encode(f.read()).decode("ascii")
            result["delivery_filename"] = f"Lieferschein_{invoice_data.get('number', '').replace('/', '_')}.pdf"

        return jsonify(result)
    except Exception as e:
        return _error_response(
            "Beim Erstellen der Rechnung/des Lieferscheins ist ein Fehler aufgetreten.",
            detail=str(e),
        )
    finally:
        for p in [invoice_path, delivery_path]:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass


# --- PROVISION ---
@app.route('/api/provision', methods=['POST'])
def generate_provision():
    payload = request.json
    items = payload.get("items", [])
    invoice_data = payload.get("invoice_data", {})
    customer_data = payload.get("customer_data", {})

    from src.pdf.commission_invoice import generate_commission_invoice

    output_path = os.path.join(tempfile.gettempdir(), f"prov_{uuid.uuid4().hex}.pdf")

    try:
        generate_commission_invoice(items, invoice_data, customer_data, output_path)
        with open(output_path, "rb") as f:
            pdf_b64 = base64.b64encode(f.read()).decode("ascii")
            
        filename = f"Provisionsrechnung_{invoice_data.get('number', '').replace('/', '_')}.pdf"
        return jsonify({"pdf": pdf_b64, "filename": filename})
    except Exception as e:
        return _error_response(
            "Beim Erstellen der Provisionsrechnung ist ein Fehler aufgetreten.",
            detail=str(e),
        )
    finally:
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except OSError:
                pass


# --- CREDIT NOTE ---
@app.route('/api/credit-note', methods=['POST'])
def generate_credit_note():
    payload = request.json
    items = payload.get("items", [])
    invoice_data = payload.get("invoice_data", {})
    customer_data = payload.get("customer_data", {})

    from src.pdf.credit_note import generate_credit_note as _generate_credit_note

    output_path = os.path.join(tempfile.gettempdir(), f"cred_{uuid.uuid4().hex}.pdf")

    try:
        _generate_credit_note(items, invoice_data, customer_data, output_path)
        with open(output_path, "rb") as f:
            pdf_b64 = base64.b64encode(f.read()).decode("ascii")
            
        filename = f"Gutschrift_{invoice_data.get('number', '').replace('/', '_')}.pdf"
        return jsonify({"pdf": pdf_b64, "filename": filename})
    except Exception as e:
        return _error_response(
            "Beim Erstellen der Gutschrift ist ein Fehler aufgetreten.",
            detail=str(e),
        )
    finally:
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except OSError:
                pass


# --- ORDER ---
@app.route('/api/order/apply', methods=['POST'])
def order_apply():
    payload = request.json or {}
    source_filename = payload.get("source_filename", "")
    source_file_base64 = payload.get("source_file_base64")
    target_filename = payload.get("target_filename", "")
    target_file_base64 = payload.get("target_file_base64")

    if not source_filename or not source_file_base64:
        return jsonify({"error": "Keine Bestellliste hochgeladen."}), 400
    if not target_filename or not target_file_base64:
        return jsonify({"error": "Keine Ziel-Liste hochgeladen."}), 400

    source_ext = os.path.splitext(source_filename)[1].lower()
    target_ext = os.path.splitext(target_filename)[1].lower()

    source_path = None
    target_path = None
    try:
        source_fd, source_path = tempfile.mkstemp(suffix=source_ext)
        os.close(source_fd)
        target_fd, target_path = tempfile.mkstemp(suffix=target_ext)
        os.close(target_fd)

        with open(source_path, "wb") as f:
            f.write(base64.b64decode(source_file_base64))
        with open(target_path, "wb") as f:
            f.write(base64.b64decode(target_file_base64))

        from src.order.parser import parse_order_source
        from src.order.matcher import read_target_list, apply_order_column

        order_lookup = parse_order_source(source_path)
        target = read_target_list(target_path)
        result = apply_order_column(target, order_lookup)

        return jsonify({
            "headers": result.headers,
            "rows": [[_json_safe(v) for v in row] for row in result.rows],
            "n_matched": result.n_matched,
            "n_not_found": result.n_not_found,
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return _error_response(
            "Beim Abgleich der Order-Mengen ist ein Fehler aufgetreten.",
            detail=str(e),
        )
    finally:
        for p in (source_path, target_path):
            if p:
                try:
                    os.remove(p)
                except OSError:
                    pass


# --- ORDER EXPORT ---
@app.route('/api/order/export', methods=['POST'])
def order_export():
    payload = request.json or {}
    headers = payload.get("headers", [])
    rows = payload.get("rows", [])

    from src.order.exporter import export_order_result

    output_path = os.path.join(tempfile.gettempdir(), f"order_{uuid.uuid4().hex}.xlsx")

    try:
        export_order_result(headers, rows, output_path)
        with open(output_path, "rb") as f:
            xlsx_b64 = base64.b64encode(f.read()).decode("ascii")
        return jsonify({"xlsx_base64": xlsx_b64, "filename": "Order-Ergebnis.xlsx"})
    except Exception as e:
        return _error_response(
            "Beim Export des Order-Ergebnisses ist ein Fehler aufgetreten.",
            detail=str(e),
        )
    finally:
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except OSError:
                pass


# Expose the app object for Vercel Serverless
# Vercel handles the routing automatically based on vercel.json
if __name__ == '__main__':
    app.run(port=5328)

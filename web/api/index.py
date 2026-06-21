from flask import Flask, request, jsonify
import sys
import os
import json
import base64
import tempfile
import uuid

# Add the project root to sys.path so 'src' can be imported
current_dir = os.path.dirname(os.path.abspath(__file__))
if os.path.exists(os.path.join(current_dir, 'src')):
    sys.path.append(current_dir)
else:
    sys.path.append(os.path.abspath(os.path.join(current_dir, '..', '..')))

app = Flask(__name__)

# --- DEBUG (temporary) ---
@app.route('/api/debug', methods=['GET'])
def debug_info():
    info = {
        "current_dir": current_dir,
        "current_dir_listing": sorted(os.listdir(current_dir)) if os.path.isdir(current_dir) else None,
        "src_exists_in_current_dir": os.path.exists(os.path.join(current_dir, 'src')),
        "sys_path": sys.path,
        "cwd": os.getcwd(),
        "cwd_listing": sorted(os.listdir(os.getcwd())),
        "file": os.path.abspath(__file__),
    }
    return jsonify(info)


# --- PARSE ---
@app.route('/api/parse', methods=['POST'])
def parse_file():
    if 'file' not in request.files:
        return jsonify({"error": "Keine Datei hochgeladen."}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Keine Datei ausgewählt."}), 400

    # Save to temp file
    ext = os.path.splitext(file.filename)[1].lower()
    fd, temp_path = tempfile.mkstemp(suffix=ext)
    os.close(fd)
    
    try:
        file.save(temp_path)
        
        if ext == ".pdf":
            from src.pdf_input.parser import parse_pdf
            items = parse_pdf(temp_path)
        else:
            from src.excel.parser import parse_excel
            items = parse_excel(temp_path)

        result = []
        for item in items:
            result.append({
                "ean": str(item.get("ean", "")),
                "product": str(item.get("product", "")),
                "quantity": int(item.get("quantity", 0)),
                "source_price": float(item.get("source_price", 0.0)),
            })

        return jsonify({"items": result})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Unerwarteter Fehler: {e}"}), 500
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
        return jsonify({"error": str(e)}), 500
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
        return jsonify({"error": str(e)}), 500
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
        return jsonify({"error": str(e)}), 500
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

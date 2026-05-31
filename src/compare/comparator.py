"""
Vergleichslogik für den VergleichsBot.
Matched Bestellung gegen Lieferung: EAN → SKU → Produktname.
"""


def compare(order_items, delivery_items):
    """
    Vergleicht zwei Positionslisten miteinander.

    Matching-Reihenfolge: EAN (exakt) → SKU (exakt) → Produktname (case-insensitive)

    Returns:
        list[dict]:
            identifier  – EAN / SKU / Produktname (bestes verfügbares Feld)
            product     – Produktname
            ordered_qty – bestellte Menge (0 wenn nicht bestellt)
            delivered_qty – gelieferte Menge (0 wenn nicht geliefert)
            status      – "OK" | "FEHLT" | "FALSCHE_MENGE" | "NICHT_BESTELLT"
    """
    # Lookup-Indizes für Lieferung aufbauen
    by_ean  = {}
    by_sku  = {}
    by_name = {}
    used    = set()

    for i, item in enumerate(delivery_items):
        if item["ean"]:
            by_ean.setdefault(item["ean"].strip(), []).append(i)
        if item["sku"]:
            by_sku.setdefault(item["sku"].strip().lower(), []).append(i)
        if item["product"]:
            by_name.setdefault(item["product"].strip().lower(), []).append(i)

    results = []

    for order in order_items:
        matched = None

        if order["ean"]:
            for idx in by_ean.get(order["ean"].strip(), []):
                if idx not in used:
                    matched = idx
                    break

        if matched is None and order["sku"]:
            for idx in by_sku.get(order["sku"].strip().lower(), []):
                if idx not in used:
                    matched = idx
                    break

        if matched is None and order["product"]:
            for idx in by_name.get(order["product"].strip().lower(), []):
                if idx not in used:
                    matched = idx
                    break

        identifier = order["ean"] or order["sku"] or order["product"]
        product    = order["product"] or order["sku"] or order["ean"]

        if matched is None:
            results.append({
                "identifier":   identifier,
                "product":      product,
                "ordered_qty":  order["quantity"],
                "delivered_qty": 0,
                "status":       "FEHLT",
            })
        else:
            used.add(matched)
            dlv     = delivery_items[matched]
            ord_qty = order["quantity"]
            dlv_qty = dlv["quantity"]
            results.append({
                "identifier":   identifier,
                "product":      product,
                "ordered_qty":  ord_qty,
                "delivered_qty": dlv_qty,
                "status":       "OK" if dlv_qty == ord_qty else "FALSCHE_MENGE",
            })

    # Positionen in Lieferung, die nicht bestellt wurden
    for i, dlv in enumerate(delivery_items):
        if i not in used:
            identifier = dlv["ean"] or dlv["sku"] or dlv["product"]
            product    = dlv["product"] or dlv["sku"] or dlv["ean"]
            results.append({
                "identifier":   identifier,
                "product":      product,
                "ordered_qty":  0,
                "delivered_qty": dlv["quantity"],
                "status":       "NICHT_BESTELLT",
            })

    return results

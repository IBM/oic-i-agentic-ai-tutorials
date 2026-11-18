"""Purchase-order copies and delivery challans: verify them against the Odoo PO, and record goods received.

A delivery challan that fits the open receipt books the GRN in Odoo (stock picking validated), and any bill
held for a GRN shortage on the same PO gets a note so AP can release it.
"""

import html

from . import chatter
from .controls import match_lines
from .india import inr
from .odoo import Odoo

PRICE_TOLERANCE_PCT = 2.0


def _check(code, category, status, title, detail, action=""):
    c = {"code": code, "category": category, "status": status, "title": title, "detail": detail}
    if action:
        c["action"] = action
    return c


def _vendor_check(checks, po, doc, code):
    gstin = (doc.get("supplier_gstin") or "").upper()
    vendor = po["partner_id"][1]
    ok = not gstin or gstin == po.get("vendor_gstin", gstin)
    checks.append(_check(code, "Vendor", "pass" if ok else "fail", "Supplier matches the PO",
                         f"{vendor} · GSTIN {po.get('vendor_gstin') or '—'}" if ok else
                         f"Document GSTIN {gstin} ≠ PO vendor {vendor} ({po.get('vendor_gstin')})",
                         "" if ok else "Confirm the supplier and PO number."))


def _po(odoo: Odoo, number: str) -> dict | None:
    po = odoo.purchase_order(number) if number else None
    if po:
        po["vendor_gstin"] = odoo.search_read("res.partner", [("id", "=", po["partner_id"][0])], ["vat"])[0]["vat"] or ""
    return po


def _result(checks, po, kind, extra=None):
    fails = [c for c in checks if c["status"] == "fail"]
    for c in fails:
        c["label"] = c["title"]
    return {"kind": kind, "checks": checks, "exceptions": len(fails),
            "po": po and {"id": po["id"], "name": po["name"], "url": po["url"], "state": po["state"],
                          "vendor": po["partner_id"][1], "amount_untaxed": po["amount_untaxed"]},
            **(extra or {})}


# ---- purchase-order copy ------------------------------------------------------------------
def verify_po(doc: dict, odoo: Odoo) -> dict:
    checks = []
    po = _po(odoo, doc.get("po_number", ""))
    if not po:
        checks.append(_check("PO-11", "Purchase order", "fail", "PO exists in Odoo",
                             f"PO '{doc.get('po_number') or '—'}' not found",
                             "Check the PO number; a PO issued outside Odoo needs to be raised in the ERP."))
        return _result(checks, None, "purchase_order", {"summary": "PO not found in Odoo"})
    checks.append(_check("PO-11", "Purchase order", "pass", "PO exists in Odoo",
                         f"{po['name']} · {po['state']} · ₹{inr(po['amount_untaxed'])} untaxed"))
    _vendor_check(checks, po, doc, "PO-12")
    issues = []
    for dl, pl in match_lines(doc.get("line_items") or [], po["lines"]):
        if not pl:
            issues.append(f"{dl['description'][:40]}: not on the Odoo PO")
            continue
        if abs(dl["quantity"] - pl["product_qty"]) > 1e-6:
            issues.append(f"{pl['name'][:40]}: quantity {dl['quantity']:g} vs {pl['product_qty']:g} in Odoo")
        if dl["unit_price"] and pl["price_unit"] and \
                abs(dl["unit_price"] - pl["price_unit"]) / pl["price_unit"] * 100 > PRICE_TOLERANCE_PCT:
            issues.append(f"{pl['name'][:40]}: rate ₹{inr(dl['unit_price'])} vs ₹{inr(pl['price_unit'])} in Odoo")
    checks.append(_check("PO-13", "Purchase order", "fail" if issues else "pass", "Lines agree with the Odoo PO",
                         "; ".join(issues) if issues else f"{len(po['lines'])} line(s): quantities and rates agree",
                         "The copy differs from the approved PO; confirm which version the supplier is working to."
                         if issues else ""))
    result = _result(checks, po, "purchase_order")
    result["summary"] = f"{po['name']} verified" if not result["exceptions"] else f"{po['name']}: copy differs from Odoo"
    odoo.note("purchase.order", po["id"], _html("Purchase-order copy received", doc, checks))
    return result


# ---- delivery challan → GRN --------------------------------------------------------------
def receive(doc: dict, odoo: Odoo) -> dict:
    checks = []
    po = _po(odoo, doc.get("po_number", ""))
    challan = doc.get("challan_number") or ""
    if not po:
        checks.append(_check("GRN-11", "Goods receipt", "fail", "PO exists in Odoo",
                             f"PO '{doc.get('po_number') or '—'}' not found",
                             "Hold the goods at the gate until purchasing confirms the order."))
        return _result(checks, None, "delivery_challan", {"summary": "PO not found — nothing received"})
    checks.append(_check("GRN-11", "Goods receipt", "pass", "PO exists in Odoo", f"{po['name']} · {po['partner_id'][1]}"))
    _vendor_check(checks, po, doc, "GRN-12")

    def notes(text):
        return odoo.search_read("mail.message", [("model", "=", "stock.picking"), ("body", "ilike", f"{text} {challan}")],
                                ["res_id"]) if challan else []
    booked, reversed_ = notes("Goods received against challan"), notes("Reversed challan")
    seen = booked if len(booked) > len(reversed_) else []
    checks.append(_check("DUP-03", "Risk", "fail" if seen else "pass", "Challan not already received",
                         f"Challan {challan} was already booked on receipt #{seen[0]['res_id']}" if seen
                         else f"Challan {challan or '—'} not booked before"))

    open_pick = next((r for r in po["receipts"] if r["state"] not in ("done", "cancel")), None)
    moves = odoo.search_read("stock.move", [("picking_id", "=", open_pick["id"])],
                             ["id", "product_id", "product_uom_qty", "purchase_line_id"]) if open_pick else []
    pairs = match_lines(doc.get("line_items") or [], [{**pl, "open": pl["product_qty"] - pl["qty_received"]}
                                                    for pl in po["lines"]])
    issues, plan = [], []
    for dl, pl in pairs:
        if not pl:
            issues.append(f"{dl['description'][:40]}: not on {po['name']}")
            continue
        move = next((m for m in moves if m["product_id"][0] == pl["product_id"][0]), None)
        if not move:
            issues.append(f"{pl['name'][:40]}: nothing open to receive (ordered {pl['product_qty']:g}, received {pl['qty_received']:g})")
        elif dl["quantity"] > move["product_uom_qty"] + 1e-6:
            issues.append(f"{pl['name'][:40]}: challan {dl['quantity']:g} vs open {move['product_uom_qty']:g}")
        else:
            plan.append((move, dl["quantity"], pl))
    checks.append(_check("GRN-13", "Goods receipt", "fail" if issues else "pass", "Quantities fit the open receipt",
                         "; ".join(issues) if issues else
                         "; ".join(f"{pl['name'][:40]}: {q:g} of {m['product_uom_qty']:g} open" for m, q, pl in plan),
                         "Stores to count the delivery and confirm with purchasing before accepting it." if issues else ""))

    result = _result(checks, po, "delivery_challan")
    if result["exceptions"] or not plan:
        result["summary"] = "Not received — exception for stores and purchasing"
        return result

    for move, qty, _pl in plan:
        odoo.call("stock.move", "write", [move["id"]], {"quantity": qty, "picked": True})
    odoo.call("stock.picking", "button_validate", [open_pick["id"]], context={"skip_backorder": False,
                                                                             "picking_ids_not_to_backorder": []})
    odoo.note("stock.picking", open_pick["id"], _html(f"Goods received against challan {challan}", doc, checks))
    released = _notify_held_bills(odoo, po, open_pick["name"], challan)
    result.update(summary=f"Received {open_pick['name']} against {po['name']}"
                          + (f" · {len(released)} held bill(s) can now be released" if released else ""),
                  receipt={"id": open_pick["id"], "name": open_pick["name"],
                           "url": f"{odoo.url}/odoo/action-stock.action_picking_tree_all/{open_pick['id']}"},
                  released_bills=released)
    return result


def _notify_held_bills(odoo: Odoo, po: dict, picking: str, challan: str) -> list[dict]:
    bills = odoo.search_read("account.move", [("move_type", "=", "in_invoice"), ("state", "=", "draft"),
                                              ("invoice_origin", "=", po["name"])], ["id", "name", "ref"])
    for b in bills:
        odoo.note("account.move", b["id"],
                  f"<p><b>AP agent</b>: balance quantity received on {html.escape(picking)} (challan "
                  f"{html.escape(challan)}). The GRN shortage on this bill is resolved; it can be approved as invoiced.</p>")
    return [{"id": b["id"], "ref": b["ref"]} for b in bills]


def _html(title: str, doc: dict, checks: list[dict]) -> str:
    return chatter.note(html.escape(title), checks)


def undo_receipt(odoo: Odoo, picking_id: int, challan: str = "") -> int:
    """Demo reset: return the received goods to the vendor, then re-open the quantity as a pending receipt, so
    the challan scenario can be replayed. Returns the new pending receipt id."""
    pick = odoo.search_read("stock.picking", [("id", "=", picking_id)],
                            ["picking_type_id", "location_id", "location_dest_id", "partner_id", "origin", "move_ids"])[0]
    ptype = odoo.search_read("stock.picking.type", [("id", "=", pick["picking_type_id"][0])], ["return_picking_type_id"])[0]
    moves = odoo.search_read("stock.move", [("id", "in", pick["move_ids"])],
                             ["id", "product_id", "quantity", "purchase_line_id", "uom_id"])

    def picking(type_id, src, dest, lines, validate):
        pid = odoo.call("stock.picking", "create", {
            "picking_type_id": type_id, "location_id": src, "location_dest_id": dest,
            "partner_id": pick["partner_id"][0], "origin": pick["origin"],
            "move_ids": [(0, 0, {"product_id": m["product_id"][0], "product_uom_qty": m["quantity"],
                                 "uom_id": m["uom_id"][0], "location_id": src, "location_dest_id": dest,
                                 "purchase_line_id": m["purchase_line_id"][0], **extra(m)}) for m in lines]})
        odoo.call("stock.picking", "action_confirm", [pid])
        if validate:
            for mv in odoo.search_read("stock.move", [("picking_id", "=", pid)], ["id", "product_uom_qty"]):
                odoo.call("stock.move", "write", [mv["id"]], {"quantity": mv["product_uom_qty"], "picked": True})
            odoo.call("stock.picking", "button_validate", [pid])
        return pid

    odoo.note("stock.picking", picking_id, f"<p>Reversed challan {html.escape(challan)} (demo reset)</p>")
    src, dest = pick["location_id"][0], pick["location_dest_id"][0]
    extra = lambda m: {"origin_returned_move_id": m["id"], "to_refund": True}  # noqa: E731
    picking(ptype["return_picking_type_id"][0], dest, src, moves, validate=True)
    extra = lambda m: {}  # noqa: E731
    return picking(pick["picking_type_id"][0], src, dest, moves, validate=False)

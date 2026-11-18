"""Internal AP Copilot tools: worklist, invoice / PO / vendor lookups and exception approval in Odoo."""

from datetime import date

from ibm_watsonx_orchestrate.agent_builder.tools import ToolPermission, tool

from erp import ODOO_CREDENTIALS, PAYMENT_LABELS, STATE_LABELS, Erp, mask


@tool(name="ap_exception_worklist", permission=ToolPermission.READ_ONLY, expected_credentials=ODOO_CREDENTIALS)
def ap_exception_worklist() -> dict:
    """List vendor bills on hold for AP review in Odoo, with the exception raised by the AP agent and the
    value at risk. Use for questions like 'what needs my attention', 'show open exceptions', 'what is on hold'."""
    erp = Erp()
    bills = erp.read("account.move", [("move_type", "=", "in_invoice"), ("state", "=", "draft"),
                                      ("activity_ids", "!=", False)],
                     ["id", "ref", "partner_id", "amount_total", "invoice_date", "invoice_origin", "activity_ids"],
                     order="invoice_date desc", limit=50)
    items = [{
        "bill_id": b["id"], "supplier_invoice": b["ref"], "vendor": b["partner_id"][1], "po": b["invoice_origin"],
        "amount_inr": b["amount_total"], "invoice_date": b["invoice_date"], "exception": "; ".join(erp.open_reviews(b)),
        "odoo_link": erp.bill_url(b["id"]),
    } for b in bills]
    return {"open_exceptions": len(items), "value_on_hold_inr": round(sum(i["amount_inr"] for i in items), 2),
            "items": items}


@tool(name="invoice_status", permission=ToolPermission.READ_ONLY, expected_credentials=ODOO_CREDENTIALS)
def invoice_status(reference: str) -> dict:
    """Get the full AP status of a supplier invoice from Odoo: booking state, payment state, amounts, TDS
    withheld, due date, PO, open review tasks and the AP agent's control results.

    Args:
        reference: Supplier invoice number (e.g. 'NPI/GJ/26-27/1182'), Odoo bill number (e.g. 'BILL/26-27/10/0007') or bill id.
    """
    erp = Erp()
    b = erp.find_bill(reference)
    if not b:
        return {"found": False, "message": f"No vendor bill found for '{reference}'"}
    return {
        "found": True, "bill_id": b["id"], "bill_number": b["name"] or "(draft — not yet numbered)",
        "supplier_invoice": b["ref"], "vendor": b["partner_id"][1], "po": b["invoice_origin"],
        "status": STATE_LABELS.get(b["state"], b["state"]), "payment": PAYMENT_LABELS.get(b["payment_state"], b["payment_state"]),
        "invoice_date": b["invoice_date"], "due_date": b["invoice_date_due"],
        "taxable_inr": b["amount_untaxed"], "gst_inr": b["amount_tax"], "invoice_total_inr": b["amount_total"],
        "tds_to_withhold_at_payment_inr": erp.tds_withheld(b),
        "net_payable_inr": round(b["amount_total"] - erp.tds_withheld(b), 2),
        "open_review_tasks": erp.open_reviews(b), "ap_agent_controls": erp.agent_note(b["id"]),
        "odoo_link": erp.bill_url(b["id"]),
    }


@tool(name="purchase_order_status", permission=ToolPermission.READ_ONLY, expected_credentials=ODOO_CREDENTIALS)
def purchase_order_status(po_number: str) -> dict:
    """Show a purchase order from Odoo with ordered, received (GRN / service entry) and billed quantity per line,
    goods receipts and open value. Use for 3-way match questions such as 'what was received on PO X'.

    Args:
        po_number: Purchase order number, e.g. 'MSC-PO-26-0158'.
    """
    erp = Erp()
    rows = erp.read("purchase.order", [("name", "=ilike", po_number.strip())],
                    ["id", "name", "partner_id", "state", "date_order", "amount_untaxed", "picking_ids", "invoice_ids"])
    if not rows:
        return {"found": False, "message": f"PO '{po_number}' not found"}
    po = rows[0]
    lines = erp.read("purchase.order.line", [("order_id", "=", po["id"])],
                     ["product_id", "product_qty", "qty_received", "qty_invoiced", "price_unit"])
    receipts = erp.read("stock.picking", [("id", "in", po["picking_ids"])], ["name", "state", "date_done"]) if po["picking_ids"] else []
    return {
        "found": True, "po": po["name"], "vendor": po["partner_id"][1], "state": po["state"],
        "order_date": po["date_order"][:10], "untaxed_value_inr": po["amount_untaxed"],
        "lines": [{"item": l["product_id"][1].split("] ", 1)[-1], "ordered": l["product_qty"],
                   "received": l["qty_received"], "billed": l["qty_invoiced"], "unit_price_inr": l["price_unit"],
                   "received_not_billed": round(l["qty_received"] - l["qty_invoiced"], 3),
                   "not_yet_received": round(l["product_qty"] - l["qty_received"], 3)} for l in lines],
        "goods_receipts": [{"grn": r["name"], "state": r["state"], "date": (r["date_done"] or "")[:10]} for r in receipts],
        "bills_linked": len(po["invoice_ids"]),
        "odoo_link": f"{erp.url}/odoo/purchase/{po['id']}",
    }


@tool(name="vendor_profile", permission=ToolPermission.READ_ONLY, expected_credentials=ODOO_CREDENTIALS)
def vendor_profile(vendor: str) -> dict:
    """Look up a supplier in the Odoo vendor master: GSTIN, PAN, state, TDS section and e-invoice tags,
    verified bank account (masked), and financial-year spend / open bills.

    Args:
        vendor: Vendor name (partial is fine) or GSTIN.
    """
    erp = Erp()
    q = vendor.strip()
    fields = ["id", "name", "vat", "email", "city", "state_id", "category_id"]
    rows = erp.read("res.partner", [("vat", "=", q.upper())], fields, limit=1) or \
        erp.read("res.partner", [("name", "ilike", q), ("supplier_rank", ">", 0)], fields, limit=1)
    if not rows:
        return {"found": False, "message": f"No vendor matching '{vendor}'"}
    v = rows[0]
    tags = [t["name"] for t in erp.read("res.partner.category", [("id", "in", v["category_id"])], ["name"])]
    banks = erp.read("res.partner.bank", [("partner_id", "=", v["id"])], ["account_number", "bank_name", "bank_bic"])
    today = date.today()
    fy_start = date(today.year if today.month >= 4 else today.year - 1, 4, 1).isoformat()
    bills = erp.read("account.move", [("move_type", "=", "in_invoice"), ("partner_id", "=", v["id"]),
                                      ("state", "!=", "cancel")], ["state", "amount_untaxed", "invoice_date"])
    return {
        "found": True, "vendor": v["name"], "gstin": v["vat"], "pan": (v["vat"] or "")[2:12],
        "location": f"{v['city']}, {v['state_id'][1] if v['state_id'] else ''}", "email": v["email"],
        "policy_tags": tags,
        "verified_bank_accounts": [{"bank": b["bank_name"], "account": mask(b["account_number"]), "ifsc": b["bank_bic"]}
                                   for b in banks],
        "fy_booked_untaxed_inr": round(sum(b["amount_untaxed"] for b in bills
                                           if b["state"] == "posted" and (b["invoice_date"] or "") >= fy_start), 2),
        "bills_on_hold": sum(b["state"] == "draft" for b in bills),
        "odoo_link": f"{erp.url}/odoo/contacts/{v['id']}",
    }


@tool(name="approve_ap_exception", permission=ToolPermission.READ_WRITE, expected_credentials=ODOO_CREDENTIALS)
def approve_ap_exception(reference: str, justification: str) -> dict:
    """Approve a vendor bill that is on hold and post it to the general ledger in Odoo, closing its review task
    and recording the justification in the audit trail. Only call after the user explicitly confirms approval.

    Args:
        reference: Supplier invoice number, Odoo bill number or bill id of the bill on hold.
        justification: Why the exception is being overridden (recorded on the bill).
    """
    erp = Erp()
    b = erp.find_bill(reference)
    if not b:
        return {"approved": False, "message": f"No vendor bill found for '{reference}'"}
    if b["state"] != "draft":
        return {"approved": False, "message": f"Bill is already {STATE_LABELS.get(b['state'], b['state'])}"}
    erp.call("account.move", "action_post", [b["id"]])
    if b["activity_ids"]:
        erp.call("mail.activity", "action_feedback", b["activity_ids"], feedback=f"Approved via AP Copilot: {justification}")
    erp.call("account.move", "message_post", [b["id"]], body=f"<p>Approved via AP Copilot (watsonx Orchestrate): {justification}</p>", body_is_html=True,
             message_type="comment", subtype_xmlid="mail.mt_note")
    posted = erp.read("account.move", [("id", "=", b["id"])], ["name", "amount_total"])[0]
    return {"approved": True, "bill_number": posted["name"], "amount_inr": posted["amount_total"],
            "odoo_link": erp.bill_url(b["id"])}


@tool(name="expense_claims", permission=ToolPermission.READ_ONLY, expected_credentials=ODOO_CREDENTIALS)
def expense_claims(status: str = "pending", employee: str = "") -> dict:
    """List employee expense claims in Odoo created from receipts (taxi, hotel, meals, card slips), with the
    policy exception the AP agent raised. Use for 'pending expense approvals', 'what did Priya claim', etc.

    Args:
        status: "pending" for claims awaiting the manager, or "all".
        employee: Optional employee name filter.
    """
    erp = Erp()
    domain = [("state", "=", "draft")] if status == "pending" else []
    if employee:
        domain.append(("employee_id.name", "ilike", employee))
    rows = erp.read("hr.expense", domain, ["id", "name", "employee_id", "total_amount", "date", "state", "payment_mode",
                                           "activity_ids"], order="date desc", limit=50)
    items = [{
        "expense_id": r["id"], "description": r["name"], "employee": r["employee_id"][1], "amount_inr": r["total_amount"],
        "date": r["date"], "status": {"draft": "Awaiting manager approval"}.get(r["state"], r["state"].replace("_", " ")),
        "paid_by": "Company card" if r["payment_mode"] == "company_account" else "Employee (reimbursable)",
        "exception": "; ".join(a["summary"] for a in erp.read("mail.activity", [("id", "in", r["activity_ids"])], ["summary"]))
        if r["activity_ids"] else "",
    } for r in rows]
    return {"count": len(items), "total_inr": round(sum(i["amount_inr"] for i in items), 2), "items": items}

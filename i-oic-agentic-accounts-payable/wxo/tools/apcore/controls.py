"""ERP-side AP controls, evaluated against live Odoo data after the wxO flow has extracted the invoice.
Runs inside the flow's `erp_controls` tool node; the routing decision itself is the flow's decision table.

Every control returns the same shape as the flow's statutory checks:
    {code, category, status: pass|warn|fail|info, title, detail, action?}
plus the counts the flow's decision table routes on: touchless (post), exception (draft + review task)
or blocked (no bill).
"""

from datetime import date
from difflib import SequenceMatcher

from .india import TDS_RULES, inr
from .odoo import Odoo

PRICE_TOLERANCE_PCT = 2.0


FAIL_LABELS = {
    "DOC-01": "Missing invoice particulars", "DOC-02": "HSN/SAC missing", "GST-01": "Invalid supplier GSTIN",
    "GST-02": "Invalid buyer GSTIN", "GST-03": "Wrong GST regime", "GST-04": "Non-standard GST rate",
    "GST-05": "Wrong buyer GSTIN", "MATH-01": "Line totals don't add up", "MATH-02": "Invoice total mismatch",
    "VEND-01": "Supplier not in vendor master", "DUP-01": "Duplicate invoice", "BANK-01": "Bank account changed",
    "EINV-02": "IRN missing", "PO-01": "PO not found", "PO-02": "Line not on PO", "PO-03": "Price above PO",
    "GRN-01": "GRN shortage", "TDS-01": "TDS section mismatch",
}


def _check(code, category, status, title, detail, action=""):
    c = {"code": code, "category": category, "status": status, "title": title, "detail": detail}
    if action:
        c["action"] = action
    return c


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, (a or "").lower(), (b or "").lower()).ratio()


def match_lines(inv_lines: list[dict], po_lines: list[dict]) -> list[tuple[dict, dict | None]]:
    """Pair each invoice line with its best PO line by description similarity."""
    free = list(po_lines)
    pairs = []
    for il in inv_lines:
        best = max(free, key=lambda pl: _similar(il["description"], pl["name"]), default=None)
        if best and _similar(il["description"], best["name"]) >= 0.45:
            free.remove(best)
            pairs.append((il, best))
        else:
            pairs.append((il, None))
    return pairs


def evaluate(invoice: dict, payment_nature: dict, odoo: Odoo) -> dict:
    checks: list[dict] = [dict(c) for c in invoice.get("checks") or []]  # statutory checks from the wxO flow
    company = odoo.company()
    taxable = float(invoice.get("taxable_value") or 0)
    total = float(invoice.get("total_amount") or 0)

    # ---- Vendor master -----------------------------------------------------------------
    vendor = odoo.find_vendor(invoice.get("supplier_gstin", ""), invoice.get("supplier_name", ""))
    if not vendor:
        checks.append(_check("VEND-01", "Vendor", "fail", "Supplier exists in vendor master",
                             f"No vendor with GSTIN {invoice.get('supplier_gstin') or '—'} in Odoo",
                             "Onboard the supplier (KYC, GSTIN, PAN, bank proof) before processing the invoice."))
        return _decide(checks, invoice, None, None, [], {"applicable": False}, company)

    if vendor["vat"] == invoice.get("supplier_gstin"):
        checks.append(_check("VEND-01", "Vendor", "pass", "Supplier exists in vendor master",
                             f"Matched {vendor['name']} on GSTIN {vendor['vat']}"))
    else:
        checks.append(_check("VEND-01", "Vendor", "fail", "Supplier GSTIN matches vendor master",
                             f"Invoice GSTIN {invoice.get('supplier_gstin') or '—'} ≠ master GSTIN {vendor['vat']}",
                             "Confirm the supplier's registration; ITC is only available on the registered GSTIN."))

    if invoice.get("buyer_gstin") == company["gstin"]:
        checks.append(_check("GST-05", "GST", "pass", "Billed to our GSTIN",
                             f"Buyer GSTIN {company['gstin']} matches {company['name']}"))
    else:
        checks.append(_check("GST-05", "GST", "fail", "Billed to our GSTIN",
                             f"Invoice is addressed to GSTIN {invoice.get('buyer_gstin') or '—'}, ours is {company['gstin']}",
                             "Ask the supplier to re-issue the invoice to the correct GSTIN, otherwise ITC is lost."))

    # ---- Duplicate detection -----------------------------------------------------------
    same_ref = odoo.bills_for(vendor["id"], invoice.get("invoice_number", ""))
    if same_ref:
        b = same_ref[0]
        checks.append(_check("DUP-01", "Risk", "fail", "Not a duplicate invoice",
                             f"Invoice {invoice.get('invoice_number')} already booked as {b['name'] or 'draft bill'} "
                             f"(#{b['id']}, {b['state']}, ₹{inr(b['amount_total'])}) on {b['invoice_date']}",
                             "Blocked to prevent double payment. Reply to the supplier quoting the original bill."))
    else:
        near = [b for b in odoo.bills_for(vendor["id"]) if abs(b["amount_untaxed"] - taxable) < 1 and taxable]
        checks.append(_check("DUP-01", "Risk", "warn" if near else "pass", "Not a duplicate invoice",
                             f"Same amount as bill {near[0]['name']} with a different number — possible re-issue" if near
                             else "No bill with this supplier invoice number in Odoo"))

    # ---- Bank account verification (payment fraud) ------------------------------------
    acct = (invoice.get("bank_account") or "").strip()
    master = {b["account_number"].replace(" ", ""): b for b in vendor["banks"]}
    bank_id = None
    if not acct:
        checks.append(_check("BANK-01", "Risk", "info", "Remittance account matches vendor master",
                             "No bank details printed; payment will use the master account"))
        bank_id = next(iter(master.values()), {}).get("id")
    elif acct in master:
        bank_id = master[acct]["id"]
        checks.append(_check("BANK-01", "Risk", "pass", "Remittance account matches vendor master",
                             f"A/c ···{acct[-4:]} ({master[acct]['bank_name']}) is the verified account"))
    else:
        known = ", ".join(f"···{a[-4:]}" for a in master) or "none"
        checks.append(_check("BANK-01", "Risk", "fail", "Remittance account matches vendor master",
                             f"Invoice asks for payment to {invoice.get('bank_name') or 'bank'} A/c ···{acct[-4:]} "
                             f"(IFSC {invoice.get('bank_ifsc') or '—'}); master has {known}",
                             "Possible payment-diversion fraud. Do not update bank details from an invoice — verify by "
                             "call-back to the registered contact and get a cancelled cheque before any change."))

    # ---- e-Invoice -----------------------------------------------------------------------
    if vendor["einvoice_applicable"]:
        ok = bool(invoice.get("irn"))
        checks.append(_check("EINV-02", "E-invoice", "pass" if ok else "fail", "IRN present (e-invoicing applies)",
                             "Supplier is e-invoice applicable; IRN " + (f"{invoice['irn'][:12]}… present" if ok else "missing"),
                             "" if ok else "Reject: without an IRN this is not a valid tax invoice and ITC cannot be claimed. "
                                           "Ask the supplier to register it on the IRP."))

    # ---- PO / GRN 3-way match ------------------------------------------------------------
    po = odoo.purchase_order(invoice.get("po_number", "")) if invoice.get("po_number") else None
    pairs: list = []
    if not po:
        checks.append(_check("PO-01", "3-way match", "fail", "Valid purchase order referenced",
                             f"PO '{invoice.get('po_number') or '—'}' not found in Odoo",
                             "Route to the requisitioner to confirm the PO, or raise a retrospective PO."))
    elif po["partner_id"][0] != vendor["id"]:
        checks.append(_check("PO-01", "3-way match", "fail", "Valid purchase order referenced",
                             f"{po['name']} belongs to {po['partner_id'][1]}, not {vendor['name']}",
                             "Confirm the PO number with the supplier."))
        po = None
    else:
        checks.append(_check("PO-01", "3-way match", "pass", "Valid purchase order referenced",
                             f"{po['name']} · {po['state']} · ₹{inr(po['amount_untaxed'])} untaxed"))
        pairs = match_lines(invoice.get("line_items") or [], po["lines"])
        _price_and_qty_checks(checks, pairs, po)

    # ---- TDS -------------------------------------------------------------------------------
    tds = _tds(checks, vendor, payment_nature or {}, taxable, odoo)

    result = _decide(checks, invoice, vendor, po, pairs, tds, company)
    result["bank_id"] = bank_id
    return result


def _price_and_qty_checks(checks, pairs, po):
    tol = PRICE_TOLERANCE_PCT
    price_issues, qty_issues, unmatched, variance = [], [], [], 0.0
    for il, pl in pairs:
        if not pl:
            unmatched.append(il["description"])
            continue
        if pl["price_unit"] and abs(il["unit_price"] - pl["price_unit"]) / pl["price_unit"] * 100 > tol:
            delta = round((il["unit_price"] - pl["price_unit"]) * il["quantity"], 2)
            variance += delta
            price_issues.append(f"{pl['name'][:40]}: billed ₹{inr(il['unit_price'])} vs PO ₹{inr(pl['price_unit'])} "
                                f"({(il['unit_price'] / pl['price_unit'] - 1) * 100:+.1f}%, ₹{inr(delta)})")
        open_qty = round(pl["qty_received"] - pl["qty_invoiced"], 3)
        if il["quantity"] > open_qty + 1e-6:
            qty_issues.append(f"{pl['name'][:40]}: billed {il['quantity']:g}, received {pl['qty_received']:g}, "
                              f"already billed {pl['qty_invoiced']:g} → open {open_qty:g}")

    checks.append(_check("PO-02", "3-way match", "fail" if unmatched else "pass", "Every line maps to a PO line",
                         ("Not on PO: " + "; ".join(unmatched)) if unmatched else f"{len(pairs)} line(s) matched to {po['name']}",
                         "Ask the buyer whether the extra items were ordered." if unmatched else ""))
    checks.append(_check("PO-03", "3-way match", "fail" if price_issues else "pass",
                         f"Unit price within ±{tol:g}% of PO",
                         "; ".join(price_issues) if price_issues else "All unit prices agree with the PO",
                         f"Request a credit note for ₹{inr(variance)} or obtain buyer approval for the revised price."
                         if price_issues else ""))
    grns = ", ".join(r["name"] for r in po["receipts"] if r["state"] == "done") or "service entry on PO"
    pending = ", ".join(r["name"] for r in po["receipts"] if r["state"] not in ("done", "cancel"))
    checks.append(_check("GRN-01", "3-way match", "fail" if qty_issues else "pass",
                         "Billed quantity ≤ received quantity (GRN)",
                         ("; ".join(qty_issues) + f". Receipts: {grns}" + (f"; backorder {pending} open" if pending else ""))
                         if qty_issues else f"Quantities covered by {grns}",
                         "Post for the received quantity and request a credit note for the balance, "
                         "or hold until the backorder is received." if qty_issues else ""))


def _tds(checks, vendor, nature, taxable, odoo) -> dict:
    master = vendor.get("tds_nature")
    ai = nature.get("nature")
    ai_conf = float(nature.get("confidence") or 0)
    ai_text = f"AI classified the payment as '{ai}' ({ai_conf:.0%}): {nature.get('rationale', '')}".strip()
    applied = master

    if master and ai and ai != master and ai_conf >= 0.7 and ai in TDS_RULES:
        checks.append(_check("TDS-01", "TDS", "fail", "TDS section consistent with nature of payment",
                             f"Vendor master says {TDS_RULES[master]['label']} but {ai_text}",
                             "Tax team to confirm the correct section and update the vendor master tag."))
    elif not master and ai in ("professional", "technical", "contract", "rent") and ai_conf >= 0.7:
        checks.append(_check("TDS-01", "TDS", "fail", "TDS section consistent with nature of payment",
                             f"Vendor master has no TDS section but {ai_text}",
                             "Confirm the TDS section and tag the vendor in Odoo so future bills are touchless."))
        applied = ai if ai in TDS_RULES else None
    else:
        checks.append(_check("TDS-01", "TDS", "pass", "TDS section consistent with nature of payment",
                             (f"Vendor master: {TDS_RULES[master]['label']} — " if master else "No TDS section on vendor — ") + ai_text))

    if not applied:
        return {"applicable": False, "nature": ai}
    rule = TDS_RULES[applied]
    fy_billed = odoo.fy_billed_untaxed(vendor["id"])
    if applied == "goods":
        base = min(taxable, max(0.0, fy_billed + taxable - rule["threshold_aggregate"]))
    else:
        base = taxable if taxable > rule["threshold_single"] or fy_billed + taxable > rule["threshold_single"] else 0.0
    amount = round(base * rule["rate"] / 100)
    status_detail = (f"Sec {rule['section']} (formerly {rule['legacy']}) @ {rule['rate']:g}% on ₹{inr(base)} = ₹{inr(amount)}; "
                     f"FY-to-date billed ₹{inr(fy_billed)}") if amount else \
        f"Sec {rule['section']}: below threshold (FY-to-date ₹{inr(fy_billed)}), no deduction"
    checks.append(_check("TDS-02", "TDS", "pass", "TDS computed", status_detail))
    return {"applicable": amount > 0, "nature": applied, "label": rule["label"], "section": rule["section"],
            "legacy": rule["legacy"], "rate": rule["rate"], "base": base, "amount": amount,
            "odoo_tax": rule["odoo_tax"]}


def _decide(checks, invoice, vendor, po, pairs, tds, company) -> dict:
    if any(c["code"] == "DUP-01" and c["status"] == "fail" for c in checks):
        for c in checks:  # quantities were consumed by the original bill — a consequence, not a second issue
            if c["code"] == "GRN-01" and c["status"] == "fail":
                c.update(status="info", detail="Quantity already billed against the original invoice", action="")
    fails = [c for c in checks if c["status"] == "fail"]
    for c in fails:
        c["label"] = FAIL_LABELS.get(c["code"], c["title"])
    total = float(invoice.get("total_amount") or 0)
    return {  # the counts feed the flow's routing decision table
        "duplicates": sum(c["code"] == "DUP-01" for c in fails),
        "exceptions": len(fails),
        "checks": checks,
        "vendor": vendor and {k: vendor[k] for k in ("id", "name", "vat", "email", "tags", "url", "tds_nature",
                                                      "einvoice_applicable")},
        "po": po and {"id": po["id"], "name": po["name"], "url": po["url"], "state": po["state"],
                      "receipts": po["receipts"], "amount_untaxed": po["amount_untaxed"]},
        "lines": [{"invoice": il, "po_line": pl and {k: pl[k] for k in ("id", "name", "product_id", "product_qty",
                                                                        "qty_received", "qty_invoiced", "price_unit",
                                                                        "tax_ids")}}
                  for il, pl in pairs],
        "tds": tds,
        "net_payable": round(total - (tds.get("amount") or 0), 2),
        "evaluated_on": date.today().isoformat(),
        "company": company["name"],
    }


def bill_lines(result: dict, odoo: Odoo, received_qty_only: bool = False) -> list[dict]:
    """Translate matched invoice lines into Odoo vendor-bill lines linked to the PO."""
    tds = result.get("tds") or {}
    tds_tax = odoo.tax_id(tds["odoo_tax"]) if tds.get("applicable") else None
    lines = []
    for pair in result["lines"]:
        il, pl = pair["invoice"], pair["po_line"]
        qty = il["quantity"]
        if pl and received_qty_only:
            qty = max(0.0, min(qty, pl["qty_received"] - pl["qty_invoiced"]))
        line = {"name": il["description"], "quantity": qty, "price_unit": il["unit_price"]}
        if pl:
            line.update(product_id=pl["product_id"][0], purchase_line_id=pl["id"])
            taxes = list(pl["tax_ids"])
        else:
            taxes = []
        if tds_tax:
            taxes.append(tds_tax)
        line["tax_ids"] = [(6, 0, taxes)]
        if qty > 0:
            lines.append(line)
    return lines

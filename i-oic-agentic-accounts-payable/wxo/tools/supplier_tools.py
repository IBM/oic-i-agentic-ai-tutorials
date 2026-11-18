"""Supplier Desk tools: self-service invoice status for suppliers.

Every lookup requires the supplier's GSTIN and only returns bills belonging to that GSTIN,
with supplier-safe wording (no internal control notes, fraud flags or other vendors' data).
"""

from ibm_watsonx_orchestrate.agent_builder.tools import ToolPermission, tool

from erp import ODOO_CREDENTIALS, PAYMENT_LABELS, Erp

SUPPLIER_REASONS = {
    "GRN shortage": "Billed quantity is higher than the quantity received at our plant",
    "Price above PO": "Invoice prices differ from the purchase order",
    "Wrong GST regime": "GST appears to be charged under the wrong regime (CGST/SGST vs IGST)",
    "IRN missing": "The invoice is missing its e-invoice IRN",
    "Bank account changed": "Bank details need verification with your registered contact",
    "Wrong buyer GSTIN": "The invoice is addressed to an incorrect GSTIN",
    "PO not found": "The purchase order reference could not be matched",
    "Line not on PO": "Some invoice lines are not on the purchase order",
    "Above ₹25 lakh touchless limit": "The invoice is with our approver for sign-off",
}


def _supplier_status(erp: Erp, b: dict) -> dict:
    reviews = erp.open_reviews(b)
    reasons = sorted({text for key, text in SUPPLIER_REASONS.items() for r in reviews if key.lower() in r.lower()})
    if b["state"] == "draft":
        status = "Under review by Accounts Payable"
    elif b["state"] == "cancel":
        status = "Rejected — please contact Accounts Payable or submit a corrected invoice"
    else:
        status = {"paid": "Paid", "in_payment": "Payment in progress"}.get(b["payment_state"], "Approved — scheduled for payment")
    out = {"supplier_invoice": b["ref"], "invoice_date": b["invoice_date"], "status": status,
           "payment": PAYMENT_LABELS.get(b["payment_state"], b["payment_state"]),
           "invoice_value_inr": b["amount_total"], "tds_withheld_inr": erp.tds_withheld(b),
           "net_payable_inr": round(b["amount_total"] - erp.tds_withheld(b), 2)}
    if b["state"] == "posted":
        out["expected_payment_date"] = b["invoice_date_due"]
    if reasons:
        out["action_needed"] = reasons
    return out


def _vendor_id(erp: Erp, gstin: str) -> int | None:
    rows = erp.read("res.partner", [("vat", "=", (gstin or "").strip().upper())], ["id"], limit=1)
    return rows[0]["id"] if rows else None


@tool(name="supplier_invoice_status", permission=ToolPermission.READ_ONLY, expected_credentials=ODOO_CREDENTIALS)
def supplier_invoice_status(invoice_number: str, supplier_gstin: str) -> dict:
    """Tell a supplier the processing and payment status of one of their invoices.

    Args:
        invoice_number: The supplier's own invoice number, e.g. 'KPA/26-27/073'.
        supplier_gstin: The supplier's 15-character GSTIN, used to verify the caller owns the invoice.
    """
    erp = Erp()
    vid = _vendor_id(erp, supplier_gstin)
    if not vid:
        return {"verified": False, "message": "This GSTIN is not registered as a supplier with us."}
    b = erp.find_bill(invoice_number)
    if not b or b["partner_id"][0] != vid:
        return {"verified": True, "found": False,
                "message": f"We have not received invoice {invoice_number} from this GSTIN yet."}
    return {"verified": True, "found": True, **_supplier_status(erp, b)}


@tool(name="supplier_open_invoices", permission=ToolPermission.READ_ONLY, expected_credentials=ODOO_CREDENTIALS)
def supplier_open_invoices(supplier_gstin: str) -> dict:
    """List all invoices a supplier has submitted with their status and expected payment dates.

    Args:
        supplier_gstin: The supplier's 15-character GSTIN.
    """
    erp = Erp()
    vid = _vendor_id(erp, supplier_gstin)
    if not vid:
        return {"verified": False, "message": "This GSTIN is not registered as a supplier with us."}
    bills = erp.read("account.move", [("move_type", "=", "in_invoice"), ("partner_id", "=", vid)],
                     ["id", "ref", "state", "payment_state", "amount_total", "invoice_date", "invoice_date_due",
                      "activity_ids", "line_ids"], order="invoice_date desc", limit=20)
    return {"verified": True, "invoices": [_supplier_status(erp, b) for b in bills]}

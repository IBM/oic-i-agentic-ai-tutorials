"""Book the routed invoice in Odoo: post it touchless, or hold it as a draft bill with a review task.
Every bill carries the agent's control log in its chatter."""

import html

from . import chatter
from .controls import bill_lines
from .india import inr
from .odoo import Odoo

def post(invoice: dict, result: dict, odoo: Odoo) -> dict:
    bill_id = _create(invoice, result, odoo, "touchless")
    bill = odoo.post_bill(bill_id)
    return {"summary": f"Posted {bill['name']} touchless", "bill": bill}


def hold(invoice: dict, result: dict, odoo: Odoo, reason: str = "") -> dict:
    """Draft bill + review task. `reason` comes from the decision table when a policy rule (not a failed
    control) sends a clean invoice to review, e.g. the touchless value limit."""
    if reason and not result["exceptions"]:
        result["checks"].append({"code": "DOA-01", "category": "Approval", "status": "fail", "label": reason,
                                 "title": "Within touchless posting limit", "detail": reason,
                                 "action": "Approve as invoiced if the purchase was authorised."})
        result["exceptions"] = 1
    if not result["vendor"]:
        return {"summary": "On hold — supplier not in vendor master, no bill created", "bill": None, "controls": result}
    bill_id = _create(invoice, result, odoo, "exception")
    fails = [c for c in result["checks"] if c["status"] == "fail"]
    odoo.schedule_review(bill_id, f"AP exception: {', '.join(c['label'] for c in fails)}",
                         "<br/>".join(f"<b>{c['code']}</b> {html.escape(c['detail'])}" for c in fails))
    return {"summary": f"Draft bill #{bill_id} on hold · review task assigned", "bill": odoo.bill(bill_id),
            "controls": result}


def _create(invoice: dict, result: dict, odoo: Odoo, route: str) -> int:
    bill_id = odoo.create_bill(
        partner_id=result["vendor"]["id"], ref=invoice["invoice_number"], invoice_date=invoice.get("invoice_date"),
        lines=bill_lines(result, odoo), po_name=(result.get("po") or {}).get("name", ""),
        bank_id=result.get("bank_id"))
    odoo.note("account.move", bill_id, chatter_html(result, route))
    return bill_id


def chatter_html(result: dict, route: str) -> str:
    tds = result.get("tds") or {}
    tds_line = (f"<p>TDS: Sec {tds['section']} ({tds['legacy']}) @ {tds['rate']:g}% = ₹{inr(tds['amount'])} · "
                f"Net payable ₹{inr(result['net_payable'])}</p>") if tds.get("applicable") else ""
    return chatter.note(f"route: <b>{route.upper()}</b>", result["checks"], tds_line)

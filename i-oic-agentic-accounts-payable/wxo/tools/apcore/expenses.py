"""Employee expense receipts (company card or reimbursable): policy controls and booking as Odoo expenses.

Controls follow the same shape as the AP controls, and the flow's decision table routes on the counts:
blocked (duplicate), exception (manager approval) or touchless (auto-approved).
"""

import html
from datetime import date

from . import chatter
from .india import inr
from .odoo import Odoo

TAG_CARD_PREFIX = "Corporate card ··"
MAX_AGE_DAYS = 60

# category -> Odoo expense product (default_code), display name, policy limit and the unit it applies to.
EXPENSE_POLICY = {
    "local_travel": {"code": "EXP-LOCAL", "name": "Local conveyance", "limit": 1500, "per": "receipt"},
    "hotel": {"code": "EXP-HOTEL", "name": "Hotel stay", "limit": 6000, "per": "night"},
    "meals": {"code": "FOOD", "name": "Meals & entertainment", "limit": 2000, "per": "person"},
    "airfare": {"code": "EXP-AIR", "name": "Air travel", "limit": 15000, "per": "receipt"},
    "other": {"code": "EXP_GEN", "name": "Other business expense", "limit": 3000, "per": "receipt"},
}
# GST on food and beverages, outdoor catering and personal travel is blocked credit under s.17(5) CGST Act.
ITC_BLOCKED = {"meals"}

FAIL_LABELS = {"EXP-01": "Receipt particulars missing", "EXP-02": "Employee not identified",
               "EXP-03": "Above policy limit", "EXP-04": "Submitted late", "DUP-02": "Duplicate receipt",
               "EXP-06": "Card not the submitter's"}


def _check(code, status, title, detail, action="", category="Expense policy"):
    c = {"code": code, "category": category, "status": status, "title": title, "detail": detail}
    if action:
        c["action"] = action
    return c


def find_employee(odoo: Odoo, card_last4: str = "", email: str = "") -> tuple[dict | None, str]:
    """Resolve the employee from the corporate card printed on the receipt, else from the submitter."""
    fields = ["id", "name", "work_email", "job_title", "parent_id", "category_ids"]
    if card_last4:
        tag = odoo.search_read("hr.employee.category", [("name", "=", f"{TAG_CARD_PREFIX}{card_last4}")], ["id"])
        if tag:
            rows = odoo.search_read("hr.employee", [("category_ids", "in", [tag[0]["id"]])], fields, limit=1)
            if rows:
                return rows[0], "card"
    if email:
        rows = odoo.search_read("hr.employee", [("work_email", "=ilike", email.strip())], fields, limit=1)
        if rows:
            return rows[0], "submitter"
    return None, ""


def evaluate(receipt: dict, category: dict, submitted_by: str, odoo: Odoo) -> dict:
    checks = []
    company = odoo.company()
    total = float(receipt.get("total_amount") or 0)
    cat = category.get("category") if category.get("category") in EXPENSE_POLICY else "other"
    policy = EXPENSE_POLICY[cat]

    missing = [k for k in ("merchant_name", "receipt_date", "total_amount") if not receipt.get(k)]
    checks.append(_check("EXP-01", "fail" if missing else "pass", "Receipt shows merchant, date and amount",
                         ("Missing: " + ", ".join(missing)) if missing else
                         f"{receipt['merchant_name']} · {receipt['receipt_date']} · ₹{inr(total)}",
                         "Ask the employee for a legible itemised receipt." if missing else "", "Document"))

    card = (receipt.get("card_last4") or "").strip()
    employee, how = find_employee(odoo, card, submitted_by)
    submitter, _ = find_employee(odoo, "", submitted_by) if submitted_by else (None, "")
    if not employee:
        checks.append(_check("EXP-02", "fail", "Employee identified",
                             f"No employee for card ··{card or '—'} or submitter {submitted_by or '—'}",
                             "Confirm who incurred the expense before booking it."))
    else:
        checks.append(_check("EXP-02", "pass", "Employee identified",
                             f"{employee['name']} ({employee['job_title'] or 'employee'}), matched on "
                             + (f"corporate card ··{card}" if how == "card" else f"submitter {submitted_by}")))
    if how == "card" and submitter and submitter["id"] != employee["id"]:
        checks.append(_check("EXP-06", "fail", "Card belongs to the submitter",
                             f"Card ··{card} is issued to {employee['name']}, but {submitter['name']} submitted it",
                             "Check whether the receipt was forwarded or shared before reimbursing anyone."))
    payment_mode = "company_account" if how == "card" else "own_account"

    units = 1.0
    if policy["per"] == "night":
        units = max(1.0, float(receipt.get("nights") or 1))
    elif policy["per"] == "person":
        units = max(1.0, float(receipt.get("persons") or 1))
    allowed = policy["limit"] * units
    per_unit = round(total / units, 2)
    unit = {"night": "per night", "person": "per person", "receipt": "per receipt"}[policy["per"]]
    over = total > allowed + 0.5
    checks.append(_check("EXP-03", "fail" if over else "pass", f"Within {policy['name'].lower()} policy",
                         f"₹{inr(per_unit)} {unit} vs limit ₹{inr(policy['limit'])} {unit}"
                         + (f" (₹{inr(total - allowed)} over)" if over else ""),
                         "Manager to approve the excess or reimburse up to the policy limit." if over else ""))

    try:
        age = (date.today() - date.fromisoformat(receipt.get("receipt_date") or "")).days
    except ValueError:
        age = 0
    checks.append(_check("EXP-04", "fail" if age > MAX_AGE_DAYS else "pass", f"Submitted within {MAX_AGE_DAYS} days",
                         f"Receipt is {age} day(s) old"))

    dup = odoo.search_read("hr.expense", [("name", "ilike", f"({receipt.get('receipt_number')})"),
                                          ("state", "!=", "refused")],
                           ["id", "name", "employee_id", "total_amount", "date"], limit=1) \
        if receipt.get("receipt_number") else []
    if not dup and receipt.get("merchant_name") and total:
        dup = odoo.search_read("hr.expense", [("total_amount", "=", total), ("date", "=", receipt.get("receipt_date")),
                                              ("state", "!=", "refused")],
                               ["id", "name", "employee_id", "total_amount", "date"], limit=1)
    checks.append(_check("DUP-02", "fail" if dup else "pass", "Not a duplicate receipt",
                         (f"Already claimed as expense #{dup[0]['id']} by {dup[0]['employee_id'][1]} "
                          f"(₹{inr(dup[0]['total_amount'])}, {dup[0]['date']})") if dup else "No earlier claim for this receipt",
                         "Blocked to prevent double reimbursement." if dup else "", "Risk"))

    gst = round(sum(float(receipt.get(k) or 0) for k in ("cgst_amount", "sgst_amount", "igst_amount")), 2)
    merchant_state = (receipt.get("merchant_gstin") or "")[:2]
    if not gst:
        itc = (False, "No GST charged")
    elif cat in ITC_BLOCKED:
        itc = (False, f"GST ₹{inr(gst)} on food and beverages is blocked credit (s.17(5)); booked as cost")
    elif (receipt.get("buyer_gstin") or "") != company["gstin"]:
        itc = (False, f"GST ₹{inr(gst)} not claimable: receipt is not billed to our GSTIN {company['gstin']}")
    elif merchant_state != company["gstin"][:2]:
        itc = (False, f"GST ₹{inr(gst)} not claimable: charged in state {merchant_state}, where we are not registered")
    else:
        itc = (True, f"GST ₹{inr(gst)} eligible for input tax credit")
    checks.append(_check("GST-06", "pass" if itc[0] else "info", "GST input credit", itc[1], category="GST"))

    fails = [c for c in checks if c["status"] == "fail"]
    for c in fails:
        c["label"] = FAIL_LABELS.get(c["code"], c["title"])
    return {
        "duplicates": sum(c["code"] == "DUP-02" for c in fails),
        "exceptions": len(fails),
        "checks": checks,
        "category": cat, "category_name": policy["name"], "purpose": category.get("purpose", ""),
        "employee": employee and {"id": employee["id"], "name": employee["name"], "job_title": employee["job_title"],
                                  "manager": employee["parent_id"] and employee["parent_id"][1]},
        "payment_mode": payment_mode,
        "itc_eligible": itc[0], "gst": gst, "total": total,
        "evaluated_on": date.today().isoformat(), "company": company["name"],
    }


def book(receipt: dict, result: dict, odoo: Odoo, approve: bool) -> dict:
    """Create the Odoo expense: submitted and approved when every control passed, otherwise a draft with an
    approval task."""
    if not result["employee"]:
        return {"summary": "On hold — employee not identified, no expense created", "expense": None}
    product = odoo.search_read("product.product", [("default_code", "=", EXPENSE_POLICY[result["category"]]["code"])],
                               ["id"], limit=1)
    vals = {
        "name": f"{result['category_name']} · {receipt.get('merchant_name', '')}"[:90]
                + (f" ({receipt['receipt_number']})" if receipt.get("receipt_number") else ""),
        "employee_id": result["employee"]["id"],
        "product_id": product[0]["id"] if product else False,
        "total_amount_currency": result["total"],
        "date": receipt.get("receipt_date") or date.today().isoformat(),
        "payment_mode": result["payment_mode"],
        "description": result.get("purpose") or "",
    }
    if not result["itc_eligible"]:
        vals["tax_ids"] = [(5, 0, 0)]  # GST is part of the cost, not a recoverable input tax
    exp_id = odoo.call("hr.expense", "create", vals)
    odoo.note("hr.expense", exp_id, _chatter_html(result, "auto-approved" if approve else "manager approval"))
    if approve:  # submitting by the AP service user approves it (company-card spend is settled at once)
        odoo.call("hr.expense", "action_submit", [exp_id])
    else:  # left in draft with a task for the employee's manager

        fails = [c for c in result["checks"] if c["status"] == "fail"]
        odoo.schedule_activity("hr.expense", exp_id, f"Expense exception: {', '.join(c['label'] for c in fails)}",
                               "<br/>".join(f"<b>{c['code']}</b> {html.escape(c['detail'])}" for c in fails))
    exp = expense(odoo, exp_id)
    mode = "company card" if result["payment_mode"] == "company_account" else "reimbursable"
    return {"summary": f"Expense #{exp_id} {'approved' if approve else 'awaiting manager approval'} · {mode}",
            "expense": exp}


def expense(odoo: Odoo, exp_id: int) -> dict:
    e = odoo.search_read("hr.expense", [("id", "=", exp_id)],
                         ["id", "name", "state", "total_amount", "payment_mode", "employee_id", "date"])[0]
    e["url"] = f"{odoo.url}/odoo/action-hr_expense.hr_expense_actions_all/{exp_id}"
    return e


def _chatter_html(result: dict, route: str) -> str:
    return chatter.note(f"expense route: <b>{route.upper()}</b>", result["checks"])

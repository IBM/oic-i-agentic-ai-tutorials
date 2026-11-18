"""Workbench side of the process:

    intake → wxO object storage → ap_document_processing_flow (extract · GST checks · TDS classification ·
    ERP controls · routing decision table · Odoo bill posted | held | blocked) → notify the supplier

Reviewer actions on held bills (approve / reject / email) and the ERP sync run here.
"""

import html
import shutil
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image

from apcore import controls, expenses, receiving
from apcore.india import inr
from apcore.odoo import Odoo
from app import config, mail, store
from app.wxo import WxO

wxo = WxO()
odoo = Odoo(config.ODOO_URL, config.ODOO_DB, config.ODOO_USERNAME, config.ODOO_PASSWORD)
_pool = ThreadPoolExecutor(max_workers=3)



# ---- intake ------------------------------------------------------------------------------
class UnreadableDocument(ValueError):
    pass


def submit(data: bytes, filename: str, source: str = "upload", meta: dict | None = None) -> dict:
    safe = Path(filename).name.replace(" ", "_")
    path = config.UPLOAD_DIR / f"{uuid.uuid4().hex[:8]}_{safe}"
    path.write_bytes(data)
    try:
        preview = _preview(path)
    except Exception as exc:  # corrupt PDF, password-protected file, or an image format Pillow cannot read
        path.unlink(missing_ok=True)
        raise UnreadableDocument(f"{filename} could not be opened ({exc.__class__.__name__}). Check the file isn't "
                                 "damaged or password-protected.") from exc
    doc = store.create(source=source, file_name=safe, file_path=str(path), preview_path=preview,
                       status="processing", stage="received", meta=meta or {})
    store.log(doc["id"], "intake", "done", f"Received {safe} via {source} ({len(data) / 1024:.0f} KB)")
    _pool.submit(_run, doc["id"])
    return store.get(doc["id"])


def _preview(path: Path) -> str:
    out = path.with_suffix(".preview.png")
    if path.suffix.lower() == ".pdf":
        pdfium.PdfDocument(str(path))[0].render(scale=2).to_pil().save(out)
    else:
        Image.open(path).convert("RGB").save(out)
    return str(out)


# ---- processing --------------------------------------------------------------------------
def _run(doc_id: int) -> None:
    doc = store.get(doc_id)
    try:
        t0 = time.perf_counter()
        store.update(doc_id, stage="extracting")
        ref = wxo.upload(Path(doc["file_path"]).read_bytes(), doc["file_name"])
        store.log(doc_id, "upload", "done", "Stored in watsonx Orchestrate object storage", _ms(t0))

        t1 = time.perf_counter()
        store.log(doc_id, "flow", "running", f"{config.WXO_FLOW_NAME} started")
        run = wxo.run_flow(config.WXO_FLOW_NAME, {"document_ref": ref, "submitted_by": doc["meta"].get("sender", "")},
                           on_progress=lambda node: store.log(doc_id, "flow", "running", f"{node} complete"))
        out = run["output"]
        doc_type = out.get("doc_type") or "other"
        status, result, erp, header = OUTCOME.get(doc_type, _other)(out)
        extraction = {k: v for k, v in out.items() if k in EXTRACTION_KEYS}
        fails = [c for c in result.get("checks", []) if c["status"] == "fail"]
        store.log(doc_id, "flow", "done", f"Flow instance {run['instance_id'][:8]} · {DOC_LABELS.get(doc_type, doc_type)}"
                  + (f" · route: {result['decision']}" if result.get("decision") else ""), _ms(t1),
                  instance_id=run["instance_id"], nodes=[{**n, "label": n["name"]} for n in run["nodes"]])
        if result.get("checks"):
            store.log(doc_id, "controls", "done", f"{len(result['checks'])} controls · {len(fails)} exception(s)"
                      + (f" · {result['route_reason']}" if result.get("route_reason") else ""))
        store.log(doc_id, "erp", "done", erp.get("summary", ""))
        store.update(doc_id, status=status, stage="done", extraction=extraction, controls=result, erp=erp, **header,
                     meta={**doc["meta"], "doc_type": doc_type, "cycle_seconds": round(time.perf_counter() - t0, 1)})
        _acknowledge(store.get(doc_id))
    except Exception as exc:  # surfaced in the UI with the failing step
        store.log(doc_id, "error", "failed", str(exc)[:400])
        store.update(doc_id, status="failed", error=str(exc)[:400])


DOC_LABELS = {"supplier_invoice": "Supplier invoice", "expense_receipt": "Expense receipt",
              "purchase_order": "Purchase order", "delivery_challan": "Delivery challan", "other": "Unsupported document"}
EXTRACTION_KEYS = ("doc_type", "detected_schema", "document", "invoice", "payment_nature", "expense_category", "kvps",
                   "metadata", "extracted_text")
ROUTE_STATUS = {"touchless": "posted", "exception": "exception", "blocked": "blocked"}


# Each document type's flow branch fills its own outputs; these turn them into (status, controls, erp, header).
def _invoice(out: dict):
    inv = out.get("invoice") or {}
    booked = out.get("posted") or out.get("held") or {}
    result = booked.pop("controls", None) or out.get("controls") or {}
    result.update(decision=out.get("route") or "exception", route_reason=out.get("route_reason") or "")
    erp = booked
    if result["decision"] == "blocked":
        dup = next((c for c in result.get("checks", []) if c["code"] == "DUP-01"), {})
        erp = {"summary": "Blocked — no bill created", "bill": None, "reason": dup.get("detail", "")}
    return (ROUTE_STATUS[result["decision"]], result, erp,
            {"vendor": inv.get("supplier_name"), "invoice_number": inv.get("invoice_number"),
             "invoice_date": inv.get("invoice_date"), "total": inv.get("total_amount")})


def _expense(out: dict):
    rec = out.get("document") or {}
    result = out.get("expense_controls") or {}
    route = out.get("route") if out.get("route") in ROUTE_STATUS else "exception"
    result.update(decision=route, route_reason=out.get("route_reason") or "", category_ai=out.get("expense_category"))
    booked = out.get("expense_approved") or out.get("expense_held") or {}
    erp = {"summary": booked.get("summary") or "", "expense": booked.get("expense")}
    if route == "blocked":
        dup = next((c for c in result.get("checks", []) if c["code"] == "DUP-02"), {})
        erp = {"summary": "Blocked — no expense created", "expense": None, "reason": dup.get("detail", "")}
    return (ROUTE_STATUS[route], result, erp,
            {"vendor": rec.get("merchant_name"), "invoice_number": rec.get("receipt_number"),
             "invoice_date": rec.get("receipt_date"), "total": rec.get("total_amount")})


def _receiving(key: str, ok_status: str):
    def outcome(out: dict):
        rec = out.get("document") or {}
        result = out.get(key) or {}
        erp = {"summary": result.get("summary", ""), "receipt": result.get("receipt"),
               "released_bills": result.get("released_bills") or []}
        return ("exception" if result.get("exceptions") else ok_status, result, erp,
                {"vendor": (result.get("po") or {}).get("vendor") or rec.get("supplier_name"),
                 "invoice_number": rec.get("challan_number") or rec.get("po_number"),
                 "invoice_date": rec.get("challan_date") or rec.get("po_date"), "total": None})
    return outcome


def _other(out: dict):
    return ("unsupported", {}, {"summary": "Not an AP document the agent handles — left for a person"},
            {"vendor": None, "invoice_number": None, "invoice_date": None, "total": None})


OUTCOME = {"supplier_invoice": _invoice, "expense_receipt": _expense,
           "purchase_order": _receiving("po_check", "verified"),
           "delivery_challan": _receiving("receipt", "received"), "other": _other}


def _ms(t: float) -> float:
    return round((time.perf_counter() - t) * 1000)


def _acknowledge(doc: dict) -> None:
    sender = doc["meta"].get("sender")
    if not (doc["source"] == "email" and sender and mail.configured()):  # samples carry a fictional submitter
        return
    status = {"posted": "has been accepted and scheduled for payment",
              "exception": "is under review by our Accounts Payable team",
              "blocked": "appears to be a duplicate of a document we have already processed",
              "received": "has been booked as a goods receipt", "verified": "has been matched to our purchase order"
              }.get(doc["status"], "was received")
    try:
        mail.send(sender, f"Re: {doc['meta'].get('subject') or 'Invoice'} — {doc['invoice_number'] or doc['file_name']}",
                  mail.render([f"Thank you. Invoice <b>{html.escape(doc['invoice_number'] or doc['file_name'])}</b> {status}."],
                              [("Invoice total", f"₹{inr(doc['total'] or 0)}"), ("Reference", f"AP-{doc['id']:05d}")]),
                  doc["meta"].get("message_id", ""))
        store.log(doc["id"], "notify", "done", f"Acknowledgement emailed to {sender}")
    except Exception as exc:
        store.log(doc["id"], "notify", "failed", f"Acknowledgement not sent: {exc}")


# ---- reviewer actions ---------------------------------------------------------------------
def approve(doc_id: int, resolution: str = "as_invoiced", note: str = "") -> dict:
    doc = store.get(doc_id)
    if (doc["erp"] or {}).get("expense"):
        return _approve_expense(doc, note)
    bill = (doc["erp"] or {}).get("bill")
    if doc["status"] != "exception" or not bill:
        raise ValueError("Only invoices on hold with a draft bill can be approved")
    if resolution == "received_qty":
        lines = controls.bill_lines(doc["controls"], odoo, received_qty_only=True)
        odoo.call("account.move", "write", [bill["id"]], {"invoice_line_ids": [(5, 0, 0)] + [(0, 0, l) for l in lines]})
    posted = odoo.post_bill(bill["id"])
    label = "for received quantity only" if resolution == "received_qty" else "as invoiced"
    odoo.close_reviews(bill["id"], f"Approved {label}. {note}".strip())
    odoo.note("account.move", bill["id"], f"<p>Approved by AP reviewer {label}. {html.escape(note)}</p>")
    store.log(doc_id, "review", "done", f"Approved {label}; posted {posted['name']}" + (f" — {note}" if note else ""))
    return store.update(doc_id, status="approved", erp={**doc["erp"], "bill": posted, "resolution": resolution})


def _approve_expense(doc: dict, note: str) -> dict:
    exp = doc["erp"]["expense"]
    if doc["status"] != "exception":
        raise ValueError("Only expenses awaiting approval can be approved")
    odoo.call("hr.expense", "action_submit", [exp["id"]])
    odoo.close_activities("hr.expense", exp["id"], f"Approved by manager. {note}".strip())
    odoo.note("hr.expense", exp["id"], f"<p>Approved by manager from the AP workbench. {html.escape(note)}</p>")
    store.log(doc["id"], "review", "done", "Expense approved" + (f" — {note}" if note else ""))
    return store.update(doc["id"], status="approved", erp={**doc["erp"], "expense": expenses.expense(odoo, exp["id"]),
                                                           "summary": f"Expense #{exp['id']} approved by manager"})


def reject(doc_id: int, reason: str, email_vendor: bool = False, body: str = "") -> dict:
    doc = store.get(doc_id)
    exp = (doc["erp"] or {}).get("expense")
    if exp:
        odoo.close_activities("hr.expense", exp["id"], f"Refused: {reason}")
        wiz = odoo.call("hr.expense.refuse.wizard", "create", {"expense_ids": [(6, 0, [exp["id"]])], "reason": reason})
        odoo.call("hr.expense.refuse.wizard", "action_refuse", [wiz])
        store.log(doc_id, "review", "done", f"Expense refused — {reason}")
        return store.update(doc_id, status="rejected", erp={**doc["erp"], "expense": expenses.expense(odoo, exp["id"]),
                                                            "summary": f"Expense #{exp['id']} refused"})
    bill = (doc["erp"] or {}).get("bill")
    if bill:
        odoo.close_reviews(bill["id"], f"Rejected: {reason}")
        odoo.note("account.move", bill["id"], f"<p>Rejected by AP reviewer: {html.escape(reason)}</p>")
        odoo.cancel_bill(bill["id"])
        bill = odoo.bill(bill["id"])
    store.log(doc_id, "review", "done", f"Rejected — {reason}")
    if email_vendor:
        email_supplier(doc_id, body=body)
    return store.update(doc_id, status="rejected", erp={**(doc["erp"] or {}), "bill": bill})


def vendor_email_draft(doc_id: int) -> dict:
    doc = store.get(doc_id)
    vendor = (doc["controls"] or {}).get("vendor") or {}
    inv = (doc["extraction"] or {}).get("invoice") or {}
    issues = [c for c in (doc["controls"] or {}).get("checks", []) if c["status"] == "fail"]
    supplier_text = {
        "GST-03": "GST has been charged under the wrong regime for the place of supply. Please issue a corrected invoice.",
        "GST-05": "The invoice is addressed to an incorrect GSTIN. Please re-issue it to our registered GSTIN.",
        "EINV-02": "The invoice does not carry an IRN although e-invoicing applies to you. Please register it on the IRP.",
        "PO-03": "Unit prices differ from the purchase order. Please issue a credit note or share the approved revision.",
        "GRN-01": "Billed quantity exceeds the quantity received at our plant. We can pay for the received quantity; "
                  "please issue a credit note for the balance.",
        "BANK-01": "The bank details on the invoice differ from our records. For your security we will call your "
                   "registered contact to verify before making any change; payment is on hold until then.",
        "DUP-01": "This invoice number has already been booked; no further action is needed.",
        "PO-01": "We could not find the purchase order quoted on the invoice. Please confirm the PO number.",
    }
    points = [supplier_text.get(c["code"], c["title"]) for c in issues]
    body = (f"Dear {vendor.get('name', 'Supplier')},\n\nThank you for invoice {inv.get('invoice_number', '')} dated "
            f"{inv.get('invoice_date', '')} for ₹{inr(inv.get('total_amount') or 0)}. Our review found:\n\n"
            + "\n".join(f"• {p}" for p in points) + "\n\nRegards,\nAccounts Payable\n" + (doc["controls"] or {}).get("company", ""))
    return {"to": vendor.get("email", ""), "subject": f"Invoice {inv.get('invoice_number', '')} — action required",
            "body": body}


def email_supplier(doc_id: int, to: str = "", subject: str = "", body: str = "") -> dict:
    draft = vendor_email_draft(doc_id)
    to, subject, body = to or draft["to"], subject or draft["subject"], body or draft["body"]
    sent_to = mail.send(to, subject, mail.render([html.escape(p).replace("\n", "<br/>") for p in body.split("\n\n")]))
    store.log(doc_id, "notify", "done", f"Supplier emailed at {sent_to}: {subject}")
    return store.get(doc_id)


_last_sync = [0.0]


def sync_from_erp(min_interval_s: float = 8.0) -> None:
    """Reflect decisions taken outside this app (AP Copilot agent, or directly in Odoo) on held invoices."""
    if time.time() - _last_sync[0] < min_interval_s:
        return
    _last_sync[0] = time.time()
    held = [d for d in store.all_docs() if d["status"] == "exception" and (d["erp"] or {}).get("bill")]
    if not held:
        return
    states = {b["id"]: b for b in odoo.search_read("account.move", [("id", "in", [d["erp"]["bill"]["id"] for d in held])],
                                                   ["id", "state", "name"])}
    for d in held:
        b = states.get(d["erp"]["bill"]["id"])
        if b and b["state"] in ("posted", "cancel"):
            bill = odoo.bill(b["id"])
            store.log(d["id"], "review", "done", f"{'Posted' if b['state'] == 'posted' else 'Cancelled'} {b['name'] or ''} outside the "
                                                 "workbench (AP Copilot or Odoo)")
            store.update(d["id"], status="approved" if b["state"] == "posted" else "rejected", erp={**d["erp"], "bill": bill})


# ---- inbox & housekeeping -----------------------------------------------------------------
def poll_inbox() -> list[dict]:
    return [submit(m["data"], m["filename"], "email",
                   {"sender": m["sender"], "subject": m["subject"], "message_id": m["message_id"]})
            for m in mail.fetch_invoices()]


def reset() -> int:
    """Remove every bill and expense this app created in Odoo, reverse goods it received, and clear local
    documents (repeatable demos)."""
    removed = 0
    for doc in store.all_docs():
        erp = doc["erp"] or {}
        if erp.get("expense"):
            try:
                odoo.call("hr.expense", "action_reset", [erp["expense"]["id"]])
            except Exception:
                pass  # already a draft
            odoo.call("hr.expense", "unlink", [erp["expense"]["id"]])
            removed += 1
        if erp.get("receipt") and doc["status"] == "received":
            receiving.undo_receipt(odoo, erp["receipt"]["id"],
                                   ((doc["extraction"] or {}).get("document") or {}).get("challan_number", ""))
            removed += 1
        bill = erp.get("bill")
        if bill:
            try:
                if odoo.bill(bill["id"])["state"] != "draft":
                    odoo.call("account.move", "button_draft", [bill["id"]])
                odoo.call("account.move", "unlink", [bill["id"]])
            except Exception:
                odoo.cancel_bill(bill["id"])
            removed += 1
    store.clear()
    shutil.rmtree(config.UPLOAD_DIR, ignore_errors=True)
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return removed

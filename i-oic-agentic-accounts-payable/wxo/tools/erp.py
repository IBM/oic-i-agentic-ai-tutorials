"""Shared Odoo access for the watsonx Orchestrate agent tools.

Credentials come from the `odoo_erp` key-value connection (url, db, username, password),
so no secrets live in the tool code.
"""

import re
import xmlrpc.client

from ibm_watsonx_orchestrate.agent_builder.connections import ConnectionType, ExpectedCredentials
from ibm_watsonx_orchestrate.run import connections

APP_ID = "odoo_erp"
ODOO_CREDENTIALS = [ExpectedCredentials(app_id=APP_ID, type=ConnectionType.KEY_VALUE)]


class Erp:
    def __init__(self):
        c = connections.key_value(APP_ID)
        self.url, self.db, self.user, self.pwd = c["url"].rstrip("/"), c["db"], c["username"], c["password"]
        common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common", allow_none=True)
        self.uid = common.authenticate(self.db, self.user, self.pwd, {})
        if not self.uid:
            raise RuntimeError("Odoo authentication failed — check the odoo_erp connection")
        self.models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object", allow_none=True)

    def call(self, model, method, *args, **kw):
        try:
            return self.models.execute_kw(self.db, self.uid, self.pwd, model, method, list(args), kw)
        except xmlrpc.client.Fault as fault:
            if "cannot marshal None" in fault.faultString:
                return None
            raise RuntimeError(fault.faultString.strip().splitlines()[-1]) from fault

    def read(self, model, domain, fields, **kw):
        return self.call(model, "search_read", domain, fields=fields, **kw)

    def bill_url(self, bill_id):
        return f"{self.url}/odoo/vendor-bills/{bill_id}"

    def find_bill(self, reference: str) -> dict | None:
        """Find a vendor bill by supplier invoice number, Odoo bill number or record id."""
        ref = (reference or "").strip()
        fields = ["id", "name", "ref", "partner_id", "state", "payment_state", "amount_untaxed", "amount_tax",
                  "amount_total", "amount_residual", "invoice_date", "invoice_date_due", "invoice_origin",
                  "activity_ids", "line_ids"]
        domain_base = [("move_type", "=", "in_invoice")]
        for domain in ([("ref", "=ilike", ref)], [("name", "=ilike", ref)], [("ref", "ilike", ref)]):
            rows = self.read("account.move", domain_base + domain, fields, order="id desc", limit=1)
            if rows:
                return rows[0]
        if ref.lstrip("#").isdigit():
            rows = self.read("account.move", domain_base + [("id", "=", int(ref.lstrip("#")))], fields)
            return rows[0] if rows else None
        return None

    def tds_withheld(self, bill: dict) -> float:
        """TDS on the bill's lines. Odoo applies India TDS as a withholding tax at payment time, so it is
        computed from the line bases rather than read from a tax line."""
        lines = self.read("account.move.line", [("id", "in", bill["line_ids"]), ("display_type", "=", "product")],
                          ["balance", "tax_ids"])
        tax_ids = sorted({t for l in lines for t in l["tax_ids"]})
        rates = {t["id"]: abs(t["amount"]) for t in self.read("account.tax", [("id", "in", tax_ids),
                                                                              ("is_withholding_tax", "=", True)],
                                                              ["amount"])}
        return round(sum(l["balance"] * rates[t] / 100 for l in lines for t in l["tax_ids"] if t in rates))

    def open_reviews(self, bill: dict) -> list[str]:
        if not bill.get("activity_ids"):
            return []
        return [a["summary"] for a in self.read("mail.activity", [("id", "in", bill["activity_ids"])], ["summary"])]

    def agent_note(self, bill_id: int) -> str:
        msgs = self.read("mail.message", [("model", "=", "account.move"), ("res_id", "=", bill_id),
                                          ("body", "ilike", "AP agent")], ["body"], order="id desc", limit=1)
        return strip_html(msgs[0]["body"]) if msgs else ""


def strip_html(html: str) -> str:
    text = re.sub(r"</(p|tr)>", "\n", html or "")
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"[ \t]+", " ", text).strip()


def mask(account: str) -> str:
    return f"···{account[-4:]}" if account else ""


STATE_LABELS = {"draft": "On hold for AP review", "posted": "Approved and booked", "cancel": "Rejected / cancelled"}
PAYMENT_LABELS = {"not_paid": "Not yet paid", "in_payment": "Payment in progress", "paid": "Paid",
                  "partial": "Partially paid", "reversed": "Reversed"}

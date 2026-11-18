"""Thin Odoo XML-RPC client for the AP agent: vendor master, POs/GRNs and vendor bills."""

import xmlrpc.client
from datetime import date
from functools import lru_cache

from .india import TAG_EINVOICE, TAG_TDS_PREFIX, TDS_RULES


class OdooError(RuntimeError):
    pass


class Odoo:
    def __init__(self, url: str, db: str, username: str, password: str):
        self.url = url.rstrip("/")
        self.db, self.username, self.password = db, username, password
        self._uid = None

    # ---- transport -------------------------------------------------------------------
    @property
    def uid(self) -> int:
        if not self._uid:
            common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common", allow_none=True)
            self._uid = common.authenticate(self.db, self.username, self.password, {})
            if not self._uid:
                raise OdooError(f"Odoo authentication failed for {self.username} on {self.db}")
        return self._uid

    def call(self, model, method, *args, **kwargs):
        proxy = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object", allow_none=True)
        try:
            return proxy.execute_kw(self.db, self.uid, self.password, model, method, list(args), kwargs)
        except xmlrpc.client.Fault as fault:
            # Button methods return None, which Odoo cannot marshal; the action itself succeeded.
            if "cannot marshal None" in fault.faultString:
                return None
            raise OdooError(fault.faultString.strip().splitlines()[-1]) from fault

    def search_read(self, model, domain, fields, **kw):
        return self.call(model, "search_read", domain, fields=fields, **kw)

    def ping(self) -> dict:
        info = self.company()
        return {"connected": True, "url": self.url, "db": self.db, "company": info["name"]}

    # ---- master data -----------------------------------------------------------------
    def company(self) -> dict:
        c = self.search_read("res.company", [], ["name", "vat", "state_id", "currency_id"], limit=1)[0]
        state_code = ""
        if c.get("state_id"):
            state_code = self.search_read("res.country.state", [("id", "=", c["state_id"][0])], ["l10n_in_tin"])[0]["l10n_in_tin"]
        return {"id": c["id"], "name": c["name"], "gstin": c.get("vat") or "", "state_code": state_code,
                "currency": c["currency_id"][1]}

    def find_vendor(self, gstin: str = "", name: str = "") -> dict | None:
        fields = ["id", "name", "vat", "email", "category_id", "bank_ids", "state_id", "street", "city"]
        rows = []
        if gstin:
            rows = self.search_read("res.partner", [("vat", "=", gstin.strip().upper())], fields, limit=1)
        if not rows and name:
            rows = self.search_read("res.partner", [("name", "ilike", name.strip()), ("supplier_rank", ">", 0)], fields, limit=1)
        if not rows:
            return None
        v = rows[0]
        tags = [t["name"] for t in self.search_read("res.partner.category", [("id", "in", v["category_id"])], ["name"])]
        v["tags"] = tags
        v["einvoice_applicable"] = TAG_EINVOICE in tags
        v["tds_nature"] = next((k for k, r in TDS_RULES.items() if f"{TAG_TDS_PREFIX}{r['label']}" in tags), None)
        v["banks"] = self.search_read("res.partner.bank", [("partner_id", "=", v["id"])],
                                      ["id", "account_number", "bank_name", "bank_bic"])
        v["url"] = f"{self.url}/odoo/contacts/{v['id']}"
        return v

    @lru_cache(maxsize=64)
    def tax_id(self, name: str) -> int | None:
        ids = self.call("account.tax", "search", [("name", "=", name), ("type_tax_use", "=", "purchase")], limit=1)
        return ids[0] if ids else None

    # ---- purchasing ------------------------------------------------------------------
    def purchase_order(self, name: str) -> dict | None:
        rows = self.search_read("purchase.order", [("name", "=", (name or "").strip())],
                                ["id", "name", "partner_id", "state", "date_order", "amount_untaxed",
                                 "amount_total", "order_line", "picking_ids", "invoice_status"], limit=1)
        if not rows:
            return None
        po = rows[0]
        po["lines"] = self.search_read(
            "purchase.order.line", [("order_id", "=", po["id"])],
            ["id", "product_id", "name", "product_qty", "qty_received", "qty_invoiced", "price_unit",
             "uom_id", "tax_ids", "price_subtotal"])
        for line in po["lines"]:  # Odoo 20 leaves `name` empty unless the description was edited
            line["name"] = (line["name"] or line["product_id"][1].split("] ", 1)[-1]).strip()
        po["receipts"] = self.search_read("stock.picking", [("id", "in", po["picking_ids"]),
                                                            ("picking_type_code", "=", "incoming")],
                                          ["name", "state", "date_done", "scheduled_date"]) if po["picking_ids"] else []
        po["url"] = f"{self.url}/odoo/purchase/{po['id']}"
        return po

    # ---- payables --------------------------------------------------------------------
    def bills_for(self, partner_id: int, ref: str = "") -> list[dict]:
        domain = [("move_type", "=", "in_invoice"), ("partner_id", "=", partner_id), ("state", "!=", "cancel")]
        if ref:
            domain.append(("ref", "=ilike", ref.strip()))
        return self.search_read("account.move", domain,
                                ["id", "name", "ref", "invoice_date", "amount_total", "amount_untaxed", "state"],
                                order="id desc", limit=50)

    def fy_billed_untaxed(self, partner_id: int, on: date | None = None) -> float:
        on = on or date.today()
        fy_start = date(on.year if on.month >= 4 else on.year - 1, 4, 1).isoformat()
        rows = self.search_read("account.move", [("move_type", "=", "in_invoice"), ("partner_id", "=", partner_id),
                                                 ("state", "=", "posted"), ("invoice_date", ">=", fy_start)],
                                ["amount_untaxed"])
        return round(sum(r["amount_untaxed"] for r in rows), 2)

    def create_bill(self, *, partner_id, ref, invoice_date, lines, po_name="", bank_id=None, narration="") -> int:
        vals = {
            "move_type": "in_invoice",
            "partner_id": partner_id,
            "ref": ref,
            "invoice_date": invoice_date or date.today().isoformat(),
            "invoice_origin": po_name,
            "l10n_in_gst_treatment": "regular",
            "invoice_line_ids": [(0, 0, line) for line in lines],
        }
        if bank_id:
            vals["partner_bank_id"] = bank_id
        if narration:
            vals["narration"] = narration
        return self.call("account.move", "create", vals)

    def bill(self, bill_id: int) -> dict:
        b = self.search_read("account.move", [("id", "=", bill_id)],
                             ["id", "name", "ref", "state", "payment_state", "amount_untaxed", "amount_tax",
                              "amount_total", "amount_residual", "invoice_date", "invoice_date_due", "partner_id"])[0]
        b["url"] = f"{self.url}/odoo/vendor-bills/{bill_id}"
        return b

    def post_bill(self, bill_id: int) -> dict:
        self.call("account.move", "action_post", [bill_id])
        return self.bill(bill_id)

    def note(self, model: str, rec_id: int, html: str) -> None:
        # body_is_html: over RPC Odoo otherwise escapes the body and the chatter shows raw tags
        self.call(model, "message_post", [rec_id], body=html, body_is_html=True, message_type="comment",
                  subtype_xmlid="mail.mt_note")

    def schedule_review(self, bill_id: int, summary: str, note: str = "") -> None:
        self.schedule_activity("account.move", bill_id, summary, note)

    def schedule_activity(self, model: str, rec_id: int, summary: str, note: str = "") -> None:
        model_id = self.call("ir.model", "search", [("model", "=", model)], limit=1)[0]
        type_ids = self.call("mail.activity.type", "search", [("category", "=", "default")], limit=1) or \
            self.call("mail.activity.type", "search", [], limit=1)
        self.call("mail.activity", "create", {
            "res_model_id": model_id,
            "res_id": rec_id,
            "activity_type_id": type_ids[0],
            "summary": summary[:120],
            "note": note,
            "user_id": self.uid,
            "date_deadline": date.today().isoformat(),
        })

    def close_reviews(self, bill_id: int, feedback: str) -> None:
        self.close_activities("account.move", bill_id, feedback)

    def close_activities(self, model: str, rec_id: int, feedback: str) -> None:
        ids = self.call("mail.activity", "search", [("res_model", "=", model), ("res_id", "=", rec_id)])
        if ids:
            self.call("mail.activity", "action_feedback", ids, feedback=feedback)

    def cancel_bill(self, bill_id: int) -> None:
        self.call("account.move", "button_cancel", [bill_id])

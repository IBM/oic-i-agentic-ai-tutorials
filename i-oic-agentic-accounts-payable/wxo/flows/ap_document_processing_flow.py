"""watsonx Orchestrate agentic flow: any AP document from intake to the right action in Odoo.

    START -> read_document      (Document processing: OCR, picks the matching schema = document type,
                                 key-value / table extraction with bounding boxes)
          -> identify_document  (Script: normalises fields for the detected type)
          -> document type ─┬ supplier_invoice → statutory_checks (script) → classify_payment (prompt, TDS)
                            │                    → erp_controls (tool) → route_invoice (decision table)
                            │                    → post_bill | hold_bill | END (duplicate)
                            ├ expense_receipt  → classify_expense (prompt) → expense_controls (tool)
                            │                    → route_expense (decision table) → approve | hold | END
                            ├ purchase_order   → verify_po (tool: compare with the Odoo PO, log on the PO)
                            ├ delivery_challan → receive_goods (tool: book the GRN, release held bills)
                            └ other            → END (unsupported: left for a person)

The LLM is used only for judgement (nature of payment for TDS, expense category); every number, GSTIN and ERP
check is deterministic, and routing policies are decision tables AP can change in the flow editor.
"""

from typing import List, Optional

from pydantic import BaseModel, Field

# Import flows before types (circular-import quirk in the ADK).
from ibm_watsonx_orchestrate.flow_builder.flows import END, START, Flow, flow
from ibm_watsonx_orchestrate.flow_builder.types import (
    DocProcField,
    DocProcInput,
    DocProcKVPSchema,
    DocProcOutputFormat,
    DocProcTable,
    DecisionsCondition,
    DecisionsRule,
    NodeErrorHandlerConfig,
    PromptLLMParameters,
)

TOUCHLESS_LIMIT_INR = 2_500_000  # delegation of authority: above ₹25 lakh a person signs off
LLM = "virtual-policy/ap_claude_fallback"  # Claude Sonnet 4.6, gpt-oss-120b on 429 / 5xx (see deploy.sh)
DOC_TYPES = {"GSTTaxInvoice": "supplier_invoice", "ExpenseReceipt": "expense_receipt",
             "PurchaseOrder": "purchase_order", "DeliveryChallan": "delivery_challan"}


def _f(description: str, example: str) -> DocProcField:
    return DocProcField(description=description, default="", example=example)


GST_INVOICE_SCHEMA = DocProcKVPSchema(
    document_type="GSTTaxInvoice",
    document_description="An Indian GST tax invoice from a business supplier of goods or services to a "
                         "registered company buyer, with a Bill To section, the buyer's purchase order number and "
                         "HSN/SAC line items. Not a cab, hotel, restaurant or card receipt.",
    fields={
        "supplier_name": _f("Legal name of the supplier issuing the invoice (top of page)", "Sahyadri Drums & Containers Pvt. Ltd."),
        "supplier_gstin": _f("15-character GSTIN of the supplier", "27AAHCS7314P1ZR"),
        "supplier_address": _f("Address of the supplier", "Gat No. 312, Chakan MIDC Phase II, Pune - 410501"),
        "buyer_name": _f("Name of the buyer in the Bill To section", "Meridian Specialty Chemicals India Pvt. Ltd."),
        "buyer_gstin": _f("GSTIN of the buyer in the Bill To section", "27AAJCM4821K1Z7"),
        "place_of_supply": _f("Place of supply state with state code", "Maharashtra (27)"),
        "invoice_number": _f("Supplier invoice number", "SDC/26-27/0418"),
        "invoice_date": _f("Invoice date", "2026-10-28"),
        "po_number": _f("Buyer's purchase order / order number", "MSC-PO-26-0147"),
        "irn": _f("64-character e-invoice Invoice Reference Number (IRN), if printed", "b66715466c35dae003a57b13096a66275dfd63fb64184cb174a555c59541b9a8"),
        "taxable_value": _f("Total taxable value before GST", "304200.00"),
        "cgst_amount": _f("Total CGST amount, if charged", "27378.00"),
        "sgst_amount": _f("Total SGST / UTGST amount, if charged", "27378.00"),
        "igst_amount": _f("Total IGST amount, if charged", "54756.00"),
        "total_amount": _f("Total invoice value including tax", "358956.00"),
        "bank_name": _f("Supplier bank name for remittance", "HDFC Bank"),
        "bank_account": _f("Supplier bank account number for remittance", "50200041873310"),
        "bank_ifsc": _f("IFSC code of the supplier bank branch", "HDFC0001267"),
        "line_items": DocProcTable(
            type="array",
            description="Invoice line items table",
            columns={
                "description": _f("Description of goods or services", "HDPE Open-Top Drum 200 L"),
                "hsn_sac": _f("HSN or SAC code", "39231090"),
                "quantity": _f("Quantity", "120"),
                "uom": _f("Unit of measure", "Nos"),
                "unit_price": _f("Rate per unit", "2450.00"),
                "amount": _f("Taxable value of the line", "294000.00"),
            },
        ),
    },
)


RECEIPT_SCHEMA = DocProcKVPSchema(
    document_type="ExpenseReceipt",
    document_description="A receipt or bill for an employee's business expense — a taxi or cab trip, hotel stay, "
                         "restaurant or meal, fuel, flight, or a card charge slip — even when it is titled 'tax "
                         "invoice'. Issued by a merchant to a traveller or diner, paid by card or UPI, with no "
                         "purchase order.",
    fields={
        "merchant_name": _f("Name of the merchant, hotel, restaurant or cab operator", "CityRide Mobility Pvt. Ltd."),
        "merchant_gstin": _f("GSTIN of the merchant", "27AAICC5520L1ZI"),
        "receipt_number": _f("Receipt, bill or invoice number", "CR-MUM-26-884213"),
        "receipt_date": _f("Date of the receipt", "2026-11-03"),
        "buyer_gstin": _f("Customer / buyer GSTIN if the bill is addressed to a company", "27AAJCM4821K1Z7"),
        "guest_or_trip": _f("Guest name, trip route or other description of the service", "Taloja MIDC → Vashi station"),
        "nights": _f("Number of nights for a hotel stay", "2"),
        "persons": _f("Number of covers / persons for a meal", "3"),
        "taxable_value": _f("Amount before GST", "612.00"),
        "cgst_amount": _f("CGST amount", "15.30"),
        "sgst_amount": _f("SGST amount", "15.30"),
        "igst_amount": _f("IGST amount", "0.00"),
        "total_amount": _f("Total amount paid", "642.60"),
        "card_last4": _f("Last 4 digits of the card used for payment, if paid by card", "4821"),
        "line_items": DocProcTable(type="array", description="Items on the receipt", columns={
            "description": _f("Item or service", "Trip fare"),
            "quantity": _f("Quantity", "1"),
            "amount": _f("Amount", "612.00"),
        }),
    },
)

PO_SCHEMA = DocProcKVPSchema(
    document_type="PurchaseOrder",
    document_description="A purchase order issued by the buyer to a supplier, possibly signed by the supplier.",
    fields={
        "po_number": _f("Purchase order number", "MSC-PO-26-0161"),
        "po_date": _f("PO date", "2026-10-01"),
        "supplier_name": _f("Supplier name", "Coromandel Plant Services Pvt. Ltd."),
        "supplier_gstin": _f("Supplier GSTIN", "33AAGCC6671D1ZU"),
        "line_items": DocProcTable(type="array", description="Ordered items", columns={
            "description": _f("Item description", "Quarterly Reactor & Pump AMC (Q3)"),
            "quantity": _f("Ordered quantity", "1"),
            "unit_price": _f("Rate", "225000.00"),
        }),
    },
)

CHALLAN_SCHEMA = DocProcKVPSchema(
    document_type="DeliveryChallan",
    document_description="A delivery challan, delivery note or goods receipt note that accompanies goods "
                         "delivered against a purchase order.",
    fields={
        "challan_number": _f("Delivery challan / delivery note number", "NPI/DC/26-27/1190"),
        "challan_date": _f("Challan date", "2026-11-04"),
        "po_number": _f("Purchase order the goods are delivered against", "MSC-PO-26-0158"),
        "supplier_name": _f("Supplier / consignor name", "Narmada Petrochem Industries Ltd."),
        "supplier_gstin": _f("Supplier / consignor GSTIN", "24AABCN5532R1Z4"),
        "vehicle_number": _f("Vehicle number", "GJ-06-AT-4471"),
        "line_items": DocProcTable(type="array", description="Goods delivered", columns={
            "description": _f("Description of goods", "Polyisobutylene PIB 1300 (bulk)"),
            "quantity": _f("Quantity delivered", "2"),
            "uom": _f("Unit of measure", "MT"),
        }),
    },
)

NUMERIC = ["taxable_value", "cgst_amount", "sgst_amount", "igst_amount", "total_amount", "nights", "persons",
           "quantity", "unit_price", "amount"]

IDENTIFY_SCRIPT = r'''
TYPES = __TYPES__
NUMERIC = __NUMERIC__

def attr(o, k):
    if isinstance(o, dict):
        return o.get(k)
    return getattr(o, k, None)

def num(v):
    s = "".join(ch for ch in str(v or "") if ch.isdigit() or ch in ".-")
    try:
        return round(float(s), 2) if s not in ("", ".", "-") else 0.0
    except Exception:
        return 0.0

def iso_date(v):
    s = str(v or "").strip().replace("/", "-").replace(".", "-")
    p = s.split("-")
    if len(p) == 3 and len(p[2]) == 4:
        return p[2] + "-" + p[1].zfill(2) + "-" + p[0].zfill(2)
    return s

out = flow["read_document"].output
pages = attr(attr(out, "metadata") or {}, "pages_metadata") or []
detected = str(attr(pages[0], "document_type") or "") if pages else ""
fields, rows = {}, {}
for item in attr(out, "kvps") or []:
    k, v = attr(item, "key"), attr(item, "value")
    label = attr(k, "semantic_label") if k is not None else ""
    val = (attr(v, "normalized_text") or attr(v, "raw_text") or "") if v is not None else ""
    if not label:
        continue
    if "." in label and attr(item, "table_row_index") is not None:
        rows.setdefault(attr(item, "table_row_index"), {})[label.split(".", 1)[1]] = val
    else:
        fields[label] = val
for key in list(fields.keys()):
    if key in NUMERIC:
        fields[key] = num(fields[key])
    elif key.endswith("_date"):
        fields[key] = iso_date(fields[key])
    elif key.endswith("gstin"):
        fields[key] = str(fields[key]).replace(" ", "").upper()
    elif key == "card_last4":
        fields[key] = "".join(ch for ch in str(fields[key]) if ch.isdigit())[-4:]
lines = []
for idx in sorted(rows.keys()):
    r = rows[idx]
    line = {"description": str(r.get("description", "")).strip()}
    for k in ("quantity", "unit_price", "amount"):
        line[k] = num(r.get(k))
    line["uom"] = str(r.get("uom", "")).strip()
    lines.append(line)
fields["line_items"] = lines
doc_type = TYPES.get(detected, "other")
self.output.doc_type = doc_type
self.output.detected_schema = detected or "none"
self.output.fields = fields
self.output.summary = (str(fields.get("merchant_name") or fields.get("supplier_name") or "") + "\n"
                       + str(fields.get("guest_or_trip") or "") + "\n"
                       + "\n".join("- " + l["description"] for l in lines))
'''.replace("__TYPES__", repr(DOC_TYPES)).replace("__NUMERIC__", repr(NUMERIC))


class LineItem(BaseModel):
    description: str = ""
    hsn_sac: str = ""
    quantity: float = 0.0
    uom: str = ""
    unit_price: float = 0.0
    amount: float = 0.0


class StatutoryCheck(BaseModel):
    code: str
    category: str
    status: str = Field(description="pass | warn | fail | info")
    title: str
    detail: str = ""


class InvoiceRecord(BaseModel):
    supplier_name: str = ""
    supplier_gstin: str = ""
    supplier_address: str = ""
    buyer_name: str = ""
    buyer_gstin: str = ""
    place_of_supply: str = ""
    invoice_number: str = ""
    invoice_date: str = ""
    po_number: str = ""
    irn: str = ""
    taxable_value: float = 0.0
    cgst_amount: float = 0.0
    sgst_amount: float = 0.0
    igst_amount: float = 0.0
    total_amount: float = 0.0
    bank_name: str = ""
    bank_account: str = ""
    bank_ifsc: str = ""
    line_items: List[LineItem] = Field(default_factory=list)
    lines_text: str = Field(default="", description="Line items as plain text, for the classifier")
    checks: List[StatutoryCheck] = Field(default_factory=list)


class ClassifierInput(BaseModel):
    supplier_name: str = ""
    lines_text: str = ""


class PaymentNature(BaseModel):
    nature: str = Field(description="One of: goods, professional, technical, contract, rent, other")
    confidence: float = Field(description="0.0 - 1.0")
    rationale: str = Field(description="One sentence explaining the classification")


class FlowInput(DocProcInput):
    submitted_by: str = Field(default="", description="Email of the employee or mailbox that sent the document")


class DocumentRecord(BaseModel):
    doc_type: str = Field(description="supplier_invoice | expense_receipt | purchase_order | delivery_challan | other")
    detected_schema: str = ""
    fields: dict = Field(default_factory=dict)
    summary: str = ""


class ExpenseSummary(BaseModel):
    summary: str = ""


class ExpenseCategory(BaseModel):
    category: str = Field(description="One of: local_travel, hotel, meals, airfare, other")
    purpose: str = Field(description="Likely business purpose in a short phrase")
    confidence: float = Field(description="0.0 - 1.0")


class FlowOutput(BaseModel):
    doc_type: str = ""
    detected_schema: str = ""
    document: Optional[dict] = None  # normalised fields for non-invoice documents
    invoice: Optional[InvoiceRecord] = None
    payment_nature: Optional[PaymentNature] = None
    expense_category: Optional[ExpenseCategory] = None
    kvps: Optional[List[dict]] = None
    metadata: Optional[dict] = None
    extracted_text: str = ""
    route: str = ""
    route_reason: str = ""
    controls: Optional[dict] = None
    posted: Optional[dict] = None  # each branch fills only its own outputs
    held: Optional[dict] = None
    expense_controls: Optional[dict] = None
    expense_approved: Optional[dict] = None
    expense_held: Optional[dict] = None
    po_check: Optional[dict] = None
    receipt: Optional[dict] = None


STATUTORY_CHECKS_SCRIPT = r'''
CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
SLABS = [0.0, 5.0, 18.0, 40.0]

def num(v):
    s = "".join(ch for ch in str(v or "") if ch.isdigit() or ch in ".-")
    try:
        return round(float(s), 2) if s not in ("", ".", "-") else 0.0
    except Exception:
        return 0.0

def iso_date(v):
    s = str(v or "").strip().replace("/", "-").replace(".", "-")
    p = s.split("-")
    if len(p) == 3 and len(p[0]) == 4:
        return s
    if len(p) == 3 and len(p[2]) == 4:
        return p[2] + "-" + p[1].zfill(2) + "-" + p[0].zfill(2)
    return s

def gstin_ok(g):
    g = (g or "").strip().upper()
    if len(g) != 15 or not g[:2].isdigit() or g[13] != "Z":
        return False
    for ch in g:
        if ch not in CHARS:
            return False
    total = 0
    for i in range(14):
        prod = CHARS.index(g[i]) * (2 if i % 2 else 1)
        total += prod // 36 + prod % 36
    return CHARS[(36 - total % 36) % 36] == g[14]

def attr(o, k):
    if isinstance(o, dict):
        return o.get(k)
    return getattr(o, k, None)

node_out = flow["read_document"].output
raw_kvps = attr(node_out, "kvps") or []

fields = {}
rows = {}
for item in raw_kvps:
    k = attr(item, "key")
    v = attr(item, "value")
    label = attr(k, "semantic_label") if k is not None else ""
    val = (attr(v, "normalized_text") or attr(v, "raw_text") or "") if v is not None else ""
    if not label:
        continue
    if "." in label and attr(item, "table_row_index") is not None:
        idx = attr(item, "table_row_index")
        rows.setdefault(idx, {})[label.split(".", 1)[1]] = val
    else:
        fields[label] = val

lines = []
for idx in sorted(rows.keys()):
    r = rows[idx]
    lines.append({
        "description": str(r.get("description", "")).strip(),
        "hsn_sac": "".join(ch for ch in str(r.get("hsn_sac", "")) if ch.isdigit()),
        "quantity": num(r.get("quantity")),
        "uom": str(r.get("uom", "")).strip(),
        "unit_price": num(r.get("unit_price")),
        "amount": num(r.get("amount")),
    })

sup_gstin = str(fields.get("supplier_gstin", "")).replace(" ", "").upper()
buy_gstin = str(fields.get("buyer_gstin", "")).replace(" ", "").upper()
pos = str(fields.get("place_of_supply", ""))
pos_code = "".join(ch for ch in pos if ch.isdigit())[:2] or buy_gstin[:2]
taxable = num(fields.get("taxable_value"))
cgst = num(fields.get("cgst_amount"))
sgst = num(fields.get("sgst_amount"))
igst = num(fields.get("igst_amount"))
total = num(fields.get("total_amount"))
irn = str(fields.get("irn", "")).strip().lower().replace(" ", "")
line_sum = round(sum(l["amount"] for l in lines), 2)
if taxable == 0.0:
    taxable = line_sum

checks = []
def add(code, cat, status, title, detail):
    checks.append({"code": code, "category": cat, "status": status, "title": title, "detail": detail})

missing = [n for n in ["invoice_number", "invoice_date", "supplier_gstin", "total_amount"] if not fields.get(n)]
add("DOC-01", "Document", "fail" if missing else "pass", "Mandatory invoice particulars",
    ("Missing: " + ", ".join(missing)) if missing else "Invoice no., date, supplier GSTIN and total present")
no_hsn = [str(i + 1) for i, l in enumerate(lines) if len(l["hsn_sac"]) < 4]
add("DOC-02", "Document", "warn" if no_hsn else "pass", "HSN / SAC on every line",
    ("No valid HSN/SAC on line(s) " + ", ".join(no_hsn)) if no_hsn else str(len(lines)) + " line(s) carry HSN/SAC codes")

add("GST-01", "GST", "pass" if gstin_ok(sup_gstin) else "fail", "Supplier GSTIN valid",
    sup_gstin + (" passes format and check-digit validation" if gstin_ok(sup_gstin) else " fails format / check-digit validation"))
add("GST-02", "GST", "pass" if gstin_ok(buy_gstin) else "fail", "Buyer GSTIN valid",
    buy_gstin + (" passes format and check-digit validation" if gstin_ok(buy_gstin) else " fails format / check-digit validation"))

intra = sup_gstin[:2] == pos_code
if intra:
    ok = igst == 0.0 and cgst > 0 and abs(cgst - sgst) <= 0.5
    add("GST-03", "GST", "pass" if ok else "fail", "Tax regime matches place of supply",
        "Intra-state supply (" + sup_gstin[:2] + " to " + pos_code + "): expects CGST + SGST" + ("" if ok else "; invoice charges IGST " + str(igst)))
else:
    ok = cgst == 0.0 and sgst == 0.0 and igst > 0
    add("GST-03", "GST", "pass" if ok else "fail", "Tax regime matches place of supply",
        "Inter-state supply (" + sup_gstin[:2] + " to " + pos_code + "): expects IGST" + ("" if ok else "; invoice charges CGST " + str(cgst) + " + SGST " + str(sgst) + " instead"))

tax_total = round(cgst + sgst + igst, 2)
eff = round(tax_total * 100.0 / taxable, 2) if taxable else 0.0
slab = min(SLABS, key=lambda s: abs(s - eff))
add("GST-04", "GST", "pass" if abs(slab - eff) <= 0.1 else "warn", "GST rate is a notified slab",
    "Effective rate " + str(eff) + "% (nearest slab " + str(slab) + "%)")

bad_lines = [str(i + 1) for i, l in enumerate(lines) if l["quantity"] and l["unit_price"] and abs(round(l["quantity"] * l["unit_price"], 2) - l["amount"]) > 1.0]
add("MATH-01", "Arithmetic", "fail" if bad_lines or abs(line_sum - taxable) > 1.0 else "pass", "Line items add up",
    (("Qty x rate mismatch on line(s) " + ", ".join(bad_lines) + ". ") if bad_lines else "") +
    "Sum of lines " + str(line_sum) + " vs taxable value " + str(taxable))
diff = round(taxable + tax_total - total, 2)
add("MATH-02", "Arithmetic", "pass" if abs(diff) <= 1.0 else "fail", "Taxable value + GST = invoice total",
    str(taxable) + " + " + str(tax_total) + " = " + str(round(taxable + tax_total, 2)) + " vs total " + str(total))

irn_ok = len(irn) == 64 and all(ch in "0123456789abcdef" for ch in irn)
add("EINV-01", "E-invoice", "pass" if irn_ok else "info", "IRN printed on invoice",
    "Valid 64-character IRN found" if irn_ok else "No IRN on the document")

self.output.supplier_name = str(fields.get("supplier_name", "")).strip()
self.output.supplier_gstin = sup_gstin
self.output.supplier_address = str(fields.get("supplier_address", "")).strip()
self.output.buyer_name = str(fields.get("buyer_name", "")).strip()
self.output.buyer_gstin = buy_gstin
self.output.place_of_supply = pos
self.output.invoice_number = str(fields.get("invoice_number", "")).strip()
self.output.invoice_date = iso_date(fields.get("invoice_date"))
self.output.po_number = str(fields.get("po_number", "")).strip()
self.output.irn = irn if irn_ok else ""
self.output.taxable_value = taxable
self.output.cgst_amount = cgst
self.output.sgst_amount = sgst
self.output.igst_amount = igst
self.output.total_amount = total
self.output.bank_name = str(fields.get("bank_name", "")).strip()
self.output.bank_account = "".join(ch for ch in str(fields.get("bank_account", "")) if ch.isalnum())
self.output.bank_ifsc = str(fields.get("bank_ifsc", "")).replace(" ", "").upper()
self.output.line_items = lines
self.output.lines_text = "\n".join("- " + l["description"] + " (HSN/SAC " + l["hsn_sac"] + ", qty " + str(l["quantity"]) + " " + l["uom"] + ")" for l in lines)
self.output.checks = checks
'''


@flow(
    name="ap_document_processing_flow",
    display_name="AP document processing (invoices · receipts · POs · challans → Odoo)",
    description=(
        "Reads any accounts-payable document, recognises its type and processes it end to end against Odoo: "
        "GST supplier invoices (GST, 3-way match, TDS, then post / hold / block the bill), employee expense "
        "receipts (policy checks, then an approved or held expense), purchase-order copies (verified against the "
        "PO) and delivery challans (goods received). Input: the document and, optionally, the submitter's email."
    ),
    input_schema=FlowInput,
    output_schema=FlowOutput,
)
def build_ap_document_processing_flow(aflow: Flow = None) -> Flow:
    read = aflow.docproc(
        name="read_document",
        display_name="Read & classify document (WDU)",
        description="OCR, document-type detection across the AP schemas, key-value / table extraction with "
                    "bounding boxes.",
        task="text_extraction",
        output_format=DocProcOutputFormat.object,
        enable_hw=True,
        kvp_schemas=[GST_INVOICE_SCHEMA, RECEIPT_SCHEMA, PO_SCHEMA, CHALLAN_SCHEMA],
        kvp_enable_text_hints=True,
        error_handler_config=NodeErrorHandlerConfig(
            error_message="Document extraction failed.", max_retries=1, retry_interval=1000
        ),
    )
    read.map_input(input_variable="document_ref", expression="flow.input.document_ref")

    identify = aflow.script(
        name="identify_document",
        display_name="Identify document type",
        description="Maps the detected schema to a document type and normalises the extracted fields.",
        output_schema=DocumentRecord,
        script=IDENTIFY_SCRIPT,
    )

    def rule(node: str, when: tuple[str, DecisionsCondition], route: str, reason: str) -> DecisionsRule:
        return (DecisionsRule().condition(f'flow["{node}"].output.{when[0]}', when[1])
                .action("flow.output.route", route).action("flow.output.route_reason", reason))

    # ---- supplier invoice ---------------------------------------------------------------------
    checks = aflow.script(
        name="statutory_checks",
        display_name="GST & arithmetic checks",
        description="Normalises extracted values and runs deterministic GSTIN, GST regime, slab and arithmetic checks.",
        output_schema=InvoiceRecord,
        script=STATUTORY_CHECKS_SCRIPT,
    )
    classify = aflow.prompt(
        name="classify_payment",
        display_name="Classify nature of payment (TDS)",
        description="Classifies what is being paid for, which drives the TDS section.",
        system_prompt=[
            "You are an Indian accounts-payable tax specialist.",
            "Classify the nature of payment on a supplier invoice for TDS purposes under the Income-tax Act, 2025.",
            "Choose exactly one nature:",
            "goods - purchase of goods or materials;",
            "professional - fees for professional or consultancy services: engineering, process-safety or HAZOP "
            "studies, legal, audit, advisory, and consultants deployed on site;",
            "technical - fees for technical services delivered by a provider: software support, equipment testing "
            "or calibration, technical assistance. Not consultancy or studies;",
            "contract - contract work (maintenance contracts, AMC, repairs, labour, transport, job work, catering);",
            "rent - rent of land, building, plant or machinery;",
            "other - none of the above.",
            "SAC codes starting 99 indicate services; HSN codes indicate goods.",
            "Return the nature, your confidence between 0 and 1, and a one-sentence rationale.",
        ],
        user_prompt="Supplier: {supplier_name}\nLine items:\n{lines_text}",
        llm=LLM,
        llm_parameters=PromptLLMParameters(temperature=0.01),  # 0 is dropped by the ADK; near-greedy for repeatability
        input_schema=ClassifierInput,
        output_schema=PaymentNature,
    )
    classify.map_input("supplier_name", 'flow["statutory_checks"].output.supplier_name')
    classify.map_input("lines_text", 'flow["statutory_checks"].output.lines_text')

    erp = aflow.tool("ap_erp_controls", name="erp_controls", display_name="ERP controls (Odoo)",
                     error_handler_config=NodeErrorHandlerConfig(error_message="ERP controls failed.", max_retries=1,
                                                                 retry_interval=2000))
    erp.map_input("invoice", 'flow["statutory_checks"].output')
    erp.map_input("payment_nature", 'flow["classify_payment"].output')

    decide = aflow.decisions(
        name="route_invoice",
        display_name="AP routing policy",
        description="First matching rule wins: duplicates are blocked, any failed control goes to review, and "
                    "clean invoices above the touchless limit need a person's sign-off.",
        rules=[
            rule("erp_controls", ("duplicates", DecisionsCondition().greater_than(0)), "blocked", "Duplicate invoice"),
            rule("erp_controls", ("exceptions", DecisionsCondition().greater_than(0)), "exception", ""),
            rule("erp_controls", ("invoice_total", DecisionsCondition().greater_than(TOUCHLESS_LIMIT_INR)), "exception",
                 "Above ₹25 lakh touchless limit"),
        ],
        default_actions={"flow.output.route": "touchless", "flow.output.route_reason": ""},
    )
    post = aflow.tool("ap_post_bill", name="post_bill", display_name="Post bill in Odoo")
    hold = aflow.tool("ap_hold_bill", name="hold_bill", display_name="Hold for AP review")
    for node in (post, hold):
        node.map_input("invoice", 'flow["statutory_checks"].output')
        node.map_input("control_result", 'flow["erp_controls"].output.result')
    hold.map_input("reason", "flow.output.route_reason")
    route = aflow.branch(name="route", display_name="Route invoice", evaluator="flow.output.route")
    route.case("touchless", post).case("exception", hold).case("blocked", END)

    # ---- employee expense receipt ---------------------------------------------------------------
    category = aflow.prompt(
        name="classify_expense",
        display_name="Classify expense category",
        description="Decides the expense-policy category and likely business purpose from the receipt.",
        system_prompt=[
            "You classify employee business-expense receipts for an Indian company's expense policy.",
            "Choose exactly one category:",
            "local_travel - taxi, cab, auto, metro, local conveyance or parking;",
            "hotel - hotel or guest-house accommodation;",
            "meals - restaurant, food, beverages or client entertainment;",
            "airfare - flights;",
            "other - anything else.",
            "Also give the likely business purpose in a short phrase, and your confidence between 0 and 1.",
        ],
        user_prompt="{summary}",
        llm=LLM,
        llm_parameters=PromptLLMParameters(temperature=0.01),  # 0 is dropped by the ADK; near-greedy for repeatability
        input_schema=ExpenseSummary,
        output_schema=ExpenseCategory,
    )
    category.map_input("summary", 'flow["identify_document"].output.summary')

    exp = aflow.tool("ap_expense_controls", name="expense_controls", display_name="Expense policy controls (Odoo)")
    exp.map_input("receipt", 'flow["identify_document"].output.fields')
    exp.map_input("category", 'flow["classify_expense"].output')
    exp.map_input("submitted_by", "flow.input.submitted_by")

    decide_exp = aflow.decisions(
        name="route_expense",
        display_name="Expense routing policy",
        description="Duplicates are blocked, any failed policy control needs the manager, otherwise auto-approve.",
        rules=[
            rule("expense_controls", ("duplicates", DecisionsCondition().greater_than(0)), "blocked", "Duplicate receipt"),
            rule("expense_controls", ("exceptions", DecisionsCondition().greater_than(0)), "exception", "Manager approval"),
        ],
        default_actions={"flow.output.route": "touchless", "flow.output.route_reason": ""},
    )
    approve = aflow.tool("ap_book_expense", name="approve_expense", display_name="Approve expense in Odoo")
    hold_exp = aflow.tool("ap_book_expense", name="hold_expense", display_name="Hold expense for manager")
    for node, ok in ((approve, "True"), (hold_exp, "False")):
        node.map_input("receipt", 'flow["identify_document"].output.fields')
        node.map_input("control_result", 'flow["expense_controls"].output.result')
        node.map_input("approve", ok)
    route_exp = aflow.branch(name="route_exp", display_name="Route expense", evaluator="flow.output.route")
    route_exp.case("touchless", approve).case("exception", hold_exp).case("blocked", END)

    # ---- purchase-order copy and delivery challan ------------------------------------------------
    verify = aflow.tool("ap_verify_po", name="verify_po", display_name="Verify PO against Odoo")
    receive = aflow.tool("ap_receive_goods", name="receive_goods", display_name="Receive goods (GRN) in Odoo")
    for node in (verify, receive):
        node.map_input("document", 'flow["identify_document"].output.fields')

    by_type = aflow.branch(name="document_type", display_name="Document type",
                           evaluator='flow["identify_document"].output.doc_type')
    (by_type.case("supplier_invoice", checks).case("expense_receipt", category)
     .case("purchase_order", verify).case("delivery_challan", receive).case("other", END))

    aflow.sequence(START, read, identify, by_type)
    aflow.sequence(checks, classify, erp, decide, route)
    aflow.sequence(category, exp, decide_exp, route_exp)
    for node in (post, hold, approve, hold_exp, verify, receive):
        aflow.edge(node, END)

    # Explicit maps (with defaults) for every output, so branches without a decision table never fall back to
    # the runtime's automatic output mapping.
    aflow.map_output(output_variable="route", expression="flow.output.route", default_value="")
    aflow.map_output(output_variable="route_reason", expression="flow.output.route_reason", default_value="")
    aflow.map_output(output_variable="doc_type", expression='flow["identify_document"].output.doc_type')
    aflow.map_output(output_variable="detected_schema", expression='flow["identify_document"].output.detected_schema')
    aflow.map_output(output_variable="document", expression='flow["identify_document"].output.fields')
    aflow.map_output(output_variable="kvps", expression='flow["read_document"].output.kvps')
    aflow.map_output(output_variable="metadata", expression='flow["read_document"].output.metadata')
    aflow.map_output(output_variable="extracted_text", expression='flow["read_document"].output.text')
    aflow.map_output(output_variable="invoice", expression='flow["statutory_checks"].output')
    aflow.map_output(output_variable="payment_nature", expression='flow["classify_payment"].output')
    aflow.map_output(output_variable="controls", expression='flow["erp_controls"].output.result')
    aflow.map_output(output_variable="posted", expression='flow["post_bill"].output')
    aflow.map_output(output_variable="held", expression='flow["hold_bill"].output')
    aflow.map_output(output_variable="expense_category", expression='flow["classify_expense"].output')
    aflow.map_output(output_variable="expense_controls", expression='flow["expense_controls"].output.result')
    aflow.map_output(output_variable="expense_approved", expression='flow["approve_expense"].output')
    aflow.map_output(output_variable="expense_held", expression='flow["hold_expense"].output')
    aflow.map_output(output_variable="po_check", expression='flow["verify_po"].output')
    aflow.map_output(output_variable="receipt", expression='flow["receive_goods"].output')
    return aflow

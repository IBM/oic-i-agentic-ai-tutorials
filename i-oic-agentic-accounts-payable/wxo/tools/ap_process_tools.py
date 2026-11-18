"""Process tools used as nodes of ap_document_processing_flow: invoice controls and bill booking, expense
policy and booking, PO verification and goods receipt. Agents do not call these directly; the flow's decision
tables choose which booking node runs."""

from ibm_watsonx_orchestrate.agent_builder.tools import ToolPermission, tool
from ibm_watsonx_orchestrate.run import connections
from pydantic import BaseModel, ConfigDict, Field

from apcore import booking, controls, expenses, receiving
from apcore.odoo import Odoo
from erp import APP_ID, ODOO_CREDENTIALS


# Typed (open) inputs for the flow nodes. The flow runtime also passes the previous node's output as `data`,
# which every tool accepts and ignores.
class Invoice(BaseModel):
    model_config = ConfigDict(extra="allow")
    invoice_number: str = ""
    supplier_gstin: str = ""
    total_amount: float = 0.0
    checks: list[dict] = Field(default_factory=list)


class PaymentNature(BaseModel):
    model_config = ConfigDict(extra="allow")
    nature: str = ""
    confidence: float = 0.0
    rationale: str = ""


class ControlResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    duplicates: int = 0
    exceptions: int = 0
    checks: list[dict] = Field(default_factory=list)
    vendor: dict | None = None


class ControlOutcome(BaseModel):
    duplicates: int = Field(description="Failed duplicate-invoice controls (DUP-01)")
    exceptions: int = Field(description="Failed controls in total, including statutory checks from the flow")
    invoice_total: float = Field(description="Invoice total in INR")
    result: ControlResult = Field(description="Control results: checks, vendor, PO, matched lines, TDS, net payable")


class Booking(BaseModel):
    summary: str
    bill: dict | None = None
    controls: dict | None = Field(default=None, description="Control results, updated when a policy rule added a check")


def _plain(value) -> dict:
    return value.model_dump() if isinstance(value, BaseModel) else dict(value or {})


def _odoo() -> Odoo:
    c = connections.key_value(APP_ID)
    return Odoo(c["url"], c["db"], c["username"], c["password"])


@tool(name="ap_erp_controls", permission=ToolPermission.READ_ONLY, expected_credentials=ODOO_CREDENTIALS)
def ap_erp_controls(invoice: Invoice, payment_nature: PaymentNature, data: dict | None = None) -> ControlOutcome:
    """Run the ERP controls on an extracted GST invoice against live Odoo data: vendor master and buyer GSTIN,
    duplicates, remittance bank account, e-invoice IRN, PO price and GRN quantity (3-way match) and TDS."""
    result = controls.evaluate(_plain(invoice), _plain(payment_nature), _odoo())
    return ControlOutcome(duplicates=result["duplicates"], exceptions=result["exceptions"],
                          invoice_total=float(invoice.total_amount or 0), result=result)


@tool(name="ap_post_bill", permission=ToolPermission.READ_WRITE, expected_credentials=ODOO_CREDENTIALS)
def ap_post_bill(invoice: Invoice, control_result: ControlResult, data: dict | None = None) -> Booking:
    """Create and post the vendor bill in Odoo for an invoice that passed every control (touchless)."""
    return Booking(**booking.post(_plain(invoice), _plain(control_result), _odoo()))


@tool(name="ap_hold_bill", permission=ToolPermission.READ_WRITE, expected_credentials=ODOO_CREDENTIALS)
def ap_hold_bill(invoice: Invoice, control_result: ControlResult, reason: str = "",
                 data: dict | None = None) -> Booking:
    """Create a draft vendor bill in Odoo with a review task listing the exceptions, for AP to approve or reject."""
    return Booking(**booking.hold(_plain(invoice), _plain(control_result), _odoo(), reason))


# ---- expenses, PO copies and delivery challans --------------------------------------------------
class Document(BaseModel):
    model_config = ConfigDict(extra="allow")
    line_items: list[dict] = Field(default_factory=list)


class ExpenseCategory(BaseModel):
    model_config = ConfigDict(extra="allow")
    category: str = "other"
    purpose: str = ""


class ExpenseOutcome(BaseModel):
    duplicates: int
    exceptions: int
    result: ControlResult


class Outcome(BaseModel):
    model_config = ConfigDict(extra="allow")
    summary: str = ""
    exceptions: int = 0
    checks: list[dict] = Field(default_factory=list)


@tool(name="ap_expense_controls", permission=ToolPermission.READ_ONLY, expected_credentials=ODOO_CREDENTIALS)
def ap_expense_controls(receipt: Document, category: ExpenseCategory, submitted_by: str = "",
                        data: dict | None = None) -> ExpenseOutcome:
    """Check an employee expense receipt against the expense policy and Odoo: employee and corporate card,
    category limit, age, duplicate claims and GST input-credit eligibility."""
    result = expenses.evaluate(_plain(receipt), _plain(category), submitted_by, _odoo())
    return ExpenseOutcome(duplicates=result["duplicates"], exceptions=result["exceptions"], result=result)


@tool(name="ap_book_expense", permission=ToolPermission.READ_WRITE, expected_credentials=ODOO_CREDENTIALS)
def ap_book_expense(receipt: Document, control_result: ControlResult, approve: bool = False,
                    data: dict | None = None) -> dict:
    """Create the employee expense in Odoo: approved when every control passed, otherwise held for the manager."""
    return expenses.book(_plain(receipt), _plain(control_result), _odoo(), approve)


@tool(name="ap_verify_po", permission=ToolPermission.READ_WRITE, expected_credentials=ODOO_CREDENTIALS)
def ap_verify_po(document: Document, data: dict | None = None) -> Outcome:
    """Compare a purchase-order copy (e.g. signed by the supplier) with the PO in Odoo and log the result on it."""
    return Outcome(**receiving.verify_po(_plain(document), _odoo()))


@tool(name="ap_receive_goods", permission=ToolPermission.READ_WRITE, expected_credentials=ODOO_CREDENTIALS)
def ap_receive_goods(document: Document, data: dict | None = None) -> Outcome:
    """Book the goods on a delivery challan against the open Odoo receipt (GRN) when the quantities fit, and
    tell AP when a bill held for a GRN shortage on the same PO can be released."""
    return Outcome(**receiving.receive(_plain(document), _odoo()))

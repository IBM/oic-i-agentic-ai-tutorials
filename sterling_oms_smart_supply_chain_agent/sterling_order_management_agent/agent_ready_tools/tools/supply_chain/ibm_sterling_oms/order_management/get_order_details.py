from typing import Optional

from ibm_watsonx_orchestrate.agent_builder.tools import tool

from agent_ready_tools.clients.sterling_oms_client import get_sterling_oms_client
from agent_ready_tools.tools.procurement.common_dataclasses import ToolResponse
from agent_ready_tools.tools.supply_chain.ibm_sterling_oms.order_management.common_dataclasses import (
    OMSOrderDate,
    OMSOrderDetails,
    OMSOrderLine,
    OMSOrderNote,
    display_error_from_response,
    get_order_details_body_from_template,
)
from agent_ready_tools.utils.tool_credentials import STERLING_OMS_CONNECTIONS


@tool(expected_credentials=STERLING_OMS_CONNECTIONS)
def sterling_oms_get_order_details(
    order_number: str,
    order_header_key: str,
    enterprise_code: Optional[str] = None,
) -> ToolResponse[OMSOrderDetails]:
    """
    Retrieves order details.

    Args:
        order_number: The number of the order
        order_header_key: The unique id of the order, returned by the tool `sterling_oms_get_orders`.
        enterprise_code: The unique ID of the enterprise to which the orders belong to

    Returns:
        The retrieved order details.
    """
    try:
        client = get_sterling_oms_client()
    except (ValueError, AssertionError):
        return ToolResponse(success=False, message="Failure to retrieve credentials")

    body = get_order_details_body_from_template(order_number, order_header_key, enterprise_code)

    response = client.post_request(resource_name="/invoke/getPage", payload=body)
    if "errors" in response:
        return ToolResponse(success=False, message=display_error_from_response(response["errors"]))

    r = response.get("Output", {}).get("Order", {})

    assert isinstance(r, dict)

    result = OMSOrderDetails(
        order_id=r.get("id", ""),
        order_number=r.get("OrderNo"),
        order_date=r.get("OrderDate"),
        order_type=r.get("DocumentType"),
        status=r.get("Status"),
        buyer_organization=r.get("BuyerOrganizationCode"),
        requested_ship_date=r.get("ReqShipDate"),
        requested_delivery_date=r.get("ReqDeliveryDate"),
        bill_to_id=r.get("BillToID"),
        vendor_id=r.get("VendorID", ""),
        customer_po_number=r.get("CustomerPONo", ""),
        total_amount=r.get("PriceInfo", {}).get("TotalAmount", "")
        + " "
        + r.get("PriceInfo", {}).get("Currency", ""),
        order_lines=None,
        order_dates=None,
        order_notes=None,
        city_name=r.get("PersonInfoShipTo", {}).get("City", ""),
        zip_code=r.get("PersonInfoShipTo", {}).get("ZipCode", ""),
        # address= r.get("PersonInfoShipTo",{}).get("AddressLine1","")
    )

    line_items = r.get("OrderLines", {}).get("OrderLine")
    if line_items is not None and isinstance(line_items, list):
        result.order_lines = [
            OMSOrderLine(
                item_id=line.get("ItemDetails", {}).get("ItemID"),
                uom=line.get("ItemDetails", {}).get("UnitOfMeasure"),
                ship_node=line.get("ShipNode"),
                segment=line.get("Segment"),
                segment_type=line.get("SegmentType"),
            )
            for line in line_items
        ]

    dates = r.get("OrderDates", {}).get("OrderDate")
    if dates is not None and isinstance(dates, list):
        result.order_dates = [
            OMSOrderDate(
                committed_date=date.get("CommittedDate"),
                expected_date=date.get("ExpectedDate"),
            )
            for date in dates
        ]

    notes = r.get("Notes", {}).get("Note")
    if notes is not None and isinstance(notes, list):
        result.order_notes = [
            OMSOrderNote(
                note_text=note.get("NoteText"),
                reason_code=note.get("ReasonCode"),
            )
            for note in notes
        ]

    return ToolResponse(success=True, message="Following is the order details", content=result)

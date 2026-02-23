from typing import Any, Optional

from ibm_watsonx_orchestrate.agent_builder.tools import tool

from agent_ready_tools.clients.sterling_oms_client import get_sterling_oms_client
from agent_ready_tools.tools.procurement.common_dataclasses import ToolResponse
from agent_ready_tools.tools.supply_chain.ibm_sterling_oms.order_management.common_dataclasses import (
    OMSUpdateOrderResponse,
)
from agent_ready_tools.utils.tool_credentials import STERLING_OMS_CONNECTIONS


@tool(expected_credentials=STERLING_OMS_CONNECTIONS)
def sterling_oms_update_order(
    order_id: str,
    vendor_id: Optional[str] = None,
    customer_po_number: Optional[str] = None,
    committed_date: Optional[str] = None,
    expected_date: Optional[str] = None,
) -> ToolResponse[OMSUpdateOrderResponse]:
    """
    Updates an order.

    Args:
        order_id: The unique identifier of the order.
        vendor_id: The unique identifier of the vendor or supplier.
        customer_po_number: The purchase order number of the customer.
        committed_date: The committed date from supplier in ISO format (YYYY-MM-DD).
        expected_date: The expected date from supplier in ISO format (YYYY-MM-DD).

    Returns:
        The response of updating an order.
    """

    try:
        client = get_sterling_oms_client()
    except (ValueError, AssertionError):
        return ToolResponse(success=False, message="Failure to retrieve credentials")

    payload: dict[str, Any] = {
        "VendorID": vendor_id,
        "CustomerPONo": customer_po_number,
    }

    order_dates = {}

    if committed_date and expected_date:
        order_dates["OrderDate"] = [
            {"CommittedDate": committed_date, "ExpectedDate": expected_date}
        ]
    elif committed_date:
        order_dates["OrderDate"] = [{"CommittedDate": committed_date}]
    elif expected_date:
        order_dates["OrderDate"] = [{"ExpectedDate": expected_date}]

    if order_dates:
        payload["OrderDates"] = order_dates

    payload = {key: value for key, value in payload.items() if value}

    if not payload:
        return ToolResponse(
            success=False,
            message="No fields provided for update, please specify at least one field.",
        )

    response = client.patch_request(resource_name=f"order/{order_id}", payload=payload)

    if "errors" in response:
        return ToolResponse(success=False, message=response["errors"][0].get("ErrorDescription"))

    update_order_response = OMSUpdateOrderResponse(
        order_id=response.get("id", ""),
        order_number=response.get("OrderNo", ""),
    )

    return ToolResponse(
        success=True, message="Order was updated successfully.", content=update_order_response
    )

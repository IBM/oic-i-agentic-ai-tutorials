from typing import Optional

from ibm_watsonx_orchestrate.agent_builder.tools import tool

from agent_ready_tools.clients.sterling_oms_client import get_sterling_oms_client
from agent_ready_tools.tools.procurement.common_dataclasses import ToolResponse
from agent_ready_tools.tools.supply_chain.ibm_sterling_oms.order_management.common_dataclasses import (
    OMSOrderHeader,
    get_order_list_body_from_template,
)
from agent_ready_tools.utils.date_conversion import iso_8601_datetime_convert_to_date
from agent_ready_tools.utils.tool_credentials import STERLING_OMS_CONNECTIONS


@tool(expected_credentials=STERLING_OMS_CONNECTIONS)
def sterling_oms_get_orders(
    buyer_organization_code: Optional[str] = None,
    order_number: Optional[str] = None,
    enterprise_code: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    status: Optional[str] = None,
    limit: Optional[int] = 10,
    skip: Optional[int] = 0,
) -> ToolResponse[list[OMSOrderHeader]]:
    """
    Retrieves a list of orders.

    Args:
        buyer_organization_code: Buyer Organization Code (e.g. Sterling)
        order_number: The number of the order
        enterprise_code: The enterprise code of the buyer
        from_date: Beginning date to query from in ISO-8601 format (YYYY-MM-DD)
        to_date: End date to query to in ISO-8601 format (YYYY-MM-DD)
        status: Status of Order (e.g. Backordered, Created, Cancelled, etc.)
        limit: Number of entries to show
        skip: Offset of entries to skip

    Returns:
        The retrieved orders.
    """
    try:
        client = get_sterling_oms_client()
    except (ValueError, AssertionError):
        return ToolResponse(success=False, message="Failure to retrieve credentials")

    payload = get_order_list_body_from_template(
        buyer_organization_code,
        order_number,
        enterprise_code,
        from_date,
        to_date,
        status,
        limit,
        skip,
    )

    response = client.post_request(resource_name="invoke/getPage", payload=payload)
    if "errorMessage" in response:
        return ToolResponse(success=False, message=response["errorMessage"])

    order_list = response.get("Output", {}).get("OrderList", {}).get("Order", [])

    order_header_list = []
    for order in order_list:
        order_header_list.append(
            OMSOrderHeader(
                order_number=order.get("OrderNo", ""),
                order_status=order.get("Status", ""),
                buyer_organization=order.get("BuyerOrganizationCode"),
                enterprise=order.get("EnterpriseCode", ""),
                order_date=iso_8601_datetime_convert_to_date(order.get("OrderDate", "")),
                total_amount=f"{order.get("PriceInfo", {}).get("TotalAmount", "0.00")} {order.get("PriceInfo", {}).get("Currency", "")}",
                hold_status=order.get("HoldFlag", ""),
                order_id=order.get("OrderHeaderKey", ""),
                city_name=order.get("PersonInfoShipTo", {}).get("City", ""),
                zip_code=order.get("PersonInfoShipTo", {}).get("ZipCode", ""),
                # address= order.get("PersonInfoShipTo",{}).get("AddressLine1","")
            )
        )

    if len(order_header_list) == 0:
        return ToolResponse(success=False, message="No orders were found")

    return ToolResponse(
        success=True,
        message=f"{len(order_header_list)} orders retrieved successfully.",
        content=order_header_list,
    )

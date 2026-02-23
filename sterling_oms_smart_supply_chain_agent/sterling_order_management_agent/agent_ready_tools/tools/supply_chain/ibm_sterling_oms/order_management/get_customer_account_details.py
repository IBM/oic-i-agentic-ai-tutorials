from typing import List, Optional

from ibm_watsonx_orchestrate.agent_builder.tools import tool

from agent_ready_tools.clients.sterling_oms_client import get_sterling_oms_client
from agent_ready_tools.tools.procurement.common_dataclasses import ToolResponse
from agent_ready_tools.tools.supply_chain.ibm_sterling_oms.order_management.common_dataclasses import (
    OMSCustomerAccount,
    get_customer_account_details_body_from_template,
)
from agent_ready_tools.utils.tool_credentials import STERLING_OMS_CONNECTIONS


@tool(expected_credentials=STERLING_OMS_CONNECTIONS)
def sterling_oms_get_customer_account_details(
    buyer_organization_code: Optional[str] = None,
    organization_code: Optional[str] = None,
    customer_id: Optional[str] = None,
    limit: Optional[int] = 10,
    skip: Optional[int] = 0,
) -> ToolResponse[List[OMSCustomerAccount]]:
    """
    Retrieves customer account details.

    Args:
        buyer_organization_code: The organization code of the buyer.
        organization_code: The organization code of the Account Manager.
        customer_id: The identifier of the customer.
        limit: Number of customer records to be returned.
        skip: Number of records to skip for pagination.

    Returns:
        The details of the customer account.
    """

    try:
        client = get_sterling_oms_client()
    except (ValueError, AssertionError):
        return ToolResponse(success=False, message="Failure to retrieve credentials")

    payload = get_customer_account_details_body_from_template(
        buyer_organization_code, organization_code, customer_id, limit, skip
    )

    response = client.post_request(resource_name="invoke/getPage", payload=payload)

    if "errors" in response:
        return ToolResponse(success=False, message=response["errors"][0].get("ErrorDescription"))

    if not response.get("Output", {}).get("CustomerList", {}).get("Customer"):
        return ToolResponse(success=False, message="No customer account details were found")

    result = []
    details = response.get("Output", {}).get("CustomerList", {}).get("Customer", [])

    for item in details:
        result.append(
            OMSCustomerAccount(
                customer_id=item.get("CustomerID", ""),
                customer_classification_code=item.get("CustomerClassificationCode", ""),
                buyer_organization_code=item.get("BuyerOrganizationCode", ""),
                customer_type=item.get("CustomerType", ""),
            )
        )

    return ToolResponse(
        success=True, message="Retrieved customer account details successfully.", content=result
    )

from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission
import json


@tool(
    name="update_billing_address",
    description="Update the billing address for a credit card account using the credit card number.",
    permission=ToolPermission.ADMIN
)
def update_billing_address(credit_card_number: str, billing_address: str) -> str:
    """
    Update the billing address for a credit card account.
    
    This is a dummy implementation that simulates updating a billing address.
    In production, this would connect to a payment processing system or database.
    
    :param credit_card_number: The credit card number to identify the account
    :param billing_address: The new billing address to set
    :return: Success message as JSON string
    """
    # Validate inputs
    if not credit_card_number or not credit_card_number.strip():
        return json.dumps({"error": "Credit card number is required"})
    
    if not billing_address or not billing_address.strip():
        return json.dumps({"error": "Billing address is required"})
    
    # Simulate successful update
    result = {
        "status": "success",
        "message": "Credit card updated",
        "credit_card_number": credit_card_number,
        "billing_address": billing_address,
        "timestamp": "2026-01-25T19:17:00Z"
    }
    
    return json.dumps(result)

# Made with Bob

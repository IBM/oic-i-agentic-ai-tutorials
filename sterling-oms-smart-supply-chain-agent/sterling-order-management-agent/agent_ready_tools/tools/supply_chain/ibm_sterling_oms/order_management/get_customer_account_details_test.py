from unittest.mock import MagicMock, patch

from agent_ready_tools.tools.supply_chain.ibm_sterling_oms.order_management.common_dataclasses import (
    get_customer_account_details_body_from_template,
)
from agent_ready_tools.tools.supply_chain.ibm_sterling_oms.order_management.get_customer_account_details import (
    sterling_oms_get_customer_account_details,
)


def test_get_customer_account_details() -> None:
    """Test customer account details retrieval using a mock client."""

    test_data = {
        "buyer_organization_code": "ORG_001",
        "organization_code": "ORG_002",
        "customer_id": "CUST_12345",
        "limit": 10,
        "skip": 0,
        "customer_classification_code": "Retail",
        "customer_type": "01",
    }

    output_response = {
        "Output": {
            "CustomerList": {
                "Customer": [
                    {
                        "CustomerID": test_data["customer_id"],
                        "CustomerClassificationCode": test_data["customer_classification_code"],
                        "BuyerOrganizationCode": test_data["buyer_organization_code"],
                        "CustomerType": test_data["customer_type"],
                    }
                ]
            }
        }
    }

    with patch(
        "agent_ready_tools.tools.supply_chain.ibm_sterling_oms.order_management.get_customer_account_details.get_sterling_oms_client"
    ) as mock_client_factory:
        mock_client = MagicMock()
        mock_client_factory.return_value = mock_client
        mock_client.post_request.return_value = output_response

        response = sterling_oms_get_customer_account_details(
            buyer_organization_code=test_data["buyer_organization_code"],
            organization_code=test_data["organization_code"],
            limit=test_data["limit"],
            skip=test_data["skip"],
        ).content

        assert response
        assert response[0].customer_id == test_data["customer_id"]
        assert response[0].customer_type == test_data["customer_type"]

        mock_client.post_request.assert_called_once_with(
            resource_name="invoke/getPage",
            payload=get_customer_account_details_body_from_template(
                buyer_organization_code=str(test_data["buyer_organization_code"]),
                organization_code=str(test_data["organization_code"]),
            ),
        )

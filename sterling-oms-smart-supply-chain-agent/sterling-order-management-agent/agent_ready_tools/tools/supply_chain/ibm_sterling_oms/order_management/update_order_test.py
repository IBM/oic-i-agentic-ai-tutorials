from unittest.mock import MagicMock, patch

from agent_ready_tools.tools.supply_chain.ibm_sterling_oms.order_management.update_order import (
    sterling_oms_update_order,
)


def test_sterling_oms_update_order() -> None:
    """Test the updation of an order using a mock client."""

    test_data = {
        "order_id": "20250422204015344248",
        "vendor_id": "43534569",
        "customer_po_number": "3455",
        "committed_date": "2025-10-27",
        "expected_date": "2025-10-27",
        "order_number": "Y100000210",
    }

    output_response = {
        "OrderNo": test_data["order_number"],
        "id": test_data["order_id"],
    }

    test_payload = {
        "VendorID": test_data["vendor_id"],
        "CustomerPONo": test_data["customer_po_number"],
        "OrderDates": {
            "OrderDate": [
                {
                    "CommittedDate": test_data["committed_date"],
                    "ExpectedDate": test_data["expected_date"],
                }
            ]
        },
    }

    with patch(
        "agent_ready_tools.tools.supply_chain.ibm_sterling_oms.order_management.update_order.get_sterling_oms_client"
    ) as mock_client_factory:
        mock_client = MagicMock()
        mock_client_factory.return_value = mock_client
        mock_client.patch_request.return_value = output_response

        response = sterling_oms_update_order(
            order_id=test_data["order_id"],
            vendor_id=test_data["vendor_id"],
            committed_date=test_data["committed_date"],
            expected_date=test_data["expected_date"],
            customer_po_number=test_data["customer_po_number"],
        ).content

        assert response
        assert response.order_id == test_data["order_id"]
        assert response.order_number == test_data["order_number"]

        mock_client.patch_request.assert_called_once_with(
            resource_name=f"order/{test_data["order_id"]}", payload=test_payload
        )

from unittest.mock import MagicMock, patch

from agent_ready_tools.tools.supply_chain.ibm_sterling_oms.order_management.common_dataclasses import (
    get_order_list_body_from_template,
)
from agent_ready_tools.tools.supply_chain.ibm_sterling_oms.order_management.get_orders import (
    sterling_oms_get_orders,
)

TEST_ORDERS = {
    "Output": {
        "OrderList": {
            "LastOrderHeaderKey": "202508210735165187483",
            "LastRecordSet": "Y",
            "Order": [
                {
                    "BillToID": "100000258",
                    "DocumentType": "0001",
                    "EnterpriseCode": "Aurora",
                    "HoldFlag": "N",
                    "OrderDate": "2025-08-22T23:01:31+00:00",
                    "OrderHeaderKey": "202508222301045249801",
                    "OrderNo": "Y100001089",
                    "PriceInfo": {"Currency": "USD", "TotalAmount": "249.00"},
                    "Status": "Shipped",
                },
                {
                    "DocumentType": "0001",
                    "EnterpriseCode": "Quickkart",
                    "HoldFlag": "N",
                    "OrderDate": "2025-08-22T09:43:27+00:00",
                    "OrderHeaderKey": "202508220943275232794",
                    "OrderNo": "Y100001085",
                    "PriceInfo": {"Currency": "EUR", "TotalAmount": "77.00"},
                    "Status": "Carried",
                },
                {
                    "BillToID": "CUST_1000002",
                    "DocumentType": "0001",
                    "EnterpriseCode": "Quickkart",
                    "HoldFlag": "N",
                    "OrderDate": "2025-08-22T09:39:41+00:00",
                    "OrderHeaderKey": "202508220939415232446",
                    "OrderNo": "Y100001084",
                    "PriceInfo": {"Currency": "EUR", "TotalAmount": "154.00"},
                    "Status": "Created",
                },
            ],
        }
    }
}


def test_get_orders() -> None:
    """Test get item supplies using a mock client."""

    with patch(
        "agent_ready_tools.tools.supply_chain.ibm_sterling_oms.order_management.get_orders.get_sterling_oms_client"
    ) as mock_coupa_client:
        mock_client = MagicMock()
        mock_coupa_client.return_value = mock_client
        mock_client.post_request.return_value = TEST_ORDERS

        response = sterling_oms_get_orders().content

        assert response[0].order_number == "Y100001089"

        mock_client.post_request.assert_called_once_with(
            resource_name="invoke/getPage", payload=get_order_list_body_from_template()
        )

from unittest.mock import MagicMock, patch

from agent_ready_tools.tools.supply_chain.ibm_sterling_oms.order_management.common_dataclasses import (
    get_order_details_body_from_template,
)
from agent_ready_tools.tools.supply_chain.ibm_sterling_oms.order_management.get_order_details import (
    sterling_oms_get_order_details,
)

TEST_ORDER = {
    "Output": {
        "Order": {
            "Status": "Shipped",
            "OrderLines": {
                "OrderLine": [
                    {
                        "ItemDetails": {"UnitOfMeasure": "EACH", "ItemID": "MS-5001"},
                        "SegmentType": "B2B Accounts",
                        "Segment": "Platinum",
                    }
                ]
            },
            "BuyerOrganizationCode": "Steelix",
            "DocumentType": "0001",
            "ReqShipDate": "2025-05-06T00:00:00+00:00",
            "OrderNo": "ContractOrd04_SO1",
            "BillToID": "CUST_1000889",
            "OrderHeaderKey": "ContractOrd04_SO1",
            "HoldFlag": "N",
            "PriceInfo": {"Currency": "USD", "TotalAmount": "50000.00"},
            "OrderDate": "2025-05-06T00:00:00+00:00",
            "OrderDates": {
                "OrderDate": [
                    {"ExpectedDate": "2025-05-02T00:00:00+00:00"},
                    {"ExpectedDate": "2025-05-02T00:00:00+00:00"},
                    {"ExpectedDate": "2025-05-02T00:00:00+00:00"},
                    {"ExpectedDate": "2025-05-02T00:00:00+00:00"},
                ]
            },
            "Notes": {
                "Note": [
                    {
                        "NoteText": "Order #Y100000331 is backordered as an inbound shipment for item FST-3001 is delayed from supplier Acme to Woodland_DC",
                        "ReasonCode": "YCD_BACKORDER_INFO",
                    }
                ]
            },
        }
    },
}


def test_get_orders() -> None:
    """Test get item supplies using a mock client."""

    test_order = {"order_id": "Y100000331", "order_header_key": "ContractOrd04_SO1"}

    with patch(
        "agent_ready_tools.tools.supply_chain.ibm_sterling_oms.order_management.get_order_details.get_sterling_oms_client"
    ) as mock_coupa_client:
        mock_client = MagicMock()
        mock_coupa_client.return_value = mock_client
        mock_client.post_request.return_value = TEST_ORDER

        response = sterling_oms_get_order_details(
            test_order["order_id"], test_order["order_header_key"]
        ).content

        assert response

        mock_client.post_request.assert_called_once_with(
            resource_name="/invoke/getPage",
            payload=get_order_details_body_from_template(
                test_order["order_id"], test_order["order_header_key"]
            ),
        )

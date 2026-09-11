from enum import Enum
from typing import Any, Dict, Optional

from pydantic.dataclasses import dataclass

# from invoke/getStatusList, querying requires the specific status code so storing a dict of common codes here
STATUS_DESC_TO_CODE = {
    "Draft Order Created": "1000",
    "Awaiting Validation": "1000.100",
    "Validaiton Successful": "1000.100.10",
    "Validaiton Failed": "1000.100.20",
    "Print Job Configured": "1000.200",
    "Shipment Packaged": "1000.300",
    "Clinic Appointment Requested": "1000.400",
    "In Check Out": "1000.90",
    "Resume from Suspend": "1000.90.20",
    "Draft Order Reserved Awaiting Acceptance": "1040",
    "Draft Order Reserved": "1050",
    "Created": "1100",
    "Created (Awaiting Fulfillment)": "1100.005",
    "E GiftCard Delivered": "1100.01",
    "Acknowledged": "1100.010",
    "Suspended (Awaiting Input)": "1100.015",
    "Suspended (Awaiting Validation)": "1100.016",
    "Running": "1100.020",
    "Suspended": "1100.030",
    "Completed": "1100.040",
    "Aborted": "1100.090",
    "Synched": "1100.100",
    "Print Job Queued": "1100.200",
    "Shipment Staged for Driver": "1100.300",
    "Clinic Appointment Confirmed": "1100.400",
    "Carried": "1100.7777",
    "Totaled Out": "1100.90",
    "Tendered Out": "1100.90.10",
    "Reserved Awaiting Acceptance": "1140",
    "Reserved": "1200",
    "Being Negotiated": "1230",
    "Accepted": "1260",
    "Backordered": "1300",
    "Unscheduled": "1310",
    "Backordered From Node": "1400",
    "Scheduled": "1500",
    "Awaiting Chained Order Creation": "1600",
    "Awaiting Procurement Purchase Order Creation": "2030",
    "Awaiting Procurement Transfer Order Creation": "2060",
    "Chained Order Created": "2100",
    "Drop Ship Created": "2100.100",
    "Mirakl Order Created": "2100.M",
    "Procurement Purchase Order Created": "2130",
    "Procurement Purchase Order Shipped": "2130.01",
    "Procurement PO Received": "2130.70.06.10",
    "Work Order Created": "2140",
    "Work Order Completed": "2141",
    "Procurement Transfer Order Created": "2160",
    "Procurement Transfer Order Shipped": "2160.01",
    "Procurement TO Received": "2160.70.06.10",
    "Released": "3200",
    "Awaiting Shipment Consolidation": "3200.01",
    "Awaiting WMS Interface": "3200.02",
    "Sent To Node": "3300",
    "Included In Shipment": "3350",
    "Sent To Store": "3350.10",
    "At Store Awaiting Customer Pickup": "3350.10.10",
    "At Store Awaiting Packing and Shipping": "3350.10.20",
    "Awaiting Warranty Activation": "3350.100",
    "Warranty Activation Sucessful": "3350.100.10",
    "Warranty Activation Failed": "3350.100.20",
    "Ready for Customer": "3350.20",
    "Packed for Customer": "3350.30",
    "Shipped": "3700",
    "Return Created": "3700.01",
    "Return Received": "3700.02",
    "Gift Card Delivered": "3700.100",
    "Order Lost In Transit": "3700.1200",
    "Package Shipped": "3700.200",
    "Picked Up": "3700.30",
    "Order In Transit": "3700.3001",
    "Order Delayed": "3700.333",
    "Order Delivery Failed": "3700.500",
    "Order Refused By Customer": "3700.600",
    "Order At Store": "3700.700",
    "Order Delivered": "3700.7777",
    "Unreceived": "3780",
    "Received": "3900",
    "Receipt Closed": "3950",
    "Held": "8000",
    "Shipment Delayed": "8500",
    "Cancelled": "9000",
}


def display_error_from_response(response: Dict[str, Any]) -> str:
    """Parse the error response into a user friendly format."""
    return str(response["errors"])


# TODO: refactor into PascalCase dataclasses that can be serialized into the same format as this payload
def get_order_details_body_from_template(
    order_number: str, order_header_key: str, enterprise_code: Optional[str] = None
) -> Dict[str, Any]:
    """Generate post request payload based on order_number and order_header."""
    return {
        "PageNumber": 1,
        "PageSize": 10,
        "PaginationStrategy": "GENERIC",
        "Refresh": "N",
        "API": {
            "IsFlow": "N",
            "Name": "getOrderDetails",
            "Input": {
                "Order": {
                    "OrderNo": order_number if order_number is not None else "",
                    "OrderHeaderKey": order_header_key if order_header_key is not None else "",
                    "EnterpriseCode": enterprise_code if enterprise_code is not None else "",
                    "DocumentType": OrderDocumentType.SALES_ORDER,
                }
            },
            "Template": {
                "Order": {
                    "BillToID": "",
                    "VendorID": "",
                    "CustomerPONo": "",
                    "ContractID": "",
                    "BuyerOrganizationCode": "",
                    "DocumentType": "",
                    "OrderNo": "",
                    "OrderHeaderKey": "",
                    "HoldFlag": "",
                    "Status": "",
                    "ReqShipDate": "",
                    "ReqDeliveryDate": "",
                    "OrderDate": "",
                    "PriceInfo": {"Currency": "", "TotalAmount": ""},
                    "Notes": {"Note": {"ReasonCode": "", "NoteText": ""}},
                    "OrderDates": {"OrderDate": {"CommittedDate": "", "ExpectedDate": ""}},
                    "PersonInfoShipTo": {"City": "", "ZipCode": "", "AddressLine1": ""},
                    "OrderLines": {
                        "OrderLine": {
                            "Segment": "",
                            "SegmentType": "",
                            "ShipNode": "",
                            "ItemDetails": {"ItemID": "", "UnitOfMeasure": ""},
                        }
                    },
                }
            },
        },
        "PageSetToken": "",
    }


def get_order_list_body_from_template(
    buyer_organization_code: Optional[str] = None,
    order_number: Optional[str] = None,
    enterprise_code: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    status: Optional[str] = None,
    limit: Optional[int] = 0,
    skip: Optional[int] = 0,
) -> Dict[str, Any]:
    """Generate post request payload for get order list."""

    check_limit = int(limit) if limit and int(limit) > 0 else 10

    check_skip = int(skip) if skip and int(skip) >= 0 else 0

    page_number = (check_skip // check_limit) + 1

    return {
        "PageNumber": page_number,
        "PageSize": check_limit,
        "PaginationStrategy": "GENERIC",
        "Refresh": "N",
        "API": {
            "IsFlow": "N",
            "Name": "getOrderList",
            "Input": {
                "Order": {
                    "BuyerOrganizationCode": (
                        buyer_organization_code if buyer_organization_code is not None else ""
                    ),
                    "OrderNo": order_number if order_number is not None else "",
                    "EnterpriseCode": enterprise_code if enterprise_code is not None else "",
                    "DraftOrderFlag": "N",
                    "DocumentType": "0001",
                    "ReadFromHistory": "N",
                    "FromOrderDate": from_date if from_date is not None else "",
                    "ToOrderDate": to_date if to_date is not None else "",
                    "Status": STATUS_DESC_TO_CODE.get(status, "") if status is not None else "",
                    "OrderDateQryType": "BETWEEN",
                    "OrderBy": {"Attribute": {"Name": "OrderDate", "Desc": True}},
                }
            },
            "Template": {
                "OrderList": {
                    "TotalNumberOfRecords": "",
                    "Order": {
                        "OrderHeaderKey": "",
                        "OrderNo": "",
                        "OrderDate": "",
                        "Status": "",
                        "HoldFlag": "",
                        "BuyerOrganizationCode": "",
                        "EnterpriseCode": "",
                        "BillToID": "",
                        "DocumentType": "",
                        "ReqShipDate": "",
                        "ReqDeliveryDate": "",
                        "PriceInfo": {"Currency": "", "TotalAmount": ""},
                        "PersonInfoShipTo": {"City": "", "ZipCode": "", "AddressLine1": ""},
                    },
                }
            },
        },
        "PageSetToken": "",
    }


class OrderDocumentType(str, Enum):
    """The order document types."""

    SALES_ORDER = "0001"
    RETURN_ORDER = "0003"

    @classmethod
    def validate_document_type(cls, val: Optional[str]) -> Optional[str]:
        """
        Utility function to validate document types for the Enum, can be SALES_ORDER, RETURN_ORDER,
        0001, 0003, etc.

        Args:
            val: Document type value

        Returns:
            Proper value defined in the enum.
        """

        # if its None it's also fine
        if val is None:
            return None
        # can use SALES_ORDER
        if val in cls.__members__:
            return cls[val]
        try:  # can use 0001
            return cls(val)
        except ValueError:
            raise ValueError(
                f"Invalid order_type {val}. "
                f"Allowed: {list(cls.__members__.keys())} or {[e.value for e in cls]}"
            )


# TODO: refactor into PascalCase dataclasses that can be serialized into the same format as this payload
def get_customer_account_details_body_from_template(
    buyer_organization_code: Optional[str] = None,
    organization_code: Optional[str] = None,
    customer_id: Optional[str] = None,
    limit: Optional[int] = 10,
    skip: Optional[int] = 0,
) -> Dict[str, Any]:
    """Generate post request payload for customer account details."""

    check_limit = int(limit) if limit and int(limit) > 0 else 10

    check_skip = int(skip) if skip and int(skip) >= 0 else 0

    page_number = (check_skip // check_limit) + 1

    return {
        "PageNumber": page_number,
        "PageSize": check_limit,
        "PaginationStrategy": "GENERIC",
        "Refresh": "N",
        "API": {
            "IsFlow": "N",
            "Name": "getCustomerList",
            "Input": {
                "Order": {
                    "BuyerOrganizationCode": (
                        buyer_organization_code if buyer_organization_code is not None else ""
                    ),
                    "OrganizationCode": organization_code if organization_code is not None else "",
                    "CustomerID": customer_id if customer_id is not None else "",
                    "CustomerType": "01",
                }
            },
            "Template": {
                "CustomerList": {
                    "TotalNumberOfRecords": "",
                    "Customer": {
                        "CustomerID": "",
                        "BuyerOrganizationCode": "",
                        "CustomerType": "",
                        "CustomerClassificationCode": "",
                    },
                }
            },
        },
        "PageSetToken": "",
    }


@dataclass
class OMSOrderHeader:
    """Represents an order."""

    order_number: str
    order_status: str
    buyer_organization: Optional[str]
    enterprise: str
    order_date: str
    total_amount: str
    hold_status: str
    order_id: str
    city_name: str
    zip_code: str
    # AddressLine1 : Optional[str]


@dataclass
class OMSCustomerAccount:
    """Represents the details of a customer account."""

    customer_id: str
    customer_classification_code: Optional[str]
    buyer_organization_code: str
    customer_type: str


@dataclass
class OMSOrderLine:
    """Represents an order line."""

    item_id: str
    uom: str
    ship_node: Optional[str]
    segment: Optional[str]
    segment_type: Optional[str]


@dataclass
class OMSOrderDate:
    """Represents order dates."""

    committed_date: Optional[str]
    expected_date: Optional[str]


@dataclass
class OMSOrderNote:
    """Represents an order note."""

    note_text: str
    reason_code: Optional[str]


@dataclass
class OMSOrderDetails:
    """Represents an order."""

    order_id: str
    order_number: Optional[str]
    order_date: Optional[str]
    order_type: Optional[str]
    status: Optional[str]
    buyer_organization: Optional[str]
    requested_ship_date: Optional[str]
    requested_delivery_date: Optional[str]
    bill_to_id: Optional[str]
    total_amount: Optional[str]
    vendor_id: Optional[str]
    customer_po_number: Optional[str]
    city_name: Optional[str]
    zip_code: Optional[str]
    # AddressLine1 : Optional[str]
    order_lines: Optional[list[OMSOrderLine]]
    order_dates: Optional[list[OMSOrderDate]]
    order_notes: Optional[list[OMSOrderNote]]


@dataclass
class OMSUpdateOrderResponse:
    """Represents the response of updating an order."""

    order_id: str
    order_number: Optional[str]

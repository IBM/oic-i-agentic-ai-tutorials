from dataclasses import dataclass
from typing import Any, List

from agent_ready_tools.utils.api_response_processing_utils import (
    get_index_value,
    get_rest_value,
    get_soap_value,
)


@dataclass
class TestAccounts:
    """TestAccounts class defines a test object for testing nested SOAP responses."""

    __test__ = False
    accounts: List


@dataclass
class TestDataAccounts:
    """TestDataAccounts class defines a test object for testing nested SOAP responses."""

    __test__ = False
    data: TestAccounts


@dataclass
class TestBank:
    """TestBank class defines a test object for testing nested SOAP responses."""

    __test__ = False
    bank: TestDataAccounts


@dataclass
class TestDuplicate:
    """TestDuplicate class defines a test object for testing nested SOAP responses."""

    __test__ = False
    data: TestBank


@dataclass
class TestName:
    """TestName class defines a test object for testing nested SOAP responses."""

    __test__ = False
    first_name: str
    last_name: str


@dataclass
class TestResponseData:
    """TestResponseData class defines a test object for testing nested SOAP responses."""

    __test__ = False
    data: TestName


@dataclass
class TestSOAPResponse:
    """TestSOAPResponse class defines a test object for testing nested SOAP responses."""

    __test__ = False
    response: TestResponseData


@dataclass
class DepartmentData:
    """DepartmentData class defines a test object for testing nested SOAP responses."""

    name: str
    lead: str
    employees: List[str]


@dataclass
class LocationData:
    """LocationData class defines a test object for testing nested SOAP responses."""

    headquarters: str
    branches: List[str]


@dataclass
class MultiTree:
    """MultiTree class defines a test object for testing nested SOAP responses."""

    company_name: str
    location: LocationData
    departments: List[DepartmentData]


TEST_REST_RESPONSE = {"response": {"data": {"First Name": "Mark", "Last Name": "Anthony"}}}

TEST_REST_DUPlICATE_RESPONSE = {"data": {"bank": {"data": {"accounts": ["Chase", "Wells Fargo"]}}}}

TEST_REST_MULTI_TREE: dict[str, Any] = {
    "company_name": "TechCore Solutions Inc.",
    "location": {"headquarters": "San Francisco, CA", "branches": ["New York, NY"]},
    "departments": {
        "engineering": {
            "lead": "Test Manager 1",
            "employees": ["Daniel", "Sunaina", "Briana", "Aaron"],
        },
        "sales": {"lead": "Test Manager 2", "employees": ["Daniel", "Sunaina", "Briana", "Aaron"]},
        "human_resources": {
            "lead": "Test Manager 3",
            "employees": ["Daniel", "Sunaina", "Briana", "Aaron"],
        },
    },
    "metadata": {"created_at": "2025-10-08"},
}


def test_get_index_value() -> None:
    """
    Testing the happy path of the get_index_value() utility function.

    Making sure the function retrieves the value at a valid index from the input object.
    """

    result = get_index_value(
        input_obj=["test", "data"],
        default=None,
        index=0,
    )

    assert result == "test"
    assert result is not None


def test_get_index_value_invalid_index_val() -> None:
    """
    Testing the default return behavior of the get_index_value() utility function.

    Making sure the function returns the specified default return from the input object when an
    invalid index value is specified.
    """

    result = get_index_value(
        input_obj=["test", "data"],
        default=None,
        index=2,
    )

    assert result is None


def test_get_index_value_invalid_input_object() -> None:
    """
    Testing the default return behavior of the get_index_value() utility function.

    Making sure the function returns the specified default return from the input object when an
    invalid input object is specified.
    """

    result = get_index_value(
        input_obj=None,  # Non-indexable object
        default=None,
        index=2,
    )

    assert result is None


def test_get_rest_value_str_key() -> None:
    """Testing the behavior of the get_rest_value() utility function happy path of getting a single
    key that's inputted as a string, not a list."""

    result = get_rest_value(resp_obj=TEST_REST_RESPONSE, key_chain="response")

    assert result == TEST_REST_RESPONSE["response"]


def test_get_rest_value_invalid_str_key() -> None:
    """Testing the behavior of the get_rest_value() utility function when getting an invalid single
    key that's inputted as a string, not a list."""

    result = get_rest_value(resp_obj=TEST_REST_RESPONSE, key_chain="response1")

    assert result is None


def test_get_rest_value_parent_dict() -> None:
    """Testing the behavior of the get_rest_value() utility function happy path of getting a key
    from the parent dictionary."""

    result = get_rest_value(resp_obj=TEST_REST_RESPONSE, key_chain=["response"])

    assert result == TEST_REST_RESPONSE["response"]


def test_get_rest_value_middle_node() -> None:
    """Testing the behavior of the get_rest_value() utility function happy path of getting a key of
    a middle dictionary."""

    result = get_rest_value(resp_obj=TEST_REST_RESPONSE, key_chain=["response", "data"])

    assert result == TEST_REST_RESPONSE["response"]["data"]


def test_get_rest_value_nested_child_node() -> None:
    """Testing the behavior of the get_rest_value() utility function happy path of getting a key of
    a nested child dictionary."""

    result = get_rest_value(
        resp_obj=TEST_REST_RESPONSE, key_chain=["response", "data", "First Name"]
    )

    assert result == TEST_REST_RESPONSE["response"]["data"]["First Name"]


def test_get_rest_value_default_return() -> None:
    """Testing the behavior of the get_rest_value() utility function default return when a non
    existent key is asked for from the getter function."""

    result = get_rest_value(resp_obj=TEST_REST_RESPONSE, key_chain="key does not exist")

    assert result is None


def test_get_rest_value_nested_default_return() -> None:
    """Testing the behavior of the get_rest_value() utility function default return when a non
    existent key is asked for from a child dictionary."""

    result = get_rest_value(
        resp_obj=TEST_REST_RESPONSE, key_chain=["response", "key does not exist"]
    )

    assert result is None


def test_get_rest_value_duplicate_attrs() -> None:
    """Testing the behavior of the get_rest_value() utility function when there are duplicate keys
    in the chain of keys."""

    result = get_rest_value(
        resp_obj=TEST_REST_DUPlICATE_RESPONSE, key_chain=["data", "bank", "data", "accounts"]
    )
    assert result == TEST_REST_DUPlICATE_RESPONSE["data"]["bank"]["data"]["accounts"]

    result = get_rest_value(
        resp_obj=TEST_REST_DUPlICATE_RESPONSE, key_chain=["data", "bank", "data"]
    )
    assert result == TEST_REST_DUPlICATE_RESPONSE["data"]["bank"]["data"]

    result = get_rest_value(resp_obj=TEST_REST_DUPlICATE_RESPONSE, key_chain=["data", "bank"])
    assert result == TEST_REST_DUPlICATE_RESPONSE["data"]["bank"]

    result = get_rest_value(resp_obj=TEST_REST_DUPlICATE_RESPONSE, key_chain=["data"])
    assert result == TEST_REST_DUPlICATE_RESPONSE["data"]


def test_get_rest_value_complex_dict() -> None:
    """Testing the behavior of the get_rest_value() utility function with a complex multi child
    structure."""

    result = get_rest_value(resp_obj=TEST_REST_MULTI_TREE, key_chain=["location", "headquarters"])
    assert result == TEST_REST_MULTI_TREE["location"]["headquarters"]

    result = get_rest_value(
        resp_obj=TEST_REST_MULTI_TREE,
        key_chain=["departments", "engineering", "employees"],
    )
    assert result == TEST_REST_MULTI_TREE["departments"]["engineering"]["employees"]

    result = get_rest_value(
        resp_obj=TEST_REST_MULTI_TREE,
        key_chain=["departments", "engineering", "lead"],
    )
    assert result == TEST_REST_MULTI_TREE["departments"]["engineering"]["lead"]

    result = get_rest_value(
        resp_obj=TEST_REST_MULTI_TREE,
        key_chain=["departments", "sales", "employees"],
    )
    assert result == TEST_REST_MULTI_TREE["departments"]["sales"]["employees"]

    result = get_rest_value(
        resp_obj=TEST_REST_MULTI_TREE, key_chain=["departments", "sales", "lead"]
    )
    assert result == TEST_REST_MULTI_TREE["departments"]["sales"]["lead"]


def test_get_soap_value_parent_node() -> None:
    """Testing the behavior of the get_soap_value() utility function happy path of getting the
    parent node of the tree."""

    test_nested_name_object = TestName(first_name="Mark", last_name="Anthony")
    test_nested_response_object = TestResponseData(data=test_nested_name_object)
    test_nested_soap_object = TestSOAPResponse(response=test_nested_response_object)

    result = get_soap_value(resp_obj=test_nested_soap_object, key_chain="response")

    assert result == test_nested_soap_object.response


def test_get_soap_value_middle_node() -> None:
    """Testing the behavior of the get_soap_value() utility function happy path of getting one of
    the middle nodes the tree."""

    test_nested_name_object = TestName(first_name="Mark", last_name="Anthony")
    test_nested_response_object = TestResponseData(data=test_nested_name_object)
    test_nested_soap_object = TestSOAPResponse(response=test_nested_response_object)

    result = get_soap_value(resp_obj=test_nested_soap_object, key_chain="response.data")

    assert result == test_nested_soap_object.response.data


def test_get_soap_value_nested_child_node() -> None:
    """Testing the behavior of the get_soap_value() utility function happy path of getting one of
    the nested child nodes of the tree."""

    test_nested_name_object = TestName(first_name="Mark", last_name="Anthony")
    test_nested_response_object = TestResponseData(data=test_nested_name_object)
    test_nested_soap_object = TestSOAPResponse(response=test_nested_response_object)

    result = get_soap_value(resp_obj=test_nested_soap_object, key_chain="response.data.first_name")

    assert result == test_nested_soap_object.response.data.first_name


def test_get_soap_value_duplicate_attrs() -> None:
    """Testing the behavior of the get_soap_value() utility function when there are duplicate keys
    in the chain of keys."""

    test_accounts = TestAccounts(accounts=["Chase", "Wells Fargo"])
    test_data_accounts = TestDataAccounts(data=test_accounts)
    test_bank = TestBank(bank=test_data_accounts)
    test_duplicate = TestDuplicate(data=test_bank)

    result = get_soap_value(resp_obj=test_duplicate, key_chain="data.bank.data.accounts")
    assert result == test_duplicate.data.bank.data.accounts

    result = get_soap_value(resp_obj=test_duplicate, key_chain="data.bank.data")
    assert result == test_duplicate.data.bank.data

    result = get_soap_value(resp_obj=test_duplicate, key_chain="data.bank")
    assert result == test_duplicate.data.bank

    result = get_soap_value(resp_obj=test_duplicate, key_chain="data")
    assert result == test_duplicate.data


def test_get_soap_value_default_return() -> None:
    """Testing the behavior of the get_soap_value() utility function default return when a non
    existent attribute is asked for from the getter function."""

    test_nested_name_object = TestName(first_name="Mark", last_name="Anthony")
    test_nested_response_object = TestResponseData(data=test_nested_name_object)
    test_nested_soap_object = TestSOAPResponse(response=test_nested_response_object)

    result = get_soap_value(resp_obj=test_nested_soap_object, key_chain="attribute does not exist")

    assert result is None


def test_get_soap_value_nested_default_return() -> None:
    """Testing the behavior of the get_soap_value() utility function default return when a non
    existent child attribute is asked for from the getter function."""

    test_nested_name_object = TestName(first_name="Mark", last_name="Anthony")
    test_nested_response_object = TestResponseData(data=test_nested_name_object)
    test_nested_soap_object = TestSOAPResponse(response=test_nested_response_object)

    result = get_soap_value(
        resp_obj=test_nested_soap_object, key_chain="response.data.middle_name_attr_does_not_exist"
    )

    assert result is None


def test_get_soap_value_complex() -> None:
    """Testing the behavior of the get_soap_value() utility function with a complex multi child
    structure."""

    test_department_data = [
        DepartmentData(name="engineering", lead="Manager1", employees=["Daniel", "Sunaina"]),
        DepartmentData(name="sales", lead="Manager2", employees=["Daniel", "Sunaina"]),
    ]
    test_location_data = LocationData(
        headquarters="SF",
        branches=["NY"],
    )
    test_multi_tree = MultiTree(
        company_name="TechCore Solutions Inc.",
        location=test_location_data,
        departments=test_department_data,
    )

    result = get_soap_value(resp_obj=test_multi_tree, key_chain="location.headquarters")
    assert result == test_multi_tree.location.headquarters

    result = get_soap_value(
        resp_obj=test_multi_tree,
        key_chain="departments",
    )
    assert "engineering" == test_multi_tree.departments[0].name
    assert "sales" == test_multi_tree.departments[1].name

    result = get_soap_value(
        resp_obj=test_multi_tree,
        key_chain="departments",
    )
    assert "Manager1" == test_multi_tree.departments[0].lead
    assert "Manager2" == test_multi_tree.departments[1].lead

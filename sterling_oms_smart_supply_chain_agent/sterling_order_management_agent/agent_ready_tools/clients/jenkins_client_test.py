from http import HTTPMethod, HTTPStatus
from typing import Dict
from unittest.mock import MagicMock, patch

import requests
from requests import Response

from agent_ready_tools.clients.error_handling import ErrorDetails
from agent_ready_tools.clients.jenkins_client import JenkinsClient

TEST_DATA: Dict[str, str] = {
    "base_url": "https://jenkins.example.com",
    "username": "mock-user",
    "password": "mock-token",
}


def get_test_client(base_url: str, username: str, password: str) -> JenkinsClient:
    """
    Creates and returns a JenkinsClient instance using the provided base URL and credentials.

    Args:
        base_url (str): The base URL of the Jenkins API.
        username (str): Jenkins username.
        password (str): Jenkins API token.

    Returns:
        JenkinsClient: An initialized JenkinsClient object for testing purposes.
    """
    return JenkinsClient(base_url=base_url, username=username, password=password)


@patch("agent_ready_tools.clients.jenkins_client.requests.request")
def test_jenkins_client_get_request_success(mock_request: MagicMock) -> None:
    """
    Test that JenkinsClient successfully retrieves data via GET request.

    Verifies:
        - Response is a dictionary.
        - Contains expected 'status', 'result', and 'http_code'.
    """
    mock_response = MagicMock(spec=Response)
    mock_response.status_code = HTTPStatus.OK
    mock_response.json.return_value = {"job": "build-job"}
    mock_request.return_value = mock_response

    client = get_test_client(TEST_DATA["base_url"], TEST_DATA["username"], TEST_DATA["password"])
    response = client.get_request("api/json")

    expected_url = f"{TEST_DATA['base_url']}/api/json"
    mock_request.assert_called_once()
    _, kwargs = mock_request.call_args

    assert kwargs["method"] == HTTPMethod.GET
    assert kwargs["url"] == expected_url

    assert isinstance(response, dict)
    assert response["status"] == "success"
    assert response["http_code"] == HTTPStatus.OK


@patch("agent_ready_tools.clients.jenkins_client.requests.request")
def test_jenkins_client_post_request_success(mock_request: MagicMock) -> None:
    """
    Test that JenkinsClient successfully creates or triggers a resource via POST request.

    Verifies:
        - Response is a dictionary.
        - Contains expected keys and HTTP status code.
    """
    mock_response = MagicMock(spec=Response)
    mock_response.status_code = HTTPStatus.CREATED
    mock_response.json.return_value = {"created": True}
    mock_request.return_value = mock_response

    client = get_test_client(TEST_DATA["base_url"], TEST_DATA["username"], TEST_DATA["password"])
    payload = {"parameter": "value"}
    response = client.post_request("job/test/build", payload=payload)

    expected_url = f"{TEST_DATA['base_url']}/job/test/build"
    mock_request.assert_called_once()
    _, kwargs = mock_request.call_args

    assert kwargs["method"] == HTTPMethod.POST
    assert kwargs["url"] == expected_url
    assert kwargs["json"] == payload

    assert isinstance(response, dict)
    assert response["created"] is True
    assert response["http_code"] == HTTPStatus.CREATED


@patch("agent_ready_tools.clients.jenkins_client.requests.request")
def test_jenkins_client_put_request_success(mock_request: MagicMock) -> None:
    """
    Test that JenkinsClient successfully updates a resource via PUT request.

    Verifies:
        - Response is a dictionary.
        - Contains expected updated data and HTTP status code.
    """
    mock_response = MagicMock(spec=Response)
    mock_response.status_code = HTTPStatus.OK
    mock_response.json.return_value = {"updated": True}
    mock_request.return_value = mock_response

    client = get_test_client(TEST_DATA["base_url"], TEST_DATA["username"], TEST_DATA["password"])
    payload = {"config": "new-value"}
    response = client.put_request("job/test/config.xml", payload=payload)

    expected_url = f"{TEST_DATA['base_url']}/job/test/config.xml"
    mock_request.assert_called_once()
    _, kwargs = mock_request.call_args

    assert kwargs["method"] == HTTPMethod.PUT
    assert kwargs["url"] == expected_url
    assert kwargs["json"] == payload

    assert isinstance(response, dict)
    assert response["updated"] is True
    assert response["http_code"] == HTTPStatus.OK


@patch("agent_ready_tools.clients.jenkins_client.requests.request")
def test_jenkins_client_delete_request_success(mock_request: MagicMock) -> None:
    """
    Test that JenkinsClient successfully deletes a resource via DELETE request.

    Verifies:
        - Response is an integer representing HTTP status code.
    """
    mock_response = MagicMock(spec=Response)
    mock_response.status_code = HTTPStatus.NO_CONTENT
    mock_request.return_value = mock_response

    client = get_test_client(TEST_DATA["base_url"], TEST_DATA["username"], TEST_DATA["password"])
    response = client.delete_request("job/test")

    expected_url = f"{TEST_DATA['base_url']}/job/test"
    mock_request.assert_called_once()
    _, kwargs = mock_request.call_args

    assert kwargs["method"] == HTTPMethod.DELETE
    assert kwargs["url"] == expected_url

    assert response == HTTPStatus.NO_CONTENT


@patch("agent_ready_tools.clients.jenkins_client.requests.request")
def test_jenkins_client_get_request_error(mock_request: MagicMock) -> None:
    """
    Test that JenkinsClient handles errors during GET request.

    Simulates:
        - 404 Not Found error response.

    Verifies:
        - Response is an ErrorDetails object with correct status and reason.
    """
    mock_response = MagicMock(spec=requests.Response)
    mock_response.status_code = HTTPStatus.NOT_FOUND
    mock_response.json.return_value = {"message": "Job not found"}
    mock_response.url = f"{TEST_DATA['base_url']}/job/missing"
    mock_response.reason = "Not Found"
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError()

    mock_request.return_value = mock_response

    client = get_test_client(TEST_DATA["base_url"], TEST_DATA["username"], TEST_DATA["password"])
    response = client.get_request("job/missing")

    assert isinstance(response, ErrorDetails)
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.reason == "Not Found"
    assert response.url == mock_response.url
    assert "Job not found" in str(response.details)


@patch("agent_ready_tools.clients.jenkins_client.requests.request")
def test_jenkins_client_post_request_error(mock_request: MagicMock) -> None:
    """
    Test that JenkinsClient handles errors during POST request.

    Simulates:
        - 400 Bad Request error response.

    Verifies:
        - Response is an ErrorDetails object with correct status and reason.
    """
    mock_response = MagicMock(spec=Response)
    mock_response.status_code = HTTPStatus.BAD_REQUEST
    mock_response.json.return_value = {"message": "Invalid parameters"}
    mock_response.url = f"{TEST_DATA['base_url']}/job/test/build"
    mock_response.reason = "Bad Request"
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError()

    mock_request.return_value = mock_response

    client = get_test_client(TEST_DATA["base_url"], TEST_DATA["username"], TEST_DATA["password"])
    response = client.post_request("job/test/build", payload={"invalid": "data"})

    assert isinstance(response, ErrorDetails)
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.reason == "Bad Request"
    assert response.url == mock_response.url
    assert "Invalid parameters" in str(response.details)


@patch("agent_ready_tools.clients.jenkins_client.requests.request")
def test_jenkins_client_delete_request_error(mock_request: MagicMock) -> None:
    """
    Test that JenkinsClient handles errors during DELETE request.

    Simulates:
        - 403 Forbidden error response.

    Verifies:
        - Response is an ErrorDetails object with correct status and reason.
    """
    mock_response = MagicMock(spec=Response)
    mock_response.status_code = HTTPStatus.FORBIDDEN
    mock_response.json.return_value = {"message": "Access denied"}
    mock_response.url = f"{TEST_DATA['base_url']}/job/test"
    mock_response.reason = "Forbidden"
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError()

    mock_request.return_value = mock_response

    client = get_test_client(TEST_DATA["base_url"], TEST_DATA["username"], TEST_DATA["password"])
    response = client.delete_request("job/test")

    assert isinstance(response, ErrorDetails)
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.reason == "Forbidden"
    assert response.url == mock_response.url
    assert "Access denied" in str(response.details)

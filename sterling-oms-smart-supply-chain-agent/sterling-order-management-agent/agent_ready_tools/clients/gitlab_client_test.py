from http import HTTPMethod, HTTPStatus
from typing import Dict
from unittest.mock import MagicMock, patch

import requests
from requests import Response

from agent_ready_tools.clients.error_handling import ErrorDetails
from agent_ready_tools.clients.gitlab_client import GitLabClient

TEST_DATA: Dict[str, str] = {"base_url": "https://gitlab.com", "token": "mock-token"}

HEADERS = {"Authorization": f"Bearer {TEST_DATA['token']}", "Content-Type": "application/json"}


def get_test_client(base_url: str, token: str) -> GitLabClient:
    """
    Creates and returns a GitLabClient instance using the provided base URL and bearer token.

    Args:
        base_url (str): The base URL of the GitLab API.
        token (str): The bearer token used for authentication.

    Returns:
        GitLabClient: An initialized GitLabClient object for testing purposes.
    """
    return GitLabClient(base_url=base_url, bearer_token=token)


@patch("agent_ready_tools.clients.gitlab_client.requests.request")
def test_gitlab_client_get_request_success(mock_request: MagicMock) -> None:
    """
    Test that GitLabClient successfully retrieves data via GET request.

    Verifies:
        - Response is a dictionary.
        - Contains expected 'status', 'result', and 'http_code'.
    """
    mock_response = MagicMock(spec=Response)
    mock_response.status_code = HTTPStatus.OK
    mock_response.json.return_value = [{"id": 1, "name": "project1"}]
    mock_request.return_value = mock_response

    client = get_test_client(TEST_DATA["base_url"], TEST_DATA["token"])
    response = client.get_request("projects")

    expected_url = f"{TEST_DATA['base_url']}/api/v4/projects"
    mock_request.assert_called_once()
    _, kwargs = mock_request.call_args

    assert kwargs["method"] == HTTPMethod.GET
    assert kwargs["url"] == expected_url
    assert kwargs["headers"] == HEADERS

    assert isinstance(response, dict)
    assert response["status"] == "success"
    assert response["http_code"] == HTTPStatus.OK


@patch("agent_ready_tools.clients.gitlab_client.requests.request")
def test_gitlab_client_post_request_success(mock_request: MagicMock) -> None:
    """
    Test that GitLabClient successfully creates a resource via POST request.

    Verifies:
        - Response is a dictionary.
        - Contains expected resource ID and HTTP status code.
    """
    mock_response = MagicMock(spec=Response)
    mock_response.status_code = HTTPStatus.CREATED
    mock_response.json.return_value = {"id": 123}
    mock_request.return_value = mock_response

    client = get_test_client(TEST_DATA["base_url"], TEST_DATA["token"])
    payload = {"name": "test"}
    response = client.post_request("projects", payload=payload)

    expected_url = f"{TEST_DATA['base_url']}/api/v4/projects"
    mock_request.assert_called_once()
    _, kwargs = mock_request.call_args

    assert kwargs["method"] == HTTPMethod.POST
    assert kwargs["url"] == expected_url
    assert kwargs["headers"] == HEADERS
    assert kwargs["json"] == payload

    assert isinstance(response, dict)
    assert response["id"] == 123
    assert response["http_code"] == HTTPStatus.CREATED


@patch("agent_ready_tools.clients.gitlab_client.requests.request")
def test_gitlab_client_delete_request_success(mock_request: MagicMock) -> None:
    """
    Test that GitLabClient successfully deletes a resource via DELETE request.

    Verifies:
        - Response is an integer representing HTTP status code.
    """
    mock_response = MagicMock(spec=Response)
    mock_response.status_code = HTTPStatus.NO_CONTENT
    mock_request.return_value = mock_response

    client = get_test_client(TEST_DATA["base_url"], TEST_DATA["token"])
    response = client.delete_request("projects/123")

    expected_url = f"{TEST_DATA['base_url']}/api/v4/projects/123"
    mock_request.assert_called_once()
    _, kwargs = mock_request.call_args

    assert kwargs["method"] == HTTPMethod.DELETE
    assert kwargs["url"] == expected_url
    assert kwargs["headers"] == HEADERS

    assert response == HTTPStatus.NO_CONTENT


@patch("agent_ready_tools.clients.gitlab_client.requests.request")
def test_gitlab_client_get_request_error(mock_request: MagicMock) -> None:
    """
    Test that GitLabClient handles errors during GET request.

    Simulates:
        - 404 Not Found error response.

    Verifies:
        - Response is an ErrorDetails object with correct status and reason.
    """
    # Create a mock response simulating a 404 error
    mock_response = MagicMock(spec=requests.Response)
    mock_response.status_code = HTTPStatus.NOT_FOUND
    mock_response.json.return_value = {"message": "Not Found"}
    mock_response.url = f"{TEST_DATA['base_url']}/api/v4/invalid/endpoint"
    mock_response.reason = "Not Found"
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError()

    mock_request.return_value = mock_response

    client = get_test_client(TEST_DATA["base_url"], TEST_DATA["token"])
    response = client.get_request("invalid/endpoint")

    assert isinstance(response, ErrorDetails)
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.reason == "Not Found"
    assert response.url == mock_response.url
    assert "Not Found" in str(response.details)


@patch("agent_ready_tools.clients.gitlab_client.requests.request")
def test_gitlab_client_put_request_success(mock_request: MagicMock) -> None:
    """
    Test that GitLabClient successfully updates a resource via PUT request.

    Verifies:
        - Response is a dictionary.
        - Contains expected updated data and HTTP status code.
    """
    mock_response = MagicMock(spec=Response)
    mock_response.status_code = HTTPStatus.OK
    mock_response.json.return_value = {"updated": True}
    mock_request.return_value = mock_response

    client = get_test_client(TEST_DATA["base_url"], TEST_DATA["token"])
    payload = {"name": "updated-name"}
    response = client.put_request("projects/123", payload=payload)

    expected_url = f"{TEST_DATA['base_url']}/api/v4/projects/123"
    mock_request.assert_called_once()
    _, kwargs = mock_request.call_args

    assert kwargs["method"] == HTTPMethod.PUT
    assert kwargs["url"] == expected_url
    assert kwargs["headers"] == HEADERS
    assert kwargs["json"] == payload

    assert isinstance(response, dict)
    assert response["updated"] is True
    assert response["http_code"] == HTTPStatus.OK


@patch("agent_ready_tools.clients.gitlab_client.requests.request")
def test_gitlab_client_post_request_error(mock_request: MagicMock) -> None:
    """
    Test that GitLabClient handles errors during POST request.

    Simulates:
        - 400 Bad Request error response.

    Verifies:
        - Response is an ErrorDetails object with correct status and reason.
    """
    mock_response = MagicMock(spec=Response)
    mock_response.status_code = HTTPStatus.BAD_REQUEST
    mock_response.json.return_value = {"message": "Invalid payload"}
    mock_response.url = f"{TEST_DATA['base_url']}/api/v4/projects"
    mock_response.reason = "Bad Request"
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError()

    mock_request.return_value = mock_response

    client = get_test_client(TEST_DATA["base_url"], TEST_DATA["token"])
    response = client.post_request("projects", payload={"invalid": "data"})

    assert isinstance(response, ErrorDetails)
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert response.reason == "Bad Request"
    assert response.url == mock_response.url
    assert "Invalid payload" in str(response.details)


@patch("agent_ready_tools.clients.gitlab_client.requests.request")
def test_gitlab_client_delete_request_error(mock_request: MagicMock) -> None:
    """
    Test that GitLabClient handles errors during DELETE request.

    Simulates:
        - 403 Forbidden error response.

    Verifies:
        - Response is an ErrorDetails object with correct status and reason.
    """
    mock_response = MagicMock(spec=Response)
    mock_response.status_code = HTTPStatus.FORBIDDEN
    mock_response.json.return_value = {"message": "Access denied"}
    mock_response.url = f"{TEST_DATA['base_url']}/api/v4/projects/123"
    mock_response.reason = "Forbidden"
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError()

    mock_request.return_value = mock_response

    client = get_test_client(TEST_DATA["base_url"], TEST_DATA["token"])
    response = client.delete_request("projects/123")

    assert isinstance(response, ErrorDetails)
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert response.reason == "Forbidden"
    assert response.url == mock_response.url
    assert "Access denied" in str(response.details)

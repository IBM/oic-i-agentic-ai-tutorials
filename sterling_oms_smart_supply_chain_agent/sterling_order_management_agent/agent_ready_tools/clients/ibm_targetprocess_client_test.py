from typing import Any, Dict
from unittest.mock import MagicMock, patch

from agent_ready_tools.clients.error_handling import ErrorDetails
from agent_ready_tools.clients.ibm_targetprocess_client import IBMTargetProcessClient

# Sample test data
test_data: Dict[str, Any] = {
    "base_url": "https://your-domain.tpondemand.com",
    "access_token": "test_token",
    "entity": "UserStories",
    "payload": {"Name": "Test Story"},
    "params": {"take": 10},
}


@patch("agent_ready_tools.clients.ibm_targetprocess_client.requests.get")
def test_ibm_targetprocess_get_success(mock_get: MagicMock) -> None:
    """
    Test that the `IBM_Targetprocess` is working as expected. Test
    `IBMTargetprocessClient.get_request` with mocked `requests.get`.

    Args:
        mock_get: The mock for the requests.get function. We mock the `requests`
            library directly to allow for verification of the URL, headers, and
            parameters constructed by the client method.
    """
    mock_get.return_value = MagicMock()
    mock_get.return_value.raise_for_status = MagicMock()
    mock_get.return_value.json.return_value = {"Items": []}

    # Call the IBMTargetProcessClient client
    client = IBMTargetProcessClient(
        base_url=test_data["base_url"], access_token=test_data["access_token"]
    )
    # Call get_request function from IBMTargetProcessClient client
    response = client.get_request(entity=test_data["entity"], params=test_data["params"])
    assert response == {"Items": []}

    # Ensure the API call was made with expected parameters
    mock_get.assert_called_once_with(
        f"{client.base_url}/api/{client.version}/{test_data['entity']}?access_token={client.access_token}",
        headers={
            "Accept": "application/json",
        },
        params=test_data["params"],
    )


@patch("agent_ready_tools.clients.ibm_targetprocess_client.requests.post")
def test_ibm_targetprocess_post_success(mock_post: MagicMock) -> None:
    """
    Test that the `IBM_Targetprocess` is working as expected. Test
    `IBMTargetProcessClient.post_request` with mocked `requests.post`.

    Args:
        mock_post: The mock for the requests.post function. We mock the `requests`
            library directly to allow for verification of the URL, headers, and
            payload constructed by the client method.
    """
    mock_post.return_value = MagicMock()
    mock_post.return_value.raise_for_status = MagicMock()
    mock_post.return_value.json.return_value = {"Id": 123}

    # Call the IBMTargetProcessClient client
    client = IBMTargetProcessClient(
        base_url=test_data["base_url"], access_token=test_data["access_token"]
    )

    # Call post_request function from IBMTargetProcessClient client
    response = client.post_request(entity=test_data["entity"], payload=test_data["payload"])
    assert response == {"Id": 123}

    # Ensure the API call was made with expected parameters
    mock_post.assert_called_once_with(
        f"{client.base_url}/api/{client.version}/{test_data['entity']}?access_token={client.access_token}",
        json=test_data["payload"],
        headers={
            "Accept": "application/json",
        },
        params=None,
    )


@patch("agent_ready_tools.clients.ibm_targetprocess_client.requests.put")
def test_ibm_targetprocess_put_success(mock_put: MagicMock) -> None:
    """
    Test that the `IBM_Targetprocess` is working as expected. Test
    `IBMTargetProcessClient.put_request` with mocked `requests.put`.

    Args:
        mock_put: The mock for the requests.put function. We mock the `requests`
            library directly to allow for verification of the URL, headers, and
            payload constructed by the client method.
    """
    mock_put.return_value = MagicMock()
    mock_put.return_value.raise_for_status = MagicMock()
    mock_put.return_value.json.return_value = {"Updated": True}

    # Call the IBMTargetProcessClient client
    client = IBMTargetProcessClient(
        base_url=test_data["base_url"], access_token=test_data["access_token"]
    )

    # Call put_request function from IBMTargetProcessClient client
    response = client.put_request(entity=test_data["entity"], payload=test_data["payload"])
    assert response == {"Updated": True}

    # Ensure the API call was made with expected parameters
    mock_put.assert_called_once_with(
        f"{client.base_url}/api/{client.version}/{test_data['entity']}?access_token={client.access_token}",
        json=test_data["payload"],
        headers={
            "Accept": "application/json",
        },
        params=None,
    )


@patch("agent_ready_tools.clients.ibm_targetprocess_client.requests.delete")
def test_ibm_targetprocess_delete_success(mock_delete: MagicMock) -> None:
    """
    Test that the `IBM_Targetprocess` is working as expected. Test
    `IBMTargetProcessClient.delete_request` with mocked `requests.delete`.

    Args:
        mock_delete: The mock for the requests.delete function. We mock the
            `requests` library directly to allow for verification of the URL and
            headers constructed by the client method.
    """
    mock_delete.return_value = MagicMock()
    mock_delete.return_value.raise_for_status = MagicMock()
    mock_delete.return_value.json.return_value = {"Deleted": True}

    # Call the IBMTargetProcessClient client
    client = IBMTargetProcessClient(
        base_url=test_data["base_url"], access_token=test_data["access_token"]
    )

    # Call delete_request function from IBMTargetProcessClient client
    response = client.delete_request(entity=test_data["entity"])
    assert response == {"Deleted": True}

    # Ensure the API call was made with expected parameters
    mock_delete.assert_called_once_with(
        f"{client.base_url}/api/{client.version}/{test_data['entity']}?access_token={client.access_token}",
        headers={
            "Accept": "application/json",
        },
        params=None,
    )


@patch("agent_ready_tools.clients.ibm_targetprocess_client.requests.get")
def test_ibm_targetprocess_get_error(mock_get: MagicMock) -> None:
    """
    Test that the `IBMTargetprocessClient.get_request` handles errors correctly.

    Args:
        mock_get: The mock for the requests.get function. We mock the `requests`
            library directly to simulate an API error and verify that the client
            handles it by returning an ErrorDetails object.
    """
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = Exception("API Error")
    mock_response.status_code = 400
    mock_response.reason = "Bad Request"
    mock_response.url = f"{test_data['base_url']}/api/v1/{test_data['entity']}"
    mock_response.json.return_value = {"error": "Invalid parameter"}
    mock_get.return_value = mock_response

    client = IBMTargetProcessClient(
        base_url=test_data["base_url"], access_token=test_data["access_token"]
    )
    response = client.get_request(entity=test_data["entity"])

    assert isinstance(response, ErrorDetails)
    assert response.status_code == 400
    assert response.reason == "Bad Request"
    assert response.details == {"error": "Invalid parameter"}

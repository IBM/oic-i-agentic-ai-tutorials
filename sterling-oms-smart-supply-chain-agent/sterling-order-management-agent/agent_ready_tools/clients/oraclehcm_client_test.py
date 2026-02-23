from unittest.mock import MagicMock, patch

from agent_ready_tools.clients.oraclehcm_client import OracleHCMClient


@patch("agent_ready_tools.clients.oraclehcm_client.requests.get")
def test_oraclehcm_client(mock_get: MagicMock) -> None:
    """
    Test that the `OracleHCMClient` is working as expected. Test `OracleHCMClient.get_request` with
    mocked `requests.get`.

    Args:
        mock_client: The mock for the requests.get function
    """
    test_data = {"access_token": "NmUzYWM4MWYxMDAwMTZl", "entity": "test-entity"}

    # Create a mock instance for API requests
    mock_client = MagicMock()
    mock_client.json.return_value = {
        "access_token": test_data["access_token"],
        "items": [{"id": 1}],
    }
    mock_client.status_code = 200  # Ensure no HTTP error
    mock_client.raise_for_status = MagicMock()  # Prevent raising errors
    mock_get.return_value = mock_client  # Set the mock return value

    # Call the OracleHCMClient client
    client: OracleHCMClient = OracleHCMClient("", "", "")

    # Call get_request function from OracleHCMClient client
    response = client.get_request(entity=test_data["entity"])

    # Ensure that get_request() executed and returned proper values
    assert response
    if isinstance(response, dict):
        assert response["access_token"] == test_data["access_token"]
        mock_get.assert_called_once_with(
            url=f"{client.base_url}/hcmRestApi/resources/{client.version}/{test_data['entity']}",
            auth=client.auth,
            params={"links": "self"},
            headers={},
        )
    else:
        raise AssertionError(f"Expected dict, got {type(response)}: {response}")

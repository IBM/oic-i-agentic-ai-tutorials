from unittest.mock import MagicMock, patch

from agent_ready_tools.clients.oracle_fusion_client import OracleFusionClient


@patch("agent_ready_tools.clients.oracle_fusion_client.requests.get")
def test_oracle_fusion_client(mock_client: MagicMock) -> None:
    """
    Test that the `OracleFusionClient` is working as expected. Test `OracleFusionClient.get_request`
    with mocked `requests.get`.

    Args:
        mock_client: The mock for the requests.get function
    """

    # Define mock API response data
    test_data = {"access_token": "NmUzYWM4MWYxMDAwMTZl", "entity": "test-entity"}

    # Create a mock instance for API requests
    mock_client.return_value = MagicMock()
    mock_client.return_value.json.return_value = {"access_token": test_data["access_token"]}
    mock_client.return_value.status_code = 200  # Ensure no HTTP error
    mock_client.return_value.raise_for_status = MagicMock()  # Prevent raising errors

    # Call the OracleFUSIONClient client
    client: OracleFusionClient = OracleFusionClient("", "", "")

    # Call get_request function from OracleFUSIONClient client
    response = client.get_request(resource_name="suppliers")

    # Ensure that get_request() executed and returned proper values
    assert response

    # Ensure the API call was made with expected parameters
    mock_client.assert_called_once_with(
        url=f"{client.base_url}/fscmRestApi/resources/{client.version}/suppliers",
        headers={},
        params={},
        auth=client.auth,
    )

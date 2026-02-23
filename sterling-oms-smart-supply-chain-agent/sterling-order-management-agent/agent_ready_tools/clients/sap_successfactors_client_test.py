from unittest.mock import MagicMock, patch

from agent_ready_tools.clients.sap_successfactors_client import SAPSuccessFactorsClient


@patch("agent_ready_tools.clients.sap_successfactors_client.requests.get")
def test_sap_successfactors_client(mock_client: MagicMock) -> None:
    """
    Test that the `SAPSuccessFactorsClient` is working as expected. Test the
    `SAPSuccessFactorsClient.get_request` with mocked requests.get.

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

    # Call the SAPSuccessFactorsClient client
    client: SAPSuccessFactorsClient = SAPSuccessFactorsClient("", "", "")

    # Call get_request function from SAPSuccessFactorsClient client
    response = client.get_request(entity=test_data["entity"], is_no_data_an_error=False)

    # Ensure that get_request() executed and returned proper values
    assert response
    if isinstance(response, dict):
        assert response["access_token"] == test_data["access_token"]
    else:
        raise AssertionError(f"Expected dict response, got {type(response)}")

    # Ensure the API call was made with expected parameters
    mock_client.assert_called_once_with(
        url=f"{client.base_url}/odata/v2/{test_data['entity']}",
        auth=client.auth,
        params={"$format": "JSON"},
    )

from unittest.mock import MagicMock, patch

from agent_ready_tools.clients.sap_s4_hana_client import SAPS4HanaClient


@patch("agent_ready_tools.clients.sap_s4_hana_client.requests.get")
def test_sap_s4_hana_client(mock_client: MagicMock) -> None:
    """
    Test that the `SAPS4HanaClient` is working as expected. Test the `SAPS4HanaClient.get_request`
    with mocked requests.get.

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
    client: SAPS4HanaClient = SAPS4HanaClient("", "", "")

    # Call get_request function from SAPSuccessFactorsClient client
    response = client.get_request(entity=test_data["entity"])

    assert response
    assert response["response"]["access_token"] == test_data["access_token"]

    # Ensure the API call was made with expected parameters
    mock_client.assert_called_once_with(
        url=f"{client.base_url}/{test_data["entity"]}",
        params={"$format": "json"},
        auth=client.auth,
        headers={"x-csrf-token": "Fetch"},
    )

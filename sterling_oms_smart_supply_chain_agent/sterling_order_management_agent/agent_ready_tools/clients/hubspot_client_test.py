from unittest.mock import MagicMock, patch

from agent_ready_tools.clients.hubspot_client import HubSpotClient


@patch("requests.post")
def test_coupa_client(mock_post: MagicMock) -> None:
    """
    Test that the `HubSpotClient` is working as expected.

    Args:
        mock_post: The mock for the requests.post function
    """

    # Define mock API response data
    test_data = {"access_token": "NmUzYWM4MWYxMDAwMTZl"}

    # Create a mock instance for API requests
    mock_client = MagicMock()
    mock_client.json.return_value = test_data
    mock_client.status_code = 200
    mock_client.raise_for_status = MagicMock()  # Simulate successful request
    mock_post.return_value = mock_client  # Set the mock return value

    # Call the HubSpot client
    response: HubSpotClient = HubSpotClient("", "", "", "", "", "")

    # Ensure that HubSpotClient() executed and returned proper values
    assert response
    assert response.bearer_token == test_data["access_token"]

    # Ensure the API call was made with expected parameters
    mock_client.json.assert_called_once()

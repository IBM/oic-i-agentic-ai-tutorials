from unittest.mock import MagicMock, patch

from agent_ready_tools.clients.zoominfo_client import ZoominfoClient


@patch("requests.post")
def test_zoominfo_client(mock_post: MagicMock) -> None:
    """
    Test that the `ZoominfoClient` is working as expected.

    Args:
        mock_post: The mock for the requests.post function
    """

    # Define mock API response data
    test_data = {"jwt": "NmUzYWM4MWYxMDAwMTZl"}

    # Create a mock instance for API requests
    mock_client = MagicMock()
    mock_client.json.return_value = test_data
    mock_client.status_code = 200
    mock_client.raise_for_status = MagicMock()  # Simulate successful request
    mock_post.return_value = mock_client  # Set the mock return value

    # Call the Zoominfo client
    response: ZoominfoClient = ZoominfoClient("", "", "", "")

    # Ensure that ZoominfoClient() executed and returned proper values
    assert response
    assert response.access_token == test_data["jwt"]

    # Ensure the API call was made with expected parameters
    mock_client.json.assert_called_once()

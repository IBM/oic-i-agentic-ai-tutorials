from unittest.mock import MagicMock, patch

from agent_ready_tools.clients.salesloft_client import SalesloftClient


@patch("requests.post")
def test_salesloft_client(mock_post: MagicMock) -> None:
    """
    Test that the `SalesloftClient` is working as expected.

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

    # Call the Salesloft client
    response: SalesloftClient = SalesloftClient("", "", "", "")

    # Ensure that SalesloftClient() executed and returned proper values
    assert response
    assert response.bearer_token == test_data["access_token"]

    # Ensure the API call was made with expected parameters
    mock_client.json.assert_called_once()

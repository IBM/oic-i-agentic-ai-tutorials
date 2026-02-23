from unittest.mock import patch

from agent_ready_tools.clients.microsoft_client import MicrosoftClient


def test_microsoft_client() -> None:
    """Test that the `MicrosoftClient` is working as expected."""

    test_data = {"test_key": "test_val"}

    # Patch WorkdayAuthManager to mock its behavior
    with patch(
        "agent_ready_tools.clients.microsoft_client.MicrosoftClient.get_request"
    ) as mock_get_request:
        # Create a mock for the MicrosoftClient's instance
        mock_client = MicrosoftClient("", "")
        mock_get_request.return_value = test_data

        # Call get_request function from MicrosoftClient
        response = mock_client.get_request("test_endpoint")

        # Ensure that get_request() executed and returned proper values
        assert response == test_data

        # Ensure the MicrosoftClient API call was made with expected parameters
        mock_get_request.assert_called_once_with("test_endpoint")

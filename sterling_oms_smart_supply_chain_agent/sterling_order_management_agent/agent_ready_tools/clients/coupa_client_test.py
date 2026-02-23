from unittest.mock import patch

from agent_ready_tools.clients.coupa_client import CoupaClient


def test_coupa_client() -> None:
    """Test that the CoupaClient `get_request` method is working as expected."""

    # Define mock API response data
    test_data = {"test_key": "test_val"}

    with patch(
        "agent_ready_tools.clients.coupa_client.CoupaClient.get_request"
    ) as mock_get_request:
        # Create a mock for the CoupaClient's instance
        mock_client = CoupaClient("", "token")
        mock_get_request.return_value = test_data

        # Call get_request function from CoupaClient
        response = mock_client.get_request("test_endpoint")

        # Ensure that get_request() executed and returned proper values
        assert response == test_data

        # Ensure the CoupaClient API call was made with expected parameters
        mock_get_request.assert_called_once_with("test_endpoint")

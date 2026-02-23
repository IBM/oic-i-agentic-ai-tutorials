from unittest.mock import MagicMock, patch

from agent_ready_tools.clients.clients_enums import AccessLevel
from agent_ready_tools.clients.workday_client import WorkdayClient


def test_workday_client() -> None:
    """Test that the `WorkdayClient` is working as expected."""

    # Define mock API response data
    access_token = "NmUzYWM4MWYxMDAwMTZl"

    # Patch WorkdayAuthManager to mock its behavior
    with patch("agent_ready_tools.clients.workday_client.WorkdayAuthManager") as mock_auth_manager:
        # Create a mock for the WorkdayClient's instance
        mock_client = MagicMock()
        mock_client.get_bearer_token.return_value = access_token
        mock_auth_manager.return_value = mock_client

        # Create the WorkdayClient instance
        client: WorkdayClient = WorkdayClient("", "", "", "", "", "", "", AccessLevel.MANAGER)

        # Call get_bearer_token function from WorkdayClient client
        response = client.auth_manager.get_bearer_token()

        # Ensure that get_bearer_token() executed and returned proper values
        assert response == access_token

        # Ensure the WorkdayClient API call was made with expected parameters
        mock_client.get_bearer_token.assert_called_once_with()

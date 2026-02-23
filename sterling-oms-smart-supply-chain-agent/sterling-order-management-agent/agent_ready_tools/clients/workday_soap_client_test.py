from unittest.mock import MagicMock, patch

from agent_ready_tools.clients.workday_soap_client import WorkdaySOAPClient


def test_workday_soap_client() -> None:
    """Test that the `WorkdaySOAPClient` is working as expected."""

    # Define mock API response data
    access_token = "NmUzYWM4MWYxMDAwMTZl"

    # Patch WorkdayAuthManager to mock its behavior
    with patch(
        "agent_ready_tools.clients.workday_soap_client.WorkdayAuthManager"
    ) as mock_auth_manager:
        # Create a mock for the WorkdaySOAPClient's instance
        mock_client = MagicMock()
        mock_client.get_bearer_token.return_value = access_token
        mock_auth_manager.return_value = mock_client

        # Create the WorkdaySOAPClient instance
        client: WorkdaySOAPClient = WorkdaySOAPClient("", "", "", "", "", "", "")

        # Call get_bearer_token function from WorkdaySOAPClient client
        response = client.auth_manager.get_bearer_token()

        # Ensure that get_bearer_token() executed and returned proper values
        assert response == access_token

        # Ensure the WorkdaySOAPClient API call was made with expected parameters
        mock_client.get_bearer_token.assert_called_once_with()

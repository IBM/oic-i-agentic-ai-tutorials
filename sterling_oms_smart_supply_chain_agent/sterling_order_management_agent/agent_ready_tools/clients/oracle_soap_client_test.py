from unittest.mock import MagicMock, patch

from agent_ready_tools.clients.oracle_soap_client import OracleSOAPClient


def test_oracle_soap_client_auth() -> None:
    """Test that the `OracleSOAPClient` is working as expected."""

    # Define mock API response data
    test_data = {"username": "testuser"}

    with patch("agent_ready_tools.clients.oracle_soap_client.HTTPBasicAuth") as mock_auth:
        # Create a mock for the HTTPBasicAuth instance
        mock_auth_instance = MagicMock()
        mock_auth_instance.username = test_data["username"]
        mock_auth.return_value = mock_auth_instance

        # Create the OracleSOAPClient instance
        client = OracleSOAPClient("", "", "")

        # Call the OracleSOAPClient client
        response = client.auth.username

        assert response
        assert response == test_data["username"]

        # Ensure the OracleSOAPClient API call was made with expected parameters
        mock_auth.assert_called_once_with("", "")

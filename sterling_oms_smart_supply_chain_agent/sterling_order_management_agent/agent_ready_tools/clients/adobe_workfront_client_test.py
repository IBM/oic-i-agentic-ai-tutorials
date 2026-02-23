from unittest.mock import MagicMock, patch

from agent_ready_tools.clients.adobe_workfront_client import AdobeWorkfrontClient


def test_adobe_workfront_client() -> None:
    """Test that the `AdobeWorkfrontClient` is working as expected."""

    # Define mock API response data
    test_data = {"access_token": "ebd156f104824d1eb0611b5a1ef02b76"}

    # Patch AdobeWorkfrontAuthManager to mock its behavior
    with patch(
        "agent_ready_tools.clients.adobe_workfront_client.AdobeWorkfrontAuthManager"
    ) as mock_auth_manager:
        # Create a mock for the AdobeWorkfrontClient's instance
        mock_client = MagicMock()
        mock_client.get_bearer_token.return_value = test_data["access_token"]
        mock_auth_manager.return_value = mock_client

        # Create the AdobeWorkfrontClient instance
        client: AdobeWorkfrontClient = AdobeWorkfrontClient("", "", "", "", "", "")

        # Call get_bearer_token function from AdobeWorkfrontClient client

        response = client.auth_manager.get_bearer_token()

        # Ensure that get_bearer_token() executed and returned proper values

        assert response == test_data["access_token"]

        # Ensure the AdobeWorkfrontClient API call was made with expected parameters
        mock_client.get_bearer_token.assert_called_once_with()

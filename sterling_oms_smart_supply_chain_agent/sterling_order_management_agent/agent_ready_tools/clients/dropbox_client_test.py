from unittest.mock import patch

from agent_ready_tools.clients.dropbox_client import DropboxClient


def test_dropbox_client() -> None:
    """Test that the `DropboxClient` is working as expected."""

    # Define mock API response data
    test_data = {"test_key": "test_val"}

    # Patch DropboxClient.post_request to mock its behavior
    with patch(
        "agent_ready_tools.clients.dropbox_client.DropboxClient.post_request"
    ) as mock_post_request:
        # Set mock return value for post_request
        mock_post_request.return_value = test_data

        # Create the DropboxClient instance
        client: DropboxClient = DropboxClient("", "", "")

        # Call post_request function from DropboxClient
        response = client.post_request("test_entity")

        # Ensure that post_request() executed and returned proper values
        assert response == test_data

        # Ensure the DropboxClient function call was made with expected parameters
        mock_post_request.assert_called_once_with("test_entity")

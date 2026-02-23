from unittest.mock import patch

from agent_ready_tools.clients.box_client import BoxClient


def test_box_client() -> None:
    """Test that the `BoxClient` is working as expected."""

    # Define mock API response data
    test_data = {"test_key": "test_val"}

    # Patch BoxClient to mock its behavior
    with patch("agent_ready_tools.clients.box_client.BoxClient.post_request") as mock_post_request:
        # set mock return val for post_request fn
        mock_post_request.return_value = test_data

        # Create the BoxClient instance
        client: BoxClient = BoxClient("", "")

        # Call post_request function from BoxClient client
        response = client.post_request("test_entity")

        # Ensure that post_request() executed and returned proper values
        assert response == test_data

        # Ensure the BoxClient fn call was made with expected parameters
        mock_post_request.assert_called_once_with("test_entity")

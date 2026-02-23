from unittest.mock import MagicMock, patch

from agent_ready_tools.clients.google_client import GoogleClient


@patch("requests.post")
def test_google_client(mock_post: MagicMock) -> None:
    """
    Test that the `GoogleClient` is working as expected.

    Args:
        mock_post: The mock for the requests.post function
    """

    # Define mock API response data
    test_data = {
        "return_val": {"test_key": "test_val"},
        "entity": "test_entity",
        "service": "drive",
        "version": "v3",
    }

    # Create a mock instance for API requests
    mock_post.return_value = MagicMock()
    mock_post.return_value.status_code = 200  # Ensure correct status code
    mock_post.return_value.json.return_value = test_data["return_val"]  # Simulate JSON response
    mock_post.return_value.raise_for_status = MagicMock()  # Simulate success

    # Initialize the GoogleClient
    client: GoogleClient = GoogleClient("", "")

    # Ensure that GoogleClient() executed and returned proper values
    assert client
    resp = client.post_request(
        entity=test_data["entity"],  # type: ignore[arg-type]
        service=test_data["service"],  # type: ignore[arg-type]
        version=test_data["version"],  # type: ignore[arg-type]
    )
    assert resp
    assert resp == test_data["return_val"]
    # Ensure the API calls were made with expected parameters
    mock_post.assert_called_once_with(
        url=f"{client.base_url}/{test_data["service"]}/{test_data["version"]}/{test_data["entity"]}",
        headers=client.headers,
        json=None,
        data=None,
        params=None,
    )

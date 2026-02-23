import json
from unittest.mock import MagicMock, patch

from agent_ready_tools.clients.dnb_client import DNBClient


@patch("requests.post")
def test_dnb_client(mock_post: MagicMock) -> None:
    """
    Test that the `DNBClient` is working as expected.

    Args:
        mock_post: The mock for the requests.post function
    """

    # Define mock API response data
    test_data = {
        "data": {},
        "endpoint": "test_endpoint",
        "category": "test_category",
        "version": "v1",
    }

    # Create a mock instance for API requests
    mock_post.return_value = MagicMock()
    mock_post.return_value.status_code = 200  # Ensure correct status code
    mock_post.return_value.json.return_value = test_data  # Simulate JSON response
    mock_post.return_value.raise_for_status = MagicMock()  # Simulate success

    # Initialize the DNB client
    client: DNBClient = DNBClient("", "")

    # Ensure that DNBClient() executed and returned proper values
    assert client
    resp = client.post_request(
        endpoint=test_data["endpoint"],  # type: ignore[arg-type]
        category=test_data["category"],  # type: ignore[arg-type]
        data=test_data["data"],  # type: ignore[arg-type]
        version=test_data["version"],  # type: ignore[arg-type]
    )
    assert resp
    assert resp == test_data
    # Ensure the API calls were made with expected parameters
    mock_post.assert_called_once_with(
        url=f"{client.base_url}/{test_data["version"]}/{test_data["category"]}/{test_data["endpoint"]}",
        headers=client.headers,
        data=json.dumps(test_data["data"]),
    )

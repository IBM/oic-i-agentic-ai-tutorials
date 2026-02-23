from http import HTTPMethod
from unittest.mock import MagicMock, patch

from agent_ready_tools.clients.swagger_client import WxOSwaggerClient
from agent_ready_tools.utils.export_chat_response_data import threads_test_data


@patch("requests.request")
def test_client(mock_request: MagicMock) -> None:
    """Test that the pull_thread function returns the expected response."""

    # Define mock API response data
    test_data = {
        "url": "api/v1/threads",
        "json": threads_test_data,
        "token": "FAKE TOKEN",
    }

    # Create a mock instance for API requests
    mock_request.return_value = MagicMock()
    mock_request.return_value.status_code = 200  # Ensure correct status code
    mock_request.return_value.json.return_value = test_data["json"]  # Simulate JSON response
    mock_request.return_value.raise_for_status = MagicMock()  # Simulate success

    # Initialize the WxO Swagger Client
    client: WxOSwaggerClient = WxOSwaggerClient(
        bearer_token=test_data["token"]  # type: ignore[arg-type]
    )

    # Ensure that WxOSwaggerClient() executed and returned proper values
    assert client
    assert client.bearer_token == test_data["token"]

    resp = client.get_request(url_path=test_data["url"])  # type: ignore[arg-type]
    assert resp
    assert resp == test_data["json"]

    # Ensure requests.request was called with expected params
    mock_request.assert_called_once_with(
        HTTPMethod.GET, f"{client.base_url}/{test_data["url"]}", headers=client.headers
    )

import json
from unittest.mock import MagicMock, patch

from agent_ready_tools.clients.dynamics_365_client import Dynamics365Client


@patch("requests.post")
@patch("agent_ready_tools.clients.dynamics_365_client.Dynamics365Client")
def test_dynamics365_client(mock_d365: MagicMock, mock_post: MagicMock) -> None:
    """
    Test that the `dynamicsClient` is working as expected.

    Args:
        mock_d365: The mock for the Dynamics365C class
        mock_post: The mock for the requests.post function
    """

    # Define mock API response data
    test_data = {
        "data": {},
        "entity": "test_entity",
        "api_version": "v9.1",
    }

    # Create a mock instance for API requests
    mock_post.return_value = MagicMock()
    mock_post.return_value.status_code = 200  # Ensure correct status code
    mock_post.return_value.json.return_value = test_data  # Simulate JSON response
    mock_post.return_value.raise_for_status = MagicMock()  # Simulate success

    # Initialize the Dynamics365 client
    client: Dynamics365Client = Dynamics365Client("", "")

    # Ensure that Dynamics365() executed and returned proper values
    assert client
    resp = client.post_request(
        entity=test_data["entity"],  # type: ignore[arg-type]
        data=test_data["data"],  # type: ignore[arg-type]
        api_version=test_data["api_version"],  # type: ignore[arg-type]
    )
    assert resp
    assert resp == test_data
    # Ensure the API calls were made with expected parameters
    mock_post.assert_called_once_with(
        url=f"{client.base_url}/api/data/{test_data["api_version"]}/{test_data["entity"]}",
        headers=client.headers,
        data=json.dumps(test_data["data"]),
    )

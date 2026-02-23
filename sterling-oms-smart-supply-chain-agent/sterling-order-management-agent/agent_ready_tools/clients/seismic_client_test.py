from unittest.mock import MagicMock, patch

from agent_ready_tools.clients.seismic_client import SeismicClient


@patch("requests.post")
def test_seismic_client(mock_client: MagicMock) -> None:
    """
    Test that the `SeismicClient` is working as expected. Test `SeismicClient.post_request` with
    mocked requests.post.

    Args:
        mock_client: The mock for the requests.post function.
    """

    # Define mock API test data
    test_data = {
        "endpoint": "generative",
        "category": "search",
        "version": "v1",
    }
    api_response = {"result": "success"}

    # Create a mock instance for API requests
    mock_client.return_value = MagicMock()
    mock_client.return_value.json.return_value = api_response
    mock_client.return_value.status_code = 200
    mock_client.return_value.raise_for_status = MagicMock()

    # Call the SeismicClient client
    client = SeismicClient("", "")

    # Call post_request function from SeismicClient
    response = client.post_request(
        endpoint=test_data["endpoint"], category=test_data["category"], version=test_data["version"]
    )

    # Ensure that post_request() executed and returned proper values
    assert response == api_response

    # Ensure the API call was made with expected parameters
    mock_client.assert_called_with(
        url=f"{client.base_url}/{test_data['category']}/{test_data['version']}/{test_data['endpoint']}",
        headers=client.headers,
        json=None,
        params={"$format": "JSON"},
    )

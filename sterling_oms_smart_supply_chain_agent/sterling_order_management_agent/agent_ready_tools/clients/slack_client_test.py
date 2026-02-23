from unittest.mock import MagicMock, patch

from agent_ready_tools.clients.slack_client import SlackClient


@patch("agent_ready_tools.clients.slack_client.requests.get")
def test_slack_client(mock_client: MagicMock) -> None:
    """
    Test that the `SlackClient` is working as expected. Test `SlackClient.get_request` with mocked
    `requests.get`.

    Args:
        mock_client: The mock for the requests.get function
    """

    # Define mock API response data
    test_data = {"base_url": "https://slack.com/api", "token": "token", "entity": "users.list"}

    # Create a mock instance for API requests
    mock_client.return_value = MagicMock()
    mock_client.return_value.status_code = 200  # Ensure no HTTP error
    mock_client.return_value.raise_for_status = MagicMock()  # Prevent raising errors

    # Call the SlackClient client
    client: SlackClient = SlackClient(
        base_url=test_data["base_url"], bearer_token=test_data["token"]
    )

    # Call get_request function from SlackClient client
    response = client.get_request(entity=test_data["entity"])

    # Ensure that get_request() executed and returned proper values
    assert response

    # Ensure the API call was made with expected parameters
    mock_client.assert_called_once_with(
        url=f"{test_data["base_url"]}/users.list",
        headers={
            "Authorization": f"Bearer {test_data["token"]}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        params=None,
    )

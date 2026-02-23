from unittest.mock import MagicMock, patch

from agent_ready_tools.clients.jira_client import JiraClient


@patch("requests.get")
def test_jira_client(mock_get: MagicMock) -> None:
    """
    Test that the `JiraClient` is working as expected. Test `JiraClient.get_request` with mocked
    `requests.get`.

    Args:
         mock_get: The mock for the requests.get function
    """

    # Define mock response data
    test_init_data = [{"id": "NmUzYWM4MWYxMDAwMTZl"}]
    test_data = {"entity": "NmUzYWM4MWYxMDAwMTZl", "entity_data": "test_entity_data"}

    # Create a mock instance for API requests
    mock_get.return_value = MagicMock()
    mock_get.return_value.json.return_value = test_init_data
    mock_get.return_value.status_code = 200  # Ensure no HTTP error
    mock_get.return_value.raise_for_status = MagicMock()  # Prevent raising errors

    # Initialize the Jira client
    client: JiraClient = JiraClient("", "")
    # /oauth/token/accessible-resources called in client init
    mock_get.assert_called_once_with(
        url=f"{client.base_url}/oauth/token/accessible-resources",
        headers=client.headers,
    )

    # Mock GET response and call get_request function from Jira client
    mock_get.return_value.json.return_value = test_data
    response = client.get_request(entity=test_data["entity"])

    # Ensure that get_request() executed and returned proper values
    assert response
    assert response["entity_data"] == test_data["entity_data"]
    mock_get.assert_called_with(
        url=f"{client.base_url}/ex/jira/{client.cloud_id}/rest/api/{client.version}/{test_data["entity"]}",
        headers=client.headers,
        params=None,
    )

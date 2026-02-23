from unittest.mock import MagicMock, patch

from agent_ready_tools.clients.servicenow_client import ServiceNowClient


@patch("agent_ready_tools.clients.servicenow_client.requests.get")
def test_servicenow_client(mock_client: MagicMock) -> None:
    """
    Test that the `ServiceNowClient` is working as expected. Test `ServiceNowClient.get_request`
    with mocked requests.get.

    Args:
        mock_client: The mock for the requests.get function
    """

    # Define mock API response data
    test_data = {
        "entity": "test",
        "category": "search",
        "version": "v1",
    }

    # Create a mock instance for API requests
    mock_client.return_value = MagicMock()
    mock_client.return_value.status_code = 200  # Ensure no HTTP error
    mock_client.return_value.raise_for_status = MagicMock()  # Prevent raising errors

    # Call the ServiceNowClient client
    client: ServiceNowClient = ServiceNowClient("", "")

    # Call get_request function from ServiceNowClient client
    response = client.get_request(entity=test_data["entity"])

    # Ensure that get_request() executed and returned proper values
    assert response

    # Ensure the API call was made with expected parameters
    mock_client.assert_called_once_with(
        url=f"{client.base_url}/api/{client.path_url}/{test_data['entity']}",
        headers=client.headers,
        params={"sysparm_query": "ORDERBYDESCsys_updated_on"},
    )

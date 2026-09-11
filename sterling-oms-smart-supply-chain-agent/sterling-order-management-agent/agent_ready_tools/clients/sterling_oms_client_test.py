from unittest.mock import MagicMock, patch

from agent_ready_tools.clients.sterling_oms_client import SterlingOMSClient


@patch("agent_ready_tools.clients.sterling_oms_client.ClientSideCertificateHTTPAdapter")
@patch("agent_ready_tools.clients.sterling_oms_client.requests.Session.get")
@patch("agent_ready_tools.clients.sterling_oms_client.requests.Session.post")
def test_sterling_oms_client(
    mock_post: MagicMock,
    mock_get: MagicMock,
    mock_mem_adapter: MagicMock,
) -> None:
    """
    Test that the Sterling OMS is working as expected.

    Args:
        mock_post: The mock for the session.post function
        mock_get: The mock for the session.get function
        mock_mem_adapter: The mock for the in-memory adapter
    """

    # Define mock API response data
    test_data = {"test_key": "test_val"}
    test_endpoint = "invoke/getPage"
    test_payload = {
        "PageNumber": 1,
        "PageSize": 10,
        "PaginationStrategy": "GENERIC",
        "Refresh": "N",
        "API": {"IsFlow": "N", "Name": "getOrderDetails"},
    }

    # Create a mock instance for adapters
    mock_adapter_instance = MagicMock()
    mock_mem_adapter.return_value = mock_adapter_instance

    # Create a mock instance for API requests
    mock_session_post = MagicMock()
    mock_post.return_value = mock_session_post

    test_status_code_get = 200

    mock_session_get = MagicMock()
    mock_session_get.status_code = test_status_code_get
    mock_get.return_value = mock_session_get

    # Call the client
    client: SterlingOMSClient = SterlingOMSClient(
        base_url="https://host/api",
        username="user",
        password="pw",
        client_cert="dummy-cert",
        client_key="dummy-key",
    )
    with patch(
        "agent_ready_tools.clients.sterling_oms_client.SterlingOMSClient.post_request"
    ) as mock_post_request:
        # set mock return val for get_request fn
        mock_post_request.return_value = test_data

        response = client.post_request(resource_name=test_endpoint, payload=test_payload)

        # Ensure that SterlingOMSClient() executed and returned proper values
        assert response == test_data

        # Ensure the API call was made with expected parameters
        mock_post_request.assert_called_once_with(resource_name=test_endpoint, payload=test_payload)

    mock_get.assert_called_once()
    mock_post.assert_called_once()

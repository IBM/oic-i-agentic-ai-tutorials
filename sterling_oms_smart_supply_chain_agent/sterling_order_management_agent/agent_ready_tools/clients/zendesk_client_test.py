from http import HTTPStatus
from unittest.mock import MagicMock, patch

from agent_ready_tools.clients.zendesk_client import ZendeskClient


@patch("agent_ready_tools.clients.zendesk_client.requests.request")
def test_zendesk_client_post_request(mock_request: MagicMock) -> None:
    """Test that the ZendeskClient post_request works as expected."""

    # Mock API response data
    test_data = {"ticket": {"id": 123, "subject": "Test Ticket"}}

    # Configure the mock response
    mock_response = MagicMock()
    mock_response.json.return_value = test_data
    mock_response.status_code = HTTPStatus.OK
    mock_response.raise_for_status = MagicMock()
    mock_request.return_value = mock_response

    # Initialize Zendesk client
    client = ZendeskClient(base_url="https://example.zendesk.com", bearer_token="fake_token")

    # Call post_request
    payload = {"ticket": {"subject": "Test Ticket"}}
    response = client.post_request(entity="tickets", payload=payload)

    # Assertions
    assert isinstance(response, dict)
    assert response["status_code"] == HTTPStatus.OK
    assert response["ticket"]["id"] == 123

    # Ensure the underlying request was called correctly
    mock_request.assert_called_once_with(
        method="POST",
        url="https://example.zendesk.com/api/v2/tickets",
        headers={
            "Authorization": "Bearer fake_token",
        },
        params=None,
        json=payload,
        data=None,
    )

from unittest.mock import MagicMock, patch

from twilio.base.exceptions import TwilioRestException

from agent_ready_tools.clients.error_handling import ErrorDetails
from agent_ready_tools.clients.twilio_client import TwilioClient


@patch("agent_ready_tools.clients.twilio_client.Client")
def test_twilio_client_post_request_success(mock_twilio_client: MagicMock) -> None:
    """Test that the TwilioClient creates a resource successfully via post_request."""
    mock_client_instance = mock_twilio_client.return_value
    mock_message = MagicMock()
    mock_message.sid = "SM123"
    mock_message.body = "Hello"
    mock_message.from_ = "+15017122661"
    mock_message.to = "+15558675309"
    mock_message.status = "sent"
    mock_message.date_sent = "2025-09-09"
    mock_client_instance.messages.create.return_value = mock_message

    client = TwilioClient(
        base_url="https://api.twilio.com",
        api_key="key",
        api_key_secret="secret",
    )
    response = client.post_request(
        client.client.messages, to="+15558675309", from_="+15017122661", body="Hello"
    )

    assert isinstance(response, dict)
    assert response.get("status") == "success"
    item = response.get("item")
    assert item is not None
    assert item.sid == "SM123"
    mock_client_instance.messages.create.assert_called_once_with(
        to="+15558675309", from_="+15017122661", body="Hello"
    )


@patch("agent_ready_tools.clients.twilio_client.Client")
def test_twilio_client_post_request_error(mock_twilio_client: MagicMock) -> None:
    """Test that the TwilioClient handles errors when sending a message."""
    mock_client_instance = mock_twilio_client.return_value
    mock_client_instance.messages.create.side_effect = TwilioRestException(
        status=400, uri="/Messages", msg="The 'To' number is not a valid phone number."
    )

    client = TwilioClient(
        base_url="https://api.twilio.com",
        api_key="key",
        api_key_secret="secret",
    )
    response = client.post_request(
        client.client.messages, to="invalid", from_="+15017122661", body="Hello"
    )

    assert isinstance(response, ErrorDetails)
    assert response.status_code == 400
    assert response.reason is not None
    assert "not a valid phone number" in response.reason


@patch("agent_ready_tools.clients.twilio_client.Client")
def test_twilio_client_get_request_success(mock_twilio_client: MagicMock) -> None:
    """Test that the TwilioClient retrieves a resource successfully via get_request."""
    mock_client_instance = mock_twilio_client.return_value
    mock_message_instance = MagicMock()
    mock_message_instance.sid = "SM123"
    mock_message_instance.body = "Hello"
    mock_message_instance.from_ = "+15017122661"
    mock_message_instance.to = "+15558675309"
    mock_message_instance.status = "delivered"
    mock_message_instance.date_sent = "2025-09-09"
    mock_client_instance.messages.return_value.fetch.return_value = mock_message_instance

    client = TwilioClient(
        base_url="https://api.twilio.com",
        api_key="key",
        api_key_secret="secret",
    )
    response = client.get_request(client.client.messages, resource_id="SM123")

    assert isinstance(response, dict)
    assert response.get("status") == "success"
    item = response.get("item")
    assert item is not None
    assert item.sid == "SM123"
    assert item.body == "Hello"
    mock_client_instance.messages.assert_called_once_with("SM123")
    mock_client_instance.messages.return_value.fetch.assert_called_once()


@patch("agent_ready_tools.clients.twilio_client.Client")
def test_twilio_client_update_request_success(mock_twilio_client: MagicMock) -> None:
    """Test that the TwilioClient updates a resource successfully via update_request."""
    mock_client_instance = mock_twilio_client.return_value
    mock_call_instance = MagicMock()
    mock_call_instance.sid = "CA123"
    mock_call_instance.status = "completed"
    mock_client_instance.calls.return_value.update.return_value = mock_call_instance

    client = TwilioClient(
        base_url="https://api.twilio.com",
        api_key="key",
        api_key_secret="secret",
    )
    response = client.update_request(client.client.calls, resource_id="CA123", status="completed")

    assert isinstance(response, dict)
    assert response.get("status") == "success"
    item = response.get("item")
    assert item is not None
    assert item.sid == "CA123"
    assert item.status == "completed"
    mock_client_instance.calls.assert_called_once_with("CA123")
    mock_client_instance.calls.return_value.update.assert_called_once_with(status="completed")


@patch("agent_ready_tools.clients.twilio_client.Client")
def test_twilio_client_delete_request_success(mock_twilio_client: MagicMock) -> None:
    """Test that the TwilioClient deletes a resource successfully via delete_request."""
    mock_client_instance = mock_twilio_client.return_value
    mock_client_instance.messages.return_value.delete.return_value = True

    client = TwilioClient(
        base_url="https://api.twilio.com",
        api_key="key",
        api_key_secret="secret",
    )
    response = client.delete_request(client.client.messages, resource_id="SM123")

    assert isinstance(response, dict)
    assert response.get("status") == "success"
    assert response.get("deleted") is True
    mock_client_instance.messages.assert_called_once_with("SM123")
    mock_client_instance.messages.return_value.delete.assert_called_once()


@patch("agent_ready_tools.clients.twilio_client.Client")
def test_twilio_client_delete_request_error(mock_twilio_client: MagicMock) -> None:
    """Test that the TwilioClient handles errors when deleting a resource."""
    mock_client_instance = mock_twilio_client.return_value
    mock_client_instance.messages.return_value.delete.side_effect = TwilioRestException(
        status=404, uri="/Messages/SM123", msg="The requested resource was not found."
    )

    client = TwilioClient(
        base_url="https://api.twilio.com",
        api_key="key",
        api_key_secret="secret",
    )
    response = client.delete_request(client.client.messages, resource_id="SM123")

    assert isinstance(response, ErrorDetails)
    assert response.status_code == 404
    assert response.reason is not None
    assert "not found" in response.reason
    mock_client_instance.messages.assert_called_once_with("SM123")
    mock_client_instance.messages.return_value.delete.assert_called_once()

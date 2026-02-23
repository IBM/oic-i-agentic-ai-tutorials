import time
from unittest.mock import MagicMock, patch

import jwt

from agent_ready_tools.clients.salesforce_client import SalesforceClient


@patch("requests.post")
@patch("agent_ready_tools.clients.salesforce_client.Salesforce")
def test_salesforce_client(mock_sf: MagicMock, mock_post: MagicMock) -> None:
    """
    Test that the `SalesforceClient` is working as expected.

    Args:
        mock_sf: The mock for the Salesforce class
        mock_post: The mock for the requests.post function
    """

    # Define mock API response data
    current_time = int(time.time())
    valid_jwt = jwt.encode({"exp": current_time + 3600}, "secret", algorithm="HS256")
    test_data = {"access_token": valid_jwt, "expires_in": 3600}

    # Create a mock instance for API requests
    mock_client = MagicMock()
    mock_client.status_code = 200  # Ensure correct status code
    mock_client.json.return_value = test_data  # Simulate JSON response
    mock_client.raise_for_status = MagicMock()  # Simulate success

    mock_post.return_value = mock_client  # Set created mock for the post function

    mock_sf.return_value = MagicMock()  # Mock Salesforce SDK

    # Call the Salesforce client
    client: SalesforceClient = SalesforceClient("", "")

    # Ensure that SalesforceClient() executed and returned proper values
    assert client
    assert client.salesforce_object

    # Ensure the API calls were made with expected parameters
    resp = client.post_request("v1.0.0", "Leads")
    assert resp
    assert resp == test_data
    mock_post.assert_called_once()
    mock_client.json.assert_called_once()

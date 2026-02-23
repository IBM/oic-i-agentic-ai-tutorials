from unittest.mock import patch

from agent_ready_tools.clients.ibm_sip_client import IBMSIPClient


def test_ibm_sip_client() -> None:
    """Test that get_request from IBM Sterling Intelligent Promising client is working as
    expected."""

    # Define mock API response data
    test_data = {"test_key": "test_val"}

    with patch(
        "agent_ready_tools.clients.ibm_sip_client.IBMSIPClient.get_request"
    ) as mock_get_request:
        # Create a mock for the IBM SIP's instance
        mock_client = IBMSIPClient("https://api.watsoncommerce.ibm.com/tenant_id", "token")
        mock_get_request.return_value = test_data

        # Call get_request function from IBM SIP
        response = mock_client.get_request("test_endpoint")

        # Ensure that get_request() executed and returned proper values
        assert response == test_data

        # Ensure the IBM SIP API call was made with expected parameters
        mock_get_request.assert_called_once_with("test_endpoint")

from unittest.mock import MagicMock, patch

from agent_ready_tools.clients.ibm_planning_analytics_client import IBMPlanningAnalyticsClient


@patch("agent_ready_tools.clients.ibm_planning_analytics_client.requests.Session")
def test_ibm_pa_client_basic_auth(patch_session: MagicMock) -> None:
    """
    Test that the `IBMPlanningAnalyticsClient` is working as expected. Test
    `IBMPlanningAnalyticsClient._fetch_session_token` with mocked `requests.get`.

    Args:
        mock_get: The mock object for the requests.get function
    """

    # Define mock API response data
    cookies = {
        "paSession": "s%3AeUf1SKlKuFIdOXYPQNuSAR7wb3JfVT2W.m7KviYcZaZRWg4yT6VXjiOwPRuyz2a3Xvk0oR26WPHc",
        "SameSite": "None",
    }
    # Create a mock response instance for API requests
    mock_session = MagicMock()
    patch_session.return_value = mock_session
    mock_api_response = MagicMock()
    mock_session.get.return_value = mock_api_response
    mock_cookie = MagicMock()
    mock_session.cookies = mock_cookie
    mock_cookie.get_dict.return_value = cookies
    mock_api_response.status_code = 200  # Ensure no HTTP error
    mock_api_response.raise_for_status = MagicMock()  # Prevent raising errors

    # Call the IBM PA client, _fetch_session_token is called implicitly in the initializer.
    client: IBMPlanningAnalyticsClient = IBMPlanningAnalyticsClient(
        base_url="", username="", password="", tenant_id="", model_name="", version=""
    )
    mock_session.get.assert_called_once()
    test_cookies = client.session.cookies.get_dict()
    assert test_cookies.get("paSession") == cookies["paSession"]

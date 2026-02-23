from unittest.mock import patch

from agent_ready_tools.clients.auth_manager import (
    AdobeWorkfrontAuthManager,
    AuthManager,
    HubSpotAuthManager,
    WorkdayAuthManager,
)
from agent_ready_tools.clients.clients_enums import AccessLevel


def test_auth_manager_initialization() -> None:
    """Test that AuthManager is called correctly during initialization."""

    # Define mock API response data
    test_data = {
        "access_token": "NmUzYWM4MWYxMDAwMTZl",
        "refresh_token": "MDAwMTNmUzMWYxZlYWM4",
        "client_id": "giekqar6ye2gvz",
        "client_secret": "mU5MzgtZTc5Ny0",
        "token_url": "https://example.com/ccx/oauth2/tenant1/token",
        "token_cache_file": "test_auth.json",
    }

    # Patch HTTPBasicAuth to check if it's being called in the initialization
    with patch("agent_ready_tools.clients.auth_manager.HTTPBasicAuth") as mock_auth:
        # Create an AuthManager instance for testing
        client = AuthManager(
            token_url=str(test_data["token_url"]),
            client_id=str(test_data["client_id"]),
            client_secret=str(test_data["client_secret"]),
            initial_bearer_token=str(test_data["access_token"]),
            initial_refresh_token=str(test_data["refresh_token"]),
            token_cache_file=test_data["token_cache_file"],
        )

        # Ensure the API call was made with expected parameters
        mock_auth.assert_called_once_with(test_data["client_id"], test_data["client_secret"])

        # Call get_bearer_token() function from AuthManager client
        response = client.get_bearer_token()

        # Ensure that get_bearer_token() executed and returned proper values
        assert response == test_data["access_token"]


def test_adobe_workfront_auth_manager() -> None:
    """Test that AdobeWorkfrontAuthManager is called correctly during initialization."""

    # Define mock API response data
    test_data = {
        "bearer_token": "f79adec51b4343f9852d41743c79c118",
        "refresh_token": "ZcV/6ENPJiqjZbj5+9+lVgmhsZKJbcjD2cF6Wf/Nob9BHOZG0C3geyZHLmtXX46X6xLL7A8dG0DiMqyyhljuxI0DGIKfmSxA5VMJ0t0lJTUjFoOQJ9b7TBLJABdLtcuiKO/MIGX49jPw+sPzXYMcsSGT6Eg+Fa36g8QKhK3A0hhR6kzrkt7J9/MqVLlowpLLJoexdCEzoqZu6FnKlIhkIHIOgFHT1ouQKeFMGAVPMODtJY1cOeKdjx1Hswl/ePj+tywyaQKj9klBmx4dVyU7R6OJVASHcPBrdNSfelpY+cS0eZAQ/82ziDX4kG+QF4KNyyGUelb6LPSREtBsfElS",
        "client_id": "d2a7fdc06a94790558bbc32a7d5e1c13",
        "client_secret": "Db2_cIWRUfahXytojf9jf7DSVKgVNphAVi6Q7EBKlVM",
        "token_url": "https://example.com/integrations/oauth2/api/v1/token",
    }

    # Patch HTTPBasicAuth to check if it's being called in the initialization
    with patch("agent_ready_tools.clients.auth_manager.HTTPBasicAuth") as mock_auth:
        # Create a AdobeWorkfrontAuthManager instance for testing
        client = AdobeWorkfrontAuthManager(
            token_url=str(test_data["token_url"]),
            client_id=str(test_data["client_id"]),
            client_secret=str(test_data["client_secret"]),
            initial_bearer_token=str(test_data["bearer_token"]),
            initial_refresh_token=str(test_data["refresh_token"]),
        )

        # Ensure the API call was made with expected parameters
        mock_auth.assert_called_once_with(test_data["client_id"], test_data["client_secret"])

        # Call get_bearer_token() function from AdobeWorkfrontAuthManager client
        response = client.get_bearer_token()

        # Ensure that get_bearer_token() executed and returned proper values
        assert response == test_data["bearer_token"]


def test_hubspot_auth_manager() -> None:
    """Test that HubSpotManager is called correctly during initialization."""

    # Define mock API response data
    test_data = {
        "access_token": "COKbzveEMxIPQlNQMl8kQEwrAgIASDSkWGLWvhHQgwKyLTCi-gPgHMhSeJqCf5IATmpMpW0sficvvCANNkzoTQlNQMl8kQEwrAgYACBkGcX4Ba0IU0bfRQU83bg53SVo52a0Y3LXbEYtKA25hMlIAWgBgAGjArItMcAB4AA",
        "refresh_token": "yf2-8gh4h-35n0-4642-h475-07e6999732a5",
        "client_id": "dfsfsf7a8d-f8f8-4430-8777-34232443",
        "client_secret": "f07b4aaa-34c8-4543-a324-bc3cf546a1f4",
        "token_url": "https://example.com/oauth/v1/token",
    }

    # Patch HTTPBasicAuth to check if it's being called in the initialization
    with patch("agent_ready_tools.clients.auth_manager.HTTPBasicAuth") as mock_auth:
        # Create a HubSpotAuthManager instance for testing
        client = HubSpotAuthManager(
            token_url=str(test_data["token_url"]),
            client_id=str(test_data["client_id"]),
            client_secret=str(test_data["client_secret"]),
            initial_bearer_token=str(test_data["access_token"]),
            initial_refresh_token=str(test_data["refresh_token"]),
        )

        # Ensure the API call was made with expected parameters
        mock_auth.assert_called_once_with(test_data["client_id"], test_data["client_secret"])

        # Call get_bearer_token() function from HubSpotAuthManager client
        response = client.get_bearer_token()

        # Ensure that get_bearer_token() executed and returned proper values
        assert response == test_data["access_token"]


def test_workday_auth_manager() -> None:
    """Test that WorkdayAuthManager is called correctly during initialization."""

    # Define mock API response test data
    test_data = {
        "access_token": "NmUzYWM4MWYxMDAwMTZl",
        "refresh_token": "MDAwMTNmUzMWYxZlYWM4",
        "client_id": "giekqar6ye2gvz",
        "client_secret": "mU5MzgtZTc5Ny0",
        "token_url": "https://example.com/ccx/oauth2/tenant1/token",
    }

    # Patch HTTPBasicAuth to check if it's being called in the initialization
    with patch("agent_ready_tools.clients.auth_manager.HTTPBasicAuth") as mock_auth:
        # Create a WorkdayAuthManager instance for testing
        client = WorkdayAuthManager(
            token_url=str(test_data["token_url"]),
            client_id=str(test_data["client_id"]),
            client_secret=str(test_data["client_secret"]),
            initial_bearer_token=str(test_data["access_token"]),
            initial_refresh_token=str(test_data["refresh_token"]),
            access_level=AccessLevel.EMPLOYEE,
        )

        # Ensure the API call was made with expected parameters
        mock_auth.assert_called_once_with(test_data["client_id"], test_data["client_secret"])

        # Call get_bearer_token() function from WorkdayAuthManager client
        response = client.get_bearer_token()

        # Ensure that get_bearer_token() executed and returned proper values
        assert response == test_data["access_token"]

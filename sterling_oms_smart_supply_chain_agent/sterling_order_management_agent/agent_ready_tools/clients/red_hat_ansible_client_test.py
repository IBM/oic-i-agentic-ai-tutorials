from unittest.mock import patch

from agent_ready_tools.clients.red_hat_ansible_client import AnsibleClient


def test_ansible_client_post_request() -> None:
    """Test that the `AnsibleClient` post_request works as expected."""

    # Define mock API response data
    test_data = {"job_id": 123, "status": "successful"}

    # Patch AnsibleClient's post_request to mock its behavior
    with patch(
        "agent_ready_tools.clients.red_hat_ansible_client.AnsibleClient.post_request"
    ) as mock_post_request:
        # Set mock return value for post_request function
        mock_post_request.return_value = test_data

        # Create the AnsibleClient instance
        client: AnsibleClient = AnsibleClient(
            base_url="http://example.com", bearer_token="fake-token"
        )

        # Call post_request function from AnsibleClient
        response = client.post_request("job_templates/launch", payload={"extra_vars": {}})

        # Ensure that post_request() executed and returned proper values
        assert response == test_data

        # Ensure the AnsibleClient function call was made with expected parameters
        mock_post_request.assert_called_once_with(
            "job_templates/launch", payload={"extra_vars": {}}
        )

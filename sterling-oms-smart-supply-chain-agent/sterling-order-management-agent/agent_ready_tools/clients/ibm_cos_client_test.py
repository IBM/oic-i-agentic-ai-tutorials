from unittest.mock import ANY, MagicMock, patch

from agent_ready_tools.clients.ibm_cos_client import IBMCOSClient, get_ibm_cos_client
from agent_ready_tools.utils.credentials import CredentialKeys
from agent_ready_tools.utils.systems import Systems


@patch("agent_ready_tools.clients.ibm_cos_client.ibm_boto3.resource")
def test_ibm_cos_client_initialization(mock_boto_resource: MagicMock) -> None:
    """Test that the `IBMCOSClient` initializes correctly."""
    mock_cos_instance = MagicMock()
    mock_boto_resource.return_value = mock_cos_instance
    api_key = "test_api_key"
    instance_id = "test_instance_id"
    endpoint_url = "https://s3.us.cloud-object-storage.appdomain.cloud"

    client = IBMCOSClient(
        api_key=api_key,
        instance_id=instance_id,
        endpoint_url=endpoint_url,
    )

    assert client.cos_resource is mock_cos_instance
    mock_boto_resource.assert_called_once_with(
        "s3",
        ibm_api_key_id=api_key,
        ibm_service_instance_id=instance_id,
        config=ANY,
        endpoint_url=endpoint_url,
    )


@patch("agent_ready_tools.clients.ibm_cos_client.ibm_boto3.resource")
def test_list_buckets(mock_boto_resource: MagicMock) -> None:
    """Test the list_buckets method."""
    mock_bucket = MagicMock()
    mock_bucket.name = "my-bucket"
    mock_bucket.creation_date.isoformat.return_value = "2024-01-01T00:00:00"

    mock_cos_instance = MagicMock()
    mock_cos_instance.buckets.all.return_value = [mock_bucket]
    mock_boto_resource.return_value = mock_cos_instance

    client = IBMCOSClient(api_key="key", instance_id="id", endpoint_url="url")
    buckets = client.list_buckets()

    assert len(buckets) == 1
    assert buckets[0]["name"] == "my-bucket"
    assert buckets[0]["creation_date"] == "2024-01-01T00:00:00"
    mock_cos_instance.buckets.all.assert_called_once()


@patch("agent_ready_tools.clients.ibm_cos_client.get_tool_credentials")
@patch("agent_ready_tools.clients.ibm_cos_client.ibm_boto3.resource")
def test_get_ibm_cos_client(
    mock_boto_resource: MagicMock,
    mock_get_credentials: MagicMock,
) -> None:
    """Test the get_ibm_cos_client factory function."""
    test_creds = {
        CredentialKeys.API_KEY: "test_api_key",
        CredentialKeys.INSTANCE_ID: "test_instance_id",
        CredentialKeys.BASE_URL: "test_endpoint_url",
    }
    mock_get_credentials.return_value = test_creds
    mock_cos_instance = MagicMock()
    mock_boto_resource.return_value = mock_cos_instance

    client = get_ibm_cos_client()

    mock_get_credentials.assert_called_once_with(Systems.IBM_COS)
    mock_boto_resource.assert_called_once_with(
        "s3",
        ibm_api_key_id=test_creds[CredentialKeys.API_KEY],
        ibm_service_instance_id=test_creds[CredentialKeys.INSTANCE_ID],
        config=ANY,
        endpoint_url=test_creds[CredentialKeys.BASE_URL],
    )
    assert isinstance(client, IBMCOSClient)
    assert client.cos_resource is mock_cos_instance

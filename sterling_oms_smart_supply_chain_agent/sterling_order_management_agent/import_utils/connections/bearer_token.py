from typing import Any, Optional

from ibm_watsonx_orchestrate.agent_builder.connections.types import ConnectionEnvironment
from ibm_watsonx_orchestrate.client.connections import utils
from ibm_watsonx_orchestrate.client.connections.connections_client import (
    ClientAPIException,
    ConnectionsClient,
)


class AdvancedConnectionClient(ConnectionsClient):
    """AdvancedConnectionClient."""

    def get_runtime_credentials(
        self, conn_id: str, env: str = ConnectionEnvironment.DRAFT
    ) -> dict[Any, Any] | None:
        """Get runtime credentials for a connection."""
        try:
            return self._get(
                f"/connections/applications/runtime_credentials?connection_id={conn_id}&env={env}"
            )
        except ClientAPIException as e:
            # Returns 400 when app creds exist but runtime cred don't yet exist
            if e.response.status_code in [404, 400]:
                return None
            raise e

    def update(self, *args: Any, **kwargs: Any) -> None:
        """update."""


def _get_advanced_connections_client() -> AdvancedConnectionClient:
    """Get client."""
    return utils.instantiate_client(
        client=AdvancedConnectionClient,
        # pylint: disable=protected-access
        url=utils._get_connections_manager_url(),
    )


def get_token_for_app_id(app_id: str) -> Optional[str]:
    """
    Get the bearer token for the given app ID.

    Args:
        app_id (str): The ID of the app for which to get the bearer token.

    Returns:
        Optional[str]: The bearer token for the given app ID, or None if the token cannot be retrieved.
    """
    client = _get_advanced_connections_client()
    conn_response = client.get(app_id)
    if conn_response is None:
        return None

    runtime_creds = client.get_runtime_credentials(
        conn_response.connection_id, ConnectionEnvironment.DRAFT
    )
    if runtime_creds is None:
        return None
    bearer_token = runtime_creds.get("runtime_credentials", {}).get("access_token")
    return bearer_token

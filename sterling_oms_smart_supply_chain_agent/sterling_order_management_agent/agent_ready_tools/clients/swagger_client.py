from http import HTTPMethod
import os
from typing import Any, Dict, List, Optional

import requests
import yaml


class WxOSwaggerClient:
    """Basic Client to send a request."""

    def __init__(self, base_url: str = "http://localhost:4321", bearer_token: Optional[str] = None):
        """
        Initialize the client.

        Args:
            base_url: The base URL for the WxO Swagger API. eg. 'https://archer.staging-wa.watson-orchestrate.ibm.com'
            bearer_token: The token to authenticate with (required for SaaS).
        """
        self.base_url = base_url
        self.cred_path = f"{os.path.expanduser('~')}/.cache/orchestrate/credentials.yaml"
        self.bearer_token = bearer_token if bearer_token else self._get_credential()
        self.headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {self.bearer_token}",
        }

    def _get_credential(self) -> str:
        """Get local bearer token."""
        with open(self.cred_path, "r") as f:
            yaml_content_dict = yaml.safe_load(f)

        token = yaml_content_dict.get("auth", {}).get("local", {}).get("wxo_mcsp_token")
        assert token is not None, "Authorization token was not found."

        return token

    def get_request(self, url_path: str) -> List[Dict[str, Any]]:
        """
        Send a GET request to an API.

        Args:
            url_path: The remaining URL path after the base URL.

        Returns:
            A response dictionary from the request.
        """

        url = f"{self.base_url}/{url_path}"
        try:
            response = requests.request(HTTPMethod.GET, url, headers=self.headers)
            response.raise_for_status()
        except requests.exceptions.ConnectionError as e:
            raise requests.exceptions.ConnectionError(
                f"Connection Error: Check that the WxO Server is running. \n\n{e}"
            )

        return response.json()

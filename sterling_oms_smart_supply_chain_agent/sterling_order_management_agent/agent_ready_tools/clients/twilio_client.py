from http import HTTPStatus
from typing import Any, Dict, Optional

from requests.exceptions import RequestException
from requests.models import Response
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from agent_ready_tools.clients.error_handling import (
    ErrorDetails,
    handling_exceptions,
    no_data_in_get_request,
)
from agent_ready_tools.utils.credentials import CredentialKeys, get_tool_credentials
from agent_ready_tools.utils.systems import Systems

T = Dict[str, Any] | ErrorDetails


class TwilioClient:
    """A remote client for Twilio."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        api_key_secret: str,
    ):
        """
        Args:
            base_url: The base URL for the Twilio API.
            api_key: The API Key for Twilio authentication.
            api_key_secret: The API Key Secret for Twilio authentication.
        """
        # The twilio client uses the api_key and api_key_secret for authentication.
        # The base_url is used to set the region for the client.
        self.client = Client(username=api_key, password=api_key_secret)
        self.client.http_client.session.base_url = base_url

    def post_request(self, resource: Any, **kwargs: Any) -> T:
        """
        Creates a resource using the Twilio API.

        Args:
            resource: The Twilio resource to create on (e.g., self.client.messages).
            **kwargs: Keyword arguments to pass to the create method (e.g., to, from_, body).

        Returns:
            A dictionary containing the created item or an ErrorDetails object on failure.
        """
        try:
            item = resource.create(**kwargs)
            return {"status": "success", "item": item}
        except TwilioRestException as e:
            return ErrorDetails(
                status_code=e.status,
                reason=e.msg,
                details={"code": e.code},
                url=e.uri,
                recommendation="Review Twilio API documentation for this error code.",
            )
        except Exception as e:  # pylint: disable=broad-except
            return handling_exceptions(exception=e, url=resource.uri)

    def get_request(self, resource: Any, resource_id: Optional[str] = None, **kwargs: Any) -> T:
        """
        Retrieves a resource by its ID or lists resources using the Twilio API.

        Args:
            resource: The Twilio resource to fetch from (e.g., self.client.messages).
            resource_id: The ID (e.g., SID) of the resource to retrieve.
            **kwargs: Optional keyword arguments to pass to the list method (e.g., limit=20).

        Returns:
            A dictionary containing the status and the resource details.
        """
        try:
            if resource_id:
                item = resource(resource_id).fetch()
            else:
                item = resource.list(**kwargs)
            return {"status": "success", "item": item}
        except TwilioRestException as e:
            if e.status == HTTPStatus.NOT_FOUND.value:
                empty_response = Response()
                empty_response.reason = e.msg
                return no_data_in_get_request(empty_response)
            return ErrorDetails(
                status_code=e.status,
                reason=e.msg,
                details={"code": e.code},
                url=e.uri,
                recommendation="Review Twilio API documentation for this error code.",
            )
        except Exception as e:  # pylint: disable=broad-except
            return handling_exceptions(exception=e, url=resource.uri)

    def update_request(
        self,
        resource: Any,
        resource_id: str,
        **kwargs: Any,
    ) -> T:
        """
        Updates a resource using the Twilio API.

        Args:
            resource: The Twilio resource to update on (e.g., self.client.calls).
            resource_id: The ID (e.g., SID) of the resource to update.
            **kwargs: Keyword arguments to pass to the update method (e.g., status="completed").

        Returns:
            A dictionary containing the updated item or an ErrorDetails object on failure.
        """
        try:
            item = resource(resource_id).update(**kwargs)
            return {"status": "success", "item": item}
        except TwilioRestException as e:
            return ErrorDetails(
                status_code=e.status,
                reason=e.msg,
                details={"code": e.code},
                url=e.uri,
                recommendation="Review Twilio API documentation for this error code.",
            )
        except Exception as e:  # pylint: disable=broad-except
            return handling_exceptions(exception=e, url=resource.uri)

    def delete_request(self, resource: Any, resource_id: str) -> T:
        """
        Deletes a resource using the Twilio API.

        Args:
            resource: The Twilio resource to delete from (e.g., self.client.messages).
            resource_id: The ID (e.g., SID) of the resource to delete.

        Returns:
            A dictionary confirming deletion or an ErrorDetails object on failure.
        """
        try:
            deleted = resource(resource_id).delete()
            if deleted:
                return {"status": "success", "deleted": True}
            # This case might not be reachable as delete() raises an exception on failure
            return {"status": "failure", "deleted": False}
        except TwilioRestException as e:
            return ErrorDetails(
                status_code=e.status,
                reason=e.msg,
                details={"code": e.code},
                url=e.uri,
                recommendation="Review Twilio API documentation for this error code.",
            )
        except Exception as e:  # pylint: disable=broad-except
            return handling_exceptions(exception=e, url=resource.uri)


def get_twilio_client() -> TwilioClient | ErrorDetails:
    """
    Get the Twilio client with credentials.

    NOTE: DO NOT CALL DIRECTLY IN TESTING!

    To test, either mock this call or call the client directly.

    Returns:
        A new instance of the Twilio client or the error details if an error occurs during creating new instance of the Twilio client.
    """
    try:
        credentials = get_tool_credentials(Systems.TWILIO)
        twilio_client = TwilioClient(
            base_url=credentials[CredentialKeys.BASE_URL],
            api_key=credentials[CredentialKeys.USERNAME],
            api_key_secret=credentials[CredentialKeys.PASSWORD],
        )
    except (AssertionError, ValueError, RequestException, TwilioRestException) as e:
        return ErrorDetails(
            status_code=None,
            url=None,
            reason=f"Caught error during Twilio client initialization:{str(e)}",
            details=f"Caught error during Twili client initialization:{str(e)}",
            recommendation=None,
        )
    return twilio_client

import re
import traceback
from typing import Any, Dict, Optional, TypeVar
from urllib.parse import urlencode

from pydantic.dataclasses import dataclass
import requests

T = TypeVar("T")


@dataclass
class ErrorDetails:
    """A unified wrapper to fetch all details about the error."""

    status_code: Optional[int]
    url: Optional[str]
    reason: Optional[str]
    details: Optional[Any | str]
    recommendation: Optional[str]


def no_data_in_get_request(response: requests.Response | Dict[str, Any]) -> ErrorDetails:
    """
    Used when GET request returns no data.

    Args:
        response: GET request response

    Returns:
        ErrorDetails response specifying GET API call returned no data.
    """
    if isinstance(response, requests.Response):
        return ErrorDetails(
            status_code=response.status_code,
            url=response.url,
            reason=response.reason,
            details="GET API call returned no data",
            recommendation="Verify the request parameters and ensure the requested resource exists.",
        )
    else:
        return ErrorDetails(
            status_code=response.get("status_code"),
            url=response.get("url"),
            reason=response.get("reason"),
            details="GET API call returned no data",
            recommendation="Verify the request parameters and ensure the requested resource exists.",
        )


def extract_error_details(response: requests.Response) -> ErrorDetails:
    """
    Used when raise_for_status() raises exceptions.

    Args:
        response: The API request response

    Returns:
        ErrorDetails response specifying details of HTTP error.
    """
    status_code = response.status_code
    try:
        error_body = response.json()
    except ValueError:
        error_body = response.text.strip()

    details = error_body if error_body else None

    # Recommendation based on common HTTP status codes
    if 400 <= status_code < 500:
        if status_code == 401:
            recommendation = "Check your authentication credentials."
        elif status_code == 403:
            recommendation = "You don’t have permission. Contact your admin."
        elif status_code == 404:
            recommendation = "The resource may not exist. Verify the URL."
        elif status_code == 429:
            recommendation = "Too many requests. Wait and try again later."
        else:
            recommendation = "Check your request parameters or configuration."
    elif 500 <= status_code < 600:
        recommendation = "Server error. Try again later or contact support if it persists."
    else:
        recommendation = "Unexpected response. Review logs or contact support."

    return ErrorDetails(
        status_code=response.status_code,
        url=response.url,
        reason=response.reason,
        details=details,
        recommendation=recommendation,
    )


def extract_error_details_sales_dnb(
    response: requests.Response, api_url: Optional[str], url_params: Optional[Dict]
) -> ErrorDetails:
    """
    Used when raise_for_status() raises exceptions.

    Args:
        response: The API request response
        pi_url: the api being called
        url_params: optional parameters associated with the api call

    Returns:
        ErrorDetails response specifying details of DnB HTTP error.
    """

    status_code = response.status_code
    try:
        error_body = response.json()
    except ValueError:
        error_body = response.text.strip()

    details = error_body if error_body else None

    # Check for a special case where get industry profile returns "empty list", but technically it doesn't return HTTP Error from the API
    # Returns True if we are using "https://plus.dnb.com/v1/industryprofile" and the profiles list is empty
    flag_industry_profile_empty_list = bool(
        api_url == "https://plus.dnb.com/v1/industryprofile"
        and not error_body.get("profiles", None)
    )
    recommendation = "Unexpected response. Review logs or contact support."
    if "error" in error_body or flag_industry_profile_empty_list:

        # If url_params is None or empty, then just use api_url, else add the url_params to end of api_url
        if not url_params or not isinstance(url_params, Dict):
            request_url = api_url
        else:
            request_params = urlencode(url_params)
            request_url = f"{api_url}?{request_params}"
        error_body["request_url"] = request_url

        # When get industry profile returns "empty list", there is no error object, so need to manually build it
        if (
            api_url == "https://plus.dnb.com/v1/industryprofile"
            and flag_industry_profile_empty_list
        ):
            error_message = "No data returned for get industry profile"
            error_code = 99999
        else:
            error_code = error_body["error"]["errorCode"]
            error_message = error_body["error"]["errorMessage"]

        return ErrorDetails(
            status_code=error_code,
            url=request_url,
            reason=error_message,
            details=details,
            recommendation=recommendation,
        )

    # Recommendation based on common HTTP status codes
    if 400 <= status_code < 500:
        if status_code == 401:
            recommendation = "Check your authentication credentials."
        elif status_code == 403:
            recommendation = "You don’t have permission. Contact your admin."
        elif status_code == 404:
            recommendation = "The resource may not exist. Verify the URL."
        elif status_code == 429:
            recommendation = "Too many requests. Wait and try again later."
        else:
            recommendation = "Check your request parameters or configuration."
    elif 500 <= status_code < 600:
        recommendation = "Server error. Try again later or contact support if it persists."
    else:
        recommendation = "Unexpected response. Review logs or contact support."

    return ErrorDetails(
        status_code=response.status_code,
        url=response.url,
        reason=response.reason,
        details=details,
        recommendation=recommendation,
    )


def handling_exceptions(exception: Exception, url: str) -> ErrorDetails:
    """
    Used when API request raises an Exception.

    Args:
        exception: exception raised by the API request.
        url: the url that was called

    Returns:
        ErrorDetails response specifying the raised exception.
    """
    details = None
    if isinstance(exception, requests.exceptions.Timeout):
        reason = "Request timed out"
        recommendation = "Check your network connection or try again later."
    elif isinstance(exception, requests.exceptions.ConnectionError):
        reason = "Could not connect"
        recommendation = "Ensure the server is reachable and you're online."
    elif isinstance(exception, requests.exceptions.RequestException):
        reason = "A request error occurred"
        recommendation = f"{exception} Review the request or try again later."
    elif isinstance(exception, Exception):
        reason = f"An unexpected error occurred: {exception}"
        details = print("".join(traceback.format_exception(exception)))
        recommendation = (
            f"{exception} Recommendation: Try again or contact support if the problem persists."
        )

    return ErrorDetails(
        status_code=None,
        url=url,
        reason=reason,
        details=details,
        recommendation=recommendation,
    )


def extract_soap_error_details(response: requests.Response) -> ErrorDetails:
    """
    Parses a SOAP Fault XML response and returns an ErrorDetails object with meaningful information.

    Args:
        response: The SOAP API request response.

    Returns:
        ErrorDetails response specifying details of HTTP error.
    """

    error_xml = response.text.strip()

    if not error_xml:
        return ErrorDetails(
            status_code=response.status_code,
            url=response.url,
            reason="Unknown Error",
            details="No error details found.",
            recommendation="Review request and retry.",
        )

    # Extract tags from XML
    faultcode = extract_tag(error_xml, "faultcode")
    faultstring = extract_tag(error_xml, "faultstring")
    message = extract_tag(error_xml, "wd:Message")
    detail_message = extract_tag(error_xml, "wd:Detail_Message")
    xpath = extract_tag(error_xml, "wd:Xpath")

    # Determine error type
    error_type = map_error_type(faultcode)

    return ErrorDetails(
        status_code=response.status_code,
        url=response.url,
        reason=f"Check XPath: {xpath}" if xpath else "Review error details",
        details=faultstring or detail_message or message or "Unknown fault",
        recommendation=error_type,
    )


def extract_tag(xml: str, tag: str) -> Optional[str]:
    """Helper to extract text from a given XML tag."""
    match = re.search(rf"<{tag}[^>]*>(?P<tag_contents>.*?)</{tag}>", xml, re.DOTALL)
    return match.group("tag_contents") if match else None


def map_error_type(faultcode: Optional[str]) -> str:
    """Maps faultcode to a human-readable error type."""
    if not faultcode:
        return "Unexpected response. Review logs or contact support."
    faultcode_lower = faultcode.lower()
    if "authenticationerror" in faultcode_lower:
        return "Check your authentication credentials"
    elif "authorizationerror" in faultcode_lower:
        return "You don't have permission. Contact your admin."
    elif "validationerror" in faultcode_lower:
        return "Check your request parameters or configuration"
    elif "businessprocesserror" in faultcode_lower:
        return "Business process error. Review the workflow or business rules associated with this request"
    elif "server" in faultcode_lower:
        return "Internal Server error. Try again later or contact support if it persists."
    return "Unexpected response. Review logs or contact support."


def return_error_details_for_specific_reason(
    reason: Optional[str], details: Optional[str], recommendation: Optional[str]
) -> ErrorDetails:
    """
    Used when API request raises an Exception.

    Args:
        reason: Reason for the error
        details: details about the error
        recommendation: recommendation to rectify the error

    Returns:
        ErrorDetails response specifying the reason and or details and or recommendation
    """
    return ErrorDetails(
        status_code=None,
        url=None,
        reason=reason,
        details=details,
        recommendation=recommendation,
    )

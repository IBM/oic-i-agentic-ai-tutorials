from datetime import datetime, timezone
import re
from zoneinfo import ZoneInfo


def sap_date_to_iso_8601(sap_date: str) -> str:
    """
    Convert a string SAP API input format to ISO 8601 ie., "/Date(<DATE-IN-MILISECONDS>)/" -> "YYYY-
    MM-DD" .

    Args:
        sap_date: the date as a string in SAP API input format (ie., `/Date(1661990400000)/`).

    Returns:
        The date as a string in ISO 8601 format (ie., YYYY-MM-DD), or the string itself if the
        pattern is not found.
    """
    match = re.search(r"/Date\((\d+)\)/", sap_date)
    if match:
        timestamp_ms = int(match.group(1))
        dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d")
    return sap_date


def iso_8601_to_sap_date(date: str, *, tzinfo: timezone = timezone.utc) -> str:
    """
    Convert a string in ISO 8601 format to the SAP API input format ie., "YYYY-MM-DD" ->
    "/Date(<DATE-IN-MILISECONDS>)/".

    Args:
        date: the date as a string in ISO 8601 format (ie., YYYY-MM-DD).
        tzinfo: the timezone info, utc by default.

    Returns:
        the date as a string in SAP API input format.
    """
    date_as_datetime = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=tzinfo)
    date_as_milliseconds = int(date_as_datetime.timestamp() * 1000)
    return f"/Date({date_as_milliseconds})/"


def iso_8601_datetime_convert_to_date(iso_datetime: str) -> str:
    """
    Converts an ISO 8601 datetime string to a ISO 8601 date in 'YYYY-MM-DD' format. Used for
    reformatting dates given from Seismic APIs.

    Args:
        iso_datetime: The ISO 8601 datetime string (e.g., "2019-06-18T16:29:37.960Z").

    Returns:
        The date in 'YYYY-MM-DD' format.
    """
    return datetime.fromisoformat(iso_datetime.rstrip("Z")).date().isoformat()


def convert_str_to_coupa_time(date_str: str) -> str:
    """Given a date string "YYYY-MM-DD", return "MM/DD/YY 12:00 AM +0000"."""
    # Parse as a date (no time)
    parsed_date = datetime.strptime(date_str, "%Y-%m-%d")

    la_midnight = parsed_date.replace(tzinfo=ZoneInfo("America/Los_Angeles"))
    #  Format to "MM/DD/YY HH:MM AM/PM +ZZZZ"
    return la_midnight.strftime("%m/%d/%y %I:%M %p %z")


def format_datetime(date_time: str) -> str:
    """
    Format datetime to MMM DD, YYYY, HH:MM format in the local time zone.

    Args:
        date_time: a string datetime from the wxo orchestrate server API.

    Returns:
        A human readable version a time date.
    """
    dt = datetime.fromisoformat(date_time.replace("Z", "+00:00")).astimezone()
    return dt.strftime("%b %d, %Y, %I:%M%p")


def weekday_from_iso_date(date: str, *, tzinfo: timezone = timezone.utc) -> str:
    """
    Get the weekday from an ISO Date.

    -> "Wednesday".

    Args:
        date: the date as a string in ISO 8601 format (ie., YYYY-MM-DD).
        tzinfo: the timezone info, utc by default.

    Returns:
        the day of the week.
    """
    try:
        date_as_datetime = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=tzinfo)
    except ValueError:
        return ""
    return date_as_datetime.strftime("%A")

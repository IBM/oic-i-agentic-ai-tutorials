from datetime import date, datetime, timezone
from typing import Optional, Union

from agent_ready_tools.apis.workday_soap_services.recruiting.api import (  # type: ignore[attr-defined]
    XmlDate,
    XmlDateTime,
)


def to_xml_date(dt: Optional[Union[date, datetime, str]]) -> Optional[XmlDate]:
    """
    Converts a Python datetime object or ISO-8601 string to a Workday-compatible XmlDate object.

    Args:
        dt: A Python datetime object or an ISO-8601 formatted string representing a specific date.
            This is typically used for fields such as 'as_of_effective_date' in Workday SOAP requests,
            where only the date portion is required without the time component.

    Returns:
        An XmlDate object if the input value is provided; otherwise, returns None.
        This ensures compatibility with Workday SOAP API expectations for date-only fields.
    """

    if dt is None:
        return None

    if isinstance(dt, str):
        if dt.endswith("Z"):
            dt = dt[:-1] + "+00:00"
        dt = datetime.fromisoformat(dt)

    elif isinstance(dt, date) and not isinstance(dt, datetime):
        dt = datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return XmlDate(dt.year, dt.month, dt.day)


def to_xml_datetime(dt: Optional[Union[datetime, str]]) -> Optional[XmlDateTime]:
    """
    Converts a Python datetime object or ISO-8601 string to a Workday-compatible XmlDateTime object.

    Args:
        dt: A Python datetime object or an ISO-8601 formatted string representing a specific date and time.
            This is typically used for fields such as 'as_of_entry_date_time', 'updated_from', or
            'effective_through' in Workday SOAP requests.

    Returns:
        An XmlDateTime object if the input value is provided; otherwise, returns None.
        This ensures compatibility with Workday SOAP API expectations for datetime fields.
    """

    if dt is None:
        return None

    if isinstance(dt, str):
        if dt.endswith("Z"):
            dt = dt[:-1] + "+00:00"
        dt = datetime.fromisoformat(dt)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return XmlDateTime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)

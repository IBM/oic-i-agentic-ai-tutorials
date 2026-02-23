from datetime import datetime, timezone

from xsdata.models.datatype import XmlDate, XmlDateTime

from agent_ready_tools.utils.xml_date_conversion import to_xml_date, to_xml_datetime


def test_to_xml_date_valid_datetime() -> None:
    """Verifies that `to_xml_date` converts a valid datetime."""
    result = to_xml_date(datetime(2023, 8, 30, tzinfo=timezone.utc))
    assert result == XmlDate(2023, 8, 30)


def test_to_xml_date_valid_string() -> None:
    """Verifies that `to_xml_date` converts an ISO string."""
    result = to_xml_date("2023-08-30T15:45:12Z")
    assert result == XmlDate(2023, 8, 30)


def test_to_xml_date_none() -> None:
    """Verifies that `to_xml_date` returns None for None input."""
    assert to_xml_date(None) is None


def test_to_xml_datetime_valid_datetime() -> None:
    """Verifies that `to_xml_datetime` converts a valid datetime."""
    result = to_xml_datetime(datetime(2023, 3, 5, 12, 34, 56, tzinfo=timezone.utc))
    assert result == XmlDateTime(2023, 3, 5, 12, 34, 56)


def test_to_xml_datetime_valid_string() -> None:
    """Verifies that `to_xml_datetime` converts an ISO string."""
    result = to_xml_datetime("2023-03-05T12:34:56Z")
    assert result == XmlDateTime(2023, 3, 5, 12, 34, 56)


def test_to_xml_datetime_none() -> None:
    """Verifies that `to_xml_datetime` returns None for None input."""
    assert to_xml_datetime(None) is None

import pytest

from agent_ready_tools.utils.date_conversion import (
    iso_8601_datetime_convert_to_date,
    iso_8601_to_sap_date,
    sap_date_to_iso_8601,
)


def test_sap_date_to_iso_8601_valid() -> None:
    """Verifies that the `sap_date_to_iso_8601` function converts a valid date."""
    result = sap_date_to_iso_8601("/Date(1661990400000)/")
    assert result == "2022-09-01"


def test_sap_date_to_iso_8601_invalid() -> None:
    """Verifies that the `sap_date_to_iso_8601` function does not convert an invalid date."""
    result = sap_date_to_iso_8601("Date(1661990400000)")  # Missing wrapping '/'
    assert result == "Date(1661990400000)"


def test_iso_8601_to_sap_date_valid() -> None:
    """Verifies that the `iso_8601_to_sap_date` function converts a valid date."""
    assert iso_8601_to_sap_date("2022-09-01") == "/Date(1661990400000)/"


def test_iso_8601_to_sap_date_invalid() -> None:
    """Verifies that the `iso_8601_to_sap_date` function does not convert an invalid date."""
    with pytest.raises(ValueError):
        iso_8601_to_sap_date("2022-13-01")  # Month value > 12


def test_iso_8601_datetime_convert_to_date_valid() -> None:
    """Verifies that the `iso_8601_datetime_convert_to_date` function converts a valid date."""
    assert iso_8601_datetime_convert_to_date("2019-05-31T05:19:56.123Z") == "2019-05-31"


def test_iso_8601_datetime_convert_to_date_invalid() -> None:
    """Verifies that the `iso_8601_datetime_convert_to_date` function does not convert an invalid
    date."""
    with pytest.raises(ValueError):
        iso_8601_datetime_convert_to_date("2019-05-31T05:19:5")

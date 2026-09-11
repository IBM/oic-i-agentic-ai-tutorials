from agent_ready_tools.utils.integer_readable_format import integer_readable_format


def test_integer_readable_format_dollars() -> None:
    """Verifies that the `integer_readable_format` function converts a valid dollar value."""
    result = integer_readable_format(377595000, "dollar")
    assert result == "$377,595,000"


def test_integer_readable_format_long_int() -> None:
    """Verifies that the `integer_readable_format` function converts a valid long integer."""
    assert integer_readable_format(6000, "long_int") == "6,000"


def test_integer_readable_format_empty_long_int() -> None:
    """Verifies that the `integer_readable_format` function converts a empty string (long int)"""
    assert integer_readable_format("", "long_int") == ""


def test_integer_readable_format_empty_dollar() -> None:
    """Verifies that the `integer_readable_format` function converts a empty string (dollar)"""
    assert integer_readable_format("", "dollar") == ""

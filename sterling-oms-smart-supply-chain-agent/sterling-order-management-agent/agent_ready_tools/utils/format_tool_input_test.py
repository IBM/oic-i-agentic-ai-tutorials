import enum
import json

import pytest

from agent_ready_tools.utils import format_tool_input


def test_string_to_list_of_strings() -> None:
    """Verifies that the `string_to_list_of_strings` functions."""
    assert format_tool_input.string_to_list_of_strings("foo") == ["foo"]
    assert format_tool_input.string_to_list_of_strings("['foo', 'bar']") == [
        "foo",
        "bar",
    ]

    with pytest.raises(json.JSONDecodeError):
        format_tool_input.string_to_list_of_strings("['foo'], ['bar']")

    assert format_tool_input.string_to_list_of_strings("[foo") == ["[foo"]


def test_string_to_list_of_enums() -> None:
    """Verifies that the `string_to_list_of_enums` functions."""

    class MyClass(enum.Enum):
        """Test Enum."""

        FOO = 1
        BAR = 2

    assert format_tool_input.string_to_list_of_enums(
        "FOO",
        MyClass,
    ) == [MyClass.FOO]

    assert format_tool_input.string_to_list_of_enums(
        "['FOO', 'BAR']",
        MyClass,
    ) == [MyClass.FOO, MyClass.BAR]

    with pytest.raises(KeyError):
        format_tool_input.string_to_list_of_enums(
            "['FOO', 'BAR', 'BAZ']",
            MyClass,
        )


def test_string_to_list_of_ints() -> None:
    """Verifies that the `string_to_list_of_ints` function behaves as expected."""
    assert format_tool_input.string_to_list_of_ints([123, 456]) == [123, 456]
    assert format_tool_input.string_to_list_of_ints("123") == [123]
    assert format_tool_input.string_to_list_of_ints("123,456") == [123, 456]
    assert format_tool_input.string_to_list_of_ints("[123, 456]") == [123, 456]


def test_string_to_boolean() -> None:
    """Verifies that the `string_to_boolean` function behaves as expected."""
    assert format_tool_input.string_to_boolean("true") is True
    assert format_tool_input.string_to_boolean("false") is False
    assert format_tool_input.string_to_boolean("None") is False


def test_is_empty_string() -> None:
    """Verifies that the `is_empty_value` function behaves as expected."""
    assert format_tool_input.is_empty_value("null") is True
    assert format_tool_input.is_empty_value("") is True
    assert format_tool_input.is_empty_value(None) is True
    assert format_tool_input.is_empty_value("None") is False

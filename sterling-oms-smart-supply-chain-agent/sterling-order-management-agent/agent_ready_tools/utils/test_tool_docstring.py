from typing import Dict, Optional
from unittest.mock import MagicMock

import docstring_parser  # pants: no-infer-dep
import pytest

from agent_ready_tools.utils.tool_docstring import (
    extract_returns_section_from_google_style_docstring,
    normalize_docstring_section,
    validate_args_section,
    validate_returns_section,
)

# ===============================
# GENERIC HELPERS TESTS
# ===============================


@pytest.mark.parametrize(
    "input_text, expected",
    [
        ("Some TEXT  ", "some text"),  # trims spaces, lowercases
        ("   MULTI Line \nText  ", "multi line text"),  # strip newlines
        ("", ""),  # empty string stays empty
        ("  Already clean", "already clean"),  # simple lowercase
    ],
)
def test_normalize_docstring_section(input_text: str, expected: str) -> None:
    """Tests normalize_docstring_section function with different strings."""
    assert normalize_docstring_section(input_text) == expected


@pytest.mark.parametrize(
    "docstring, expected",
    [
        ("Returns:\n Some description", "Some description"),  # basic
        ("Summary.\n\nReturns:   Something detailed", "Something detailed"),  # trims spaces
        ("Returns:\n    Indented text here", "Indented text here"),  # removes indentation
        (
            "Returns:\n    Indented text here\nRaises:\n   raises an error",
            "Indented text here",
        ),  # ignores raises section
        ("No returns here", None),  # missing "Returns:" entirely
        ("", None),  # empty string
    ],
)
def test_extract_returns_section(docstring: str, expected: str) -> None:
    """Tests extract_returns_section_from_google_style_docstring function with different
    docstrings."""
    assert extract_returns_section_from_google_style_docstring(docstring) == expected


# ===============================
# ARGS SECTION TESTS
# ===============================


# Minimal fake classes to keep tests self-contained
def mock_json_schema_object(title: str, type_: str, description: Optional[str]) -> MagicMock:
    """Create a mock that looks like a JsonSchemaObject with required attributes."""
    obj = MagicMock()
    obj.title = title
    obj.type = type_
    obj.description = description
    return obj


def mock_tool_with_args(args_dict: Dict[str, MagicMock]) -> MagicMock:
    """
    Create a mock that looks like PythonTool with the nested structure:

    python_tool.__tool_spec__.input_schema.properties -> args_dict
    """
    tool = MagicMock()
    tool.__tool_spec__ = MagicMock()
    tool.__tool_spec__.input_schema = MagicMock()
    tool.__tool_spec__.input_schema.properties = args_dict
    return tool


# Tests


def test_missing_argument_in_tool_spec() -> None:
    """Tests that when a parsed tool has different arguments, the validation fails."""
    python_tool = mock_tool_with_args(
        {"arg1": mock_json_schema_object("arg1", "string", "Some description")}
    )
    parsed_docstring = docstring_parser.parse(
        """
        Args:
            arg1: Some description"
            missing_arg: This arg is not in the tool spec.
        """
    )

    errors = validate_args_section(python_tool, parsed_docstring)
    assert len(errors) == 1
    assert errors[0].error
    assert "Argument name missing in the parsed tool specification." in errors[0].error


def test_argument_is_object_type_skips_check() -> None:
    """Tests that when the tool's argument is an object, the validation succedes."""
    python_tool = mock_tool_with_args(
        {"arg1": mock_json_schema_object("arg1", "object", "Some description")}
    )
    parsed_docstring = docstring_parser.parse(
        """
        Args:
            arg1: Some description.
        """
    )

    errors = validate_args_section(python_tool, parsed_docstring)
    assert errors == []  # no errors for object type


def test_missing_description() -> None:
    """Tests that when a tool's argument is missing a description, the validation fails."""
    python_tool = mock_tool_with_args({"arg1": mock_json_schema_object("arg1", "string", None)})
    parsed_docstring = docstring_parser.parse(
        """
        Args:
            arg1: Some description in docstring.
        """
    )

    errors = validate_args_section(python_tool, parsed_docstring)
    assert len(errors) == 1
    assert errors[0].error
    assert "Missing description" in errors[0].error


def test_description_differs() -> None:
    """Tests that when the tool's argument has different description than in the parsed docstring,
    the validation fails."""
    python_tool = mock_tool_with_args(
        {"arg1": mock_json_schema_object("arg1", "string", "Tool spec description")}
    )
    parsed_docstring = docstring_parser.parse(
        """
        Args:
            arg1: Different docstring description.
        """
    )

    errors = validate_args_section(python_tool, parsed_docstring)
    assert len(errors) == 1
    assert errors[0].error
    assert "differs from tool specification" in errors[0].error
    assert "Different docstring description" in errors[0].error
    assert "Tool spec description" in errors[0].error


def test_extra_arguments_in_tool_spec() -> None:
    """Tests that when there are more arguments in tool than in parsed docstring, the validation
    fails."""

    python_tool = mock_tool_with_args(
        {"arg1": mock_json_schema_object("arg1", "string", "Some description")}
    )
    parsed_docstring = docstring_parser.parse(
        """
        Args:
            # Empty args section
        """
    )

    errors = validate_args_section(python_tool, parsed_docstring)
    assert len(errors) == 1
    assert errors[0].error
    assert "Argument missing in docstring" in errors[0].error
    assert errors[0].tool_argument.argument_name == "arg1"


# ===============================
# RETURN SECTION TESTS
# ===============================


def mock_python_tool_with_returns(description: str, fn_docstring: str) -> MagicMock:
    """
    Create a mock that looks like the minimal PythonTool needed for validate_returns_section:

    - __tool_spec__.output_schema.description -> description
    - fn.__doc__ -> fn_docstring
    """
    tool = MagicMock()
    tool.__tool_spec__ = MagicMock()
    tool.__tool_spec__.output_schema = MagicMock()
    tool.__tool_spec__.output_schema.description = description

    def _fn() -> None:
        pass

    _fn.__doc__ = fn_docstring
    tool.fn = _fn
    return tool


def test_missing_returns_section_in_tool_spec() -> None:
    """Test that when a tool's docstring's return section is missing, the validation fails."""
    python_tool = mock_python_tool_with_returns(description="", fn_docstring="Returns:\n Something")
    parsed = docstring_parser.parse(python_tool.fn.__doc__ or "")
    msg = validate_returns_section(python_tool, parsed)
    assert msg == "Missing Returns section describing the tool output."


def test_missing_or_incorrect_returns_section_in_docstring() -> None:
    """Tests that when a return section is missing in parsed docstring, the validation fails."""
    python_tool = mock_python_tool_with_returns(description="Expected output", fn_docstring="")
    parsed = docstring_parser.parse(python_tool.fn.__doc__ or "")
    msg = validate_returns_section(python_tool, parsed)
    assert (
        msg
        == "Returns section is missing or incorrectly formatted. Follow Google style convention."
    )


def test_returns_section_description_differs() -> None:
    """Tests that when a tool's docstring is different than the parsed, the validation fails."""
    python_tool = mock_python_tool_with_returns(
        description="Expected output",
        fn_docstring="Something\nReturns:\n    different output",
    )
    parsed = docstring_parser.parse(python_tool.fn.__doc__ or "")
    msg = validate_returns_section(python_tool, parsed)
    assert "Returns section description differs from tool specification." in msg


def test_raw_returns_section_differs() -> None:
    """Tests that when a tool's docstring is different than the raw, the validation fails."""
    # Same parsed text, but raw docstring extracted differently (simulating indentation issue)
    python_tool = mock_python_tool_with_returns(
        description="expected output",
        fn_docstring="Returns:\n    expected output\nand something else",
    )
    parsed = docstring_parser.parse(python_tool.fn.__doc__ or "")
    msg = validate_returns_section(python_tool, parsed)
    assert "Raw Returns section differs from tool specification (possible indentation issue)" in msg


def test_returns_section_valid() -> None:
    """Tests that a correctly formatted docstring passes validation."""
    python_tool = mock_python_tool_with_returns(
        description="expected output",
        fn_docstring="Function description\nReturns:\n  expected output",
    )
    parsed = docstring_parser.parse(python_tool.fn.__doc__ or "")
    msg = validate_returns_section(python_tool, parsed)
    assert msg == ""

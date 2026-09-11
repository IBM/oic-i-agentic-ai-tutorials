from enum import StrEnum
import inspect
import re
from typing import List, Optional, Tuple

# it's a library used by orchestrate to parse docstrings
import docstring_parser  # pants: no-infer-dep
from ibm_watsonx_orchestrate.agent_builder.tools import PythonTool
from ibm_watsonx_orchestrate.agent_builder.tools.types import JsonSchemaObject, ToolResponseBody
from pydantic import BaseModel


# ===============================
# ENUMS
# ===============================
class GoogleDocstringsSections(StrEnum):
    """Enum specifying the section present in the google-styled docstrings."""

    ARGS = "Args:"
    RETURNS = "Returns:"
    RAISES = "Raises:"
    EXAMPLES = "Examples:"
    ATTRIBUTES = "Attributes:"
    NOTE = "Note:"
    REFERENCES = "References:"
    TODO = "Todo:"
    YIELDS = "Yields:"


# ===============================
# DATA MODELS
# ===============================


class ToolArgument(BaseModel):
    """
    Represents a broken tool argument.

    Attributes:
        argument_name (str): The name of the argument
        argument_description (str): The description of the argument.
    """

    argument_name: str
    argument_description: str | None


class ToolArgumentError(BaseModel):
    """
    Represents an error found in a tool argument.

    Attributes:
        tool_argument (ToolArgument): The tool argument that contains an error.
        error (str): The error message for the param
    """

    tool_argument: ToolArgument
    error: str | None


class DocstringValidationResult(BaseModel):
    """
    Represents the result of a docstring validation check.

    Attributes:
        arguments_with_errors: A list of error messages if the docstring is invalid.
        return_error: Error related to the Returns: section of the docstring.
        docstring_missing: If the tool doesn't have a docstring.
    """

    arguments_with_errors: list[ToolArgumentError]
    return_error: str
    docstring_missing: bool

    @property
    def is_valid(self) -> bool:
        """
        Check if the docstring validation result is valid.

        Returns:
            bool: True if there are no arguments with errors, False otherwise.
        """
        return len(self.arguments_with_errors) == 0 and not (
            self.return_error or self.docstring_missing
        )


# ===============================
# GENERIC HELPERS
# ===============================


def normalize_docstring_section(text: str) -> str:
    """Lowercase, remove punctuation, and collapse spaces."""
    text = text.lower()
    text = re.sub(r"\W+", " ", text)  # Keep only alphanumerics and spaces
    return " ".join(text.split())  # Collapse multiple spaces


def extract_returns_section_from_google_style_docstring(docstring: str) -> Optional[str]:
    """Extract the Returns section from a Google-style docstring."""
    lines = docstring.splitlines()
    in_returns = False
    returns_lines = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith(GoogleDocstringsSections.RETURNS):
            in_returns = True
            stripped = stripped[len(GoogleDocstringsSections.RETURNS) :].strip()
            if stripped:
                returns_lines.append(stripped)
            continue
        if in_returns:
            # Stop if the next section starts (e.g., "Raises:", "Examples:", "Attributes:")
            section_names = "|".join(re.escape(s.value) for s in GoogleDocstringsSections)
            if re.match(rf"^({section_names})$", stripped):
                break
            elif line.strip() == "":
                # blank line – probably allowed
                continue
            else:
                returns_lines.append(line.strip())
    return "\n".join(returns_lines) if returns_lines else None


# ===============================
# ARGUMENT CHECKS
# ===============================


def arg_missing_in_tool_spec(param_name: str, tool_args: dict) -> bool:
    """Check if a parameter is missing from the tool's input schema."""
    return param_name not in tool_args


def arg_is_object_type(parsed_arg: JsonSchemaObject) -> bool:
    """Check if an argument is of type 'object' (skip description check)."""
    return parsed_arg.type == "object"


def arg_missing_description(parsed_arg: JsonSchemaObject) -> bool:
    """Check if an argument is missing its description."""
    return not parsed_arg.description


def arg_description_differs(
    parsed_arg: JsonSchemaObject, param: docstring_parser.DocstringParam
) -> bool:
    """Check if the argument's description differs from the one in the docstring."""
    return normalize_docstring_section(parsed_arg.description or "") != normalize_docstring_section(
        param.description or ""
    )


def extra_args_in_tool_spec(tool_args: dict) -> list:
    """Return extra arguments from the tool spec not present in the docstring."""
    return list(tool_args.values())


# ===============================
# RETURNS CHECKS
# ===============================


def return_section_missing_in_tool_spec(tool_return: ToolResponseBody) -> bool:
    """Check if the tool's return value lacks a description."""
    return not tool_return.description


def return_description_missing(parsed_returns: Optional[docstring_parser.DocstringReturns]) -> bool:
    """Check if the parsed Returns section is missing or lacks a description."""
    return not (parsed_returns and parsed_returns.description)


def get_tool_return_diff(
    parsed_returns: Optional[docstring_parser.DocstringReturns], tool_return: ToolResponseBody
) -> Optional[Tuple[str, str]]:
    """
    Compare parsed Returns section description to tool specification.

    Returns a tuple (parsed_description, tool_description) if they differ.
    """
    parsed_desc = (
        normalize_docstring_section(parsed_returns.description)
        if parsed_returns and parsed_returns.description
        else ""
    )
    tool_desc = normalize_docstring_section(tool_return.description)
    return (parsed_desc, tool_desc) if parsed_desc != tool_desc else None


def get_raw_vs_tool_desc(
    python_tool: PythonTool, tool_return: ToolResponseBody
) -> Optional[Tuple[str, str]]:
    """
    Compare raw Returns section from the docstring to tool specification.

    Returns a tuple (raw_docstring_desc, tool_description) if they differ.
    """
    raw_docstring = inspect.getdoc(python_tool.fn) or ""
    raw_returns = extract_returns_section_from_google_style_docstring(raw_docstring)
    raw_desc = normalize_docstring_section(raw_returns or "")
    tool_desc = normalize_docstring_section(tool_return.description)
    return (raw_desc, tool_desc) if raw_desc != tool_desc else None


# ===============================
# ARGUMENTS VALIDATION
# ===============================


def validate_args_section(
    python_tool: PythonTool, parsed_docstring: docstring_parser.Docstring
) -> List[ToolArgumentError]:
    """
    Validate the arguments section of a Google-style docstring against the PythonTool's input
    schema.

    This function performs the following checks for each argument described in the parsed docstring:
    - Whether the argument exists in the tool's input schema.
    - Whether the argument is of type "object" (in which case description checks are skipped).
    - Whether the argument has a description in the tool's input schema.
    - Whether the description in the docstring matches the description in the tool's input schema.

    Additionally, it checks if there are any extra arguments defined in the tool's input schema
    that are missing from the docstring.

    Args:
        python_tool (PythonTool): The tool whose input schema is used for validation.
        parsed_docstring (docstring_parser.Docstring): The parsed Google-style docstring object.

    Returns:
        List[ToolArgumentError]: A list of errors describing mismatches or missing argument documentation.
    """
    errors: List[ToolArgumentError] = []
    tool_args = dict(python_tool.__tool_spec__.input_schema.properties)

    for param in parsed_docstring.params:
        if arg_missing_in_tool_spec(param.arg_name, tool_args):
            errors.append(
                ToolArgumentError(
                    tool_argument=ToolArgument(
                        argument_name=param.arg_name or "", argument_description=param.description
                    ),
                    error="Argument name missing in the parsed tool specification.",
                )
            )
            continue

        parsed_arg = tool_args.pop(param.arg_name)

        if arg_is_object_type(parsed_arg):
            continue

        if arg_missing_description(parsed_arg):
            errors.append(
                ToolArgumentError(
                    tool_argument=ToolArgument(
                        argument_name=parsed_arg.title or "",
                        argument_description=parsed_arg.description,
                    ),
                    error="Missing description.",
                )
            )
            continue

        if arg_description_differs(parsed_arg, param):
            errors.append(
                ToolArgumentError(
                    tool_argument=ToolArgument(
                        argument_name=parsed_arg.title or "",
                        argument_description=parsed_arg.description,
                    ),
                    error=(
                        "Docstring description differs from tool specification.\n"
                        f"Docstring: {param.description}\nTool spec: {parsed_arg.description}"
                    ),
                )
            )

    for extra_arg in extra_args_in_tool_spec(tool_args):
        errors.append(
            ToolArgumentError(
                tool_argument=ToolArgument(
                    argument_name=extra_arg.title or "", argument_description=extra_arg.description
                ),
                error="Argument missing in docstring.",
            )
        )

    return errors


# ===============================
# RETURNS VALIDATION
# ===============================


def validate_returns_section(
    python_tool: PythonTool, parsed_docstring: docstring_parser.Docstring
) -> str:
    """
    Validate that the Returns section in the docstring matches the tool's output schema.

    Returns an error message if validation fails, otherwise an empty string.
    """
    tool_return = python_tool.__tool_spec__.output_schema

    if return_section_missing_in_tool_spec(tool_return):
        return "Missing Returns section describing the tool output."

    parsed_returns = parsed_docstring.returns

    if return_description_missing(parsed_returns):
        return (
            "Returns section is missing or incorrectly formatted. Follow Google style convention."
        )

    diff = get_tool_return_diff(parsed_returns, tool_return)
    if diff:
        parsed_desc, tool_desc = diff
        return (
            f"Returns section description differs from tool specification.\n"
            f"Expected: {tool_desc}\nFound:    {parsed_desc}"
        )

    raw_diff = get_raw_vs_tool_desc(python_tool, tool_return)
    if raw_diff:
        raw_desc, tool_desc = raw_diff
        return (
            "Raw Returns section differs from tool specification (possible indentation issue).\n"
            f"Expected: {tool_desc}\nFound:    {raw_desc}"
        )

    return ""


# ===============================
# MAIN VALIDATOR
# ===============================


def get_parsed_docstring(python_tool: PythonTool) -> Optional[docstring_parser.Docstring]:
    """Parse the docstring of a given PythonTool's function using docstring_parser - function used by orchestrate"""
    return docstring_parser.parse(python_tool.fn.__doc__) if python_tool.fn.__doc__ else None


def validate_google_style_docstring(python_tool: PythonTool) -> DocstringValidationResult:
    """
    Validate whether a PythonTool's function has a valid Google-style formatted docstring.

    This function checks:
    - Whether the docstring exists.
    - Whether the arguments in the docstring match the tool's input schema.
    - Whether the returns section in the docstring is correctly formatted and consistent with the tool's output schema.

    Args:
        python_tool (PythonTool): The tool whose docstring is to be validated.

    Returns:
        DocstringValidationResult: An object containing lists of argument errors, return section errors,
                                   and a flag indicating if the docstring is missing.
    """
    docstring_missing = False
    args_errors: List[ToolArgumentError] = []
    return_error = ""

    parsed_docstring = get_parsed_docstring(python_tool)
    if not parsed_docstring:
        docstring_missing = True
        return DocstringValidationResult(
            arguments_with_errors=args_errors,
            return_error=return_error,
            docstring_missing=docstring_missing,
        )

    args_errors = validate_args_section(python_tool, parsed_docstring)
    return_error = validate_returns_section(python_tool, parsed_docstring)

    return DocstringValidationResult(
        arguments_with_errors=args_errors,
        return_error=return_error,
        docstring_missing=docstring_missing,
    )

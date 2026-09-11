"""
Utility for generating mock files from tool call results.

This module provides functionality to:
1. Call a tool with specified arguments
2. Capture the response
3. Generate a Python mock file with @patch_tool_id decorator
"""

import inspect
import json
from pathlib import Path
from typing import Any, Dict, Optional, Set, Type

from ibm_watsonx_orchestrate.agent_builder.connections import ExpectedCredentials
from ibm_watsonx_orchestrate.agent_builder.connections.types import ConnectionType
from import_utils.connections.bearer_token import get_token_for_app_id
from import_utils.utils.directory import find_target_directory
from import_utils.utils.tools_data_mapper import ToolData, ToolsDataMap
from pydantic import BaseModel
import typer
import yaml

from agent_ready_tools.utils.credentials import CredentialKeys
from agent_ready_tools.utils.tool_credentials import get_system_from_credentials


class ToolCallConfig(BaseModel):
    """Config file for tool calls."""

    tool_name: str
    tool_args: dict


def _load_config(path: Path) -> ToolCallConfig:
    """Load JSON or YAML config file into a ToolCallConfig."""
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    if path.suffix.lower() in [".yml", ".yaml"]:
        with path.open("r") as f:
            return ToolCallConfig(**yaml.safe_load(f))
    elif path.suffix.lower() == ".json":
        with path.open("r") as f:
            return ToolCallConfig(**json.load(f))
    else:
        raise ValueError("Unsupported config file format. Use .yaml, .yml, or .json")


def _get_tool_module_path(tool_name: str) -> Optional[str]:
    """
    Get the module path for a tool by its name.

    Args:
        tool_name: Name of the tool

    Returns:
        Module path string or None if not found
    """
    tool = ToolsDataMap().get_tool_by_name(tool_name)
    if not tool:
        return None

    # Get the module where the tool function is defined
    module = inspect.getmodule(tool.object.fn)
    if module:
        return module.__name__
    return None


def _get_computed_field_names(value: Any) -> set:
    """
    Get the names of computed fields for a Pydantic model.

    Args:
        value: Pydantic model instance

    Returns:
        Set of computed field names
    """
    computed_fields = set()

    # Pydantic v2
    if hasattr(value, "model_computed_fields"):
        computed_fields = set(value.model_computed_fields.keys())
    # Pydantic v1 - computed fields are typically not in __fields__
    elif hasattr(value, "dict") and hasattr(value.__class__, "__fields__"):
        # Get all fields from dict() and subtract actual model fields
        all_fields = set(value.dict().keys())
        model_fields = set(value.__class__.__fields__.keys())
        computed_fields = all_fields - model_fields

    # Special case: ToolResponse always has is_success as a computed field
    # Ensure it's excluded even if not detected above
    if value.__class__.__name__ == "ToolResponse" and "is_success" not in computed_fields:
        computed_fields.add("is_success")

    return computed_fields


def _format_value_repr(value: Any, indent: int = 0) -> str:
    """
    Format a Python value into its string representation for code generation.

    Args:
        value: The value to format
        indent: Current indentation level for nested structures

    Returns:
        String representation of the value suitable for Python code
    """

    indent_str = "    " * indent
    next_indent_str = "    " * (indent + 1)

    # --- FIX: detect Pydantic models FIRST ---
    if isinstance(value, BaseModel):
        class_name = value.__class__.__name__
        data = value.__dict__

        computed = _get_computed_field_names(value)

        fields = []
        for key, val in data.items():
            if key not in computed:
                fields.append(f"{next_indent_str}{key}={_format_value_repr(val, indent + 1)}")

        if not fields:
            return f"{class_name}()"

        return f"{class_name}(\n" + ",\n".join(fields) + f"\n{indent_str})"

    # --- existing logic continues ---
    if value is None:
        return "None"
    elif isinstance(value, str):
        return f'"{value}"'
    elif isinstance(value, (int, float, bool)):
        return str(value)
    elif isinstance(value, list):
        if not value:
            return "[]"
        items = [_format_value_repr(item, indent + 1) for item in value]
        if len(items) == 1 and len(items[0]) < 50:
            return f"[{items[0]}]"
        return "[\n" + ",\n".join(f"{next_indent_str}{item}" for item in items) + f"\n{indent_str}]"
    elif isinstance(value, dict):
        if not value:
            return "{}"
        items = [
            f"{next_indent_str}{_format_value_repr(k)}: {_format_value_repr(v, indent + 1)}"
            for k, v in value.items()
        ]
        return "{\n" + ",\n".join(items) + f"\n{indent_str}}}"

    # fallback for arbitrary objects
    elif hasattr(value, "__dict__"):
        class_name = value.__class__.__name__
        fields = [
            f"{next_indent_str}{k}={_format_value_repr(v, indent + 1)}"
            for k, v in value.__dict__.items()
        ]
        return f"{class_name}(\n" + ",\n".join(fields) + f"\n{indent_str})"

    return repr(value)


def _collect_pydantic_classes(value: Any) -> set[Any]:
    """
    Recursively collect all Pydantic model classes from a value.

    Args:
        value: Any value that may contain Pydantic models (directly, in lists, dicts, or nested objects)

    Returns:
        Set of Pydantic BaseModel classes found in the value tree
    """

    all_classes: set[Any] = set()

    def recurse_collect(value: Any, classes: Set[Type[BaseModel]]) -> None:

        # Case 1: the value itself is a Pydantic model
        if (
            isinstance(value, BaseModel)
            or hasattr(value.__class__, "__pydantic_decorated__")
            or hasattr(value, "__pydantic_core_schema__")
        ):
            classes.add(value.__class__)
            # Recurse on fields
            for v in value.__dict__.values():
                recurse_collect(v, classes)

        # Case 2: list -> recurse each item
        elif isinstance(value, list):
            for item in value:
                recurse_collect(item, classes)

        # Case 3: dict -> recurse into values
        elif isinstance(value, dict):
            for v in value.values():
                recurse_collect(v, classes)

        # Case 4: arbitrary python object with attributes
        elif hasattr(value, "__dict__"):
            for v in value.__dict__.values():
                recurse_collect(v, classes)

        # Else: primitive → nothing to collect

    recurse_collect(value, all_classes)
    return all_classes


def _update_access_token_for_tool(tool: ToolData) -> None:
    """Update the access token for the given tool."""
    credentials_path = find_target_directory("agent_ready_tools") / "utils" / "credentials.json"
    if not credentials_path.exists():
        raise FileNotFoundError(f"Could not find credentials file.")
    try:
        oauth_credentials: list[ExpectedCredentials] = [
            cred
            for cred in tool.object.expected_credentials
            if cred.type == ConnectionType.OAUTH2_AUTH_CODE
        ]

        for cred in oauth_credentials:
            app_id = cred.app_id
            typer.echo(f"  Getting OAuth2 connection for app_id: {app_id}")
            access_token = get_token_for_app_id(app_id)
            if access_token is None:
                raise ValueError(
                    f"Access token is None. Failed to get access token for app_id: {app_id}"
                )

            systems = get_system_from_credentials(cred)

            # Update credentials.json with the new bearer token
            with credentials_path.open("r") as f:
                credentials = json.load(f)

            # Update the bearer token for this connection
            for system in systems:
                # subsystem
                if system[1] is not None:
                    system_value = system[0].value
                    sub_system = system[1]
                    credentials[system_value][sub_system][
                        CredentialKeys.BEARER_TOKEN
                    ] = access_token
                else:
                    system_value = system[0]
                    credentials[system_value.value][CredentialKeys.BEARER_TOKEN] = access_token

                typer.echo(f"  Updated bearer token for {app_id}")

            # Write back to file
            with credentials_path.open("w") as f:
                json.dump(credentials, f, indent=2)
            break  # Only process first credential with app_id
    except Exception as e:  # pylint: disable=broad-except
        typer.echo(f"Error: Could not update bearer token: {e}")
        raise e


def _call_tool_and_generate_mock(tool: ToolData, tool_args: Dict[str, Any]) -> Optional[str]:
    """
    Call a tool with arguments and generate mock code from the result.

    Args:
        tool_name: Name of the tool to call
        tool_args: Arguments to pass to the tool

    Returns:
        Generated mock code string, or None if tool call failed
    """
    # Get tool module path for imports
    tool_module_path = _get_tool_module_path(tool.name)

    # Call the tool
    typer.echo(f"  Calling with args: {tool_args}")
    try:
        result = tool.object.fn(**tool_args)
        typer.echo(f"  Success! Result type: {type(result).__name__}")

        # Generate mock code
        mock_code = _generate_mock_code(tool.name, tool_args, result, tool_module_path)
        return mock_code

    except Exception as e:  # pylint: disable=broad-except
        typer.echo(f"  Error calling tool: {e}")
        return None


def _output_mock_code(
    mock_code: str, output_path: Optional[str] = None, num_fixtures: int = 1
) -> None:
    """
    Output generated mock code to file or stdout.

    Args:
        mock_code: The generated mock code
        output_path: Optional path to write the file. If None, prints to stdout.
        num_fixtures: Number of fixture functions generated (for reporting)
    """
    if output_path:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(mock_code)
        typer.echo(f"\n{'='*80}")
        typer.echo(f"Mock file written to: {output_path}")
        typer.echo(f"Generated {num_fixtures} fixture function(s)")
        typer.echo(f"{'='*80}")
    else:
        typer.echo("\n" + "=" * 80)
        typer.echo("Generated Mock Code:")
        typer.echo("=" * 80)
        typer.echo(mock_code)
        typer.echo("=" * 80)
        if num_fixtures > 1:
            typer.echo(f"Generated {num_fixtures} fixture function(s)")


def _generate_mock_code(
    tool_name: str,
    tool_args: Dict[str, Any],
    result: Any,
    tool_module_path: Optional[str] = None,
) -> str:
    """
    Generate Python mock code from a tool call result.

    Args:
        tool_name: Name of the tool
        tool_args: Arguments passed to the tool
        result: Result returned by the tool
        tool_module_path: Optional module path for imports

    Returns:
        Python code as a string
    """
    # Determine imports needed
    imports = ["from typing import Any"]

    # Add import for patch decorator
    imports.append("from agent_ready_tools.utils.tool_snapshot.patch import patch_tool_id")

    # Try to determine the response type and add import
    if hasattr(result, "__class__"):
        # Collect nested types to import
        if tool_module_path:
            # Collect unique class names from nested objects
            nested_classes = _collect_pydantic_classes(result)

            if nested_classes:
                for cls in nested_classes:
                    module = cls.__module__
                    class_name = cls.__name__
                    import_stmt = f"from {module} import {class_name}\n"
                    imports.append(import_stmt)

    # Build the decorator arguments
    decorator_args = [f'tool_name="{tool_name}"']
    if tool_args:
        # Format tool_kwargs
        kwargs_items = [f'"{k}": {_format_value_repr(v)}' for k, v in tool_args.items()]
        kwargs_str = "{" + ", ".join(kwargs_items) + "}"
        decorator_args.append(f"tool_kwargs={kwargs_str}")

    # Generate the function
    function_name = f"fixture_{tool_name}"

    # Determine return type with generic parameters if applicable
    if hasattr(result, "__class__"):
        return_type = result.__class__.__name__

        # Check if this is a generic type like ToolResponse[T]
        if (
            return_type == "ToolResponse"
            and hasattr(result, "tool_output")
            and result.tool_output is not None
        ):
            # Get the type of tool_output
            tool_output_type = result.tool_output.__class__.__name__
            return_type = f"ToolResponse[{tool_output_type}]"
    else:
        return_type = "Any"

    # Format the result
    result_repr = _format_value_repr(result, indent=1)

    # Build the complete code
    code_lines = imports + [
        "",
        "",
        f"@patch_tool_id({', '.join(decorator_args)})",
        f"def {function_name}(*args: Any, **kwargs: Any) -> {return_type}:",
        f'    """Mock fixture for {tool_name}."""',
        f"    return {result_repr}",
        "",
    ]

    return "\n".join(code_lines)


def generate_mock_from_config(config_path: str, output_path: Optional[str] = None) -> None:
    """
    Generate a mock file from a tool call config (YAML/JSON).

    Args:
        config_path: Path to the tool call config YAML/JSON file
        output_path: Optional path to write the generated mock file
    """
    # Load config
    cfg = _load_config(Path(config_path))
    tool_name = cfg.tool_name
    tool_args = cfg.tool_args

    typer.echo(f"Calling {tool_name} with args {tool_args}...")

    # Get the tool
    tool = ToolsDataMap().get_tool_by_name(tool_name)
    if not tool:
        typer.echo(f"  Warning: Tool '{tool_name}' not found. Skipping.")
        return None

    # Handle updating any required token data
    _update_access_token_for_tool(tool)

    # Call tool and generate mock
    mock_code = _call_tool_and_generate_mock(tool, tool_args)

    if not mock_code:
        typer.echo(f"Error: Failed to generate mock for tool '{tool_name}'.")
        raise typer.Exit(code=1)

    # Output the code
    _output_mock_code(mock_code, output_path)
    return None


def generate_mock_from_test_case(test_case_path: str, output_path: Optional[str] = None) -> None:
    """
    Generate mock file(s) from an ADK test case JSON file.

    Extracts tool calls from goal_details and generates mocks for each.

    Args:
        test_case_path: Path to the ADK test case JSON file
        output_path: Optional path to write the generated mock file
    """
    test_file = Path(test_case_path)

    # Load the test case JSON
    with test_file.open("r") as f:
        test_case = json.load(f)

    # Extract tool calls from goal_details
    goal_details = test_case.get("goal_details", [])
    tool_calls = [detail for detail in goal_details if detail.get("type") == "tool_call"]

    if not tool_calls:
        typer.echo(f"No tool calls found in test case: {test_case_path}")
        return

    typer.echo(f"Found {len(tool_calls)} tool call(s) in test case")

    # Generate mocks for all tool calls
    all_mock_code = []

    for i, tool_call in enumerate(tool_calls, 1):
        tool_name = tool_call.get("tool_name")
        tool_args = tool_call.get("args", {})

        if not tool_name:
            typer.echo(f"Skipping tool call {i}: no tool_name specified")
            continue

        typer.echo(f"\n[{i}/{len(tool_calls)}] Processing tool: {tool_name}")

        # Get the tool
        tool = ToolsDataMap().get_tool_by_name(tool_name)
        if not tool:
            typer.echo(f"  Warning: Tool '{tool_name}' not found. Skipping.")
            continue

        # Handle updating any required token data
        _update_access_token_for_tool(tool)

        # Call tool and generate mock
        mock_code = _call_tool_and_generate_mock(tool, tool_args)

        if mock_code:
            all_mock_code.append(mock_code)

    if not all_mock_code:
        typer.echo("\nNo mocks generated successfully.")
        return

    # Combine all mocks into one file
    # Collect all unique imports
    all_imports = set()
    all_functions = []

    for code in all_mock_code:
        lines = code.split("\n")
        imports = []
        function_lines = []
        in_imports = True

        for line in lines:
            if in_imports and (
                line.startswith("from ") or line.startswith("import ") or line.strip() == ""
            ):
                if line.strip():
                    imports.append(line)
            else:
                in_imports = False
                function_lines.append(line)

        all_imports.update(imports)
        all_functions.append("\n".join(function_lines).strip())

    # Build final code
    final_code = "\n".join(sorted(all_imports)) + "\n\n\n" + "\n\n\n".join(all_functions) + "\n"

    # Output the code
    _output_mock_code(final_code, output_path, num_fixtures=len(all_functions))

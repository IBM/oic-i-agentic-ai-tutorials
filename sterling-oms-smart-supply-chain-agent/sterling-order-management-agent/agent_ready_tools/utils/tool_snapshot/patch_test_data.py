"""
Patch Data file example/used for testing.

Notes:
    - patcher will pass all (*args: Any, **kwargs: Any) through as if running production code.
        - Either add the same (*args: Any, **kwargs: Any) signature.
        - Or match the arg signature with the original tool you are patching.
        - You can also have a mix of (required_arg, *args: Any, **kwargs: Any) as well.

    - Dynamic search of "fixture" is reliant on the use of the @patch_too_id decorator.
        - Any helper functions without the decorator will be ignored.

    - Patch data module will be added to the ToolsRuntime deliverables
        - Imports limited to the `agent_ready_tools` space.
        - Any other imports will cause an ImportError. e.g. `import agent_validation` will fail.

    - CAUTION: There is no validation on whether the response return type is the same as for the tool.
        - e.g. `get_email_types_oracle` expected return type is `ToolResponse`
               but you can return an `EmailTypeResponse` instead.
        - Use the same return type as the original tool.
"""

import dataclasses
from typing import Any

from agent_ready_tools.tools.hr.employee_support.oracle_hcm.get_email_types import (
    EmailTypeResponse,
    EmailTypes,
)
from agent_ready_tools.tools.tool_response import ToolResponse
from agent_ready_tools.utils.tool_snapshot.patch import patch_tool_id


@patch_tool_id(tool_name="get_email_types_oracle", tool_kwargs={})
def get_email_types_mock_data() -> ToolResponse[Any]:
    """
    Patch data for get_email_types_oracle for testing.

    Returns:
        ToolResponse similar to what we will see in get_email_types_oracle.
    """

    return ToolResponse(
        error_details=None,
        tool_output=EmailTypeResponse(
            email_types=[
                EmailTypes(
                    email_type_code="1",
                    email_type_name="type 1",
                ),
                EmailTypes(
                    email_type_code="2",
                    email_type_name="type 2",
                ),
            ]
        ),
    )


@dataclasses.dataclass
class MockResponse:
    """Simple Mock Response dataclass to build out valid `ToolResponse` object."""

    msg: str


@patch_tool_id(tool_name="mock_tool_patched_success", tool_kwargs={})
def mock_tool_patched_success_shouldnt_match(*args: Any, **kwargs: Any) -> ToolResponse[Any]:
    """
    Base case for matching, no kwargs but should be a search parameter.

    Args:
        args: args for the original `__call__` function.
        kwargs: kwargs for the original `__call__` function.

    Returns:
        ToolResponse
    """
    return ToolResponse(error_details=None, tool_output=MockResponse(msg="original response"))


@patch_tool_id(tool_name="mock_tool_patched_success", tool_kwargs={"arg_one": 1, "arg_two": 2})
def mock_tool_patched_success_match(*args: Any, **kwargs: Any) -> ToolResponse[Any]:
    """
    Fixture for a kwarg matching through the decorator.

    Args:
        args: args for the original `__call__` function.
        kwargs: kwargs for the original `__call__` function.

    Returns:
        ToolResponse
    """
    return ToolResponse(error_details=None, tool_output=None)


@patch_tool_id(tool_name="mock_tool_patched_signature_test", tool_kwargs={"arg_one": 1})
def mock_tool_patched_signature_test_should_fail() -> ToolResponse[Any]:
    """
    Fixture for a mismatching function signature, should fail since it is expected to pass args in.

    Returns:
        ToolResponse
    """
    return ToolResponse(error_details=None, tool_output=MockResponse(msg="original response"))


@patch_tool_id(tool_name="mock_tool_kwargs_match_priority")
def mock_tool_no_kwargs_requirement(*args: Any, **kwargs: Any) -> ToolResponse[Any]:
    """
    A fixture used to test prioritization during fixture discovery. When included in a priority
    test, it should appear last in the search order and must not be selected, because higher-
    priority fixtures define keyword arguments in their decorators.

    Args:
        args: args passthrough
        kwargs: kwargs passthrough

    Returns:
        ToolResponse
    """
    return ToolResponse(error_details=None, tool_output=MockResponse(msg="error"))


@patch_tool_id(tool_name="mock_tool_kwargs_match_priority", tool_kwargs={"arg_one": 1})
def mock_tool_kwargs_priority(*args: Any, **kwargs: Any) -> ToolResponse[Any]:
    """
    Fixture for a partial kwargs signature match. Should pass due to matching values. Ignore any
    kwargs not defined in decorator.

    Args:
        args: args passthrough
        kwargs: kwargs passthrough

    Returns:
        ToolResponse
    """
    return ToolResponse(error_details=None, tool_output=MockResponse(msg="original response"))


@patch_tool_id(tool_name="mock_tool_match_no_kwargs")
def mock_tool_kwargs_priority_optional_non_match(*args: Any, **kwargs: Any) -> ToolResponse[Any]:
    """
    Fixture for a partial kwargs signature match. Should fail due to mismatching values. Ignore any
    kwargs not defined in decorator.

    Args:
        args: args passthrough
        kwargs: kwargs passthrough

    Returns:
        ToolResponse
    """
    return ToolResponse(error_details=None, tool_output=MockResponse(msg="original response"))

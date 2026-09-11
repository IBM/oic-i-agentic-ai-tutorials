import inspect
import types
from typing import Any
from unittest.mock import patch

from ibm_watsonx_orchestrate.agent_builder.connections import ConnectionType, ExpectedCredentials
from ibm_watsonx_orchestrate.agent_builder.tools import tool
from import_utils.utils.directory import find_target_directory
import pytest

from agent_ready_tools.tools.hr.employee_support.oracle_hcm.get_email_types import (
    EmailTypeResponse,
    EmailTypes,
    get_email_types_oracle,
)
from agent_ready_tools.tools.tool_response import ToolResponse
from agent_ready_tools.utils.tool_snapshot.patch import (
    find_patched_function,
    patch_expected_credentials,
    patch_python_tool_call_func,
    patch_tool_id,
)
from agent_ready_tools.utils.tool_snapshot.patch_test_data import MockResponse

_pants_dir = find_target_directory("agent_ready_tools") / "utils" / "tool_snapshot"
PATCH_DATA_FILEPATH = str(_pants_dir / "patch_test_data.py")
EXPECTED_EMPTY_RESPONSE: ToolResponse[Any] = ToolResponse(error_details=None, tool_output=None)
SUCCESSFUL_RESPONSE = ToolResponse(
    error_details=None, tool_output=MockResponse(msg="original response")
)


def test_patching_tool_response() -> None:
    """
    Test that the tool is correctly patched. Two conditions must be satisfied:

    - The patched tool with the same name is found
    - The patched tool expects the same arguments
    """

    with patch_python_tool_call_func(PATCH_DATA_FILEPATH):

        _expected_response = ToolResponse(
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

        result = get_email_types_oracle()

        assert result == _expected_response, "Patcher didn't work."


def test_patched_func_parameters_search_failure() -> None:
    """Test if and when parameters search fails."""

    @tool
    def mock_tool_patched_failure(arg_one: int, arg_two: int) -> ToolResponse[Any]:
        """Mock tool for testing."""
        return ToolResponse(error_details=None, tool_output=MockResponse(msg="Failed"))

    with patch_python_tool_call_func(PATCH_DATA_FILEPATH):
        expected_partial_message = "No matching patch function."
        try:
            mock_tool_patched_failure(1, arg_two=2)
        except KeyError as ke:
            if expected_partial_message not in str(ke):
                raise


def test_patched_func_parameters_search_success() -> None:
    """
    Test if and when parameters search succeeds.

    - Tests the binding of any loose args to a kwarg in the arg signature.
    - Tests the binding of any default args to kwargs in the arg signature.
    - Tests that matching does work and returns the proper response.
    """

    @tool
    def mock_tool_patched_success(arg_one: int = 1, arg_two: int = 2) -> ToolResponse[Any]:
        """Mock tool for testing."""
        return ToolResponse(error_details=None, tool_output=MockResponse(msg="Failed"))

    with patch_python_tool_call_func(PATCH_DATA_FILEPATH):
        result = mock_tool_patched_success(1, arg_two=2)
        assert result == EXPECTED_EMPTY_RESPONSE, "Patcher arg signature matching didn't work."

    with patch_python_tool_call_func(PATCH_DATA_FILEPATH):
        resp = mock_tool_patched_success()
        assert resp == EXPECTED_EMPTY_RESPONSE, "Patcher default args to kwargs didn't work."


def test_patched_func_data_arg_mismatch() -> None:
    """
    Expecting a failure from the args not matching between the fixture and the original tool call
    func.

    args in the function signature, not the decorator.
    """

    @tool
    def mock_tool_patched_signature_test(arg_one: int) -> ToolResponse[Any]:
        """Mock tool for testing."""
        return ToolResponse(error_details=None, tool_output=MockResponse(msg="Failed"))

    with patch_python_tool_call_func(PATCH_DATA_FILEPATH):
        expected_err_msg = r"mock_tool_patched_signature_test_should_fail\(\) takes 0 positional arguments but 1 was given"
        with pytest.raises(TypeError, match=expected_err_msg):
            mock_tool_patched_signature_test(1)


def test_triple_patching() -> None:
    """Test in case of multiple patching due to broad target file searching, should work as
    intended."""

    @tool
    def mock_tool_patched_success(arg_one: int = 1, arg_two: int = 2) -> ToolResponse[Any]:
        """Mock tool for testing."""
        return ToolResponse(error_details=None, tool_output=MockResponse(msg="Failed"))

    with patch_python_tool_call_func(PATCH_DATA_FILEPATH):
        with patch_python_tool_call_func(PATCH_DATA_FILEPATH):
            with patch_python_tool_call_func(PATCH_DATA_FILEPATH):
                resp = mock_tool_patched_success()
                assert (
                    resp == EXPECTED_EMPTY_RESPONSE
                ), "Patcher default args to kwargs didn't work."


def test_loosen_kwargs_match_for_fixture_search() -> None:
    """
    Test to make sure fixtures in `patch_test_data.py` prioritizes functions with kwargs
    requirements before functions without kwargs requirements.

    Also tests that any non-defined kwargs are optional and don't affect the matching.

    Requirements are defined in the decorator's `tool_kwargs` argument.
    """

    @tool
    def mock_tool_kwargs_match_priority(arg_one: int, arg_two: int) -> ToolResponse[Any]:
        """Mock tool for testing."""
        return ToolResponse(error_details=None, tool_output=MockResponse(msg="Failed"))

    with patch_python_tool_call_func(PATCH_DATA_FILEPATH):
        resp = mock_tool_kwargs_match_priority(arg_one=1, arg_two=2)
        assert resp == SUCCESSFUL_RESPONSE, "Patcher kwargs match didn't work."


def test_match_on_decorated_fixture_with_no_kwargs_requirements() -> None:
    """Test the matching up of a fixture function that doesn't have a kwargs requirements even
    though arguments are passed in."""

    @tool
    def mock_tool_match_no_kwargs(arg_one: int, arg_two: int) -> ToolResponse[Any]:
        """Mock tool for testing."""
        return ToolResponse(error_details=None, tool_output=MockResponse(msg="Failed"))

    with patch_python_tool_call_func(PATCH_DATA_FILEPATH):
        resp = mock_tool_match_no_kwargs(arg_one=1, arg_two=2)
        assert resp == SUCCESSFUL_RESPONSE, "Patcher kwargs match didn't work."


def test_patched_function_finder() -> None:
    """
    Test `find_patched_function`.

    Should match on function that is decorated with `@patch_tool_id`. Even though tool_kwargs has 2
    kwargs, the decorator only lists once, but should still match. Even though one of the fixtures
    has no `tool_kwargs` (accepts any tool_kwargs). Should be     ignored due to priority search on
    fixtures with tool_kwargs requirements.
    """

    # Create a mock module instead of importing the real patch_data module
    mock_patch_data_module = types.ModuleType("mock_patch_data")

    @patch_tool_id(tool_name="target_dummy_fixture", tool_kwargs={"arg_one": 1})
    def target_dummy_fixture() -> None:
        pass

    @patch_tool_id(tool_name="target_dummy_fixture")
    def dont_match_priority() -> None:
        pass

    def should_be_ignored_during_search() -> None:
        """Dummy function that should be ignored during the search for patch fixture functions."""

    patcher = patch.object(
        target=inspect,
        attribute="getmembers",
        return_value=[
            (None, should_be_ignored_during_search),
            (None, target_dummy_fixture),
            (None, dont_match_priority),
        ],
    )
    patcher.start()

    found_fn = find_patched_function(
        patch_data_module=mock_patch_data_module,
        tool_name="target_dummy_fixture",
        tool_kwargs={"arg_one": 1, "arg_two": 2},
    )

    assert found_fn.__name__ == "target_dummy_fixture" == target_dummy_fixture.__name__

    patcher.stop()


def test_patch_connections() -> None:
    """
    Test the PythonTools' connection patcher.

    Regardless of which ExpectedCredentials is passed in, the PythonTool object's
    expected_credentials should be an empty list, as-if the tool does not need a connection.
    """

    dummy_creds = ExpectedCredentials(app_id="DummyConn", type=ConnectionType.BASIC_AUTH.value)

    # Create tool with credentials BEFORE patching
    @tool(expected_credentials=[dummy_creds])
    def dummy_tool_before() -> bool:
        return True

    # Verify tool has credentials before patching
    assert hasattr(dummy_tool_before, "expected_credentials")
    assert len(dummy_tool_before.expected_credentials) == 1
    assert dummy_tool_before.expected_credentials[0].app_id == "DummyConn"

    # Apply the patch
    with patch_expected_credentials():
        # Create tool with credentials DURING patching
        @tool(expected_credentials=[dummy_creds])
        def dummy_tool_patched() -> bool:
            return True

        # Verify the patch worked - expected_credentials should be empty
        assert hasattr(dummy_tool_patched, "expected_credentials")
        assert dummy_tool_patched.expected_credentials == []
        assert len(dummy_tool_patched.expected_credentials) == 0

    # After exiting context, verify patch is removed
    @tool(expected_credentials=[dummy_creds])
    def dummy_tool_after() -> bool:
        return True

    assert len(dummy_tool_after.expected_credentials) == 1
    assert dummy_tool_after.expected_credentials[0].app_id == "DummyConn"


def test_patch_connections_patcher_after_interpretation() -> None:
    """
    Test the PythonTools' connection patcher will not work if patching occurs after interpretation.

    This is because the code is run during the decoration of the function, so the patching has to
    occur before the tool definition.
    """

    dummy_creds = ExpectedCredentials(app_id="DummyConn", type=ConnectionType.BASIC_AUTH.value)

    # Create tool with credentials BEFORE patching
    @tool(expected_credentials=[dummy_creds])
    def dummy_tool() -> bool:
        return True

    # Verify tool has credentials before patching
    assert hasattr(dummy_tool, "expected_credentials")
    assert len(dummy_tool.expected_credentials) == 1
    assert dummy_tool.expected_credentials[0].app_id == "DummyConn"

    # After patching, credentials should still appear. Patching occurred too late.
    with patch_expected_credentials():
        assert hasattr(dummy_tool, "expected_credentials")
        assert dummy_tool.expected_credentials[0].app_id == "DummyConn"

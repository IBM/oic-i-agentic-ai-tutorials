from pathlib import Path

from import_utils.utils.directory import find_target_directory
from import_utils.validation.dependency_mapper import (
    DepMapperOutputObject,
    agent_tool_dependency_mapper,
    instructions_tokenizer,
    primitive_dependency_mapping,
    yaml_processor,
)
import pytest


class YamlTestData:
    """Defining the test data from the test_agent.yaml that is used in the dependency mapper
    tests."""

    agent_name = "sap_compensation_agent"
    instructions = "**How To Use Tools**\n- When the user asks for their recent payslips, use the get_payslip_details tool to retrieve the data.\n- When the user asks about their overall compensation and pay, use the get_current_compensation_details_sap\n  tool to retrieve the data.\n\n- When the user asks about the benefits plan they are enrolled in, use the get_benefits_plan tool to retrieve the data.\n- To obtain user ID or user external ID use the get_user_successfactors_ids tool. Call this tool only with an email address provided by the user. If the user provided an ID, there is no need to use this tool. If the tool returns None inform the user that no user was found for the provided email address.\n"
    tools = [
        "get_user_successfactors_ids",
        "get_payslip_details",
        "get_current_compensation_details_sap",
        "get_benefits_plan",
    ]


def test_yaml_processor() -> None:
    """Test helper function yaml_processor."""
    test_data_file = Path("./import_utils/validation/test_data/test_agent.yaml")
    result = yaml_processor(file_path=test_data_file)

    assert result.agent_name_data == YamlTestData.agent_name
    assert result.instructions_data == YamlTestData.instructions
    assert result.tools_data == YamlTestData.tools


def test_instructions_tokenizer() -> None:
    """Test helper function instructions_tokenizer with test_agent.yaml file data."""
    result = instructions_tokenizer(
        tokens=YamlTestData.tools, instructions=YamlTestData.instructions
    )

    assert result
    assert result == {
        "get_benefits_plan",
        "get_payslip_details",
        "get_user_successfactors_ids",
        "get_current_compensation_details_sap",
    }


def test_agent_tool_dependency_mapper() -> None:
    """Test function agent_tool_dependency_mapper against test_agent.yaml file data."""
    result = agent_tool_dependency_mapper(Path("import_utils"))

    assert result
    result1 = result[0]
    assert isinstance(result1, DepMapperOutputObject)
    assert result1.agent_name == "sap_compensation_agent"
    difference = set(result1.internal_agent_tools) ^ set(YamlTestData.tools)
    assert not difference
    assert result1.external_agent_tools == []


# TODO: Don't use live code for testing, create temp files to run test.
def test_map_tool_with_dependencies() -> None:
    """
    Tools with dependencies will return a list of files that are imported by tool.

    This is built by recursively checking the dependants for any grandchildren dependencies.
    """
    target_dir = find_target_directory("agent_ready_tools")
    tool_with_deps_path = (
        "agent_ready_tools/tools/procurement/invoice_support/coupa/invoice_po_matching.py"
    )
    tool_abspath = Path(tool_with_deps_path).resolve()

    dep_manifest = primitive_dependency_mapping(
        target_dir=target_dir, tool_py_filepath=tool_abspath
    )

    assert dep_manifest


# TODO: Fix test when we have properly set up this test file to work with mocks or test env.
@pytest.mark.xfail(
    reason="Expanded scope of the dep mapper to include other dirs in agent_ready_tools."
)
def test_map_tool_without_dependencies() -> None:
    """Tools without dependencies will return an empty list."""
    target_dir = find_target_directory("agent_ready_tools")
    tool_no_deps_path = (
        "agent_ready_tools/tools/hr/employee_support/sap_successfactors/get_benefits_plan.py"
    )
    tool_abspath = Path(tool_no_deps_path).resolve()

    dep_manifest = primitive_dependency_mapping(
        target_dir=target_dir, tool_py_filepath=tool_abspath
    )

    assert dep_manifest == []

import datetime
from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch

from ibm_watsonx_orchestrate.agent_builder.agents import AgentKind, AgentStyle, SpecVersion
from ibm_watsonx_orchestrate.agent_builder.connections import ConnectionType, ExpectedCredentials
from ibm_watsonx_orchestrate.agent_builder.tools import PythonTool, ToolPermission, ToolSpec
from ibm_watsonx_orchestrate.agent_builder.tools.types import PythonToolBinding, ToolBinding
from import_utils.catalog.agent_config_data import AgentConfigBuilder
from import_utils.catalog.applications_config_data import ApplicationsConfigBuilder
from import_utils.catalog.export_catalog_cmd import DEFAULT_PUBLISHER_NAME
from import_utils.catalog.metadata.catalog_metadata import (
    AgentMetadata,
    ApplicationMetadata,
    CatalogMetadata,
    OfferingMetadata,
    ToolMetadata,
)
from import_utils.catalog.offering_config_data import OfferingConfigBuilder
from import_utils.catalog.release_config_data import CollaboratorPath, ReleaseConfigData
from import_utils.catalog.tool_config_data import ToolConfigBuilder
from import_utils.catalog.types import (
    DEFAULT_DELETE_BY_DATE,
    DEFAULT_LANGUAGES_SUPPORTED,
    MISSING_VALUE_SENTINEL,
    AgentConfigSpec,
    AgentRoleName,
    ApplicationsSpec,
    AssetsSpec,
    CategoryName,
    DomainName,
    FormFactorSpec,
    OfferingConfigSpec,
    PartNumberSpec,
    PricingFrequencyType,
    PricingSpec,
    PricingType,
    PublisherName,
    ScopeSpec,
    TenantTypeSpec,
    ToolConfigSpec,
)
from import_utils.tool_importer.agent_yamls_data import AgentYamlsData
from import_utils.utils.tools_data_mapper import ToolData
import more_itertools
from pydantic_extra_types.semantic_version import SemanticVersion  # pants: no-infer-dep
import pytest

TEST_MANAGER_FILEPATH = Path(
    "./import_utils/catalog/test_data/collaborator_agents/hr/employee_support/test_1_manager.yaml"
)

TEST_COLLABORATOR_FILEPATH = Path(
    "./import_utils/catalog/test_data/collaborator_agents/hr/employee_support/test_1_collaborator_agent.yaml"
)

TEST_COLLABORATOR_DIRPATH = Path("./import_utils/catalog/test_data/collaborator_agents")

TOOL_PACKAGE_ROOT = "agent_ready_tools"

TEST_VERSION = SemanticVersion.parse("1.2.3")

_tool_spec1 = ToolSpec(
    name="test_spec_1",
    description="This is tool 1",
    permission=ToolPermission.READ_ONLY,
    binding={
        "python": {
            "function": f"{TOOL_PACKAGE_ROOT}.test:test_tool_1",
            "requirements": ["some_lib:1.0.0"],
        }
    },
)

_tool_spec2 = ToolSpec(
    name="test_spec_2",
    description="This is tool 2",
    permission=ToolPermission.READ_ONLY,
    binding={
        "python": {
            "function": f"{TOOL_PACKAGE_ROOT}.test:test_tool_2",
            "requirements": ["some_lib:1.0.0"],
        }
    },
)

_tool_no_expected_creds_tool = ToolSpec(
    name="test_no_expected_creds_tool",
    description="This is a tool with no EXPECTED_CREDENTIALS specified",
    permission=ToolPermission.READ_ONLY,
    binding={
        "python": {
            "function": f"{TOOL_PACKAGE_ROOT}.test:test_no_expected_creds_tool",
            "requirements": ["some_lib:1.0.0"],
        }
    },
)


TEST_EXPECTED_CREDENTIALS = [
    ExpectedCredentials(app_id="test_app_id_1", type=ConnectionType.API_KEY_AUTH),
    ExpectedCredentials(app_id="test_app_id_2", type=ConnectionType.API_KEY_AUTH),
]

TEST_TOOLS = {
    "test_tool_1": ToolData(
        name="test_tool_1",
        module_name="test_module_1",
        file_path=Path(f"{TOOL_PACKAGE_ROOT}/test/test_tool_1.py"),
        object=PythonTool(
            fn=f"{TOOL_PACKAGE_ROOT}.test:test_tool_1",
            spec=_tool_spec1,
            expected_credentials=TEST_EXPECTED_CREDENTIALS,
        ),
    ),
    "test_tool_2": ToolData(
        name="test_tool_2",
        module_name="test_module_2",
        file_path=Path(f"{TOOL_PACKAGE_ROOT}/test/test_tool_2.py"),
        object=PythonTool(
            fn=f"{TOOL_PACKAGE_ROOT}.test:test_tool_2",
            spec=_tool_spec2,
            expected_credentials=TEST_EXPECTED_CREDENTIALS,
        ),
    ),
    "test_no_expected_creds_tool": ToolData(
        name="test_no_expected_creds_tool",
        module_name="test_module_3",
        file_path=Path(f"{TOOL_PACKAGE_ROOT}/test/test_no_expected_creds_tool.py"),
        object=PythonTool(
            fn=f"{TOOL_PACKAGE_ROOT}.test:test_no_expected_creds_tool",
            spec=_tool_no_expected_creds_tool,
            expected_credentials=[],
        ),
    ),
}


TEST_APPLICATIONS = [
    ApplicationsSpec(
        app_id="test_app_id_1",
        name="test_name_1",
        description="test_description_1",
        icon="test_svg_1",
    ),
    ApplicationsSpec(
        app_id="test_app_id_2",
        name="test_name_2",
        description="test_description_2",
        icon="test_svg_2",
    ),
]

TEST_OFFERING_CONFIG_1_GT = {
    "name": "hr_employee_support_1",
    "display_name": MISSING_VALUE_SENTINEL,
    "domain": DomainName.HR,
    "publisher": DEFAULT_PUBLISHER_NAME,
    "version": str(TEST_VERSION),
    "description": MISSING_VALUE_SENTINEL,
    "assets": {
        DEFAULT_PUBLISHER_NAME: {
            "agents": ["test_1_collaborator_agent", "test_1_manager"],
            "tools": ["test_tool_1", "test_tool_2"],
        }
    },
    "part_number": {"aws": None, "ibm_cloud": None, "cp4d": None},
    "scope": {
        "form_factor": {"aws": "paid", "ibm_cloud": "paid", "cp4d": "paid"},
        "tenant_type": {"trial": "paid"},
    },
    "pricing": {"currency": "USD", "amount": "100.00", "frequency": "monthly"},
    "delete_by": DEFAULT_DELETE_BY_DATE,
}

TEST_OFFERING_CONFIG_2_GT = {
    "name": "hr_employee_support_2",
    "display_name": MISSING_VALUE_SENTINEL,
    "domain": DomainName.HR,
    "publisher": DEFAULT_PUBLISHER_NAME,
    "version": str(TEST_VERSION),
    "description": MISSING_VALUE_SENTINEL,
    "assets": {
        DEFAULT_PUBLISHER_NAME: {
            "agents": ["test_2_collaborator_agent", "test_2_manager"],
            "tools": ["test_tool_1"],
        }
    },
    "part_number": {"aws": None, "ibm_cloud": None, "cp4d": None},
    "scope": {
        "form_factor": {"aws": "paid", "ibm_cloud": "paid", "cp4d": "paid"},
        "tenant_type": {"trial": "paid"},
    },
    "pricing": {"currency": "USD", "amount": "100.00", "frequency": "monthly"},
    "delete_by": DEFAULT_DELETE_BY_DATE,
}

TEST_COLLABORATOR_CONFIG_1_GT = {
    "name": "test_1_collaborator_agent",
    "display_name": MISSING_VALUE_SENTINEL,
    "category": CategoryName.AGENT,
    "agent_role": AgentRoleName.COLLABORATOR,
    "kind": AgentKind.NATIVE,
    "description": "Collaborator agent 1 for use in unit tests.",
    "instructions": "Lorem ipsum dolor sit amet...",
    "tools": ["test_tool_1", "test_tool_2"],
    "collaborators": [],
    "llm": "watsonx/meta-llama/llama-3-2-90b-vision-instruct",
    "style": AgentStyle.DEFAULT,
    "glossary": [],
    "chat_with_docs": None,
    "context_access_enabled": True,
    "context_variables": [],
    "custom_join_tool": None,
    "id": None,
    "spec_version": SpecVersion.V1,
    "starter_prompts": None,
    "structured_output": None,
    "welcome_content": None,
    "guidelines": [],
    "knowledge_base": [],
    "publisher": DEFAULT_PUBLISHER_NAME,
    "supported_apps": [],
    "hidden": False,
    "tags": [DomainName.HR],
    "language_support": DEFAULT_LANGUAGES_SUPPORTED,
    "delete_by": DEFAULT_DELETE_BY_DATE,
    "voice_configuration": None,
    "voice_configuration_id": None,
}

TEST_MANAGER_CONFIG_1_GT = {
    "name": "test_1_manager",
    "display_name": MISSING_VALUE_SENTINEL,
    "category": CategoryName.AGENT,
    "agent_role": AgentRoleName.MANAGER,
    "kind": AgentKind.NATIVE,
    "description": "Test manager agent 1 for use in unit tests.",
    "instructions": "Lorem ipsum dolor sit amet...",
    "tools": [],
    "collaborators": ["test_1_collaborator_agent"],
    "llm": "watsonx/meta-llama/llama-3-2-90b-vision-instruct",
    "style": AgentStyle.DEFAULT,
    "glossary": [],
    "chat_with_docs": None,
    "context_access_enabled": True,
    "context_variables": [],
    "custom_join_tool": None,
    "id": None,
    "spec_version": SpecVersion.V1,
    "starter_prompts": None,
    "structured_output": None,
    "welcome_content": None,
    "guidelines": [],
    "knowledge_base": [],
    "hidden": False,
    "publisher": DEFAULT_PUBLISHER_NAME,
    "supported_apps": [],
    "tags": [DomainName.HR],
    "language_support": DEFAULT_LANGUAGES_SUPPORTED,
    "delete_by": DEFAULT_DELETE_BY_DATE,
    "voice_configuration": None,
    "voice_configuration_id": None,
}

TEST_COLLABORATOR_CONFIG_2_GT = {
    "name": "test_2_collaborator_agent",
    "display_name": MISSING_VALUE_SENTINEL,
    "category": CategoryName.AGENT,
    "agent_role": AgentRoleName.COLLABORATOR,
    "kind": AgentKind.NATIVE,
    "description": "Collaborator agent 2 for use in unit tests.",
    "instructions": "Lorem ipsum dolor sit amet...",
    "tools": ["test_tool_1"],
    "collaborators": [],
    "llm": "watsonx/meta-llama/llama-3-2-90b-vision-instruct",
    "style": AgentStyle.DEFAULT,
    "glossary": [],
    "chat_with_docs": None,
    "context_access_enabled": True,
    "context_variables": [],
    "custom_join_tool": None,
    "id": None,
    "spec_version": SpecVersion.V1,
    "starter_prompts": None,
    "structured_output": None,
    "welcome_content": None,
    "guidelines": [],
    "knowledge_base": [],
    "publisher": DEFAULT_PUBLISHER_NAME,
    "supported_apps": [],
    "hidden": False,
    "tags": [DomainName.HR],
    "language_support": DEFAULT_LANGUAGES_SUPPORTED,
    "delete_by": DEFAULT_DELETE_BY_DATE,
    "voice_configuration": None,
    "voice_configuration_id": None,
}

TEST_MANAGER_CONFIG_2_GT = {
    "name": "test_2_manager",
    "display_name": MISSING_VALUE_SENTINEL,
    "category": CategoryName.AGENT,
    "agent_role": AgentRoleName.MANAGER,
    "kind": AgentKind.NATIVE,
    "description": "Test manager agent 2 for use in unit tests.",
    "instructions": "Lorem ipsum dolor sit amet...",
    "tools": [],
    "collaborators": ["test_2_collaborator_agent"],
    "llm": "watsonx/meta-llama/llama-3-2-90b-vision-instruct",
    "style": AgentStyle.DEFAULT,
    "glossary": [],
    "chat_with_docs": None,
    "context_access_enabled": True,
    "context_variables": [],
    "custom_join_tool": None,
    "id": None,
    "spec_version": SpecVersion.V1,
    "starter_prompts": None,
    "structured_output": None,
    "welcome_content": None,
    "guidelines": [],
    "knowledge_base": [],
    "hidden": False,
    "publisher": DEFAULT_PUBLISHER_NAME,
    "supported_apps": [],
    "tags": [DomainName.HR],
    "language_support": DEFAULT_LANGUAGES_SUPPORTED,
    "delete_by": DEFAULT_DELETE_BY_DATE,
    "voice_configuration": None,
    "voice_configuration_id": None,
}

TEST_TOOL_1_CONFIG_GT = {
    "applications": [
        {
            "app_id": "test_app_id_1",
            "description": "This is a description.",
            "name": "Bar",
        },
        {
            "app_id": "test_app_id_2",
            "description": "This is another description.",
            "name": "Bin",
        },
    ],
    "binding": {
        "python": {
            "function": "test_module_1:test_tool_1",
            "requirements": ["some_lib:1.0.0"],
        }
    },
    "is_async": False,
    "category": CategoryName.TOOL,
    "description": "This is tool 1",
    "display_name": "Test Tool",
    "name": "test_spec_1",
    "permission": ToolPermission.READ_ONLY,
    "publisher": DEFAULT_PUBLISHER_NAME,
    "tags": [DomainName.HR],
    "language_support": DEFAULT_LANGUAGES_SUPPORTED,
    "delete_by": DEFAULT_DELETE_BY_DATE,
}

TEST_TOOL_2_CONFIG_GT = {
    "applications": [{"app_id": "test_app_id_1"}, {"app_id": "test_app_id_2"}],
    "binding": {
        "python": {
            "function": "test_module_2:test_tool_2",
            "requirements": ["some_lib:1.0.0"],
        }
    },
    "category": CategoryName.TOOL,
    "is_async": False,
    "description": "This is tool 2",
    "name": "test_spec_2",
    "permission": ToolPermission.READ_ONLY,
    "publisher": DEFAULT_PUBLISHER_NAME,
    "tags": [DomainName.HR],
    "language_support": DEFAULT_LANGUAGES_SUPPORTED,
    "delete_by": DEFAULT_DELETE_BY_DATE,
}


TEST_APPLICATIONS_CONFIG_GT = {
    "name": "applications_file",
    "version": str(TEST_VERSION),
    "applications": [
        {
            "app_id": "test_app_id_1",
            "name": "test_name_1",
            "description": "test_description_1",
            "icon": "test_svg_1",
        },
        {
            "app_id": "test_app_id_2",
            "name": "test_name_2",
            "description": "test_description_2",
            "icon": "test_svg_2",
        },
    ],
}

CATALOG_METADATA = CatalogMetadata(
    manager_offering_map={
        "test_1_manager": "hr_employee_support_1",
        "test_2_manager": "hr_employee_support_2",
    },
    offering_map={
        "hr_employee_support_1": OfferingMetadata(
            offering="hr_employee_support_1",
            manager_agent="test_1_manager",
            domain=DomainName.HR,
            display_name="Offering Display Name",
            description="This is the offering description.",
        ),
        "hr_employee_support_2": OfferingMetadata(
            offering="hr_employee_support_2",
            manager_agent="test_2_manager",
            domain=DomainName.HR,
            display_name="Offering Display Name",
            description="This is the offering description.",
        ),
    },
    agent_map={
        "test_1_collaborator_agent": AgentMetadata(
            agent="test_agent",
            display_name="Test Agent",
            description="This is a test agent.",
            icon=None,
        ),
        "test_2_collaborator_agent": AgentMetadata(
            agent="test_agent2",
            display_name="Test Agent 2",
            description="This is a test agent.",
            icon=None,
        ),
        "test_1_manager": AgentMetadata(
            agent="test_manager_agent",
            display_name="Test Manager Agent",
            description="This is a test manager agent.",
            icon=None,
        ),
        "test_2_manager": AgentMetadata(
            agent="test_manager_agent2",
            display_name="Test Manager Agent 2",
            description="This is a test manager agent.",
            icon=None,
        ),
    },
    application_map={
        "test_app_id_1": ApplicationMetadata(
            app_id="Foo",
            name="Bar",
            description="This is a description.",
            icon=None,
        ),
        "test_app_id_2": ApplicationMetadata(
            app_id="Baz",
            name="Bin",
            description="This is another description.",
            icon=None,
        ),
    },
    tool_map={
        "test_tool_1": ToolMetadata(
            tool="test_tool_1",
            display_name="Test Tool",
            description="A tool description.",
            icon=None,
        ),
        "test_tool_2": ToolMetadata(
            tool="test_tool_2",
            display_name="Test Tool Also",
            description="A tool description.",
            icon=None,
        ),
    },
)


def mock_get_tool_by_name(tool_name: str) -> ToolData:
    """
    Mock get_tool_by_name through side_effect.

    Args:
        tool_name: target tool name

    Returns:
        ToolData object from TEST_TOOLS
    """
    return TEST_TOOLS[tool_name]


def mock_get_required_connections_for_tool_list(tool_list: List[str]) -> List[str]:
    """
    Mock get_required_connections_for_tool_list through side_effect.

    Args:
        tool_list: target tools list

    Returns:
        List of required connections from tools in TEST_TOOLS
    """

    tool_data = TEST_TOOLS[more_itertools.one(tool_list)]
    return [c.app_id for c in tool_data.object.expected_credentials]


@pytest.mark.xfail(reason="Need to update test to conform to orchestrate 1.14.1")
@patch(
    "import_utils.connections.tools_app_id_mapper.ConnectionsToolMapper.get_required_connections_for_tool_list"
)
@patch("import_utils.utils.tools_data_mapper.ToolsDataMap.get_tool_by_name")
def test_release_config_data(
    mock_tool_method: MagicMock, mock_connections_method: MagicMock
) -> None:
    """Test release config builder and associated config data."""
    mock_tool_method.side_effect = mock_get_tool_by_name
    mock_connections_method.side_effect = mock_get_required_connections_for_tool_list

    collaborator_dir = CollaboratorPath(TEST_COLLABORATOR_DIRPATH)
    publisher = DEFAULT_PUBLISHER_NAME
    version = TEST_VERSION

    config_data: ReleaseConfigData = ReleaseConfigData.build(
        collaborator_dir=collaborator_dir,
        catalog_metadata=CATALOG_METADATA,
        publisher=publisher,
        version=version,
    )
    # Offering config data
    offering_specs = [
        offering_config_data.offering_config_spec
        for offering_config_data in config_data.offerings_config_data.data
    ]
    actual_offering_specs = [
        OfferingConfigSpec(
            name="hr_employee_support_1",
            display_name="Offering Display Name",
            domain=DomainName.HR,
            publisher=PublisherName.IBM,
            version=SemanticVersion(major=1, minor=2, patch=3, prerelease=None, build=None),
            description="This is the offering description.",
            assets={
                PublisherName.IBM: AssetsSpec(
                    agents=["test_1_collaborator_agent", "test_1_manager"],
                    tools=["test_tool_1", "test_tool_2"],
                )
            },
            part_number=PartNumberSpec(aws=None, ibm_cloud=None, cp4d=None),
            scope=ScopeSpec(
                form_factor=FormFactorSpec(
                    aws=PricingType.PAID, ibm_cloud=PricingType.PAID, cp4d=PricingType.PAID
                ),
                tenant_type=TenantTypeSpec(trial=PricingType.PAID),
            ),
            pricing=PricingSpec(
                currency="USD", amount="100.00", frequency=PricingFrequencyType.MONTHLY
            ),
            delete_by=datetime.date(2999, 1, 1),
        ),
        OfferingConfigSpec(
            name="hr_employee_support_2",
            display_name="Offering Display Name",
            domain=DomainName.HR,
            publisher=PublisherName.IBM,
            version=SemanticVersion(major=1, minor=2, patch=3, prerelease=None, build=None),
            description="This is the offering description.",
            assets={
                PublisherName.IBM: AssetsSpec(
                    agents=["test_2_collaborator_agent", "test_2_manager"], tools=["test_tool_1"]
                )
            },
            part_number=PartNumberSpec(aws=None, ibm_cloud=None, cp4d=None),
            scope=ScopeSpec(
                form_factor=FormFactorSpec(
                    aws=PricingType.PAID, ibm_cloud=PricingType.PAID, cp4d=PricingType.PAID
                ),
                tenant_type=TenantTypeSpec(trial=PricingType.PAID),
            ),
            pricing=PricingSpec(
                currency="USD", amount="100.00", frequency=PricingFrequencyType.MONTHLY
            ),
            delete_by=datetime.date(2999, 1, 1),
        ),
    ]
    # TODO: The ordering of offering_specs can vary per test run. Investigate and enforce ordering.
    assert all(os in offering_specs for os in actual_offering_specs)

    # Agents config data
    agent_specs = [
        agent_config_data.agent_config_spec for agent_config_data in config_data.agents_config_data
    ]
    actual_agent_specs = [
        AgentConfigSpec(
            spec_version="v1",
            kind="native",
            id=None,
            name="test_1_collaborator_agent",
            display_name="Test Agent",
            description="This is a test agent.",
            context_access_enabled=True,
            context_variables=[],
            voice_configuration_id=None,
            voice_configuration=None,
            llm="watsonx/meta-llama/llama-3-2-90b-vision-instruct",
            style="default",
            custom_join_tool=None,
            structured_output=None,
            instructions="Lorem ipsum dolor sit amet...",
            guidelines=[],
            collaborators=[],
            tools=["test_tool_1", "test_tool_2"],
            hidden=False,
            knowledge_base=[],
            chat_with_docs=None,
            starter_prompts=None,
            welcome_content=None,
            category=CategoryName.AGENT,
            agent_role=AgentRoleName.COLLABORATOR,
            publisher=PublisherName.IBM,
            supported_apps=[],
            glossary=[],
            tags=[DomainName.HR],
            language_support=["English"],
            delete_by=datetime.date(2999, 1, 1),
        ),
        AgentConfigSpec(
            spec_version="v1",
            kind="native",
            id=None,
            name="test_1_manager",
            display_name="Test Manager Agent",
            description="This is a test manager agent.",
            context_access_enabled=True,
            context_variables=[],
            voice_configuration_id=None,
            voice_configuration=None,
            llm="watsonx/meta-llama/llama-3-2-90b-vision-instruct",
            style="default",
            custom_join_tool=None,
            structured_output=None,
            instructions="Lorem ipsum dolor sit amet...",
            guidelines=[],
            collaborators=["test_1_collaborator_agent"],
            tools=[],
            hidden=False,
            knowledge_base=[],
            chat_with_docs=None,
            starter_prompts=None,
            welcome_content=None,
            category=CategoryName.AGENT,
            agent_role=AgentRoleName.MANAGER,
            publisher=PublisherName.IBM,
            supported_apps=[],
            glossary=[],
            tags=[DomainName.HR],
            language_support=["English"],
            delete_by=datetime.date(2999, 1, 1),
        ),
        AgentConfigSpec(
            spec_version="v1",
            kind="native",
            id=None,
            name="test_2_collaborator_agent",
            display_name="Test Agent 2",
            description="This is a test agent.",
            context_access_enabled=True,
            context_variables=[],
            voice_configuration_id=None,
            voice_configuration=None,
            llm="watsonx/meta-llama/llama-3-2-90b-vision-instruct",
            style="default",
            custom_join_tool=None,
            structured_output=None,
            instructions="Lorem ipsum dolor sit amet...",
            guidelines=[],
            collaborators=[],
            tools=["test_tool_1"],
            hidden=False,
            knowledge_base=[],
            chat_with_docs=None,
            starter_prompts=None,
            welcome_content=None,
            category=CategoryName.AGENT,
            agent_role=AgentRoleName.COLLABORATOR,
            publisher=PublisherName.IBM,
            supported_apps=[],
            glossary=[],
            tags=[DomainName.HR],
            language_support=["English"],
            delete_by=datetime.date(2999, 1, 1),
        ),
        AgentConfigSpec(
            spec_version="v1",
            kind="native",
            id=None,
            name="test_2_manager",
            display_name="Test Manager Agent 2",
            description="This is a test manager agent.",
            context_access_enabled=True,
            context_variables=[],
            voice_configuration_id=None,
            voice_configuration=None,
            llm="watsonx/meta-llama/llama-3-2-90b-vision-instruct",
            style="default",
            custom_join_tool=None,
            structured_output=None,
            instructions="Lorem ipsum dolor sit amet...",
            guidelines=[],
            collaborators=["test_2_collaborator_agent"],
            tools=[],
            hidden=False,
            knowledge_base=[],
            chat_with_docs=None,
            starter_prompts=None,
            welcome_content=None,
            category=CategoryName.AGENT,
            agent_role=AgentRoleName.MANAGER,
            publisher=PublisherName.IBM,
            supported_apps=[],
            glossary=[],
            tags=[DomainName.HR],
            language_support=["English"],
            delete_by=datetime.date(2999, 1, 1),
        ),
    ]
    # TODO: The ordering of agent_specs can vary per test run. Investigate and enforce ordering.
    assert all(ags in agent_specs for ags in actual_agent_specs)

    # Tools config data
    tool_specs = [
        tool_config_data.tool_config_spec for tool_config_data in config_data.tools_config_data
    ]
    actual_tool_specs = [
        ToolConfigSpec(
            name="test_spec_1",
            id=None,
            display_name="Test Tool",
            description="This is tool 1",
            permission=ToolPermission.READ_ONLY,
            binding=ToolBinding(
                python=PythonToolBinding(
                    function="test_module_1:test_tool_1",
                    requirements=["some_lib:1.0.0"],
                ),
            ),
            toolkit_id=None,
            is_async=False,
            publisher=PublisherName.IBM,
            category=CategoryName.TOOL,
            tags=[DomainName.HR],
            applications=[
                ApplicationsSpec(
                    app_id="test_app_id_1",
                    name="Bar",
                    description="This is a description.",
                    icon=None,
                ),
                ApplicationsSpec(
                    app_id="test_app_id_2",
                    name="Bin",
                    description="This is another description.",
                    icon=None,
                ),
            ],
            language_support=["English"],
            delete_by=datetime.date(2999, 1, 1),
        ),
        ToolConfigSpec(
            name="test_spec_2",
            id=None,
            display_name="Test Tool Also",
            description="This is tool 2",
            permission=ToolPermission.READ_ONLY,
            binding=ToolBinding(
                python=PythonToolBinding(
                    function="test_module_2:test_tool_2",
                    requirements=["some_lib:1.0.0"],
                ),
            ),
            toolkit_id=None,
            is_async=False,
            publisher=PublisherName.IBM,
            category=CategoryName.TOOL,
            tags=[DomainName.HR],
            applications=[
                ApplicationsSpec(
                    app_id="test_app_id_1",
                    name="Bar",
                    description="This is a description.",
                    icon=None,
                ),
                ApplicationsSpec(
                    app_id="test_app_id_2",
                    name="Bin",
                    description="This is another description.",
                    icon=None,
                ),
            ],
            language_support=["English"],
            delete_by=datetime.date(2999, 1, 1),
        ),
    ]
    # TODO: The ordering of agent_specs can vary per test run. Investigate and enforce ordering.
    assert all(ts in tool_specs for ts in actual_tool_specs)

    # Version
    assert config_data.version == str(TEST_VERSION)


@pytest.mark.xfail(reason="Need to update test to conform to orchestrate 1.14.1")
@patch(
    "import_utils.connections.tools_app_id_mapper.ConnectionsToolMapper.get_required_connections_for_tool_list"
)
@patch("import_utils.utils.tools_data_mapper.ToolsDataMap.get_tool_by_name")
def test_offering_config_data(
    mock_tool_method: MagicMock, mock_connections_method: MagicMock
) -> None:
    """Test offering config builder and offering config data."""
    mock_tool_method.side_effect = mock_get_tool_by_name
    mock_connections_method.side_effect = mock_get_required_connections_for_tool_list

    publisher = DEFAULT_PUBLISHER_NAME
    version = TEST_VERSION

    manager_yaml_data = AgentYamlsData(manager_filepath=TEST_MANAGER_FILEPATH)
    config_data = OfferingConfigBuilder().build(
        manager_yaml_data=manager_yaml_data,
        catalog_metadata=CATALOG_METADATA,
        publisher=publisher,
        version=version,
    )
    # Update GTs with Metadata
    test_offering_config_1_gt_with_metadata = {**TEST_OFFERING_CONFIG_1_GT}
    offering_metadata_1 = CATALOG_METADATA.offering_map.get("hr_employee_support_1")
    assert offering_metadata_1
    assert offering_metadata_1.display_name
    assert offering_metadata_1.description
    test_offering_config_1_gt_with_metadata["display_name"] = offering_metadata_1.display_name
    test_offering_config_1_gt_with_metadata["description"] = offering_metadata_1.description
    assert (
        config_data.offering_config_spec.model_dump() == test_offering_config_1_gt_with_metadata
    ), config_data.offering_config_spec
    assert (
        config_data.offering_config_spec.model_dump() != TEST_OFFERING_CONFIG_1_GT
    ), config_data.offering_config_spec


@pytest.mark.xfail(reason="Need to update test to conform to 1.14.1")
def test_agent_config_data() -> None:
    """Test agent config builder and agent config data."""
    publisher = DEFAULT_PUBLISHER_NAME

    config_data = AgentConfigBuilder().build(
        agent_name="test_agent",
        catalog_metadata=CATALOG_METADATA,
        agent_role=AgentRoleName.COLLABORATOR,
        agent_filepath=TEST_COLLABORATOR_FILEPATH,
        domain=DomainName.HR,
        publisher=publisher,
    )
    # The metadata fields overwrite the agent display name and description
    test_collaborator_config_1_gt_metadata = {**TEST_COLLABORATOR_CONFIG_1_GT}
    agent_metadata_3 = CATALOG_METADATA.agent_map.get("test_1_collaborator_agent")
    assert agent_metadata_3
    assert agent_metadata_3.display_name
    assert agent_metadata_3.description
    test_collaborator_config_1_gt_metadata["display_name"] = agent_metadata_3.display_name
    test_collaborator_config_1_gt_metadata["description"] = agent_metadata_3.description
    assert (
        config_data.agent_config_spec.model_dump() == test_collaborator_config_1_gt_metadata
    ), config_data.agent_config_spec
    assert (
        config_data.agent_config_spec.model_dump() != TEST_COLLABORATOR_CONFIG_1_GT
    ), config_data.agent_config_spec


@patch(
    "import_utils.connections.tools_app_id_mapper.ConnectionsToolMapper.get_required_connections_for_tool_list"
)
@patch("import_utils.utils.tools_data_mapper.ToolsDataMap.get_tool_by_name")
def test_tool_config_data(mock_tool_method: MagicMock, mock_connections_method: MagicMock) -> None:
    """Test tool config builder and tool config data."""
    mock_tool_method.side_effect = mock_get_tool_by_name
    mock_connections_method.side_effect = mock_get_required_connections_for_tool_list

    domain = DomainName.HR
    publisher = DEFAULT_PUBLISHER_NAME
    catalog_metadata = CATALOG_METADATA

    config_data = ToolConfigBuilder().build(
        tool_name="test_tool_1",
        domain=domain,
        publisher=publisher,
        catalog_metadata=catalog_metadata,
    )
    assert (
        config_data.tool_config_spec.model_dump(exclude_none=True) == TEST_TOOL_1_CONFIG_GT
    ), config_data.tool_config_spec


@patch(
    "import_utils.connections.tools_app_id_mapper.ConnectionsToolMapper.get_required_connections_for_tool_list"
)
@patch("import_utils.utils.tools_data_mapper.ToolsDataMap.get_tool_by_name")
def test_tool_with_no_expected_credentials(
    mock_tool_method: MagicMock, mock_connections_method: MagicMock
) -> None:
    """Test that a tool with no expected credentials throws an AssertionError."""
    mock_tool_method.side_effect = mock_get_tool_by_name
    mock_connections_method.side_effect = mock_get_required_connections_for_tool_list

    domain = DomainName.HR
    publisher = DEFAULT_PUBLISHER_NAME

    with pytest.raises(AssertionError):
        # tool 'test_no_expected_creds_tool' is missing 'expected_credentials' param
        ToolConfigBuilder().build(
            tool_name="test_no_expected_creds_tool",
            domain=domain,
            publisher=publisher,
            catalog_metadata=CatalogMetadata(),
        )


def test_applications_config_data() -> None:
    """Test applications config builder and applications config data."""

    version = TEST_VERSION
    publisher = DEFAULT_PUBLISHER_NAME
    applications_data = TEST_APPLICATIONS

    config_data = ApplicationsConfigBuilder().build(
        version=version, publisher=publisher, applications_data=applications_data
    )
    assert (
        config_data.applications_config_spec.model_dump(exclude_none=True)
        == TEST_APPLICATIONS_CONFIG_GT
    ), config_data.applications_config_spec

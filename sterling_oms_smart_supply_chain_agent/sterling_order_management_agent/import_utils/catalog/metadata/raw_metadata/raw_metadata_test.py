from pathlib import Path

from import_utils.catalog.metadata.raw_metadata.raw_metadata import (
    AgentsToolsRow,
    ConnectionsRow,
    IconsRow,
    PartNumbersRow,
    RawCatalogMetadata,
)

RAW_AGENTS_TOOLS_METADATA = [
    AgentsToolsRow(
        domain="HR",
        offering="hr_employee_support_sap",
        offering_display_name="Employee Support for SAP SuccessFactors",
        offering_description="Provide employee support for SAP SuccessFactors users",
        agent="sap_employee_support_manager",
        agent_display_name="Employee Support Manager",
        agent_description="Handles user support cases",
        tool=None,
        tool_display_name=None,
        tool_description=None,
        application_name=None,
        icon="SAP",
    ),
    AgentsToolsRow(
        domain="HR",
        offering=None,
        offering_display_name=None,
        offering_description=None,
        agent="sap_employee_immigration_agent",
        agent_display_name="Employee Visa",
        agent_description=None,
        tool=None,
        tool_display_name=None,
        tool_description=None,
        application_name=None,
        icon="SAP",
    ),
    AgentsToolsRow(
        domain="HR",
        offering=None,
        offering_display_name=None,
        offering_description=None,
        agent=None,
        agent_display_name=None,
        agent_description=None,
        tool="get_user_successfactors_ids",
        tool_display_name="Get user  ID in SAP SuccessFactors",
        tool_description="Gets a user's person_id_external and user_id from SAP SuccessFactors.",
        application_name="SAP SuccessFactors",
        icon="SAP",
    ),
    AgentsToolsRow(
        domain="HR",
        offering=None,
        offering_display_name=None,
        offering_description=None,
        agent=None,
        agent_display_name=None,
        agent_description=None,
        tool="get_visa_details",
        tool_display_name="Get visa details in SAP SuccessFactors",
        tool_description="Retrieves a user's visa information in SAP SuccessFactors.",
        application_name="SAP SuccessFactors",
        icon="SAP",
    ),
]

RAW_CONNECTIONS_METADATA = [
    ConnectionsRow(
        app_id="sap_successfactors_basic_ibm_184bdbd3",
        app_id_name="SAP SuccessFactors",
        auth_type="Key Value",
        app_id_icon="SAP",
    )
]

RAW_PART_NUMBERS_METADATA = [
    PartNumbersRow(
        domain="HR",
        offering="hr_employee_support_sap",
        ibm_cloud_pn="D1234A",
        aws_pn="D1234B",
        description="SAP HR Employee Support Offering",
        monthly_price="100",
    )
]

RAW_ICONS_METADATA = [
    IconsRow(
        name="SAP",
        svg_icon="<svg>sap_svg_icon</svg>",
    ),
    IconsRow(
        name="Oracle",
        svg_icon="<svg>oracle_svg_icon</svg>",
    ),
    IconsRow(
        name="Workday",
        svg_icon=None,
    ),
]

TEST_METADATA_PATH = Path("import_utils/catalog/metadata/test_data/test_metadata.xlsx")


def test_raw_catalog_metadata_building() -> None:
    """Test raw catalog metadata building."""

    metadata = RawCatalogMetadata.from_filepath(filepath=TEST_METADATA_PATH)

    assert metadata.agent_and_tools_sheet == RAW_AGENTS_TOOLS_METADATA
    assert metadata.connections_sheet == RAW_CONNECTIONS_METADATA
    assert metadata.part_numbers_sheet == RAW_PART_NUMBERS_METADATA
    assert metadata.icons_sheet == RAW_ICONS_METADATA

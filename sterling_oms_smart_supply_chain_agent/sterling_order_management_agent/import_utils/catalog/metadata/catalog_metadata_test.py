from pathlib import Path

from import_utils.catalog.metadata.catalog_metadata import (
    AgentMetadata,
    ApplicationMetadata,
    CatalogMetadata,
    IconMetadata,
    OfferingMetadata,
    PartNumberMetadata,
    ToolMetadata,
)

OFFERING_MAP_GT = {
    "hr_employee_support_sap": OfferingMetadata(
        offering="hr_employee_support_sap",
        manager_agent="sap_employee_support_manager",
        domain="HR",
        display_name="Employee Support for SAP SuccessFactors",
        description="Provide employee support for SAP SuccessFactors users",
    )
}

AGENT_MAP_GT = {
    "sap_employee_support_manager": AgentMetadata(
        agent="sap_employee_support_manager",
        display_name="Employee Support Manager",
        description="Handles user support cases",
        icon="SAP",
    ),
    "sap_employee_immigration_agent": AgentMetadata(
        agent="sap_employee_immigration_agent",
        display_name="Employee Visa",
        description=None,
        icon="SAP",
    ),
}

TOOL_MAP_GT = {
    "get_user_successfactors_ids": ToolMetadata(
        tool="get_user_successfactors_ids",
        display_name="Get user  ID in SAP SuccessFactors",
        description="Gets a user's person_id_external and user_id from SAP SuccessFactors.",
        icon="SAP",
    ),
    "get_visa_details": ToolMetadata(
        tool="get_visa_details",
        display_name="Get visa details in SAP SuccessFactors",
        description="Retrieves a user's visa information in SAP SuccessFactors.",
        icon="SAP",
    ),
}

CONNECTION_MAP_GT = {
    "sap_successfactors_basic_ibm_184bdbd3": ApplicationMetadata(
        app_id="sap_successfactors_basic_ibm_184bdbd3",
        name="SAP SuccessFactors",
        description=None,
        icon="SAP",
    )
}

PART_NUMBER_MAP_GT = {
    "hr_employee_support_sap": PartNumberMetadata(
        offering="hr_employee_support_sap",
        ibm_cloud_pn="D1234A",
        aws_pn="D1234B",
        description="SAP HR Employee Support Offering",
        monthly_price="100",
    )
}

ICON_MAP_GT = {
    "SAP": IconMetadata(
        icon="SAP",
        inline_svg="<svg>sap_svg_icon</svg>",
    ),
    "Oracle": IconMetadata(
        icon="Oracle",
        inline_svg="<svg>oracle_svg_icon</svg>",
    ),
    "Workday": IconMetadata(
        icon="Workday",
        inline_svg=None,
    ),
}

TEST_METADATA_PATH = Path("import_utils/catalog/metadata/test_data/test_metadata.xlsx")


def test_catalog_metadata_building() -> None:
    """Test catalog metadata building."""

    metadata_dicts = CatalogMetadata.from_filepath(filepath=TEST_METADATA_PATH)

    assert metadata_dicts.offering_map == OFFERING_MAP_GT
    assert metadata_dicts.agent_map == AGENT_MAP_GT
    assert metadata_dicts.tool_map == TOOL_MAP_GT
    assert metadata_dicts.application_map == CONNECTION_MAP_GT
    assert metadata_dicts.part_number_map == PART_NUMBER_MAP_GT
    assert metadata_dicts.icon_map == ICON_MAP_GT

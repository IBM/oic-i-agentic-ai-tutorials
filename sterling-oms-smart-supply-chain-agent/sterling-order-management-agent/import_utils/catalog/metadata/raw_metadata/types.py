from enum import StrEnum


class SheetData(StrEnum):
    """Class to define sheet data values in input file."""

    AGENTS_AND_TOOLS = "Agent and Tools"
    CONNECTIONS = "Connections"
    PART_NUMBERS = "Part Numbers"
    ICONS = "Icons"


class AgentsToolsHeaders(StrEnum):
    """Class to define 'Agent and Tools' sheet headers."""

    DOMAIN = "Domain"

    OFFERING = "Offering"
    OFFERING_DISPLAY_NAME = "Offering Display Name"
    OFFERING_DESCRIPTION = "Offering Description"

    AGENT = "Agent"
    AGENT_DISPLAY_NAME = "Agent Display Name"
    AGENT_DESCRIPTION = "Agent Description"

    TOOL = "Tool"
    TOOL_DISPLAY_NAME = "Tool Display Name"
    TOOL_DESCRIPTION = "Tool Description"
    APPLICATION_NAME = "Application Name"

    ICON = "Icon"


class ConnectionsHeaders(StrEnum):
    """Class to define 'Connections' sheet headers."""

    APP_ID = "App ID"
    APP_ID_NAME = "App ID Name"
    AUTH_TYPE = "Auth Type"
    ICON = "App ID Icon"


class PartNumbersHeaders(StrEnum):
    """Class to define 'Part Numbers' headers."""

    DOMAIN = "Domain"
    OFFERING = "Offering"
    IBM_CLOUD_PN = "IBM Cloud PN"
    AWS_PN = "AWS PN"
    DESCRIPTION = "Description"
    MONTHLY_PRICE = "Price /month"


class IconsHeaders(StrEnum):
    """Class to define 'Icons' headers."""

    NAME = "Name"
    SVG_ICON = "SVG Icon"

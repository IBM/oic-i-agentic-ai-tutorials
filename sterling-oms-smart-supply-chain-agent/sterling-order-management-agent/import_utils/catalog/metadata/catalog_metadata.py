from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from import_utils.catalog.metadata.raw_metadata.raw_metadata import (
    AgentsToolsRow,
    ConnectionsRow,
    IconsRow,
    PartNumbersRow,
    RawCatalogMetadata,
)
from import_utils.catalog.metadata.raw_metadata.validation import validate_raw_metadata


@dataclass
class IconMetadata:
    """Structured metadata for 'icon'."""

    icon: str | None
    inline_svg: str | None

    @classmethod
    def from_row(cls, row: IconsRow) -> "IconMetadata":
        """
        Creates IconMetadata from a raw IconsRow row.

        Args:
            row: The raw IconsRow row.

        Returns:
            A IconMetadata instance populated with raw metadata
            from a IconsRow row.
        """
        return cls(
            icon=row.name,
            inline_svg=row.svg_icon,
        )


@dataclass
class OfferingMetadata:
    """Structured metadata for 'offering'."""

    offering: str | None
    manager_agent: str | None
    domain: str | None
    display_name: str | None
    description: str | None

    @classmethod
    def from_row(cls, row: AgentsToolsRow) -> "OfferingMetadata":
        """
        Creates OfferingMetadata from a raw AgentsToolsRow row.

        Args:
            row: The raw AgentsToolsRow row.

        Returns:
            An OfferingMetadata instance populated with raw metadata
            from an AgentToolsRow row.
        """
        return cls(
            offering=row.offering,
            manager_agent=row.agent,
            domain=row.domain,
            display_name=row.offering_display_name,
            description=row.offering_description,
        )


@dataclass
class AgentMetadata:
    """Structured metadata for 'agent'."""

    agent: str | None
    display_name: str | None
    description: str | None
    icon: str | None

    @classmethod
    def from_row(cls, row: AgentsToolsRow) -> "AgentMetadata":
        """
        Creates AgentMetadata from a raw AgentsToolsRow row.

        Args:
            row: The raw AgentsToolsRow row.

        Returns:
            An AgentMetadata instance populated with raw metadata
            from an AgentToolsRow row.
        """
        return cls(
            agent=row.agent,
            display_name=row.agent_display_name,
            description=row.agent_description,
            icon=row.icon,
        )


@dataclass
class ToolMetadata:
    """Structured metadata for 'tool'."""

    tool: str | None
    display_name: str | None
    description: str | None
    icon: str | None

    @classmethod
    def from_row(cls, row: AgentsToolsRow) -> "ToolMetadata":
        """
        Creates ToolMetadata from a raw AgentsToolsRow row.

        Args:
            row: The raw AgentsToolsRow row.

        Returns:
            A ToolMetadata instance populated with raw metadata
            from an AgentToolsRow row.
        """
        return cls(
            tool=row.tool,
            display_name=row.tool_display_name,
            description=row.tool_description,
            icon=row.icon,
        )


@dataclass
class ApplicationMetadata:
    """Structured metadata for 'application'."""

    app_id: str | None
    name: str | None
    description: str | None
    icon: str | None  # TODO: add validation for icon's SVG format

    @classmethod
    def from_row(cls, row: ConnectionsRow) -> "ApplicationMetadata":
        """
        Creates ApplicationMetadata from a raw ConnectionsRow row.

        Args:
            row: The raw ConnectionsRow row.

        Returns:
            An ApplicationMetadata instance populated with raw metadata
            from a ConnectionsRow row.
        """
        return cls(
            app_id=row.app_id,
            name=row.app_id_name,
            description=None,  # TODO: Build into the Row
            icon=row.app_id_icon,
        )


@dataclass
class PartNumberMetadata:
    """Structured metadata for 'part number'."""

    offering: str | None
    ibm_cloud_pn: str | None
    aws_pn: str | None
    description: str | None
    monthly_price: str | None

    @classmethod
    def from_row(cls, row: PartNumbersRow) -> "PartNumberMetadata":
        """
        Creates PartNumberMetadata from a raw PartNumbersRow row.

        Args:
            row: The raw PartNumbersRow row.

        Returns:
            A PartNumberMetadata instance populated with raw metadata
            from a PartNumbersRow row.
        """
        return cls(
            offering=row.offering,
            ibm_cloud_pn=row.ibm_cloud_pn,
            aws_pn=row.aws_pn,
            description=row.description,
            monthly_price=row.monthly_price,
        )


@dataclass
class CatalogMetadata:
    """Dataclass holding metadata dictionaries keyed by string identifiers."""

    # map of manager agent -> offering
    manager_offering_map: Mapping[str, str] = field(default_factory=dict)

    offering_map: Mapping[str, OfferingMetadata] = field(default_factory=dict)
    agent_map: Mapping[str, AgentMetadata] = field(default_factory=dict)
    tool_map: Mapping[str, ToolMetadata] = field(default_factory=dict)
    application_map: Mapping[str, ApplicationMetadata] = field(default_factory=dict)
    part_number_map: Mapping[str, PartNumberMetadata] = field(default_factory=dict)
    icon_map: Mapping[str, IconMetadata] = field(default_factory=dict)

    @classmethod
    def from_filepath(cls, filepath: Path) -> "CatalogMetadata":
        """
        Builds all metadata dicts from a specified filepath.

        Args:
            filepath: Path to the Excel file containing the catalog data.

        Returns:
            A CatalogMetadata instance containing metadata dicts.
        """
        raw_metadata = RawCatalogMetadata.from_filepath(filepath)
        validate_raw_metadata(raw_metadata)

        manager_offering_dict = {}

        offering_dict = {}
        agent_dict = {}
        tool_dict = {}
        application_dict = {}
        part_number_dict = {}
        icon_dict = {}

        for icon_row in raw_metadata.icons_sheet:
            icon_key = icon_row.name
            assert icon_key is not None
            icon_dict[icon_key] = IconMetadata.from_row(icon_row)

        for agent_tool_row in raw_metadata.agent_and_tools_sheet:
            offering_key = agent_tool_row.offering
            agent_key = agent_tool_row.agent
            tool_key = agent_tool_row.tool

            if offering_key is not None:
                assert agent_key is not None
                manager_offering_dict[agent_key] = offering_key
                offering_dict[offering_key] = OfferingMetadata.from_row(agent_tool_row)

            # Use only the first instance of agent name for dictionary
            if agent_key is not None and agent_key not in agent_dict:
                agent_dict[agent_key] = AgentMetadata.from_row(agent_tool_row)

            # Use only the first instance of tool name for dictionary
            if tool_key is not None and tool_key not in tool_dict:
                tool_dict[tool_key] = ToolMetadata.from_row(agent_tool_row)

        for connections_row in raw_metadata.connections_sheet:
            application_key = connections_row.app_id
            assert application_key is not None
            application_dict[application_key] = ApplicationMetadata.from_row(connections_row)

        for part_number_row in raw_metadata.part_numbers_sheet:
            part_number_key = part_number_row.offering
            assert part_number_key is not None
            part_number_dict[part_number_key] = PartNumberMetadata.from_row(part_number_row)

        return cls(
            manager_offering_map=manager_offering_dict,
            offering_map=offering_dict,
            agent_map=agent_dict,
            tool_map=tool_dict,
            application_map=application_dict,
            part_number_map=part_number_dict,
            icon_map=icon_dict,
        )

    def get_icon_metadata(
        self,
        icon_name: str,
    ) -> IconMetadata:
        """
        Get the icon metadata object for the given icon name.

        Args:
            icon_name: The name of the icon to get metadata for.

        Returns:
            The icon metadata object for the given icon name.
        """
        assert (
            icon := self.icon_map.get(icon_name)
        ) is not None, (
            f"Icon {icon_name!r} is not a valid icon name. Valid icon names: {self.icon_map.keys()}"
        )

        return icon

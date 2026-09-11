from dataclasses import dataclass
import json
from pathlib import Path
from typing import Dict, List

from ibm_watsonx_orchestrate.agent_builder.tools import PythonTool
from import_utils.catalog.metadata.catalog_metadata import (
    ApplicationMetadata,
    CatalogMetadata,
    ToolMetadata,
)
from import_utils.catalog.types import (
    DEFAULT_DELETE_BY_DATE,
    DEFAULT_LANGUAGES_SUPPORTED,
    ApplicationsSpec,
    CategoryName,
    DomainName,
    PublisherName,
    ToolConfigSpec,
)
from import_utils.connections.tools_app_id_mapper import ConnectionsToolMapper
from import_utils.utils.tools_data_mapper import ToolsDataMap
from pydantic import ValidationError


@dataclass
class ToolConfigData:
    """Dataclass representing the format for tool config data."""

    tool_name: str  # the tool name
    domain: DomainName  # the domain name for this tool
    publisher: PublisherName  # the publisher name for this tool

    tool_config_spec: ToolConfigSpec  # the config spec schema
    relative_export_filepath: Path  # the relative export filepath for config data


class ToolConfigBuilder:
    """Class to build tool config data in the format prescribed for 'catalog' ingestion."""

    _domain: DomainName
    _publisher: PublisherName

    def build(
        self,
        tool_name: str,
        domain: DomainName,
        publisher: PublisherName,
        catalog_metadata: CatalogMetadata,
    ) -> ToolConfigData:
        """
        Args:
            tool_name: the name of the tool to process.
            domain: the domain name.
            publisher: the publisher name.
            catalog_metadata: the catalog metadata

        Returns:
            the tool config data.
        """
        self._domain = domain
        self._publisher = publisher
        rel_export_filepath = self._get_relative_export_filepath(tool_name)
        return ToolConfigData(
            tool_name=tool_name,
            domain=domain,
            publisher=publisher,
            relative_export_filepath=rel_export_filepath,
            tool_config_spec=self._get_tool_config_spec(tool_name, catalog_metadata),
        )

    def _get_tool_config_spec(
        self,
        tool_name: str,
        catalog_metadata: CatalogMetadata,
    ) -> ToolConfigSpec:
        """
        Args:
            tool_name: the name of the tool to process.
            catalog_metadata: the catalog metadata

        Returns:
            agent config data as prescribed by AgentConfigModel schema.
        """
        tool_data = self._get_python_tool_data(tool_name=tool_name)
        applications_data = self._get_applications_data(tool_name, catalog_metadata)

        # NOTE: this field defaults to English for now, but it should be pulled
        # from a source-of-truth specified in either AgentSpec or ToolSpec (currently
        # there's no language_support field in either).
        language_support = DEFAULT_LANGUAGES_SUPPORTED

        # NOTE: this field defaults to '2999-01-01' for now, but it should be pulled
        # from a source-of-truth specified in metadata and validated here.
        delete_by = DEFAULT_DELETE_BY_DATE

        tool_config_metadata: ToolMetadata | None = catalog_metadata.tool_map.get(tool_name)
        assert tool_config_metadata, tool_name

        try:
            config_data = ToolConfigSpec(
                **tool_data,
                display_name=tool_config_metadata.display_name,
                category=CategoryName.TOOL,
                publisher=self._publisher,
                tags=[self._domain],
                applications=applications_data,
                language_support=language_support,
                delete_by=delete_by,
            )
        except ValidationError as e:
            raise ValueError(e)
        return config_data

    def _get_python_tool_data(self, tool_name: str) -> Dict[str, str]:
        """
        Args:
            tool_name: the name of the tool for which to retrieve the underlying
        PythonTool data

        Returns:
            the PythonTool data as a dict
        """
        tool = ToolsDataMap().get_tool_by_name(tool_name=tool_name)
        assert tool is not None, f"{tool_name} is not a valid tool dependency"

        assert isinstance(tool.object, PythonTool)
        tool_data = json.loads(tool.object.dumps_spec())

        tool_data["binding"]["python"]["function"] = tool.module_name + ":" + tool_name

        return tool_data

    def _get_applications_data(
        self, tool_name: str, catalog_metadata: CatalogMetadata
    ) -> List[ApplicationsSpec]:
        """
        Args:
            tool_name: the name of the tool to process.
            catalog_metadata: the catalog metadata.

        Returns:
            a list of containing connections app_id and, optionally, the app_id name
        """
        connections = ConnectionsToolMapper().get_required_connections_for_tool_list([tool_name])
        assert connections, f"Tool {tool_name!r} is missing 'expected_credentials' param."
        result: List[ApplicationsSpec] = []
        for conn in sorted(connections):
            app_metadata: ApplicationMetadata | None = catalog_metadata.application_map.get(conn)
            assert app_metadata
            assert app_metadata.name is not None
            result.append(
                ApplicationsSpec(
                    app_id=conn,
                    name=app_metadata.name,
                    description=app_metadata.description,
                    icon=app_metadata.icon,
                )
            )
        return result

    def _get_relative_export_filepath(self, tool_name: str) -> Path:
        """
        Args:
            tool_name: the name of the tool to process.

        Returns:
            the relative export filepath for tool config data.
        """
        filepath = f"publishers/{self._publisher}/tools/{tool_name}/config.json"
        return Path(filepath)

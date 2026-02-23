from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from import_utils.catalog.agent_config_data import AgentConfigData
from import_utils.catalog.applications_config_data import (
    ApplicationsConfigBuilder,
    ApplicationsConfigData,
)
from import_utils.catalog.metadata.catalog_metadata import CatalogMetadata
from import_utils.catalog.offering_config_data import (
    OfferingConfigBuilder,
    OfferingConfigData,
    OfferingConfigDataList,
)
from import_utils.catalog.tool_config_data import ToolConfigData
from import_utils.catalog.types import PublisherName
from import_utils.tool_importer.agent_yamls_data import AgentYamlsData
from import_utils.utils.logger import get_logger
from more_itertools import unique_everseen
from pydantic_extra_types.semantic_version import SemanticVersion  # pants: no-infer-dep

LOGGER = get_logger(__name__)


@dataclass
class CollaboratorPath:
    """A path to a collaborator directory and all manager agent paths within that directory."""

    path: Path
    manager_paths: List[Path] = field(init=False)

    def __post_init__(self) -> None:
        """Collect all manager filepaths from which we need to construct offering/agent/tool
        configs."""
        self.manager_paths = [*self.path.rglob("*manager.yaml")]


@dataclass
class ReleaseConfigData:
    """Dataclass representing the format for release config data."""

    offerings_config_data: OfferingConfigDataList
    catalog_metadata: CatalogMetadata
    agents_config_data: List[AgentConfigData] = field(init=False)
    tools_config_data: List[ToolConfigData] = field(init=False)
    applications_config_data: List[ApplicationsConfigData] = field(init=False)

    publisher: PublisherName
    version: SemanticVersion  # the version for this release

    def __post_init__(self) -> None:
        """Load additional config data."""
        self.agents_config_data = [
            *unique_everseen(self.offerings_config_data.agents_config_data_list)
        ]
        self.tools_config_data = [
            *unique_everseen(self.offerings_config_data.tools_config_data_list)
        ]
        self.applications_config_data = [
            ApplicationsConfigBuilder().build(
                version=self.version,
                publisher=self.publisher,
                applications_data=[
                    *unique_everseen(self.offerings_config_data.applications_spec_list)
                ],
            ),
        ]

    @classmethod
    def build(
        cls,
        collaborator_dir: CollaboratorPath,
        catalog_metadata: CatalogMetadata,
        publisher: PublisherName,
        version: SemanticVersion,
    ) -> "ReleaseConfigData":
        """
        Args:
            collaborator_dir: the CollaboratorPath of the 'collaborator agents' directory.
            catalog_metadata: the CatalogMetadata.
            publisher: the publisher name.
            version: the version for this catalog offering.

        Returns:
            the config data for this release.
        """
        # Generate offering config data from collaborator files
        offerings_config_data_list: List[OfferingConfigData] = []
        for manager_filepath in collaborator_dir.manager_paths:
            manager_yaml_data = AgentYamlsData(manager_filepath=manager_filepath)
            entrypoint_manager_name = manager_yaml_data.entrypoint_manager_name
            if entrypoint_manager_name not in catalog_metadata.manager_offering_map:
                LOGGER.info(
                    f"Manager agent {entrypoint_manager_name!r} is not defined in metadata, it will not be included in release"
                )
                continue
            LOGGER.info(f"Building release artifacts for manager agent {entrypoint_manager_name}")
            offerings_config_data_list.append(
                OfferingConfigBuilder().build(
                    manager_yaml_data=manager_yaml_data,
                    catalog_metadata=catalog_metadata,
                    version=version,
                    publisher=publisher,
                )
            )

        # Custom object contains all config, agent, tool, and application data in order.
        return ReleaseConfigData(
            offerings_config_data=OfferingConfigDataList(data=offerings_config_data_list),
            catalog_metadata=catalog_metadata,
            publisher=publisher,
            version=version,
        )

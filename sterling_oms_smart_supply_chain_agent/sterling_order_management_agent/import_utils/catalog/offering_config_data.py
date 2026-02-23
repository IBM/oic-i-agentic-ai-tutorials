from dataclasses import dataclass, field
import itertools
from pathlib import Path
from typing import Dict, List, Optional

from import_utils.catalog.agent_config_data import AgentConfigBuilder, AgentConfigData
from import_utils.catalog.metadata.catalog_metadata import CatalogMetadata, OfferingMetadata
from import_utils.catalog.tool_config_data import ToolConfigBuilder, ToolConfigData
from import_utils.catalog.types import (
    DEFAULT_DELETE_BY_DATE,
    AgentRoleName,
    ApplicationsSpec,
    AssetsSpec,
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
)
from import_utils.tool_importer.agent_yamls_data import AgentYamlsData
from pydantic import ValidationError
from pydantic_extra_types.semantic_version import SemanticVersion  # pants: no-infer-dep


@dataclass
class OfferingConfigData:
    """Dataclass representing the format for offering config data."""

    agents_config_data: List[AgentConfigData]  # list of agent config data entries in this offering
    tools_config_data: List[ToolConfigData]  # list of tool config data entries in this offering

    offering_name: str  # the offering name
    domain: DomainName  # the domain name for this offering
    publisher: PublisherName  # the publisher name for this offering

    version: SemanticVersion  # the version for this offering

    offering_config_spec: OfferingConfigSpec  # the offering config spec schema
    relative_export_filepath: Path  # the relative export filepath for config data


@dataclass
class OfferingConfigDataList:
    """A Sequence of OfferingConfigData."""

    data: List[OfferingConfigData]
    agents_config_data_list: List[AgentConfigData] = field(init=False)
    tools_config_data_list: List[ToolConfigData] = field(init=False)
    applications_spec_list: List[ApplicationsSpec] = field(init=False)

    def __post_init__(self) -> None:
        """Load lists of relevant config data, preserving ordering across fields."""
        self.agents_config_data_list = list(
            itertools.chain.from_iterable([oc.agents_config_data for oc in self.data])
        )
        self.tools_config_data_list = list(
            itertools.chain.from_iterable([oc.tools_config_data for oc in self.data])
        )
        self.applications_spec_list = list(
            itertools.chain.from_iterable(
                [tc.tool_config_spec.applications for tc in self.tools_config_data_list]
            )
        )


class OfferingConfigBuilder:
    """Class to build offering config data in the format prescribed for 'catalog' ingestion."""

    _manager_yaml_data: AgentYamlsData
    _tools: List[str]
    _domain: DomainName
    _publisher: PublisherName
    _agents: Dict[str, str]
    _version: SemanticVersion
    _offering_config_spec: OfferingConfigSpec
    _entrypoint_manager_name: str

    def build(
        self,
        manager_yaml_data: AgentYamlsData,
        catalog_metadata: CatalogMetadata,
        version: SemanticVersion,
        publisher: PublisherName,
    ) -> OfferingConfigData:
        """
        Args:
            manager_yaml_data: the manager yaml file as an entry point.
            catalog_metadata: the catalog metadata.
            version: the version for this catalog offering.
            publisher: the publisher name.

        Returns:
            The offering config data for this manager agent yaml data.
        """
        self._manager_yaml_data = manager_yaml_data
        self._entrypoint_manager_name = self._manager_yaml_data.entrypoint_manager_name

        self._agents = self._manager_yaml_data.get_agent_name_to_filepath_mapping()
        self._tools = self._manager_yaml_data.get_tool_dependencies()[1]
        self._publisher = publisher
        self._version = version
        self._offering_config_spec = self._get_offering_config_spec(catalog_metadata)
        self._domain = self._offering_config_spec.domain

        return OfferingConfigData(
            offering_name=self._offering_config_spec.name,
            agents_config_data=[
                AgentConfigBuilder().build(
                    agent_name=agent_name,
                    agent_role=(
                        AgentRoleName.MANAGER
                        if agent_name == self._entrypoint_manager_name
                        else AgentRoleName.COLLABORATOR
                    ),
                    agent_filepath=Path(agent_filepath),
                    domain=self._domain,
                    publisher=self._publisher,
                    catalog_metadata=catalog_metadata,
                )
                for agent_name, agent_filepath in self._agents.items()
            ],
            tools_config_data=[
                ToolConfigBuilder().build(
                    tool_name=tool_name,
                    domain=self._domain,
                    publisher=self._publisher,
                    catalog_metadata=catalog_metadata,
                )
                for tool_name in self._tools
            ],
            domain=self._domain,
            publisher=self._publisher,
            version=self._version,
            offering_config_spec=self._offering_config_spec,
            relative_export_filepath=self._get_relative_export_filepath(),
        )

    def _get_offering_config_spec(self, catalog_metadata: CatalogMetadata) -> OfferingConfigSpec:
        """
        Compiles, validates and returns all offering config data as prescribed by OfferingConfigSpec
        schema.

        Args:
            catalog_metadata: the catalog metadata

        Returns:
            offering config data as prescribed by OfferingConfigSpec schema.
        """
        name = catalog_metadata.manager_offering_map.get(self._entrypoint_manager_name)
        assert name is not None

        offering_metadata: OfferingMetadata | None = catalog_metadata.offering_map.get(name)
        assert offering_metadata, name
        assert offering_metadata.display_name is not None
        assert offering_metadata.domain is not None
        assert offering_metadata.description is not None
        assert (
            offering_metadata.domain in DomainName
        ), f"'{offering_metadata.domain}' is not a valid domain. Please add '{offering_metadata.domain}' to {DomainName}"
        display_name = offering_metadata.display_name
        domain = DomainName(offering_metadata.domain)
        publisher = self._publisher
        version = self._version
        description = offering_metadata.description
        config_data: OfferingConfigSpec

        try:
            assets = {publisher: AssetsSpec(agents=[*self._agents], tools=self._tools)}
            part_number = self._get_part_number_spec()
            scope = self._get_scope_spec()
            pricing = self._get_pricing_spec()

            # NOTE: this field defaults to '2999-01-01' for now, but it should be pulled
            # from a source-of-truth specified in metadata and validated here.
            delete_by = DEFAULT_DELETE_BY_DATE

            config_data = OfferingConfigSpec(
                name=name,
                display_name=display_name,
                domain=DomainName(domain),
                publisher=publisher,
                version=version,
                description=description,
                assets=assets,
                part_number=part_number,
                scope=scope,
                pricing=pricing,
                delete_by=delete_by,
            )
        except ValidationError as e:
            raise ValueError(e)
        return config_data

    def _get_rel_manager_filepath(self) -> Path:
        """Returns manager filepath relative to collaborator_agents dir."""
        manager_filepath = self._manager_yaml_data.manager_filepath
        directory = manager_filepath.parent

        while directory.name != "collaborator_agents":
            directory = directory.parent
        rel_manager_filepath = manager_filepath.relative_to(directory)

        return rel_manager_filepath

    def _get_relative_export_filepath(self) -> Path:
        """Returns the relative export filepath for offering config data."""
        filepath = (
            f"publishers/{self._publisher}/offerings/{self._offering_config_spec.name}/config.json"
        )
        return Path(filepath)

    def _get_part_number_spec(self) -> PartNumberSpec:
        """
        Compiles, validates and returns all part number data as prescribed by the PartNumberSpec
        schema.

        Returns:
            part number data as prescribed by the PartNumberSpec schema.
        """
        # TODO: these values need to be ingested from an offering data CSV.
        return PartNumberSpec(aws=None, ibm_cloud=None, cp4d=None)

    def _get_scope_spec(self) -> ScopeSpec:
        """
        Compiles, validates and returns all scope data as prescribed by the ScopeSpec schema.

        Returns:
            scope data as prescribed by the ScopeSpec schema.
        """
        # TODO: these values need to be ingested from an offering data CSV.
        return ScopeSpec(
            form_factor=FormFactorSpec(
                aws=PricingType.PAID, ibm_cloud=PricingType.PAID, cp4d=PricingType.PAID
            ),
            tenant_type=TenantTypeSpec(trial=PricingType.PAID),
        )

    def _get_pricing_spec(self) -> Optional[PricingSpec]:
        """
        Compiles, validates and returns all scope data as prescribed by the PricingSpec schema.

        Returns:
            scope data as prescribed by the PricingSpec schema.
        """
        # TODO: these values need to be ingested from an offering data CSV.
        pricing_type = PricingType.PAID  # Need to set based on metadata values

        if pricing_type is PricingType.FREE:
            return None
        return PricingSpec(currency="USD", amount="100.00", frequency=PricingFrequencyType.MONTHLY)

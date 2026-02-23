from dataclasses import dataclass
from pathlib import Path

from ibm_watsonx_orchestrate.agent_builder.agents.agent import Agent
from import_utils.catalog.metadata.catalog_metadata import AgentMetadata, CatalogMetadata
from import_utils.catalog.types import (
    DEFAULT_DELETE_BY_DATE,
    DEFAULT_LANGUAGES_SUPPORTED,
    MISSING_VALUE_SENTINEL,
    AgentConfigSpec,
    AgentRoleName,
    CategoryName,
    DomainName,
    PublisherName,
)
from pydantic import ValidationError


@dataclass
class AgentConfigData:
    """Dataclass representing the format for agent config data."""

    agent_filepath: Path  # the agent filepath

    agent_name: str  # the agent name
    domain: DomainName  # the domain name for this agent
    publisher: PublisherName  # the publisher name for this agent

    agent_config_spec: AgentConfigSpec  # the config spec schema
    relative_export_filepath: Path  # the relative export filepath for config data


class AgentConfigBuilder:
    """Class to build agent config data in the format prescribed for 'catalog' ingestion."""

    _domain: DomainName
    _publisher: PublisherName
    _agent_role: AgentRoleName

    def build(
        self,
        agent_name: str,
        agent_role: AgentRoleName,
        agent_filepath: Path,
        domain: DomainName,
        publisher: PublisherName,
        catalog_metadata: CatalogMetadata,
    ) -> AgentConfigData:
        """
        Args:
            agent_name: the name of the agent to process.
            agent_role: the agent role, either 'manager' or 'collaborator'.
            agent_filepath: filepath to the agent yaml file to process.
            domain: the domain name.
            publisher: the publisher name.
            catalog_metadata: catalog metadata

        Returns:
            The agent config data.
        """
        self._domain = domain
        self._publisher = publisher
        self._agent_role = agent_role
        rel_export_filepath = self._get_relative_export_filepath(agent_name)
        return AgentConfigData(
            agent_name=agent_name,
            agent_filepath=agent_filepath,
            domain=domain,
            publisher=publisher,
            relative_export_filepath=rel_export_filepath,
            agent_config_spec=self._get_agent_config_spec(agent_filepath, catalog_metadata),
        )

    def _get_agent_config_spec(
        self,
        agent_filepath: Path,
        catalog_metadata: CatalogMetadata,
    ) -> AgentConfigSpec:
        """
        Args:
            agent_filepath: filepath to the agent yaml file to process.
            catalog_metadata: the catalog metadata

        Returns:
            agent config data as prescribed by AgentConfigSpec schema.
        """
        agent_data: Agent = Agent.from_spec(str(agent_filepath))
        agent_config_metadata: AgentMetadata | None = catalog_metadata.agent_map.get(
            agent_data.name
        )
        assert agent_config_metadata, agent_data.name
        try:
            agent_data_args = {**agent_data.model_dump()}
            agent_data_args["display_name"] = (
                agent_data_args["display_name"] or MISSING_VALUE_SENTINEL
            )
            # NOTE: this field defaults to English for now, but it should be pulled
            # from a source-of-truth specified in either AgentSpec or ToolSpec (currently
            # there's no language_support field in either).
            language_support = DEFAULT_LANGUAGES_SUPPORTED

            # NOTE: this field defaults to '2999-01-01' for now, but it should be pulled
            # from a source-of-truth specified in metadata and validated here.
            delete_by = DEFAULT_DELETE_BY_DATE

            # NOTE: this is a temporary workaround to address the misalignment between
            # ADK's AgentSpec's 'guidelines' field and OOTB pipeline's agent spec validation.
            # See https://github.ibm.com/WatsonOrchestrate/wxo-domains/issues/4597
            agent_data_args["guidelines"] = agent_data_args["guidelines"] or []
            agent_data_args["display_name"] = agent_config_metadata.display_name
            agent_data_args["description"] = agent_config_metadata.description
            config_data = AgentConfigSpec(
                **agent_data_args,
                category=CategoryName.AGENT,
                agent_role=self._agent_role,
                publisher=self._publisher,
                supported_apps=[],
                glossary=[],
                tags=[self._domain],
                language_support=language_support,
                delete_by=delete_by,
            )
        except ValidationError as e:
            raise ValueError(e)
        return config_data

    def _get_relative_export_filepath(self, agent_name: str) -> Path:
        """
        Args:
            agent_name: the name of the agent to process.

        Returns:
            the relative export filepath for agent config data.
        """
        filepath = f"publishers/{self._publisher}/agents/{agent_name}/config.json"
        return Path(filepath)

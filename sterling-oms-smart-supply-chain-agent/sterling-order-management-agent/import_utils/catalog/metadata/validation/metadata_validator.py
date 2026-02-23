from dataclasses import dataclass, field, fields
from enum import StrEnum
from typing import List, Mapping, Optional

from import_utils.catalog.metadata.catalog_metadata import CatalogMetadata
from import_utils.catalog.repo_artifact_inventory.repo_artifact_inventory import (
    RepoArtifactInventory,
    build_repo_artifact_inventory,
)
from rich.console import Console
from rich.table import Table
from rich.text import Text


class MissingMetadataType(StrEnum):
    """Class to define 'missing metadata' types."""

    AGENT = "agent"
    TOOL = "tool"
    OFFERING = "offering"
    APP_ID = "app-id"


@dataclass
class MissingMetadataEntry:
    """Dataclass that defines a single missing metadata entry."""

    key: str  # the metadata entry key
    metadata_type: MissingMetadataType  # the metadata type
    missing_fields: List[str] = field(default_factory=list)  # list of missing metadata fields
    missing_entry: bool = False  # whether the entire entry is missing from metadata


class MetadataValidator:
    """A class that validates metadata against repository artifacts and provides reporting
    capabilities."""

    def __init__(
        self,
        metadata: CatalogMetadata,
        repo_artifact_inventory: Optional[RepoArtifactInventory] = None,
    ):
        """
        Initializes the MetadataValidator instance.

        Args:
            metadata: The CatalogMetadata instance to evaluate.
            repo_artifact_inventory: Optional. A RepoArtifactInventory instance which will be used to validate
                metadata against existing repo artifacts. If not provided, it will be generated automatically
                using manager_offering_map from the metadata.
        """
        self.metadata = metadata

        if repo_artifact_inventory is None:
            self._repo_artifact_inventory = build_repo_artifact_inventory(
                only_managers=list(metadata.manager_offering_map)
            )
        else:
            self._repo_artifact_inventory = repo_artifact_inventory

        self._missing_metadata = self._get_missing_metadata()

    @property
    def missing_metadata(self) -> List[MissingMetadataEntry]:
        """
        Returns all missing or incomplete entries in catalog metadata.

        Returns:
            A list of objects representing missing or
            incomplete metadata entries. Returns an empty list if all metadata is complete.
        """
        return self._missing_metadata

    @property
    def has_missing_metadata(self) -> bool:
        """
        Returns True if there is any missing metadata, False otherwise.

        This property efficiently checks if any metadata entries are missing
        or incomplete without requiring iteration through the entire list.

        Returns:
            True if there is missing metadata, False otherwise.
        """
        return bool(self._missing_metadata)

    def _get_missing_metadata(self) -> List[MissingMetadataEntry]:
        """
        Returns all missing or incomplete entries in catalog metadata.

        Returns:
            A list of MissingMetadataEntry objects.
        """
        missing_metadata: List[MissingMetadataEntry] = []

        for manager in self._repo_artifact_inventory.all_managers:
            offering = self.metadata.manager_offering_map.get(manager)
            assert offering is not None, f"Offering missing for manager {manager!r}."
            missing_metadata_entry = self._get_missing_metadata_entry(
                key=offering,
                metadata_map=self.metadata.offering_map,
                metadata_type=MissingMetadataType.OFFERING,
            )
            if missing_metadata_entry is not None:
                missing_metadata.append(missing_metadata_entry)

        for agent in self._repo_artifact_inventory.all_agents:
            missing_metadata_entry = self._get_missing_metadata_entry(
                key=agent,
                metadata_map=self.metadata.agent_map,
                metadata_type=MissingMetadataType.AGENT,
            )
            if missing_metadata_entry is not None:
                missing_metadata.append(missing_metadata_entry)

        for tool in self._repo_artifact_inventory.all_tools:
            missing_metadata_entry = self._get_missing_metadata_entry(
                key=tool,
                metadata_map=self.metadata.tool_map,
                metadata_type=MissingMetadataType.TOOL,
            )
            if missing_metadata_entry is not None:
                missing_metadata.append(missing_metadata_entry)

        for application in self._repo_artifact_inventory.all_app_ids:
            missing_metadata_entry = self._get_missing_metadata_entry(
                key=application,
                metadata_map=self.metadata.application_map,
                metadata_type=MissingMetadataType.APP_ID,
            )
            if missing_metadata_entry is not None:
                missing_metadata.append(missing_metadata_entry)

        return missing_metadata

    def _get_missing_metadata_entry(
        self, key: str, metadata_map: Mapping, metadata_type: MissingMetadataType
    ) -> Optional[MissingMetadataEntry]:
        """
        A helper method to get missing metadata fields for the given metadata entry.

        Args:
            key: The key of the metadata entry to check.
            metadata_map: The metadata map to query against.
            metadata_type: The metadata type for this query.

        Returns:
            Returns None if no missing fields are found, otherwise returns a MissingMetadataEntry instance.
        """
        metadata = metadata_map.get(key)

        if metadata is None:
            return MissingMetadataEntry(key=key, metadata_type=metadata_type, missing_entry=True)

        missing_fields = [f.name for f in fields(metadata) if getattr(metadata, f.name) is None]

        if missing_fields:
            return MissingMetadataEntry(
                key=key, missing_fields=missing_fields, metadata_type=metadata_type
            )
        return None

    def get_missing_metadata_report(self) -> Table:
        """
        Returns a rich.table Table with a report of all the missing metadata entries.

        Returns:
            A formatted Table object containing a report of all the missing metadata.
        """
        report_table = Table(
            title="MISSING METADATA REPORT", header_style="bold white", show_lines=True
        )

        report_table.add_column("Type", no_wrap=True)
        report_table.add_column("Key", no_wrap=True)
        report_table.add_column("Missing Fields", no_wrap=True)

        for entry in self.missing_metadata:
            missing_str = (
                Text(f"Entire entry is missing in metadata", "red")
                if entry.missing_entry
                else Text(", ".join(entry.missing_fields), "bright_cyan")
            )
            report_table.add_row(entry.metadata_type, entry.key, missing_str)

        return report_table

    def print_missing_metadata_report(self, console: Optional[Console] = None) -> None:
        """
        Prints a report of all the missing metadata entries.

        Args:
            console: an optional rich.console.Console instance for output formatting.
                If not provided, a new Console instance will be created.
        """
        console = console or Console()
        console.print(self.get_missing_metadata_report())

    def print_offerings_report(self, console: Optional[Console] = None) -> None:
        """
        Prints a report of all the offerings specified in metadata.

        Args:
            console: an optional rich.console.Console instance for output formatting.
                If not provided, a new Console instance will be created.
        """
        console = console or Console()
        console.print(self.get_offerings_report())

    def get_offerings_report(self) -> Table:
        """
        Returns a rich.table Table containing a report of all the offerings specified in metadata
        and validated against existing repo artifacts.

        Returns:
             A formatted Table object containing a rendered offerings report.
        """
        report_table = Table(title="OFFERINGS REPORT", header_style="bold white", show_lines=True)

        report_table.add_column("Offering", no_wrap=True)
        report_table.add_column("Manager Agent", no_wrap=True)

        # NOTE: only manager agents with corresponding offerings are included here.
        for manager in self._repo_artifact_inventory.all_managers:
            offering = self.metadata.manager_offering_map.get(manager)
            assert offering is not None, f"Offering missing for manager {manager!r}."
            report_table.add_row(offering, manager)

        for manager in self._repo_artifact_inventory.excluded_managers:
            excluded_str = Text("EXCLUDED - no offering defined in metadata", style="red")
            report_table.add_row(excluded_str, manager)

        return report_table

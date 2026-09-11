from dataclasses import dataclass
from pathlib import Path
from typing import List

from import_utils.catalog.types import ApplicationsConfigSpec, ApplicationsSpec, PublisherName
from more_itertools import unique_everseen
from pydantic import ValidationError
from pydantic_extra_types.semantic_version import SemanticVersion  # pants: no-infer-dep


@dataclass
class ApplicationsConfigData:
    """Dataclass representing the format for applications config data."""

    applications_config_spec: ApplicationsConfigSpec  # the applications config spec schema
    relative_export_filepath: Path  # the relative export filepath for config data


class ApplicationsConfigBuilder:
    """Class to build applications config data in the format prescribed for 'catalog' ingestion."""

    _version: SemanticVersion
    _publisher: PublisherName
    _applications_data: List[ApplicationsSpec]

    def build(
        self,
        version: SemanticVersion,
        publisher: PublisherName,
        applications_data: List[ApplicationsSpec],
    ) -> ApplicationsConfigData:
        """
        Args:
            version: the version for this release of applications config data.
            publisher: the publisher name.
            applications_data: the list of applications for for this release of applications config
                data.

        Returns:
            the applications config data.
        """
        self._version = version
        self._publisher = publisher
        self._applications_data = applications_data
        rel_export_filepath = self._get_relative_export_filepath()
        return ApplicationsConfigData(
            applications_config_spec=self._get_applications_config_spec(),
            relative_export_filepath=rel_export_filepath,
        )

    def _get_applications_config_spec(self) -> ApplicationsConfigSpec:
        """Returns applications config data as prescribed by ApplicationsConfigSpec schema."""
        # TODO: add validation for uniqueness of items in 'applications' in ApplicationsConfigSpec.
        try:
            unique_applications = list(unique_everseen(self._applications_data))
            applications = sorted(unique_applications, key=lambda x: x.app_id)
            config_data = ApplicationsConfigSpec(
                version=self._version,
                applications=applications,
            )
        except ValidationError as e:
            raise ValueError(e)
        return config_data

    def _get_relative_export_filepath(self) -> Path:
        """Returns the relative export filepath for applications config data."""
        filepath = f"publishers/{self._publisher}/applications/config.json"
        return Path(filepath)

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List
import warnings

from import_utils.catalog.metadata.raw_metadata.types import (
    AgentsToolsHeaders,
    ConnectionsHeaders,
    IconsHeaders,
    PartNumbersHeaders,
    SheetData,
)
import numpy as np
import pandas as pd
from pydantic import BaseModel


def clean_df_nan_values(sheet_map: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """
    Cleans a dictionary of dataframes by applying standard preprocessing steps.

    This function:
    - Drops fully empty rows
    - Strips leading/trailing whitespace from string cells
    - Removes duplicate rows
    - Replaces NaN and empty strings ("") with None
    - Converts integer values to strings (to allow downstream string validation)

    Args:
        sheet_map: A dictionary mapping sheet names to raw DataFrames.

    Returns:
        A dictionary with cleaned DataFrames for each sheet.
    """
    clean_sheet_map = {}
    for sheet, df in sheet_map.items():
        # Drop rows with empty values in 'index' column
        clean_df = df.dropna(how="all")
        # Strip whitespaces from data
        clean_df = clean_df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        # Drop duplicate rows
        clean_df = clean_df.drop_duplicates()
        # Replace 'nan', "" values with 'None'
        clean_df = clean_df.replace({np.nan: None, "": None})
        # Convert integers to strings, integer validation should happen downstream of loading.
        clean_df = clean_df.map(lambda x: str(x) if isinstance(x, (int, np.integer)) else x)

        clean_sheet_map[sheet] = clean_df

    return clean_sheet_map


class AgentsToolsRow(BaseModel):
    """Represents a single row from the 'Agent and Tools' sheet."""

    domain: str | None

    offering: str | None
    offering_display_name: str | None
    offering_description: str | None

    agent: str | None
    agent_display_name: str | None
    agent_description: str | None

    tool: str | None
    tool_display_name: str | None
    tool_description: str | None
    application_name: str | None

    icon: str | None


class ConnectionsRow(BaseModel):
    """Represents a single row from the 'Connections' sheet."""

    app_id: str | None
    app_id_name: str | None
    auth_type: str | None
    app_id_icon: str | None


class PartNumbersRow(BaseModel):
    """Represents a single row from the 'Part Numbers' sheet."""

    domain: str | None
    offering: str | None
    ibm_cloud_pn: str | None
    aws_pn: str | None
    description: str | None
    monthly_price: str | None


class IconsRow(BaseModel):
    """Represents a single row from the 'Icons' sheet."""

    name: str | None
    svg_icon: str | None


@dataclass
class RawCatalogMetadata:
    """Container for raw catalog data loaded from an Excel workbook."""

    agent_and_tools_sheet: List[AgentsToolsRow]
    connections_sheet: List[ConnectionsRow]
    part_numbers_sheet: List[PartNumbersRow]
    icons_sheet: List[IconsRow]

    @classmethod
    def from_filepath(cls, filepath: Path) -> "RawCatalogMetadata":
        """
        Loads raw catalog data from an Excel file and maps it into structured row classes.

        Args:
            filepath: Path to the Excel file containing the catalog metadata.

        Returns:
            A RawCatalogData instance populated with structured rows from each sheet.
        """
        # Suppress openpyxl Data Validation warning
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Data Validation extension is not supported")
            sheet_map = pd.read_excel(filepath, sheet_name=None)

        # Clean up nan, empty string and duplicate values
        sheet_map = clean_df_nan_values(sheet_map)

        assert all(
            h in sheet_map for h in SheetData
        ), f"SheetData values: {list(SheetData)} do not match sheet names: {list(sheet_map)}"

        assert all(
            h in sheet_map[SheetData.AGENTS_AND_TOOLS] for h in AgentsToolsHeaders
        ), f"""AgentsToolsHeaders values: {list(AgentsToolsHeaders)} do not match 
        {SheetData.AGENTS_AND_TOOLS.value!r} column names: {list(sheet_map[SheetData.AGENTS_AND_TOOLS])}"""

        assert all(
            h in sheet_map[SheetData.CONNECTIONS] for h in ConnectionsHeaders
        ), f"""ConnectionsHeaders values: {list(ConnectionsHeaders)} do not match 
        {SheetData.CONNECTIONS.value!r}  names: {list(sheet_map[SheetData.CONNECTIONS])}"""

        assert all(
            h in sheet_map[SheetData.PART_NUMBERS] for h in PartNumbersHeaders
        ), f"""PartNumbersHeaders values: {list(PartNumbersHeaders)} do not match 
        {SheetData.PART_NUMBERS.value!r}  names: {list(sheet_map[SheetData.PART_NUMBERS])}"""

        assert all(
            h in sheet_map[SheetData.ICONS] for h in IconsHeaders
        ), f"""IconsHeaders values: {list(IconsHeaders)} do not match 
        {SheetData.ICONS.value!r}  names: {list(sheet_map[SheetData.ICONS])}"""

        agent_and_tools_sheet = [
            AgentsToolsRow(
                domain=row[AgentsToolsHeaders.DOMAIN],
                offering=row[AgentsToolsHeaders.OFFERING],
                offering_display_name=row[AgentsToolsHeaders.OFFERING_DISPLAY_NAME],
                offering_description=row[AgentsToolsHeaders.OFFERING_DESCRIPTION],
                agent=row[AgentsToolsHeaders.AGENT],
                agent_display_name=row[AgentsToolsHeaders.AGENT_DISPLAY_NAME],
                agent_description=row[AgentsToolsHeaders.AGENT_DESCRIPTION],
                tool=row[AgentsToolsHeaders.TOOL],
                tool_display_name=row[AgentsToolsHeaders.TOOL_DISPLAY_NAME],
                tool_description=row[AgentsToolsHeaders.TOOL_DESCRIPTION],
                application_name=row[AgentsToolsHeaders.APPLICATION_NAME],
                icon=row[AgentsToolsHeaders.ICON],
            )
            for _, row in sheet_map[SheetData.AGENTS_AND_TOOLS].iterrows()
        ]
        connections_sheet = [
            ConnectionsRow(
                app_id=row[ConnectionsHeaders.APP_ID],
                app_id_name=row[ConnectionsHeaders.APP_ID_NAME],
                auth_type=row[ConnectionsHeaders.AUTH_TYPE],
                app_id_icon=row[ConnectionsHeaders.ICON],
            )
            for _, row in sheet_map[SheetData.CONNECTIONS].iterrows()
        ]

        part_numbers_sheet = [
            PartNumbersRow(
                domain=row[PartNumbersHeaders.DOMAIN],
                offering=row[PartNumbersHeaders.OFFERING],
                ibm_cloud_pn=row[PartNumbersHeaders.IBM_CLOUD_PN],
                aws_pn=row[PartNumbersHeaders.AWS_PN],
                description=row[PartNumbersHeaders.DESCRIPTION],
                monthly_price=row[PartNumbersHeaders.MONTHLY_PRICE],
            )
            for _, row in sheet_map[SheetData.PART_NUMBERS].iterrows()
        ]

        icons_sheet = [
            IconsRow(
                name=row[IconsHeaders.NAME],
                svg_icon=row[IconsHeaders.SVG_ICON],
            )
            for _, row in sheet_map[SheetData.ICONS].iterrows()
        ]

        return cls(
            agent_and_tools_sheet=agent_and_tools_sheet,
            connections_sheet=connections_sheet,
            part_numbers_sheet=part_numbers_sheet,
            icons_sheet=icons_sheet,
        )

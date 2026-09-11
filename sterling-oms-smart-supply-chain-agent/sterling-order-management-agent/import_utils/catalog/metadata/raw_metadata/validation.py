from typing import List, Set

from import_utils.catalog.metadata.raw_metadata.raw_metadata import RawCatalogMetadata
from utils.validators import is_valid_svg_string


def validate_raw_metadata(raw_metadata: RawCatalogMetadata) -> None:
    """
    Validates raw metadata.

    Args:
        raw_metadata: the raw catalog metadata to validate.
    """

    offering_keys: List[str] = []

    # Build a set of available icon names from the Icons sheet
    available_icons: Set[str] = {
        icon_row.name for icon_row in raw_metadata.icons_sheet if icon_row.name is not None
    }

    for agent_tool_row in raw_metadata.agent_and_tools_sheet:
        offering_key = agent_tool_row.offering
        agent_key = agent_tool_row.agent
        tool_key = agent_tool_row.tool
        icon_key = agent_tool_row.icon

        if _key := (agent_key or tool_key):
            # If an icon is specified, validate that it exists in the Icons sheet
            if icon_key:
                assert (
                    icon_key in available_icons
                ), f"{_key!r} references icon {icon_key!r} which does not exist in the Icons sheet"

        assert not (
            agent_key and tool_key
        ), f"Row cannot contain both agent and tool values. Got agent = {agent_key!r}, tool = {tool_key!r}"
        if offering_key:
            assert (
                not offering_key in offering_keys
            ), f"Multiple entries for offering: {offering_key}"
            assert (
                offering_key and agent_key
            ), f"Row contains offering but no manager agent for offering: {offering_key!r}"
            offering_keys.append(offering_key)

    for connections_row in raw_metadata.connections_sheet:
        assert connections_row.app_id is not None, f"app_id field missing in row: {connections_row}"
        assert (
            connections_row.app_id_icon is not None
        ), f"app_id icon name missing in row: {connections_row}"

        # Validate that the icon exists in the Icons sheet
        icon_name = connections_row.app_id_icon
        assert (
            icon_name in available_icons
        ), f"Connection {connections_row.app_id!r} references icon {icon_name!r} which does not exist in the Icons sheet"

    for part_number_row in raw_metadata.part_numbers_sheet:
        assert (
            part_number_row.offering is not None
        ), f"offering field missing for row: {part_number_row}"

    for icon_row in raw_metadata.icons_sheet:
        assert icon_row.name is not None, f"icon 'name' field missing for row: {icon_row}"

        # Note, there are currently no requirements for icon rows to specify an SVG string.
        # If SVG string is required in the future, add 'assert icon_row.svg_icon is not None' here.

        if icon_row.svg_icon:
            if not is_valid_svg_string(icon_row.svg_icon):
                print(f"SVG parsing failed for {icon_row.name!r}'s SVG icon")

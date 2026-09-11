import argparse
import json
from typing import Any
import xml.etree.ElementTree as ET

import requests
from requests.auth import HTTPBasicAuth

from agent_ready_tools.utils.credentials import CredentialKeys, get_tool_credentials
from agent_ready_tools.utils.systems import Systems

TYPE_MAPPING: dict[str, str] = {
    "Edm.String": "string",
    "Edm.Boolean": "boolean",
    "Edm.Int32": "integer",
    "Edm.Int64": "integer",
    "Edm.Decimal": "number",
    "Edm.DateTime": "string",
    "Edm.DateTimeOffset": "string",
}

NAMESPACES: dict[str, str] = {
    "edmx": "http://schemas.microsoft.com/ado/2007/06/edmx",
    "edm": "http://schemas.microsoft.com/ado/2008/09/edm",
    "sap": "http://www.successfactors.com/edm/sap",
    "m": "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata",
}


def get_api_metadata(base_url: str, auth: HTTPBasicAuth, api_name: str) -> ET.Element:
    """
    Get the SAP SuccessFactors OData metadata document for the specified API.

    Args:
        base_url: The base URL of the SAP SuccessFactors API.
        auth: The HTTPBasicAuth object to use for authentication.
        api_name: The name of the API for which the metadata should be retrieved.

    Returns:
        The root element of the parsed XML metadata document.
    """
    metadata_url = f"{base_url}/odata/v2/{api_name}/$metadata"
    response = requests.get(url=metadata_url, auth=auth)
    response.raise_for_status()
    return ET.fromstring(response.text)


def get_description(xml_data: ET.Element, entity_name: str) -> str:
    """
    Get the description for the specified API EntitySet.

    Args:
        xml_data: The root element of the parsed XML metadata document.
        entity_name: The name of the API EntitySet for which the description is to be extracted.

    Returns:
        The extracted long description if available, otherwise an empty string.
    """
    for schema in xml_data.findall(".//edm:Schema", NAMESPACES):
        entity_set = schema.find(
            f"edm:EntityContainer/edm:EntitySet[@Name='{entity_name}']", NAMESPACES
        )
        if entity_set is not None:
            documentation = entity_set.find("edm:Documentation", NAMESPACES)
            if documentation is not None:
                description = documentation.find("edm:LongDescription", NAMESPACES)
                if description is not None and description.text:
                    return description.text.strip()
    return ""


def parse_entity_type(xml_data: ET.Element, entity_name: str) -> ET.Element:
    """
    Search the XML metadata for an EntityType element with the specified name.

    Args:
        xml_data: The root element of the parsed XML metadata document.
        entity_name: The name of the EntityType to locate within the metadata.

    Returns:
        The matching EntityType element from the metadata.
    """
    for schema in xml_data.findall(".//edm:Schema", NAMESPACES):
        entity_type = schema.find(f"edm:EntityType[@Name='{entity_name}']", NAMESPACES)
        if entity_type is not None:
            return entity_type
    raise ValueError(f"EntityType '{entity_name}' not found in the metadata.")


def convert_entity_to_json_schema(
    entity: ET.Element, api_name: str, description: str
) -> dict[str, Any]:
    """
    Convert an OData EntityType XML element into a JSON Schema representation.

    Args:
        entity: The XML Element corresponding to the OData EntityType.
        api_name: The API name associated with the provided entity.
        description: The description associated with the provided entity.

    Returns:
        A dictionary representing the JSON Schema for the entity.
    """
    schema: dict[str, Any] = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": api_name,
        "description": description,
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    }

    for prop in entity.findall("edm:Property", NAMESPACES):
        name = prop.attrib.get("Name")
        edm_type = prop.attrib.get("Type", "")
        json_type = TYPE_MAPPING.get(edm_type, "string")

        prop_schema: dict[str, Any] = {"type": json_type}

        if edm_type == "Edm.DateTime":
            prop_schema["format"] = "date"
        elif edm_type == "Edm.DateTimeOffset":
            prop_schema["format"] = "date-time"

        max_length = prop.attrib.get("MaxLength")
        if max_length is not None:
            try:
                prop_schema["maxLength"] = int(max_length)
            except ValueError:
                pass

        label = prop.attrib.get("{http://www.successfactors.com/edm/sap}label")
        if label:
            prop_schema["description"] = label

        if name:
            schema["properties"][name] = prop_schema
            if prop.attrib.get("Nullable", "true").lower() == "false":
                schema["required"].append(name)

    return schema


def main() -> None:
    """Generates a JSON schema representing the input parameters for the provided SuccessFactors
    API."""
    parser = argparse.ArgumentParser(
        description="Generate a JSON schema representing the input parameters for the provided SuccessFactors API."
    )
    parser.add_argument("api_name", type=str, help="Name of the SuccessFactors API entity.")
    args = parser.parse_args()

    credentials = get_tool_credentials(Systems.SAP_SUCCESSFACTORS)
    base_url = credentials[CredentialKeys.BASE_URL]
    username = credentials[CredentialKeys.USERNAME]
    password = credentials[CredentialKeys.PASSWORD]
    auth = HTTPBasicAuth(username=username, password=password)

    metadata = get_api_metadata(base_url=base_url, auth=auth, api_name=args.api_name)
    description = get_description(xml_data=metadata, entity_name=args.api_name)
    entity = parse_entity_type(xml_data=metadata, entity_name=args.api_name)
    json_schema = convert_entity_to_json_schema(
        entity=entity, api_name=args.api_name, description=description
    )
    print(json.dumps(json_schema, indent=2))


if __name__ == "__main__":
    main()

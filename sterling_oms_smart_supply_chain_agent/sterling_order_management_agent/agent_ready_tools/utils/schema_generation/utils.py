from typing import Any, List

import requests

COMMON_KEYS: list[str] = [
    "type",
    "format",
    "description",
    "default",
    "enum",
    "maximum",
    "minimum",
    "maxLength",
    "minLength",
    "pattern",
]


def get_api_spec(url: str) -> dict[str, Any]:
    """
    Retrieve the OpenAPI Schema from the provided URL.

    Args:
        url: The URL to retrieve the OpenAPI Schema from.

    Returns:
        A JSON representation of the OpenAPI Schema.
    """
    response = requests.get(url)
    response.raise_for_status()
    return response.json()


def resolve_ref(spec: dict[str, Any], ref: str) -> dict[str, Any]:
    """
    Resolve a local JSON reference within the provided spec.

    Args:
        spec: A JSON representation of the API's OpenAPI Schema.
        ref: The reference string that needs to be resolved.

    Returns:
        The dictionary object from the spec pointed to by the reference.
    """
    if not ref.startswith("#/"):
        raise ValueError(f"Only local refs are supported, got: {ref}")
    parts = ref.lstrip("#/").split("/")
    result = spec
    for part in parts:
        if part not in result:
            raise KeyError(f"Reference part '{part}' not found in spec.")
        result = result[part]
    return result


def fully_resolve_schema(spec: Any, schema: dict[str, Any], current_ref: str = "") -> Any:
    """
    Recursively resolve any $ref entries in the given schema using the provided spec.

    Args:
        spec: A JSON representation of the API's OpenAPI Schema.
        schema: The schema with entries to be resolved.
        current_ref: The current ref to avoid circular references.

    Returns:
        The fully resolved schema.
    """
    if isinstance(schema, dict):
        if "$ref" in schema and schema["$ref"] != current_ref:
            current_ref = schema["$ref"]
            resolved = resolve_ref(spec, current_ref)
            return fully_resolve_schema(spec=spec, schema=resolved, current_ref=current_ref)

        if "allOf" in schema and isinstance(schema["allOf"], list):
            merged = {}
            for item in schema["allOf"]:
                resolved_item = fully_resolve_schema(spec=spec, schema=item)
                if isinstance(resolved_item, dict) and resolved_item:
                    merged.update(resolved_item)

            for key, value in schema.items():
                if key != "allOf":
                    merged[key] = fully_resolve_schema(spec=spec, schema=value)
            return merged

        else:
            return {
                k: fully_resolve_schema(spec=spec, schema=v, current_ref=current_ref)
                for k, v in schema.items()
            }
    elif isinstance(schema, list):
        return [fully_resolve_schema(spec=spec, schema=item) for item in schema]
    else:
        return schema


def get_api_summary(spec: dict[str, Any], api_path: str, method: str) -> str:
    """
    Retrieve the summary for the specified API path and HTTP method.

    Args:
        spec: A JSON representation of the API's OpenAPI Schema.
        api_path: The API endpoint path.
        method: The HTTP method used for the endpoint.

    Returns:
        The summary for the specified API operation.
    """
    path_item = spec.get("paths", {})[api_path][method]
    return path_item.get("summary", path_item.get("description", ""))


def get_all_parameters(
    spec: dict[str, Any], api_path: str, method_filter: str
) -> List[dict[str, Any]]:
    """
    Retrieve all parameters for the specified API path and HTTP method.

    Args:
        spec: A JSON representation of the API's OpenAPI Schema.
        api_path: The API endpoint path.
        method_filter: The HTTP method used for the endpoint.

    Returns:
        A list of parameter objects for the specified API path and method.
    """
    paths = spec.get("paths", {})
    if api_path not in paths:
        raise ValueError(f"Path '{api_path}' not found in the API spec.")

    path_item = paths[api_path]
    params_by_key: dict[str, dict[str, Any]] = {}

    # Add any path-level parameters.
    for param in path_item.get("parameters", []):
        key = f"{param.get('in')}:{param.get('name')}"
        params_by_key[key] = param

    # Only include parameters from the specified HTTP method.
    for method, operation in path_item.items():
        if method != method_filter:
            continue

        for param in operation.get("parameters", []):
            key = f"{param.get('in')}:{param.get('name')}"
            params_by_key[key] = param

    return list(params_by_key.values())


def convert_parameter_to_schema(spec: dict[str, Any], param: dict[str, Any]) -> dict[str, Any]:
    """
    Convert a single parameter object to a JSON schema property.

    Args:
        spec: A JSON representation of the API's OpenAPI Schema.
        param: The parameter object from the API specification.

    Returns:
        A dictionary representing the JSON schema property for the parameter.
    """
    location = param.get("in")
    schema: dict[str, Any] = {"in": location}

    if location == "body":
        # For a body parameter, the schema is under "schema".
        param_schema = param["schema"]
        if "$ref" in param_schema:
            resolved = fully_resolve_schema(spec=spec, schema=param_schema)
            schema.update(resolved)
        else:
            schema.update(param_schema)
    else:
        # For non-body parameters, copy over common keys.
        for key in COMMON_KEYS:
            if key in param:
                schema[key] = param[key]

        # Default type to string if not specified.
        if "type" not in schema:
            schema["type"] = "string"

    return schema


def generate_json_schema(
    spec: dict[str, Any], api_path: str, method: str, parameters: List[dict[str, Any]]
) -> dict[str, Any]:
    """
    Generate a JSON schema representation of the input parameters for an API endpoint.

    Args:
        spec: A JSON representation of the API's OpenAPI Schema.
        api_path: The API endpoint path.
        method: The HTTP method used for the endpoint.
        parameters: A list of parameter objects to include in the schema.

    Returns:
        The JSON schema for the specified API endpoint.
    """
    properties: dict[str, Any] = {}
    required: List[str] = []

    for param in parameters:
        name = param.get("name", "")
        param_schema = convert_parameter_to_schema(spec=spec, param=param)
        properties[name] = param_schema
        if param.get("required", False):
            required.append(name)

    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": api_path,
        "description": get_api_summary(spec=spec, api_path=api_path, method=method),
        "type": "object",
        "properties": properties,
        "required": required,
    }

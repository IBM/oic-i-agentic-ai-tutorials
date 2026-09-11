import argparse
import json
from typing import Any

from agent_ready_tools.utils.schema_generation.utils import fully_resolve_schema, get_api_spec


def get_response_schema(spec: dict[str, Any], api_path: str, method: str) -> dict[str, Any]:
    """
    Generates a JSON schema representation of the response for the specified API endpoint and
    method.

    Args:
        spec: A JSON representation of the API's OpenAPI Schema.
        api_path: The API endpoint path.
        method: The HTTP method used for the endpoint.

    Returns:
        The JSON schema for the specified API endpoint.
    """
    paths = spec.get("paths", {})
    if api_path not in paths:
        raise ValueError(f"Path {api_path} not found in spec")

    path_item = paths[api_path]
    operation = path_item.get(method.lower(), {})
    responses = operation.get("responses", {})

    for code in ["200", "201", "default"]:
        if code in responses:
            response_obj = responses[code]
            if "schema" in response_obj:
                schema = response_obj["schema"]
                return fully_resolve_schema(spec=spec, schema=schema)
    return {}


def main() -> None:
    """Generates a JSON schema representing the output for the provided Workday API."""
    parser = argparse.ArgumentParser(
        description="Generate a JSON schema representing the output for the provided Workday API."
    )
    parser.add_argument("url", type=str, help="The URL to the API's OpenAPI Schema.")
    parser.add_argument(
        "path",
        type=str,
        help="The API endpoint path. Example: '/workers/{ID}/businessTitleChanges'.",
    )
    parser.add_argument(
        "method",
        type=str,
        choices=["get", "post", "put", "delete", "patch", "options", "head"],
        help="The HTTP method.",
    )
    args = parser.parse_args()

    spec = get_api_spec(args.url)
    response_schema = get_response_schema(spec, args.path, args.method)
    print(json.dumps(response_schema, indent=2))


if __name__ == "__main__":
    main()

import argparse
import json

from agent_ready_tools.utils.schema_generation.utils import (
    generate_json_schema,
    get_all_parameters,
    get_api_spec,
)


def main() -> None:
    """Generates a JSON schema representing the input parameters for the provided Workday API."""
    parser = argparse.ArgumentParser(
        description="Generate a JSON schema representing the input parameters for the provided Workday API."
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
    parameters = get_all_parameters(spec=spec, api_path=args.path, method_filter=args.method)
    json_schema = generate_json_schema(
        spec=spec, api_path=args.path, method=args.method, parameters=parameters
    )
    print(json.dumps(json_schema, indent=2))


if __name__ == "__main__":
    main()

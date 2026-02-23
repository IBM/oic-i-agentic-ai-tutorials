import argparse
import json
import tempfile

from agent_ready_tools.clients.coupa_client import get_coupa_client
from agent_ready_tools.utils.schema_generation.utils import generate_json_schema, get_all_parameters

API_DOCS_PATH = "api_docs/:id"


def main() -> None:
    """Generates a JSON schema representing the input parameters for the provided Workday API."""
    parser = argparse.ArgumentParser(
        description="Generate a JSON schema representing the input parameters for the provided Workday API."
    )
    parser.add_argument(
        "path",
        type=str,
        help="The API endpoint path. Example: '/suppliers'.",
    )
    parser.add_argument(
        "method",
        type=str,
        choices=["get", "post", "put", "delete", "patch", "options", "head"],
        help="The HTTP method.",
    )
    parser.add_argument("--to_file", action="store_true", help="Save result to a temp file.")
    args = parser.parse_args()

    client = get_coupa_client()
    spec = client.get_request(API_DOCS_PATH)
    parameters = get_all_parameters(spec=spec, api_path=args.path, method_filter=args.method)
    json_schema = generate_json_schema(
        spec=spec, api_path=args.path, method=args.method, parameters=parameters
    )
    if args.to_file:
        with tempfile.NamedTemporaryFile(mode="w+t", delete=False) as temp_file:
            temp_file.write(json.dumps(json_schema, indent=2))
            print(f"Schema written to: {temp_file.name}")
    else:
        print(json.dumps(json_schema, indent=2))


if __name__ == "__main__":
    main()

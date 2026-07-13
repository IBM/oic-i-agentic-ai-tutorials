# Dummy Customer Tools Repo With FastAPI Wrapper

This folder models the situation where a customer already has a Python tools repository with tool files and a `requirements.txt`. The added layer is a FastAPI wrapper and Dockerfile that expose those existing tools as OpenAPI operations.

The pattern is:

1. Keep customer-owned tool logic in `tools/`.
2. Keep customer-owned dependencies in `requirements.txt`.
3. Add FastAPI dependencies in `requirements-fastapi.txt`.
4. Add request and response models in `app/models.py`.
5. Expose each existing tool through a stable FastAPI route in `app/main.py`.
6. Share the generated OpenAPI document from `/openapi.json` with the tool consumer.

## Layout

```text
app/
  main.py                  FastAPI routes and OpenAPI metadata
  models.py                Pydantic request and response schemas
  security.py              Optional API key enforcement
  tool_registry.py         Human-readable tool catalog
tools/
  math_tools.py            Existing customer-style tool example
  text_tools.py            Existing customer-style tool example
  customer_tools.py        Existing customer-style tool example
openapi/
  tool-bindings.json       Example OpenAPI tool binding payloads
Dockerfile                 Container image for the wrapped tool repo
requirements.txt           Existing customer tool dependencies
requirements-fastapi.txt   Added wrapper dependencies
```

## Tools Included

- `compute_integral`: computes a definite integral for a safe allow-list of math functions.
- `extract_text_insights`: returns word count, sentence count, and top keywords.
- `score_customer_priority`: scores a customer signal and recommends the next action.

## How To Adapt This To A Customer Repo

For a real customer repository, keep their existing tool files and `requirements.txt` in place. Add the wrapper files from this template:

- `app/`
- `requirements-fastapi.txt`
- `Dockerfile`
- `.dockerignore`

Then update `app/main.py` to import the customer's tool functions and expose one route per tool operation. Update `app/models.py` with the request and response schemas that should appear in the generated OpenAPI contract.

## Run Locally

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-fastapi.txt
export TOOL_API_KEY="replace-with-demo-key"
fastapi dev app/main.py
```

Set `TOOLS_SERVER_URL` to the URL where the service is reachable before trying the sample requests.

```sh
export TOOLS_SERVER_URL="<your server URL>"
curl -s "$TOOLS_SERVER_URL/health"
```

## Run With Docker

```sh
docker build -t openapi-python-tools-server .
docker run --rm -p 8000:8000 -e TOOL_API_KEY="replace-with-demo-key" openapi-python-tools-server
```

## Example Request

```sh
curl -s -X POST "$TOOLS_SERVER_URL/tools/math/integral" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $TOOL_API_KEY" \
  -d '{
    "function_name": "sin",
    "lower_bound": 0,
    "upper_bound": 3.14159,
    "intervals": 1000
  }'
```

## OpenAPI Contract

FastAPI serves the generated OpenAPI contract at:

```text
$TOOLS_SERVER_URL/openapi.json
```

Interactive documentation is available at:

```text
$TOOLS_SERVER_URL/docs
```

`openapi/tool-bindings.json` shows how each route can be represented as an OpenAPI tool binding with a placeholder server URL. Replace `https://customer-tools.example.com` with the deployed server URL before importing the bindings.

## Security

If `TOOL_API_KEY` is set, all tool routes require the `X-API-Key` header. If `TOOL_API_KEY` is not set, the routes remain open for quick demos.

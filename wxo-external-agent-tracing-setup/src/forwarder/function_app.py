"""
forwarder/function_app.py
=========================
Azure Function App (Python v2 Model) for WXO OTLP Trace Forwarder.

Endpoints:
  - POST /api/v1/traces
  - POST /api/v1/traces/{agent_id}
  - POST /api/traces
  - POST /api/traces/{agent_id}
  - GET  /api/health
"""

import json
import logging
import os
import sys

_curr_dir = os.path.dirname(os.path.abspath(__file__))
_repo_root = os.path.dirname(_curr_dir)
for p in (_curr_dir, _repo_root):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    import azure.functions as func
except ImportError:
    func = None

try:
    from forwarder.forwarder import OtlpForwarder
except ImportError:
    from forwarder import OtlpForwarder

logger = logging.getLogger("azure_otlp_forwarder")
forwarder = OtlpForwarder()

if func is not None:
    app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

    @app.route(route="health", methods=["GET"])
    def health_check(req: func.HttpRequest) -> func.HttpResponse:
        return func.HttpResponse(
            json.dumps({"status": "healthy", "service": "wxo-otlp-forwarder"}),
            status_code=200,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"},
        )

    # One trigger per function: azure-functions rejects stacked @app.route decorators.
    @app.route(route="v1/traces/{agent_id?}", methods=["POST", "OPTIONS"])
    def handle_v1_traces(req: func.HttpRequest) -> func.HttpResponse:
        return handle_traces(req)

    @app.route(route="traces/{agent_id?}", methods=["POST", "OPTIONS"])
    def handle_traces_short(req: func.HttpRequest) -> func.HttpResponse:
        return handle_traces(req)

    def handle_traces(req: func.HttpRequest) -> func.HttpResponse:
        if req.method == "OPTIONS":
            return func.HttpResponse(
                status_code=204,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
                    "Access-Control-Allow-Headers": "*",
                },
            )

        headers = {k.lower(): v for k, v in req.headers.items()}
        content_type = headers.get("content-type", "application/json")
        content_encoding = headers.get("content-encoding", "")

        path_agent_id = req.route_params.get("agent_id", "")
        query_params = dict(req.params)

        body_bytes = req.get_body()

        # refresh settings/map -> auth -> process (shared by every platform adapter)
        status, body = forwarder.handle(
            body_bytes=body_bytes,
            content_type=content_type,
            content_encoding=content_encoding,
            headers=headers,
            query_params=query_params,
            path_agent_id=path_agent_id,
        )
        return func.HttpResponse(
            json.dumps(body),
            status_code=status,
            mimetype="application/json",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
            },
        )

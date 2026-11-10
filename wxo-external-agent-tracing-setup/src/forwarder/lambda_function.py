"""
forwarder/lambda_function.py
============================
AWS Lambda handler for the WXO OTLP Trace Forwarder.

Compatible with:
  - AWS API Gateway (HTTP API payload format v1.0 and v2.0)
  - AWS API Gateway (REST API)
  - AWS Lambda Function URLs
  - Direct Lambda invocation

Environment Variables:
  - WXO_DEPLOYMENT_MODE: cloud (default) | cpd
  cloud mode:
  - API_KEY: WXO IAM API Key (or WXO_API_KEY)
  - TOKEN_URL: WXO IAM Token URL
  - WXO_TENANT_ID: Default WXO Tenant ID
  - WXO_OTEL_EXPORT_URL: Default WXO Trace Ingest URL
  cpd mode (export URL is derived from these):
  - CPD_HOST_URL, CPD_USERNAME, CPD_PASSWORD, CPD_INSTANCE_ID, CPD_NAMESPACE
  - CPD_VERIFY_TLS: "true" to verify the CPD certificate (default: skipped)
  both:
  - ENVIRONMENT_NAME: draft | live
  - WXO_AGENT_MAP: JSON mapping of platform agent IDs to WXO agents

Invocation:
  # Direct Lambda invoke (returns trace IDs in response body):
  aws lambda invoke \\
    --function-name wxo-otlp-forwarder \\
    --payload file://test_event.json \\
    --cli-binary-format raw-in-base64-out \\
    response.json && cat response.json

  # Or via Function URL / API Gateway:
  curl -X POST https://<lambda-url>/v1/traces \\
    -H 'Content-Type: application/json' \\
    -d @test_event.json
"""

from __future__ import annotations

import base64
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
    from forwarder.forwarder import OtlpForwarder
except ImportError:
    from forwarder import OtlpForwarder

logger = logging.getLogger()
logger.setLevel(logging.INFO)

forwarder = OtlpForwarder()


def lambda_handler(event: dict, context) -> dict:
    """AWS Lambda entrypoint."""
    logger.info("Received invocation event")

    # ── Health checks / warmup pings ─────────────────────────────────────────
    path = event.get("rawPath") or event.get("path") or ""
    if path in ("/health", "/healthz"):
        return _response(200, {"status": "healthy", "service": "wxo-otlp-forwarder"})

    # ── OPTIONS pre-flight ────────────────────────────────────────────────────
    if (event.get("requestContext", {}).get("http", {}).get("method") or
            event.get("httpMethod", "")) == "OPTIONS":
        return _response(200, {})

    # ── Extract headers (case-insensitive) ────────────────────────────────────
    raw_headers = event.get("headers", {}) or {}
    headers = {k.lower(): v for k, v in raw_headers.items()}

    content_type = headers.get("content-type", "application/json")
    content_encoding = headers.get("content-encoding", "")

    # ── Extract body bytes (handling Base64 from API Gateway) ─────────────────
    raw_body = event.get("body", "")
    is_b64 = event.get("isBase64Encoded", False)

    if isinstance(raw_body, bytes):
        body_bytes = raw_body
    elif is_b64 and isinstance(raw_body, str):
        try:
            body_bytes = base64.b64decode(raw_body)
        except Exception as exc:
            logger.error(f"Failed to decode base64 body: {exc}")
            return _response(400, {"error": "Invalid base64 encoding"})
    elif isinstance(raw_body, str):
        body_bytes = raw_body.encode("utf-8")
    elif isinstance(raw_body, dict):
        # Direct Lambda invoke with the OTLP payload passed as a plain dict
        # under the "body" key — serialise it back to JSON bytes.
        body_bytes = json.dumps(raw_body).encode("utf-8")
    elif not raw_body:
        # Direct Lambda invoke: the entire event IS the OTLP payload when it
        # contains resourceSpans / resource_attrs (no API-Gateway envelope).
        if "resourceSpans" in event or "resource_attrs" in event or "scope_spans" in event:
            body_bytes = json.dumps(event).encode("utf-8")
            content_type = "application/json"
        else:
            body_bytes = b""
    else:
        body_bytes = b""

    # ── Extract path-encoded agent_id ─────────────────────────────────────────
    path_parameters = event.get("pathParameters") or {}
    path_agent_id = path_parameters.get("agent_id") or path_parameters.get("proxy", "")
    if not path_agent_id:
        parts = [p for p in path.split("/") if p and p not in ("v1", "traces", "ingest")]
        if parts:
            path_agent_id = parts[0]

    # ── Extract query parameters ──────────────────────────────────────────────
    query_params = event.get("queryStringParameters") or {}

    # ── refresh settings/map -> auth -> process ───────────────────────────────
    status, body = forwarder.handle(
        body_bytes=body_bytes,
        content_type=content_type,
        content_encoding=content_encoding,
        headers=headers,
        query_params=query_params,
        path_agent_id=path_agent_id,
    )

    # ── Enrich successful responses with trace IDs ────────────────────────────
    # job_ids returned by WXO are Langfuse trace IDs.  Surfacing them as
    # trace_ids in the response lets you navigate directly to the new trace
    # in the WXO UI without any additional lookup step.
    if status == 200 and body.get("job_ids"):
        trace_ids = [jid for jid in body["job_ids"] if jid]
        if trace_ids:
            body["trace_ids"] = trace_ids
            logger.info("Forwarded trace IDs: %s", trace_ids)

    return _response(status, body)


def _response(status_code: int, body_dict: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
        },
        "body": json.dumps(body_dict),
    }

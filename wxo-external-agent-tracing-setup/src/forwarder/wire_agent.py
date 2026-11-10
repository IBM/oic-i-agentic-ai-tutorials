#!/usr/bin/env python3
"""
forwarder/wire_agent.py
=======================
Main CLI entrypoint and standalone HTTP daemon for the OTLP Forwarder.

Usage:
    python3 src/forwarder/wire_agent.py               # run OTLP receiver daemon (port 4318)
    python3 src/forwarder/wire_agent.py --test        # send synthetic test trace to WXO
    python3 src/forwarder/wire_agent.py --dry-run     # validate credentials & agent map
    python3 src/forwarder/wire_agent.py --port 8080   # run on custom port
"""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import logging
import os
import re
from socketserver import ThreadingMixIn
import sys
import threading
import time
import urllib.parse

# Ensure repo root is on sys.path
_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from forwarder.forwarder import (
    OtlpForwarder, auth_configured, build_otlp_payload, cpd_export_url,
    deployment_mode, get_bearer_token, post_to_wxo,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("wxo_otlp_forwarder")


# ---------------------------------------------------------------------------
# Config Loader
# ---------------------------------------------------------------------------
def _load_env_file(path: str, section: str = None) -> None:
    """Load key-value pairs from .env or section-based config file if not already set in environment."""
    if not os.path.exists(path):
        return
    try:
        sys.path.insert(0, os.path.join(_repo_root, "lib"))
        from parse_env_section import parse_config

        data = parse_config(path, section)
        for var, val in data.items():
            if var not in os.environ:
                os.environ[var] = val
    except Exception as exc:
        log.debug(f"Failed to read env file {path}: {exc}")


# Auto-load config files if running directly
_repo_base = os.path.dirname(_repo_root)
_cfg_dir = os.path.join(_repo_base, "config")
if os.path.exists(os.path.join(_repo_base, "config.env")):
    _load_env_file(os.path.join(_repo_base, "config.env"), "claude")
elif os.path.exists(os.path.join(_cfg_dir, "config.env")):
    _load_env_file(os.path.join(_cfg_dir, "config.env"), "claude")
elif os.path.exists(os.path.join(_repo_base, ".env")):
    _load_env_file(os.path.join(_repo_base, ".env"), "claude")
else:
    _load_env_file(os.path.join(_cfg_dir, "shared.env"))
    _load_env_file(os.path.join(_cfg_dir, "claude.env"))


def _cfg(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


OTLP_RECEIVER_PORT = int(_cfg("OTLP_PORT") or _cfg("PORT") or _cfg("OTLP_RECEIVER_PORT") or 4318)
WXO_MODE           = deployment_mode()   # cloud | cpd (WXO_DEPLOYMENT_MODE)
WXO_OTEL_EXPORT_URL= cpd_export_url() if WXO_MODE == "cpd" else _cfg("WXO_OTEL_EXPORT_URL")
WXO_TENANT_ID      = "" if WXO_MODE == "cpd" else (extract_tenant_id(WXO_OTEL_EXPORT_URL) or _cfg("WXO_TENANT_ID"))
WXO_ENVIRONMENT    = _cfg("ENVIRONMENT_NAME", "draft")
WXO_API_KEY        = _cfg("API_KEY") or _cfg("WXO_API_KEY")
WXO_TOKEN_URL      = _cfg("TOKEN_URL", "https://account-iam.platform.saas.ibm.com/api/2.0/apikeys/token")


# ---------------------------------------------------------------------------
# Validation & Test Runners
# ---------------------------------------------------------------------------
def validate_config(dry_run: bool = False) -> bool:
    """Validate mandatory environment variables and agent map."""
    errors: list[str] = []
    if WXO_MODE == "cpd":
        for var in ("CPD_HOST_URL", "CPD_USERNAME", "CPD_PASSWORD", "CPD_INSTANCE_ID", "CPD_NAMESPACE"):
            if not _cfg(var):
                errors.append(f"  ✗  {var} not set in config.env [claude] (WXO_DEPLOYMENT_MODE=cpd)")
    else:
        if not WXO_API_KEY:
            errors.append("  ✗  API_KEY not set in config/shared.env or config/claude.env")
        if not WXO_TOKEN_URL:
            errors.append("  ✗  TOKEN_URL not set in config/shared.env")
        if not WXO_OTEL_EXPORT_URL and not os.environ.get("WXO_AGENT_MAP"):
            errors.append("  ✗  WXO_OTEL_EXPORT_URL not set in config/claude.env")
        if not WXO_TENANT_ID and not os.environ.get("WXO_AGENT_MAP"):
            errors.append("  ✗  Tenant ID could not be extracted from WXO_OTEL_EXPORT_URL "
                          "(expected '.../instances/<id>/...'); fix the URL or set WXO_TENANT_ID explicitly")

    agent_map = OtlpForwarder.parse_agent_map()

    if errors:
        for err in errors:
            print(err)
        return False

    print("  ✓  Configuration validated successfully.")
    print(f"     Deployment Mode    : {WXO_MODE}")
    if WXO_MODE == "cloud":
        print(f"     Default Tenant ID  : {WXO_TENANT_ID or '(configured per-agent in WXO_AGENT_MAP)'}")
    print(f"     Default Export URL : {WXO_OTEL_EXPORT_URL or '(configured per-agent in WXO_AGENT_MAP)'}")
    print(f"     Environment        : {WXO_ENVIRONMENT}")
    print(f"     Mapped Agents ({len(agent_map)}):")
    if agent_map:
        for k, v in agent_map.items():
            aid = v.get("wxo_agent_id", "")
            dname = v.get("wxo_display_name", k)
            print(f"       • '{k}' → agent_id: {aid} (display: {dname})")
    else:
        print("       (No explicit WXO_AGENT_MAP entries; will use global defaults and direct UUIDs)")

    if dry_run:
        print(f"\n  [dry-run] Fetching {'CPD' if WXO_MODE == 'cpd' else 'IBM Cloud IAM'} token to verify credentials...")
        token = get_bearer_token(WXO_API_KEY, WXO_TOKEN_URL, logger=log)
        if token:
            print(f"  ✓  IAM Bearer token obtained successfully (length={len(token)})")
        else:
            print("  ✗  Failed to obtain IAM Bearer token. Please check API_KEY and TOKEN_URL.")
            return False

    return True


def run_test() -> None:
    """Send a synthetic OTLP test trace to WXO to verify end-to-end connectivity."""
    print("\n── WXO OTLP Forwarder Test Trace ──────────────────────────────")
    forwarder = OtlpForwarder()
    routing = forwarder.resolve_wxo_agent(["test_agent", "default"], default_name="test_agent")

    agent_id = routing["agent_id"]
    tenant_id = routing["tenant_id"]
    export_url = routing["export_url"]
    api_key = routing["api_key"]
    token_url = routing["token_url"]

    if not agent_id or not export_url or not auth_configured(api_key):
        print("  ✗ Cannot send test trace: missing WXO_AGENT_ID, export URL, or credentials "
              f"(mode={WXO_MODE}).")
        sys.exit(1)

    print(f"  Target Agent ID   : {agent_id}")
    print(f"  Target Tenant ID  : {tenant_id}")
    print(f"  Target Export URL : {export_url}")
    print("  Obtaining IAM Bearer token...")

    token = get_bearer_token(api_key, token_url, logger=log)
    if not token:
        print("  ✗ Failed to obtain IAM Bearer token. Test aborted.")
        sys.exit(1)
    print("  ✓ IAM Bearer token obtained.")

    now_ns = int(time.time() * 1e9)
    test_payload = build_otlp_payload(
        agent_id=agent_id,
        agent_name=routing["agent_name"],
        tenant_id=tenant_id,
        environment=routing["environment"],
        prompt="Hello from WXO OTLP Forwarder verification suite!",
        response="Forwarder is operational and successfully transforming and shipping traces to WXO Agent Analytics.",
        start_ns=now_ns - 1_200_000_000,
        end_ns=now_ns,
        input_tokens=14,
        output_tokens=18,
        platform="otlp_forwarder",
        model_name="otlp-test-v1",
        tool_calls=[{
            "name": "verify_connectivity",
            "input": "ping",
            "output": "pong",
            "start_ns": now_ns - 800_000_000,
            "end_ns": now_ns - 200_000_000,
            "is_error": False,
        }],
    )

    print("  Posting synthetic trace to WXO...")
    job_id = post_to_wxo(
        payload=test_payload,
        bearer_token=token,
        export_url=export_url,
        agent_id=agent_id,
        tenant_id=tenant_id,
        logger=log,
    )

    if job_id:
        print(f"\n  ✓ Test trace accepted by WXO! Job ID: {job_id}")
        print("  Check WXO Agent Analytics dashboard to view trace.")
    else:
        print("\n  ✗ Failed to post test trace to WXO.")
        sys.exit(1)


# ---------------------------------------------------------------------------
# HTTP Server & Request Handler
# ---------------------------------------------------------------------------
class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class OtlpForwarderHandler(BaseHTTPRequestHandler):
    forwarder: OtlpForwarder = OtlpForwarder()

    def log_message(self, format, *args):
        log.info(f"{self.client_address[0]} - {format % args}")

    def _send_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors()
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/health", "/healthz", "/livez"):
            self.send_response(200)
            self._send_cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "healthy", "service": "wxo-otlp-forwarder"}\n')
            return

        if parsed.path in ("/mappings", "/api/mappings", "/admin/mappings"):
            current_map = self.forwarder.get_agent_map(force_refresh=True)
            self.send_response(200)
            self._send_cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(current_map, indent=2).encode("utf-8") + b"\n")
            return

        self.send_response(200)
        self._send_cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        resp_data = {
            "service": "wxo-otlp-forwarder",
            "status": "ready",
            "endpoints": [
                "POST /v1/traces",
                "POST /v1/traces/{agent_id}",
                "POST /traces",
                "POST /traces/{agent_id}",
                "GET /mappings",
                "POST /mappings",
                "GET /health",
            ],
            "mapped_agents_count": len(self.forwarder.get_agent_map()),
        }
        self.wfile.write(json.dumps(resp_data, indent=2).encode("utf-8") + b"\n")

    def _reject_unauthorized(self) -> bool:
        """Refresh settings/map and check the caller's token. Sends 401 and returns True if rejected."""
        if self.forwarder.check_request(dict(self.headers)):
            return False
        self.send_response(401)
        self._send_cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"error": "Unauthorized"}\n')
        return True

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length) if content_length > 0 else b""

        # Same gate as Lambda/Azure: refresh config, then require the token if one is set.
        if self._reject_unauthorized():
            return

        # Dynamic mapping update endpoint: POST /mappings
        if parsed.path in ("/mappings", "/api/mappings", "/admin/mappings"):
            try:
                new_mappings = json.loads(body_bytes.decode("utf-8"))
                for k, v in new_mappings.items():
                    self.forwarder.set_agent_mapping(k, v)
                self.send_response(200)
                self._send_cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "updated", "mappings": self.forwarder.get_agent_map()}).encode("utf-8") + b"\n")
            except Exception as exc:
                self.send_response(400)
                self._send_cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"Invalid JSON payload: {exc}"}).encode("utf-8") + b"\n")
            return

        content_type = self.headers.get("Content-Type", "application/json")
        content_encoding = self.headers.get("Content-Encoding", "")

        # Extract path-based agent ID: /v1/traces/<agent_id> or /traces/<agent_id>
        path_agent_id = ""
        parts = [p for p in parsed.path.split("/") if p and p not in ("v1", "traces", "ingest")]
        if parts:
            path_agent_id = parts[0]

        qs = urllib.parse.parse_qs(parsed.query)

        # Immediate 200 OK acknowledgment to prevent OTel exporter timeouts
        self.send_response(200)
        self._send_cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status": "ok"}\n')

        # Asynchronously process and forward trace payload to WXO
        headers_dict = dict(self.headers)
        threading.Thread(
            target=self._process_async,
            args=(body_bytes, content_type, content_encoding, headers_dict, qs, path_agent_id),
            daemon=True,
        ).start()

    def _process_async(self, body_bytes, content_type, content_encoding, headers, query_params, path_agent_id):
        try:
            self.forwarder.process_payload(
                body_bytes=body_bytes,
                content_type=content_type,
                content_encoding=content_encoding,
                headers=headers,
                query_params=query_params,
                path_agent_id=path_agent_id,
            )
        except Exception as exc:
            log.error(f"Error processing trace payload: {exc}", exc_info=True)


def run_server(port: int = OTLP_RECEIVER_PORT) -> None:
    """Start standalone multithreaded OTLP trace receiver server."""
    OtlpForwarderHandler.forwarder = OtlpForwarder()
    server = ThreadedHTTPServer(("0.0.0.0", port), OtlpForwarderHandler)
    log.info(f"╔══════════════════════════════════════════════════════════════════╗")
    log.info(f"║        WXO OTLP Forwarder Server Started                       ║")
    log.info(f"╚══════════════════════════════════════════════════════════════════╝")
    log.info(f"  Listening on        : http://0.0.0.0:{port}")
    log.info(f"  OTLP Ingest Path    : http://0.0.0.0:{port}/v1/traces")
    log.info(f"  Health Endpoint     : http://0.0.0.0:{port}/health")
    log.info(f"  Mapped agents       : {len(OtlpForwarderHandler.forwarder.agent_map)}")
    log.info("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Stopping OTLP Forwarder server...")
        server.shutdown()


def main():
    parser = argparse.ArgumentParser(description="WXO OTLP Trace Forwarder")
    parser.add_argument("--receiver", "--server", action="store_true", help="Start OTLP trace receiver daemon (default)")
    parser.add_argument("--port", type=int, default=OTLP_RECEIVER_PORT, help="Port to listen on (default: 4318)")
    parser.add_argument("--test", action="store_true", help="Send synthetic test trace to WXO")
    parser.add_argument("--dry-run", action="store_true", help="Validate configuration without starting server")
    args = parser.parse_args()

    if args.dry_run:
        ok = validate_config(dry_run=True)
        sys.exit(0 if ok else 1)

    if args.test:
        validate_config(dry_run=False)
        run_test()
        sys.exit(0)

    validate_config(dry_run=False)
    run_server(port=args.port)


if __name__ == "__main__":
    main()

"""
sitecustomize.py  —  WXO shared agent trace hook
=================================================
Single file shared by all three platforms:
  • AWS AgentCore Runtime   (injected into ECR image via aws/agent-patch/)
  • Vertex AI Self-hosted   (injected into Cloud Run / GKE via container_hook/)
  • Azure AI Foundry Hosted (bundled with agent source version via azure/)

Python imports sitecustomize automatically at startup — BEFORE any user code —
so this file patches the agent's HTTP / RPC handler with zero changes to
server.py or agent.py.

Supported frameworks
--------------------
  • http.server     (stdlib BaseHTTPRequestHandler)
  • Starlette / FastAPI  (ASGI, via BaseHTTPMiddleware + Router.__call__ for Azure SSE)
  • Flask           (WSGI, via wsgi_app wrapper)
  • Django          (WSGI, via WSGIHandler.__call__ patch)
  • Generic WSGI    (Falcon, Bottle, Pyramid, wsgiref, …)
  • Tornado         (async, via Application.__call__ wrap)
  • aiohttp         (async, via Application middleware injection)
  • gRPC            (unary-unary, server-streaming, client-streaming, bidi-streaming)

Platform detection (auto, overridable with WXO_PLATFORM env var)
-----------------
  "azure_ai_foundry"  — WXO_PLATFORM=azure_ai_foundry or WXO_ENVIRONMENT set
                        Activates OpenAI Responses-API prompt/response extractors
                        and SSE streaming parser (response.completed events).
  "aws_agentcore"     — WXO_HOOK_URL is set (API GW fallback)
  "cloud_agent"       — everything else (Vertex, generic containers)

Deployment mode (WXO_DEPLOYMENT_MODE, default "cloud")
-------------------------------------------------------
  cloud  IBM Cloud SaaS — API key → IBM IAM token (WXO_API_KEY + WXO_TOKEN_URL),
         export URL = WXO_OTEL_EXPORT_URL, x-ibm-tenant-id header sent.
  cpd    Cloud Pak for Data — username/password → POST <CPD_HOST_URL>/icp4d-api/v1/authorize
         (token cached 12 h), export URL built from CPD_HOST_URL + CPD_NAMESPACE +
         CPD_INSTANCE_ID (or WXO_OTEL_EXPORT_URL if set), no tenant header,
         TLS verification skipped unless CPD_VERIFY_TLS=true (self-signed certs).

Multi-tenant support (cloud_agent / aws_agentcore)
---------------------------------------------------
Per-request tenant context resolved from headers > body metadata > env vars.
Bearer-token and OTel TracerProvider caches are keyed per (api_key, token_url).

OTel child-span capture
-----------------------
When opentelemetry-sdk is installed, the hook creates a per-tenant
TracerProvider backed by an in-memory exporter, starts a root span, and
propagates its context so LangChain / LlamaIndex / httpx child spans attach
automatically.  Falls back to a single synthetic span when SDK is absent.

Config (all env vars, no hardcoded values)
------------------------------------------
  WXO_DEPLOYMENT_MODE    cloud (default) | cpd
  WXO_AGENT_ID           UUID from WXO console
  WXO_AGENT_NAME         snake_case display name
  -- cloud mode --
  WXO_TENANT_ID          WXO tenant id
  WXO_API_KEY            IBM API key
  WXO_TOKEN_URL          IAM token endpoint
  WXO_OTEL_EXPORT_URL    WXO OTLP ingestion URL
  -- cpd mode --
  CPD_HOST_URL           CPD base URL (https://cpd-<ns>.apps.<cluster>)
  CPD_USERNAME / CPD_PASSWORD
  CPD_INSTANCE_ID        WXO instance id  (builds the trace ingest URL)
  CPD_NAMESPACE          namespace CPD is deployed in (builds the trace ingest URL)
  CPD_VERIFY_TLS         "true" to verify CPD TLS certs (default: skipped)
  WXO_ENVIRONMENT_NAME   draft | live  (also accepted: WXO_ENVIRONMENT)
  WXO_PLATFORM           azure_ai_foundry | aws_agentcore | cloud_agent (auto)
  WXO_HOOK_URL           AWS API GW fallback (optional, aws_agentcore only)
  OTEL_DISABLE_CONSOLE   set to "true" to silence [wxo_hook] log lines
"""

from __future__ import annotations

import io
import json
import logging
import os
import sys
import threading
import time
import uuid

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

_LOG = logging.getLogger("wxo_hook")
if not _LOG.handlers:
    _h = logging.StreamHandler(sys.stderr)
    _h.setFormatter(logging.Formatter("[wxo_hook] %(message)s"))
    _LOG.addHandler(_h)
_LOG.setLevel(
    logging.CRITICAL if os.environ.get("OTEL_DISABLE_CONSOLE", "").lower() == "true"
    else logging.INFO
)

# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------

def _detect_platform() -> str:
    explicit = os.environ.get("WXO_PLATFORM", "").strip().lower()
    if explicit:
        return explicit
    if os.environ.get("WXO_HOOK_URL"):
        return "aws_agentcore"
    # Azure Foundry sets WXO_ENVIRONMENT (not WXO_ENVIRONMENT_NAME)
    if "WXO_ENVIRONMENT" in os.environ and "WXO_ENVIRONMENT_NAME" not in os.environ:
        return "azure_ai_foundry"
    return "cloud_agent"

_PLATFORM = _detect_platform()

# ---------------------------------------------------------------------------
# Config — canonical WXO_* prefix, with bare-name and platform fallbacks
# ---------------------------------------------------------------------------

_DEPLOYMENT_MODE = "cpd" if os.environ.get("WXO_DEPLOYMENT_MODE", "cloud").strip().lower() == "cpd" else "cloud"

_AGENT_ID    = os.environ.get("WXO_AGENT_ID",          "")
_AGENT_NAME  = os.environ.get("WXO_AGENT_NAME",         "agent" if _PLATFORM != "azure_ai_foundry" else "azure_foundry_agent")
_API_KEY     = (os.environ.get("WXO_API_KEY")            or os.environ.get("API_KEY",            ""))
_TOKEN_URL   = (os.environ.get("WXO_TOKEN_URL")          or os.environ.get("TOKEN_URL",          ""))
_EXPORT_URL  = (os.environ.get("WXO_OTEL_EXPORT_URL")   or os.environ.get("OTEL_EXPORT_URL",    ""))

# CPD (on-prem) credentials — only used when WXO_DEPLOYMENT_MODE=cpd
_CPD_HOST    = os.environ.get("CPD_HOST_URL",    "")
_CPD_USER    = os.environ.get("CPD_USERNAME",    "")
_CPD_PASS    = os.environ.get("CPD_PASSWORD",    "")
_CPD_INST    = os.environ.get("CPD_INSTANCE_ID", "")
_CPD_NS      = os.environ.get("CPD_NAMESPACE",   "")
_CPD_VERIFY  = os.environ.get("CPD_VERIFY_TLS", "false").strip().lower() in ("1", "true", "yes")
if _DEPLOYMENT_MODE == "cpd" and not _EXPORT_URL and _CPD_HOST and _CPD_NS and _CPD_INST:
    _EXPORT_URL = f"{_CPD_HOST.rstrip('/')}/{_CPD_NS}/instances/{_CPD_INST}/v1/agentops-v3/traces"

def _extract_tenant_id(url: str) -> str:
    if url:
        m = re.search(r'/instances/([^/?#]+)', url)
        if m:
            return m.group(1).strip()
    return ""

_TENANT_ID   = _extract_tenant_id(_EXPORT_URL) or (os.environ.get("WXO_TENANT_ID") or os.environ.get("TENANT_ID", "")).strip()
_ENVIRONMENT = (os.environ.get("WXO_ENVIRONMENT_NAME")
                or os.environ.get("WXO_ENVIRONMENT")
                or os.environ.get("ENVIRONMENT_NAME",   "draft"))
_HOOK_URL    = os.environ.get("WXO_HOOK_URL",            "")   # AWS API GW fallback

_ACTIVE = bool(_EXPORT_URL or _HOOK_URL)
if not _ACTIVE:
    _LOG.warning(
        "Trace export URL not set — tracing disabled. "
        + ("Set CPD_HOST_URL + CPD_NAMESPACE + CPD_INSTANCE_ID (or WXO_OTEL_EXPORT_URL)"
           if _DEPLOYMENT_MODE == "cpd" else "Set WXO_OTEL_EXPORT_URL")
    )

# ---------------------------------------------------------------------------
# Shared helpers — delegate to shared/wxo_span.py when on dev path, else inline
# ---------------------------------------------------------------------------

_wxo_span = None
try:
    _repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _repo_root not in sys.path:
        sys.path.insert(0, _repo_root)
    import shared.wxo_span as _wxo_span  # type: ignore[import]
except Exception:
    pass

# ---------------------------------------------------------------------------
# Recursion / dedup guards
# ---------------------------------------------------------------------------

_IN_TRACE_POST    = threading.local()  # set while POSTing the trace itself
_IN_REQUEST_TRACE = threading.local()  # set while any layer is already tracing

# ---------------------------------------------------------------------------
# Process-wide in-flight request dedup — prevents any two patches from both
# emitting a trace for the same request, regardless of framework or platform.
#
# Key: sha256(request_body)[:16]  — stable across sync/async/thread boundaries.
# A key is inserted when a patch claims a request and removed when it finishes.
# Any second patch that computes the same key finds it occupied and skips.
# TTL of 60 s guards against leaks if a response never arrives.
# ---------------------------------------------------------------------------
import hashlib as _hashlib

_INFLIGHT: dict[str, float] = {}   # key → claim_time (monotonic seconds)
_INFLIGHT_TTL   = 60.0             # seconds before a stale claim is expired
_INFLIGHT_LOCK  = threading.Lock()


def _inflight_claim(body_bytes: bytes) -> str | None:
    """Try to claim this request body for tracing.

    Returns the claim key if successful (caller owns this request),
    or None if another patch already claimed it.
    Expired claims (> TTL) are evicted before checking.
    """
    if not body_bytes:
        return None
    key = _hashlib.sha256(body_bytes).hexdigest()[:16]
    now = time.monotonic()
    with _INFLIGHT_LOCK:
        # Evict stale claims
        stale = [k for k, t in _INFLIGHT.items() if now - t > _INFLIGHT_TTL]
        for k in stale:
            _INFLIGHT.pop(k, None)
        if key in _INFLIGHT:
            return None          # already claimed by another layer
        _INFLIGHT[key] = now
        return key


def _inflight_release(key: str | None) -> None:
    """Release a previously claimed request key."""
    if key:
        with _INFLIGHT_LOCK:
            _INFLIGHT.pop(key, None)

# ---------------------------------------------------------------------------
# Hosted-agent conversation continuity — response_id → session_id map
# ---------------------------------------------------------------------------
# Azure Foundry kind:hosted agents use the Responses API with store=False.
# Each response carries a unique `id` (resp_xxx).  The caller chains turns by
# sending `previous_response_id` in the next request.  We use this chain to
# group multiple turns into one WXO session.
#
# Map: response_id → session_id (populated after each successful response)
# On the next turn the incoming `previous_response_id` is looked up here to
# inherit the same session_id, preserving conversation history in WXO.
_RESPONSE_SESSION_MAP: dict[str, str] = {}
_RESPONSE_SESSION_MAX = 5000   # cap — drop oldest when full

# Set to True (process-wide) when _patch_grpc() successfully injects the
# WxoInterceptor.  Used by _make_do_post_wrapper so that HTTP-bridge do_POST
# handlers in a gRPC process defer tracing to the interceptor layer, which
# runs on a *different* thread and therefore cannot share a threading.local.
_GRPC_INTERCEPTOR_ACTIVE: bool = False

# ---------------------------------------------------------------------------
# Response-chain session resolution (kind:hosted conversation continuity)
# ---------------------------------------------------------------------------
# Session ID priority for Azure kind:hosted agents:
#   1. agent_session_id from the SSE stream  (stable, set by Azure, survives
#      across container instances — always use this when present)
#   2. Explicit header  x-ibm-conversation-id  (caller-supplied override)
#   3. In-process previous_response_id → session_id map  (same-instance chain)
#   4. Fresh UUID  (first turn, no context available)
#
# agent_session_id is emitted in the very first SSE event (response.created)
# so it is available before response.completed.  We update ctx["session_id"]
# as soon as we see it in the stream, which means subsequent turns in the same
# Azure session always share the same WXO session ID regardless of which
# container instance handles them.

def _resolve_hosted_session(body_parsed: dict, ctx: dict) -> str:
    """Return a stable session_id for this turn.

    Priority:
      1. Explicit header x-ibm-conversation-id (already in ctx["session_id"])
      2. Azure conversation ID from request body — "conversation" field is a
         stable, per-conversation identifier that Azure sends on every turn
         (both turn 1 and turn 2+).  It can be a plain string or a dict with
         an "id" key: {"id": "conv_..."}.
      3. Fresh random UUID (fallback — should not be needed in practice)

    Azure's agent_session_id / previous_response_id are NOT used:
      - agent_session_id is container-scoped (shared across all conversations
        in one container instance) and causes cross-thread ID bleed.
      - previous_response_id is never sent by Azure in the request body.
    """
    # Honour explicitly passed session (e.g. from x-ibm-conversation-id header)
    if ctx.get("session_id"):
        return ctx["session_id"]
    # Azure sends conversation field on every turn — use it as the stable ID.
    conv = body_parsed.get("conversation", "")
    if isinstance(conv, dict):
        conv = conv.get("id", "") or ""
    if conv and isinstance(conv, str):
        return conv.strip()
    # Fallback: fresh UUID
    return uuid.uuid4().hex


def _update_session_from_sse(evt: dict, ctx: dict) -> None:
    """No-op: kept for call-site compatibility.

    Azure's agent_session_id (conv_01...) is shared across unrelated
    conversations in the same Azure agent session, so using it as the WXO
    conversation ID causes duplicate traces and cross-thread ID bleed.
    Session identity is now determined solely by the x-ibm-conversation-id
    header or a per-request UUID from _resolve_hosted_session.
    """


def _register_response_session(response_id: str, session_id: str) -> None:
    """Store response_id → session_id so the next turn can inherit it."""
    if not response_id or not session_id:
        return
    if len(_RESPONSE_SESSION_MAP) >= _RESPONSE_SESSION_MAX:
        # Drop the oldest 10 % to keep memory bounded
        drop = list(_RESPONSE_SESSION_MAP.keys())[:max(1, _RESPONSE_SESSION_MAX // 10)]
        for k in drop:
            _RESPONSE_SESSION_MAP.pop(k, None)
    _RESPONSE_SESSION_MAP[response_id] = session_id


# ---------------------------------------------------------------------------
# Token counting (stdlib approximation, no tiktoken dependency)
# ---------------------------------------------------------------------------

def _count_tokens(text: str) -> int:
    if _wxo_span:
        return _wxo_span.count_tokens(text)
    import re as _re
    _pat = _re.compile(r"(?i:'s|'t|'re|'ve|'m|'ll|'d)|[^\W\d_]+|\d{1,3}|[^\w\s]+", _re.UNICODE)
    return len(_pat.findall(text)) if text else 0

# ---------------------------------------------------------------------------
# Bearer token — thread-safe, TTL-aware.
#   cloud: keyed per (api_key, token_url) — IBM IAM
#   cpd:   keyed per (username, host)     — POST /icp4d-api/v1/authorize
# ---------------------------------------------------------------------------

def _ssl_ctx():
    """TLS context for WXO calls — CPD self-signed certs are accepted unless CPD_VERIFY_TLS=true."""
    import ssl as _ssl
    ctx = _ssl.create_default_context()
    if _DEPLOYMENT_MODE == "cpd" and not _CPD_VERIFY:
        ctx.check_hostname = False
        ctx.verify_mode    = _ssl.CERT_NONE
    return ctx


def _get_cpd_token() -> str:
    """CPD bearer token (12 h TTL, refreshed 5 min early), cached per (username, host)."""
    if not _CPD_USER or not _CPD_PASS or not _CPD_HOST:
        return ""
    _cache: dict = getattr(_get_cpd_token, "_cache", {})
    _lock         = getattr(_get_cpd_token, "_lock",  threading.Lock())
    _get_cpd_token._cache = _cache   # type: ignore[attr-defined]
    _get_cpd_token._lock  = _lock    # type: ignore[attr-defined]
    cache_key = (_CPD_USER, _CPD_HOST.rstrip("/"))
    now = time.time()
    with _lock:
        entry = _cache.get(cache_key, {})
        if entry.get("token") and now < entry.get("expires_at", 0):
            return entry["token"]
    from urllib.request import Request as _R, urlopen as _u
    req = _R(_CPD_HOST.rstrip("/") + "/icp4d-api/v1/authorize",
             data=json.dumps({"username": _CPD_USER, "password": _CPD_PASS}).encode(),
             headers={"Content-Type": "application/json", "Accept": "application/json",
                      "User-Agent": "curl/7.68.0"}, method="POST")
    try:
        with _u(req, timeout=30, context=_ssl_ctx()) as resp:
            body = json.loads(resp.read())
        token = body.get("token", "")
        if not token:
            _LOG.warning(f"No token in CPD /authorize response: {list(body.keys())}")
            return ""
        with _lock:
            _cache[cache_key] = {"token": token, "expires_at": now + 43200 - 300}
        _LOG.info("CPD bearer token refreshed")
        return token
    except Exception as exc:
        _LOG.warning(f"CPD token refresh failed: {exc}")
        return ""


def _get_bearer_token_for(api_key: str, token_url: str) -> str:
    """Bearer token for the active deployment mode (cloud: IAM api_key exchange; cpd: authorize)."""
    if _DEPLOYMENT_MODE == "cpd":
        return _get_cpd_token()
    if _wxo_span:
        try:
            return _wxo_span.get_bearer_token(api_key, token_url, logger=_LOG)
        except Exception as exc:
            _LOG.warning(f"Token refresh failed: {exc}")
            return ""
    import ssl as _ssl
    _cache: dict = getattr(_get_bearer_token_for, "_cache", {})
    _lock         = getattr(_get_bearer_token_for, "_lock",  threading.Lock())
    _get_bearer_token_for._cache = _cache   # type: ignore[attr-defined]
    _get_bearer_token_for._lock  = _lock    # type: ignore[attr-defined]
    if not api_key or not token_url:
        return ""
    cache_key = (api_key, token_url)
    now = time.time()
    with _lock:
        entry = _cache.get(cache_key, {})
        if entry.get("token") and now < entry.get("expires_at", 0):
            return entry["token"]
    from urllib.request import Request as _R, urlopen as _u
    from urllib.parse import urlencode as _ue
    if "/identity/token" in token_url:
        _data  = _ue({"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": api_key}).encode()
        _ctype = "application/x-www-form-urlencoded"
    else:
        _data  = json.dumps({"apikey": api_key}).encode()
        _ctype = "application/json"
    req = _R(token_url, data=_data,
             headers={"Content-Type": _ctype, "Accept": "application/json",
                      "User-Agent": "curl/7.68.0"}, method="POST")
    try:
        with _u(req, timeout=30, context=_ssl.create_default_context()) as resp:
            body = json.loads(resp.read())
        token   = body.get("token") or body.get("access_token") or body.get("iam_token", "")
        raw_ttl = int(body.get("expires_in", 3600) or 3600)
        ttl     = max(raw_ttl - 300, 60)
        with _lock:
            _cache[cache_key] = {"token": token, "expires_at": now + ttl}
        _LOG.info(f"Bearer token refreshed (ttl={raw_ttl}s)")
        return token
    except Exception as exc:
        _LOG.warning(f"Token refresh failed: {exc}")
        return ""

# ---------------------------------------------------------------------------
# A2A (Agent-to-Agent / JSON-RPC 2.0) helpers
# ---------------------------------------------------------------------------

def _is_a2a_request(body: dict) -> bool:
    """Return True when body is a JSON-RPC 2.0 A2A message/send (or message/stream)."""
    return (
        isinstance(body, dict)
        and body.get("jsonrpc") == "2.0"
        and isinstance(body.get("method"), str)
        and body["method"].startswith("message/")
    )


def _parts_to_text(parts) -> str:
    """Concatenate all text parts from an A2A parts list."""
    if not isinstance(parts, list):
        return ""
    texts = []
    for p in parts:
        if isinstance(p, dict):
            t = p.get("text") or p.get("content") or ""
            if t and isinstance(t, str):
                texts.append(t)
    return " ".join(texts).strip()


def _extract_a2a_prompt(body: dict) -> str:
    """
    Fast-path extractor for JSON-RPC 2.0 A2A request payloads.
    Handles:
      params.message.parts[]          (message/send, message/stream)
      params.messages[-1].parts[]     (history array variant)
    """
    params = body.get("params") or {}
    if not isinstance(params, dict):
        return ""
    # Single-message variant: params.message.parts
    msg = params.get("message")
    if isinstance(msg, dict):
        text = _parts_to_text(msg.get("parts") or [])
        if text:
            return text
    # Multi-message / history variant: params.messages[].parts
    messages = params.get("messages")
    if isinstance(messages, list):
        for m in reversed(messages):
            if isinstance(m, dict):
                text = _parts_to_text(m.get("parts") or [])
                if text:
                    return text
    return ""


def _extract_a2a_response(body: dict) -> str:
    """
    Fast-path extractor for JSON-RPC 2.0 A2A response payloads.
    Handles:
      result.artifacts[].parts[]           (task completed with artifacts)
      result.status.message.parts[]        (status message)
      result.history[-1].parts[]           (last assistant turn)
      result (plain string)
    """
    result = body.get("result")
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    if not isinstance(result, dict):
        return ""
    # Artifacts (primary A2A completed-task shape)
    artifacts = result.get("artifacts")
    if isinstance(artifacts, list):
        texts = []
        for art in artifacts:
            if isinstance(art, dict):
                text = _parts_to_text(art.get("parts") or [])
                if text:
                    texts.append(text)
        if texts:
            return " ".join(texts)
    # Status message (e.g. failed state)
    status = result.get("status")
    if isinstance(status, dict):
        msg_block = status.get("message")
        if isinstance(msg_block, dict):
            text = _parts_to_text(msg_block.get("parts") or [])
            if text:
                return text
    # History (last assistant turn)
    history = result.get("history")
    if isinstance(history, list):
        for m in reversed(history):
            if isinstance(m, dict) and m.get("role") in ("assistant", "agent"):
                text = _parts_to_text(m.get("parts") or [])
                if text:
                    return text
    return ""

# ---------------------------------------------------------------------------
# Text extraction — generic A2A / WXO agent protocol
# ---------------------------------------------------------------------------

def _extract_text_field(obj) -> str | None:
    """Recursively extract plain text from standard, A2A, or nested agent responses."""
    if obj is None:
        return None
    if isinstance(obj, str):
        try:
            parsed = json.loads(obj)
            if isinstance(parsed, (dict, list)):
                return _extract_text_field(parsed)
        except Exception:
            pass
        return obj
    if isinstance(obj, dict):
        # A2A fast-path: JSON-RPC 2.0 request (params.message.parts)
        if _is_a2a_request(obj):
            text = _extract_a2a_prompt(obj)
            if text:
                return text
        # A2A fast-path: JSON-RPC 2.0 response (result.artifacts / result.status)
        if obj.get("jsonrpc") == "2.0" and "result" in obj:
            text = _extract_a2a_response(obj)
            if text:
                return text
        if "artifacts" in obj and isinstance(obj["artifacts"], list):
            texts = []
            for art in obj["artifacts"]:
                if isinstance(art, dict) and "parts" in art and isinstance(art["parts"], list):
                    for part in art["parts"]:
                        if isinstance(part, dict) and "text" in part and isinstance(part["text"], str):
                            texts.append(part["text"])
            if texts:
                return "".join(texts)
        r_block = obj.get("result")
        if isinstance(r_block, dict):
            parts = r_block.get("parts")
            if isinstance(parts, list) and parts:
                first = parts[0]
                if isinstance(first, dict) and first.get("text"):
                    return str(first["text"])
        status = obj.get("status")
        if isinstance(status, dict) and status.get("state") == "failed":
            msg_block = status.get("message")
            if isinstance(msg_block, dict):
                parts = msg_block.get("parts")
                if isinstance(parts, list) and parts:
                    first = parts[0]
                    if isinstance(first, dict) and first.get("text"):
                        return str(first["text"])
        if "history" in obj and isinstance(obj["history"], list):
            for msg in reversed(obj["history"]):
                if isinstance(msg, dict) and msg.get("role") in ("assistant", "agent"):
                    for part in msg.get("parts", []):
                        if isinstance(part, dict) and "text" in part and isinstance(part["text"], str):
                            return part["text"]
        for k in ("outputText", "result", "text", "content", "message", "response", "answer", "output", "prompt"):
            if k in obj:
                v = obj[k]
                if isinstance(v, str):
                    return v
                if isinstance(v, list) and v:
                    res = _extract_text_field(v[0])
                    if res:
                        return res
                if isinstance(v, dict):
                    res = _extract_text_field(v)
                    if res:
                        return res
        for v in obj.values():
            if isinstance(v, (dict, list)):
                res = _extract_text_field(v)
                if res:
                    return res
    if isinstance(obj, list) and obj:
        for item in obj:
            res = _extract_text_field(item)
            if res:
                return res
    return None

# ---------------------------------------------------------------------------
# Azure AI Foundry — OpenAI Responses API extractors (SSE + JSON)
# Always compiled in; only called when _PLATFORM == "azure_ai_foundry"
# ---------------------------------------------------------------------------

def _content_to_text(content) -> str:
    """Normalise an OpenAI Responses API content field to plain text."""
    if isinstance(content, str):
        stripped = content.strip()
        if stripped.startswith("[") or stripped.startswith("{"):
            try:
                result = _content_to_text(json.loads(stripped))
                if result:
                    return result
            except Exception:
                pass
        return content
    if isinstance(content, list):
        parts = []
        for c in content:
            if not isinstance(c, dict):
                continue
            t = c.get("text", "")
            if t:
                parts.append(t)
                continue
            if c.get("type") == "message":
                inner = _content_to_text(c.get("content", ""))
                if inner:
                    parts.append(inner)
        return " ".join(parts)
    return ""


_TOOL_CONTINUATION_ROLES = frozenset({"tool", "assistant", "function", "system"})


def _is_tool_continuation(body: dict) -> bool:
    """Return True when body is an internal tool-result continuation request.

    Covers all Azure kind:hosted agent frameworks that re-enter the
    ResponsesHostServer to submit tool outputs:

      Responses API (agent_framework, semantic_kernel, autogen, custom):
        {"previous_response_id": "...", "input": [{"role": "tool", ...}]}

        Azure agent framework also re-enters with the full history:
        {"previous_response_id": "...", "input": [
            {"role": "user",      ...},   ← original user message still present
            {"role": "assistant", ...},   ← agent tool_call turn
            {"role": "tool",      ...}    ← tool result  ← last item
        ]}
        The key signal is previous_response_id + ANY "tool" role in the list.

      OpenAI chat-completions style (some custom adapters):
        {"messages": [..., {"role": "tool", "content": "..."}]}   ← last is tool

      Stringified tool output (rare):
        {"previous_response_id": "...", "input": "<tool result text>"}

    A genuine NEW user request never carries previous_response_id alongside
    a tool-role message.
    """
    if not isinstance(body, dict):
        return False

    has_prev = bool(body.get("previous_response_id"))

    # ── Responses API shape: input is a list ─────────────────────────────────
    inp = body.get("input")
    if isinstance(inp, list) and inp:
        last = inp[-1] if inp else {}
        # Last message is a non-user role → tool continuation
        if isinstance(last, dict) and last.get("role") in _TOOL_CONTINUATION_ROLES:
            return True
        # previous_response_id present AND any tool-role message in the list
        # (Azure agent framework sends full history on re-entry)
        if has_prev:
            roles = {item.get("role") for item in inp if isinstance(item, dict)}
            if "tool" in roles or "function" in roles:
                return True
        # No user message anywhere in the list → tool continuation
        roles = {item.get("role") for item in inp if isinstance(item, dict)}
        if roles and "user" not in roles:
            return True

    # ── Chat-completions shape: messages is a list ────────────────────────────
    messages = body.get("messages")
    if isinstance(messages, list) and messages:
        last_msg = messages[-1] if messages else {}
        if isinstance(last_msg, dict) and last_msg.get("role") in _TOOL_CONTINUATION_ROLES:
            return True
        roles = {m.get("role") for m in messages if isinstance(m, dict)}
        if roles and "user" not in roles:
            return True

    # ── Stringified tool output with previous_response_id ────────────────────
    if has_prev and isinstance(inp, str):
        # Heuristic: no "?" in the input and it's short → likely a tool result
        if inp and "?" not in inp and len(inp) < 500:
            return True

    return False


def _extract_prompt_azure(body: dict) -> str:
    """Extract user prompt from an OpenAI Responses API request body."""
    inp = body.get("input", "")
    if isinstance(inp, str) and inp:
        return inp
    if isinstance(inp, list):
        for item in reversed(inp):
            if not isinstance(item, dict):
                continue
            if item.get("role") == "user":
                text = _content_to_text(item.get("content", ""))
                if text:
                    return text
    for key in ("message", "prompt", "query", "text"):
        v = body.get(key)
        if isinstance(v, str) and v:
            return v
    if body.get("role") == "user":
        text = _content_to_text(body.get("content", ""))
        if text:
            return text
    messages = body.get("messages", [])
    if isinstance(messages, list):
        for item in reversed(messages):
            if not isinstance(item, dict):
                continue
            if item.get("role") == "user":
                text = _content_to_text(item.get("content", ""))
                if text:
                    return text
    if inp:
        return json.dumps(inp)[:300]
    return ""


def _extract_tool_calls_from_responses_output(output: list) -> list:
    """Extract tool calls from the Responses API response.completed output array.

    The output array contains items of type:
      • "function_call"        — {name, arguments, call_id, ...}
      • "function_call_output" — {call_id, output, ...}  (the tool result)
      • "message"              — the final assistant message

    We pair each function_call with its matching function_call_output by call_id.
    """
    calls_by_id: dict = {}
    outputs_by_id: dict = {}

    for item in (output or []):
        if not isinstance(item, dict):
            continue
        t = item.get("type", "")
        if t == "function_call":
            cid = item.get("call_id", "") or item.get("id", "")
            calls_by_id[cid] = item
        elif t == "function_call_output":
            cid = item.get("call_id", "") or item.get("id", "")
            outputs_by_id[cid] = item.get("output", "")

    result = []
    for cid, fc in calls_by_id.items():
        name = fc.get("name", "")
        if not name:
            continue
        result.append({
            "name":   name,
            "input":  fc.get("arguments", ""),
            "output": str(outputs_by_id.get(cid, "")),
            "sub_calls": [],
        })
    return result


def _extract_response_azure(body: dict) -> tuple[str, int, int]:
    """Extract (text, input_tokens, output_tokens) from a Responses API response."""
    text = ""
    for item in body.get("output", []):
        if not isinstance(item, dict):
            continue
        if item.get("type") == "message":
            for c in item.get("content", []):
                if isinstance(c, dict) and c.get("type") == "output_text":
                    text = c.get("text", "")
                    break
        if text:
            break
    if not text:
        for key in ("text", "response", "answer"):
            v = body.get(key)
            if isinstance(v, str) and v:
                text = v
                break
    if not text and body.get("role") == "assistant":
        text = _content_to_text(body.get("content", ""))
    if not text:
        v = body.get("output")
        if isinstance(v, str) and v:
            text = v
    usage = body.get("usage", {})
    it = int(usage.get("input_tokens",  usage.get("prompt_tokens",     0)) or 0)
    ot = int(usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0)
    return text, it, ot


def _extract_prompt_from_completed_azure(full_resp: dict) -> str:
    """Recover user prompt from a response.completed SSE event when request had no input."""
    inp = full_resp.get("input", "")
    if isinstance(inp, str) and inp:
        return inp
    if isinstance(inp, list):
        for item in reversed(inp):
            if isinstance(item, dict) and item.get("role") == "user":
                content = item.get("content", "")
                if isinstance(content, str) and content:
                    return content
    return ""


def _extract_prompt(body: dict) -> str:
    """Unified prompt extractor — Responses API on Azure, A2A/generic elsewhere."""
    if _PLATFORM == "azure_ai_foundry":
        return _extract_prompt_azure(body)
    # A2A fast-path: JSON-RPC 2.0 message/send or message/stream
    if _is_a2a_request(body):
        text = _extract_a2a_prompt(body)
        if text:
            return text
    result = _extract_text_field(body)
    if result:
        return result
    args = (body.get("params") or {}).get("arguments") or {}
    result = _extract_text_field(args)
    if result:
        return result
    return json.dumps(body)[:500] if body else ""


def _normalise_tool_call(tc: dict) -> dict | None:
    """Normalise a single raw tool-call dict into the standard {name,input,output,sub_calls} shape.

    Handles:
      • OpenAI format:   {id, type, function: {name, arguments}}
      • Bedrock toolUse: {name/toolUseId, input}
      • Generic:         {name, input/parameters, output/result}
      • With sub_calls:  any of the above + sub_calls / subCalls list
    """
    fn   = tc.get("function") or {}
    name = (fn.get("name") or tc.get("name") or tc.get("toolName") or tc.get("toolUseId") or "").strip()
    if not name:
        return None
    inp = (fn.get("arguments")
           or (json.dumps(tc["input"]) if isinstance(tc.get("input"), dict) else str(tc.get("input") or ""))
           or str(tc.get("parameters") or ""))
    out = str(tc.get("output") or tc.get("result") or "")

    # Recurse into sub_calls / subCalls
    raw_sub = tc.get("sub_calls") or tc.get("subCalls") or tc.get("sub_tools") or []
    sub_calls = []
    for s in (raw_sub if isinstance(raw_sub, list) else []):
        if isinstance(s, dict):
            n = _normalise_tool_call(s)
            if n:
                sub_calls.append(n)

    return {"name": name, "input": inp, "output": out, "sub_calls": sub_calls}


def _extract_tool_calls_from_body(body: dict) -> list:
    """Extract tool/function invocations from an agent response body.

    Handles multiple formats:
      • OpenAI / Azure chat completions: choices[].message.tool_calls[]
      • AWS Bedrock Converse API:         output.message.content[].toolUse
      • A2A JSON-RPC result:              result.parts[].toolUse
      • Generic:                          tool_calls[] / toolCalls[] at top level
      • Nested:                           any of the above + sub_calls / subCalls

    Returns a list of {name, input, output, sub_calls} dicts.
    output is "" for tool calls extracted from LLM responses (the output comes
    back in the next user turn), but is populated when the event carries both
    the call and its result (e.g. AgentCore callback events).
    """
    if not isinstance(body, dict):
        return []
    raw: list = []

    # ── OpenAI / Azure chat completions format ────────────────────────────────
    for choice in (body.get("choices") or []):
        msg = choice.get("message") or {}
        for tc in (msg.get("tool_calls") or []):
            raw.append(tc)

    # ── AWS Bedrock Converse API format ───────────────────────────────────────
    out_msg = ((body.get("output") or {}).get("message") or {})
    for part in (out_msg.get("content") or []):
        if "toolUse" in part:
            raw.append(part["toolUse"])

    # ── Top-level tool_calls / toolCalls arrays ───────────────────────────────
    for tc in (body.get("tool_calls") or body.get("toolCalls") or []):
        if isinstance(tc, dict):
            raw.append(tc)

    # ── A2A / JSON-RPC result envelope ────────────────────────────────────────
    result = body.get("result") or {}
    if isinstance(result, dict):
        for part in (result.get("parts") or []):
            if isinstance(part, dict) and "toolUse" in part:
                raw.append(part["toolUse"])
        # Also check result.tool_calls (some A2A servers surface them here)
        for tc in (result.get("tool_calls") or result.get("toolCalls") or []):
            if isinstance(tc, dict):
                raw.append(tc)
        # A2A v0.2 artifacts — result.artifacts[].parts[].text may be JSON with tool_calls
        for artifact in (result.get("artifacts") or []):
            if not isinstance(artifact, dict):
                continue
            for part in (artifact.get("parts") or []):
                if not isinstance(part, dict):
                    continue
                text = part.get("text") or part.get("content") or ""
                if not isinstance(text, str) or not text.strip().startswith("{"):
                    continue
                try:
                    parsed = __import__("json").loads(text)
                    if not isinstance(parsed, dict):
                        continue
                    # Direct tool_calls array embedded in artifact text
                    for tc in (parsed.get("tool_calls") or parsed.get("toolCalls") or []):
                        if isinstance(tc, dict):
                            raw.append(tc)
                except Exception:
                    pass

    # Normalise + deduplicate by name+input
    calls = []
    seen: set = set()
    for tc in raw:
        if not isinstance(tc, dict):
            continue
        n = _normalise_tool_call(tc)
        if n is None:
            continue
        k = (n["name"], str(n["input"])[:100])
        if k not in seen:
            seen.add(k)
            calls.append(n)
    return calls


def _extract_response_text(body: dict) -> tuple[str, int, int]:
    """Unified response extractor — returns (text, input_tokens, output_tokens)."""
    if _PLATFORM == "azure_ai_foundry":
        return _extract_response_azure(body)
    # A2A fast-path: JSON-RPC 2.0 response with result envelope
    if isinstance(body, dict) and body.get("jsonrpc") == "2.0" and "result" in body:
        text = _extract_a2a_response(body)
        if text:
            return text, 0, 0
    text = _extract_text_field(body) or ""
    # Read real token counts from the response body when present.
    # Our framework agents return {"outputText":…, "usage":{"inputTokens":…,"outputTokens":…}}
    # Also accept flat keys: inputTokens/outputTokens, input_tokens/output_tokens.
    it = ot = 0
    if isinstance(body, dict):
        usage = body.get("usage") or {}
        if isinstance(usage, dict):
            it = int(usage.get("inputTokens")  or usage.get("input_tokens")  or 0)
            ot = int(usage.get("outputTokens") or usage.get("output_tokens") or 0)
        if not it:
            it = int(body.get("inputTokens")  or body.get("input_tokens")  or 0)
        if not ot:
            ot = int(body.get("outputTokens") or body.get("output_tokens") or 0)
    return text, it, ot


def _apply_response_meta(ctx: dict, parsed_resp: dict, it: int = 0, ot: int = 0) -> None:
    """Stamp real usage + model_id from an agent JSON response onto ctx."""
    if it or ot:
        ctx["input_tokens"]  = it
        ctx["output_tokens"] = ot
    if ctx.get("model_name") or not isinstance(parsed_resp, dict):
        return
    model = (parsed_resp.get("modelId") or parsed_resp.get("model_id")
             or parsed_resp.get("model") or parsed_resp.get("modelName") or "")
    if model:
        ctx["model_name"] = str(model).strip()


# ---------------------------------------------------------------------------
# Per-request tenant context (multi-tenant / cloud_agent / aws_agentcore)
# ---------------------------------------------------------------------------

def _resolve_tenant_context(headers: dict, body_parsed: dict) -> dict:
    """
    Resolve WXO tenant/agent identity for a single request.
    Priority: HTTP headers > request body metadata > env vars.
    Returns a dict with: tenant_id, agent_id, agent_name, api_key, token_url,
                         export_url, environment, model_name, session_id, user_id.
    """
    meta = {}
    params = {}
    if isinstance(body_parsed, dict):
        params = body_parsed.get("params") or {}
        if isinstance(params, dict):
            meta = params.get("metadata") or {}
            if not isinstance(meta, dict):
                meta = {}

    message = params.get("message") if isinstance(params.get("message"), dict) else {}

    def _h(key):        return headers.get(key, "") or headers.get(key.lower(), "")
    def _m(key):        return str(meta.get(key, "")) if meta.get(key) else ""
    def _b(*keys):
        if not isinstance(body_parsed, dict):
            return ""
        for k in keys:
            v = body_parsed.get(k)
            if v is not None and str(v).strip():
                return str(v).strip()
        return ""

    tenant_id   = _h("x-ibm-tenant-id")   or _m("tenant_id")   or _TENANT_ID
    agent_id    = _h("x-ibm-agent-id")    or _m("agent_id")    or _AGENT_ID
    agent_name  = _h("x-ibm-agent-name")  or _m("agent_name")  or _AGENT_NAME
    api_key     = _h("x-ibm-api-key")     or _m("api_key")     or _API_KEY
    token_url   = _h("x-ibm-token-url")   or _m("token_url")   or _TOKEN_URL
    export_url  = _h("x-ibm-export-url")  or _m("export_url")  or _EXPORT_URL or _HOOK_URL
    environment = _h("x-ibm-environment") or _m("environment") or _ENVIRONMENT
    model_name  = (_h("x-ibm-model-name") or _h("x-wxo-model-name")
                   or _m("model_name") or _m("model") or _m("model_id") or _m("modelId")
                   # Request body (AgentCore / Bedrock Converse shapes)
                   or _b("modelId", "model_id", "model", "modelName")
                   or os.environ.get("BEDROCK_MODEL_ID", "")
                   or os.environ.get("AWS_BEDROCK_MODEL_ID", "")
                   or os.environ.get("WXO_MODEL_NAME", "")
                   or os.environ.get("MODEL_ID", ""))
    session_id  = (params.get("contextId") or message.get("contextId")
                   or _m("thread_id") or _m("session_id") or _m("sessionId")
                   or _h("x-wxo-thread-id") or _h("x-ibm-conversation-id")
                   # AgentCore Runtime session — header is the stable per-conversation key
                   or _h("x-amzn-bedrock-agentcore-runtime-session-id")
                   or _h("x-amzn-bedrock-agentcore-session-id")
                   or _h("x-amzn-session-id")
                   or _b("contextId", "conversation_id", "conversationId",
                         "runtimeSessionId", "sessionId", "session_id", "threadId")
                   or "")
    user_id     = (_h("x-ibm-user-id") or _h("x-wxo-user-id")
                   or _m("user_id") or _m("userId") or f"usr_{uuid.uuid4().hex[:12]}")

    return {
        "tenant_id":   tenant_id,
        "agent_id":    agent_id,
        "agent_name":  agent_name,
        "api_key":     api_key,
        "token_url":   token_url,
        "export_url":  export_url,
        "environment": environment,
        "model_name":  str(model_name),
        "session_id":  str(session_id),
        "user_id":     user_id,
        # Azure token counts (filled in by Starlette/ASGI path on azure_ai_foundry)
        "input_tokens":  0,
        "output_tokens": 0,
    }

# ---------------------------------------------------------------------------
# OpenTelemetry child-span capture (optional, SDK must be installed)
# ---------------------------------------------------------------------------

_otel_available = False
try:
    from opentelemetry import trace as _otel_trace
    from opentelemetry.sdk.trace import TracerProvider as _TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor as _SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter as _InMemoryExporter
    from opentelemetry.sdk.resources import Resource as _Resource
    from opentelemetry.trace import SpanKind as _SpanKind
    from opentelemetry.context import attach as _ctx_attach, detach as _ctx_detach
    _otel_available = True
    _LOG.info("opentelemetry-sdk found — child span capture enabled")
except ImportError:
    _LOG.info("opentelemetry-sdk not installed — single-span mode")


def _readable_span_to_otlp_dict(span, trace_id_hex: str, parent_span_id_hex: str) -> dict:
    ctx = span.context
    sid = f"{ctx.span_id:016x}"
    # Always use the caller-supplied trace_id_hex so every span in the payload
    # shares the same trace ID as the root span, regardless of what the OTel SDK
    # generated internally.
    attrs = []
    for k, v in (span.attributes or {}).items():
        if isinstance(v, int):
            attrs.append({"key": k, "value": {"intValue": int(v)}})
        else:
            attrs.append({"key": k, "value": {"stringValue": str(v)}})
    status_code = 2 if (span.status and span.status.status_code.name == "ERROR") else 0
    return {
        "traceId":           trace_id_hex,
        "spanId":            sid,
        "parentSpanId":      f"{span.parent.span_id:016x}" if span.parent else parent_span_id_hex,
        "name":              span.name,
        "kind":              span.kind.value if span.kind else 3,
        "startTimeUnixNano": span.start_time,
        "endTimeUnixNano":   span.end_time,
        "status":            {"code": status_code},
        "attributes":        attrs,
    }


class _RequestSpanContext:
    """OTel TracerProvider + root span lifetime for a single request."""

    def __init__(self, ctx: dict):
        self._ctx = ctx
        self._provider = None
        self._exporter = None
        self._root_span = None
        self._token     = None
        import secrets as _sec
        self.root_trace_id = uuid.uuid4().hex
        self.root_span_id  = _sec.token_hex(8)

    def __enter__(self):
        if not _otel_available:
            return self
        resource = _Resource.create({
            "service.name":           self._ctx["agent_name"],
            "service.version":        "1.0.0",
            "tenant.id":              self._ctx["tenant_id"],
            "agent.id":               self._ctx["agent_id"],
            "agent.name":             self._ctx["agent_name"],
            "environment.name":       self._ctx["environment"],
            "deployment.environment": self._ctx["environment"],
            "gen_ai.agent.id":        self._ctx["agent_id"],
            "gen_ai.agent.name":      self._ctx["agent_name"],
        })
        self._exporter = _InMemoryExporter()
        self._provider = _TracerProvider(resource=resource)
        self._provider.add_span_processor(_SimpleSpanProcessor(self._exporter))
        tracer = self._provider.get_tracer("wxo-hook", "1.0.0")
        self._root_span = tracer.start_span(
            f"invoke_agent {self._ctx['agent_name']}", kind=_SpanKind.SERVER,
        )
        from opentelemetry.trace import set_span_in_context as _ssic
        self._token = _ctx_attach(_ssic(self._root_span))
        span_ctx = self._root_span.get_span_context()
        self.root_trace_id = f"{span_ctx.trace_id:032x}"
        self.root_span_id  = f"{span_ctx.span_id:016x}"
        return self

    def finish(self, is_error: bool = False, error_msg: str = ""):
        if self._root_span is None:
            return
        try:
            if is_error:
                from opentelemetry.trace import Status, StatusCode
                self._root_span.set_status(Status(StatusCode.ERROR, error_msg[:500]))
            self._root_span.end()
        except Exception:
            pass
        if self._token is not None:
            try:
                _ctx_detach(self._token)
            except Exception:
                pass

    def get_child_spans(self) -> list:
        if self._exporter is None:
            return []
        return [
            _readable_span_to_otlp_dict(s, self.root_trace_id, self.root_span_id)
            for s in self._exporter.get_finished_spans()
            if f"{s.context.span_id:016x}" != self.root_span_id
        ]

    def shutdown(self):
        if self._provider is not None:
            try:
                self._provider.shutdown()
            except Exception:
                pass

# ---------------------------------------------------------------------------
# POST span to WXO
# ---------------------------------------------------------------------------

def _is_tool_span_dict(sp: dict, attrs: dict) -> bool:
    """Return True when *sp* (OTel span dict) represents a tool / function invocation."""
    oi = attrs.get("openinference.span.kind", "")
    if oi == "TOOL":
        return True
    n = sp.get("name", "")
    return (
        bool(attrs.get("tool.name") or attrs.get("gen_ai.tool.name"))
        or "tool" in n.lower()
        or "function_call" in n.lower()
    )


def _extract_tool_calls_from_child_spans(child_spans: list) -> list:
    """Scan OTel child span dicts and extract TOOL spans as tool_call records.

    Preserves parent-child relationships: a TOOL span whose parentSpanId is
    another TOOL span's spanId becomes a ``sub_calls`` entry on the parent,
    matching the full nested hierarchy the agent actually executed.

    Each tool span dict has an "attributes" list of {"key":..., "value":{...}} entries.
    Returns a list of top-level tool_call dicts (children of generate_content /
    call_llm / invoke_agent), each optionally carrying:
        sub_calls: [{name, input, output, start_ns, end_ns, is_error, sub_calls}, ...]
    """
    if not child_spans:
        return []

    # ── Build span-id → attrs dict and classify each span ────────────────────
    span_by_id: dict[str, dict] = {}
    tool_span_ids: set = set()
    for sp in child_spans:
        sid = sp.get("spanId", "")
        if not sid:
            continue
        attrs_raw = sp.get("attributes") or []
        attrs: dict = {}
        for a in attrs_raw:
            val = a.get("value", {})
            attrs[a["key"]] = (
                val.get("stringValue") or val.get("intValue") or val.get("boolValue") or ""
            )
        sp["_attrs"] = attrs   # cache for reuse below
        span_by_id[sid] = sp
        if _is_tool_span_dict(sp, attrs):
            tool_span_ids.add(sid)

    # ── Build tool_call dicts, grouping sub-tools under their parent ──────────
    def _tc_from_span(sp: dict) -> dict:
        attrs = sp.get("_attrs", {})
        tool_name = attrs.get("tool.name") or attrs.get("gen_ai.tool.name") or sp.get("name", "")
        return {
            "name":     tool_name,
            "input":    str(attrs.get("tool.parameters") or attrs.get("input.value") or ""),
            "output":   str(attrs.get("tool.output") or attrs.get("output.value") or ""),
            "start_ns": int(sp.get("startTimeUnixNano") or 0),
            "end_ns":   int(sp.get("endTimeUnixNano") or 0),
            "is_error": sp.get("status", {}).get("code") == 2,
            "sub_calls": [],
        }

    # Build the tree: map parent_tool_span_id → [child tool_call dicts]
    tc_by_id: dict[str, dict] = {}
    for sid in tool_span_ids:
        tc_by_id[sid] = _tc_from_span(span_by_id[sid])

    # Assign each tool span either to its parent tool or to the top-level list
    top_level: list = []
    for sid in tool_span_ids:
        sp = span_by_id[sid]
        parent_id = sp.get("parentSpanId", "")
        if parent_id and parent_id in tool_span_ids:
            # Sub-tool: attach to parent's sub_calls
            tc_by_id[parent_id]["sub_calls"].append(tc_by_id[sid])
        else:
            # Top-level tool (parent is generate_content or call_llm or root)
            top_level.append(tc_by_id[sid])

    # Sort all lists by start_ns for deterministic ordering
    top_level.sort(key=lambda t: t.get("start_ns") or 0)
    for tc in tc_by_id.values():
        tc["sub_calls"].sort(key=lambda t: t.get("start_ns") or 0)

    # Clean up the cached _attrs before returning
    for sp in child_spans:
        sp.pop("_attrs", None)

    return top_level


def _post_trace(
    prompt: str,
    response: str,
    start_ns: int,
    end_ns: int,
    ctx: dict,
    is_error: bool = False,
    error_msg: str = "",
    trace_id: str = "",
    span_id: str = "",
    child_spans: list | None = None,
    tool_calls: list | None = None,
) -> None:
    """
    Build a WXO-compatible OTLP payload and fire-and-forget POST it to WXO.

    ctx is the per-request tenant context dict from _resolve_tenant_context().
    ctx["input_tokens"] / ctx["output_tokens"] carry real counts on Azure (set
    by the ASGI wrapper); elsewhere they are 0 and estimated internally.
    ctx["tool_calls"] may carry tool invocation records injected by agent code;
    these are merged with tool spans extracted from OTel child_spans.
    """
    if getattr(_IN_REQUEST_TRACE, "active", False):
        _LOG.debug("_post_trace: skipping duplicate call from secondary layer")
        return

    target_url = ctx.get("export_url") or ""
    if not target_url:
        return

    _IN_REQUEST_TRACE.active = True

    agent_id    = ctx["agent_id"]
    agent_name  = ctx["agent_name"]
    tenant_id   = ctx["tenant_id"]
    environment = ctx["environment"]
    api_key     = ctx["api_key"]
    token_url   = ctx["token_url"]
    platform    = _PLATFORM
    input_tokens  = ctx.get("input_tokens",  0)
    output_tokens = ctx.get("output_tokens", 0)

    # ── Merge tool calls: explicit list > ctx dict > extracted from OTel spans ──
    _tool_calls: list = (
        tool_calls
        if tool_calls is not None
        else (ctx.get("tool_calls") or [])
    )
    # Also mine any TOOL spans that the OTel SDK captured as child_spans
    _otel_tools = _extract_tool_calls_from_child_spans(child_spans or [])
    if _otel_tools:
        # Deduplicate by (name, start_ns) — OTel spans may already be in ctx.tool_calls
        _existing_keys = {(t.get("name"), t.get("start_ns")) for t in _tool_calls}
        for tc in _otel_tools:
            k = (tc.get("name"), tc.get("start_ns"))
            if k not in _existing_keys:
                _tool_calls.append(tc)
                _existing_keys.add(k)

    _LOG.info(
        f"trace | platform={platform!r} tenant={tenant_id!r} agent={agent_id!r} "
        f"prompt={prompt[:60]!r} response={response[:60]!r} tool_calls={len(_tool_calls)}"
    )

    if _wxo_span:
        _sid = ctx.get("session_id") or ""
        _extra = []
        if _sid:
            _extra.append({"key": "session.id", "value": {"stringValue": str(_sid)}})
            if platform == "aws_agentcore":
                _extra.append({"key": "aws.session.id", "value": {"stringValue": str(_sid)}})
        payload = _wxo_span.build_otlp_payload(
            agent_id=agent_id, agent_name=agent_name,
            tenant_id=tenant_id, environment=environment,
            prompt=prompt, response=response,
            start_ns=start_ns, end_ns=end_ns,
            is_error=is_error, error_msg=error_msg,
            platform=platform, model_name=ctx.get("model_name", ""),
            trace_id=trace_id, span_id=span_id,
            session_id=_sid, user_id=ctx.get("user_id", ""),
            input_tokens=input_tokens, output_tokens=output_tokens,
            child_spans=child_spans or [],
            tool_calls=_tool_calls or None,
            extra_attributes=_extra or None,
            reasoning_steps=ctx.get("reasoning_steps") or None,
        )
    else:
        import re as _re, secrets as _sec
        _pat       = _re.compile(r"(?i:'s|'t|'re|'ve|'m|'ll|'d)|[^\W\d_]+|\d{1,3}|[^\w\s]+", _re.UNICODE)
        _trace_id  = trace_id or uuid.uuid4().hex
        _span_id   = span_id  or _sec.token_hex(8)
        session_id = ctx.get("session_id") or str(uuid.uuid4())
        user_id    = ctx.get("user_id") or f"usr_{uuid.uuid4().hex[:12]}"
        span_name  = f"invoke_agent {agent_name}"
        latency_ms = max(1, (end_ns - start_ns) // 1_000_000)
        tokens_estimated = (input_tokens == 0 and output_tokens == 0)
        if tokens_estimated:
            input_tokens  = len(_pat.findall(prompt))   if prompt   else 0
            output_tokens = len(_pat.findall(response)) if response else 0
        total_tokens = input_tokens + output_tokens

        # Azure error type label
        _error_type = {"azure_ai_foundry": "AzureAgentError",
                       "aws_agentcore":    "AgentCoreError"}.get(platform, "AgentError")

        sv = lambda k, v: {"key": k, "value": {"stringValue": str(v)}}
        iv = lambda k, v: {"key": k, "value": {"intValue":    int(v)}}
        input_msg  = json.dumps([{"role": "user",      "content": prompt}])
        output_msg = json.dumps([{"role": "assistant", "content": response}])
        _sc_workspace_id = "00000000-0000-0000-0000-000000000001"
        _sc_model = ctx.get("model_name") or ""
        _sc_tags = json.dumps([
            f"agent_id:{agent_id}",
            f"environment:{environment}",
            f"tenant_id:{tenant_id}",
            f"workspace_id:{_sc_workspace_id}",
        ])
        attrs = [
            sv("agent.id",              agent_id),
            sv("agent.name",            agent_name),
            sv("agent.display_name",    agent_name),
            sv("agent.version",         "1"),
            sv("gen_ai.operation.name", "invoke_agent"),
            sv("gen_ai.agent.id",       agent_id),
            sv("gen_ai.agent.name",     agent_name),
            sv("thread.id",             session_id),
            sv("conversation.id",       session_id),
            sv("session.id",            session_id),
            sv("langfuse.session.id",   session_id),
            sv("langfuse.user.id",      user_id),
            sv("message.id",            str(uuid.uuid4())),
            sv("environment.name",      environment),
            sv("environment.id",        environment),
            sv("workspace.id",          _sc_workspace_id),
            sv("instance.id",           tenant_id),
            sv("tenant.id",             tenant_id),
            # WXO facet attributes — tag generation and routing
            sv("wxo.facet.tenant_id",    tenant_id),
            sv("wxo.facet.workspace_id", _sc_workspace_id),
            sv("wxo.facet.agent_id",     agent_id),
            sv("wxo.facet.workflow_id",  span_name),
            sv("wxo.channel.name",       "external_agent"),
            sv("wxo.channel.type",       "text"),
            # Langfuse trace-level markers
            sv("langfuse.internal.as_root", "true"),
            sv("langfuse.trace.name",    span_name),
            sv("langfuse.tags",          _sc_tags),
            sv("is.root",                "true"),
            sv("global_transaction_id",  _trace_id),
            sv("gen_ai.input.messages",  input_msg),
            sv("gen_ai.output.messages", output_msg),
            # Structured WXO message envelope — gives the Langfuse trace a rich input object
            sv("gen_ai.message.input",   json.dumps({
                "role": "user", "content": prompt,
                "mentions": None, "document_ids": None, "parent_message_id": None,
                "additional_properties": {
                    "wxa_message": None, "display_properties": None, "tool_calls": None,
                    "tool_call_id": None, "tool_name": None, "wxo_connection_status": None,
                    "log_id": None, "captured_logs": None, "is_interrupt": False,
                    "tool_flow_properties": None, "architect_conversational_state": None,
                    "current_workflow": None, "metadata": None, "agent_id": None,
                    "a2a_task_completed": False, "error_code": None,
                },
                "assistant_id": None, "context": None, "step_history": None,
                "message_state": None, "log_id": None, "meta": None,
                "user_defined": None, "session_id": session_id, "trace_id": None,
            })),
            sv("input.value",    prompt),   sv("output.value",   response),
            sv("gen_ai.task.input", prompt), sv("gen_ai.task.output", response),
            sv("input",  prompt),           sv("output", response),
            sv("llm.model_name",          _sc_model),
            sv("model",                   _sc_model),
            sv("gen_ai.response.model",   _sc_model),
            sv("llm.system",       platform),
            sv("framework",        platform),
            sv("agent.execution.status", "error"  if is_error else "success"),
            sv("agent.business_outcome", "failed" if is_error else "success"),
            sv("tokens.estimated",       str(tokens_estimated).lower()),
            sv("openinference.span.kind", "AGENT"),
            sv("gen_ai.system",           platform),
            sv("gen_ai.request.model",    _sc_model),
            iv("latency_ms",                      latency_ms),
            iv("llm.usage.prompt_tokens",         input_tokens),
            iv("llm.usage.completion_tokens",     output_tokens),
            iv("llm.usage.total_tokens",          total_tokens),
            iv("gen_ai.usage.prompt_tokens",      input_tokens),
            iv("gen_ai.usage.completion_tokens",  output_tokens),
            iv("gen_ai.usage.input_tokens",       input_tokens),
            iv("gen_ai.usage.output_tokens",      output_tokens),
            iv("llm.token_count.prompt",          input_tokens),
            iv("llm.token_count.completion",      output_tokens),
            iv("llm.token_count.total",           total_tokens),
            sv("provided_usage_details",
               json.dumps({"input": input_tokens, "output": output_tokens, "total": total_tokens})),
            sv("langfuse.observation.usage_details",
               json.dumps({"input": input_tokens, "output": output_tokens, "total": total_tokens})),
        ]
        # Azure-specific session tag
        if platform == "azure_ai_foundry" and session_id:
            attrs.append(sv("azure.session.id", session_id))
        if platform == "aws_agentcore" and session_id:
            attrs.append(sv("aws.session.id", session_id))
        if is_error and error_msg:
            attrs += [sv("error.type", _error_type), sv("error.message", error_msg[:4000])]

        # Reasoning step events — each entry becomes a ``steps`` row in Langfuse,
        # matching the shape emitted by WXO's internal LangGraph pipeline.
        _step_events: list[dict] = []
        _model_for_steps = ctx.get("model_name") or ""
        for _step_text in (ctx.get("reasoning_steps") or []):
            if _step_text:
                _step_events.append({
                    "name": "gen_ai.reasoning",
                    "timeUnixNano": start_ns,
                    "attributes": [
                        sv("gen_ai.reasoning.content", str(_step_text)[:4000]),
                        sv("langfuse.step.type",        "reasoning"),
                        sv("langfuse.step.name",        f"generate_content {_model_for_steps}".strip()),
                    ],
                })

        root_span = {
            "traceId": _trace_id, "spanId": _span_id, "name": span_name, "kind": 2,
            "startTimeUnixNano": start_ns, "endTimeUnixNano": end_ns,
            "status": {"code": 2 if is_error else 0}, "attributes": attrs,
            **({"events": _step_events} if _step_events else {}),
        }

        # ── Synthetic child tree: call_llm → generate_content <model> ─────────
        # Only emitted when no OTel child spans were already captured.
        _synthetic: list = []
        if not child_spans:
            import secrets as _sec2
            _model      = ctx.get("model_name") or ""
            _llm_id     = _sec2.token_hex(8)
            _gen_id     = _sec2.token_hex(8)
            _llm_start  = start_ns + max(1_000_000, (end_ns - start_ns) // 20)
            _llm_end    = end_ns   - max(1_000_000, (end_ns - start_ns) // 20)
            _gen_start  = _llm_start + max(500_000, (_llm_end - _llm_start) // 20)
            _gen_end    = _llm_end   - max(500_000, (_llm_end - _llm_start) // 20)
            _usage_json = json.dumps({"input": input_tokens, "output": output_tokens, "total": total_tokens})
            # CHAIN wrapper — usage lives only on generate_content (GENERATION)
            _llm_attrs  = [
                sv("openinference.span.kind",        "CHAIN"),
                sv("gen_ai.request.model",           _model),
                sv("gen_ai.response.model",          _model),
                sv("llm.model_name",                 _model),
                sv("model",                          _model),
                sv("gen_ai.system",                  platform),
                sv("gen_ai.input.messages",          input_msg),
                sv("gen_ai.output.messages",         output_msg),
            ]
            _synthetic.append({
                "traceId": _trace_id, "spanId": _llm_id, "parentSpanId": _span_id,
                "name": "call_llm", "kind": 3,
                "startTimeUnixNano": _llm_start, "endTimeUnixNano": _llm_end,
                "status": {"code": 2 if is_error else 0}, "attributes": _llm_attrs,
            })
            _gen_attrs = [
                sv("openinference.span.kind",        "LLM"),
                sv("gen_ai.request.model",           _model),
                sv("gen_ai.response.model",          _model),
                sv("llm.model_name",                 _model),
                sv("model",                          _model),
                sv("gen_ai.system",                  platform),
                sv("gen_ai.prompt",                  prompt[:2000]),
                sv("gen_ai.completion",              response[:2000]),
                sv("gen_ai.input.messages",          input_msg),
                sv("gen_ai.output.messages",         output_msg),
                iv("gen_ai.usage.input_tokens",      input_tokens),
                iv("gen_ai.usage.output_tokens",     output_tokens),
                iv("gen_ai.usage.prompt_tokens",     input_tokens),
                iv("gen_ai.usage.completion_tokens", output_tokens),
                iv("llm.usage.prompt_tokens",        input_tokens),
                iv("llm.usage.completion_tokens",    output_tokens),
                iv("llm.token_count.prompt",         input_tokens),
                iv("llm.token_count.completion",     output_tokens),
                iv("llm.token_count.total",          total_tokens),
                sv("provided_usage_details",               _usage_json),
                sv("langfuse.observation.usage_details",   _usage_json),
            ]
            _synthetic.append({
                "traceId": _trace_id, "spanId": _gen_id, "parentSpanId": _llm_id,
                "name": ("generate_content " + _model).strip() if _model else "generate_content", "kind": 3,
                "startTimeUnixNano": _gen_start, "endTimeUnixNano": _gen_end,
                "status": {"code": 2 if is_error else 0}, "attributes": _gen_attrs,
            })

            # ── TOOL spans — recursive helper handles sub_calls nesting ─────────
            # Use _tool_calls which already merges ctx, explicit arg, and OTel spans.
            _tc_list  = _tool_calls
            _tc_count = len(_tc_list)
            _gen_window = max(1, _gen_end - _gen_start)

            def _emit_tools_inline(tc_list, parent_id, win_s, win_e, _depth=0):
                """Recursively emit TOOL spans + sub_calls into _synthetic.

                Depth-aware span kind:
                  depth=0  → top-level tool call (has sub_calls)  → kind=CHAIN so
                             Langfuse renders it as a collapsible container with
                             the tool name visible, not a collapsed leaf.
                  depth>0  → sub-call / leaf tool execution       → kind=TOOL so
                             it renders as a tool invocation node.
                A top-level tool with NO sub_calls is also emitted as TOOL (leaf).
                """
                _cnt  = len(tc_list)
                _win  = max(1, win_e - win_s)
                _slot = _win // (_cnt + 1) if _cnt else _win
                for _ii, _t in enumerate(tc_list):
                    _ts = _t.get("start_ns") or (win_s + _slot * (_ii + 1))
                    _te = _t.get("end_ns")   or (_ts + max(1_000_000, _slot // 2))
                    _ts = max(win_s, min(_ts, win_e - 1_000_000))
                    _te = max(_ts + 1_000_000, min(_te, win_e))
                    _tn = str(_t.get("name", f"tool_{_ii}"))
                    _tid = _sec2.token_hex(8)
                    _sub = _t.get("sub_calls") or []
                    # Parent tool (has sub_calls) → CHAIN so Langfuse shows it as
                    # a collapsible wrapper rather than collapsing it into the leaf.
                    _kind_val = "CHAIN" if (_depth == 0 and _sub) else "TOOL"
                    _ta = [
                        sv("openinference.span.kind", _kind_val),
                        sv("tool.name",               _tn),
                        sv("gen_ai.tool.name",        _tn),
                    ]
                    if _t.get("input"):
                        _ta.append(sv("tool.parameters", str(_t["input"])[:2000]))
                        _ta.append(sv("input.value",     str(_t["input"])[:2000]))
                    if _t.get("output"):
                        # NB: no output.value on TOOL spans — WXO drops the span.
                        _ta.append(sv("tool.output",  str(_t["output"])[:2000]))
                    _synthetic.append({
                        "traceId": _trace_id, "spanId": _tid, "parentSpanId": parent_id,
                        "name": _tn, "kind": 3,
                        "startTimeUnixNano": _ts, "endTimeUnixNano": _te,
                        "status": {"code": 2 if _t.get("is_error") else 0},
                        "attributes": _ta,
                    })
                    if _sub:
                        _emit_tools_inline(_sub, _tid, _ts, _te, _depth + 1)

            _emit_tools_inline(_tc_list, _gen_id, _gen_start, _gen_end)

            # ── RETRIEVER span (RETRIEVER, child of generate_content) ─────────
            # Only emit retrieval spans when the agent actually has RAG data
            # (ctx["retrieval_calls"]) or when there are no tool calls at all
            # (kind:prompt / RAG-only agents that never call tools).
            # For kind:hosted agents that use tools, skip the synthetic stub —
            # a fake "retrieval" span alongside real tool spans is misleading.
            _rc_list  = ctx.get("retrieval_calls")
            if _rc_list is None and not _tc_list:
                _rc_list = [{}]   # synthetic stub only for tool-free agents
            if not _rc_list:
                _rc_list = []
            _rc_count = len(_rc_list)
            _rc_slot  = _gen_window // (_rc_count + _tc_count + 1) if _rc_count else _gen_window
            for _j, _rc in enumerate(_rc_list):
                _rc_start = _rc.get("start_ns") or (_gen_start + _rc_slot * (_tc_count + _j + 1))
                _rc_end   = _rc.get("end_ns")   or (_rc_start + max(1_000_000, _rc_slot // 2))
                _rc_start = max(_gen_start, min(_rc_start, _gen_end - 1_000_000))
                _rc_end   = max(_rc_start + 1_000_000, min(_rc_end, _gen_end))
                _rc_attrs = [
                    sv("openinference.span.kind", "RETRIEVER"),
                    sv("retrieval.source",        _rc.get("source", "knowledge_base")),
                ]
                if _rc.get("query"):
                    _rc_attrs.append(sv("input.value",       _rc["query"][:2000]))
                    _rc_attrs.append(sv("retrieval.query",   _rc["query"][:2000]))
                if _rc.get("result"):
                    _rc_attrs.append(sv("output.value",        _rc["result"][:2000]))
                    _rc_attrs.append(sv("retrieval.documents", _rc["result"][:2000]))
                _synthetic.append({
                    "traceId": _trace_id, "spanId": _sec2.token_hex(8),
                    "parentSpanId": _gen_id,
                    "name": _rc.get("name", "retrieval"), "kind": 3,
                    "startTimeUnixNano": _rc_start, "endTimeUnixNano": _rc_end,
                    "status": {"code": 2 if _rc.get("is_error") else 0},
                    "attributes": _rc_attrs,
                })

        spans   = [root_span] + _synthetic + (child_spans or [])
        payload = {"resourceSpans": [{"resource": {"attributes": [
            sv("service.name",              agent_name),
            sv("service.version",           "1.0.0"),
            sv("telemetry.sdk.language",    "python"),
            sv("telemetry.sdk.name",        "opentelemetry"),
            sv("telemetry.sdk.version",     "1.0.0"),
            sv("application",               agent_name),
            sv("tenant.id",                 tenant_id),
            sv("agent.id",                  agent_id),
            sv("agent.name",                agent_name),
            sv("agent.display_name",        agent_name),
            sv("gen_ai.agent.id",           agent_id),
            sv("gen_ai.agent.name",         agent_name),
            sv("environment.name",          environment),
            sv("deployment.environment",    environment),
        ]}, "scopeSpans": [{"scope": {"name": "wxo-universal-forwarder", "version": "2.0.0"}, "spans": spans}]}]}

    def _send():
        _IN_TRACE_POST.active = True
        try:
            token = _get_bearer_token_for(api_key, token_url)
            if not token:
                _LOG.warning(f"No bearer token (mode={_DEPLOYMENT_MODE!r} tenant={tenant_id!r}) — trace dropped")
                return
            if _wxo_span:
                _wxo_span.post_to_wxo(payload, token, target_url, agent_id, tenant_id, logger=_LOG)
            else:
                from urllib.request import Request as _R, urlopen as _u
                _post_headers = {
                    "Authorization": f"Bearer {token}", "Content-Type": "application/json",
                    "User-Agent": "curl/7.68.0",
                    "x-ibm-agent-id":               agent_id,
                    "x-langfuse-ingestion-version": "4",
                }
                if tenant_id and _DEPLOYMENT_MODE == "cloud":   # CPD has no tenant header
                    _post_headers["x-ibm-tenant-id"] = tenant_id
                    _post_headers["x-tenant-id"]     = tenant_id
                req = _R(target_url, data=json.dumps(payload).encode(),
                         headers=_post_headers, method="POST")
                with _u(req, timeout=30, context=_ssl_ctx()) as resp:
                    resp_body = json.loads(resp.read() or b"{}")
                    job_id    = resp_body.get("data", {}).get("id", "N/A")
                    _LOG.info(f"WXO POST {resp.status} mode={_DEPLOYMENT_MODE!r} job_id={job_id}")

            # Post evaluation scores if present in ctx
            _scores = ctx.get("scores") or []
            if _scores and _wxo_span and hasattr(_wxo_span, "post_scores_to_wxo"):
                _tid = (payload.get("resourceSpans", [{}])[0]
                               .get("scopeSpans", [{}])[0]
                               .get("spans", [{}])[0]
                               .get("traceId", ""))
                _wxo_span.post_scores_to_wxo(
                    _scores, token, target_url, agent_id, agent_name,
                    _tid, tenant_id, logger=_LOG,
                )
        except Exception as exc:
            _LOG.warning(f"Trace send failed: {exc}")
        finally:
            _IN_TRACE_POST.active = False

    threading.Thread(target=_send, daemon=True, name="wxo-post-trace").start()
    _IN_REQUEST_TRACE.active = False

# ---------------------------------------------------------------------------
# Central tracing entry point used by all sync framework patches
# ---------------------------------------------------------------------------

def _trace_request(
    prompt: str,
    call_original,       # callable(rsc) → (response_text, is_error, error_msg, start_ns, end_ns)
    headers: dict,       # lowercase header keys → values
    body_parsed: dict,
    input_tokens: int = 0,
    output_tokens: int = 0,
):
    """Resolve tenant ctx, activate OTel, call original handler, post trace."""
    ctx = _resolve_tenant_context(headers, body_parsed)
    ctx["input_tokens"]  = input_tokens
    ctx["output_tokens"] = output_tokens
    if not ctx["export_url"]:
        return

    rsc = _RequestSpanContext(ctx)
    rsc._ctx = ctx
    start_ns = time.time_ns()

    try:
        rsc.__enter__()
        response_text, is_error, error_msg, start_ns, end_ns = call_original(rsc)
        ctx["input_tokens"]  = rsc._ctx.get("input_tokens",  ctx["input_tokens"])
        ctx["output_tokens"] = rsc._ctx.get("output_tokens", ctx["output_tokens"])
        if rsc._ctx.get("model_name"):
            ctx["model_name"] = rsc._ctx["model_name"]
        if rsc._ctx.get("session_id"):
            ctx["session_id"] = rsc._ctx["session_id"]
    except Exception as exc:
        end_ns = time.time_ns()
        rsc.finish(is_error=True, error_msg=str(exc))
        rsc.shutdown()
        _post_trace("" if not prompt else prompt, "", start_ns, end_ns, ctx,
                    is_error=True, error_msg=str(exc),
                    trace_id=rsc.root_trace_id, span_id=rsc.root_span_id,
                    child_spans=rsc.get_child_spans())
        raise
    else:
        rsc.finish(is_error=is_error, error_msg=error_msg)
        child_spans = rsc.get_child_spans()
        rsc.shutdown()
        if prompt or response_text:
            _post_trace(prompt, response_text, start_ns, end_ns, ctx,
                        is_error=is_error, error_msg=error_msg,
                        trace_id=rsc.root_trace_id, span_id=rsc.root_span_id,
                        child_spans=child_spans)

# ---------------------------------------------------------------------------
# http.server patch
# ---------------------------------------------------------------------------

def _make_do_post_wrapper(original_do_post):
    def _wrapped_do_post(self):
        if getattr(_IN_TRACE_POST, "active", False):
            return original_do_post(self)

        # The gRPC agent's HTTP bridge calls the servicer directly (not via
        # grpc.server), so this HTTP hook is the only tracer for AgentCore
        # HTTP invocations.  Native gRPC traffic is still traced by the
        # interceptor; _inflight_claim prevents a double post if both fire.
        content_length = int(self.headers.get("Content-Length", 0) or 0)
        body_bytes = self.rfile.read(content_length) if content_length else b""
        self.rfile = io.BytesIO(body_bytes)

        if body_bytes and (b'"resourceSpans"' in body_bytes[:64] or b'"apikey"' in body_bytes[:64]):
            return original_do_post(self)

        # Claim this request — skip if another layer already owns it
        _dk = _inflight_claim(body_bytes)
        if _dk is None:
            return original_do_post(self)

        raw_headers: dict = {k.lower(): v for k, v in (self.headers.items() if hasattr(self, "headers") else [])}
        body_parsed: dict = {}
        prompt = ""
        try:
            body_parsed = json.loads(body_bytes.decode("utf-8", errors="replace"))
            if not isinstance(body_parsed, dict):
                body_parsed = {}
            prompt = _extract_prompt(body_parsed)
        except Exception:
            prompt = body_bytes.decode("utf-8", errors="replace")[:500]

        original_wfile = self.wfile
        _captured = []

        class _SniffingWfile:
            def write(self, data):
                if data:
                    _captured.append(data if isinstance(data, bytes) else data.encode("utf-8", errors="replace"))
                return original_wfile.write(data)
            def flush(self):
                return original_wfile.flush()
            def __getattr__(self, name):
                return getattr(original_wfile, name)

        self.wfile = _SniffingWfile()

        def _call_original(rsc):
            start = time.time_ns()
            is_err = False; err_msg = ""
            try:
                original_do_post(self)
            except Exception as exc:
                is_err = True; err_msg = str(exc); raise
            finally:
                end = time.time_ns()
                self.wfile = original_wfile
                resp_text = ""; it = ot = 0
                try:
                    raw = b"".join(_captured).decode("utf-8", errors="replace")
                    if "\r\n\r\n" in raw:
                        raw = raw.split("\r\n\r\n", 1)[1]
                    elif "\n\n" in raw:
                        raw = raw.split("\n\n", 1)[1]
                    parsed_resp = json.loads(raw.strip())
                    resp_text, it, ot = _extract_response_text(parsed_resp)
                    _apply_response_meta(rsc._ctx, parsed_resp, it, ot)
                    if not resp_text:
                        resp_text = json.dumps(parsed_resp)[:300]
                    # Extract tool calls from the response body and store in ctx
                    _body_tools = _extract_tool_calls_from_body(parsed_resp)
                    if _body_tools:
                        rsc._ctx.setdefault("tool_calls", [])
                        _existing = {(t.get("name"), str(t.get("input",""))[:100])
                                     for t in rsc._ctx["tool_calls"]}
                        for _bt in _body_tools:
                            k = (_bt["name"], str(_bt.get("input",""))[:100])
                            if k not in _existing:
                                rsc._ctx["tool_calls"].append(_bt)
                                _existing.add(k)
                except Exception:
                    pass
            return resp_text, is_err, err_msg, start, end

        try:
            _trace_request(prompt, _call_original, raw_headers, body_parsed)
        except Exception:
            pass
        finally:
            _inflight_release(_dk)

    return _wrapped_do_post


def _patch_handler_class(cls):
    if cls.__dict__.get("_wxo_patched"):
        return
    orig = cls.__dict__.get("do_POST")
    if orig:
        cls.do_POST = _make_do_post_wrapper(orig)
        cls._wxo_patched = True
        _LOG.info(f"do_POST patched on subclass: {cls.__module__}.{cls.__qualname__}")


def _patch_all_handler_subclasses():
    try:
        import http.server as _hs
        def _walk(klass):
            for sub in klass.__subclasses__():
                _patch_handler_class(sub)
                _walk(sub)
        _walk(_hs.BaseHTTPRequestHandler)
    except Exception as exc:
        _LOG.warning(f"subclass walk failed: {exc}")


def _patch_http_server():
    try:
        import http.server as _hs
        base = _hs.BaseHTTPRequestHandler
        if not getattr(base, "_wxo_patched", False):
            orig = base.__dict__.get("do_POST")
            if orig:
                base.do_POST = _make_do_post_wrapper(orig)
            else:
                def _stub(self): pass
                base.do_POST = _make_do_post_wrapper(_stub)
            base._wxo_patched = True
            _LOG.info("http.server.BaseHTTPRequestHandler.do_POST patched")
        _patch_all_handler_subclasses()
    except Exception as exc:
        _LOG.warning(f"http.server patch failed: {exc}")

# ---------------------------------------------------------------------------
# Starlette / FastAPI patch
# ---------------------------------------------------------------------------

# _WxoMiddleware is defined at module scope (populated lazily on first starlette
# import) so that the identity check in _install_starlette_middleware:
#   not any(getattr(m, "cls", None) is _WxoMiddleware for m in user_mw)
# reliably recognises an already-installed instance across repeated calls from
# _deferred_patch / _patch_existing_starlette_apps.
# Defining the class inside the function created a new class object each call,
# so the `is` check always failed, resulting in double (triple…) trace fires.
_WxoMiddleware = None
_wxo_mw_scope_active: set = set()   # process-wide scope dedup guard


def _get_wxo_middleware_class():
    """Return the singleton _WxoMiddleware class, creating it on first call."""
    global _WxoMiddleware
    if _WxoMiddleware is not None:
        return _WxoMiddleware

    try:
        from starlette.middleware.base import BaseHTTPMiddleware
        from starlette.requests import Request as _SR_Req

        class _WxoMiddlewareClass(BaseHTTPMiddleware):
            async def dispatch(self, request: _SR_Req, call_next):
                if request.method != "POST":
                    return await call_next(request)

                scope_key = id(request.scope)
                if scope_key in _wxo_mw_scope_active:
                    return await call_next(request)
                _wxo_mw_scope_active.add(scope_key)

                raw_headers = {k.lower(): v for k, v in request.headers.items()}
                body = await request.body()
                body_parsed: dict = {}
                prompt = ""; it = ot = 0
                try:
                    body_parsed = json.loads(body.decode("utf-8", errors="replace"))
                    if not isinstance(body_parsed, dict):
                        body_parsed = {}
                    prompt = _extract_prompt(body_parsed)
                except Exception:
                    prompt = body.decode("utf-8", errors="replace")[:300]

                # Skip internal tool-continuation re-entries from the agent framework
                if _PLATFORM == "azure_ai_foundry" and _is_tool_continuation(body_parsed):
                    _wxo_mw_scope_active.discard(scope_key)
                    return await call_next(request)

                # Claim this request process-wide — bail if another layer already owns it
                _inflight_key = _inflight_claim(body)
                if _inflight_key is None:
                    _wxo_mw_scope_active.discard(scope_key)
                    return await call_next(request)

                ctx = _resolve_tenant_context(raw_headers, body_parsed)
                if not ctx["export_url"]:
                    _inflight_release(_inflight_key)
                    _wxo_mw_scope_active.discard(scope_key)
                    return await call_next(request)

                # Resolve stable session_id before the response arrives.
                if _PLATFORM == "azure_ai_foundry":
                    ctx["session_id"] = _resolve_hosted_session(body_parsed, ctx)

                rsc = _RequestSpanContext(ctx)
                rsc.__enter__()
                start_ns = time.time_ns()
                is_error = False; error_msg = ""; resp_text = ""

                try:
                    response = await call_next(request)
                except Exception as exc:
                    is_error = True; error_msg = str(exc); end_ns = time.time_ns()
                    rsc.finish(is_error=True, error_msg=error_msg)
                    child_spans = rsc.get_child_spans(); rsc.shutdown()
                    if prompt:
                        _post_trace(prompt, "", start_ns, end_ns, ctx,
                                    is_error=True, error_msg=error_msg,
                                    trace_id=rsc.root_trace_id, span_id=rsc.root_span_id,
                                    child_spans=child_spans)
                    _inflight_release(_inflight_key)
                    _wxo_mw_scope_active.discard(scope_key)
                    raise

                end_ns = time.time_ns()
                content_type = response.headers.get("content-type", "")
                is_json = "application/json" in content_type
                is_sse  = "text/event-stream" in content_type
                is_streaming = is_sse or "stream" in content_type or response.status_code == 206

                if is_sse:
                    # Azure Foundry kind:hosted SSE path
                    try:
                        from starlette.responses import Response as _SR
                        resp_body = b""
                        async for chunk in response.body_iterator:
                            resp_body += chunk if isinstance(chunk, bytes) else chunk.encode()
                        response = _SR(content=resp_body, status_code=response.status_code,
                                       headers=dict(response.headers), media_type=response.media_type)
                        for line in resp_body.decode("utf-8", errors="replace").splitlines():
                            if not line.startswith("data:"):
                                continue
                            data_str = line[len("data:"):].strip()
                            if not data_str or data_str == "[DONE]":
                                continue
                            try:
                                evt = json.loads(data_str)
                            except Exception:
                                continue
                            # Capture agent_session_id from every event (first seen
                            # in response.created — before response.completed)
                            _update_session_from_sse(evt, ctx)
                            if evt.get("type") != "response.completed":
                                continue
                            full_resp = evt.get("response", {})
                            resp_text, it, ot = _extract_response_azure(full_resp)
                            if not prompt:
                                prompt = _extract_prompt_from_completed_azure(full_resp)
                            ctx["input_tokens"]  = it
                            ctx["output_tokens"] = ot
                            # Model: prefer response field; fall back to FOUNDRY_MODEL_NAME env var
                            if not ctx.get("model_name"):
                                ctx["model_name"] = (full_resp.get("model") or "").strip() or \
                                    os.environ.get("FOUNDRY_MODEL_NAME", "") or \
                                    os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME", "")
                            # Extract tool calls from response.completed output array
                            _resp_tools = _extract_tool_calls_from_responses_output(
                                full_resp.get("output", [])
                            )
                            if _resp_tools:
                                ctx.setdefault("tool_calls", [])
                                _ek = {(t.get("name"), str(t.get("input", ""))[:100])
                                       for t in ctx["tool_calls"]}
                                for _rt in _resp_tools:
                                    k = (_rt["name"], str(_rt.get("input", ""))[:100])
                                    if k not in _ek:
                                        ctx["tool_calls"].append(_rt)
                                        _ek.add(k)
                            # Register response id for conversation chaining (same-instance fallback)
                            _register_response_session(
                                full_resp.get("id", ""),
                                ctx.get("session_id", ""),
                            )
                            break
                    except Exception as exc:
                        _LOG.warning(f"SSE parse failed: {exc}")
                elif is_json and not is_streaming:
                    try:
                        from starlette.responses import Response as _SR
                        resp_body = b""
                        async for chunk in response.body_iterator:
                            resp_body += chunk if isinstance(chunk, bytes) else chunk.encode()
                        response = _SR(content=resp_body, status_code=response.status_code,
                                       headers=dict(response.headers), media_type=response.media_type)
                        parsed_resp = json.loads(resp_body.decode("utf-8", errors="replace"))
                        resp_text, it, ot = _extract_response_text(parsed_resp)
                        ctx["input_tokens"]  = it
                        ctx["output_tokens"] = ot
                        _body_tools = _extract_tool_calls_from_body(parsed_resp)
                        if _body_tools:
                            ctx.setdefault("tool_calls", [])
                            _ek = {(t.get("name"), str(t.get("input",""))[:100])
                                   for t in ctx["tool_calls"]}
                            for _bt in _body_tools:
                                k = (_bt["name"], str(_bt.get("input",""))[:100])
                                if k not in _ek:
                                    ctx["tool_calls"].append(_bt)
                                    _ek.add(k)
                    except Exception:
                        pass

                rsc.finish(is_error=is_error, error_msg=error_msg)
                child_spans = rsc.get_child_spans(); rsc.shutdown()
                if prompt or resp_text:
                    _post_trace(prompt, resp_text, start_ns, end_ns, ctx,
                                is_error=is_error, error_msg=error_msg,
                                trace_id=rsc.root_trace_id, span_id=rsc.root_span_id,
                                child_spans=child_spans)
                _inflight_release(_inflight_key)
                _wxo_mw_scope_active.discard(scope_key)
                return response

        _WxoMiddleware = _WxoMiddlewareClass
    except Exception:
        pass
    return _WxoMiddleware


def _install_starlette_middleware(app):
    try:
        mw_cls = _get_wxo_middleware_class()
        if mw_cls is None:
            return

        from starlette.middleware import Middleware as _Middleware
        entry = _Middleware(mw_cls)
        user_mw = getattr(app, "user_middleware", None)
        if user_mw is not None:
            if not any(getattr(m, "cls", None) is mw_cls for m in user_mw):
                user_mw.insert(0, entry)
                _LOG.info("WXO middleware injected via user_middleware")
            else:
                _LOG.debug("WXO middleware already present — skipping")
                return
            # On azure_ai_foundry, defer stack rebuild to avoid crashing ResponsesHostServer
            if _PLATFORM != "azure_ai_foundry":
                app.middleware_stack = app.build_middleware_stack()
        else:
            # Check if already added via add_middleware
            existing = getattr(app, "middleware_stack", None)
            if existing is not None and getattr(existing, "_wxo_installed", False):
                return
            app.add_middleware(mw_cls)
            if existing is not None:
                existing._wxo_installed = True
            _LOG.info("WXO middleware added via add_middleware")
    except Exception as exc:
        _LOG.warning(f"Starlette middleware install failed: {exc}")


def _patch_router_call():
    """Azure-specific: patch starlette.routing.Router.__call__ directly.
    This is the approach used by the original azure/sitecustomize.py and is
    safe to call during __init__ because it patches the class, not the instance
    middleware stack, so no build_middleware_stack() is needed.
    """
    try:
        import starlette.routing as _sr
        if getattr(_sr.Router, "_wxo_patched", False):
            return
        _orig_call = _sr.Router.__call__

        async def _wxo_router_call(self, scope, receive, send):
            if scope.get("type") != "http" or scope.get("method", "").upper() != "POST":
                return await _orig_call(self, scope, receive, send)
            # Buffer body for prompt extraction
            body_chunks = []
            async def _receive():
                msg = await receive()
                if msg.get("type") == "http.request":
                    body_chunks.append(msg.get("body", b""))
                return msg

            resp_chunks: list = []
            status_code = [200]
            resp_headers: list = []

            async def _send(msg):
                if msg["type"] == "http.response.start":
                    status_code[0] = msg.get("status", 200)
                    resp_headers.extend(msg.get("headers", []))
                elif msg["type"] == "http.response.body":
                    resp_chunks.append(msg.get("body", b""))
                await send(msg)

            start_ns = time.time_ns()
            raw_headers = {k.decode(errors="replace").lower(): v.decode(errors="replace")
                           for k, v in scope.get("headers", [])}
            try:
                await _orig_call(self, scope, _receive, _send)
            except Exception as exc:
                end_ns = time.time_ns()
                body = b"".join(body_chunks)
                try:
                    body_parsed = json.loads(body.decode("utf-8", errors="replace"))
                except Exception:
                    body_parsed = {}
                ctx = _resolve_tenant_context(raw_headers, body_parsed)
                prompt = _extract_prompt(body_parsed) if body_parsed else body.decode(errors="replace")[:300]
                _rk = _inflight_claim(body)
                if ctx["export_url"] and prompt and _rk is not None:
                    rsc = _RequestSpanContext(ctx)
                    rsc.__enter__()
                    rsc.finish(is_error=True, error_msg=str(exc))
                    child_spans = rsc.get_child_spans(); rsc.shutdown()
                    _post_trace(prompt, "", start_ns, end_ns, ctx,
                                is_error=True, error_msg=str(exc),
                                trace_id=rsc.root_trace_id, span_id=rsc.root_span_id,
                                child_spans=child_spans)
                _inflight_release(_rk)
                raise

            end_ns = time.time_ns()
            body = b"".join(body_chunks)
            resp_body = b"".join(resp_chunks)
            try:
                body_parsed = json.loads(body.decode("utf-8", errors="replace"))
            except Exception:
                body_parsed = {}
            # Skip internal tool-continuation re-entries from the agent framework
            if _PLATFORM == "azure_ai_foundry" and _is_tool_continuation(body_parsed):
                return
            _rk = _inflight_claim(body)
            if _rk is None:
                return
            ctx = _resolve_tenant_context(raw_headers, body_parsed)
            if not ctx["export_url"]:
                _inflight_release(_rk)
                return
            # Resolve stable session before processing response
            if _PLATFORM == "azure_ai_foundry":
                ctx["session_id"] = _resolve_hosted_session(body_parsed, ctx)
            rsc = _RequestSpanContext(ctx)
            rsc.__enter__()
            prompt = _extract_prompt(body_parsed) if body_parsed else body.decode(errors="replace")[:300]
            resp_text = ""; it = ot = 0
            try:
                # Check for SSE (response.completed event)
                resp_str = resp_body.decode("utf-8", errors="replace")
                if "response.completed" in resp_str:
                    for line in resp_str.splitlines():
                        if not line.startswith("data:"):
                            continue
                        try:
                            evt = json.loads(line[len("data:"):].strip())
                        except Exception:
                            continue
                        # Capture agent_session_id from every event
                        _update_session_from_sse(evt, ctx)
                        if evt.get("type") == "response.completed":
                            full_resp = evt.get("response", {})
                            resp_text, it, ot = _extract_response_azure(full_resp)
                            if not prompt:
                                prompt = _extract_prompt_from_completed_azure(full_resp)
                            # Model: response field (may be empty) → FOUNDRY_MODEL_NAME env var
                            if not ctx.get("model_name"):
                                ctx["model_name"] = (full_resp.get("model") or "").strip() or \
                                    os.environ.get("FOUNDRY_MODEL_NAME", "") or \
                                    os.environ.get("AZURE_AI_MODEL_DEPLOYMENT_NAME", "")
                            # Extract tool calls from response.completed output array
                            _resp_tools = _extract_tool_calls_from_responses_output(
                                full_resp.get("output", [])
                            )
                            if _resp_tools:
                                ctx.setdefault("tool_calls", [])
                                _ek = {(t.get("name"), str(t.get("input", ""))[:100])
                                       for t in ctx["tool_calls"]}
                                for _rt in _resp_tools:
                                    k = (_rt["name"], str(_rt.get("input", ""))[:100])
                                    if k not in _ek:
                                        ctx["tool_calls"].append(_rt)
                                        _ek.add(k)
                            _register_response_session(
                                full_resp.get("id", ""),
                                ctx.get("session_id", ""),
                            )
                            break
                else:
                    parsed_resp = json.loads(resp_body.decode("utf-8", errors="replace")) if resp_body else {}
                    resp_text, it, ot = _extract_response_text(parsed_resp)
                    # Extract tool calls from JSON response body
                    _body_tools = _extract_tool_calls_from_body(parsed_resp)
                    if _body_tools:
                        ctx.setdefault("tool_calls", [])
                        _ek = {(t.get("name"), str(t.get("input",""))[:100])
                               for t in ctx["tool_calls"]}
                        for _bt in _body_tools:
                            k = (_bt["name"], str(_bt.get("input",""))[:100])
                            if k not in _ek:
                                ctx["tool_calls"].append(_bt)
                                _ek.add(k)
                ctx["input_tokens"] = it
                ctx["output_tokens"] = ot
            except Exception:
                pass
            rsc.finish(is_error=False)
            child_spans = rsc.get_child_spans(); rsc.shutdown()
            if prompt or resp_text:
                _post_trace(prompt, resp_text, start_ns, end_ns, ctx,
                            trace_id=rsc.root_trace_id, span_id=rsc.root_span_id,
                            child_spans=child_spans)
            _inflight_release(_rk)

        _sr.Router.__call__ = _wxo_router_call
        _sr.Router._wxo_patched = True
        _LOG.info("starlette.routing.Router.__call__ patched (azure)")
    except ImportError:
        pass
    except Exception as exc:
        _LOG.warning(f"Router.__call__ patch failed: {exc}")


def _patch_starlette():
    try:
        import starlette.applications as _sa
        _orig_init = _sa.Starlette.__init__
        def _patched_init(self, *args, **kwargs):
            _orig_init(self, *args, **kwargs)
            _install_starlette_middleware(self)
            self._wxo_mw_installed = True
        _sa.Starlette.__init__ = _patched_init
        _LOG.info("Starlette.__init__ patched")
    except ImportError:
        pass
    except Exception as exc:
        _LOG.warning(f"Starlette patch failed: {exc}")


def _patch_existing_starlette_apps():
    try:
        import starlette.applications as _sa, gc
        for obj in gc.get_objects():
            try:
                if isinstance(obj, _sa.Starlette) and not getattr(obj, "_wxo_mw_installed", False):
                    _install_starlette_middleware(obj)
                    obj._wxo_mw_installed = True
            except Exception:
                pass
    except ImportError:
        pass
    except Exception as exc:
        _LOG.warning(f"Starlette app walk failed: {exc}")


# Azure: also patch starlette.routing.Router.__call__ directly (for ResponsesHostServer)
class _StarlettePatchImportHook:
    def find_module(self, fullname, path=None):
        return self if fullname == "starlette.applications" else None

    def load_module(self, fullname):
        import importlib
        if self in sys.meta_path:
            sys.meta_path.remove(self)
        mod = importlib.import_module(fullname)
        _patch_starlette()
        return mod

# ---------------------------------------------------------------------------
# Flask / generic WSGI patch
# ---------------------------------------------------------------------------

def _make_wsgi_wrapper(orig_fn, is_method=False):
    """Build a WSGI wrapper around orig_fn(environ, start_response) or self.orig(environ,...)."""
    def _call(environ, start_response, self_=None):
        if environ.get("REQUEST_METHOD") != "POST":
            return orig_fn(self_, environ, start_response) if is_method else orig_fn(environ, start_response)
        import io as _io
        start_ns = time.time_ns()
        try:
            cl = int(environ.get("CONTENT_LENGTH") or 0)
            body_bytes = (environ.get("wsgi.input") or _io.BytesIO()).read(cl) if cl else b""
            environ["wsgi.input"] = _io.BytesIO(body_bytes)
        except Exception:
            body_bytes = b""
        if b'"resourceSpans"' in body_bytes[:64] or b'"apikey"' in body_bytes[:64]:
            return orig_fn(self_, environ, start_response) if is_method else orig_fn(environ, start_response)
        # Claim this request — skip if another layer already owns it
        _wk = _inflight_claim(body_bytes)
        if _wk is None:
            return orig_fn(self_, environ, start_response) if is_method else orig_fn(environ, start_response)
        raw_headers = {k[5:].lower().replace("_", "-"): v for k, v in environ.items() if k.startswith("HTTP_")}
        body_parsed: dict = {}
        prompt = ""
        try:
            body_parsed = json.loads(body_bytes.decode("utf-8", errors="replace"))
            if not isinstance(body_parsed, dict):
                body_parsed = {}
            prompt = _extract_prompt(body_parsed)
        except Exception:
            prompt = body_bytes.decode("utf-8", errors="replace")[:500]
        captured = []
        def _sniff(status, headers, exc_info=None):
            return start_response(status, headers, exc_info) if exc_info else start_response(status, headers)
        is_error = False; error_msg = ""

        def _call_orig(rsc):
            s = time.time_ns(); is_e = False; err = ""
            try:
                it = orig_fn(self_, environ, _sniff) if is_method else orig_fn(environ, _sniff)
                for chunk in it:
                    captured.append(chunk); yield chunk
                if hasattr(it, "close"): it.close()
            except Exception as exc:
                is_e = True; err = str(exc); raise
            finally:
                end = time.time_ns()
                rt = ""; ii = oo = 0
                try:
                    raw = b"".join(captured).decode("utf-8", errors="replace")
                    parsed_resp = json.loads(raw)
                    rt, ii, oo = _extract_response_text(parsed_resp)
                    # Extract tool calls from the WSGI response body
                    _body_tools = _extract_tool_calls_from_body(parsed_resp)
                    if _body_tools:
                        rsc._ctx.setdefault("tool_calls", [])
                        _ek = {(t.get("name"), str(t.get("input",""))[:100])
                               for t in rsc._ctx["tool_calls"]}
                        for _bt in _body_tools:
                            k = (_bt["name"], str(_bt.get("input",""))[:100])
                            if k not in _ek:
                                rsc._ctx["tool_calls"].append(_bt)
                                _ek.add(k)
                except Exception:
                    pass
                # yield from trick not available in finally — return tuple
                rsc._wsgi_result = (rt, is_e, err, s, end)
                rsc._wsgi_tokens = (ii, oo)

        # WSGI generators can't use yield inside finally; use a helper generator
        def _outer_gen(rsc):
            gen = _call_orig(rsc)
            try:
                yield from gen
            finally:
                rt, is_e, err, s, end = getattr(rsc, "_wsgi_result", ("", False, "", start_ns, time.time_ns()))
                ii, oo = getattr(rsc, "_wsgi_tokens", (0, 0))
                rsc._ctx["input_tokens"]  = ii
                rsc._ctx["output_tokens"] = oo
                rsc.finish(is_error=is_e, error_msg=err)
                cs = rsc.get_child_spans(); rsc.shutdown()
                if prompt or rt:
                    _post_trace(prompt, rt, s, end, rsc._ctx,
                                is_error=is_e, error_msg=err,
                                trace_id=rsc.root_trace_id, span_id=rsc.root_span_id,
                                child_spans=cs)
                _inflight_release(_wk)

        ctx = _resolve_tenant_context(raw_headers, body_parsed)
        if not ctx["export_url"]:
            _inflight_release(_wk)
            return orig_fn(self_, environ, start_response) if is_method else orig_fn(environ, start_response)
        rsc = _RequestSpanContext(ctx)
        rsc._ctx = ctx
        rsc.__enter__()
        return _outer_gen(rsc)

    if is_method:
        def _method_wrapper(self_, environ, start_response):
            return _call(environ, start_response, self_=self_)
        return _method_wrapper
    return _call


def _patch_flask():
    try:
        import flask as _flask
        if getattr(_flask.Flask, "_wxo_wsgi_patched", False):
            return
        _orig = _flask.Flask.wsgi_app
        _flask.Flask.wsgi_app = _make_wsgi_wrapper(_orig, is_method=True)
        _flask.Flask._wxo_wsgi_patched = True
        _LOG.info("Flask.wsgi_app patched")
    except ImportError:
        pass
    except Exception as exc:
        _LOG.warning(f"Flask patch failed: {exc}")


def _patch_wsgi_callable():
    try:
        import starlette.applications as _sa
        _flask_type = None
        try:
            import flask as _fl; _flask_type = _fl.Flask
        except ImportError:
            pass
        main = sys.modules.get("__main__")
        if main is None:
            return
        for attr in ("app", "application", "wsgi_app", "create_app"):
            obj = getattr(main, attr, None)
            if obj is None:
                continue
            if callable(obj) and not isinstance(obj, _sa.Starlette):
                if _flask_type and isinstance(obj, _flask_type):
                    continue
                if getattr(obj, "_wxo_wsgi_patched", False):
                    continue
                orig = obj.__call__
                obj.__call__ = _make_wsgi_wrapper(orig)
                obj._wxo_wsgi_patched = True
                _LOG.info(f"Generic WSGI app '{attr}' patched")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Django patch
# ---------------------------------------------------------------------------

def _patch_django():
    try:
        import django.core.handlers.wsgi as _dw
        if getattr(_dw.WSGIHandler, "_wxo_patched", False):
            return
        _orig = _dw.WSGIHandler.__call__
        _dw.WSGIHandler.__call__ = _make_wsgi_wrapper(_orig, is_method=True)
        _dw.WSGIHandler._wxo_patched = True
        _LOG.info("Django WSGIHandler.__call__ patched")
    except ImportError:
        pass
    except Exception as exc:
        _LOG.warning(f"Django patch failed: {exc}")

# ---------------------------------------------------------------------------
# Tornado patch
# ---------------------------------------------------------------------------

def _patch_tornado():
    try:
        import tornado.web as _tw
        if getattr(_tw.RequestHandler, "_wxo_patched", False):
            return

        _orig_write = _tw.RequestHandler.write
        def _patched_write(self, chunk):
            if not hasattr(self, "_wxo_captured_chunks"):
                self._wxo_captured_chunks = []
            if chunk:
                if isinstance(chunk, bytes):
                    self._wxo_captured_chunks.append(chunk)
                elif isinstance(chunk, str):
                    self._wxo_captured_chunks.append(chunk.encode("utf-8", errors="replace"))
                elif isinstance(chunk, dict):
                    self._wxo_captured_chunks.append(json.dumps(chunk).encode("utf-8", errors="replace"))
            return _orig_write(self, chunk)

        _orig_execute = _tw.RequestHandler._execute

        async def _patched_execute(self, transforms, *args, **kwargs):
            request = self.request
            if getattr(request, "method", "").upper() != "POST":
                return await _orig_execute(self, transforms, *args, **kwargs)

            body_bytes = getattr(request, "body", b"") or b""
            if b'"resourceSpans"' in body_bytes[:64] or b'"apikey"' in body_bytes[:64]:
                return await _orig_execute(self, transforms, *args, **kwargs)

            req_headers = getattr(request, "headers", {})
            raw_headers: dict = {}
            try:
                raw_headers = {k.lower(): v for k, v in dict(req_headers).items()}
            except Exception:
                pass

            body_parsed: dict = {}
            prompt = ""
            try:
                body_parsed = json.loads(body_bytes.decode("utf-8", errors="replace"))
                if not isinstance(body_parsed, dict):
                    body_parsed = {}
                prompt = _extract_prompt(body_parsed)
            except Exception:
                prompt = body_bytes.decode("utf-8", errors="replace")[:500]

            ctx = _resolve_tenant_context(raw_headers, body_parsed)
            if not ctx["export_url"]:
                return await _orig_execute(self, transforms, *args, **kwargs)

            rsc = _RequestSpanContext(ctx)
            rsc.__enter__()
            start_ns = time.time_ns()
            self._wxo_captured_chunks = []
            is_error = False
            error_msg = ""

            try:
                await _orig_execute(self, transforms, *args, **kwargs)
            except Exception as exc:
                is_error = True
                error_msg = str(exc)
                raise
            finally:
                end_ns = time.time_ns()
                rt = ""
                it = ot = 0
                try:
                    captured = getattr(self, "_wxo_captured_chunks", [])
                    raw = b"".join(captured).decode("utf-8", errors="replace")
                    parsed_resp = json.loads(raw)
                    rt, it, ot = _extract_response_text(parsed_resp)
                    _apply_response_meta(ctx, parsed_resp, it, ot)

                    # Extract tool calls from response body
                    _body_tools = _extract_tool_calls_from_body(parsed_resp)
                    if _body_tools:
                        ctx.setdefault("tool_calls", [])
                        _existing = {(t.get("name"), str(t.get("input",""))[:100])
                                     for t in ctx["tool_calls"]}
                        for _bt in _body_tools:
                            k = (_bt["name"], str(_bt.get("input",""))[:100])
                            if k not in _existing:
                                ctx["tool_calls"].append(_bt)
                                _existing.add(k)
                except Exception:
                    pass

                ctx["input_tokens"] = it
                ctx["output_tokens"] = ot
                rsc.finish(is_error=is_error, error_msg=error_msg)
                cs = rsc.get_child_spans()
                rsc.shutdown()
                if prompt or rt:
                    _post_trace(prompt, rt, start_ns, end_ns, ctx,
                                is_error=is_error, error_msg=error_msg,
                                trace_id=rsc.root_trace_id, span_id=rsc.root_span_id, child_spans=cs)

        _tw.RequestHandler.write = _patched_write
        _tw.RequestHandler._execute = _patched_execute
        _tw.RequestHandler._wxo_patched = True
        _LOG.info("tornado.web.RequestHandler patched for tracing")
    except ImportError:
        pass
    except Exception as exc:
        _LOG.warning(f"Tornado patch failed: {exc}")

# ---------------------------------------------------------------------------
# aiohttp patch
# ---------------------------------------------------------------------------

def _patch_aiohttp():
    try:
        import aiohttp.web as _aw
        if getattr(_aw.Application, "_wxo_patched", False):
            return

        # Must use @_aw.middleware decorator so aiohttp registers it correctly.
        # Without it aiohttp 3.x calls the coroutine with (app, handler) during
        # setup instead of (request, handler) at request time → AttributeError.
        @_aw.middleware
        async def _wxo_middleware(request: "_aw.Request", handler):
            if request.method != "POST":
                return await handler(request)
            raw_headers = {k.lower(): v for k, v in request.headers.items()}
            try:
                body_bytes = await request.read()
            except Exception:
                body_bytes = b""
            if b'"resourceSpans"' in body_bytes[:64] or b'"apikey"' in body_bytes[:64]:
                return await handler(request)
            body_parsed: dict = {}
            prompt = ""
            try:
                body_parsed = json.loads(body_bytes.decode("utf-8", errors="replace"))
                if not isinstance(body_parsed, dict):
                    body_parsed = {}
                prompt = _extract_prompt(body_parsed)
            except Exception:
                prompt = body_bytes.decode("utf-8", errors="replace")[:500]
            ctx = _resolve_tenant_context(raw_headers, body_parsed)
            if not ctx["export_url"]:
                return await handler(request)
            rsc = _RequestSpanContext(ctx); rsc.__enter__()
            start_ns = time.time_ns(); is_error = False; error_msg = ""
            try:
                response = await handler(request)
            except Exception as exc:
                is_error = True; error_msg = str(exc); end_ns = time.time_ns()
                rsc.finish(is_error=True, error_msg=error_msg)
                cs = rsc.get_child_spans(); rsc.shutdown()
                if prompt:
                    _post_trace(prompt, "", start_ns, end_ns, ctx,
                                is_error=True, error_msg=error_msg,
                                trace_id=rsc.root_trace_id, span_id=rsc.root_span_id, child_spans=cs)
                raise
            end_ns = time.time_ns(); it = ot = 0; resp_text = ""
            if "application/json" in (response.content_type or ""):
                try:
                    rb = response.body or b""
                    parsed_resp = json.loads(rb.decode("utf-8", errors="replace"))
                    resp_text, it, ot = _extract_response_text(parsed_resp)
                    _apply_response_meta(ctx, parsed_resp, it, ot)
                    _body_tools = _extract_tool_calls_from_body(parsed_resp)
                    if _body_tools:
                        ctx.setdefault("tool_calls", [])
                        _existing = {(t.get("name"), str(t.get("input",""))[:100])
                                     for t in ctx["tool_calls"]}
                        for _bt in _body_tools:
                            k = (_bt["name"], str(_bt.get("input",""))[:100])
                            if k not in _existing:
                                ctx["tool_calls"].append(_bt)
                                _existing.add(k)
                except Exception:
                    pass
            ctx["input_tokens"] = it; ctx["output_tokens"] = ot
            rsc.finish(is_error=is_error, error_msg=error_msg)
            cs = rsc.get_child_spans(); rsc.shutdown()
            if prompt or resp_text:
                _post_trace(prompt, resp_text, start_ns, end_ns, ctx,
                            is_error=is_error, error_msg=error_msg,
                            trace_id=rsc.root_trace_id, span_id=rsc.root_span_id, child_spans=cs)
            return response

        _wxo_middleware._wxo_middleware = True
        _orig_init = _aw.Application.__init__
        def _patched_init(self, *args, **kwargs):
            mw = list(kwargs.pop("middlewares", []) or [])
            if not any(getattr(m, "_wxo_middleware", False) for m in mw):
                mw.insert(0, _wxo_middleware)
            kwargs["middlewares"] = mw
            _orig_init(self, *args, **kwargs)
        _aw.Application.__init__ = _patched_init
        _aw.Application._wxo_patched = True
        _LOG.info("aiohttp.web.Application.__init__ patched")
    except ImportError:
        pass
    except Exception as exc:
        _LOG.warning(f"aiohttp patch failed: {exc}")

# ---------------------------------------------------------------------------
# gRPC patch — all four call types
# ---------------------------------------------------------------------------

def _grpc_extract(obj) -> str:
    if obj is None: return ""
    if isinstance(obj, str): return obj
    if isinstance(obj, (bytes, bytearray)):
        return obj.decode("utf-8", errors="replace")[:500]
    for field in ("text", "message", "content", "input", "output",
                  "query", "answer", "response", "prompt", "result"):
        val = getattr(obj, field, None)
        if val and isinstance(val, str):
            return val
    try:
        from google.protobuf import json_format as _jf
        return _jf.MessageToJson(obj)[:500]
    except Exception:
        pass
    try:
        return json.dumps(dict(obj))[:500]
    except Exception:
        return str(obj)[:500]


def _patch_grpc():
    try:
        import grpc as _grpc
        if getattr(_grpc, "_wxo_server_patched", False):
            return
        _orig_server = _grpc.server

        class _WxoInterceptor(_grpc.ServerInterceptor):
            def intercept_service(self, continuation, handler_call_details):
                orig_handler = continuation(handler_call_details)
                if orig_handler is None:
                    return orig_handler

                def _meta_ctx(context):
                    try:
                        hdrs = {k: v for k, v in (context.invocation_metadata() or [])}
                    except Exception:
                        hdrs = {}
                    return _resolve_tenant_context(hdrs, {})

                def _post(p, r, s, e, ctx, is_err=False, err=""):
                    if ctx["export_url"]:
                        import secrets as _sec_grpc
                        _post_trace(p, r, s, e, ctx, is_error=is_err, error_msg=err,
                                    trace_id=uuid.uuid4().hex,
                                    span_id=_sec_grpc.token_hex(8))

                def _wrap_uu(fn):
                    def _w(req, ctx_grpc):
                        s = time.time_ns(); is_e = False; err = ""; resp = None
                        c = _meta_ctx(ctx_grpc)
                        try:
                            resp = fn(req, ctx_grpc); return resp
                        except Exception as exc:
                            is_e = True; err = str(exc); raise
                        finally:
                            _post(_grpc_extract(req), _grpc_extract(resp) if resp is not None else "",
                                  s, time.time_ns(), c, is_e, err)
                    return _w

                def _wrap_us(fn):
                    def _w(req, ctx_grpc):
                        s = time.time_ns(); is_e = False; err = ""; chunks = []
                        c = _meta_ctx(ctx_grpc)
                        try:
                            for item in fn(req, ctx_grpc):
                                chunks.append(_grpc_extract(item)); yield item
                        except Exception as exc:
                            is_e = True; err = str(exc); raise
                        finally:
                            _post(_grpc_extract(req), " ".join(chunks)[:500],
                                  s, time.time_ns(), c, is_e, err)
                    return _w

                def _wrap_su(fn):
                    def _w(req_iter, ctx_grpc):
                        s = time.time_ns(); is_e = False; err = ""; req_c = []; resp = None
                        c = _meta_ctx(ctx_grpc)
                        def _sniff():
                            for item in req_iter:
                                req_c.append(_grpc_extract(item)); yield item
                        try:
                            resp = fn(_sniff(), ctx_grpc); return resp
                        except Exception as exc:
                            is_e = True; err = str(exc); raise
                        finally:
                            _post(" ".join(req_c)[:500], _grpc_extract(resp) if resp is not None else "",
                                  s, time.time_ns(), c, is_e, err)
                    return _w

                def _wrap_ss(fn):
                    def _w(req_iter, ctx_grpc):
                        s = time.time_ns(); is_e = False; err = ""; req_c = []; resp_c = []
                        c = _meta_ctx(ctx_grpc)
                        def _sniff():
                            for item in req_iter:
                                req_c.append(_grpc_extract(item)); yield item
                        try:
                            for item in fn(_sniff(), ctx_grpc):
                                resp_c.append(_grpc_extract(item)); yield item
                        except Exception as exc:
                            is_e = True; err = str(exc); raise
                        finally:
                            _post(" ".join(req_c)[:500], " ".join(resp_c)[:500],
                                  s, time.time_ns(), c, is_e, err)
                    return _w

                kw = dict(request_deserializer=orig_handler.request_deserializer,
                          response_serializer=orig_handler.response_serializer)
                if orig_handler.unary_unary:
                    return _grpc.unary_unary_rpc_method_handler(_wrap_uu(orig_handler.unary_unary), **kw)
                if orig_handler.unary_stream:
                    return _grpc.unary_stream_rpc_method_handler(_wrap_us(orig_handler.unary_stream), **kw)
                if orig_handler.stream_unary:
                    return _grpc.stream_unary_rpc_method_handler(_wrap_su(orig_handler.stream_unary), **kw)
                if orig_handler.stream_stream:
                    return _grpc.stream_stream_rpc_method_handler(_wrap_ss(orig_handler.stream_stream), **kw)
                return orig_handler

        def _patched_server(*args, **kwargs):
            existing = list(kwargs.get("interceptors") or [])
            if not any(isinstance(i, _WxoInterceptor) for i in existing):
                existing.append(_WxoInterceptor())
            kwargs["interceptors"] = existing
            return _orig_server(*args, **kwargs)

        _grpc.server = _patched_server
        _grpc._wxo_server_patched = True
        # Signal to _make_do_post_wrapper that gRPC owns tracing for this process.
        global _GRPC_INTERCEPTOR_ACTIVE
        _GRPC_INTERCEPTOR_ACTIVE = True
        _LOG.info("grpc.server() patched — WxoInterceptor injected (unary+streaming)")
    except ImportError:
        pass
    except Exception as exc:
        _LOG.warning(f"gRPC patch failed: {exc}")

# ---------------------------------------------------------------------------
# Deferred background sweep — catches apps constructed after startup
# ---------------------------------------------------------------------------

def _deferred_patch():
    import time as _t
    _t.sleep(0.5)
    for _ in range(15):
        # On Azure, only sweep for new Starlette app instances — never run
        # WSGI / http.server / framework patches that cause a second trace.
        _patch_existing_starlette_apps()
        if _PLATFORM != "azure_ai_foundry":
            _patch_all_handler_subclasses()
            _patch_wsgi_callable()
            _patch_django()
            _patch_tornado()
            _patch_aiohttp()
        _t.sleep(2)

# ---------------------------------------------------------------------------
# Boot — runs at Python startup via sitecustomize
# ---------------------------------------------------------------------------

if _ACTIVE:
    _LOG.info(
        f"WXO hook active | mode={_DEPLOYMENT_MODE!r} platform={_PLATFORM!r} agent={_AGENT_NAME!r} "
        f"tenant={_TENANT_ID[:8] + '...' if _TENANT_ID else '(unset)'!r} "
        f"env={_ENVIRONMENT!r} otel={'yes' if _otel_available else 'no'}"
    )
    if _PLATFORM == "azure_ai_foundry":
        # Azure kind:hosted agents run on ResponsesHostServer (Starlette/ASGI).
        # Only the Starlette middleware path is needed — all http.server / WSGI /
        # Flask / Django / Tornado / aiohttp patches must NOT run: they would wrap
        # the same request a second time producing a duplicate trace with a
        # different (UUID-based) conversation ID alongside the real one.
        _patch_starlette()
        sys.meta_path.insert(0, _StarlettePatchImportHook())
        _LOG.info("Azure: Starlette middleware + import hook installed (other patches skipped)")
        threading.Thread(target=_deferred_patch, daemon=True, name="wxo-deferred-patch").start()
    else:
        _patch_http_server()
        _patch_flask()
        _patch_django()
        _patch_tornado()
        _patch_aiohttp()
        _patch_grpc()
        threading.Thread(target=_deferred_patch, daemon=True, name="wxo-deferred-patch").start()
        _patch_starlette()
else:
    _LOG.info("WXO hook loaded but disabled (WXO_OTEL_EXPORT_URL not set)")

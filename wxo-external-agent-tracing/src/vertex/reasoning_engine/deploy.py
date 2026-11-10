#!/usr/bin/env python3
"""
deploy.py
──────────
Patches ANY existing Vertex AI Reasoning Engine with WXO tracing by
reading the existing package-based agent pickle, wrapping that exact agent
instance in WxoTracingWrapper, uploading a new pickle, and patching the
existing engine to use it. No new engine is created and no AGENT_CLASS is used.

Required env vars
─────────────────
  REASONING_ENGINE_ID   existing engine resource ID
  WXO_OTEL_EXPORT_URL   WXO OTLP ingest endpoint
  WXO_TENANT_ID         IBM tenant ID
  WXO_API_KEY           IBM API key (used to fetch bearer token)
  WXO_TOKEN_URL         IBM IAM token endpoint
  WXO_AGENT_ID          agent ID shown in WXO traces
  WXO_AGENT_NAME        display name shown in WXO traces
  WXO_ENVIRONMENT_NAME  e.g. "production" or "draft"

Optional
─────────
  GOOGLE_APPLICATION_CREDENTIALS  base64-encoded GCP service-account JSON (or path)
  GCP_PROJECT_ID / GCP_REGION     default: env / us-central1

Usage
─────
    source ../../../config/shared.env
    source ../../../config/vertex.env
    export REASONING_ENGINE_ID="<existing engine id>"
    python3 reasoning_engine/deploy.py

How it works
────────────
• The existing package pickle is downloaded and deserialized.
• WxoTracingWrapper is cloudpickled around that actual existing agent.
• The new pickle is uploaded and only packageSpec.pickleObjectGcsUri is updated.
• On every query() call in the RE container the wrapper:
    1. forwards the call to the inner agent unchanged
    2. captures start/end timestamps, token counts, tool_calls from the response
    3. posts an OTLP trace to WXO_OTEL_EXPORT_URL via _post_trace()
• _post_trace() uses a thread-safe TTL cache for the IBM IAM bearer token
  and retries the POST up to 3 times with exponential backoff.
• Child spans: invoke_agent → call_llm → generate_content → TOOL/CHAIN
• All imports inside instance methods — safe across Python version mismatches
  when cloudpickle restores the object on the RE container.
"""

from __future__ import annotations

import base64
import json
import os
import re
import ssl
import sys
import threading
import time
import uuid
from urllib.request import Request, urlopen


# ── Deploy-time GCP config ────────────────────────────────────────────────────
SA_KEY_RAW         = (os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
                      or os.environ.get("GCP_SERVICE_ACCOUNT_BASE64")
                      or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")).strip()
GCP_PROJECT        = os.environ.get("GCP_PROJECT_ID", "")
GCP_REGION         = os.environ.get("GCP_REGION", "us-central1")
STAGING_BUCKET     = f"gs://{GCP_PROJECT}-agent-staging" if GCP_PROJECT else ""
REASONING_ENGINE_ID = os.environ.get("REASONING_ENGINE_ID", "")


# ══════════════════════════════════════════════════════════════════════════════
# Module-level WXO config globals
# Mirrors AWS sitecustomize.py: all helpers use these directly rather than
# accepting them as parameters — keeps call sites clean and matches the pattern.
#
# Env-var names use the WXO_* prefix consistently (same as AWS).
# Bare names (TENANT_ID, API_KEY, …) are accepted as fallbacks for
# backward compatibility with older config.env files.
# ══════════════════════════════════════════════════════════════════════════════

def _extract_tenant_id(url: str) -> str:
    if url:
        m = re.search(r'/instances/([^/?#]+)', url)
        if m:
            return m.group(1).strip()
    return ""

_AGENT_ID    = os.environ.get("WXO_AGENT_ID",          "")
_AGENT_NAME  = os.environ.get("WXO_AGENT_NAME",        "vertex_agent")
_API_KEY     = (os.environ.get("WXO_API_KEY")           or os.environ.get("API_KEY",     ""))
_TOKEN_URL   = (os.environ.get("WXO_TOKEN_URL")         or os.environ.get("TOKEN_URL",   ""))
_MODE        = "cpd" if os.environ.get("WXO_DEPLOYMENT_MODE", "cloud").strip().lower() == "cpd" else "cloud"
_CPD_HOST    = os.environ.get("CPD_HOST_URL", "").rstrip("/")
_CPD_USER    = os.environ.get("CPD_USERNAME", "")
_CPD_PASS    = os.environ.get("CPD_PASSWORD", "")
_CPD_IID     = os.environ.get("CPD_INSTANCE_ID", "")
_CPD_NS      = os.environ.get("CPD_NAMESPACE", "")
_CPD_VERIFY  = os.environ.get("CPD_VERIFY_TLS", "false")
_EXPORT_URL  = (os.environ.get("WXO_OTEL_EXPORT_URL")   or os.environ.get("OTEL_EXPORT_URL", ""))
if _MODE == "cpd":
    # CPD: no tenant header / API key. Export URL is derived from CPD_* unless overridden.
    _TENANT_ID = ""
    _EXPORT_URL = (os.environ.get("CPD_EXPORT_URL") or _EXPORT_URL
                   or (f"{_CPD_HOST}/{_CPD_NS}/instances/{_CPD_IID}/v1/agentops-v3/traces"
                       if _CPD_HOST and _CPD_NS and _CPD_IID else ""))
else:
    _TENANT_ID = _extract_tenant_id(_EXPORT_URL) or (os.environ.get("WXO_TENANT_ID") or os.environ.get("TENANT_ID", ""))
_ENVIRONMENT = (os.environ.get("WXO_ENVIRONMENT_NAME")  or os.environ.get("ENVIRONMENT_NAME", "draft"))
_GCP_PROJECT = GCP_PROJECT
_GCP_REGION  = GCP_REGION


# ══════════════════════════════════════════════════════════════════════════════
# Helpers — all cloudpickled into the agent; stdlib only, no extra runtime deps
# ══════════════════════════════════════════════════════════════════════════════

# ── Token counting (regex estimator — fallback when API gives no counts) ──────
# NOTE: _TOKEN_PAT is intentionally NOT a module-level compiled regex.
# Compiled re.Pattern objects are not safely portable across Python versions
# (deploy machine may be 3.14, Reasoning Engine container runs 3.12).
# The pattern is compiled lazily inside the function on first call instead.
_TOKEN_PAT_HOLDER: list = []   # holds [compiled_pattern] after first call

def _count_tokens(text: str) -> int:
    """Regex token estimator — compiles pattern lazily to avoid pickle version mismatch."""
    import re as _re
    if not _TOKEN_PAT_HOLDER:
        _TOKEN_PAT_HOLDER.append(_re.compile(
            r"(?i:'s|'t|'re|'ve|'m|'ll|'d)|[^\W\d_]+|\d{1,3}|[^\w\s]+", _re.UNICODE
        ))
    return len(_TOKEN_PAT_HOLDER[0].findall(text)) if text else 0


# ── Bearer token cache ────────────────────────────────────────────────────────
# _TOKEN_CACHE is a plain dict — picklable.
# _TOKEN_LOCK is NOT stored at module level because threading.Lock is a C-level
# object that cloudpickle cannot serialise. Instead, the lock is created lazily
# inside _get_bearer_token() on first call inside the Reasoning Engine container.
_TOKEN_CACHE: dict = {}
_TOKEN_LOCK_HOLDER: list = []   # holds [lock] after first call; picklable when empty


def _runtime_mode() -> str:
    """'cpd' or 'cloud' — read from the Reasoning Engine env at runtime, then the frozen global."""
    import os as _os
    m = (_os.environ.get("WXO_DEPLOYMENT_MODE") or _MODE or "cloud").strip().lower()
    return "cpd" if m == "cpd" else "cloud"


def _wxo_ssl_context():
    """CPD uses self-signed certs → skip verification unless CPD_VERIFY_TLS=true."""
    import os as _os, ssl as _s
    ctx = _s.create_default_context()
    if _runtime_mode() == "cpd" and (_os.environ.get("CPD_VERIFY_TLS") or _CPD_VERIFY).strip().lower() != "true":
        ctx.check_hostname = False
        ctx.verify_mode = _s.CERT_NONE
    return ctx


def _get_cpd_bearer_token() -> str:
    """POST username/password to <CPD_HOST_URL>/icp4d-api/v1/authorize (token cached 12h)."""
    import time as _t, json as _j, threading as _th, os as _os
    from urllib.request import Request as _R, urlopen as _u

    if not _TOKEN_LOCK_HOLDER:
        _TOKEN_LOCK_HOLDER.append(_th.Lock())
    _lock = _TOKEN_LOCK_HOLDER[0]

    host = (_os.environ.get("CPD_HOST_URL") or _CPD_HOST).rstrip("/")
    user = _os.environ.get("CPD_USERNAME") or _CPD_USER
    pw   = _os.environ.get("CPD_PASSWORD") or _CPD_PASS
    if not (host and user and pw):
        print("[wxo_vertex_hook] CPD_HOST_URL / CPD_USERNAME / CPD_PASSWORD not set")
        return ""

    now = _t.time()
    with _lock:
        if _TOKEN_CACHE.get("token") and now < _TOKEN_CACHE.get("expires_at", 0):
            return _TOKEN_CACHE["token"]

    req = _R(
        host + "/icp4d-api/v1/authorize",
        data=_j.dumps({"username": user, "password": pw}).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with _u(req, timeout=30, context=_wxo_ssl_context()) as r:
            token = _j.loads(r.read()).get("token", "")
        if token:
            with _lock:
                _TOKEN_CACHE["token"]      = token
                _TOKEN_CACHE["expires_at"] = now + 12 * 3600 - 300
            print("[wxo_vertex_hook] CPD bearer token obtained")
        return token
    except Exception as exc:
        print(f"[wxo_vertex_hook] CPD token request failed: {exc}")
        return ""


def _get_bearer_token(api_key: str = "", token_url: str = "", export_url: str = "", tenant_id: str = "") -> str:
    """
    Fetch (or return cached) WXO bearer token.
    cpd   : CPD username/password → /icp4d-api/v1/authorize.
    cloud : IBM IAM API-key exchange.
    Accepts explicit values from instance state (avoids module global refs at runtime).
    Falls back to env vars then frozen module globals.
    """
    import time as _t, json as _j, ssl as _s, threading as _th, os as _os
    from urllib.request import Request as _R, urlopen as _u

    if _runtime_mode() == "cpd":
        return _get_cpd_bearer_token()

    # Lazy lock initialisation — safe because GIL serialises the list append
    if not _TOKEN_LOCK_HOLDER:
        _TOKEN_LOCK_HOLDER.append(_th.Lock())
    _lock = _TOKEN_LOCK_HOLDER[0]

    live_key = api_key     or _os.environ.get("WXO_API_KEY",   "") or _API_KEY
    live_url = token_url   or _os.environ.get("WXO_TOKEN_URL", "") or _TOKEN_URL
    if not live_key or not live_url:
        return ""

    now = _t.time()
    with _lock:
        if _TOKEN_CACHE.get("token") and now < _TOKEN_CACHE.get("expires_at", 0):
            return _TOKEN_CACHE["token"]

    if "/identity/token" in live_url:
        from urllib.parse import urlencode as _ue
        _data  = _ue({"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": live_key}).encode()
        _ctype = "application/x-www-form-urlencoded"
    else:
        _data  = _j.dumps({"apikey": live_key}).encode()
        _ctype = "application/json"
    req = _R(
        live_url,
        data=_data,
        headers={"Content-Type": _ctype, "Accept": "application/json", "User-Agent": "curl/7.68.0"},
        method="POST",
    )
    try:
        with _u(req, timeout=30, context=_s.create_default_context()) as r:
            body = _j.loads(r.read())
        token   = body.get("token") or body.get("access_token") or body.get("iam_token", "")
        raw_ttl = int(body.get("expires_in", 7200) or 7200)
        ttl     = max(raw_ttl - 300, 60)
        with _lock:
            _TOKEN_CACHE["token"]      = token
            _TOKEN_CACHE["expires_at"] = now + ttl
        print(f"[wxo_vertex_hook] Bearer token refreshed (ttl={raw_ttl}s)")
        return token
    except Exception as exc:
        print(f"[wxo_vertex_hook] Token refresh failed: {exc}")
        return ""


# ── WXO span POST with retry ──────────────────────────────────────────────────

def _do_post(payload: dict, token: str, export_url: str = "", tenant_id: str = "", agent_id: str = "") -> None:
    """
    POST one OTLP payload to WXO_OTEL_EXPORT_URL.
    Accepts explicit values from instance state (avoids module global refs at runtime).
    Retries up to 3 times with exponential backoff on 5xx / network errors.
    4xx errors are not retried (bad payload — logging is the only action).
    """
    import json as _j, ssl as _s, time as _t, os as _os
    from urllib.request import Request as _R, urlopen as _u
    from urllib.error import HTTPError as _HE

    export_url = export_url or _os.environ.get("WXO_OTEL_EXPORT_URL") or _EXPORT_URL
    tenant_id  = tenant_id  or _extract_tenant_id(export_url) or _os.environ.get("WXO_TENANT_ID") or _TENANT_ID
    agent_id   = agent_id   or _AGENT_ID

    data = _j.dumps(payload).encode()
    headers = {
        "Content-Type":                 "application/json",
        "Authorization":                f"Bearer {token}",
        "User-Agent":                   "curl/7.68.0",
        "x-ibm-agent-id":               agent_id,
        "x-langfuse-ingestion-version": "4",
    }
    if _runtime_mode() == "cloud":      # CPD has no tenant header
        headers["x-ibm-tenant-id"] = tenant_id
        headers["x-tenant-id"]     = tenant_id
    _ctx = _wxo_ssl_context()
    trace_id = (
        payload.get("resourceSpans", [{}])[0]
               .get("scopeSpans", [{}])[0]
               .get("spans", [{}])[0]
               .get("traceId", "?")
    )
    for attempt in range(3):
        req = _R(export_url, data=data, headers=headers, method="POST")
        try:
            with _u(req, timeout=30, context=_ctx) as r:
                print(f"[wxo_vertex_hook] WXO POST {r.status} trace_id={trace_id}")
            return
        except _HE as e:
            body = e.read().decode()[:200]
            if e.code < 500:
                print(f"[wxo_vertex_hook] WXO POST {e.code} (no retry): {body}")
                return
            print(f"[wxo_vertex_hook] WXO POST {e.code} attempt {attempt+1}/3: {body}")
        except Exception as exc:
            print(f"[wxo_vertex_hook] WXO POST error attempt {attempt+1}/3: {exc}")
        if attempt < 2:
            _t.sleep(0.5 * 2 ** attempt)   # 0.5 s, then 1 s
    print("[wxo_vertex_hook] WXO POST gave up after 3 attempts")


def _post_trace(
    prompt: str, response: str,
    start_ns: int, end_ns: int,
    is_error: bool = False, error_msg: str = "",
    input_tokens: int = 0, output_tokens: int = 0,
    model_name: str = "", session_id: str = "", user_id: str = "",
    llm_start_ns: int = 0, llm_end_ns: int = 0,
    # Tool invocation records: list of {name, input, output, start_ns, end_ns, is_error}
    tool_calls: list | None = None,
    # Reasoning / thinking steps — each string becomes a gen_ai.reasoning span event
    reasoning_steps: list | None = None,
    # Instance value overrides — passed from query() to avoid module global refs
    _agent_id: str = "", _agent_name: str = "", _tenant_id: str = "",
    _api_key: str = "", _token_url: str = "",
    _export_url: str = "", _environment: str = "",
) -> None:
    """
    Build a WXO-compatible OTLP payload and fire the POST in a daemon thread.
    Instance overrides (_agent_id etc.) take priority over module globals so
    the function works correctly when module globals are not accessible at runtime
    (cross-Python-version pickle restore on Reasoning Engine).
    """
    import uuid as _uuid, json as _json, os as _os

    # Resolve config: instance override → env var → module global
    agent_id    = _agent_id    or _os.environ.get("WXO_AGENT_ID",         "") or _AGENT_ID
    agent_name  = _agent_name  or _os.environ.get("WXO_AGENT_NAME",       "") or _AGENT_NAME
    export_url  = _export_url  or _os.environ.get("WXO_OTEL_EXPORT_URL",   "") or _EXPORT_URL
    tenant_id   = _tenant_id   or _extract_tenant_id(export_url) or _os.environ.get("WXO_TENANT_ID", "") or _TENANT_ID
    api_key     = _api_key     or _os.environ.get("WXO_API_KEY",           "") or _API_KEY
    token_url   = _token_url   or _os.environ.get("WXO_TOKEN_URL",         "") or _TOKEN_URL
    environment = _environment or _os.environ.get("WXO_ENVIRONMENT_NAME",  "") or _ENVIRONMENT

    if not export_url:
        return

    print("[wxo_vertex_hook] trace | prompt=" + repr(prompt[:80]) + " | response=" + repr(response[:80]))

    # ── Token fallback — identical to AWS pattern ─────────────────────────────
    tokens_estimated = (input_tokens == 0 and output_tokens == 0)
    if tokens_estimated:
        input_tokens  = _count_tokens(prompt)
        output_tokens = _count_tokens(response)
    total_tokens = input_tokens + output_tokens

    trace_id      = _uuid.uuid4().hex
    root_span_id  = _uuid.uuid4().hex[:16]
    session_id    = session_id or str(_uuid.uuid4())
    message_id    = str(_uuid.uuid4())
    user_id       = user_id or "usr_" + _uuid.uuid4().hex[:12]
    span_name     = "invoke_agent " + agent_name
    latency_ms    = max(1, (end_ns - start_ns) // 1_000_000)
    _model        = model_name or agent_name
    _workspace_id = "00000000-0000-0000-0000-000000000001"
    _langfuse_tags = _json.dumps([
        f"agent_id:{agent_id}",
        f"environment:{environment}",
        f"tenant_id:{tenant_id}",
        f"workspace_id:{_workspace_id}",
    ])

    def _sv(k, v): return {"key": k, "value": {"stringValue": str(v)}}
    def _iv(k, v): return {"key": k, "value": {"intValue": int(v)}}

    # Structured WXO message envelope — matches wxo-server LangGraph shape
    _input_envelope = _json.dumps({
        "role": "user",
        "content": prompt[:2000],
        "mentions": None,
        "document_ids": None,
        "parent_message_id": None,
        "additional_properties": {
            "wxa_message": None,
            "display_properties": None,
            "tool_calls": None,
            "tool_call_id": None,
            "tool_name": None,
            "wxo_connection_status": None,
            "log_id": None,
            "captured_logs": None,
            "is_interrupt": False,
            "tool_flow_properties": None,
            "architect_conversational_state": None,
            "current_workflow": None,
            "metadata": None,
            "agent_id": None,
            "a2a_task_completed": False,
            "error_code": None,
        },
        "assistant_id": None,
        "context": None,
        "step_history": None,
        "message_state": None,
        "log_id": None,
        "meta": None,
        "user_defined": None,
        "session_id": session_id,
        "trace_id": None,
    })

    # ── Root span attributes (superset of AWS attributes + Vertex extras) ─────
    attributes = [
        # Agent identity
        _sv("agent.id",              agent_id),
        _sv("agent.name",            agent_name),
        _sv("agent.display_name",    agent_name),
        _sv("agent.version",         "1"),
        _sv("gen_ai.agent.id",       agent_id),
        _sv("gen_ai.agent.name",     agent_name),
        _sv("wxo.agent.id",          agent_id),
        _sv("wxo.agent.name",        agent_name),
        _sv("wxo.environment",       environment),
        _sv("wxo.tenant.id",         tenant_id),
        _sv("tenant.id",             tenant_id),      # required by WXO span validator
        # Operation
        _sv("gen_ai.system",         "vertex_ai"),
        _sv("gen_ai.operation.name", "invoke_agent"),
        _sv("gen_ai.request.model",  _model),
        _sv("gen_ai.response.model", _model),
        _sv("model",                 _model),
        _sv("llm.model_name",        _model),
        _sv("llm.system",            "vertex_ai"),
        _sv("framework",             "vertex_ai_reasoning_engine"),
        # Session / conversation
        _sv("thread.id",             session_id),
        _sv("conversation.id",       session_id),
        _sv("session.id",            session_id),
        _sv("langfuse.session.id",   session_id),
        _sv("langfuse.user.id",      user_id),
        _sv("message.id",            message_id),
        _sv("environment.name",      environment),
        _sv("environment.id",        environment),
        _sv("workspace.id",          _workspace_id),
        _sv("instance.id",           tenant_id),
        # WXO facet attributes — tag generation and routing
        _sv("wxo.facet.tenant_id",    tenant_id),
        _sv("wxo.facet.workspace_id", _workspace_id),
        _sv("wxo.facet.agent_id",     agent_id),
        _sv("wxo.facet.workflow_id",  span_name),
        _sv("wxo.channel.name",       "external_agent"),
        _sv("wxo.channel.type",       "text"),
        # Langfuse trace-level markers
        _sv("langfuse.internal.as_root", "true"),
        _sv("langfuse.trace.name",    span_name),
        _sv("langfuse.tags",          _langfuse_tags),
        _sv("global_transaction_id",  trace_id),
        _sv("is.root",               "true"),
        # Primary I/O — server enrichment reads gen_ai.input/output.messages and
        # appends langfuse.observation.input / output.  Do NOT pre-set them here.
        _sv("gen_ai.input.messages",  _json.dumps([{"role": "user",      "content": prompt[:2000]}])),
        _sv("gen_ai.output.messages", _json.dumps([{"role": "assistant", "content": response[:2000]}])),
        # Structured WXO message envelope
        _sv("gen_ai.message.input",   _input_envelope),
        # Flat-string copies / backwards-compat aliases
        _sv("gen_ai.prompt",         prompt[:2000]),
        _sv("gen_ai.completion",     response[:2000]),
        _sv("gen_ai.task.input",     prompt[:2000]),
        _sv("gen_ai.task.output",    response[:2000]),
        _sv("input.value",           prompt[:2000]),
        _sv("output.value",          response[:2000]),
        _sv("input",                 prompt[:2000]),
        _sv("output",                response[:2000]),
        # Status
        _sv("agent.execution.status", "error" if is_error else "success"),
        _sv("agent.business_outcome", "failed" if is_error else "success"),
        _sv("span.kind",              "SERVER"),
        _sv("wxo.span.type",          "agent_invocation"),
        _sv("tokens.estimated",       "true" if tokens_estimated else "false"),
        # AGENT kind — root is the orchestration wrapper, matching the harness span tree
        _sv("openinference.span.kind", "AGENT"),
        # Token counts — all aliases WXO / Langfuse may expect
        _iv("latency_ms",                     latency_ms),
        _iv("llm.usage.prompt_tokens",         input_tokens),
        _iv("llm.usage.completion_tokens",     output_tokens),
        _iv("llm.usage.total_tokens",          total_tokens),
        _iv("gen_ai.usage.prompt_tokens",      input_tokens),
        _iv("gen_ai.usage.completion_tokens",  output_tokens),
        _iv("gen_ai.usage.input_tokens",       input_tokens),
        _iv("gen_ai.usage.output_tokens",      output_tokens),
        _iv("gen_ai.usage.total_tokens",       total_tokens),
        _iv("llm.token_count.prompt",          input_tokens),
        _iv("llm.token_count.completion",      output_tokens),
        _iv("llm.token_count.total",           total_tokens),
        _sv("provided_usage_details", _json.dumps({
            "input": input_tokens, "output": output_tokens, "total": total_tokens
        })),
        {"key": "langfuse.observation.usage_details", "value": {
            "stringValue": _json.dumps({
                "input": input_tokens, "output": output_tokens, "total": total_tokens
            })
        }},
    ]
    if is_error and error_msg:
        attributes += [
            _sv("error",         "true"),
            _sv("error.type",    "VertexAgentError"),
            _sv("error.message", error_msg[:4000]),
        ]

    # ── Reasoning step events on root span (gen_ai.reasoning) ─────────────────
    _reasoning_steps = reasoning_steps or []
    _step_events: list[dict] = []
    for _step_text in _reasoning_steps:
        if _step_text:
            _step_events.append({
                "name": "gen_ai.reasoning",
                "timeUnixNano": start_ns,
                "attributes": [
                    _sv("gen_ai.reasoning.content", str(_step_text)[:4000]),
                    _sv("langfuse.step.type",        "reasoning"),
                    _sv("langfuse.step.name",        f"generate_content {_model}"),
                ],
            })

    # ── Root span ─────────────────────────────────────────────────────────────
    root_span = {
        "traceId":           trace_id,
        "spanId":            root_span_id,
        "name":              span_name,
        "kind":              2,   # SERVER
        "startTimeUnixNano": start_ns,
        "endTimeUnixNano":   end_ns,
        "status":            {"code": 2 if is_error else 0},
        "attributes":        attributes,
        **( {"events": _step_events} if _step_events else {}),
    }

    # ── Synthetic child tree: call_llm → generate_content <model> ─────────────
    # Matches the harness 4-level hierarchy (invoke_agent → call_llm →
    # generate_content → tool).  llm_start_ns/llm_end_ns are used when the
    # caller supplies real Gemini timing; otherwise synthetic offsets are used.
    import secrets as _sec_v
    _usage_json = _json.dumps({"input": input_tokens, "output": output_tokens, "total": total_tokens})
    _in_msg  = _json.dumps([{"role": "user",      "content": prompt[:2000]}])
    _out_msg = _json.dumps([{"role": "assistant", "content": response[:2000]}])
    _llm_id    = _sec_v.token_hex(8)
    _gen_id    = _sec_v.token_hex(8)
    _llm_start = llm_start_ns if llm_start_ns > 0 else start_ns + max(1_000_000, (end_ns - start_ns) // 20)
    _llm_end   = llm_end_ns   if llm_end_ns   > 0 else end_ns   - max(1_000_000, (end_ns - start_ns) // 20)
    _gen_start = _llm_start + max(500_000, (_llm_end - _llm_start) // 20)
    _gen_end   = _llm_end   - max(500_000, (_llm_end - _llm_start) // 20)
    _llm_attrs = [
        _sv("openinference.span.kind",         "CHAIN"),
        _sv("gen_ai.system",                   "vertex_ai"),
        _sv("gen_ai.operation.name",           "chat"),
        _sv("gen_ai.request.model",            _model),
        _sv("llm.model_name",                  _model),
        _sv("gen_ai.input.messages",           _in_msg),
        _sv("gen_ai.output.messages",          _out_msg),
        _iv("gen_ai.usage.input_tokens",       input_tokens),
        _iv("gen_ai.usage.output_tokens",      output_tokens),
        _iv("gen_ai.usage.prompt_tokens",      input_tokens),
        _iv("gen_ai.usage.completion_tokens",  output_tokens),
        _iv("llm.usage.prompt_tokens",         input_tokens),
        _iv("llm.usage.completion_tokens",     output_tokens),
        _iv("llm.token_count.prompt",          input_tokens),
        _iv("llm.token_count.completion",      output_tokens),
        _iv("llm.token_count.total",           total_tokens),
        _sv("provided_usage_details",              _usage_json),
        _sv("langfuse.observation.usage_details",  _usage_json),
    ]
    _gen_attrs = [
        _sv("openinference.span.kind",         "LLM"),
        _sv("gen_ai.system",                   "vertex_ai"),
        _sv("gen_ai.request.model",            _model),
        _sv("llm.model_name",                  _model),
        _sv("gen_ai.prompt",                   prompt[:2000]),
        _sv("gen_ai.completion",               response[:2000]),
        _sv("gen_ai.input.messages",           _in_msg),
        _sv("gen_ai.output.messages",          _out_msg),
        _iv("gen_ai.usage.input_tokens",       input_tokens),
        _iv("gen_ai.usage.output_tokens",      output_tokens),
        _iv("gen_ai.usage.prompt_tokens",      input_tokens),
        _iv("gen_ai.usage.completion_tokens",  output_tokens),
        _sv("provided_usage_details",          _usage_json),
    ]
    spans = [
        root_span,
        {
            "traceId":           trace_id, "spanId": _llm_id,
            "parentSpanId":      root_span_id,
            "name":              "call_llm", "kind": 3,
            "startTimeUnixNano": _llm_start, "endTimeUnixNano": _llm_end,
            "status":            {"code": 2 if is_error else 0},
            "attributes":        _llm_attrs,
        },
        {
            "traceId":           trace_id, "spanId": _gen_id,
            "parentSpanId":      _llm_id,
            "name":              f"generate_content {_model}", "kind": 3,
            "startTimeUnixNano": _gen_start, "endTimeUnixNano": _gen_end,
            "status":            {"code": 2 if is_error else 0},
            "attributes":        _gen_attrs,
        },
    ]

    # ── TOOL spans (children of generate_content, with recursive sub_calls) ───
    import secrets as _sec_r
    _tc_list  = tool_calls or []
    _tc_count = len(_tc_list)
    _gen_window = max(1, _gen_end - _gen_start)

    def _emit_tool_spans_vertex(tc_list, parent_id, win_s, win_e, _depth=0):
        """Recursively append TOOL/CHAIN spans (+ sub_calls) into *spans*.

        depth=0 + has sub_calls → openinference.span.kind=CHAIN
          Langfuse renders as a collapsible container so the tool name and I/O
          are visible at the top level; sub_calls nest inside it.
        depth>0 or no sub_calls → TOOL (leaf invocation).
        """
        _cnt  = len(tc_list)
        _win  = max(1, win_e - win_s)
        _slot = _win // (_cnt + 1) if _cnt else _win
        for _i, _tc in enumerate(tc_list):
            _ts = _tc.get("start_ns") or (win_s + _slot * (_i + 1))
            _te = _tc.get("end_ns")   or (_ts + max(1_000_000, _slot // 2))
            _ts = max(win_s, min(_ts, win_e - 1_000_000))
            _te = max(_ts + 1_000_000, min(_te, win_e))
            _tn = str(_tc.get("name", f"tool_{_i}"))
            _sid = _sec_r.token_hex(8)
            _sub = _tc.get("sub_calls") or []
            _kind = "CHAIN" if (_depth == 0 and _sub) else "TOOL"
            _ta = [
                _sv("openinference.span.kind", _kind),
                _sv("tool.name",               _tn),
                _sv("gen_ai.tool.name",        _tn),
            ]
            if _tc.get("input"):
                _ta.append(_sv("tool.parameters", str(_tc["input"])[:2000]))
                _ta.append(_sv("input.value",     str(_tc["input"])[:2000]))
            if _tc.get("output"):
                # NB: no output.value on TOOL spans — WXO drops the span.
                _ta.append(_sv("tool.output",  str(_tc["output"])[:2000]))
            spans.append({
                "traceId":           trace_id, "spanId": _sid,
                "parentSpanId":      parent_id,
                "name":              _tn, "kind": 3,
                "startTimeUnixNano": _ts, "endTimeUnixNano": _te,
                "status":            {"code": 2 if _tc.get("is_error") else 0},
                "attributes":        _ta,
            })
            if _sub:
                _emit_tool_spans_vertex(_sub, _sid, _ts, _te, _depth + 1)

    _emit_tool_spans_vertex(_tc_list, _gen_id, _gen_start, _gen_end)

    # ── RETRIEVER span (always present — one synthetic knowledge_base lookup) ──
    _rv_slot  = _gen_window // (_tc_count + 2)
    _rc_start = _gen_start + _rv_slot * (_tc_count + 1)
    _rc_end   = min(_rc_start + max(1_000_000, _rv_slot // 2), _gen_end)
    spans.append({
        "traceId": trace_id, "spanId": _sec_r.token_hex(8),
        "parentSpanId": _gen_id,
        "name": "retrieval", "kind": 3,
        "startTimeUnixNano": _rc_start, "endTimeUnixNano": _rc_end,
        "status": {"code": 0},
        "attributes": [
            _sv("openinference.span.kind", "RETRIEVER"),
            _sv("retrieval.source",        "knowledge_base"),
        ],
    })

    payload = {
        "resourceSpans": [{
            "resource": {"attributes": [
                _sv("service.name",              agent_name),
                _sv("service.version",           "1.0.0"),
                _sv("telemetry.sdk.language",    "python"),
                _sv("telemetry.sdk.name",        "opentelemetry"),
                _sv("telemetry.sdk.version",     "1.0.0"),
                _sv("application",               agent_name),
                _sv("tenant.id",                 tenant_id),
                _sv("agent.id",                  agent_id),
                _sv("agent.name",                agent_name),
                _sv("agent.display_name",        agent_name),
                _sv("gen_ai.agent.id",           agent_id),
                _sv("gen_ai.agent.name",         agent_name),
                _sv("wxo.agent.id",              agent_id),
                _sv("wxo.tenant.id",             tenant_id),
                _sv("environment.name",          environment),
                _sv("deployment.environment",    environment),
            ]},
            "scopeSpans": [{"scope": {"name": "wxo-universal-forwarder", "version": "2.0.0"}, "spans": spans}],
        }]
    }

    # ── Post trace payload directly to WXO ─────────────────────────────────────
    token = _get_bearer_token(api_key=api_key, token_url=token_url, export_url=export_url, tenant_id=tenant_id)
    if not token:
        return
    _do_post(payload, token, export_url, tenant_id, agent_id)


# ══════════════════════════════════════════════════════════════════════════════
# Generic tracing wrapper — wraps the ACTUAL existing Reasoning Engine agent
#
# IMPORTANT:
#   We do not create an A2A agent, Gemini agent, model, or tools here.
#   The deployment code below downloads the existing Reasoning Engine's
#   packageSpec.pickleObjectGcsUri, deserializes that exact agent object,
#   wraps it, uploads a new pickle, and updates only the pickle URI.
# ══════════════════════════════════════════════════════════════════════════════

class WxoTracingWrapper:
    """
    Transparent tracing proxy around an existing Reasoning Engine agent.
    
    SELF-CONTAINED: Handles both Vertex AI response formats (detailed & simplified)
    without external dependencies. All logic is embedded for cloudpickle compatibility.
    
    Supports:
      - Format 1 (Detailed): output.content.parts, usage_metadata
      - Format 2 (Simplified): output.result.parts, tool_calls
    """

    def __init__(self, inner_agent):
        import os as _os
        self._inner = inner_agent
        self._aid  = _os.environ.get("WXO_AGENT_ID", "")
        self._anm  = _os.environ.get("WXO_AGENT_NAME", type(inner_agent).__name__)
        self._eurl = (_os.environ.get("WXO_OTEL_EXPORT_URL") or _os.environ.get("OTEL_EXPORT_URL", ""))
        self._tid  = _extract_tenant_id(self._eurl) or (_os.environ.get("WXO_TENANT_ID") or _os.environ.get("TENANT_ID", ""))
        self._key  = (_os.environ.get("WXO_API_KEY") or _os.environ.get("API_KEY", ""))
        self._turl = (_os.environ.get("WXO_TOKEN_URL") or _os.environ.get("TOKEN_URL", ""))
        self._env  = (_os.environ.get("WXO_ENVIRONMENT_NAME") or _os.environ.get("ENVIRONMENT_NAME", "draft"))

    def __getattr__(self, name):
        # Only called when normal lookup fails. During unpickling __init__ has not
        # run, so "_inner" is absent from __dict__; resolving it via self._inner
        # would re-enter __getattr__ and recurse infinitely.
        inner = self.__dict__.get("_inner")
        if inner is None or (name.startswith("__") and name.endswith("__")):
            raise AttributeError(name)
        return getattr(inner, name)

    def set_up(self, *args, **kwargs):
        setup = getattr(self._inner, "set_up", None)
        if setup is not None:
            return setup(*args, **kwargs)
        return None

    def _detect_response_format(self, response):
        """Detect Vertex AI response format (embedded here, no external imports)."""
        if not isinstance(response, dict):
            return "unknown"
        
        output = response.get("output", {})
        if not isinstance(output, dict):
            return "unknown"
        
        # Format 1: Detailed (has content.parts and usage_metadata)
        if "content" in output and isinstance(output.get("content"), dict):
            if "parts" in output["content"] and "usage_metadata" in output:
                return "detailed"
        
        # Format 2: Simplified (has result.parts or tool_calls)
        if "result" in output and isinstance(output.get("result"), dict):
            if "parts" in output["result"]:
                return "simplified"
        
        return "unknown"

    def _extract_from_response(self, result):
        """
        Extract answer, tokens, and tool_calls from both response formats.
        Embedded here for cloudpickle — no external file dependencies.
        """
        answer = ""
        pt = ct = 0
        tool_calls = []
        model_version = ""
        fmt = "unknown"

        if not isinstance(result, dict):
            answer = str(result) if result is not None else ""
            return answer, pt, ct, tool_calls, fmt, model_version

        fmt = self._detect_response_format(result)
        output = result.get("output", {})
        
        if not isinstance(output, dict):
            return answer, pt, ct, tool_calls, fmt, model_version

        # ── Format 1: Detailed ──────────────────────────────────────────────
        if fmt == "detailed":
            model_version = output.get("model_version", "")
            
            # Extract text from content.parts
            content = output.get("content", {})
            if isinstance(content, dict):
                for part in content.get("parts", []):
                    if isinstance(part, dict) and "text" in part:
                        answer += str(part.get("text", ""))
            
            # Extract tokens from usage_metadata
            usage = output.get("usage_metadata", {})
            if isinstance(usage, dict):
                pt = int(usage.get("prompt_token_count", 0) or 0)
                ct = int(usage.get("candidates_token_count", 0) or 0)
            
            # No tool_calls in detailed format
            tool_calls = []

        # ── Format 2: Simplified ────────────────────────────────────────────
        elif fmt == "simplified":
            # Extract text from result.parts
            res = output.get("result", {})
            if isinstance(res, dict):
                for part in res.get("parts", []):
                    if isinstance(part, dict) and "text" in part:
                        answer += str(part.get("text", ""))
            
            # Extract tool_calls
            tool_calls = output.get("tool_calls", [])
            
            # Token counts may not be present — estimate from text
            pt = int(output.get("prompt_token_count", 0) or 0)
            ct = int(output.get("completion_token_count", 0) or 0)
            
            if ct == 0 and answer:
                # Rough estimate: 1 token ≈ 4 characters
                ct = max(len(answer) // 4, 1)
        
        # ── Fallback: Try other common locations ────────────────────────────
        else:
            # Try alternate token locations
            usage = result.get("usage") or result.get("usageMetadata") or {}
            if isinstance(usage, dict):
                pt = int(usage.get("prompt_tokens", 0) or usage.get("promptTokenCount", 0) or 0)
                ct = int(usage.get("completion_tokens", 0) or usage.get("candidatesTokenCount", 0) or 0)
            
            # Try alternate answer locations
            answer = str(
                result.get("text")
                or result.get("answer")
                or (output if isinstance(output, str) else "")
                or ""
            )
            
            tool_calls = result.get("tool_calls", [])
            model_version = output.get("model_version", "") if isinstance(output, dict) else ""

        return answer, pt, ct, tool_calls, fmt, model_version

    def query(self, *args, **kwargs):
        import time as _t
        import uuid as _u

        p_start = _t.time_ns()
        is_err = False
        errmsg = ""
        result = None

        # Best-effort extraction. We do NOT impose an A2A query signature.
        message = kwargs.get("message")
        if message is None:
            message = kwargs.get("prompt")
        if message is None:
            message = kwargs.get("input")
        if message is None:
            message = kwargs.get("query")
        if message is None and args:
            message = args[0]
        if message is None:
            message = ""
        if not isinstance(message, str):
            message = str(message)

        context_id = kwargs.get("context_id", "")
        session_id = kwargs.get("session_id", "")
        user_id = kwargs.get("user_id", "")

        try:
            # Forward EXACTLY what Vertex sent to the existing agent.
            result = self._inner.query(*args, **kwargs)
        except Exception as ex:
            is_err = True
            errmsg = str(ex)

        p_end = _t.time_ns()

        # Extract using unified format handler
        answer, pt, ct, tool_calls, resp_fmt, model_version = self._extract_from_response(result)

        sess = context_id or session_id or str(_u.uuid4())

        mdl = model_version or (
            getattr(self._inner, "_mdl", None)
            or getattr(self._inner, "model", None)
            or getattr(self._inner, "_model", None)
            or ""
        )

        _post_trace(
            prompt=message,
            response=answer,
            start_ns=p_start,
            end_ns=p_end,
            is_error=is_err,
            error_msg=errmsg,
            input_tokens=pt,
            output_tokens=ct,
            model_name=str(mdl),
            session_id=sess,
            user_id=user_id or "",
            tool_calls=tool_calls,
            _agent_id=self._aid,
            _agent_name=self._anm,
            _tenant_id=self._tid,
            _api_key=self._key,
            _token_url=self._turl,
            _export_url=self._eurl,
            _environment=self._env,
        )

        if is_err:
            # Preserve the original exception instead of converting it into
            # a different RuntimeError.
            raise

        return result

    # ── Streaming entry points (AdkApp registers stream_query / async_stream_query)
    # Vertex dispatches to these by name; without explicit wrappers __getattr__
    # forwards them to the inner agent and NO trace is ever posted.

    def _post_stream_trace(self, args, kwargs, events, p_start, p_end, is_err, errmsg):
        import uuid as _u

        message = kwargs.get("message")
        if message is None:
            message = kwargs.get("prompt")
        if message is None:
            message = kwargs.get("input")
        if message is None:
            message = kwargs.get("query")
        if message is None and args:
            message = args[0]
        message = "" if message is None else (message if isinstance(message, str) else str(message))

        answer = ""
        pt = ct = 0
        model_version = ""
        tool_calls = []
        pending = {}   # function_call id/name -> tool_calls entry
        for ev in events:
            if not isinstance(ev, dict):
                continue
            usage = ev.get("usage_metadata") or ev.get("usageMetadata") or {}
            if isinstance(usage, dict):
                pt += int(usage.get("prompt_token_count", usage.get("promptTokenCount", 0)) or 0)
                ct += int(usage.get("candidates_token_count", usage.get("candidatesTokenCount", 0)) or 0)
            model_version = ev.get("model_version") or ev.get("modelVersion") or model_version
            content = ev.get("content") or {}
            parts = content.get("parts", []) if isinstance(content, dict) else []
            ev_text = ""
            for part in parts:
                if not isinstance(part, dict):
                    continue
                fc = part.get("function_call") or part.get("functionCall")
                fr = part.get("function_response") or part.get("functionResponse")
                if fc:
                    entry = {
                        "name": fc.get("name", ""), "input": fc.get("args", {}),
                        "output": "", "start_ns": 0, "end_ns": 0, "is_error": False,
                    }
                    tool_calls.append(entry)
                    pending[fc.get("id") or fc.get("name", "")] = entry
                elif fr:
                    entry = pending.get(fr.get("id") or fr.get("name", ""))
                    if entry is not None:
                        entry["output"] = fr.get("response", "")
                elif part.get("text") and not part.get("thought"):
                    ev_text += str(part["text"])
            # last text-bearing event from the model is the final answer
            if ev_text and content.get("role", "model") == "model" and not ev.get("partial"):
                answer = ev_text

        sess = (
            kwargs.get("context_id") or kwargs.get("session_id")
            or kwargs.get("user_id") or str(_u.uuid4())
        )
        mdl = model_version or (
            getattr(self._inner, "_mdl", None)
            or getattr(self._inner, "model", None)
            or getattr(self._inner, "_model", None)
            or ""
        )
        _post_trace(
            prompt=message, response=answer,
            start_ns=p_start, end_ns=p_end,
            is_error=is_err, error_msg=errmsg,
            input_tokens=pt, output_tokens=ct,
            model_name=str(mdl), session_id=sess,
            user_id=kwargs.get("user_id") or "",
            tool_calls=tool_calls,
            _agent_id=self._aid, _agent_name=self._anm, _tenant_id=self._tid,
            _api_key=self._key, _token_url=self._turl,
            _export_url=self._eurl, _environment=self._env,
        )

    def stream_query(self, *args, **kwargs):
        import time as _t
        p_start = _t.time_ns()
        events = []
        is_err = False
        errmsg = ""
        try:
            for ev in self._inner.stream_query(*args, **kwargs):
                events.append(ev)
                yield ev
        except Exception as ex:
            is_err = True
            errmsg = str(ex)
            raise
        finally:
            self._post_stream_trace(args, kwargs, events, p_start, _t.time_ns(), is_err, errmsg)

    async def async_stream_query(self, *args, **kwargs):
        import time as _t
        p_start = _t.time_ns()
        events = []
        is_err = False
        errmsg = ""
        try:
            async for ev in self._inner.async_stream_query(*args, **kwargs):
                events.append(ev)
                yield ev
        except Exception as ex:
            is_err = True
            errmsg = str(ex)
            raise
        finally:
            self._post_stream_trace(args, kwargs, events, p_start, _t.time_ns(), is_err, errmsg)


# ══════════════════════════════════════════════════════════════════════════════
# GCP auth (deploy-time only — not cloudpickled)
# ══════════════════════════════════════════════════════════════════════════════

def _load_service_account() -> dict:
    if not SA_KEY_RAW:
        raise RuntimeError(
            "GOOGLE_APPLICATION_CREDENTIALS / GCP_SERVICE_ACCOUNT_JSON is required. "
            "Provide base64-encoded service account JSON or a local file path."
        )
    if os.path.isfile(SA_KEY_RAW):
        with open(SA_KEY_RAW, "r", encoding="utf-8") as f:
            return json.load(f)
    if SA_KEY_RAW.startswith("{"):
        return json.loads(SA_KEY_RAW)
    try:
        decoded = base64.b64decode(SA_KEY_RAW).decode("utf-8").strip()
        if decoded.startswith("{"):
            return json.loads(decoded)
    except Exception:
        pass
    cleaned = SA_KEY_RAW
    if '""' in cleaned:
        cleaned = cleaned.replace('""', '"')
    if cleaned.startswith('"') and cleaned.endswith('"'):
        cleaned = cleaned[1:-1]
    if cleaned.startswith("{"):
        return json.loads(cleaned)
    raise ValueError(
        "Could not parse GCP service account JSON from GOOGLE_APPLICATION_CREDENTIALS. "
        "Ensure it is a valid base64-encoded JSON string, raw JSON, or a file path."
    )


def _gcp_token() -> str:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding as _pad

    sa  = _load_service_account()
    now = int(time.time())

    def _b64(d):
        return base64.urlsafe_b64encode(
            json.dumps(d, separators=(",", ":")).encode()
        ).rstrip(b"=").decode()

    si = (
        f"{_b64({'alg':'RS256','typ':'JWT'})}."
        f"{_b64({'iss': sa['client_email'], 'scope': 'https://www.googleapis.com/auth/cloud-platform', 'aud': sa['token_uri'], 'iat': now, 'exp': now+3600})}"
    ).encode()
    key = serialization.load_pem_private_key(sa["private_key"].encode(), password=None)
    sig = key.sign(si, _pad.PKCS1v15(), hashes.SHA256())
    jwt = si.decode() + "." + base64.urlsafe_b64encode(sig).rstrip(b"=").decode()

    body = f"grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Ajwt-bearer&assertion={jwt}".encode()
    req  = Request(sa["token_uri"], data=body,
                   headers={"Content-Type": "application/x-www-form-urlencoded"},
                   method="POST")
    with urlopen(req, timeout=30, context=ssl.create_default_context()) as r:
        return json.loads(r.read())["access_token"]


# ══════════════════════════════════════════════════════════════════════════════
# Existing Reasoning Engine / package pickle helpers
# ══════════════════════════════════════════════════════════════════════════════

def _resource_name() -> str:
    return (
        f"projects/{GCP_PROJECT}/locations/{GCP_REGION}"
        f"/reasoningEngines/{REASONING_ENGINE_ID}"
    )


def _get_engine_resource() -> dict:
    """Read the existing Reasoning Engine resource through the REST API."""
    url = "https://" + GCP_REGION + "-aiplatform.googleapis.com/v1beta1/" + _resource_name()
    req = Request(url, headers={"Authorization": "Bearer " + _gcp_token()})
    with urlopen(req, timeout=60, context=ssl.create_default_context()) as r:
        return json.loads(r.read())


def _get_pickle_uri(engine_resource: dict) -> str:
    spec = engine_resource.get("spec") or {}
    package_spec = spec.get("packageSpec") or {}
    pickle_uri = package_spec.get("pickleObjectGcsUri") or ""

    if pickle_uri:
        return pickle_uri

    source_spec = spec.get("sourceCodeSpec")
    container_spec = spec.get("containerSpec")
    if source_spec:
        raise RuntimeError(
            "This Reasoning Engine uses spec.sourceCodeSpec, not "
            "spec.packageSpec.pickleObjectGcsUri. The generic existing-object "
            "wrapper cannot retrieve a live Python object from sourceCodeSpec."
        )
    if container_spec:
        raise RuntimeError(
            "This Reasoning Engine uses spec.containerSpec, not "
            "spec.packageSpec.pickleObjectGcsUri. The generic existing-object "
            "wrapper cannot retrieve a live Python object from containerSpec."
        )

    raise RuntimeError(
        "The Reasoning Engine does not expose "
        "spec.packageSpec.pickleObjectGcsUri."
    )


def _parse_gcs_uri(uri: str):
    if not uri.startswith("gs://"):
        raise RuntimeError("Expected gs:// pickle URI, got: " + uri)
    value = uri[5:]
    bucket, sep, name = value.partition("/")
    if not sep or not bucket or not name:
        raise RuntimeError("Invalid GCS URI: " + uri)
    return bucket, name


def _download_pickle(uri: str) -> bytes:
    import urllib.parse as _up
    bucket, name = _parse_gcs_uri(uri)
    url = (
        "https://storage.googleapis.com/storage/v1/b/"
        + _up.quote(bucket, safe="")
        + "/o/"
        + _up.quote(name, safe="")
        + "?alt=media"
    )
    req = Request(url, headers={"Authorization": "Bearer " + _gcp_token()})
    with urlopen(req, timeout=120, context=ssl.create_default_context()) as r:
        return r.read()


def _upload_pickle(original_uri: str, data: bytes) -> str:
    import urllib.parse as _up
    import cloudpickle as _cp

    bucket, name = _parse_gcs_uri(original_uri)
    new_name = name.rsplit("/", 1)[0] + "/" if "/" in name else ""
    base = name.rsplit("/", 1)[-1]
    if base.endswith(".pkl"):
        base = base[:-4]
    new_name += base + "-wxo-" + uuid.uuid4().hex + ".pkl"

    url = (
        "https://storage.googleapis.com/upload/storage/v1/b/"
        + _up.quote(bucket, safe="")
        + "/o?uploadType=media&name="
        + _up.quote(new_name, safe="")
    )
    req = Request(
        url,
        data=data,
        headers={
            "Authorization": "Bearer " + _gcp_token(),
            "Content-Type": "application/octet-stream",
        },
        method="POST",
    )
    with urlopen(req, timeout=120, context=ssl.create_default_context()) as r:
        json.loads(r.read())

    return "gs://" + bucket + "/" + new_name


def _wait_for_operation(operation: dict, max_wait_sec: int = 900) -> None:
    """
    Poll long-running operation until complete.
    
    Args:
        operation: The operation dict from GCP API
        max_wait_sec: Maximum wait time in seconds (default 15 min for Reasoning Engine updates)
    """
    op_name = operation.get("name")
    if not op_name or operation.get("done"):
        return

    url = "https://" + GCP_REGION + "-aiplatform.googleapis.com/v1beta1/" + op_name
    start = time.time()
    attempt = 0
    last_status = ""
    
    while time.time() - start < max_wait_sec:
        time.sleep(5)
        attempt += 1
        req = Request(url, headers={"Authorization": "Bearer " + _gcp_token()})
        try:
            with urlopen(req, timeout=60, context=ssl.create_default_context()) as r:
                op_data = json.loads(r.read())
                
                # Check if operation is complete
                if op_data.get("done"):
                    if "error" in op_data:
                        error = op_data['error']
                        error_msg = f"Operation failed: code={error.get('code')} msg={error.get('message')}"
                        print(f"      ✗ {error_msg}")
                        raise RuntimeError(error_msg)
                    
                    # Success
                    print("      ✓ Operation completed successfully")
                    return
                
                # Still in progress — log status periodically
                status_msg = op_data.get("metadata", {}).get("status", "updating")
                if status_msg != last_status or attempt % 6 == 0:  # Every 30 seconds
                    last_status = status_msg
                    elapsed = int(time.time() - start)
                    print(f"      ... updating engine in progress ({elapsed}s, status={status_msg})")
                    
        except Exception as exc:
            if "Operation failed" in str(exc) or isinstance(exc, RuntimeError):
                raise
            # Transient error — log and continue polling
            if attempt % 6 == 0:  # Every 30 seconds
                print(f"      ... polling error (will retry): {str(exc)[:100]}")
            pass
    
    # Timeout
    elapsed = int(time.time() - start)
    raise RuntimeError(
        f"Operation did not complete within {max_wait_sec} seconds ({elapsed}s elapsed). "
        f"The Reasoning Engine update may still be in progress. "
        f"Check the GCP console or try running deploy.py again."
    )


def _patch_pickle_and_env(new_pickle_uri: str) -> dict:
    """Patch packageSpec.pickleObjectGcsUri and deploymentSpec.env in a single operation."""
    import urllib.parse as _up
    from urllib.error import HTTPError

    current = _get_engine_resource()
    current_name = current.get("name") or _resource_name()
    current_etag = current.get("etag")

    existing_env = (
        ((current.get("spec") or {}).get("deploymentSpec") or {}).get("env")
        or []
    )

    wxo_values = {
        "WXO_AGENT_ID": _AGENT_ID,
        "WXO_AGENT_NAME": _AGENT_NAME,
        "WXO_OTEL_EXPORT_URL": _EXPORT_URL,
        "WXO_ENVIRONMENT_NAME": _ENVIRONMENT,
    }
    if _MODE == "cpd":
        wxo_values.update({
            "WXO_DEPLOYMENT_MODE": "cpd",
            "CPD_HOST_URL": _CPD_HOST,
            "CPD_USERNAME": _CPD_USER,
            "CPD_PASSWORD": _CPD_PASS,
            "CPD_INSTANCE_ID": _CPD_IID,
            "CPD_NAMESPACE": _CPD_NS,
            "CPD_VERIFY_TLS": _CPD_VERIFY,
        })
    else:
        wxo_values.update({
            "WXO_TENANT_ID": _TENANT_ID,
            "WXO_API_KEY": _API_KEY,
            "WXO_TOKEN_URL": _TOKEN_URL,
        })

    merged = []
    seen = set()

    for item in existing_env:
        name = item.get("name") if isinstance(item, dict) else None
        if not name:
            continue

        if name in wxo_values:
            merged.append({"name": name, "value": wxo_values[name]})
        else:
            merged.append(item)

        seen.add(name)

    for name, value in wxo_values.items():
        if name not in seen:
            merged.append({"name": name, "value": value})

    update_mask = "spec.packageSpec.pickleObjectGcsUri,spec.deploymentSpec.env"
    url = (
        "https://"
        + GCP_REGION
        + "-aiplatform.googleapis.com/v1beta1/"
        + current_name
        + "?updateMask="
        + _up.quote(update_mask, safe=".,")
    )

    body = {
        "name": current_name,
        "spec": {
            "packageSpec": {
                "pickleObjectGcsUri": new_pickle_uri,
            },
            "deploymentSpec": {
                "env": merged,
            },
        },
    }

    if current_etag:
        body["etag"] = current_etag

    req = Request(
        url,
        data=json.dumps(body).encode(),
        headers={
            "Authorization": "Bearer " + _gcp_token(),
            "Content-Type": "application/json",
        },
        method="PATCH",
    )

    try:
        with urlopen(req, timeout=120, context=ssl.create_default_context()) as r:
            op = json.loads(r.read())
            _wait_for_operation(op)
            return op
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            "Reasoning Engine combined PATCH failed.\n"
            f"HTTP {exc.code}: {detail}\n"
            f"URL: {url}\n"
        ) from exc


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    print("=" * 72)
    print("  Vertex Reasoning Engine | patch existing agent with WXO tracing")
    print("=" * 72)

    missing = []
    if not REASONING_ENGINE_ID: missing.append("REASONING_ENGINE_ID")
    if _MODE == "cpd":
        if not _CPD_HOST:       missing.append("CPD_HOST_URL")
        if not _CPD_USER:       missing.append("CPD_USERNAME")
        if not _CPD_PASS:       missing.append("CPD_PASSWORD")
        if not _CPD_IID:        missing.append("CPD_INSTANCE_ID")
        if not _CPD_NS:         missing.append("CPD_NAMESPACE")
    else:
        if not _EXPORT_URL:     missing.append("WXO_OTEL_EXPORT_URL")
        if not _TENANT_ID and not _extract_tenant_id(_EXPORT_URL): missing.append("WXO_TENANT_ID")
        if not _API_KEY:        missing.append("WXO_API_KEY")
        if not _TOKEN_URL:      missing.append("WXO_TOKEN_URL")
    if missing:
        print("Missing required env vars: " + ", ".join(missing))
        sys.exit(1)

    if not SA_KEY_RAW:
        raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS is required by this script (base64-encoded JSON or path)")

    _gcp_token()
    print("GCP credentials valid")
    print("engine      : " + REASONING_ENGINE_ID)
    print("agent_id    : " + _AGENT_ID)
    print("agent_name  : " + _AGENT_NAME)
    print("environment : " + _ENVIRONMENT)

    print("\n[1/5] Reading existing Reasoning Engine ...")
    engine = _get_engine_resource()
    print("      resource: " + engine.get("name", _resource_name()))

    print("\n[2/5] Checking deployment type ...")
    pickle_uri = _get_pickle_uri(engine)
    print("      packageSpec.pickleObjectGcsUri: " + pickle_uri)

    print("\n[3/5] Downloading the ACTUAL existing agent pickle ...")
    import cloudpickle as _cp
    
    try:
        original_bytes = _download_pickle(pickle_uri)
        print("      pickle downloaded successfully")
    except Exception as e:
        raise RuntimeError(f"Failed to download pickle: {e}")
    
    try:
        inner_agent = _cp.loads(original_bytes)
        print(
            "      loaded: "
            + type(inner_agent).__module__
            + "."
            + type(inner_agent).__name__
        )
    except Exception as e:
        raise RuntimeError(
            f"Failed to unpickle agent. The original agent may have unresolvable imports. "
            f"Error: {e}"
        )

    print("\n      Wrapping existing agent with WxoTracingWrapper ...")
    print("      (Enhanced to handle both Vertex AI response formats)")
    
    try:
        wrapped_agent = WxoTracingWrapper(inner_agent)
        wrapped_bytes = _cp.dumps(wrapped_agent)
        print(f"      wrapped pickle size: {len(wrapped_bytes):,} bytes")
    except Exception as e:
        raise RuntimeError(f"Failed to wrap and pickle agent: {e}")

    print("\n[4/5] Uploading wrapped pickle ...")
    try:
        new_pickle_uri = _upload_pickle(pickle_uri, wrapped_bytes)
        print("      new pickle: " + new_pickle_uri)
    except Exception as e:
        raise RuntimeError(f"Failed to upload wrapped pickle: {e}")

    print("\n[5/5] Updating packageSpec.pickleObjectGcsUri and deploymentSpec.env ...")
    try:
        operation = _patch_pickle_and_env(new_pickle_uri)
        print("      update completed")
        print("      operation: " + str(operation.get("name", operation)))
    except Exception as e:
        print(f"\n✗ Failed to update Reasoning Engine: {e}")
        raise

    print("\n✓ Deployment successful!")
    print("The existing agent object was loaded, wrapped, and redeployed.")
    print("\nThe wrapper now handles both Vertex AI response formats:")
    print("  • Format 1 (Detailed): output.content.parts + usage_metadata")
    print("  • Format 2 (Simplified): output.result.parts + tool_calls")
    print("\nAll traces will be sent to WXO with complete metadata.")


if __name__ == "__main__":
    main()
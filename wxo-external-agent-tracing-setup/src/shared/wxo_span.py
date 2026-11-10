"""
shared/wxo_span.py
==================
Single canonical implementation of the primitives every WXO tracing
component needs:

    count_tokens(text)                      → int
    get_bearer_token(api_key, token_url)    → str   (cloud: IBM IAM, thread-safe, per-tenant TTL-cached)
    get_cpd_bearer_token(user, pw, host)    → str   (CPD: POST /icp4d-api/v1/authorize, TTL-cached)
    get_wxo_bearer_token(api_key, token_url)→ str   (picks cloud or CPD from WXO_DEPLOYMENT_MODE)
    resolve_export_url()                    → str   (WXO_OTEL_EXPORT_URL, or built from CPD_* in cpd mode)
    build_otlp_payload(...)                 → dict  (WXO-compatible OTLP JSON — root span)
    build_child_span(...)                   → dict  (OTLP span dict — child of a root span)
    post_to_wxo(payload, ...)               → str   (job_id, retries on 5xx)

Deployment mode — WXO_DEPLOYMENT_MODE (default "cloud")
-------------------------------------------------------
  cloud   IBM Cloud SaaS.  Token = API key → IBM IAM (API_KEY + TOKEN_URL).
          Export URL = WXO_OTEL_EXPORT_URL.  x-ibm-tenant-id header is sent.
  cpd     Cloud Pak for Data (on-prem).  Token = username/password →
          POST <CPD_HOST_URL>/icp4d-api/v1/authorize.
          Export URL = <CPD_HOST_URL>/<CPD_NAMESPACE>/instances/<CPD_INSTANCE_ID>/v1/agentops-v3/traces
          (or WXO_OTEL_EXPORT_URL when set explicitly).  No tenant header.
          TLS verification is skipped unless CPD_VERIFY_TLS=true (self-signed certs).

Used by:
  • container_hook/sitecustomize.py   (AWS Runtime + Vertex selfhosted hook)
  • azure/sitecustomize.py            (Azure hosted agent hook)
  • azure/function_app.py             (Azure prompt-agent Function App)
  • aws/agentcore_trace_hook.py       (AWS Lambda OTLP collector)

Design constraints
------------------
• Stdlib-only (no third-party deps) — all consumers are injected into
  containers or Lambdas where adding deps is non-trivial.
• Thread-safe, per-tenant bearer token cache — multiple tenants can share
  the same platform instance.  The cache is keyed by (api_key, token_url)
  so each tenant credential pair gets its own independent TTL.
• No logging config here — each consumer sets up its own logger and passes
  a logger instance to post_to_wxo() to keep noise under control.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import ssl
import threading
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# ---------------------------------------------------------------------------
# Deployment mode — "cloud" (IBM Cloud SaaS, default) or "cpd" (on-prem CPD)
# ---------------------------------------------------------------------------

def deployment_mode() -> str:
    """Return "cpd" or "cloud" from WXO_DEPLOYMENT_MODE (anything else → "cloud")."""
    mode = os.environ.get("WXO_DEPLOYMENT_MODE", "cloud").strip().lower()
    return "cpd" if mode == "cpd" else "cloud"


def ssl_context() -> ssl.SSLContext:
    """TLS context for WXO calls.  CPD uses self-signed certs, so verification is
    skipped in cpd mode unless CPD_VERIFY_TLS=true."""
    ctx = ssl.create_default_context()
    if (deployment_mode() == "cpd"
            and os.environ.get("CPD_VERIFY_TLS", "false").strip().lower() not in ("1", "true", "yes")):
        ctx.check_hostname = False
        ctx.verify_mode    = ssl.CERT_NONE
    return ctx


def build_cpd_export_url(host_url: str, namespace: str, instance_id: str) -> str:
    """<host>/<namespace>/instances/<instance_id>/v1/agentops-v3/traces ("" if any part is missing)."""
    if host_url and namespace and instance_id:
        return f"{host_url.rstrip('/')}/{namespace}/instances/{instance_id}/v1/agentops-v3/traces"
    return ""


def resolve_export_url() -> str:
    """WXO_OTEL_EXPORT_URL wins in both modes; in cpd mode it is otherwise built from CPD_*."""
    explicit = os.environ.get("WXO_OTEL_EXPORT_URL") or os.environ.get("OTEL_EXPORT_URL", "")
    if explicit or deployment_mode() != "cpd":
        return explicit
    return build_cpd_export_url(os.environ.get("CPD_HOST_URL", ""),
                                os.environ.get("CPD_NAMESPACE", ""),
                                os.environ.get("CPD_INSTANCE_ID", ""))


def extract_tenant_id(export_url: str = "") -> str:
    """Extract tenant/instance ID from an OTEL export URL or environment."""
    url = export_url or os.environ.get("WXO_OTEL_EXPORT_URL") or os.environ.get("OTEL_EXPORT_URL", "")
    if url:
        m = re.search(r'/instances/([^/?#]+)', url)
        if m:
            return m.group(1).strip()
    return (os.environ.get("WXO_TENANT_ID") or os.environ.get("TENANT_ID", "")).strip()


# ---------------------------------------------------------------------------
# Token counting — stdlib cl100k_base approximation (no tiktoken dependency)
# ---------------------------------------------------------------------------

_TOKEN_PAT = re.compile(
    r"(?i:'s|'t|'re|'ve|'m|'ll|'d)|[^\W\d_]+|\d{1,3}|[^\w\s]+",
    re.UNICODE,
)


def count_tokens(text: str) -> int:
    """Approximate BPE token count using a stdlib regex. Good enough for telemetry."""
    return len(_TOKEN_PAT.findall(text)) if text else 0


# ---------------------------------------------------------------------------
# Bearer token cache — thread-safe, TTL-aware, keyed per (api_key, token_url)
# so multiple tenants on the same platform instance each get an isolated cache.
# ---------------------------------------------------------------------------

_TOKEN_CACHE: dict[tuple[str, str], dict] = {}
_TOKEN_LOCK  = threading.Lock()
_TOKEN_REFRESH_MARGIN = 300   # refresh 5 min before expiry


def get_bearer_token(api_key: str, token_url: str, logger=None) -> str:
    """
    Exchange *api_key* for an IBM IAM bearer token.

    The cache is keyed by (api_key, token_url) so different tenant
    credentials never share a cached token — full tenant isolation.

    Returns a cached token while it has more than _TOKEN_REFRESH_MARGIN
    seconds left.  Returns "" (silently) if api_key or token_url are empty.
    Raises RuntimeError on HTTP / network errors (caller decides whether to
    swallow).
    """
    if not api_key or not token_url:
        return ""

    cache_key = (api_key, token_url)
    now = time.time()
    with _TOKEN_LOCK:
        entry = _TOKEN_CACHE.get(cache_key, {})
        if entry.get("token") and now < entry.get("expires_at", 0):
            return entry["token"]

    # iam.cloud.ibm.com / iam.test.cloud.ibm.com use form-encoded grant;
    # account-iam.* and other older endpoints accept JSON {"apikey": ...}.
    if "/identity/token" in token_url:
        from urllib.parse import urlencode as _ue
        _data  = _ue({"grant_type": "urn:ibm:params:oauth:grant-type:apikey",
                      "apikey": api_key}).encode()
        _ctype = "application/x-www-form-urlencoded"
    else:
        _data  = json.dumps({"apikey": api_key}).encode()
        _ctype = "application/json"

    req = Request(
        token_url,
        data=_data,
        headers={"Content-Type": _ctype, "Accept": "application/json", "User-Agent": "curl/7.68.0"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=30, context=ssl.create_default_context()) as resp:
            body = json.loads(resp.read())
    except HTTPError as exc:
        raise RuntimeError(
            f"Token exchange failed ({exc.code}): {exc.read().decode()[:200]}"
        ) from exc
    except URLError as exc:
        raise RuntimeError(f"Token exchange failed: {exc.reason}") from exc

    token = body.get("token") or body.get("access_token") or body.get("iam_token", "")
    if not token:
        raise RuntimeError(f"No token in IAM response: {list(body.keys())}")

    raw_ttl = int(body.get("expires_in", 3600) or 3600)
    ttl     = max(raw_ttl - _TOKEN_REFRESH_MARGIN, 60)
    with _TOKEN_LOCK:
        _TOKEN_CACHE[cache_key] = {"token": token, "expires_at": now + ttl}

    if logger:
        logger.info(f"Bearer token refreshed (ttl={raw_ttl}s, cached for {ttl}s)")
    return token


# CPD tokens are valid for ~12 h; /authorize does not return expires_in.
_CPD_TOKEN_CACHE: dict[tuple[str, str], dict] = {}
_CPD_TOKEN_TTL = 43200


def get_cpd_bearer_token(username: str, password: str, host_url: str, logger=None) -> str:
    """
    Obtain a CPD bearer token via POST <host>/icp4d-api/v1/authorize.

    Cache is keyed by (username, host_url).  Returns "" silently when any
    argument is empty; raises RuntimeError on HTTP / network errors.
    """
    if not username or not password or not host_url:
        return ""

    cache_key = (username, host_url.rstrip("/"))
    now = time.time()
    with _TOKEN_LOCK:
        entry = _CPD_TOKEN_CACHE.get(cache_key, {})
        if entry.get("token") and now < entry.get("expires_at", 0):
            return entry["token"]

    req = Request(
        host_url.rstrip("/") + "/icp4d-api/v1/authorize",
        data=json.dumps({"username": username, "password": password}).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json",
                 "User-Agent": "curl/7.68.0"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=30, context=ssl_context()) as resp:
            body = json.loads(resp.read())
    except HTTPError as exc:
        raise RuntimeError(
            f"CPD token exchange failed ({exc.code}): {exc.read().decode()[:200]}"
        ) from exc
    except URLError as exc:
        raise RuntimeError(f"CPD token exchange failed: {exc.reason}") from exc

    token = body.get("token", "")
    if not token:
        raise RuntimeError(f"No token in CPD /authorize response: {list(body.keys())}")

    ttl = _CPD_TOKEN_TTL - _TOKEN_REFRESH_MARGIN
    with _TOKEN_LOCK:
        _CPD_TOKEN_CACHE[cache_key] = {"token": token, "expires_at": now + ttl}
    if logger:
        logger.info(f"CPD bearer token refreshed (cached for {ttl}s)")
    return token


def get_wxo_bearer_token(api_key: str = "", token_url: str = "", logger=None) -> str:
    """
    Mode-aware token fetch.
      cpd   → CPD_USERNAME / CPD_PASSWORD / CPD_HOST_URL from the environment
              (api_key / token_url are ignored).
      cloud → IBM IAM exchange of *api_key* at *token_url*.
    """
    if deployment_mode() == "cpd":
        return get_cpd_bearer_token(os.environ.get("CPD_USERNAME", ""),
                                    os.environ.get("CPD_PASSWORD", ""),
                                    os.environ.get("CPD_HOST_URL", ""), logger=logger)
    return get_bearer_token(api_key, token_url, logger=logger)


# ---------------------------------------------------------------------------
# OTLP span helpers
# ---------------------------------------------------------------------------

def _sv(k: str, v) -> dict:
    return {"key": k, "value": {"stringValue": str(v)}}

def _iv(k: str, v) -> dict:
    return {"key": k, "value": {"intValue": int(v)}}


def build_otlp_payload(
    *,
    # Identity
    agent_id: str,
    agent_name: str,
    tenant_id: str,
    environment: str = "draft",
    # Trace data
    prompt: str,
    response: str,
    start_ns: int,
    end_ns: int,
    # Token counts (0 → estimated from text)
    input_tokens: int = 0,
    output_tokens: int = 0,
    # Error state
    is_error: bool = False,
    error_msg: str = "",
    # Platform tag — sets llm.system / framework span attributes
    platform: str = "cloud_agent",    # e.g. "aws_agentcore", "azure_ai_foundry", "google_vertex"
    # Actual model selected by the external agent (not the agent name)
    model_name: str = "",
    # Optional extras injected by specific platforms
    extra_attributes: list | None = None,
    # Session / correlation IDs (generated if not supplied)
    session_id: str = "",
    trace_id: str = "",
    span_id: str = "",
    # Authenticated user ID (from x-ibm-user-id / x-wxo-user-id header); generated if empty
    user_id: str = "",
    # Child spans to bundle in the same resourceSpan (list of span dicts from build_child_span)
    child_spans: list | None = None,
    # Tool calls — list of dicts: {name, input, output, start_ns, end_ns, is_error}
    # Each becomes a TOOL span (child of generate_content).
    # When empty and no child_spans, one synthetic retrieval span is still added.
    tool_calls: list | None = None,
    # Retrieval calls — list of dicts: {query, result, start_ns, end_ns, is_error}
    # Each becomes a RETRIEVER span (sibling of TOOL spans under generate_content).
    # When None (default) one synthetic retrieval span is added automatically.
    # Pass [] explicitly to suppress synthetic retrieval.
    retrieval_calls: list | None = None,
    # Reasoning / thinking steps — each string becomes a gen_ai.reasoning span event
    # on the root span, matching the ``steps`` shape emitted by wxo-server LangGraph.
    reasoning_steps: list[str] | None = None,
) -> dict:
    """
    Build a WXO-compatible synthetic OTLP JSON payload containing a root span
    and, optionally, pre-built child spans.

    I/O encoding
    ------------
    Input and output are emitted as JSON message arrays under
    ``gen_ai.input.messages`` / ``gen_ai.output.messages`` — the format the
    WXO server-side enrichment (_enrich_external_agent_json) reads to produce
    ``langfuse.observation.input`` / ``langfuse.observation.output`` for
    proper UI rendering.  Plain-string copies are kept under ``input.value``
    and ``output.value`` for ClickHouse / backwards compatibility.

    Token counts: if both input_tokens and output_tokens are 0, they are
    estimated with count_tokens() and tokens.estimated is set to "true".
    """
    tokens_estimated = input_tokens == 0 and output_tokens == 0
    if tokens_estimated:
        input_tokens  = count_tokens(prompt)
        output_tokens = count_tokens(response)
    total_tokens = input_tokens + output_tokens

    _trace_id   = trace_id   or uuid.uuid4().hex
    _span_id    = span_id    or secrets.token_hex(8)
    _session_id = session_id or str(uuid.uuid4())
    _message_id = str(uuid.uuid4())
    _user_id    = user_id    or f"usr_{uuid.uuid4().hex[:12]}"
    _span_name  = f"invoke_agent {agent_name}"
    _model_name = model_name or agent_name
    _latency_ms = max(1, (end_ns - start_ns) // 1_000_000)

    # Encode I/O as JSON message arrays — consumed by _enrich_external_agent_json
    # in the WXO server to populate langfuse.observation.input / output.
    input_messages  = json.dumps([{"role": "user",      "content": prompt}])
    output_messages = json.dumps([{"role": "assistant", "content": response}])

    # Structured WXO message envelope — matches the shape emitted by wxo-server's
    # LangGraph pipeline so the Langfuse UI renders a rich input object on the trace.
    _input_envelope = json.dumps({
        "role": "user",
        "content": prompt,
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
        "session_id": _session_id,
        "trace_id": None,
    })

    _workspace_id = "00000000-0000-0000-0000-000000000001"
    _langfuse_tags = json.dumps([
        f"agent_id:{agent_id}",
        f"environment:{environment}",
        f"tenant_id:{tenant_id}",
        f"workspace_id:{_workspace_id}",
    ])

    attributes: list = [
        # Agent identity
        _sv("agent.id",              agent_id),
        _sv("agent.name",            agent_name),
        _sv("agent.display_name",    agent_name),
        _sv("agent.version",         "1"),
        _sv("gen_ai.operation.name", "invoke_agent"),
        _sv("gen_ai.agent.id",       agent_id),
        _sv("gen_ai.agent.name",     agent_name),
        # Session / thread correlation
        _sv("thread.id",             _session_id),
        _sv("conversation.id",       _session_id),
        _sv("session.id",            _session_id),
        _sv("langfuse.session.id",   _session_id),
        _sv("langfuse.user.id",      _user_id),
        _sv("message.id",            _message_id),
        _sv("environment.name",      environment),
        _sv("environment.id",        environment),
        _sv("workspace.id",          _workspace_id),
        _sv("instance.id",           tenant_id),
        _sv("tenant.id",             tenant_id),
        # WXO facet attributes — tag generation and routing
        _sv("wxo.facet.tenant_id",    tenant_id),
        _sv("wxo.facet.workspace_id", _workspace_id),
        _sv("wxo.facet.agent_id",     agent_id),
        _sv("wxo.facet.workflow_id",  _span_name),
        _sv("wxo.channel.name",       "external_agent"),
        _sv("wxo.channel.type",       "text"),
        # Langfuse trace-level markers
        _sv("langfuse.internal.as_root", "true"),
        _sv("langfuse.trace.name",    _span_name),
        _sv("langfuse.tags",          _langfuse_tags),
        _sv("is.root",                "true"),
        _sv("global_transaction_id",  _trace_id),
        # Primary I/O — server enrichment (_enrich_external_agent_json) reads these and
        # appends langfuse.observation.input / langfuse.observation.output from them.
        # Do NOT pre-set langfuse.observation.* here — the server appends them last and
        # Langfuse uses the last duplicate value, so pre-setting would be overwritten anyway.
        _sv("gen_ai.input.messages",  input_messages),
        _sv("gen_ai.output.messages", output_messages),
        # Structured WXO message envelope — gives the Langfuse trace a rich input object
        _sv("gen_ai.message.input",   _input_envelope),
        # Flat-string copies for ClickHouse / backwards-compat
        _sv("input.value",           prompt),
        _sv("output.value",          response),
        _sv("gen_ai.task.input",     prompt),
        _sv("gen_ai.task.output",    response),
        _sv("input",                 prompt),
        _sv("output",                response),
        # Platform
        _sv("llm.model_name",         _model_name),
        _sv("model",                  _model_name),
        _sv("gen_ai.response.model",  _model_name),
        _sv("llm.system",             platform),
        _sv("framework",              platform),
        # Status
        _sv("agent.execution.status", "error" if is_error else "success"),
        _sv("agent.business_outcome", "failed" if is_error else "success"),
        _sv("tokens.estimated",       str(tokens_estimated).lower()),
        # Root is the AGENT orchestration wrapper — AGENT kind so Langfuse renders
        # it as the trace root.  Token counts still carried here for ClickHouse rollup.
        _sv("openinference.span.kind",         "AGENT"),
        _sv("gen_ai.system",                   platform),
        _sv("gen_ai.request.model",            _model_name),
        # Timing
        _iv("latency_ms",                      _latency_ms),
        # Token counts on root for ClickHouse rollup
        _iv("llm.usage.prompt_tokens",         input_tokens),
        _iv("llm.usage.completion_tokens",     output_tokens),
        _iv("llm.usage.total_tokens",          total_tokens),
        _iv("gen_ai.usage.prompt_tokens",      input_tokens),
        _iv("gen_ai.usage.completion_tokens",  output_tokens),
        _iv("gen_ai.usage.input_tokens",       input_tokens),
        _iv("gen_ai.usage.output_tokens",      output_tokens),
        _iv("llm.token_count.prompt",          input_tokens),
        _iv("llm.token_count.completion",      output_tokens),
        _iv("llm.token_count.total",           total_tokens),
        _sv("provided_usage_details", json.dumps({
            "input": input_tokens, "output": output_tokens, "total": total_tokens,
        })),
        _sv("langfuse.observation.usage_details", json.dumps({
            "input": input_tokens, "output": output_tokens, "total": total_tokens,
        })),
    ]

    # Error details
    if is_error and error_msg:
        attributes.append(_sv("error.type",    f"{platform.title().replace('_','')}Error"))
        attributes.append(_sv("error.message", error_msg[:4000]))

    # Caller-supplied extras (e.g. azure.session.id, aws.agent.runtime.id)
    if extra_attributes:
        attributes.extend(extra_attributes)

    # Reasoning step events — each entry becomes a ``steps`` row in the Langfuse
    # trace, matching the shape emitted by WXO's internal LangGraph pipeline.
    _step_events: list[dict] = []
    for _step_text in (reasoning_steps or []):
        if _step_text:
            _step_events.append({
                "name": "gen_ai.reasoning",
                "timeUnixNano": start_ns,
                "attributes": [
                    _sv("gen_ai.reasoning.content", str(_step_text)[:4000]),
                    _sv("langfuse.step.type",        "reasoning"),
                    _sv("langfuse.step.name",        f"generate_content {_model_name}"),
                ],
            })

    root_span = {
        "traceId":            _trace_id,
        "spanId":             _span_id,
        "name":               _span_name,
        "kind":               2,
        "startTimeUnixNano":  start_ns,
        "endTimeUnixNano":    end_ns,
        "status":             {"code": 2 if is_error else 0},
        "attributes":         attributes,
        **({"events": _step_events} if _step_events else {}),
    }

    # ── Synthetic child span tree: call_llm → generate_content <model> ────────
    # Mirrors the harness 4-level hierarchy so the WXO trace view shows the same
    # nesting as AgentCore harness traces.
    # Only added when no OTel child spans were captured (child_spans is empty),
    # to avoid doubling up when the agent framework already emits its own spans.
    _synthetic: list = []
    if not child_spans:
        _llm_id    = secrets.token_hex(8)
        _gen_id    = secrets.token_hex(8)
        _llm_start = start_ns + max(1_000_000, (end_ns - start_ns) // 20)
        _llm_end   = end_ns   - max(1_000_000, (end_ns - start_ns) // 20)
        _gen_start = _llm_start + max(500_000, (_llm_end - _llm_start) // 20)
        _gen_end   = _llm_end   - max(500_000, (_llm_end - _llm_start) // 20)
        _usage_json = json.dumps({"input": input_tokens, "output": output_tokens, "total": total_tokens})
        # call_llm is a CHAIN wrapper (not a GENERATION).  WXO usage metrics
        # SUM every observation with type=GENERATION, so putting usage/model
        # on both call_llm (LLM) and generate_content doubled token counts and
        # hid a stable model_id rollup.
        _llm_attrs = [
            _sv("openinference.span.kind",         "CHAIN"),
            _sv("gen_ai.request.model",            _model_name),
            _sv("gen_ai.response.model",           _model_name),
            _sv("llm.model_name",                  _model_name),
            _sv("model",                           _model_name),
            _sv("gen_ai.system",                   platform),
            _sv("gen_ai.input.messages",           input_messages),
            _sv("gen_ai.output.messages",          output_messages),
        ]
        _synthetic.append({
            "traceId":           _trace_id,
            "spanId":            _llm_id,
            "parentSpanId":      _span_id,
            "name":              "call_llm",
            "kind":              3,
            "startTimeUnixNano": _llm_start,
            "endTimeUnixNano":   _llm_end,
            "status":            {"code": 2 if is_error else 0},
            "attributes":        _llm_attrs,
        })
        _gen_attrs = [
            _sv("openinference.span.kind",         "LLM"),
            _sv("gen_ai.request.model",            _model_name),
            _sv("gen_ai.response.model",           _model_name),
            _sv("llm.model_name",                  _model_name),
            _sv("model",                           _model_name),
            _sv("gen_ai.system",                   platform),
            _sv("gen_ai.prompt",                   prompt[:2000]),
            _sv("gen_ai.completion",               response[:2000]),
            _sv("gen_ai.input.messages",           input_messages),
            _sv("gen_ai.output.messages",          output_messages),
            _iv("gen_ai.usage.input_tokens",       input_tokens),
            _iv("gen_ai.usage.output_tokens",      output_tokens),
            _iv("gen_ai.usage.prompt_tokens",      input_tokens),
            _iv("gen_ai.usage.completion_tokens",  output_tokens),
            _iv("llm.usage.prompt_tokens",         input_tokens),
            _iv("llm.usage.completion_tokens",     output_tokens),
            _iv("llm.token_count.prompt",          input_tokens),
            _iv("llm.token_count.completion",      output_tokens),
            _iv("llm.token_count.total",           total_tokens),
            _sv("provided_usage_details",                  _usage_json),
            _sv("langfuse.observation.usage_details",      _usage_json),
        ]
        _synthetic.append({
            "traceId":           _trace_id,
            "spanId":            _gen_id,
            "parentSpanId":      _llm_id,
            "name":              f"generate_content {_model_name}",
            "kind":              3,
            "startTimeUnixNano": _gen_start,
            "endTimeUnixNano":   _gen_end,
            "status":            {"code": 2 if is_error else 0},
            "attributes":        _gen_attrs,
        })

        # ── TOOL spans (children of generate_content, with optional sub-tools) ──
        # Each tool_call dict may carry a "sub_calls" list of nested tool invocations
        # (e.g. a search tool that itself fans out to document-fetch sub-tools).
        # Sub-calls are emitted as TOOL spans whose parent is the enclosing tool span,
        # producing the full nesting:
        #   generate_content
        #     └── search_tool            (TOOL)
        #           └── fetch_document   (TOOL — sub-call)
        #           └── fetch_document   (TOOL — sub-call)
        def _emit_tool_spans(tc_list, parent_id, window_start, window_end, target, _depth=0):
            """Recursively emit TOOL spans and their sub_calls into *target* list.

            Depth-aware span kind:
              depth=0 + has sub_calls → CHAIN  (Langfuse renders as collapsible
                                                container showing tool name + I/O)
              depth>0 or no sub_calls → TOOL   (leaf tool invocation node)

            This ensures the primary tool (e.g. "calculate") is visible as a
            named container in the trace view, with its sub-call ("verify_result")
            nested inside it — rather than the parent being collapsed away.
            """
            _count = len(tc_list)
            _window = max(1, window_end - window_start)
            _slot   = _window // (_count + 1) if _count else _window
            for _idx, _tc in enumerate(tc_list):
                _ts = _tc.get("start_ns") or (window_start + _slot * (_idx + 1))
                _te = _tc.get("end_ns")   or (_ts + max(1_000_000, _slot // 2))
                _ts = max(window_start, min(_ts, window_end - 1_000_000))
                _te = max(_ts + 1_000_000, min(_te, window_end))
                _tn = str(_tc.get("name", f"tool_{_idx}"))
                _sid = secrets.token_hex(8)
                _sub = _tc.get("sub_calls") or []
                # Parent tool with sub_calls → CHAIN so Langfuse shows it as a
                # collapsible wrapper; leaf tools → TOOL.
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
                target.append({
                    "traceId":           _trace_id, "spanId": _sid,
                    "parentSpanId":      parent_id,
                    "name":              _tn, "kind": 3,
                    "startTimeUnixNano": _ts, "endTimeUnixNano": _te,
                    "status":            {"code": 2 if _tc.get("is_error") else 0},
                    "attributes":        _ta,
                })
                if _sub:
                    _emit_tool_spans(_sub, _sid, _ts, _te, target, _depth + 1)

        _tc_list  = tool_calls or []
        _tc_count = len(_tc_list)
        _gen_window = max(1, _gen_end - _gen_start)
        _emit_tool_spans(_tc_list, _gen_id, _gen_start, _gen_end, _synthetic)

        # ── RETRIEVER span (child of generate_content) ─────────────────────────
        # retrieval_calls=None  → add one synthetic retrieval span (default)
        # retrieval_calls=[]    → suppress (caller explicitly opted out)
        # retrieval_calls=[...] → one span per entry with real query/result
        _rc_list = retrieval_calls if retrieval_calls is not None else [{}]
        _rc_count = len(_rc_list)
        _rc_slot  = _gen_window // (_rc_count + _tc_count + 1) if _rc_count else _gen_window
        # Place retrieval spans after tool spans in the generate_content window
        _rc_offset = _tc_count
        for _j, _rc in enumerate(_rc_list):
            _rc_start = _rc.get("start_ns") or (_gen_start + _rc_slot * (_rc_offset + _j + 1))
            _rc_end   = _rc.get("end_ns")   or (_rc_start + max(1_000_000, _rc_slot // 2))
            _rc_start = max(_gen_start, min(_rc_start, _gen_end - 1_000_000))
            _rc_end   = max(_rc_start + 1_000_000, min(_rc_end, _gen_end))
            _rc_attrs = [
                _sv("openinference.span.kind", "RETRIEVER"),
                _sv("retrieval.source",        _rc.get("source", "knowledge_base")),
            ]
            if _rc.get("query"):
                _rc_attrs.append(_sv("input.value",          _rc["query"][:2000]))
                _rc_attrs.append(_sv("retrieval.query",      _rc["query"][:2000]))
            if _rc.get("result"):
                _rc_attrs.append(_sv("output.value",         _rc["result"][:2000]))
                _rc_attrs.append(_sv("retrieval.documents",  _rc["result"][:2000]))
            _synthetic.append({
                "traceId":           _trace_id, "spanId": secrets.token_hex(8),
                "parentSpanId":      _gen_id,
                "name":              _rc.get("name", "retrieval"), "kind": 3,
                "startTimeUnixNano": _rc_start, "endTimeUnixNano": _rc_end,
                "status":            {"code": 2 if _rc.get("is_error") else 0},
                "attributes":        _rc_attrs,
            })

    # Bundle: root + synthetic children + any OTel-captured spans
    spans = [root_span] + _synthetic + (child_spans or [])

    return {
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
                _sv("environment.name",          environment),
                _sv("deployment.environment",    environment),
            ]},
            "scopeSpans": [{"scope": {"name": "wxo-universal-forwarder", "version": "2.0.0"}, "spans": spans}],
        }]
    }


def build_child_span(
    *,
    trace_id: str,
    parent_span_id: str,
    name: str,
    span_type: str = "llm",       # "llm" | "tool" | "retrieval" | "span"
    kind: int = 3,                 # CLIENT by default (LLM / tool calls go outbound)
    start_ns: int,
    end_ns: int,
    attributes: list | None = None,
    is_error: bool = False,
    error_msg: str = "",
    # LLM-specific convenience params (only used when span_type="llm" or "generate")
    model_name: str = "",
    input_tokens: int = 0,
    output_tokens: int = 0,
    prompt: str = "",
    response: str = "",
    # Tool-specific convenience params (only used when span_type="tool")
    tool_name: str = "",
    tool_input: str = "",
    tool_output: str = "",
) -> dict:
    """
    Build a single child span dict suitable for inclusion in ``child_spans``
    passed to ``build_otlp_payload``.

    Parameters
    ----------
    trace_id        : hex trace ID of the parent root span (no "0x" prefix)
    parent_span_id  : hex span ID of the parent / intermediate span
    name            : span name — e.g. "call_llm", "generate_content gemini-2.0-flash", "tool.invoke"
    span_type       : semantic type — controls ``openinference.span.kind`` and which
                      convenience attributes are injected:
                        "llm"        → openinference.span.kind=LLM  (call_llm wrapper)
                        "generate"   → openinference.span.kind=LLM  (generate_content leaf)
                        "tool"       → openinference.span.kind=TOOL
                        "retrieval"  → openinference.span.kind=RETRIEVAL
                        "span"       → openinference.span.kind=CHAIN (generic)
    kind            : OTLP span kind int (1=SERVER, 2=CLIENT, 3=PRODUCER, 4=CONSUMER, 5=INTERNAL)
    start_ns / end_ns : wall-clock nanoseconds
    attributes      : additional OTLP {"key": ..., "value": {...}} dicts (use _sv/_iv helpers);
                      these are appended AFTER the convenience attributes so callers can override
    is_error        : whether to mark the span status as ERROR
    error_msg       : short error description appended as error.message attribute

    LLM convenience (span_type in {"llm","generate"})
    -------------------------------------------------
    model_name      : LLM model identifier (e.g. "gemini-2.0-flash-001")
    input_tokens    : prompt token count (0 = omit)
    output_tokens   : completion token count (0 = omit)
    prompt          : prompt text (truncated to 2 000 chars)
    response        : completion text (truncated to 2 000 chars)

    Tool convenience (span_type="tool")
    ------------------------------------
    tool_name       : name of the tool / function called
    tool_input      : JSON-serialisable input (truncated to 2 000 chars)
    tool_output     : tool result text (truncated to 2 000 chars)
    """
    _OI_KIND = {
        "llm":       "LLM",
        "generate":  "LLM",
        "tool":      "TOOL",
        "retrieval": "RETRIEVAL",
        "span":      "CHAIN",
    }
    oi_kind = _OI_KIND.get(span_type, "CHAIN")

    span_id    = secrets.token_hex(8)
    latency_ms = max(1, (end_ns - start_ns) // 1_000_000)

    # ── Convenience attributes injected before caller extras ─────────────────
    attrs: list = [_sv("openinference.span.kind", oi_kind)]

    if span_type in ("llm", "generate"):
        if model_name:
            attrs.append(_sv("gen_ai.request.model",  model_name))
            attrs.append(_sv("llm.model_name",         model_name))
            attrs.append(_sv("gen_ai.system",          model_name))
        if prompt:
            attrs.append(_sv("gen_ai.prompt",          prompt[:2000]))
            attrs.append(_sv("gen_ai.input.messages",
                             json.dumps([{"role": "user", "content": prompt[:2000]}])))
        if response:
            attrs.append(_sv("gen_ai.completion",      response[:2000]))
            attrs.append(_sv("gen_ai.output.messages",
                             json.dumps([{"role": "assistant", "content": response[:2000]}])))
        if input_tokens or output_tokens:
            total = input_tokens + output_tokens
            attrs += [
                _iv("gen_ai.usage.input_tokens",      input_tokens),
                _iv("gen_ai.usage.output_tokens",     output_tokens),
                _iv("gen_ai.usage.prompt_tokens",     input_tokens),
                _iv("gen_ai.usage.completion_tokens", output_tokens),
                _iv("llm.usage.prompt_tokens",        input_tokens),
                _iv("llm.usage.completion_tokens",    output_tokens),
                _iv("llm.token_count.prompt",         input_tokens),
                _iv("llm.token_count.completion",     output_tokens),
                _iv("llm.token_count.total",          total),
                _sv("provided_usage_details", json.dumps({
                    "input": input_tokens, "output": output_tokens, "total": total,
                })),
            ]

    elif span_type == "tool":
        if tool_name:
            attrs.append(_sv("tool.name",     tool_name))
            attrs.append(_sv("gen_ai.tool.name", tool_name))
        if tool_input:
            attrs.append(_sv("tool.parameters", tool_input[:2000]))
            attrs.append(_sv("input.value",     tool_input[:2000]))
        if tool_output:
            # NB: no output.value on TOOL spans — WXO drops the span.
            attrs.append(_sv("tool.output",  tool_output[:2000]))

    # ── Caller-supplied extras (can override the above) ───────────────────────
    attrs.extend(attributes or [])
    attrs.append(_iv("latency_ms", latency_ms))

    if is_error and error_msg:
        attrs.append(_sv("error.type",    "ChildSpanError"))
        attrs.append(_sv("error.message", error_msg[:2000]))

    return {
        "traceId":            trace_id,
        "spanId":             span_id,
        "parentSpanId":       parent_span_id,
        "name":               name,
        "kind":               kind,
        "startTimeUnixNano":  start_ns,
        "endTimeUnixNano":    end_ns,
        "status":             {"code": 2 if is_error else 0},
        "attributes":         attrs,
    }


# ---------------------------------------------------------------------------
# HTTP POST to WXO — retries on 5xx, gives up on 4xx
# ---------------------------------------------------------------------------

def post_to_wxo(
    payload: dict,
    bearer_token: str,
    export_url: str,
    agent_id: str,
    tenant_id: str,
    logger=None,
    retries: int = 3,
) -> str:
    """
    POST *payload* to *export_url*.
    Returns job_id string on success.
    Retries up to *retries* times with exponential back-off on 5xx / network errors.
    4xx errors are not retried — they indicate a bad payload.
    Raises RuntimeError after all retries are exhausted.
    """
    data = json.dumps(payload).encode()
    headers = {
        "Authorization":                  f"Bearer {bearer_token}",
        "Content-Type":                   "application/json",
        "User-Agent":                     "curl/7.68.0",
        "x-ibm-agent-id":                 agent_id,
        "x-langfuse-ingestion-version":   "4",
    }
    if tenant_id and deployment_mode() == "cloud":   # CPD has no tenant header
        headers["x-ibm-tenant-id"] = tenant_id
        headers["x-tenant-id"]     = tenant_id
    ctx = ssl_context()

    trace_id = (
        payload.get("resourceSpans", [{}])[0]
               .get("scopeSpans", [{}])[0]
               .get("spans", [{}])[0]
               .get("traceId", "?")
    )

    last_exc: Exception | None = None
    for attempt in range(retries):
        req = Request(export_url, data=data, headers=headers, method="POST")
        try:
            with urlopen(req, timeout=30, context=ctx) as resp:
                resp_body = json.loads(resp.read() or b"{}")
                job_id    = resp_body.get("data", {}).get("id", "N/A")
                if logger:
                    logger.info(f"WXO POST {resp.status} trace_id={trace_id} job_id={job_id}")
                return job_id
        except HTTPError as exc:
            body = exc.read().decode()[:200]
            if exc.code < 500:
                # 4xx — bad payload, no point retrying
                raise RuntimeError(f"WXO POST {exc.code} (no retry): {body}") from exc
            last_exc = RuntimeError(f"WXO POST {exc.code}: {body}")
            if logger:
                logger.warning(f"WXO POST {exc.code} attempt {attempt+1}/{retries}: {body}")
        except URLError as exc:
            last_exc = RuntimeError(f"WXO POST network error: {exc.reason}")
            if logger:
                logger.warning(f"WXO POST network error attempt {attempt+1}/{retries}: {exc.reason}")
        except Exception as exc:
            last_exc = exc
            if logger:
                logger.warning(f"WXO POST error attempt {attempt+1}/{retries}: {exc}")

        if attempt < retries - 1:
            time.sleep(0.5 * (2 ** attempt))   # 0.5 s → 1 s → 2 s

    raise last_exc or RuntimeError("WXO POST failed after all retries")


def post_scores_to_wxo(
    scores: list[dict],
    bearer_token: str,
    export_url: str,
    agent_id: str,
    agent_name: str,
    trace_id: str,
    tenant_id: str,
    logger=None,
) -> None:
    """POST evaluation scores to the WXO scores endpoint.

    Derives the scores URL from *export_url* by replacing
    ``inject/traces`` with ``inject/scores``.  Silently skips when
    *scores* is empty or the URL cannot be derived.

    Each score dict must contain at least ``name`` and ``value``.
    ``traceId``, ``agentId``, and ``agentName`` are stamped automatically.
    """
    if not scores:
        return
    scores_url = export_url.replace("inject/traces", "inject/scores")
    if scores_url == export_url:
        if logger:
            logger.warning("[WXO] Cannot derive scores URL from export_url — skipping score POST")
        return

    stamped: list[dict] = []
    for sc in scores:
        entry = dict(sc)
        entry.setdefault("traceId",    trace_id)
        entry.setdefault("agentId",    agent_id)
        entry.setdefault("agentName",  agent_name)
        stamped.append(entry)

    payload = {"scores": stamped}
    data    = json.dumps(payload).encode()
    headers = {
        "Authorization":                  f"Bearer {bearer_token}",
        "Content-Type":                   "application/json",
        "User-Agent":                     "curl/7.68.0",
        "x-ibm-agent-id":                 agent_id,
        "x-langfuse-ingestion-version":   "4",
    }
    if tenant_id and deployment_mode() == "cloud":
        headers["x-ibm-tenant-id"] = tenant_id
        headers["x-tenant-id"]     = tenant_id
    ctx = ssl_context()
    req = Request(scores_url, data=data, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=30, context=ctx) as resp:
            if logger:
                logger.info(f"[WXO] scores POST {resp.status} trace_id={trace_id} n={len(stamped)}")
    except Exception as exc:
        if logger:
            logger.warning(f"[WXO] scores POST failed: {exc}")

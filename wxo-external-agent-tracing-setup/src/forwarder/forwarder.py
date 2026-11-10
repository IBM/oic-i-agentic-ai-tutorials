"""
forwarder/forwarder.py
======================
OTLP Trace Forwarder for IBM watsonx Orchestrate (WXO) Agent Analytics.

Ingests standard OpenTelemetry (OTLP/HTTP) trace payloads (JSON or Protobuf)
from any agent framework or platform (LangChain, LlamaIndex, CrewAI, AutoGen,
Semantic Kernel, Claude, OpenAI, custom SDKs, OTel Collectors), maps platform
agent IDs/models to WXO agent UUIDs and tenant configurations, transforms the
traces into WXO-compliant OTLP format, and posts them to WXO.
"""

from __future__ import annotations

import base64
import gzip
import hmac
import json
import logging
import os
import re
import secrets
import ssl
import struct
import sys
import threading
import time
import urllib.error
import urllib.parse
from urllib.request import Request, urlopen
import uuid

_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
log = logging.getLogger("wxo_otlp_forwarder")

# Token counting regex for fallback estimation
_TOKEN_PAT = re.compile(r"\w+|[^\w\s]", re.UNICODE)

# Thread-safe IAM token cache: (api_key, token_url) -> {"token": ..., "expires_at": ...}
_TOKEN_CACHE: dict[tuple[str, str], dict] = {}
_TOKEN_LOCK = threading.Lock()
_TOKEN_REFRESH_MARGIN = 300  # Refresh 5 mins before expiration


def count_tokens(text: str) -> int:
    """Fast approximation of token count."""
    return len(_TOKEN_PAT.findall(text)) if text else 0


# ── Deployment mode: "cloud" (IBM Cloud SaaS) or "cpd" (on-prem Cloud Pak for Data) ──
# cloud: API key → IAM token; tenant headers sent.
# cpd  : CPD_USERNAME/CPD_PASSWORD → <CPD_HOST_URL>/icp4d-api/v1/authorize;
#        no tenant header; TLS verification skipped unless CPD_VERIFY_TLS=true.
_CPD_TOKEN_TTL = 12 * 3600 - _TOKEN_REFRESH_MARGIN  # CPD tokens carry no expires_in


def deployment_mode() -> str:
    return "cpd" if os.environ.get("WXO_DEPLOYMENT_MODE", "cloud").strip().lower() == "cpd" else "cloud"


def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    if deployment_mode() == "cpd" and os.environ.get("CPD_VERIFY_TLS", "false").strip().lower() != "true":
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def cpd_export_url() -> str:
    """CPD traces URL: explicit override, else built from CPD_HOST_URL/NAMESPACE/INSTANCE_ID."""
    explicit = (os.environ.get("CPD_EXPORT_URL") or os.environ.get("WXO_OTEL_EXPORT_URL") or "").strip()
    if explicit:
        return explicit
    host = os.environ.get("CPD_HOST_URL", "").strip().rstrip("/")
    ns = os.environ.get("CPD_NAMESPACE", "").strip()
    iid = os.environ.get("CPD_INSTANCE_ID", "").strip()
    return f"{host}/{ns}/instances/{iid}/v1/agentops-v3/traces" if host and ns and iid else ""


def extract_tenant_id(export_url: str) -> str:
    """Extract tenant/instance ID from an OTEL export URL."""
    if export_url:
        m = re.search(r'/instances/([^/?#]+)', export_url)
        if m:
            return m.group(1).strip()
    return ""


def auth_configured(api_key: str) -> bool:
    """True when credentials for the active mode are available."""
    if deployment_mode() == "cpd":
        return all(os.environ.get(k, "").strip() for k in ("CPD_HOST_URL", "CPD_USERNAME", "CPD_PASSWORD"))
    return bool(api_key)


def get_cpd_bearer_token(logger=None) -> str:
    """Retrieve and cache a CPD bearer token (username/password → /icp4d-api/v1/authorize)."""
    host = os.environ.get("CPD_HOST_URL", "").strip().rstrip("/")
    username = os.environ.get("CPD_USERNAME", "").strip()
    password = os.environ.get("CPD_PASSWORD", "")
    if not host or not username or not password:
        return ""

    cache_key = ("cpd", username, host)
    now = time.time()
    with _TOKEN_LOCK:
        cached = _TOKEN_CACHE.get(cache_key)
        if cached and cached["expires_at"] > now:
            return cached["token"]

    req = Request(
        f"{host}/icp4d-api/v1/authorize",
        data=json.dumps({"username": username, "password": password}).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=30, context=_ssl_context()) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        if logger:
            logger.error(f"Failed to obtain CPD token from {host}: {exc}")
        return ""

    token = body.get("token") or ""
    if token:
        with _TOKEN_LOCK:
            _TOKEN_CACHE[cache_key] = {"token": token, "expires_at": now + _CPD_TOKEN_TTL}
    return token


def get_bearer_token(api_key: str, token_url: str, logger=None) -> str:
    """
    Retrieve and cache a WXO Bearer token for the active deployment mode.
    cloud: IBM Cloud IAM token from an API key (refreshes within 5 minutes of expiry).
    cpd:   CPD authorize token from username/password (api_key/token_url ignored).
    """
    if deployment_mode() == "cpd":
        return get_cpd_bearer_token(logger=logger)
    if not api_key or not token_url:
        return ""

    cache_key = (api_key, token_url)
    now = time.time()

    with _TOKEN_LOCK:
        cached = _TOKEN_CACHE.get(cache_key)
        if cached and cached["expires_at"] > now + _TOKEN_REFRESH_MARGIN:
            return cached["token"]

    is_cloud_iam = "/identity/token" in token_url
    if is_cloud_iam:
        data = urllib.parse.urlencode({
            "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
            "apikey": api_key,
        }).encode("utf-8")
        ctype = "application/x-www-form-urlencoded"
    else:
        data = json.dumps({"apikey": api_key}).encode("utf-8")
        ctype = "application/json"

    req = Request(
        token_url,
        data=data,
        headers={"Content-Type": ctype, "Accept": "application/json", "User-Agent": "curl/7.68.0"},
        method="POST",
    )

    try:
        ctx = ssl.create_default_context()
        with urlopen(req, timeout=30, context=ctx) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        if logger:
            logger.error(f"Failed to obtain IAM token from {token_url}: {exc}")
        return ""

    token = body.get("token") or body.get("access_token") or body.get("iam_token") or ""
    expires_in = int(body.get("expires_in", 3600))

    if token:
        with _TOKEN_LOCK:
            _TOKEN_CACHE[cache_key] = {
                "token": token,
                "expires_at": now + expires_in,
            }

    return token


def _sv(k: str, v) -> dict:
    """Helper for string attribute value in OTLP format."""
    return {"key": k, "value": {"stringValue": str(v)}}


def _iv(k: str, v) -> dict:
    """Helper for int attribute value in OTLP format."""
    return {"key": k, "value": {"intValue": int(v)}}


def _bv(k: str, v: bool) -> dict:
    """Helper for bool attribute value in OTLP format."""
    return {"key": k, "value": {"boolValue": bool(v)}}


# Map gen_ai.system values (and other signals) to a human-readable platform tag
# that becomes llm.system / framework in the forwarded WXO span.
_GEN_AI_SYSTEM_TO_PLATFORM: dict[str, str] = {
    # Azure
    "az.ai.inference":          "azure_ai_foundry",
    "azure_ai_foundry":         "azure_ai_foundry",
    "azure_openai":             "azure_ai_foundry",
    "openai":                   "openai",
    "microsoft.semantic_kernel":"azure_ai_foundry",
    # AWS
    "aws.bedrock":              "aws_agentcore",
    "aws_agentcore":            "aws_agentcore",
    "strands-agents":           "aws_agentcore",
    # Anthropic
    "anthropic":                "claude-platform",
    "claude-platform":          "claude-platform",
    # Vertex / Google
    "vertexai":                 "vertex_ai",
    "vertex_ai":                "vertex_ai",
    "google_vertex":            "vertex_ai",
    "google-cloud-aiplatform":  "vertex_ai",
    # Gemini (ADK direct)
    "gemini":                   "vertex_ai",
}


def _resolve_platform(attrs: dict, res_attrs: dict) -> str:
    """Derive a semantic platform tag from span + resource attributes."""
    gen_ai_sys = (
        attrs.get("gen_ai.system")
        or attrs.get("llm.system")
        or attrs.get("framework")
        or res_attrs.get("gen_ai.system")
        or ""
    ).lower().strip()
    if gen_ai_sys in _GEN_AI_SYSTEM_TO_PLATFORM:
        return _GEN_AI_SYSTEM_TO_PLATFORM[gen_ai_sys]
    # Fallback: service.name gives a human-readable tag
    return res_attrs.get("service.name") or "external_agent"


def build_otlp_payload(
    *,
    agent_id: str,
    agent_name: str,
    tenant_id: str,
    environment: str = "draft",
    prompt: str = "",
    response: str = "",
    start_ns: int = 0,
    end_ns: int = 0,
    input_tokens: int = 0,
    output_tokens: int = 0,
    is_error: bool = False,
    error_msg: str = "",
    platform: str = "external_agent",
    model_name: str = "",
    session_id: str = "",
    trace_id: str = "",
    span_id: str = "",
    user_id: str = "",
    tool_calls: list | None = None,
    extra_attributes: list | None = None,
    workspace_id: str = "",
    instance_id: str = "",
    reasoning_steps: list[str] | None = None,
) -> dict:
    """
    Build a WXO-compliant OTLP payload with the 4-level span tree WXO expects:

        invoke_agent <agent_name>          (AGENT root)
          └── call_llm                     (LLM wrapper — carries token counts)
                └── generate_content <model>  (LLM leaf — actual model call)
                      └── <tool_name>         (TOOL, one per tool call; optional)

    ``reasoning_steps`` is an optional list of reasoning/thinking text strings
    extracted from the upstream span (e.g. Anthropic extended-thinking, model
    chain-of-thought).  Each entry becomes a ``gen_ai.reasoning`` event on the
    root span so WXO can populate the Langfuse ``steps`` array, matching the
    structure emitted by the internal wxo-server LangGraph pipeline.
    """
    now_ns = int(time.time() * 1e9)
    _start_ns = start_ns or now_ns
    _end_ns = end_ns or (_start_ns + 1_000_000)
    if _end_ns <= _start_ns:
        _end_ns = _start_ns + 1_000_000

    tokens_estimated = (input_tokens == 0 and output_tokens == 0)
    if tokens_estimated:
        input_tokens = count_tokens(prompt)
        output_tokens = count_tokens(response)
    total_tokens = input_tokens + output_tokens

    _trace_id   = trace_id or uuid.uuid4().hex
    _span_id    = span_id or secrets.token_hex(8)
    _session_id = session_id or str(uuid.uuid4())
    _message_id = str(uuid.uuid4())
    _user_id    = user_id or f"usr_{uuid.uuid4().hex[:12]}"
    _span_name  = f"invoke_agent {agent_name}"
    _model_name = model_name or agent_name
    _latency_ms = max(1, (_end_ns - _start_ns) // 1_000_000)
    _workspace_id = workspace_id or "00000000-0000-0000-0000-000000000001"
    _instance_id  = instance_id or tenant_id  # fall back to tenant_id when not provided

    input_messages  = json.dumps([{"role": "user",      "content": prompt}])
    output_messages = json.dumps([{"role": "assistant", "content": response}])

    # WXO message envelope — mirrors the structured input object that WXO's own
    # LangGraph pipeline (wxo-server) emits on the root Langfuse trace.  External
    # agents must carry this as a span attribute so the trace's `input` field in
    # Langfuse is a rich object rather than a bare string.
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

    # WXO facet tags — mirrors what WXO's own LangGraph instrumentation emits so
    # the Langfuse UI shows rich metadata (tags, workspace facets, etc.) for all
    # external-agent platforms (AWS, Claude, Azure, Vertex).
    _langfuse_tags = json.dumps([
        f"agent_id:{agent_id}",
        f"environment:{environment}",
        f"tenant_id:{tenant_id}",
        f"workspace_id:{_workspace_id}",
    ])

    # ── Root span: invoke_agent (AGENT) ──────────────────────────────────────
    root_attrs = [
        _sv("agent.id",              agent_id),
        _sv("agent.name",            agent_name),
        _sv("agent.display_name",    agent_name),
        _sv("agent.version",         "1"),
        _sv("gen_ai.operation.name", "invoke_agent"),
        _sv("gen_ai.agent.id",       agent_id),
        _sv("gen_ai.agent.name",     agent_name),
        _sv("thread.id",             _session_id),
        _sv("conversation.id",       _session_id),
        _sv("session.id",            _session_id),
        _sv("langfuse.session.id",   _session_id),
        _sv("langfuse.user.id",      _user_id),
        _sv("message.id",            _message_id),
        _sv("environment.name",      environment),
        _sv("environment.id",        environment),
        _sv("workspace.id",          _workspace_id),
        _sv("instance.id",           _instance_id),
        _sv("tenant.id",             tenant_id),
        # WXO facet attributes — used by Langfuse for tag generation and routing
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
        _sv("gen_ai.input.messages",  input_messages),
        _sv("gen_ai.output.messages", output_messages),
        # Structured WXO message envelope — WXO reads this to set a rich input
        # object on the Langfuse trace (matching the wxo-server LangGraph shape)
        # instead of a bare string.
        _sv("gen_ai.message.input",   _input_envelope),
        _sv("input.value",   prompt),
        _sv("output.value",  response),
        _sv("gen_ai.task.input",  prompt),
        _sv("gen_ai.task.output", response),
        _sv("input",    prompt),
        _sv("output",   response),
        _sv("llm.model_name",       _model_name),
        _sv("model",                _model_name),
        _sv("gen_ai.request.model", _model_name),
        _sv("gen_ai.response.model", _model_name),
        _sv("llm.system",  platform),
        _sv("framework",   platform),
        _sv("gen_ai.system", platform),
        _sv("agent.execution.status", "error" if is_error else "success"),
        _sv("agent.business_outcome", "failed" if is_error else "success"),
        _sv("tokens.estimated", str(tokens_estimated).lower()),
        _sv("openinference.span.kind", "AGENT"),
        _sv("provided_usage_details", json.dumps(
            {"input": input_tokens, "output": output_tokens, "total": total_tokens}
        )),
        _iv("latency_ms",                  _latency_ms),
        _iv("gen_ai.usage.input_tokens",   input_tokens),
        _iv("gen_ai.usage.output_tokens",  output_tokens),
        _iv("gen_ai.usage.total_tokens",   total_tokens),
        _iv("llm.usage.prompt_tokens",     input_tokens),
        _iv("llm.usage.completion_tokens", output_tokens),
        _iv("llm.usage.total_tokens",      total_tokens),
    ]
    if error_msg:
        root_attrs.append(_sv("error.type",    "AgentError"))
        root_attrs.append(_sv("error.message", error_msg[:4000]))
    if extra_attributes:
        root_attrs.extend(extra_attributes)

    # Reasoning step events — each entry becomes a ``steps`` row in the Langfuse
    # trace, matching the shape emitted by WXO's internal LangGraph pipeline:
    #   { observationId, traceId: null, name, startTime: null, type, content }
    # We encode them as OTel span events so they survive the OTLP wire format.
    _step_events: list[dict] = []
    for _step_text in (reasoning_steps or []):
        if _step_text:
            _step_events.append({
                "name": "gen_ai.reasoning",
                "timeUnixNano": _start_ns,
                "attributes": [
                    _sv("gen_ai.reasoning.content", str(_step_text)[:4000]),
                    _sv("langfuse.step.type",        "reasoning"),
                    _sv("langfuse.step.name",        f"generate_content {_model_name}"),
                ],
            })

    root_span = {
        "traceId":           _trace_id,
        "spanId":            _span_id,
        "name":              _span_name,
        "kind":              2,   # SERVER
        "startTimeUnixNano": _start_ns,
        "endTimeUnixNano":   _end_ns,
        "status":            {"code": 2 if is_error else 0},
        "attributes":        root_attrs,
        **({"events": _step_events} if _step_events else {}),
    }

    # ── call_llm span (LLM wrapper, child of root) ────────────────────────────
    _call_llm_id = secrets.token_hex(8)
    _llm_start   = _start_ns + max(1_000_000, (_end_ns - _start_ns) // 20)
    _llm_end     = _end_ns   - max(1_000_000, (_end_ns - _start_ns) // 20)

    call_llm_span = {
        "traceId":           _trace_id,
        "spanId":            _call_llm_id,
        "parentSpanId":      _span_id,
        "name":              "call_llm",
        "kind":              3,   # CLIENT
        "startTimeUnixNano": _llm_start,
        "endTimeUnixNano":   _llm_end,
        "status":            {"code": 0},
        "attributes": [
            _sv("openinference.span.kind",        "LLM"),
            _sv("gen_ai.request.model",           _model_name),
            _sv("llm.model_name",                 _model_name),
            _sv("gen_ai.system",                  platform),
            _sv("gen_ai.input.messages",          input_messages),
            _sv("gen_ai.output.messages",         output_messages),
            _sv("provided_usage_details", json.dumps(
                {"input": input_tokens, "output": output_tokens, "total": total_tokens}
            )),
            _sv("langfuse.observation.usage_details", json.dumps(
                {"input": input_tokens, "output": output_tokens, "total": total_tokens}
            )),
            _iv("gen_ai.usage.input_tokens",      input_tokens),
            _iv("gen_ai.usage.output_tokens",     output_tokens),
            _iv("gen_ai.usage.prompt_tokens",     input_tokens),
            _iv("gen_ai.usage.completion_tokens", output_tokens),
            _iv("llm.usage.prompt_tokens",        input_tokens),
            _iv("llm.usage.completion_tokens",    output_tokens),
            _iv("llm.token_count.prompt",         input_tokens),
            _iv("llm.token_count.completion",     output_tokens),
            _iv("llm.token_count.total",          total_tokens),
        ],
    }

    # ── generate_content span (LLM leaf, child of call_llm) ──────────────────
    _gen_id    = secrets.token_hex(8)
    _gen_start = _llm_start + max(500_000, (_llm_end - _llm_start) // 20)
    _gen_end   = _llm_end   - max(500_000, (_llm_end - _llm_start) // 20)

    generate_span = {
        "traceId":           _trace_id,
        "spanId":            _gen_id,
        "parentSpanId":      _call_llm_id,
        "name":              f"generate_content {_model_name}",
        "kind":              3,
        "startTimeUnixNano": _gen_start,
        "endTimeUnixNano":   _gen_end,
        "status":            {"code": 0},
        "attributes": [
            _sv("openinference.span.kind",        "LLM"),
            _sv("gen_ai.request.model",           _model_name),
            _sv("llm.model_name",                 _model_name),
            _sv("gen_ai.system",                  platform),
            _sv("gen_ai.prompt",                  prompt[:2000]),
            _sv("gen_ai.completion",              response[:2000]),
            _sv("gen_ai.input.messages",          input_messages),
            _sv("gen_ai.output.messages",         output_messages),
            _sv("provided_usage_details", json.dumps(
                {"input": input_tokens, "output": output_tokens, "total": total_tokens}
            )),
            _iv("gen_ai.usage.input_tokens",      input_tokens),
            _iv("gen_ai.usage.output_tokens",     output_tokens),
            _iv("gen_ai.usage.prompt_tokens",     input_tokens),
            _iv("gen_ai.usage.completion_tokens", output_tokens),
        ],
    }

    spans = [root_span, call_llm_span, generate_span]

    # ── Tool spans (TOOL children of generate_content) ────────────────────────
    _gen_window = max(1, _gen_end - _gen_start)
    _tc_count   = len(tool_calls) if tool_calls else 0

    def _emit_tools(tc_list, parent_id, win_s, win_e, depth=0):
        cnt  = len(tc_list)
        slot = max(1, (win_e - win_s) // (cnt + 1)) if cnt else (win_e - win_s)
        for i, tc in enumerate(tc_list):
            ts = tc.get("start_ns") or (win_s + slot * (i + 1))
            te = tc.get("end_ns")   or (ts + max(1_000_000, slot // 2))
            ts = max(win_s, min(ts, win_e - 1_000_000))
            te = max(ts + 1_000_000, min(te, win_e))
            sub  = tc.get("sub_calls") or []
            kind = "CHAIN" if (depth == 0 and sub) else "TOOL"
            sid  = secrets.token_hex(8)
            ta = [
                _sv("openinference.span.kind", kind),
                _sv("tool.name",               str(tc.get("name", f"tool_{i}"))),
                _sv("gen_ai.tool.name",         str(tc.get("name", f"tool_{i}"))),
                _sv("tool.parameters",          str(tc.get("input",  ""))[:2000]),
                _sv("tool.output",              str(tc.get("output", ""))[:2000]),
                _sv("input.value",              str(tc.get("input",  ""))[:2000]),
                # NB: no output.value on TOOL spans — WXO drops the span.
            ]
            spans.append({
                "traceId":           _trace_id,
                "spanId":            sid,
                "parentSpanId":      parent_id,
                "name":              str(tc.get("name", f"tool_{i}")),
                "kind":              3,
                "startTimeUnixNano": ts,
                "endTimeUnixNano":   te,
                "status":            {"code": 2 if tc.get("is_error") else 0},
                "attributes":        ta,
            })
            if sub:
                _emit_tools(sub, sid, ts, te, depth + 1)

    if tool_calls:
        _emit_tools(tool_calls, _gen_id, _gen_start, _gen_end)

    # ── RETRIEVER span (synthetic knowledge-base lookup, inside generate_content)
    _rv_slot  = _gen_window // (_tc_count + 2)
    _rv_start = _gen_start + _rv_slot * (_tc_count + 1)
    _rv_end   = min(_rv_start + max(1_000_000, _rv_slot // 2), _gen_end)
    spans.append({
        "traceId":           _trace_id,
        "spanId":            secrets.token_hex(8),
        "parentSpanId":      _gen_id,
        "name":              "retrieval",
        "kind":              3,
        "startTimeUnixNano": _rv_start,
        "endTimeUnixNano":   _rv_end,
        "status":            {"code": 0},
        "attributes": [
            _sv("openinference.span.kind", "RETRIEVER"),
            _sv("retrieval.source",        "knowledge_base"),
        ],
    })

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


def post_to_wxo(
    payload: dict,
    bearer_token: str,
    export_url: str,
    agent_id: str,
    tenant_id: str,
    logger=None,
    retries: int = 3,
) -> str:
    """Post WXO OTLP JSON payload to WXO endpoint with retry support."""
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json",
        "User-Agent": "curl/7.68.0",
        "x-ibm-agent-id": agent_id,
        "x-langfuse-ingestion-version": "4",
    }
    if deployment_mode() == "cloud":  # CPD has no tenant header
        headers["x-ibm-tenant-id"] = tenant_id
        headers["x-tenant-id"] = tenant_id

    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            req = Request(export_url, data=data, headers=headers, method="POST")
            ctx = _ssl_context()
            with urlopen(req, timeout=30, context=ctx) as resp:
                resp_bytes = resp.read() or b"{}"
                body = json.loads(resp_bytes.decode("utf-8"))
                job_id = body.get("data", {}).get("id") or body.get("job_id") or "OK"
                if logger:
                    logger.info(f"Trace shipped to WXO: status={resp.status} agent_id={agent_id} job_id={job_id}")
                return job_id
        except urllib.error.HTTPError as http_err:
            err_body = http_err.read().decode("utf-8", errors="replace")
            last_exc = f"HTTP {http_err.code}: {err_body}"
            if logger:
                logger.warning(f"WXO post attempt {attempt}/{retries} failed: {last_exc}")
            if http_err.code < 500:
                break
        except Exception as exc:
            last_exc = str(exc)
            if logger:
                logger.warning(f"WXO post attempt {attempt}/{retries} failed: {exc}")

        if attempt < retries:
            time.sleep(0.5 * attempt)

    if logger:
        logger.error(f"Failed to post trace to WXO after {retries} attempts: {last_exc}")
    return ""


def post_scores_to_wxo(
    scores: list[dict],
    trace_id: str,
    bearer_token: str,
    export_url: str,
    agent_id: str,
    tenant_id: str,
    logger=None,
) -> bool:
    """
    POST Langfuse-compatible score objects to the WXO scores endpoint.

    WXO exposes a scores ingest URL derived from the traces URL by replacing
    the ``inject/traces`` suffix with ``inject/scores``.  Each score object
    must match the Langfuse score shape::

        {
          "traceId":    "<trace-id>",
          "name":       "<score-name>",      # e.g. "relevance", "toxicity"
          "value":      <float>,             # numeric score
          "dataType":   "NUMERIC",           # or "CATEGORICAL" / "BOOLEAN"
          "source":     "API",
          "comment":    "<optional text>",
          "metadata":   { "agent_id": "..." }
        }

    Returns True if the POST succeeded.
    """
    if not scores or not trace_id or not bearer_token or not export_url:
        return False

    # Derive scores URL: .../inject/traces -> .../inject/scores
    if "inject/traces" in export_url:
        scores_url = export_url.replace("inject/traces", "inject/scores")
    elif export_url.rstrip("/").endswith("/traces"):
        scores_url = export_url.rstrip("/")[:-len("traces")] + "scores"
    else:
        scores_url = export_url.rstrip("/") + "/scores"

    # Stamp every score with the trace ID and agent metadata
    stamped = []
    for s in scores:
        entry = dict(s)
        entry["traceId"] = trace_id
        entry.setdefault("source", "API")
        entry.setdefault("metadata", {})
        if agent_id:
            entry["metadata"]["agent_id"] = agent_id
        stamped.append(entry)

    payload = json.dumps({"scores": stamped}).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json",
        "User-Agent": "curl/7.68.0",
        "x-ibm-agent-id": agent_id,
        "x-langfuse-ingestion-version": "4",
    }
    if deployment_mode() == "cloud":
        headers["x-ibm-tenant-id"] = tenant_id
        headers["x-tenant-id"] = tenant_id

    try:
        req = Request(scores_url, data=payload, headers=headers, method="POST")
        ctx = _ssl_context()
        with urlopen(req, timeout=15, context=ctx) as resp:
            if logger:
                logger.info(
                    f"Scores posted to WXO: status={resp.status} "
                    f"trace_id={trace_id} count={len(stamped)}"
                )
            return True
    except Exception as exc:
        if logger:
            logger.warning(f"Failed to post scores for trace {trace_id}: {exc}")
        return False


# =============================================================================
# Zero-Dependency Pure Python Protobuf Decoder
# =============================================================================

def _proto_read_varint(data: bytes, pos: int):
    result, shift = 0, 0
    while pos < len(data):
        b = data[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            return result, pos
        shift += 7
    return result, pos


def _proto_skip(data: bytes, pos: int, wire_type: int) -> int:
    if wire_type == 0:
        _, pos = _proto_read_varint(data, pos)
    elif wire_type == 1:
        pos += 8
    elif wire_type == 2:
        length, pos = _proto_read_varint(data, pos)
        pos += length
    elif wire_type == 5:
        pos += 4
    return pos


def _proto_read_bytes(data: bytes, pos: int):
    length, pos = _proto_read_varint(data, pos)
    return data[pos:pos + length], pos + length


def _proto_read_string(data: bytes, pos: int):
    b, pos = _proto_read_bytes(data, pos)
    try:
        return b.decode("utf-8", errors="replace"), pos
    except Exception:
        return "", pos


def _decode_any_value(data: bytes) -> object:
    # AnyValue oneof: string=1, bool=2, int=3, double=4, array=5, kvlist=6, bytes=7
    pos = 0
    while pos < len(data):
        try:
            tag_wire, pos = _proto_read_varint(data, pos)
        except Exception:
            break
        field = tag_wire >> 3
        wire = tag_wire & 0x07
        if wire == 2:
            chunk, pos = _proto_read_bytes(data, pos)
            if field == 1:  # string_value
                return chunk.decode("utf-8", errors="replace")
            if field == 5:  # array_value
                return _decode_array_value(chunk)
            if field == 6:  # kvlist_value
                return _decode_kvlist_value(chunk)
            if field == 7:  # bytes_value
                return chunk.hex()
        elif wire == 0:
            v, pos = _proto_read_varint(data, pos)
            if field == 2:  # bool_value
                return bool(v)
            if field == 3:  # int_value (int64, two's complement)
                return v - (1 << 64) if v >= (1 << 63) else v
        elif wire == 1:
            if field == 4 and pos + 8 <= len(data):  # double_value
                return struct.unpack_from("<d", data, pos)[0]
            pos += 8
        else:
            pos = _proto_skip(data, pos, wire)
    return ""


def _decode_array_value(data: bytes) -> list:
    items = []
    pos = 0
    while pos < len(data):
        try:
            tag_wire, pos = _proto_read_varint(data, pos)
        except Exception:
            break
        field = tag_wire >> 3
        wire = tag_wire & 0x07
        if wire == 2 and field == 1:
            chunk, pos = _proto_read_bytes(data, pos)
            items.append(_decode_any_value(chunk))
        else:
            pos = _proto_skip(data, pos, wire)
    return items


def _decode_kvlist_value(data: bytes) -> dict:
    result = {}
    pos = 0
    while pos < len(data):
        try:
            tag_wire, pos = _proto_read_varint(data, pos)
        except Exception:
            break
        field = tag_wire >> 3
        wire = tag_wire & 0x07
        if wire == 2 and field == 1:
            chunk, pos = _proto_read_bytes(data, pos)
            k, v = _decode_key_value(chunk)
            if k:
                result[k] = v
        else:
            pos = _proto_skip(data, pos, wire)
    return result


def _decode_key_value(data: bytes) -> tuple:
    k = ""
    v = None
    pos = 0
    while pos < len(data):
        try:
            tag_wire, pos = _proto_read_varint(data, pos)
        except Exception:
            break
        field = tag_wire >> 3
        wire = tag_wire & 0x07
        if wire == 2:
            if field == 1:  # key
                k, pos = _proto_read_string(data, pos)
            elif field == 2:  # value (AnyValue message)
                chunk, pos = _proto_read_bytes(data, pos)
                v = _decode_any_value(chunk)
            else:
                pos = _proto_skip(data, pos, wire)
        else:
            pos = _proto_skip(data, pos, wire)
    return k, v


def _decode_attributes(data: bytes) -> dict:
    attrs = {}
    pos = 0
    while pos < len(data):
        try:
            tag_wire, pos = _proto_read_varint(data, pos)
        except Exception:
            break
        field = tag_wire >> 3
        wire = tag_wire & 0x07
        if wire == 2 and field == 1:
            chunk, pos = _proto_read_bytes(data, pos)
            k, v = _decode_key_value(chunk)
            if k:
                attrs[k] = v
        else:
            pos = _proto_skip(data, pos, wire)
    return attrs


def _decode_span_event(data: bytes) -> dict:
    evt = {"name": "", "attributes": {}}
    pos = 0
    while pos < len(data):
        try:
            tag_wire, pos = _proto_read_varint(data, pos)
        except Exception:
            break
        field = tag_wire >> 3
        wire = tag_wire & 0x07
        if wire == 2:
            if field == 2:  # name
                evt["name"], pos = _proto_read_string(data, pos)
            elif field == 3:  # attributes (repeated KeyValue)
                chunk, pos = _proto_read_bytes(data, pos)
                k, v = _decode_key_value(chunk)
                if k:
                    evt["attributes"][k] = v
            else:
                pos = _proto_skip(data, pos, wire)
        elif wire == 1:
            if field == 1:  # time_unix_nano (fixed64)
                if pos + 8 <= len(data):
                    evt["timeUnixNano"] = struct.unpack_from("<Q", data, pos)[0]
                    pos += 8
            else:
                pos += 8
        else:
            pos = _proto_skip(data, pos, wire)
    return evt


def _decode_span(data: bytes) -> dict:
    span = {
        "traceId": "",
        "spanId": "",
        "parentSpanId": "",
        "name": "",
        "kind": 1,
        "startTimeUnixNano": 0,
        "endTimeUnixNano": 0,
        "attributes": {},
        "events": [],
        "status": {"code": 0},
    }
    pos = 0
    while pos < len(data):
        try:
            tag_wire, pos = _proto_read_varint(data, pos)
        except Exception:
            break
        field = tag_wire >> 3
        wire = tag_wire & 0x07
        # OTLP Span: trace_id=1 span_id=2 trace_state=3 parent_span_id=4 name=5
        # kind=6 start=7 end=8 attributes=9 events=11 status=15
        if wire == 2:
            if field == 1:  # trace_id (bytes)
                b, pos = _proto_read_bytes(data, pos)
                span["traceId"] = b.hex()
            elif field == 2:  # span_id (bytes)
                b, pos = _proto_read_bytes(data, pos)
                span["spanId"] = b.hex()
            elif field == 4:  # parent_span_id (bytes)
                b, pos = _proto_read_bytes(data, pos)
                span["parentSpanId"] = b.hex() if b else ""
            elif field == 5:  # name
                span["name"], pos = _proto_read_string(data, pos)
            elif field == 9:  # attributes (repeated KeyValue)
                chunk, pos = _proto_read_bytes(data, pos)
                k, v = _decode_key_value(chunk)
                if k:
                    span["attributes"][k] = v
            elif field == 11:  # events (repeated Event)
                chunk, pos = _proto_read_bytes(data, pos)
                span["events"].append(_decode_span_event(chunk))
            elif field == 15:  # status (Status message)
                chunk, pos = _proto_read_bytes(data, pos)
                # Field 3 inside status is code
                s_pos = 0
                while s_pos < len(chunk):
                    try:
                        s_tag_wire, s_pos = _proto_read_varint(chunk, s_pos)
                    except Exception:
                        break
                    s_field = s_tag_wire >> 3
                    s_wire = s_tag_wire & 0x07
                    if s_wire == 0 and s_field == 3:
                        c, s_pos = _proto_read_varint(chunk, s_pos)
                        span["status"]["code"] = c
                    else:
                        s_pos = _proto_skip(chunk, s_pos, s_wire)
            else:
                pos = _proto_skip(data, pos, wire)
        elif wire == 1:
            if field == 7:  # start_time_unix_nano (fixed64)
                if pos + 8 <= len(data):
                    span["startTimeUnixNano"] = struct.unpack_from("<Q", data, pos)[0]
                    pos += 8
            elif field == 8:  # end_time_unix_nano (fixed64)
                if pos + 8 <= len(data):
                    span["endTimeUnixNano"] = struct.unpack_from("<Q", data, pos)[0]
                    pos += 8
            else:
                pos += 8
        elif wire == 0:
            v, pos = _proto_read_varint(data, pos)
            if field == 6:  # kind
                span["kind"] = v
        else:
            pos = _proto_skip(data, pos, wire)
    return span


def _decode_scope_spans(data: bytes) -> dict:
    scope = {"name": "", "version": ""}
    spans = []
    pos = 0
    while pos < len(data):
        try:
            tag_wire, pos = _proto_read_varint(data, pos)
        except Exception:
            break
        field = tag_wire >> 3
        wire = tag_wire & 0x07
        if wire == 2:
            if field == 2:  # spans (repeated Span)
                chunk, pos = _proto_read_bytes(data, pos)
                spans.append(_decode_span(chunk))
            elif field == 1:  # scope (InstrumentationScope)
                chunk, pos = _proto_read_bytes(data, pos)
                s_pos = 0
                while s_pos < len(chunk):
                    try:
                        st, s_pos = _proto_read_varint(chunk, s_pos)
                    except Exception:
                        break
                    sf = st >> 3
                    sw = st & 0x07
                    if sw == 2 and sf == 1:
                        scope["name"], s_pos = _proto_read_string(chunk, s_pos)
                    elif sw == 2 and sf == 2:
                        scope["version"], s_pos = _proto_read_string(chunk, s_pos)
                    else:
                        s_pos = _proto_skip(chunk, s_pos, sw)
            else:
                pos = _proto_skip(data, pos, wire)
        else:
            pos = _proto_skip(data, pos, wire)
    return {"scope": scope, "spans": spans}


def _decode_resource_spans(data: bytes) -> dict:
    res = {"attributes": {}}
    scope_spans = []
    pos = 0
    while pos < len(data):
        try:
            tag_wire, pos = _proto_read_varint(data, pos)
        except Exception:
            break
        field = tag_wire >> 3
        wire = tag_wire & 0x07
        if wire == 2:
            if field == 1:  # resource (Resource message)
                chunk, pos = _proto_read_bytes(data, pos)
                r_pos = 0
                while r_pos < len(chunk):
                    try:
                        rt, r_pos = _proto_read_varint(chunk, r_pos)
                    except Exception:
                        break
                    rf = rt >> 3
                    rw = rt & 0x07
                    if rw == 2 and rf == 1:  # attributes
                        c, r_pos = _proto_read_bytes(chunk, r_pos)
                        k, v = _decode_key_value(c)
                        if k:
                            res["attributes"][k] = v
                    else:
                        r_pos = _proto_skip(chunk, r_pos, rw)
            elif field == 2:  # scope_spans (repeated ScopeSpans)
                chunk, pos = _proto_read_bytes(data, pos)
                scope_spans.append(_decode_scope_spans(chunk))
            else:
                pos = _proto_skip(data, pos, wire)
        else:
            pos = _proto_skip(data, pos, wire)
    return {"resource": res, "scopeSpans": scope_spans}


def decode_otlp_protobuf(data: bytes) -> list[dict]:
    """
    Decode binary OTLP ExportTraceServiceRequest protobuf bytes into standard
    resourceSpans list.
    """
    resource_spans = []
    pos = 0
    while pos < len(data):
        try:
            tag_wire, pos = _proto_read_varint(data, pos)
        except Exception:
            break
        field = tag_wire >> 3
        wire = tag_wire & 0x07
        if wire == 2 and field == 1:  # resource_spans
            chunk, pos = _proto_read_bytes(data, pos)
            resource_spans.append(_decode_resource_spans(chunk))
        else:
            pos = _proto_skip(data, pos, wire)
    return resource_spans


# =============================================================================
# Forwarder Core Engine
# =============================================================================

class OtlpForwarder:
    """
    Unified OTLP Trace Forwarder Engine.
    Handles agent mapping, trace normalization, and forwarding to WXO.
    """

    def __init__(
        self,
        agent_map: dict[str, dict] | None = None,
        default_tenant_id: str = "",
        default_export_url: str = "",
        default_api_key: str = "",
        default_token_url: str = "",
        default_environment: str = "draft",
    ):
        self.agent_map = agent_map if agent_map is not None else self.parse_agent_map()
        cpd = deployment_mode() == "cpd"
        self.default_export_url = default_export_url or (
            cpd_export_url() if cpd else os.environ.get("WXO_OTEL_EXPORT_URL", "").strip()
        )
        self.default_tenant_id = "" if cpd else (default_tenant_id or extract_tenant_id(self.default_export_url) or os.environ.get("WXO_TENANT_ID", "").strip())
        self.default_api_key = default_api_key or (os.environ.get("API_KEY") or os.environ.get("WXO_API_KEY", "")).strip()
        self.default_token_url = default_token_url or os.environ.get(
            "TOKEN_URL",
            os.environ.get("WXO_TOKEN_URL", "https://account-iam.platform.saas.ibm.com/api/2.0/apikeys/token"),
        ).strip()
        self.default_environment = default_environment or os.environ.get("ENVIRONMENT_NAME", os.environ.get("WXO_ENVIRONMENT", "draft")).strip()
        # Shared secret callers must present (Authorization: Bearer <t> or x-api-key). Empty = open.
        self.auth_token = os.environ.get("FORWARDER_AUTH_TOKEN", "").strip()

    _settings_cache: dict = {}
    _settings_cache_time: float = 0

    @classmethod
    def get_settings(cls, force_refresh: bool = False) -> dict:
        """
        Runtime settings (WXO details + auth token) stored as JSON in the SSM
        parameter named by SSM_SETTINGS_PATH. Cached with the same TTL as the agent map.
        Keys: tenant_id, otel_export_url, environment, token_url, api_key, auth_token.
        """
        now = time.time()
        if not force_refresh and cls._settings_cache_time and (now - cls._settings_cache_time < cls._map_cache_ttl):
            return cls._settings_cache

        settings: dict = {}
        ssm_path = os.environ.get("SSM_SETTINGS_PATH", "").strip()
        if ssm_path:
            try:
                import boto3
                ssm_client = boto3.client("ssm", region_name=os.environ.get("AWS_REGION", "us-east-1"))
                resp = ssm_client.get_parameter(Name=ssm_path, WithDecryption=True)
                settings = json.loads(resp.get("Parameter", {}).get("Value", "{}"))
            except Exception as exc:
                log.warning(f"Settings lookup for {ssm_path} failed: {exc}")

        cls._settings_cache = settings if isinstance(settings, dict) else {}
        cls._settings_cache_time = now
        return cls._settings_cache

    def refresh(self) -> None:
        """Re-apply runtime settings and agent map (call per invocation on long-lived containers)."""
        s = self.get_settings()
        # Deployment mode + CPD login are stored in the SSM settings (Lambda target);
        # the token/URL helpers read them from the process environment.
        if s.get("deployment_mode"):
            os.environ["WXO_DEPLOYMENT_MODE"] = str(s["deployment_mode"])
        for _k in ("CPD_HOST_URL", "CPD_USERNAME", "CPD_PASSWORD", "CPD_INSTANCE_ID",
                   "CPD_NAMESPACE", "CPD_VERIFY_TLS"):
            if s.get(_k.lower()):
                os.environ[_k] = str(s[_k.lower()])
        self.default_export_url = s.get("otel_export_url") or self.default_export_url
        self.default_tenant_id = s.get("tenant_id") or extract_tenant_id(self.default_export_url) or self.default_tenant_id
        self.default_api_key = s.get("api_key") or self.default_api_key
        self.default_token_url = s.get("token_url") or self.default_token_url
        self.default_environment = s.get("environment") or self.default_environment
        self.auth_token = s.get("auth_token") or self.auth_token
        self.agent_map = self.get_agent_map()

    def is_authorized(self, headers: dict) -> bool:
        """True if no auth token is configured, or the caller presented the right one."""
        if not self.auth_token:
            return True
        hdrs = {k.lower(): v for k, v in (headers or {}).items()}
        presented = hdrs.get("x-api-key", "")
        auth = hdrs.get("authorization", "")
        if auth.lower().startswith("bearer "):
            presented = auth[7:].strip()
        return hmac.compare_digest(presented.encode(), self.auth_token.encode())

    _map_cache: dict[str, dict] = {}
    _map_cache_time: float = 0
    _map_cache_ttl: float = 60.0  # Auto-refresh remote mapping every 60s

    @classmethod
    def get_agent_map(cls, force_refresh: bool = False) -> dict[str, dict]:
        """
        Retrieve agent mapping dictionary from configured storage backend.
        Supports:
          1. Remote URL / S3 / Blob Storage (WXO_AGENT_MAP_URL)
          2. AWS SSM Parameter Store (SSM_AGENT_MAP_PATH or /wxo-agent/agent_map)
          3. Environment variable (WXO_AGENT_MAP)
          4. Persistent File (WXO_AGENT_MAP_FILE or config/agent_map.json)
        Auto-refreshes periodically with TTL caching.
        """
        now = time.time()
        if not force_refresh and cls._map_cache and (now - cls._map_cache_time < cls._map_cache_ttl):
            return cls._map_cache

        data = {}

        # 1. Remote HTTP/S3 URL
        map_url = os.environ.get("WXO_AGENT_MAP_URL", "").strip()
        if map_url:
            try:
                req = Request(map_url, headers={"Accept": "application/json"})
                ctx = ssl.create_default_context()
                with urlopen(req, timeout=10, context=ctx) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
            except Exception as exc:
                log.warning(f"Failed to fetch agent map from remote URL {map_url}: {exc}")

        # 2. AWS SSM Parameter Store (Primary Zero-Ops Cloud Option: /wxo-agent/agent_map)
        ssm_path = os.environ.get("SSM_AGENT_MAP_PATH", "").strip()
        if not data and (ssm_path or "AWS_REGION" in os.environ or os.environ.get("USE_SSM") == "1"):
            param_name = ssm_path or "/wxo-agent/agent_map"
            try:
                import boto3
                ssm_client = boto3.client("ssm", region_name=os.environ.get("AWS_REGION", "us-east-1"))
                resp = ssm_client.get_parameter(Name=param_name, WithDecryption=True)
                val = resp.get("Parameter", {}).get("Value", "{}")
                data = json.loads(val)
                log.info(f"Loaded {len(data)} agent mappings from AWS SSM ({param_name})")
            except Exception as exc:
                log.debug(f"SSM agent map lookup for {param_name} skipped/failed: {exc}")

        # 3. DynamoDB Database Table Option (DYNAMODB_TABLE_NAME)
        dynamo_table = os.environ.get("DYNAMODB_TABLE_NAME") or os.environ.get("WXO_DYNAMODB_TABLE", "").strip()
        if not data and dynamo_table:
            try:
                import boto3
                dynamo = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"))
                table = dynamo.Table(dynamo_table)
                items = table.scan().get("Items", [])
                for item in items:
                    agent_key = item.get("agent_name") or item.get("agent_id") or item.get("id")
                    if agent_key:
                        data[agent_key] = {
                            "wxo_agent_id": item.get("wxo_agent_id", ""),
                            "wxo_tenant_id": item.get("wxo_tenant_id", ""),
                            "wxo_otel_export_url": item.get("wxo_otel_export_url", ""),
                            "wxo_display_name": item.get("wxo_display_name", agent_key),
                            "environment": item.get("environment", "draft"),
                        }
                log.info(f"Loaded {len(data)} agent mappings from DynamoDB table ({dynamo_table})")
            except Exception as exc:
                log.warning(f"DynamoDB lookup failed for table {dynamo_table}: {exc}")

        # 4. PostgreSQL / SQL Database Table Option (POSTGRES_URL / DATABASE_URL)
        db_url = os.environ.get("POSTGRES_URL") or os.environ.get("DATABASE_URL", "").strip()
        if not data and db_url:
            sql_data = cls._load_from_sql(db_url)
            if sql_data:
                data = sql_data

        # 5. Environment Variable
        if not data:
            raw = os.environ.get("WXO_AGENT_MAP", "{}").strip()
            if raw and raw != "{}":
                try:
                    data = json.loads(raw)
                except Exception as exc:
                    log.warning(f"Failed to parse WXO_AGENT_MAP JSON: {exc}")

        # 4. Local / Mounted persistent file
        if not data:
            map_file = os.environ.get("WXO_AGENT_MAP_FILE")
            if not map_file:
                for cand in (
                    os.path.join(os.path.dirname(_repo_root), "agent_map.json"),
                    os.path.join(os.path.dirname(_repo_root), "config", "agent_map.json"),
                ):
                    if os.path.exists(cand):
                        map_file = cand
                        break
            if map_file and os.path.exists(map_file):
                try:
                    with open(map_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception as exc:
                    log.warning(f"Failed to load agent map file {map_file}: {exc}")

        res: dict[str, dict] = {}
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, str):
                    res[k] = {"wxo_agent_id": v}
                elif isinstance(v, dict):
                    res[k] = dict(v)
                    if "agent_id" in v and "wxo_agent_id" not in res[k]:
                        res[k]["wxo_agent_id"] = v["agent_id"]

        cls._map_cache = res
        cls._map_cache_time = now
        return res

    @staticmethod
    def parse_agent_map() -> dict[str, dict]:
        """Convenience alias for get_agent_map()."""
        return OtlpForwarder.get_agent_map()

    @classmethod
    def _load_from_sql(cls, db_url: str) -> dict:
        """Fetch mappings from PostgreSQL or SQLite table wxo_agent_mappings."""
        res = {}
        try:
            if db_url.startswith("sqlite"):
                import sqlite3
                path = db_url.replace("sqlite:///", "").replace("sqlite://", "")
                conn = sqlite3.connect(path)
                cursor = conn.cursor()
                cursor.execute("SELECT agent_name, wxo_agent_id, wxo_tenant_id, wxo_otel_export_url, wxo_display_name, environment FROM wxo_agent_mappings")
                for row in cursor.fetchall():
                    res[row[0]] = {
                        "wxo_agent_id": row[1],
                        "wxo_tenant_id": row[2],
                        "wxo_otel_export_url": row[3],
                        "wxo_display_name": row[4] or row[0],
                        "environment": row[5] or "draft",
                    }
                conn.close()
            else:
                # PostgreSQL via psycopg2 / psycopg / pg8000
                conn = None
                try:
                    import psycopg2
                    conn = psycopg2.connect(db_url)
                except ImportError:
                    try:
                        import psycopg
                        conn = psycopg.connect(db_url)
                    except ImportError:
                        try:
                            import pg8000.dbapi
                            import urllib.parse
                            p = urllib.parse.urlparse(db_url)
                            conn = pg8000.dbapi.connect(
                                user=p.username,
                                password=p.password,
                                host=p.hostname,
                                port=p.port or 5432,
                                database=p.path.lstrip("/"),
                            )
                        except Exception:
                            pass

                if conn:
                    cur = conn.cursor()
                    cur.execute("SELECT agent_name, wxo_agent_id, wxo_tenant_id, wxo_otel_export_url, wxo_display_name, environment FROM wxo_agent_mappings")
                    for row in cur.fetchall():
                        res[row[0]] = {
                            "wxo_agent_id": row[1],
                            "wxo_tenant_id": row[2],
                            "wxo_otel_export_url": row[3],
                            "wxo_display_name": row[4] or row[0],
                            "environment": row[5] or "draft",
                        }
                    conn.close()
                    log.info(f"Loaded {len(res)} agent mappings from PostgreSQL table")
        except Exception as exc:
            log.warning(f"SQL database mapping lookup failed: {exc}")
        return res

    @classmethod
    def set_agent_mapping(cls, agent_key: str, config: dict, persist: bool = True) -> dict:
        """Dynamically add or update an agent mapping at runtime."""
        current = cls.get_agent_map(force_refresh=True)
        current[agent_key] = config
        cls._map_cache = current
        cls._map_cache_time = time.time()

        if persist:
            map_file = os.environ.get("WXO_AGENT_MAP_FILE") or os.path.join(os.path.dirname(_repo_root), "agent_map.json")
            try:
                os.makedirs(os.path.dirname(os.path.abspath(map_file)), exist_ok=True)
                with open(map_file, "w", encoding="utf-8") as f:
                    json.dump(current, f, indent=2)
            except Exception as exc:
                log.warning(f"Could not persist mapping to file: {exc}")

        return current

    def resolve_wxo_agent(
        self,
        candidate_keys: list[str] | None = None,
        default_name: str = "custom_agent",
    ) -> dict:
        """
        Resolve WXO routing parameters from candidate identifiers (URL paths, headers,
        span/resource attributes, model names) against WXO_AGENT_MAP and environment defaults.
        """
        keys = [k for k in (candidate_keys or []) if k and str(k).strip()]
        map_entry = {}
        matched_key = ""

        # 1. Direct UUID or exact map match
        uuid_pat = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)

        for k in keys:
            if k in self.agent_map:
                map_entry = self.agent_map[k]
                matched_key = k
                break
            elif uuid_pat.match(k):
                map_entry = {"wxo_agent_id": k, "wxo_agent_name": default_name}
                matched_key = k
                break

        # 2. Check "default" fallback in map
        if not map_entry and "default" in self.agent_map:
            map_entry = self.agent_map["default"]
            matched_key = "default"

        # No first-entry fallback: an unmapped agent must not be attributed to another WXO agent.

        agent_id = (
            map_entry.get("wxo_agent_id")
            or map_entry.get("agent_id")
            or os.environ.get("WXO_AGENT_ID", "").strip()
            or (matched_key if uuid_pat.match(matched_key) else "")
        )

        agent_name = (
            map_entry.get("wxo_agent_name")
            or (matched_key if matched_key and matched_key != "default" and not uuid_pat.match(matched_key) else default_name)
        )
        clean_name = re.sub(r"[^a-zA-Z0-9_-]", "_", agent_name).lower()
        display_name = map_entry.get("wxo_display_name") or map_entry.get("display_name") or clean_name

        export_url = map_entry.get("wxo_otel_export_url") or map_entry.get("otel_export_url") or self.default_export_url
        tenant_id = map_entry.get("wxo_tenant_id") or map_entry.get("tenant_id") or extract_tenant_id(export_url) or self.default_tenant_id
        api_key = map_entry.get("wxo_api_key") or map_entry.get("api_key") or self.default_api_key
        token_url = map_entry.get("wxo_token_url") or map_entry.get("token_url") or self.default_token_url
        environment = map_entry.get("environment") or self.default_environment

        return {
            "matched_key": matched_key,
            "agent_id": agent_id,
            "agent_name": clean_name,
            "display_name": display_name,
            "tenant_id": tenant_id,
            "export_url": export_url,
            "api_key": api_key,
            "token_url": token_url,
            "environment": environment,
        }

    def check_request(self, headers: dict | None) -> bool:
        """
        Shared first step for every adapter (Lambda, Azure, Docker/VM):
        pick up the latest settings + agent map, then verify the caller's token.
        Returns False if the request must be rejected with 401.
        """
        self.refresh()
        if not self.is_authorized(headers or {}):
            log.warning("Rejected request: missing or invalid auth token")
            return False
        return True

    def handle(
        self,
        body_bytes: bytes,
        content_type: str = "application/json",
        content_encoding: str = "",
        headers: dict | None = None,
        query_params: dict | None = None,
        path_agent_id: str = "",
    ) -> tuple[int, dict]:
        """
        One request pipeline for all platforms: refresh -> auth -> process.
        Adapters only translate their platform's request/response shape.
        Returns (http_status, json_body).
        """
        if not self.check_request(headers):
            return 401, {"error": "Unauthorized"}
        try:
            job_ids = self.process_payload(
                body_bytes=body_bytes,
                content_type=content_type,
                content_encoding=content_encoding,
                headers=headers,
                query_params=query_params,
                path_agent_id=path_agent_id,
            )
            return 200, {"status": "ok", "job_ids": job_ids}
        except Exception as exc:
            log.error(f"Error processing OTLP payload: {exc}", exc_info=True)
            return 500, {"error": str(exc)}

    def process_payload(
        self,
        body_bytes: bytes,
        content_type: str = "application/json",
        content_encoding: str = "",
        headers: dict | None = None,
        query_params: dict | None = None,
        path_agent_id: str = "",
    ) -> list[str]:
        """
        Process incoming raw HTTP request bytes (JSON or Protobuf, optionally gzipped),
        extract spans, transform into WXO format, and ship to WXO.
        Returns list of WXO job IDs / trace confirmation IDs.
        """
        hdrs = {k.lower(): v for k, v in (headers or {}).items()}
        qparams = query_params or {}

        # Handle compression
        if content_encoding == "gzip" or body_bytes.startswith(b"\x1f\x8b"):
            try:
                body_bytes = gzip.decompress(body_bytes)
            except Exception as exc:
                log.error(f"Failed to decompress gzip payload: {exc}")
                return []

        # Determine payload type
        is_proto = "protobuf" in content_type or "octet-stream" in content_type or content_type == "application/x-protobuf"
        resource_spans = []

        if not is_proto:
            try:
                data = json.loads(body_bytes.decode("utf-8", errors="replace"))
                if isinstance(data, dict):
                    # Standard OTLP JSON: { "resourceSpans": [...] }
                    if "resourceSpans" in data:
                        resource_spans = data["resourceSpans"]
                    # AWS AgentCore Flow B direct observability callback:
                    #   Variant A: { "agentRuntimeArn": "...", "input": "...", "output": "...",
                    #                "usage": {...}, "startTime": "...", "endTime": "..." }
                    #   Variant B: { "invocationInput": {...}, "invocationOutput": {...},
                    #                "sessionId": "...", "requestId": "..." }
                    # Normalise into a synthetic resource_span so the rest of the
                    # pipeline can process it identically to any other platform.
                    elif "agentRuntimeArn" in data or "invocationInput" in data:
                        resource_spans = [{"_agentcore_callback": True, "_event": data}]
                    # AWS Strands/AgentCore flat format:
                    #   { "resource_attrs": {...}, "scope_spans": [...] }
                    elif "resource_attrs" in data or "scope_spans" in data:
                        resource_spans = [data]
                    # Claude flat single-span format:
                    #   { "span_name": "...", "resource": {...}, "attributes": {...}, ... }
                    elif "span_name" in data or ("attributes" in data and "resource" in data and "resourceSpans" not in data):
                        resource_spans = [{"_claude_flat": True, "resource": data.get("resource", {}), "_span": data}]
            except Exception:
                # Try fallback protobuf decode
                is_proto = True

        if is_proto:
            try:
                resource_spans = decode_otlp_protobuf(body_bytes)
            except Exception as exc:
                log.error(f"Failed to decode Protobuf payload: {exc}")
                return []

        # Extract explicit agent hints from URL / headers
        def _q(name: str) -> str:
            v = qparams.get(name, "")
            return (v[0] if v else "") if isinstance(v, list) else v

        explicit_agent_id = (
            path_agent_id
            or _q("wxo_agent_id")
            or _q("agent_id")
            or hdrs.get("x-wxo-agent-id", "")
            or hdrs.get("x-agent-id", "")
            or hdrs.get("x-ibm-agent-id", "")
            or hdrs.get("x-platform-agent-id", "")
        )

        job_ids = []

        for rs in resource_spans:
            # ── AWS AgentCore Flow B direct observability callback ────────────
            # Normalise the flat event into the same routing/building path as
            # any OTLP span so a single code path ships it to WXO.
            if rs.get("_agentcore_callback"):
                ev = rs["_event"]
                # Variant A: {agentRuntimeArn, input, output, usage, startTime, endTime}
                if "agentRuntimeArn" in ev:
                    arn = str(ev.get("agentRuntimeArn", ""))
                    runtime_id = arn.rstrip("/").rsplit("/", 1)[-1] if arn else ""
                    raw_prompt   = str(ev.get("input",  "") or "")
                    raw_response = str(ev.get("output", "") or "")
                    usage = ev.get("usage") or {}
                    it = int(usage.get("inputTokens",  usage.get("input_tokens",  0)) or 0)
                    ot = int(usage.get("outputTokens", usage.get("output_tokens", 0)) or 0)
                    _st = ev.get("startTime", "")
                    _et = ev.get("endTime",   "")
                    def _iso_to_ns(s):
                        try:
                            from datetime import datetime, timezone
                            dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
                            return int(dt.timestamp() * 1e9)
                        except Exception:
                            return 0
                    start_ns = _iso_to_ns(_st) or int(time.time() * 1e9) - 1_000_000_000
                    end_ns   = _iso_to_ns(_et) or int(time.time() * 1e9)
                    session_id = str(ev.get("sessionId") or ev.get("contextId") or "")
                # Variant B: {invocationInput, invocationOutput, sessionId, requestId}
                else:
                    inv_in   = ev.get("invocationInput",  {}) or {}
                    inv_out  = ev.get("invocationOutput", {}) or {}
                    raw_prompt   = str(inv_in.get("text")  or inv_in.get("input",  "") or json.dumps(inv_in)[:300])
                    raw_response = str(inv_out.get("text") or inv_out.get("output", "") or json.dumps(inv_out)[:300])
                    it, ot = 0, 0
                    start_ns = int(time.time() * 1e9) - 1_000_000_000
                    end_ns   = int(time.time() * 1e9)
                    session_id = str(ev.get("sessionId", ""))
                    runtime_id = ""

                # Resolve agent via runtime_id → agent map key
                candidate_keys = [
                    explicit_agent_id, runtime_id,
                    ev.get("agentId"), ev.get("agent_id"),
                ]
                routing = self.resolve_wxo_agent(
                    candidate_keys=[k for k in candidate_keys if k],
                    default_name=runtime_id or "aws_agentcore_agent",
                )
                agent_id   = routing["agent_id"]
                tenant_id  = routing["tenant_id"]
                export_url = routing["export_url"]
                api_key    = routing["api_key"]
                token_url  = routing["token_url"]
                env_name   = routing["environment"]
                clean_name = routing["agent_name"]

                if not agent_id or not export_url or not auth_configured(api_key):
                    log.warning(f"Skipping AgentCore callback: no WXO agent mapped "
                                f"(agent_id={agent_id!r}, export_url={bool(export_url)}, "
                                f"candidate_keys={candidate_keys})")
                    continue

                # Extract any eval scores carried on the AgentCore event
                _ac_scores = self._extract_scores({
                    k: v for k, v in ev.items()
                    if str(k).lower().startswith(("eval.", "score.", "langfuse.score.", "llm.eval."))
                })

                wxo_payload = build_otlp_payload(
                    agent_id=agent_id, agent_name=clean_name, tenant_id=tenant_id,
                    environment=env_name, prompt=raw_prompt, response=raw_response,
                    start_ns=start_ns, end_ns=end_ns,
                    input_tokens=it, output_tokens=ot,
                    platform="aws_bedrock_agentcore",
                    session_id=session_id,
                    trace_id=str(ev.get("requestId", "") or ""),
                    user_id=str(ev.get("userId", "") or ""),
                    reasoning_steps=[str(ev["reasoning"])] if ev.get("reasoning") else None,
                )
                token = get_bearer_token(api_key, token_url, logger=log)
                if token:
                    job_id = post_to_wxo(
                        payload=wxo_payload, bearer_token=token,
                        export_url=export_url, agent_id=agent_id,
                        tenant_id=tenant_id, logger=log,
                    )
                    if job_id:
                        job_ids.append(job_id)
                        if _ac_scores:
                            post_scores_to_wxo(
                                scores=_ac_scores,
                                trace_id=job_id,
                                bearer_token=token,
                                export_url=export_url,
                                agent_id=agent_id,
                                tenant_id=tenant_id,
                                logger=log,
                            )
                else:
                    log.error(f"Failed to obtain bearer token for AgentCore callback agent {agent_id}")
                continue  # done with this rs entry

            # Flatten resource attributes — handle three formats:
            # 1. Standard OTLP JSON:  resource.attributes = [{key, value}]
            # 2. AWS flat format:     resource_attrs = {k: v, ...}
            # 3. Claude flat format:  resource = {k: v, ...}  (no "attributes" sub-key)
            res_attrs = {}

            # AWS flat resource_attrs dict
            if isinstance(rs.get("resource_attrs"), dict):
                res_attrs.update(rs["resource_attrs"])

            # Standard OTLP: resource.attributes as list of {key, value}
            if isinstance(rs.get("resource", {}).get("attributes"), list):
                for a in rs["resource"]["attributes"]:
                    k = a.get("key")
                    v = a.get("value", {})
                    if isinstance(v, dict):
                        res_attrs[k] = v.get("stringValue") or v.get("intValue") or v.get("boolValue") or v.get("doubleValue") or ""
                    else:
                        res_attrs[k] = v
            # Standard OTLP: resource.attributes as plain dict
            elif isinstance(rs.get("resource", {}).get("attributes"), dict):
                res_attrs.update(rs["resource"]["attributes"])
            # Claude / any flat: resource is itself a plain dict (no "attributes" sub-key)
            elif isinstance(rs.get("resource"), dict) and "attributes" not in rs.get("resource", {}):
                res_attrs.update(rs["resource"])

            # Scope spans — support both camelCase (OTLP) and snake_case (AWS)
            scope_spans = rs.get("scopeSpans") or rs.get("scope_spans", [])

            # Claude flat single-span: synthesise a minimal scope_spans list
            if rs.get("_claude_flat") and rs.get("_span"):
                scope_spans = [{"spans": [rs["_span"]]}]

            for ss in scope_spans:
                spans = ss.get("spans", [])
                if not spans:
                    continue

                # Map spans by spanId to reconstruct root and child tool relationships
                span_by_id = {}
                for sp in spans:
                    sid = sp.get("spanId") or (sp.get("span_id") if isinstance(sp.get("span_id"), str) else "")
                    if sid:
                        span_by_id[sid] = sp

                child_tools_by_parent: dict[str, list[dict]] = {}

                # First pass: collect child tool and retriever spans
                for sp in spans:
                    p_id = sp.get("parentSpanId") or sp.get("parent_span_id")
                    if p_id and p_id in span_by_id:
                        sp_attrs = self._flatten_attributes(sp.get("attributes"))
                        sp_name = sp.get("name", "")

                        # Determine if this is a tool or retriever span
                        oi_kind = sp_attrs.get("openinference.span.kind", "").upper()
                        is_tool = (
                            oi_kind in ("TOOL", "RETRIEVER")
                            or "tool" in sp_name.lower()
                            or "tool" in sp_attrs.get("gen_ai.operation.name", "").lower()
                            or "gen_ai.tool.name" in sp_attrs
                            or "tool.name" in sp_attrs
                        )

                        if is_tool:
                            t_name = (
                                sp_attrs.get("gen_ai.tool.name")
                                or sp_attrs.get("tool.name")
                                or sp_attrs.get("tool_name")
                                or sp_name
                            )
                            t_input = (
                                sp_attrs.get("gen_ai.tool.input")
                                or sp_attrs.get("tool.parameters")
                                or sp_attrs.get("input.value")
                                or sp_attrs.get("input")
                                or ""
                            )
                            t_output = (
                                sp_attrs.get("gen_ai.tool.output")
                                or sp_attrs.get("tool.output")
                                or sp_attrs.get("output.value")
                                or sp_attrs.get("output")
                                or ""
                            )
                            status_code = sp.get("status", {}).get("code", 0)
                            t_err = status_code == 2

                            start_ns = int(sp.get("startTimeUnixNano") or sp.get("start_time_unix_nano") or time.time() * 1e9)
                            end_ns = int(sp.get("endTimeUnixNano") or sp.get("end_time_unix_nano") or time.time() * 1e9)

                            child_tools_by_parent.setdefault(p_id, []).append({
                                "name": t_name,
                                "input": str(t_input),
                                "output": str(t_output),
                                "start_ns": start_ns,
                                "end_ns": end_ns,
                                "is_error": t_err,
                            })

                # Span names that are purely internal sub-spans and must NEVER be
                # forwarded as a WXO trace, even when they arrive in their own
                # single-span HTTP request (which is the normal Anthropic OTel
                # collector behaviour — one span per batch).
                # Their token counts are stashed so the parent invocation span
                # (arriving in a later request) can pick them up via _pop_usage.
                #
                # AWS Bedrock AgentCore infra spans (memory R/W, HTTP calls) and
                # Strands internal spans are also subordinate — never forward them
                # as top-level WXO traces.
                _SUBORDINATE_SPAN_NAMES = {
                    # ── Anthropic ────────────────────────────────────────────
                    "anthropic.model_request",
                    "anthropic.model_response",
                    # ── AWS Strands ──────────────────────────────────────────
                    "execute_event_loop_cycle",   # internal loop span
                    "POST /invocations",          # HTTP entry-point
                    # ── Azure AI Foundry / Semantic Kernel ───────────────────
                    # OpenAI / Azure OpenAI completion sub-spans emitted by the
                    # az.ai.inference / openai SDK instrumentation layer.
                    # The agent-level span (create_agent_invocation / run_step)
                    # is the one we forward; these are its LLM implementation details.
                    "openai.chat",
                    "az.ai.inference.chat",
                    "ChatCompletionsClient.complete",
                    "AzureOpenAI.chat.completions.create",
                    "openai.responses.create",
                    # Azure Assistants API polling/thread sub-spans
                    "azure.ai.agent.create_run",
                    "azure.ai.agent.poll_run",
                    "azure.ai.agent.list_run_steps",
                    "azure.ai.agent.retrieve_run",
                    # ── Vertex AI (Gemini) ───────────────────────────────────
                    # gRPC / REST underlying calls emitted by google-cloud-aiplatform
                    "google.cloud.aiplatform.prediction",
                    "google.cloud.aiplatform.generate_content",
                    "PredictionServiceClient.generate_content",
                    "PredictionServiceClient.stream_generate_content",
                }

                # Subordinate span name *prefixes* (case-sensitive).
                _SUBORDINATE_SPAN_PREFIXES = (
                    # AWS Bedrock AgentCore SDK auto-instrumentation
                    "Bedrock AgentCore.",
                    # AWS Bedrock Runtime LLM calls (e.g. "chat us.amazon.nova-lite-v1:0")
                    "chat ",
                    # Azure HTTP/gRPC underlying calls
                    "GET https://",
                    "POST https://",
                    "PATCH https://",
                    # Vertex gRPC service calls
                    "google.cloud.",
                )

                # Span names that are the top-level agent invocation.  A span with
                # its parent inside the same payload is still forwarded if its name
                # is in this set (edge case: batched payloads).
                _AGENT_INVOCATION_SPAN_NAMES = {
                    # ── Anthropic ────────────────────────────────────────────
                    "anthropic.session.turn",
                    "anthropic.sessions.events.send",
                    "anthropic.messages.create",
                    # ── Generic ──────────────────────────────────────────────
                    "invoke_agent",
                    "agent.invoke",
                    "chain",
                    "llm",
                    # ── Azure AI Foundry / Semantic Kernel ───────────────────
                    # Semantic Kernel agent invocation root span
                    "microsoft.semantic_kernel.agent.invoke",
                    "create_agent_invocation",   # Azure AI Foundry Responses SDK
                    "agent_run",                 # Azure AI Foundry Assistants SDK
                    "run_step",                  # granular Assistants run-step span
                    # ── Vertex AI ────────────────────────────────────────────
                    # ADK (Agent Development Kit) agent root span
                    "vertex_ai.agent.invoke",
                    "adk.agent.invoke",
                }

                # Invocation span name *prefixes* — a span whose name starts with
                # one of these is treated as a top-level agent invocation even when
                # it has a parent in the same payload.
                _AGENT_INVOCATION_PREFIXES = (
                    "invoke_agent ",          # AWS Strands / generic
                    "generate_content ",      # Vertex Gemini direct SDK (no ADK)
                )

                def _is_subordinate(name: str) -> bool:
                    if name in _SUBORDINATE_SPAN_NAMES:
                        return True
                    return any(name.startswith(p) for p in _SUBORDINATE_SPAN_PREFIXES)

                def _is_invocation(name: str) -> bool:
                    if name in _AGENT_INVOCATION_SPAN_NAMES:
                        return True
                    return any(name.startswith(p) for p in _AGENT_INVOCATION_PREFIXES)

                # Second pass: process root / invocation spans
                for sp in spans:
                    sp_id = sp.get("spanId") or sp.get("span_id", "")
                    p_id = sp.get("parentSpanId") or sp.get("parent_span_id", "")

                    # If this span is already treated as a child tool of another span in this payload, skip it as root
                    if p_id and p_id in span_by_id and p_id in child_tools_by_parent:
                        continue

                    sp_name = sp.get("name", "")

                    # Always-subordinate spans: stash their tokens and skip,
                    # regardless of whether their parent is in this payload.
                    # This handles the common case where each span arrives in its
                    # own HTTP request from the OTel collector.
                    if _is_subordinate(sp_name):
                        _sub_attrs = self._flatten_attributes(sp.get("attributes"))
                        _sub_it = int(_sub_attrs.get("gen_ai.usage.input_tokens") or 0)
                        _sub_ot = int(_sub_attrs.get("gen_ai.usage.output_tokens") or 0)
                        _sub_trace = sp.get("traceId") or sp.get("trace_id") or ""
                        if _sub_trace and (_sub_it or _sub_ot):
                            self._record_usage(_sub_trace, _sub_it, _sub_ot)
                        continue

                    # Skip spans whose parent is in the same payload and that are
                    # not a recognised top-level agent invocation span.
                    if (
                        p_id
                        and p_id in span_by_id
                        and not _is_invocation(sp_name)
                    ):
                        continue

                    attrs = self._flatten_attributes(sp.get("attributes"))

                    # Extract prompt and response as plain text.
                    # gen_ai.input.messages / gen_ai.output.messages are JSON
                    # message arrays (e.g. from the Anthropic SDK:
                    #   [{"role":"user","parts":[{"type":"text","content":"..."}]}]
                    # or the standard OTel GenAI format:
                    #   [{"role":"user","content":"..."}]
                    # We must unwrap to plain text before passing to
                    # build_otlp_payload, which re-wraps them itself.
                    def _unwrap_messages(raw: str) -> str:
                        """Extract plain text from a JSON gen_ai messages array.
                        Returns raw if it is already plain text."""
                        if not raw or not raw.strip().startswith("["):
                            return raw
                        try:
                            msgs = json.loads(raw)
                            parts: list[str] = []
                            for m in msgs if isinstance(msgs, list) else []:
                                # Standard OTel GenAI: {"role":"...", "content":"..."}
                                c = m.get("content")
                                if isinstance(c, str) and c:
                                    parts.append(c)
                                    continue
                                # Anthropic SDK: {"role":"...", "parts":[{"type":"text","content":"..."}]}
                                for p in m.get("parts") or []:
                                    if isinstance(p, dict) and p.get("type") == "text":
                                        pc = p.get("content", "")
                                        if pc:
                                            parts.append(pc)
                                    elif isinstance(p, str) and p:
                                        parts.append(p)
                            return "\n".join(parts) if parts else raw
                        except Exception:
                            return raw

                    _raw_prompt = (
                        attrs.get("gen_ai.prompt")
                        or attrs.get("input.value")
                        or attrs.get("input")
                        or attrs.get("prompt")
                        or ""
                    )
                    _raw_response = (
                        attrs.get("gen_ai.completion")
                        or attrs.get("output.value")
                        or attrs.get("output")
                        or attrs.get("response")
                        or ""
                    )
                    # Prefer plain-text fields; fall back to unwrapping message arrays
                    if not _raw_prompt:
                        _raw_prompt = _unwrap_messages(attrs.get("gen_ai.input.messages", ""))
                    if not _raw_response:
                        _raw_response = _unwrap_messages(attrs.get("gen_ai.output.messages", ""))
                    prompt = _raw_prompt
                    response = _raw_response

                    # Extract events (OpenTelemetry GenAI / Anthropic / Semantic Kernel events)
                    events = sp.get("events", [])
                    event_prompts: list[str] = []
                    event_responses: list[str] = []
                    reasoning_steps: list[str] = []
                    # Scores that arrive as span events (e.g. LangChain eval callbacks,
                    # Phoenix/Arize eval exporters).  Merged with attribute-level scores
                    # before posting to WXO.
                    event_score_attrs: dict = {}

                    for evt in events:
                        e_attrs = self._flatten_attributes(evt.get("attributes"))
                        e_name = evt.get("name", "")
                        e_content = (
                            e_attrs.get("content")
                            or e_attrs.get("gen_ai.user.message.content")
                            or e_attrs.get("gen_ai.choice.message")
                            or e_attrs.get("message")
                            or ""
                        )

                        if e_name in ("gen_ai.user.message", "user_message", "prompt"):
                            if e_content:
                                event_prompts.append(f"[user]: {e_content}")
                        elif e_name in ("gen_ai.system.message", "system_message"):
                            if e_content:
                                event_prompts.append(f"[system]: {e_content}")
                        elif e_name in ("gen_ai.choice", "gen_ai.assistant.message", "choice", "assistant_message"):
                            if e_content:
                                event_responses.append(str(e_content))
                        elif e_name in ("gen_ai.tool.message", "tool_result"):
                            if e_content:
                                event_prompts.append(f"[tool_result]: {e_content}")
                        elif e_name in (
                            "gen_ai.reasoning", "gen_ai.thinking",
                            "anthropic.thinking", "model.reasoning",
                        ):
                            # Reasoning / chain-of-thought content — becomes a
                            # Langfuse ``steps`` entry of type "reasoning".
                            r_text = (
                                e_attrs.get("gen_ai.reasoning.content")
                                or e_attrs.get("thinking")
                                or e_content
                            )
                            if r_text:
                                reasoning_steps.append(str(r_text))
                        elif e_name.startswith(("eval.", "eval.score.", "langfuse.score.", "score.", "llm.eval.")):
                            # Eval framework emitting scores as named span events
                            # (e.g. "eval.relevance" event with value in attributes).
                            score_val = (
                                e_attrs.get("value")
                                or e_attrs.get("score")
                                or e_attrs.get("result")
                                or e_content
                            )
                            if score_val not in (None, ""):
                                event_score_attrs[e_name] = score_val
                        else:
                            # Generic: any event whose attributes carry eval.* keys
                            # (e.g. Phoenix SpanEvaluations use event attrs).
                            for ek, ev in e_attrs.items():
                                if ek.lower().startswith(("eval.", "score.", "langfuse.score.", "llm.eval.")):
                                    event_score_attrs.setdefault(ek, ev)

                    # Also pick up reasoning from span attributes directly
                    # (e.g. Anthropic SDK extended-thinking attribute, or
                    # LangChain/LangGraph additional_kwargs["reasoning"]).
                    _attr_reasoning = (
                        attrs.get("gen_ai.reasoning.content")
                        or attrs.get("anthropic.thinking")
                        or attrs.get("model.reasoning")
                    )
                    if _attr_reasoning and _attr_reasoning not in reasoning_steps:
                        reasoning_steps.append(str(_attr_reasoning))

                    if not prompt and event_prompts:
                        prompt = "\n".join(event_prompts)
                    if not response and event_responses:
                        response = "\n".join(event_responses)

                    model_name = (
                        attrs.get("gen_ai.request.model")
                        or attrs.get("gen_ai.response.model")
                        or attrs.get("llm.model_name")
                        or attrs.get("model")
                        or attrs.get("model_name")
                        or "agent_model"
                    )

                    candidate_keys = [
                        explicit_agent_id,
                        # AWS Strands/AgentCore: harness runtime ID (most specific)
                        attrs.get("aws.agent.runtime.id"),
                        res_attrs.get("aws.agent.runtime.id"),
                        # AWS WXO-native agent IDs from resource_attrs
                        res_attrs.get("wxo.agent.id"),
                        res_attrs.get("wxo.agent.name"),
                        # Azure AI Foundry / Semantic Kernel agent IDs
                        attrs.get("az.ai.agent.id"),
                        attrs.get("azure.client.agent.id"),
                        attrs.get("az.ai.agent.name"),
                        res_attrs.get("az.ai.agent.id"),
                        res_attrs.get("azure.client.agent.id"),
                        # Vertex AI / GCP — project-scoped agent name
                        res_attrs.get("gcp.resource.type"),
                        attrs.get("vertex_ai.agent.id"),
                        attrs.get("gcp.agent.id"),
                        # Generic
                        attrs.get("agent.id"),
                        attrs.get("agent_id"),
                        attrs.get("gen_ai.agent.id"),
                        attrs.get("anthropic.agent.id"),
                        attrs.get("langfuse.agent.id"),
                        attrs.get("agent.name"),
                        attrs.get("agent_name"),
                        attrs.get("gen_ai.agent.name"),
                        attrs.get("anthropic.agent.name"),
                        res_attrs.get("service.name"),
                        res_attrs.get("service.namespace"),
                        res_attrs.get("agent.name"),
                        res_attrs.get("gen_ai.agent.name"),
                        res_attrs.get("agent.id"),
                        res_attrs.get("agent_id"),
                        res_attrs.get("anthropic.agent.id"),
                        res_attrs.get("app.name"),
                        res_attrs.get("application"),
                        sp.get("name"),
                        str(model_name),
                    ]

                    try:
                        log.info(
                            "Received span: name=%r resource_attrs=%s span_attrs=%s",
                            sp.get("name"),
                            json.dumps(res_attrs, default=str)[:1500],
                            json.dumps(attrs, default=str)[:3000],
                        )
                    except Exception:
                        pass

                    # Accumulate any token usage carried directly on this
                    # invocation span (uncommon for session.turn; the tokens are
                    # normally on the subordinate model_request span which was
                    # already stashed above and skipped).
                    trace_key = sp.get("traceId") or sp.get("trace_id") or ""
                    span_it = int(attrs.get("gen_ai.usage.input_tokens") or 0)
                    span_ot = int(attrs.get("gen_ai.usage.output_tokens") or 0)
                    if trace_key and (span_it or span_ot):
                        self._record_usage(trace_key, span_it, span_ot)

                    routing = self.resolve_wxo_agent(
                        candidate_keys=candidate_keys,
                        default_name=res_attrs.get("service.name") or attrs.get("agent.name") or "external_agent",
                    )

                    agent_id = routing["agent_id"]
                    tenant_id = routing["tenant_id"]
                    export_url = routing["export_url"]
                    api_key = routing["api_key"]
                    token_url = routing["token_url"]
                    env_name = routing["environment"]
                    # Override environment from AWS resource_attrs if present
                    if res_attrs.get("wxo.environment"):
                        env_name = res_attrs["wxo.environment"]
                    clean_name = routing["agent_name"]
                    # Anthropic Sessions SDK sets gen_ai.provider.name="anthropic" on spans;
                    # the direct Messages API does not — fall back to checking gen_ai.system
                    # so agent names resolve correctly for both paths.
                    _is_anthropic = (
                        attrs.get("gen_ai.provider.name") == "anthropic"
                        or (attrs.get("gen_ai.system") or "").lower() in ("anthropic", "claude-platform")
                        or (res_attrs.get("gen_ai.system") or "").lower() in ("anthropic", "claude-platform")
                    )
                    _anthropic_name = (
                        attrs.get("gen_ai.agent.name")
                        or res_attrs.get("gen_ai.agent.name")
                        or res_attrs.get("agent.name")
                    )
                    if _is_anthropic and _anthropic_name:
                        clean_name = re.sub(r"[^a-zA-Z0-9_-]", "_", str(_anthropic_name)).lower()
                    # AWS Strands: use wxo.agent.name from resource_attrs as display name
                    if res_attrs.get("wxo.agent.name") and not clean_name:
                        clean_name = re.sub(r"[^a-zA-Z0-9_-]", "_", str(res_attrs["wxo.agent.name"])).lower()

                    if not agent_id or not export_url or not auth_configured(api_key):
                        log.warning(
                            f"Skipping span: no WXO agent mapped or missing config "
                            f"(agent_id={agent_id!r}, export_url={bool(export_url)}, "
                            f"auth={auth_configured(api_key)} mode={deployment_mode()}, "
                            f"candidate_keys={[str(k) for k in candidate_keys if k]})"
                        )
                        continue
                    log.info(f"Routing span: matched_key={routing['matched_key']!r} -> wxo_agent_id={agent_id}")

                    # Token usage
                    it = int(
                        attrs.get("gen_ai.usage.input_tokens")
                        or attrs.get("llm.usage.prompt_tokens")
                        or attrs.get("usage.prompt_tokens")
                        or 0
                    )
                    ot = int(
                        attrs.get("gen_ai.usage.output_tokens")
                        or attrs.get("llm.usage.completion_tokens")
                        or attrs.get("usage.completion_tokens")
                        or 0
                    )

                    if not (it or ot) and trace_key:
                        it, ot = self._pop_usage(trace_key)

                    session_id = (
                        attrs.get("session.id")
                        or attrs.get("anthropic.session.id")
                        or attrs.get("thread.id")
                        or attrs.get("conversation.id")
                        or attrs.get("anthropic.session_id")
                        or attrs.get("langfuse.session.id")
                        # Azure AI Foundry: Assistants thread / Responses session
                        or attrs.get("az.ai.agent.thread.id")
                        or attrs.get("gen_ai.conversation.id")
                        or attrs.get("azure.session.id")
                        # Vertex AI ADK: session identifier
                        or attrs.get("vertex_ai.session.id")
                        or attrs.get("adk.session.id")
                        # AWS Strands: harness.id as session fallback
                        or attrs.get("harness.id")
                        or ""
                    )
                    user_id = (
                        attrs.get("user.id")
                        or attrs.get("user_id")
                        or attrs.get("langfuse.user.id")
                        or attrs.get("anthropic.user_id")
                        # Azure: end-user identifier
                        or attrs.get("az.ai.agent.user_id")
                        or attrs.get("azure.user.id")
                        # Anthropic org/workspace as user context fallback
                        or attrs.get("anthropic.organization.id")
                        or ""
                    )

                    start_ns = int(sp.get("startTimeUnixNano") or sp.get("start_time_unix_nano") or time.time() * 1e9)
                    end_ns = int(sp.get("endTimeUnixNano") or sp.get("end_time_unix_nano") or (start_ns + 1_000_000))

                    _status = sp.get("status", {})
                    # status may be a dict {"code": 2} or a plain string "ERROR"/"OK"
                    if isinstance(_status, dict):
                        status_code = _status.get("code", 0)
                    else:
                        status_code = 2 if str(_status).upper() in ("ERROR", "STATUS_CODE_ERROR") else 0
                    is_err = status_code == 2

                    tool_calls = child_tools_by_parent.get(sp_id, [])
                    # Anthropic Managed Agents emit no child tool spans; the tool call is a
                    # {"type":"tool_call","name":..,"arguments":..} part in gen_ai.output.messages
                    # (content mode) of the turn that stops with "requires_action".
                    if not tool_calls and "tool_call" in (attrs.get("gen_ai.output.messages") or ""):
                        try:
                            for _m in json.loads(attrs["gen_ai.output.messages"]):
                                for _p in _m.get("parts") or []:
                                    if isinstance(_p, dict) and _p.get("type") == "tool_call" and _p.get("name"):
                                        tool_calls.append({
                                            "name": _p["name"],
                                            "input": json.dumps(_p.get("arguments") or {}),
                                            "output": "",
                                            "start_ns": start_ns,
                                            "end_ns": end_ns,
                                            "is_error": False,
                                        })
                        except (ValueError, AttributeError, TypeError):
                            pass

                    # Construct WXO Payload
                    wxo_payload = build_otlp_payload(
                        agent_id=agent_id,
                        agent_name=clean_name,
                        tenant_id=tenant_id,
                        environment=env_name,
                        prompt=str(prompt or "External agent invocation"),
                        response=str(response or "[Invocation completed]"),
                        start_ns=start_ns,
                        end_ns=end_ns,
                        input_tokens=it,
                        output_tokens=ot,
                        is_error=is_err,
                        error_msg=attrs.get("error.message", ""),
                        platform=_resolve_platform(attrs, res_attrs),
                        model_name=str(model_name),
                        session_id=str(session_id),
                        trace_id=sp.get("traceId") or sp.get("trace_id", ""),
                        span_id=sp_id,
                        user_id=str(user_id),
                        tool_calls=tool_calls,
                        reasoning_steps=reasoning_steps or None,
                    )

                    # Get IAM token and ship
                    token = get_bearer_token(api_key, token_url, logger=log)
                    if token:
                        job_id = post_to_wxo(
                            payload=wxo_payload,
                            bearer_token=token,
                            export_url=export_url,
                            agent_id=agent_id,
                            tenant_id=tenant_id,
                            logger=log,
                        )
                        if job_id:
                            job_ids.append(job_id)
                            # Post any conversation-level scores (relevance, toxicity,
                            # faithfulness, etc.) extracted from span attributes AND
                            # from span events (eval framework callbacks).
                            # event_score_attrs collected in the event loop above is
                            # merged here so both sources are captured.
                            merged_score_attrs = {**attrs, **event_score_attrs}
                            span_scores = self._extract_scores(merged_score_attrs)
                            if span_scores:
                                post_scores_to_wxo(
                                    scores=span_scores,
                                    trace_id=job_id,
                                    bearer_token=token,
                                    export_url=export_url,
                                    agent_id=agent_id,
                                    tenant_id=tenant_id,
                                    logger=log,
                                )
                    else:
                        log.error(f"Failed to obtain bearer token for agent {agent_id}")

        return job_ids

    _usage_by_trace: dict = {}
    _usage_ttl: float = 600.0

    @classmethod
    def _record_usage(cls, trace_id: str, input_tokens: int, output_tokens: int) -> None:
        now = time.time()
        for k in [k for k, v in cls._usage_by_trace.items() if now - v[0] > cls._usage_ttl]:
            cls._usage_by_trace.pop(k, None)
        _, i, o = cls._usage_by_trace.get(trace_id, (now, 0, 0))
        cls._usage_by_trace[trace_id] = (now, i + input_tokens, o + output_tokens)

    @classmethod
    def _pop_usage(cls, trace_id: str) -> tuple[int, int]:
        _, i, o = cls._usage_by_trace.pop(trace_id, (0, 0, 0))
        return i, o

    @staticmethod
    def _flatten_attributes(attrs) -> dict:
        """Flatten attributes from dict or list of {key, value} pairs."""
        if not attrs:
            return {}
        if isinstance(attrs, dict):
            res = {}
            for k, v in attrs.items():
                if isinstance(v, dict):
                    res[k] = v.get("stringValue") or v.get("intValue") or v.get("boolValue") or v.get("doubleValue") or ""
                else:
                    res[k] = v
            return res
        if isinstance(attrs, list):
            res = {}
            for item in attrs:
                k = item.get("key")
                v = item.get("value", {})
                if isinstance(v, dict):
                    res[k] = v.get("stringValue") or v.get("intValue") or v.get("boolValue") or v.get("doubleValue") or ""
                else:
                    res[k] = v
            return res
        return {}

    @staticmethod
    def _extract_scores(attrs: dict) -> list[dict]:
        """
        Extract Langfuse-compatible score objects from a flattened span attribute
        dict.  Recognised attribute patterns (all case-insensitive key prefixes):

          eval.<name>                  e.g. eval.relevance = 0.92
          eval.score.<name>            e.g. eval.score.toxicity = 0.01
          langfuse.score.<name>        e.g. langfuse.score.coherence = 1.0
          score.<name>                 e.g. score.faithfulness = 0.87
          llm.eval.<name>              e.g. llm.eval.groundedness = 0.75

        The value may be:
          - A float/int  → NUMERIC score
          - A string that looks like a float  → NUMERIC score
          - Any other string  → CATEGORICAL score with value=0

        Returns a list of score dicts ready for ``post_scores_to_wxo``.
        """
        _SCORE_PREFIXES = (
            "eval.",
            "eval.score.",
            "langfuse.score.",
            "score.",
            "llm.eval.",
        )
        scores: list[dict] = []
        seen: set[str] = set()

        for raw_key, raw_val in attrs.items():
            key_lower = (raw_key or "").lower()
            matched_prefix = ""
            for pfx in _SCORE_PREFIXES:
                if key_lower.startswith(pfx):
                    matched_prefix = pfx
                    break
            if not matched_prefix:
                continue

            score_name = raw_key[len(matched_prefix):]  # preserve original casing
            if not score_name or score_name in seen:
                continue
            seen.add(score_name)

            # Determine numeric value and data type
            try:
                numeric_val = float(raw_val)
                data_type = "NUMERIC"
                string_val = None
            except (TypeError, ValueError):
                # Categorical — keep the string, set numeric value to 0
                numeric_val = 0.0
                data_type = "CATEGORICAL"
                string_val = str(raw_val) if raw_val not in (None, "") else None

            entry: dict = {
                "name":     score_name,
                "value":    numeric_val,
                "dataType": data_type,
                "source":   "API",
                "comment":  None,
                "metadata": {},
            }
            if string_val is not None:
                entry["stringValue"] = string_val

            scores.append(entry)

        return scores

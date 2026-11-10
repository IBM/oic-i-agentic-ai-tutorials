"""
function_app.py
===============
Azure Function — Timer trigger (every 15 seconds).

Equivalent of AWS AgentCore's built-in observability callback:
  • AWS:   AgentCore fires Lambda after every invocation automatically
  • Azure: App Insights captures every invocation in AppGenAIContent;
           this Function polls that table every 15 s and forwards each
           new invocation to WXO Agent Analytics — zero change to callers.

Flow:
  1. User calls agent directly (any URL, any protocol, unchanged)
  2. Azure AI Foundry auto-emits OTEL → App Insights → AppGenAIContent
  3. This function wakes up every 15 s, queries new rows via KQL
  4. For each root span (invoke_agent), builds an OTLP span and POSTs to WXO
  5. Cursor advances so nothing is double-counted

Environment variables (Application Settings):
  LOG_ANALYTICS_WORKSPACE_ID   <your-log-analytics-workspace-id>
  WXO_TENANT_ID / WXO_AGENT_ID / WXO_API_KEY / WXO_TOKEN_URL
  WXO_OTEL_EXPORT_URL / WXO_ENVIRONMENT_NAME
  WXO_AGENT_MAP                JSON map of Foundry agent name -> WXO agent UUID
                                e.g. '{"my-agent": "wxo-uuid", ...}'
  WXO_AGENT_ID                 Fallback WXO agent UUID (used when agent not in WXO_AGENT_MAP)
  WXO_AGENT_DISPLAY_NAME       Fallback display name
  AzureWebJobsStorage          (auto-set by Azure Functions — used for cursor blob)
"""

from __future__ import annotations

import base64
import hmac
import hashlib
import json
import logging
import os
import re
import secrets
import ssl
import time
import uuid
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import azure.functions as func

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Shared helpers — try repo path (dev/CI), fall back to inline copy
# ---------------------------------------------------------------------------
_wxo_span = None
try:
    import os as _os, sys as _sys
    _repo_root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    if _repo_root not in _sys.path:
        _sys.path.insert(0, _repo_root)
    import shared.wxo_span as _wxo_span   # type: ignore[import]
except Exception:
    pass

# ---------------------------------------------------------------------------
# Config — poll / cursor settings
# ---------------------------------------------------------------------------

_WORKSPACE_ID  = os.environ.get("LOG_ANALYTICS_WORKSPACE_ID", "")
_STORAGE_CONN  = os.environ.get("AzureWebJobsStorage", "")

_CURSOR_CONT   = "azure-webjobs-hosts"
_CURSOR_BLOB   = "wxo-cursor/_all.txt"
# Agent map shared by ALL Function App instances (written by wire_agent.py). App settings
# are read once per process, so an instance that started before a redeploy keeps routing by
# the previous run's map; the blob is re-read on every poll so no instance can be stale.
_AGENT_MAP_BLOB = "wxo-cursor/agent_map.json"

# App Insights ingestion lag can be several minutes; use a wide lookback so a
# late-arriving row is never outside the window when the poller fires.
# Cursor advances on ingestion_time(), so old rows are not re-processed.
_POLL_WINDOW_MIN = 60

_SEEN_TRACE_IDS: set[str] = set()
_SEEN_MAX = 2000

# ---------------------------------------------------------------------------
# WXO config helpers — env vars
# ---------------------------------------------------------------------------

_ENV_CACHE: dict[str, str] = {}


def _get_config(name: str) -> str:
    if name not in _ENV_CACHE:
        _ENV_CACHE[name] = os.environ.get(name, "").strip()
    return _ENV_CACHE[name]


# ---------------------------------------------------------------------------
# Token counting — stdlib-only cl100k_base approximation
# ---------------------------------------------------------------------------

_TOKEN_PAT = re.compile(
    r"(?i:'s|'t|'re|'ve|'m|'ll|'d)"
    r"|[^\W\d_]+"
    r"|\d{1,3}"
    r"|[^\w\s]+",
    re.UNICODE,
)


def _count_tokens(text: str) -> int:
    return len(_TOKEN_PAT.findall(text)) if text else 0


# ---------------------------------------------------------------------------
# Log Analytics token (Managed Identity → az CLI fallback)
# ---------------------------------------------------------------------------

_LA_TOKEN_CACHE: dict = {}


def _get_la_token() -> str:
    now = time.time()
    if _LA_TOKEN_CACHE.get("token") and now < _LA_TOKEN_CACHE.get("expires_at", 0):
        return _LA_TOKEN_CACHE["token"]

    resource          = "https://api.loganalytics.io/"
    identity_endpoint = os.environ.get("IDENTITY_ENDPOINT", "")
    identity_header   = os.environ.get("IDENTITY_HEADER", "")

    if identity_endpoint and identity_header:
        try:
            req = Request(f"{identity_endpoint}?api-version=2019-08-01&resource={resource}")
            req.add_header("X-IDENTITY-HEADER", identity_header)
            with urlopen(req, timeout=10) as resp:
                body = json.loads(resp.read())
            token = body["access_token"]
            ttl   = max(int(body.get("expires_in", 3600)) - 300, 60)
            _LA_TOKEN_CACHE.update(token=token, expires_at=now + ttl)
            logger.info("[LA] Token via Managed Identity")
            return token
        except Exception as exc:
            logger.warning(f"[LA] MSI failed: {exc}")

    import subprocess
    result = subprocess.run(
        ["az", "account", "get-access-token", "--resource", resource,
         "--query", "accessToken", "-o", "tsv"],
        capture_output=True, text=True, check=True
    )
    token = result.stdout.strip()
    _LA_TOKEN_CACHE.update(token=token, expires_at=now + 3300)
    logger.info("[LA] Token via az CLI (local dev)")
    return token


# ---------------------------------------------------------------------------
# WXO bearer token — cached with TTL
# ---------------------------------------------------------------------------

# Per-tenant token cache — keyed by (api_key, token_url) so each tenant gets
# its own independently-refreshed token.
_TOKEN_CACHE: dict[tuple[str, str], dict] = {}
_TOKEN_REFRESH_MARGIN = 300
_TOKEN_DEFAULT_TTL    = 3600 - 300

# Deployment mode: "cloud" (IBM Cloud SaaS, API-key → IAM token) or
# "cpd" (on-prem Cloud Pak for Data, username/password → /icp4d-api/v1/authorize).
_CPD_TOKEN_CACHE: dict[tuple[str, str], dict] = {}
_CPD_TOKEN_TTL = 12 * 3600 - 300     # CPD tokens carry no expires_in


def _deployment_mode() -> str:
    return "cpd" if _get_config("WXO_DEPLOYMENT_MODE").lower() == "cpd" else "cloud"


def _ssl_context() -> ssl.SSLContext:
    """CPD uses self-signed certs → skip verification unless CPD_VERIFY_TLS=true."""
    if _deployment_mode() == "cpd" and _get_config("CPD_VERIFY_TLS").lower() != "true":
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    return ssl.create_default_context()


def _cpd_export_url() -> str:
    """Explicit URL wins; otherwise build it from the CPD_* settings."""
    explicit = _get_config("CPD_EXPORT_URL") or _get_config("WXO_OTEL_EXPORT_URL")
    if explicit:
        return explicit
    host, ns, iid = _get_config("CPD_HOST_URL"), _get_config("CPD_NAMESPACE"), _get_config("CPD_INSTANCE_ID")
    if not (host and ns and iid):
        return ""
    return f"{host.rstrip('/')}/{ns}/instances/{iid}/v1/agentops-v3/traces"


def _extract_tenant_id(url: str) -> str:
    if url:
        m = re.search(r'/instances/([^/?#]+)', url)
        if m:
            return m.group(1).strip()
    return ""


def _get_cpd_bearer_token() -> str:
    """POST username/password to <CPD_HOST_URL>/icp4d-api/v1/authorize."""
    host     = _get_config("CPD_HOST_URL").rstrip("/")
    username = _get_config("CPD_USERNAME")
    password = _get_config("CPD_PASSWORD")
    if not (host and username and password):
        raise RuntimeError("CPD_HOST_URL, CPD_USERNAME and CPD_PASSWORD must be set")

    cache_key = (username, host)
    now = time.time()
    entry = _CPD_TOKEN_CACHE.get(cache_key, {})
    if entry.get("token") and now < entry.get("expires_at", 0):
        return entry["token"]

    url = f"{host}/icp4d-api/v1/authorize"
    logger.info(f"[TOKEN] CPD authorize at {url}")
    req = Request(
        url,
        data=json.dumps({"username": username, "password": password}).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=30, context=_ssl_context()) as resp:
            body = json.loads(resp.read())
    except HTTPError as exc:
        raise RuntimeError(f"CPD token request failed ({exc.code}): {exc.read().decode()}") from exc
    token = body.get("token")
    if not token:
        raise RuntimeError("No token in CPD authorize response")
    _CPD_TOKEN_CACHE[cache_key] = {"token": token, "expires_at": now + _CPD_TOKEN_TTL}
    return token


def _get_bearer_token(api_key: str = "", token_url: str = "") -> str:
    """Return a WXO bearer token for the active deployment mode.

    cpd   : CPD_USERNAME/CPD_PASSWORD → CPD authorize endpoint (api_key/token_url ignored).
    cloud : exchange *api_key* for an IBM IAM bearer token. Falls back to the
            WXO_API_KEY / WXO_TOKEN_URL env vars when no explicit credentials
            are provided. Cache is keyed by (api_key, token_url).
    """
    if _deployment_mode() == "cpd":
        return _get_cpd_bearer_token()
    api_key   = api_key   or _get_config("WXO_API_KEY")
    token_url = token_url or _get_config("WXO_TOKEN_URL")
    if not api_key or not token_url:
        raise RuntimeError("WXO_API_KEY and WXO_TOKEN_URL must be set")

    cache_key = (api_key, token_url)
    now = time.time()
    entry = _TOKEN_CACHE.get(cache_key, {})
    if entry.get("token") and now < entry.get("expires_at", 0):
        remaining = int(entry["expires_at"] - now)
        logger.info(f"[TOKEN] Reusing cached token (expires in {remaining}s)")
        return entry["token"]

    logger.info(f"[TOKEN] Exchanging API key at {token_url}")
    if "/identity/token" in token_url:
        from urllib.parse import urlencode as _ue
        _data  = _ue({"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": api_key}).encode()
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
            f"Token exchange failed ({exc.code}): {exc.read().decode()}"
        ) from exc

    token = body.get("token") or body.get("access_token")
    if not token:
        raise RuntimeError(f"No token in response: {body}")

    raw_ttl = int(body.get("expires_in", _TOKEN_DEFAULT_TTL + _TOKEN_REFRESH_MARGIN) or 0)
    ttl     = max(raw_ttl - _TOKEN_REFRESH_MARGIN, 60)
    _TOKEN_CACHE[cache_key] = {"token": token, "expires_at": now + ttl}
    logger.info(f"[TOKEN] Bearer token obtained (TTL={raw_ttl}s, cached for {ttl}s)")
    return token


# ---------------------------------------------------------------------------
# WXO OTLP POST
# ---------------------------------------------------------------------------

def _post_to_wxo(payload: dict, bearer_token: str, agent_id: str, tenant_id: str,
                 export_url: str = "") -> str:
    """POST OTLP payload to WXO.  *export_url* overrides WXO_OTEL_EXPORT_URL env var.

    Tenant header is sent in cloud mode only; CPD has no tenant header.
    """
    if _deployment_mode() == "cpd":
        export_url = export_url or _cpd_export_url()
    else:
        export_url = export_url or _get_config("WXO_OTEL_EXPORT_URL")
    if not export_url:
        raise RuntimeError("WXO_OTEL_EXPORT_URL (or CPD_HOST_URL/CPD_NAMESPACE/CPD_INSTANCE_ID) must be set")

    body = json.dumps(payload).encode()
    logger.info(f"[WXO] POST {len(body)} bytes → {export_url}")
    headers = {
        "Authorization":   f"Bearer {bearer_token}",
        "Content-Type":    "application/json",
        "User-Agent":      "curl/7.68.0",
        "x-ibm-agent-id":  agent_id,
    }
    if _deployment_mode() == "cloud":
        headers["x-ibm-tenant-id"] = tenant_id
    req = Request(export_url, data=body, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=30, context=_ssl_context()) as resp:
            resp_body = json.loads(resp.read())
            job_id    = resp_body.get("data", {}).get("id", "N/A")
            logger.info(f"[WXO] HTTP {resp.status} | job_id={job_id}")
            return job_id
    except HTTPError as exc:
        raise RuntimeError(f"WXO POST failed ({exc.code}): {exc.read().decode()}") from exc
    except URLError as exc:
        raise RuntimeError(f"WXO POST failed: {exc.reason}") from exc


def _post_scores_to_wxo(
    scores: list[dict],
    bearer_token: str,
    agent_id: str,
    agent_name: str,
    trace_id: str,
    tenant_id: str,
    export_url: str,
) -> None:
    """POST evaluation scores to the WXO scores endpoint.

    Derives the scores URL from *export_url* by replacing
    ``inject/traces`` with ``inject/scores``.  Silently skips when
    *scores* is empty or the URL cannot be derived.
    """
    if not scores:
        return
    scores_url = export_url.replace("inject/traces", "inject/scores")
    if scores_url == export_url:
        logger.warning("[WXO] Cannot derive scores URL from export_url — skipping score POST")
        return

    stamped: list[dict] = []
    for sc in scores:
        entry = dict(sc)
        entry.setdefault("traceId",    trace_id)
        entry.setdefault("agentId",    agent_id)
        entry.setdefault("agentName",  agent_name)
        stamped.append(entry)

    body = json.dumps({"scores": stamped}).encode()
    headers = {
        "Authorization":   f"Bearer {bearer_token}",
        "Content-Type":    "application/json",
        "User-Agent":      "curl/7.68.0",
        "x-ibm-agent-id":  agent_id,
    }
    if _deployment_mode() == "cloud":
        headers["x-ibm-tenant-id"] = tenant_id
    req = Request(scores_url, data=body, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=30, context=_ssl_context()) as resp:
            logger.info(f"[WXO] scores POST {resp.status} trace_id={trace_id} n={len(stamped)}")
    except Exception as exc:
        logger.warning(f"[WXO] scores POST failed: {exc}")


# ---------------------------------------------------------------------------
# Cursor — Blob REST API (stdlib urllib only, no SDK)
# ---------------------------------------------------------------------------

def _parse_storage_conn(conn: str) -> tuple[str, str]:
    parts = dict(p.split("=", 1) for p in conn.split(";") if "=" in p)
    return parts.get("AccountName", ""), parts.get("AccountKey", "")


def _blob_url(account: str, blob_path: str = _CURSOR_BLOB) -> str:
    return f"https://{account}.blob.core.windows.net/{_CURSOR_CONT}/{blob_path}"


def _storage_auth_header(account: str, key: str, verb: str,
                         content_length: int, content_type: str,
                         date_str: str, blob_path: str) -> str:
    canonicalized_resource = f"/{account}/{_CURSOR_CONT}/{blob_path}"
    string_to_sign = "\n".join([
        verb,
        "",   # Content-Encoding
        "",   # Content-Language
        str(content_length) if content_length > 0 else "",
        "",   # Content-MD5
        content_type if content_type else "",
        "",   # Date (empty — using x-ms-date)
        "",   # If-Modified-Since
        "",   # If-Match
        "",   # If-None-Match
        "",   # If-Unmodified-Since
        "",   # Range
        f"x-ms-blob-type:BlockBlob\nx-ms-date:{date_str}\nx-ms-version:2020-04-08",
        canonicalized_resource,
    ])
    decoded_key = base64.b64decode(key)
    sig = base64.b64encode(
        hmac.new(decoded_key, string_to_sign.encode("utf-8"), hashlib.sha256).digest()
    ).decode()
    return f"SharedKey {account}:{sig}"


def _read_agent_map_blob() -> dict | None:
    """Return the shared agent map from blob storage, or None if absent/unreadable."""
    if not _STORAGE_CONN:
        return None
    try:
        account, key = _parse_storage_conn(_STORAGE_CONN)
        if not account or not key:
            return None
        date_str = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        auth = _storage_auth_header(account, key, "GET", 0, "", date_str, _AGENT_MAP_BLOB)
        req = Request(_blob_url(account, _AGENT_MAP_BLOB), method="GET")
        req.add_header("x-ms-date", date_str)
        req.add_header("x-ms-version", "2020-04-08")
        req.add_header("x-ms-blob-type", "BlockBlob")
        req.add_header("Authorization", auth)
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        return data if isinstance(data, dict) else None
    except Exception as exc:
        logger.info(f"[mapping] agent map blob not available — using app setting only ({exc})")
        return None


def _read_cursor() -> str:
    default = (datetime.now(timezone.utc).timestamp() - _POLL_WINDOW_MIN * 60)
    default_ts = datetime.fromtimestamp(default, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if not _STORAGE_CONN:
        return default_ts
    try:
        account, key = _parse_storage_conn(_STORAGE_CONN)
        if not account or not key:
            return default_ts
        date_str = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        auth = _storage_auth_header(account, key, "GET", 0, "", date_str, _CURSOR_BLOB)
        req = Request(_blob_url(account), method="GET")
        req.add_header("x-ms-date", date_str)
        req.add_header("x-ms-version", "2020-04-08")
        req.add_header("x-ms-blob-type", "BlockBlob")
        req.add_header("Authorization", auth)
        with urlopen(req, timeout=5) as resp:
            ts = resp.read().decode().strip()
        logger.info(f"[cursor] read: {ts}")
        return ts
    except Exception:
        logger.info(f"[cursor] not found — default: {default_ts}")
        return default_ts


def _write_cursor(ts: str) -> None:
    if not _STORAGE_CONN:
        return
    try:
        account, key = _parse_storage_conn(_STORAGE_CONN)
        if not account or not key:
            return
        data = ts.encode()
        date_str = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        auth = _storage_auth_header(account, key, "PUT", len(data),
                                    "text/plain", date_str, _CURSOR_BLOB)
        req = Request(_blob_url(account), data=data, method="PUT")
        req.add_header("x-ms-date", date_str)
        req.add_header("x-ms-version", "2020-04-08")
        req.add_header("x-ms-blob-type", "BlockBlob")
        req.add_header("Content-Type", "text/plain")
        req.add_header("Content-Length", str(len(data)))
        req.add_header("Authorization", auth)
        with urlopen(req, timeout=5) as resp:
            resp.read()
        logger.info(f"[cursor] written: {ts}")
    except Exception as exc:
        logger.warning(f"[cursor] write failed (non-fatal): {exc}")


# ---------------------------------------------------------------------------
# Dedup — in-process set guards within a warm instance lifetime
# ---------------------------------------------------------------------------

def _already_seen(trace_id: str) -> bool:
    return trace_id in _SEEN_TRACE_IDS


def _mark_seen(trace_id: str) -> None:
    global _SEEN_TRACE_IDS
    if len(_SEEN_TRACE_IDS) >= _SEEN_MAX:
        keep = list(_SEEN_TRACE_IDS)[_SEEN_MAX // 2:]
        _SEEN_TRACE_IDS = set(keep)
        logger.info(f"[dedup] trimmed seen set to {len(_SEEN_TRACE_IDS)}")
    _SEEN_TRACE_IDS.add(trace_id)


# ---------------------------------------------------------------------------
# KQL query — only root invoke_agent spans, one per user invocation
# ---------------------------------------------------------------------------

def _query_new_invocations(since: str) -> list[dict]:
    # Filter and sort on ingestion_time() so rows that arrive late in Log Analytics
    # (due to App Insights ingestion lag) are still picked up.  TimeGenerated can be
    # several minutes behind ingestion_time(), so a row with TimeGenerated before
    # `since` would previously fall outside the window and be silently dropped.
    # The invoke_agent row carries no usage or tool data.  The `chat` row (token usage)
    # and the `execute_tool` rows (arguments / result) share its gen_ai.response.id, so
    # they are joined in here to report real tokens and tool calls instead of estimates.
    # Support both kind:prompt agents (AppGenAIContent) and kind:hosted agents (AppDependencies)
    kql = f"""
let prompt_detail = AppGenAIContent
| where ingestion_time() > ago({_POLL_WINDOW_MIN}m)
| extend d = parse_json(Attributes)
| extend rid = tostring(d['gen_ai.response.id']), dop = tostring(d['gen_ai.operation.name'])
| where isnotempty(rid);
let prompt_tools = prompt_detail
| where dop == 'execute_tool'
| summarize ToolCalls = make_list(bag_pack('name', tostring(d['gen_ai.tool.name']), 'input', ToolCallArguments, 'output', ToolCallResult)) by rid;
let prompt_usage = prompt_detail
| where dop == 'chat'
| summarize chat_in = sum(toint(d['gen_ai.usage.input_tokens'])), chat_out = sum(toint(d['gen_ai.usage.output_tokens'])) by rid;
// Workflow agents: each inner agent's GenAI content row has SpanId == the id of its
// `invoke_agent <name>` dependency, which gives the step name (Writer / Reviewer / ...).
let step_names = AppDependencies
| where ingestion_time() > ago({_POLL_WINDOW_MIN}m)
| where Name startswith 'invoke_agent ' and DependencyType == 'InProc'
| project dep_id = Id, step_name = trim(' ', substring(Name, 13));
let prompt_agents = AppGenAIContent
| where ingestion_time() > datetime('{since}')
| where ingestion_time() > ago({_POLL_WINDOW_MIN}m)
| where parse_json(Attributes)['gen_ai.operation.name'] == 'invoke_agent'
| extend attrs = parse_json(Attributes)
| extend rid = tostring(attrs['gen_ai.response.id'])
| join kind=leftouter prompt_tools on rid
| join kind=leftouter prompt_usage on rid
| join kind=leftouter step_names on $left.SpanId == $right.dep_id
| project
    TimeGenerated,
    step_name      = coalesce(step_name, ''),
    IngestTime     = ingestion_time(),
    response_id    = rid,
    TraceId,
    AgentName,
    InputMessages,
    OutputMessages,
    session_id     = tostring(coalesce(attrs['gen_ai.conversation.id'], attrs['thread.id'], attrs['conversation.id'], attrs['session.id'])),
    user_id        = tostring(coalesce(attrs['langfuse.user.id'], attrs['user.id'])),
    model_name     = tostring(coalesce(attrs['gen_ai.response.model'], attrs['gen_ai.request.model'], attrs['llm.model_name'])),
    input_tokens   = toint(coalesce(attrs['gen_ai.usage.input_tokens'], attrs['gen_ai.usage.prompt_tokens'], chat_in)),
    output_tokens  = toint(coalesce(attrs['gen_ai.usage.output_tokens'], attrs['gen_ai.usage.completion_tokens'], chat_out)),
    ToolCalls;
// Hosted agents (agentserver + opentelemetry-instrumentation-openai-v2) do not put the
// prompt / completion on the span.  With content recording enabled they are logged as
// separate AppTraces rows (logger opentelemetry.instrumentation.openai_v2) whose
// ParentId is the `chat` dependency Id: one row per input message (body {{"content": ..}}),
// then one row for the choice (body {{"finish_reason":..,"message":{{"role":..,"content":..}}}}).
// Rebuild them into the [{{role, parts:[{{type:text, content}}]}}] shape _handle_row parses.
let hosted_logs = AppTraces
| where ingestion_time() > ago({_POLL_WINDOW_MIN}m)
| where tostring(parse_json(Properties)['logger_name']) == 'opentelemetry.instrumentation.openai_v2'
| where Message != 'n/a'
| extend m = parse_json(Message)
| extend is_choice = isnotnull(m['finish_reason']);
let hosted_in = hosted_logs
| where not(is_choice)
| order by TimeGenerated asc
| summarize in_list = make_list(tostring(m['content'])) by OperationId, ParentId
| project OperationId, ParentId, in_text = tostring(in_list[array_length(in_list) - 1]);
let hosted_out = hosted_logs
| where is_choice
| summarize out_text = take_any(tostring(m['message']['content'])) by OperationId, ParentId;
let hosted_content = hosted_in
| join kind=fullouter hosted_out on OperationId, ParentId
| project OperationId = coalesce(OperationId, OperationId1), ParentId = coalesce(ParentId, ParentId1), in_text, out_text;
let hosted_agents = AppDependencies
| where ingestion_time() > datetime('{since}')
| where ingestion_time() > ago({_POLL_WINDOW_MIN}m)
| where DependencyType has 'GenAI' or DependencyType == 'GenAI | openai'
| join kind=leftouter hosted_content on $left.OperationId == $right.OperationId, $left.Id == $right.ParentId
| extend props = parse_json(Properties)
// The log rows can land a few seconds after the dependency; hold the row back briefly
// so the prompt is not lost (older rows are sent regardless, e.g. content recording off).
| where isnotempty(in_text) or ingestion_time() < ago(2m)
| project
    TimeGenerated,
    IngestTime     = ingestion_time(),
    response_id    = tostring(coalesce(props['gen_ai.response.id'], props['azure.ai.agentserver.response_id'])),
    TraceId        = OperationId,
    AgentName      = tostring(coalesce(props['gen_ai.agent.name'], AppRoleName)),
    InputMessages  = tostring(coalesce(
        props['gen_ai.prompt'], props['gen_ai.input.messages'],
        iff(isnotempty(in_text), tostring(pack_array(bag_pack('role', 'user', 'parts', pack_array(bag_pack('type', 'text', 'content', in_text))))), ''))),
    OutputMessages = tostring(coalesce(
        props['gen_ai.completion'], props['gen_ai.output.messages'],
        iff(isnotempty(out_text), tostring(pack_array(bag_pack('role', 'assistant', 'parts', pack_array(bag_pack('type', 'text', 'content', out_text))))), ''))),
    session_id     = tostring(coalesce(props['gen_ai.conversation.id'], props['microsoft.session.id'], props['azure.ai.agentserver.session_id'], OperationId)),
    user_id        = tostring(coalesce(props['user.id'], props['gen_ai.user.id'])),
    model_name     = tostring(coalesce(props['gen_ai.response.model'], props['gen_ai.request.model'], Name)),
    input_tokens   = toint(coalesce(props['gen_ai.usage.input_tokens'], props['gen_ai.usage.prompt_tokens'])),
    output_tokens  = toint(coalesce(props['gen_ai.usage.output_tokens'], props['gen_ai.usage.completion_tokens'])),
    ToolCalls      = dynamic([]);
union prompt_agents, hosted_agents
| order by IngestTime asc
"""
    token = _get_la_token()
    req   = Request(
        f"https://api.loganalytics.io/v1/workspaces/{_WORKSPACE_ID}/query",
        data=json.dumps({"query": kql}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(req, timeout=30, context=ssl.create_default_context()) as resp:
            body = json.loads(resp.read())
    except HTTPError as exc:
        raise RuntimeError(f"LA query failed ({exc.code}): {exc.read().decode()[:300]}")

    tables = body.get("tables", [])
    if not tables:
        return []
    cols = [c["name"] for c in tables[0]["columns"]]
    return [dict(zip(cols, row)) for row in tables[0]["rows"]]



_AI_TOKEN_CACHE: dict = {}


def _get_ai_token() -> str:
    """Token for the Foundry project data plane (https://ai.azure.com)."""
    now = time.time()
    if _AI_TOKEN_CACHE.get("token") and now < _AI_TOKEN_CACHE.get("expires_at", 0):
        return _AI_TOKEN_CACHE["token"]
    resource = "https://ai.azure.com"
    ep, hdr = os.environ.get("IDENTITY_ENDPOINT", ""), os.environ.get("IDENTITY_HEADER", "")
    if ep and hdr:
        req = Request(f"{ep}?api-version=2019-08-01&resource={resource}")
        req.add_header("X-IDENTITY-HEADER", hdr)
        with urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read())
        token, ttl = body["access_token"], max(int(body.get("expires_in", 3600)) - 300, 60)
    else:
        import subprocess
        token = subprocess.run(["az", "account", "get-access-token", "--resource", resource,
                                "--query", "accessToken", "-o", "tsv"],
                               capture_output=True, text=True, check=True).stdout.strip()
        ttl = 3300
    _AI_TOKEN_CACHE.update(token=token, expires_at=now + ttl)
    return token


def _fetch_response_data(response_id: str) -> dict:
    """Fetch authoritative response data (input, output, usage, tool calls) from Responses API."""
    endpoint = os.environ.get("PROJECT_ENDPOINT", "").rstrip("/")
    if not (endpoint and response_id):
        return {}
    try:
        req = Request(f"{endpoint}/openai/v1/responses/{response_id}",
                      headers={"Authorization": f"Bearer {_get_ai_token()}"})
        with urlopen(req, timeout=10, context=ssl.create_default_context()) as resp:
            body = json.loads(resp.read())
            return body if isinstance(body, dict) else {}
    except Exception as exc:
        logger.warning(f"[RESPONSE] lookup failed for {response_id}: {exc}")
        return {}


def _fetch_response_usage(response_id: str) -> tuple[int, int] | None:
    """Authoritative (input, output) tokens for a Responses-API call.

    The telemetry `chat` row only covers the final model turn, so a call that ran a
    tool (code interpreter, ...) under-reports output tokens.  GET /responses/{id}
    returns the usage summed over every model turn.  Returns None when unavailable
    so the caller falls back to the telemetry numbers.
    """
    endpoint = os.environ.get("PROJECT_ENDPOINT", "").rstrip("/")
    if not (endpoint and response_id):
        return None
    try:
        req = Request(f"{endpoint}/openai/v1/responses/{response_id}",
                      headers={"Authorization": f"Bearer {_get_ai_token()}"})
        with urlopen(req, timeout=10, context=ssl.create_default_context()) as resp:
            usage = json.loads(resp.read()).get("usage") or {}
        i, o = int(usage.get("input_tokens") or 0), int(usage.get("output_tokens") or 0)
        return (i, o) if (i or o) else None
    except Exception as exc:
        logger.warning(f"[USAGE] response usage lookup failed for {response_id}: {exc}")
        return None


# ---------------------------------------------------------------------------
# Event parsing helpers (inlined from azure_trace_hook.py)
# ---------------------------------------------------------------------------

def _parse_iso_ns(s: str) -> int | None:
    if not s:
        return None
    try:
        ts = datetime.fromisoformat(s.rstrip("Z")).replace(tzinfo=timezone.utc)
        return int(ts.timestamp() * 1_000_000_000)
    except Exception:
        return None


def _extract_input(req_body: dict) -> str:
    messages = req_body.get("messages", [])
    if messages:
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, list):
                    return " ".join(
                        c.get("text", "") for c in content
                        if isinstance(c, dict) and c.get("type") == "text"
                    )
                return str(content)
    return (
        str(req_body.get("input", ""))
        or str(req_body.get("prompt", ""))
        or str(req_body.get("messages", ""))
        or ""
    )


def _extract_output(resp_body: dict) -> str:
    for item in resp_body.get("output", []):
        if isinstance(item, dict) and item.get("type") == "message":
            for c in item.get("content", []):
                if isinstance(c, dict) and c.get("type") == "output_text":
                    return c.get("text", "")
    choices = resp_body.get("choices", [])
    if choices:
        msg = choices[0].get("message", {})
        return str(msg.get("content", ""))
    return (
        str(resp_body.get("output", ""))
        or str(resp_body.get("response", ""))
        or str(resp_body.get("text", ""))
        or ""
    )


def _extract_usage(resp_body: dict) -> dict:
    usage = resp_body.get("usage", {})
    if usage:
        return {
            "inputTokens":  int(usage.get("prompt_tokens",     usage.get("input_tokens",  0)) or 0),
            "outputTokens": int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0),
            "totalTokens":  int(usage.get("total_tokens", 0) or 0),
        }
    return {}


# ---------------------------------------------------------------------------
# Row → normalised event dict for span building
# ---------------------------------------------------------------------------

def _tool_calls_from_messages(input_json: str, output_json: str) -> list[dict]:
    """Extract {name, input, output} tool calls for the CURRENT turn from message JSON."""
    def _load(s: str) -> list:
        try:
            v = json.loads(s or "[]")
            return v if isinstance(v, list) else []
        except Exception:
            return []

    in_msgs = _load(input_json)
    last_user = max((i for i, m in enumerate(in_msgs) if isinstance(m, dict) and m.get("role") == "user"), default=-1)
    current = in_msgs[last_user + 1:]

    calls: list[dict] = []
    for msg in current:
        if not isinstance(msg, dict):
            continue
        for part in msg.get("parts", []) or []:
            ptype = part.get("type")
            if msg.get("role") == "assistant" and ptype == "tool_call" and part.get("name"):
                calls.append({"name": part["name"],
                              "input": json.dumps(part.get("arguments") or {}),
                              "output": ""})
            elif ptype == "tool_call_response":
                # Pair the result with the oldest call that has no output yet.
                for c in calls:
                    if not c["output"]:
                        c["output"] = str(part.get("response") or "")
                        break

    # Tool calls the model is requesting in this turn's output (no result yet).
    for msg in _load(output_json):
        if not isinstance(msg, dict):
            continue
        for part in msg.get("parts", []) or []:
            if part.get("type") == "tool_call" and part.get("name"):
                calls.append({"name": part["name"],
                              "input": json.dumps(part.get("arguments") or {}),
                              "output": ""})
    return calls


def _row_to_event(row: dict) -> dict:
    def _user_text(messages_json: str) -> str:
        try:
            for msg in reversed(json.loads(messages_json or "[]")):
                if msg.get("role") == "user":
                    for part in msg.get("parts", []):
                        if part.get("type") == "text":
                            return part.get("content", "")
        except Exception:
            pass
        return messages_json[:300] if messages_json else ""

    def _asst_text(messages_json: str) -> str:
        try:
            for msg in json.loads(messages_json or "[]"):
                if msg.get("role") == "assistant":
                    for part in msg.get("parts", []):
                        if part.get("type") == "text":
                            return part.get("content", "")
        except Exception:
            pass
        return messages_json[:300] if messages_json else ""

    prompt   = _user_text(row.get("InputMessages", ""))
    response = _asst_text(row.get("OutputMessages", ""))

    input_tokens  = int(row.get("input_tokens")  or 0)
    output_tokens = int(row.get("output_tokens") or 0)
    resp_id = str(row.get("response_id") or "")
    if resp_id and (not prompt or not response or (input_tokens == 0 and output_tokens == 0)):
        resp_data = _fetch_response_data(resp_id)
        if resp_data:
            if not prompt:
                prompt = _extract_input(resp_data)
            if not response:
                response = _extract_output(resp_data)
            u = _extract_usage(resp_data)
            if u:
                input_tokens = u.get("inputTokens", input_tokens)
                output_tokens = u.get("outputTokens", output_tokens)
    elif resp_id:
        _api_usage = _fetch_response_usage(resp_id)
        if _api_usage:
            input_tokens, output_tokens = _api_usage
    tokens_estimated = input_tokens == 0 and output_tokens == 0

    # KQL only exposes TimeGenerated (log arrival time), not the real span start/end, so
    # the span window is anchored at push time. Anchoring on TimeGenerated made the WXO
    # session's created_at fall before the caller's invocation time (intermittent
    # "trace not found" in the test's created_after session filter).
    end_ns = int(time.time() * 1e9)

    # Estimate tokens if not available from KQL
    if tokens_estimated:
        input_tokens  = _count_tokens(prompt)
        output_tokens = _count_tokens(response)

    if not prompt:
        prompt = f"User invocation for {row.get('AgentName', 'agent')}"
    if not response:
        response = f"Response from {row.get('AgentName', 'agent')}"

    # ── Extract tool calls from the KQL row ───────────────────────────────────
    # Azure AI Foundry Log Analytics rows may carry a ToolCalls JSON column
    # (populated when the agent invoked a function/tool during the run).
    # Format: JSON array of {name, input, output} or OpenAI tool_calls shape.
    tool_calls: list = []
    raw_tc = row.get("ToolCalls") or row.get("tool_calls") or row.get("FunctionCalls") or ""
    if raw_tc:
        try:
            tc_list = json.loads(raw_tc) if isinstance(raw_tc, str) else raw_tc
            if isinstance(tc_list, list):
                for tc in tc_list:
                    if not isinstance(tc, dict):
                        continue
                    # Normalise OpenAI shape: {id, type, function: {name, arguments}}
                    fn    = tc.get("function") or {}
                    name  = fn.get("name") or tc.get("name") or tc.get("tool_name") or ""
                    inp   = fn.get("arguments") or str(tc.get("input") or tc.get("parameters") or "")
                    out   = str(tc.get("output") or tc.get("result") or "")
                    if name:
                        tool_calls.append({"name": name, "input": inp, "output": out})
        except Exception:
            pass

    # ── Fallback: client-side function tools ─────────────────────────────────
    # kind:prompt agents whose tools are client-side functions emit no `execute_tool`
    # rows, so ToolCalls is empty.  The calls are instead embedded in the message
    # JSON: a turn that *requests* a tool carries a `tool_call` part in
    # OutputMessages; the follow-up turn carries the `tool_call` (+ its
    # `tool_call_response`) in InputMessages.  Only messages after the last user
    # message are read so earlier turns of a conversation are not replayed.
    if not tool_calls:
        tool_calls = _tool_calls_from_messages(row.get("InputMessages", ""), row.get("OutputMessages", ""))

    return {
        "prompt":           prompt,
        "response":         response,
        # Prefer thread.id / conversation.id (stable across turns) over TraceId
        # (unique per invocation) so all turns of one conversation share a session.
        "session_id":       str(row.get("session_id") or "").replace("-", "") or None,
        "user_id":          str(row.get("user_id") or ""),
        "model_name":       str(row.get("model_name") or ""),
        "request_id":       "",
        "is_error":         False,
        "status_code":      200,
        "latency_ms":       1000,
        "start_ns":         end_ns - 1_000_000_000,
        "end_ns":           end_ns,
        "input_tokens":     input_tokens,
        "output_tokens":    output_tokens,
        "total_tokens":     input_tokens + output_tokens,
        "tokens_estimated": tokens_estimated,
        "error_msg":        "",
        "tool_calls":       tool_calls,
        "steps":            row.get("steps") or [],
    }


# ---------------------------------------------------------------------------
# OTLP payload builder
# ---------------------------------------------------------------------------

def _build_otlp_payload(
    tenant_id: str,
    agent_id: str,
    agent_name: str,
    agent_display_name: str,
    environment: str,
    session_id: str,
    message_id: str,
    user_id: str,
    parsed: dict,
    trace_id: str,
    input_messages: str,
    output_messages: str,
    model_name: str = "",
) -> dict:
    span_id    = secrets.token_hex(8)
    span_name  = f"invoke_agent {agent_name}"
    start_ns   = parsed["start_ns"]
    end_ns     = parsed["end_ns"]
    latency_ms = max(1, (end_ns - start_ns) // 1_000_000)
    _model     = model_name or parsed.get("model_name") or ""
    _usage_json = json.dumps({
        "input":  parsed["input_tokens"],
        "output": parsed["output_tokens"],
        "total":  parsed["total_tokens"],
    })

    def _sv(k, v): return {"key": k, "value": {"stringValue": str(v)}}
    def _iv(k, v): return {"key": k, "value": {"intValue": int(v)}}

    # Structured WXO message envelope — matches the shape emitted by wxo-server's
    # LangGraph pipeline so the Langfuse UI renders a rich input object on the trace.
    _input_envelope = json.dumps({
        "role": "user",
        "content": parsed["prompt"],
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

    # ── Root span attributes ──────────────────────────────────────────────────
    attributes = [
        _sv("agent.id",              agent_id),
        _sv("agent.name",            agent_name),
        _sv("agent.display_name",    agent_display_name),
        _sv("agent.version",         "1"),
        _sv("gen_ai.operation.name", "invoke_agent"),
        _sv("gen_ai.agent.id",       agent_id),
        _sv("gen_ai.agent.name",     agent_name),
        _sv("thread.id",             session_id),
        _sv("conversation.id",       session_id),
        _sv("session.id",            session_id),
        _sv("langfuse.session.id",   session_id),
        _sv("langfuse.user.id",      user_id),
        _sv("message.id",            message_id),
        _sv("environment.name",      environment),
        _sv("environment.id",        environment),
        _sv("workspace.id",          "00000000-0000-0000-0000-000000000001"),
        _sv("instance.id",           tenant_id),
        _sv("tenant.id",             tenant_id),
        # WXO facet attributes — tag generation and routing
        _sv("wxo.facet.tenant_id",    tenant_id),
        _sv("wxo.facet.workspace_id", "00000000-0000-0000-0000-000000000001"),
        _sv("wxo.facet.agent_id",     agent_id),
        _sv("wxo.facet.workflow_id",  span_name),
        _sv("wxo.channel.name",       "external_agent"),
        _sv("wxo.channel.type",       "text"),
        # Langfuse trace-level markers
        _sv("langfuse.internal.as_root", "true"),
        _sv("langfuse.trace.name",    span_name),
        _sv("langfuse.tags",          json.dumps([
            f"agent_id:{agent_id}",
            f"environment:{environment}",
            f"tenant_id:{tenant_id}",
            "workspace_id:00000000-0000-0000-0000-000000000001",
        ])),
        _sv("is.root",                "true"),
        _sv("global_transaction_id",  trace_id),
        # Primary I/O — server enrichment reads these to produce langfuse.observation.*
        _sv("gen_ai.input.messages",  input_messages),
        _sv("gen_ai.output.messages", output_messages),
        # Structured WXO message envelope — gives the Langfuse trace a rich input object
        _sv("gen_ai.message.input",   _input_envelope),
        # Flat-string copies for ClickHouse / backwards-compat
        _sv("input.value",  parsed["prompt"]),
        _sv("output.value", parsed["response"]),
        _sv("gen_ai.task.input",  parsed["prompt"]),
        _sv("gen_ai.task.output", parsed["response"]),
        _sv("input",               parsed["prompt"]),
        _sv("output",              parsed["response"]),
        _sv("llm.model_name",        _model),
        _sv("model",                 _model),
        _sv("gen_ai.response.model", _model),
        _sv("gen_ai.request.model",  _model),
        _sv("llm.system",          "azure_ai_foundry"),
        _sv("gen_ai.system",       "azure_ai_foundry"),
        _sv("framework",           "azure_ai_foundry"),
        _sv("agent.execution.status", "error"  if parsed["is_error"] else "success"),
        _sv("agent.business_outcome", "failed" if parsed["is_error"] else "success"),
        _sv("tokens.estimated",       str(parsed["tokens_estimated"]).lower()),
        # AGENT kind — root is the orchestration wrapper, matching harness span tree
        _sv("openinference.span.kind", "AGENT"),
        _iv("latency_ms",                     latency_ms),
        _iv("llm.usage.prompt_tokens",        parsed["input_tokens"]),
        _iv("llm.usage.completion_tokens",    parsed["output_tokens"]),
        _iv("llm.usage.total_tokens",         parsed["total_tokens"]),
        _iv("gen_ai.usage.prompt_tokens",     parsed["input_tokens"]),
        _iv("gen_ai.usage.completion_tokens", parsed["output_tokens"]),
        _iv("gen_ai.usage.input_tokens",      parsed["input_tokens"]),
        _iv("gen_ai.usage.output_tokens",     parsed["output_tokens"]),
        _iv("llm.token_count.prompt",         parsed["input_tokens"]),
        _iv("llm.token_count.completion",     parsed["output_tokens"]),
        _iv("llm.token_count.total",          parsed["total_tokens"]),
        _sv("provided_usage_details",              _usage_json),
        _sv("langfuse.observation.usage_details",  _usage_json),
    ]

    if parsed.get("session_id"):
        attributes.append(_sv("azure.session.id", parsed["session_id"]))
    if parsed.get("request_id"):
        attributes.append(_sv("azure.request.id", parsed["request_id"]))
    if parsed["is_error"] and parsed["error_msg"]:
        attributes.append(_sv("error.type",    "AzureAgentError"))
        attributes.append(_sv("error.message", parsed["error_msg"][:4000]))

    # ── Root span ─────────────────────────────────────────────────────────────
    root_span = {
        "traceId":            trace_id,
        "spanId":             span_id,
        "name":               span_name,
        "kind":               2,
        "startTimeUnixNano":  start_ns,
        "endTimeUnixNano":    end_ns,
        "status":             {"code": 2 if parsed["is_error"] else 0},
        "attributes":         attributes,
    }

    # ── Synthetic child tree: call_llm → generate_content <model> ────────────
    # Matches harness hierarchy: invoke_agent AGENT → call_llm LLM →
    # generate_content <model> LLM.
    _llm_id    = secrets.token_hex(8)
    _gen_id    = secrets.token_hex(8)
    _llm_start = start_ns + max(1_000_000, (end_ns - start_ns) // 20)
    _llm_end   = end_ns   - max(1_000_000, (end_ns - start_ns) // 20)
    _gen_start = _llm_start + max(500_000, (_llm_end - _llm_start) // 20)
    _gen_end   = _llm_end   - max(500_000, (_llm_end - _llm_start) // 20)
    _llm_attrs = [
        _sv("openinference.span.kind",         "CHAIN"),
        _sv("gen_ai.system",                   "azure_ai_foundry"),
        _sv("gen_ai.request.model",            _model),
        _sv("llm.model_name",                  _model),
        _sv("gen_ai.input.messages",           input_messages),
        _sv("gen_ai.output.messages",          output_messages),
        _iv("gen_ai.usage.input_tokens",       parsed["input_tokens"]),
        _iv("gen_ai.usage.output_tokens",      parsed["output_tokens"]),
        _iv("gen_ai.usage.prompt_tokens",      parsed["input_tokens"]),
        _iv("gen_ai.usage.completion_tokens",  parsed["output_tokens"]),
        _iv("llm.usage.prompt_tokens",         parsed["input_tokens"]),
        _iv("llm.usage.completion_tokens",     parsed["output_tokens"]),
        _iv("llm.token_count.prompt",          parsed["input_tokens"]),
        _iv("llm.token_count.completion",      parsed["output_tokens"]),
        _iv("llm.token_count.total",           parsed["total_tokens"]),
        _sv("provided_usage_details",              _usage_json),
        _sv("langfuse.observation.usage_details",  _usage_json),
    ]
    _gen_attrs = [
        _sv("openinference.span.kind",         "LLM"),
        _sv("gen_ai.system",                   "azure_ai_foundry"),
        _sv("gen_ai.request.model",            _model),
        _sv("llm.model_name",                  _model),
        _sv("gen_ai.prompt",                   parsed["prompt"][:2000]),
        _sv("gen_ai.completion",               parsed["response"][:2000]),
        _sv("gen_ai.input.messages",           input_messages),
        _sv("gen_ai.output.messages",          output_messages),
        _iv("gen_ai.usage.input_tokens",       parsed["input_tokens"]),
        _iv("gen_ai.usage.output_tokens",      parsed["output_tokens"]),
        _iv("gen_ai.usage.prompt_tokens",      parsed["input_tokens"]),
        _iv("gen_ai.usage.completion_tokens",  parsed["output_tokens"]),
        _sv("provided_usage_details",          _usage_json),
    ]

    _gen_window  = max(1, _gen_end - _gen_start)
    _tool_calls  = parsed.get("tool_calls") or []
    _tool_count  = len(_tool_calls)

    # ── TOOL spans — parented to generate_content ────────────────────────────
    # kind:prompt agents rarely expose tool detail in KQL today, so this list
    # is usually empty; when present, tool spans replace the retrieval stub.
    _tool_spans = [
        {
            "traceId":            trace_id,
            "spanId":             secrets.token_hex(8),
            "parentSpanId":       _gen_id,
            "name":               str(_tc.get("name", f"tool_{_i}")), "kind": 3,
            "startTimeUnixNano":  max(_gen_start, min(
                _tc.get("start_ns") or (_gen_start + (_gen_window // (_tool_count + 1)) * (_i + 1)),
                _gen_end - 1_000_000)),
            "endTimeUnixNano":    min(_gen_end, max(
                (_tc.get("start_ns") or _gen_start) + max(1_000_000, _gen_window // 4),
                _tc.get("end_ns") or _gen_end)),
            "status":             {"code": 2 if _tc.get("is_error") else 0},
            "attributes":         [
                _sv("openinference.span.kind", "TOOL"),
                _sv("tool.name",               str(_tc.get("name", f"tool_{_i}"))),
                _sv("gen_ai.tool.name",        str(_tc.get("name", f"tool_{_i}"))),
                *([_sv("tool.parameters", str(_tc["input"])[:2000]),
                   _sv("input.value",     str(_tc["input"])[:2000])] if _tc.get("input") else []),
                # NB: no output.value on TOOL spans — WXO drops the span.
                *([_sv("tool.output",  str(_tc["output"])[:2000])] if _tc.get("output") else []),
            ],
        }
        for _i, _tc in enumerate(_tool_calls)
    ]

    # ── RETRIEVER span — only when no real tool spans are present ────────────
    # Emitted as a synthetic 4th-level placeholder for RAG / prompt agents that
    # don't call tools.  Suppressed when actual tool spans already fill that slot
    # so that a fake "retrieval" node never appears alongside real tool spans.
    _rv_spans = []
    if not _tool_spans:
        _rv_start = _gen_start + max(500_000, _gen_window // 4)
        _rv_end   = min(_rv_start + max(1_000_000, _gen_window // 2), _gen_end)
        _rv_spans = [{
            "traceId":            trace_id,
            "spanId":             secrets.token_hex(8),
            "parentSpanId":       _gen_id,
            "name":               "retrieval", "kind": 3,
            "startTimeUnixNano":  _rv_start, "endTimeUnixNano": _rv_end,
            "status":             {"code": 0},
            "attributes":         [
                _sv("openinference.span.kind", "RETRIEVER"),
                _sv("retrieval.source",        "knowledge_base"),
            ],
        }]

    # ── Workflow steps — one AGENT span per inner agent, under the root ───────
    # A workflow trace is collapsed into a single push; each inner agent (Writer,
    # Reviewer, ...) becomes a child span laid out sequentially in the span window.
    _steps = parsed.get("steps") or []
    _step_spans = []
    if _steps:
        _slot = max(1, (end_ns - start_ns) // (len(_steps) + 1))
        for _i, _st in enumerate(_steps):
            _s_start = start_ns + _slot * _i + _slot // 4
            _s_end   = start_ns + _slot * (_i + 1)
            _s_usage = json.dumps({
                "input":  _st["input_tokens"], "output": _st["output_tokens"],
                "total":  _st["input_tokens"] + _st["output_tokens"],
            })
            _step_spans.append({
                "traceId":            trace_id,
                "spanId":             secrets.token_hex(8),
                "parentSpanId":       span_id,
                "name":               f"invoke_agent {_st['name']}", "kind": 3,
                "startTimeUnixNano":  _s_start, "endTimeUnixNano": max(_s_end, _s_start + 1_000_000),
                "status":             {"code": 0},
                "attributes":         [
                    _sv("openinference.span.kind", "AGENT"),
                    _sv("gen_ai.operation.name",   "invoke_agent"),
                    _sv("gen_ai.agent.name",       _st["name"]),
                    _sv("gen_ai.system",           "azure_ai_foundry"),
                    _sv("gen_ai.request.model",    _st["model"] or _model),
                    _sv("llm.model_name",          _st["model"] or _model),
                    _sv("input.value",             _st["input"][:2000]),
                    _sv("output.value",            _st["output"][:2000]),
                    _sv("gen_ai.prompt",           _st["input"][:2000]),
                    _sv("gen_ai.completion",       _st["output"][:2000]),
                    _iv("gen_ai.usage.input_tokens",  _st["input_tokens"]),
                    _iv("gen_ai.usage.output_tokens", _st["output_tokens"]),
                    _iv("llm.token_count.prompt",     _st["input_tokens"]),
                    _iv("llm.token_count.completion", _st["output_tokens"]),
                    _sv("provided_usage_details",             _s_usage),
                    _sv("langfuse.observation.usage_details", _s_usage),
                ],
            })

    spans = [
        root_span,
        {
            "traceId":            trace_id, "spanId": _llm_id,
            "parentSpanId":       span_id,
            "name":               "call_llm", "kind": 3,
            "startTimeUnixNano":  _llm_start, "endTimeUnixNano": _llm_end,
            "status":             {"code": 2 if parsed["is_error"] else 0},
            "attributes":         _llm_attrs,
        },
        {
            "traceId":            trace_id, "spanId": _gen_id,
            "parentSpanId":       _llm_id,
            "name":               ("generate_content " + _model).strip() if _model else "generate_content", "kind": 3,
            "startTimeUnixNano":  _gen_start, "endTimeUnixNano": _gen_end,
            "status":             {"code": 2 if parsed["is_error"] else 0},
            "attributes":         _gen_attrs,
        },
        *_tool_spans,
        *_rv_spans,
        *_step_spans,
    ]

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
                _sv("agent.display_name",        agent_display_name),
                _sv("gen_ai.agent.id",           agent_id),
                _sv("gen_ai.agent.name",         agent_name),
                _sv("environment.name",          environment),
                _sv("deployment.environment",    environment),
            ]},
            "scopeSpans": [{
                "scope": {"name": "wxo-universal-forwarder", "version": "2.0.0"},
                "spans": spans,
            }]
        }]
    }


# ---------------------------------------------------------------------------
# Multi-agent mapping — WXO_AGENT_MAP
# ---------------------------------------------------------------------------

def _get_agent_mapping() -> dict[str, dict]:
    """Parse WXO_AGENT_MAP JSON.

    Supported formats (all normalised to the full dict form internally):

      Simple (single-tenant — agent_id only):
        {"FoundryAgentName": "wxo-uuid"}

      Extended (single-tenant — agent_id + display_name):
        {"FoundryAgentName": {"agent_id": "uuid", "display_name": "name"}}

      Multi-tenant (per-agent tenant routing):
        {"FoundryAgentName": {
            "agent_id":        "uuid",
            "display_name":    "optional label",
            "tenant_id":       "tenant_id_for_this_agent",
            "otel_export_url": "https://api…/inject/traces",
            "api_key":         "optional — falls back to WXO_API_KEY env var",
            "token_url":       "optional — falls back to WXO_TOKEN_URL env var",
            "environment":     "draft"
        }}
    """
    # App setting first (cached per process), then the shared blob, which is read fresh on
    # every call and wins for any agent name it contains. Entries only in the app setting
    # (e.g. hosted agents) are kept.
    data: dict = {}
    raw = _get_config("WXO_AGENT_MAP")
    if raw:
        try:
            data.update(json.loads(raw))
        except Exception as exc:
            logger.warning(f"[mapping] Failed to parse WXO_AGENT_MAP: {exc}")
    blob_map = _read_agent_map_blob()
    if blob_map:
        data.update(blob_map)

    mapping = {}
    for k, v in data.items():
        if isinstance(v, dict):
            mapping[k] = v
        else:
            mapping[k] = {"agent_id": str(v), "display_name": k}
    return mapping


# ---------------------------------------------------------------------------
# Push one row to WXO
# ---------------------------------------------------------------------------

def _handle_row(row: dict) -> dict:
    # Global defaults — used when the agent map does not override them
    cpd_mode            = _deployment_mode() == "cpd"
    default_export_url  = _cpd_export_url() if cpd_mode else _get_config("WXO_OTEL_EXPORT_URL")
    default_tenant_id   = "" if cpd_mode else (_extract_tenant_id(default_export_url) or _get_config("WXO_TENANT_ID"))
    default_environment = (_get_config("WXO_ENVIRONMENT_NAME") or "draft").strip()

    # AgentName comes directly from the KQL result row
    agent_name = row.get("AgentName", "azure_ai_agent")

    # Resolve Foundry agent name → WXO identity via WXO_AGENT_MAP, else fallback
    mapping = _get_agent_mapping()
    if agent_name in mapping:
        cfg                = mapping[agent_name]
        agent_id           = cfg.get("agent_id", agent_name)
        agent_display_name = cfg.get("display_name", agent_name)
        # Per-agent tenant routing — falls back to global defaults
        export_url         = cfg.get("otel_export_url") or default_export_url
        tenant_id          = cfg.get("tenant_id")       or _extract_tenant_id(export_url) or default_tenant_id
        api_key            = cfg.get("api_key",   "")
        token_url          = cfg.get("token_url", "")
        environment        = cfg.get("environment", default_environment)
    else:
        fallback_id        = _get_config("WXO_AGENT_ID")
        agent_id           = fallback_id if fallback_id else agent_name
        agent_display_name = _get_config("WXO_AGENT_DISPLAY_NAME") or agent_name
        export_url         = default_export_url
        tenant_id          = _extract_tenant_id(export_url) or default_tenant_id
        api_key            = ""
        token_url          = ""
        environment        = default_environment

    if cpd_mode:
        tenant_id = ""      # CPD has no tenant header
    if (not tenant_id and not cpd_mode) or not agent_id:
        logger.warning("[HOOK] WXO_TENANT_ID / WXO_AGENT_ID not set — skipping")
        return {"statusCode": 200, "message": "WXO config missing — skipped"}

    parsed     = _row_to_event(row)
    # Use the stable thread/conversation ID so all turns in one conversation
    # share the same session in WXO. Only fall back to a new UUID when Azure
    # does not emit any thread.id / conversation.id attribute.
    session_id = parsed["session_id"] or str(uuid.uuid4()).replace("-", "")
    message_id = str(uuid.uuid4())
    user_id    = parsed["user_id"] or f"usr_{uuid.uuid4().hex[:12]}"
    trace_id   = uuid.uuid4().hex

    logger.info(
        f"[PARSED] agent={agent_name!r} tenant={tenant_id!r} "
        f"model={(parsed.get('model_name') or '')!r} "
        f"session={session_id!r} "
        f"input={len(parsed['prompt'])}chars "
        f"output={len(parsed['response'])}chars "
        f"tokens={parsed['input_tokens']}/{parsed['output_tokens']} "
        f"estimated={parsed['tokens_estimated']} "
        f"latency={parsed['latency_ms']}ms"
    )

    # Per-agent token — uses per-agent api_key if present, else global WXO_API_KEY
    bearer_token = _get_bearer_token(api_key=api_key, token_url=token_url)
    # WXO UI expects input/output messages as JSON arrays of role-content objects
    input_messages  = json.dumps([{"role": "user",      "content": parsed["prompt"]}])
    output_messages = json.dumps([{"role": "assistant", "content": parsed["response"]}])
    otlp_payload = _build_otlp_payload(
        tenant_id, agent_id, agent_name, agent_display_name,
        environment, session_id, message_id, user_id,
        parsed, trace_id,
        input_messages,
        output_messages,
        model_name=parsed.get("model_name", ""),
    )
    job_id = _post_to_wxo(otlp_payload, bearer_token, agent_id, tenant_id, export_url=export_url)

    # Extract eval scores from parsed attributes and post to WXO scores endpoint
    _eval_scores: list[dict] = []
    for _k, _v in (parsed.items() if isinstance(parsed, dict) else {}.items()):
        if isinstance(_k, str) and _k.startswith(("eval.", "score.", "langfuse.score.")):
            try:
                _eval_scores.append({"name": _k, "value": float(_v)})
            except (TypeError, ValueError):
                pass
    if _eval_scores:
        _post_scores_to_wxo(
            _eval_scores, bearer_token, agent_id, agent_name,
            trace_id, tenant_id, export_url,
        )

    logger.info(f"=== Done | trace_id={trace_id} | job_id={job_id} ===")
    return {"statusCode": 200, "trace_id": trace_id, "job_id": job_id, "spans": 1}


# ---------------------------------------------------------------------------
# Azure Function — Timer trigger every 15 seconds
# ---------------------------------------------------------------------------

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


def _last_text(messages_json: str, role: str) -> str:
    """Text of the last `role` message in a [{role, parts:[{type:text, content}]}] JSON string."""
    try:
        for msg in reversed(json.loads(messages_json or "[]")):
            if msg.get("role") == role:
                for part in msg.get("parts", []):
                    if part.get("type") == "text":
                        return str(part.get("content", ""))
    except Exception:
        pass
    return ""



def _collapse_by_trace(rows: list[dict]) -> list[dict]:
    """One row per TraceId.

    A workflow agent emits several `invoke_agent` rows per trace: one per inner agent
    (these carry the conversation id) plus platform-level rows with no conversation id.
    Pushing each separately created one WXO session per row, most under a random session id.
    Keep the conversation-bearing rows, take the first row's input (the user's prompt) and
    the last row's output (the workflow's final answer), and sum tokens across them.
    Single-row traces (prompt / hosted agents) pass through unchanged.
    """
    groups: dict[str, list[dict]] = {}
    order: list[str] = []
    for r in rows:
        key = r.get("TraceId") or f"_row{len(order)}"
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(r)

    out: list[dict] = []
    for key in order:
        grp = groups[key]
        if len(grp) == 1:
            out.append(grp[0])
            continue
        # Prefer conversation-bearing rows; with none, the platform rows (which carry a
        # response_id) duplicate the inner-agent rows, so drop them to avoid double counting.
        with_conv = ([r for r in grp if r.get("session_id")]
                     or [r for r in grp if not r.get("response_id")]
                     or grp)
        with_conv.sort(key=lambda r: str(r.get("TimeGenerated") or ""))
        first, last = with_conv[0], with_conv[-1]
        merged = dict(first)
        merged["OutputMessages"]  = last.get("OutputMessages", "")
        merged["input_tokens"]    = sum(int(r.get("input_tokens") or 0) for r in with_conv)
        merged["output_tokens"]   = sum(int(r.get("output_tokens") or 0) for r in with_conv)
        merged["IngestTime"]      = max(str(r.get("IngestTime") or "") for r in grp) or first.get("IngestTime")
        tools: list = []
        for r in with_conv:
            tc = r.get("ToolCalls")
            if isinstance(tc, list):
                tools.extend(tc)
        merged["ToolCalls"] = tools or first.get("ToolCalls")
        if len(with_conv) > 1:
            merged["steps"] = [{
                "name":          r.get("step_name") or r.get("AgentName") or f"step_{i + 1}",
                "input":         _last_text(r.get("InputMessages", ""), "user"),
                "output":        _last_text(r.get("OutputMessages", ""), "assistant"),
                "model":         r.get("model_name") or "",
                "input_tokens":  int(r.get("input_tokens") or 0),
                "output_tokens": int(r.get("output_tokens") or 0),
            } for i, r in enumerate(with_conv)]
        logger.info(f"[poll] collapsed {len(grp)} rows -> 1 for trace={key} session={merged.get('session_id')}")
        out.append(merged)
    return out


@app.timer_trigger(
    schedule="*/15 * * * * *",
    arg_name="timer",
    run_on_startup=True,
    use_monitor=False,
)
def poll_appinsights(timer: func.TimerRequest) -> None:
    logger.info(f"[poll] timer fired | past_due={timer.past_due} | seen={len(_SEEN_TRACE_IDS)}")

    since = _read_cursor()

    try:
        rows = _query_new_invocations(since)
    except Exception as exc:
        logger.error(f"[poll] query failed: {exc}")
        return

    new_rows = _collapse_by_trace([r for r in rows if not _already_seen(r.get("TraceId", ""))])
    logger.info(f"[poll] {len(rows)} in window, {len(new_rows)} unseen")

    if not new_rows:
        return

    pushed = 0
    latest_ts = since
    for row in new_rows:
        trace_id = row.get("TraceId", "")
        az_name  = row.get("AgentName", "")
        try:
            result = _handle_row(row)
            _mark_seen(trace_id)
            # Advance cursor on IngestTime so late-arriving rows are not skipped
            latest_ts = row.get("IngestTime") or row.get("TimeGenerated") or latest_ts
            pushed += 1
            logger.info(f"[poll] ✓ agent={az_name} trace={result.get('trace_id')} job={result.get('job_id')}")
        except Exception as exc:
            logger.error(f"[poll] row failed (agent={az_name} trace={trace_id}): {exc}")

    logger.info(f"[poll] pushed {pushed}/{len(new_rows)}")
    if latest_ts != since:
        _write_cursor(latest_ts)


@app.route(route="health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    cursor = _read_cursor()
    # Foundry agent name -> WXO agent_id for EVERY entry currently loaded by this
    # process. Only the agent_id is exposed (never per-agent api_key / token_url).
    agent_map = {name: cfg.get("agent_id") for name, cfg in _get_agent_mapping().items()}
    return func.HttpResponse(
        json.dumps({
            "status":      "ok",
            "workspace":   _WORKSPACE_ID,
            "agent_map":   agent_map,
            "poll_window": f"last {_POLL_WINDOW_MIN} min",
            "dedup_seen":  len(_SEEN_TRACE_IDS),
            "last_cursor": cursor,
            "schedule":    "every 15s",
        }),
        mimetype="application/json",
    )

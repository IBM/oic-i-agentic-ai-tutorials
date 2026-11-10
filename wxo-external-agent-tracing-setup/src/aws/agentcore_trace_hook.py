"""
agentcore_trace_hook.py
=======================
AWS Lambda — receives traces from Bedrock AgentCore agents and forwards
them to WXO Agent Analytics as a single synthetic OTLP span.

Two inbound paths
-----------------
A) OTLP push  (Harness / Flow A)
   The ADOT SDK pre-installed in Harness managed images pushes
   OTLP/HTTP protobuf to the API Gateway endpoint after every
   invocation.  We decode the spans, extract prompt + response from
   the gen_ai.user.message / gen_ai.choice span events, build a
   single WXO-compatible synthetic span, and POST it to WXO.

B) Direct observability callback  (custom runtime / Flow B hook)
   AgentCore calls this Lambda directly via the Observability config
   in the console, supplying a flat JSON event with "input", "output",
   "usage", "startTime", "endTime", "agentRuntimeArn".  We parse
   that directly — no protobuf needed.

Deployment mode — WXO_DEPLOYMENT_MODE (Lambda env var, default "cloud")
------------------------------------------------------------------------
  cloud  IBM Cloud SaaS.  API key → IBM IAM token; WXO_TENANT_ID required;
         export URL = WXO_OTEL_EXPORT_URL (env or per-runtime SSM).
         Credentials: see "Multi-tenant split" below.
  cpd    Cloud Pak for Data (on-prem).  username/password →
         POST <CPD_HOST_URL>/icp4d-api/v1/authorize (token cached 12 h);
         no tenant id; TLS verification skipped unless CPD_VERIFY_TLS=true.
         Export URL = WXO_OTEL_EXPORT_URL (env or per-runtime SSM) if set, else
         <CPD_HOST_URL>/<CPD_NAMESPACE>/instances/<CPD_INSTANCE_ID>/v1/agentops-v3/traces.
         Each CPD value is read from the Lambda env var, falling back to SSM:
           CPD_HOST_URL      /wxo-agent/cpd/host_url
           CPD_USERNAME      /wxo-agent/cpd/username
           CPD_PASSWORD      /wxo-agent/cpd/password
           CPD_INSTANCE_ID   /wxo-agent/cpd/instance_id
           CPD_NAMESPACE     /wxo-agent/cpd/namespace

Credentials — env vars vs SSM (cloud mode)
------------------------------------------
Multi-tenant split:

  Per-agent env vars (injected by flow_runtime.sh / flow_harness.sh):
    WXO_TENANT_ID         WXO tenant identifier   ← per agent, stamped by wiring script
    WXO_OTEL_EXPORT_URL   WXO OTLP/HTTP endpoint  ← per agent, stamped by wiring script

  SSM Parameter Store (keyed per tenant — run ssm_params.sh once per tenant):
    /wxo-agent/tenants/<tenant_id>/api_key    WXO API key for this tenant
    /wxo-agent/tenants/<tenant_id>/token_url  IBM IAM endpoint for this tenant

  Legacy SSM fallback (single-tenant; used when no per-tenant entry exists):
    /wxo-agent/API_KEY
    /wxo-agent/TOKEN_URL

  The Lambda reads WXO_TENANT_ID from os.environ, then looks up
  /wxo-agent/tenants/<WXO_TENANT_ID>/api_key in SSM.
  This means every tenant gets its own API key — full isolation.

Per-agent identity (resolved in priority order)
-----------------------------------------------
  1. wxo.* resource attrs baked into OTEL_RESOURCE_ATTRIBUTES by
     wire_agent.sh (no SSM lookup — Lambda fully stateless per agent)
  2. SSM /wxo-agent/agents/<runtime-id>/<key>  (written by wire_agent.sh
     as fallback for spans emitted before the env var was set)
  3. Name derived from agentRuntimeArn
"""

import base64
import json
import logging
import os
import re
import ssl
import time
import uuid
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Shared helpers — try repo path (dev/CI), fall back to inline copy
# ---------------------------------------------------------------------------
_wxo_span = None
try:
    import sys as _sys, os as _os
    _repo_root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    if _repo_root not in _sys.path:
        _sys.path.insert(0, _repo_root)
    import shared.wxo_span as _wxo_span   # type: ignore[import]
except Exception:
    pass

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
# AWS SSM — per-tenant + legacy flat credentials, cached across warm invocations.
# ---------------------------------------------------------------------------

_ssm = boto3.client("ssm", region_name=os.environ.get("AWS_REGION", "us-east-1"))
SSM_PREFIX = os.environ.get("SSM_PREFIX", "/wxo-agent")
_ssm_cache: dict[str, str] = {}

# "cpd" (on-prem Cloud Pak for Data) or "cloud" (IBM Cloud SaaS, default)
_DEPLOYMENT_MODE = "cpd" if os.environ.get("WXO_DEPLOYMENT_MODE", "cloud").strip().lower() == "cpd" else "cloud"

# ---------------------------------------------------------------------------
# Per-turn gap-based buffer
# ---------------------------------------------------------------------------
# The Strands/AgentCore harness flushes ADOT spans after EVERY LLM step within
# a single user turn — including intermediate tool-decision steps AND partial
# text responses.  All pushes from the same harness container share the same
# service.instance.id across ALL prompts in a session.
#
# Observed timing (from logs):
#   • Steps within ONE turn arrive ~5s apart
#   • Gap between turns (next user prompt) is typically >10s
#
# Strategy: always buffer when instance_id is present; ship on gap.
#   1. Every push (toolUse OR text response) is stored in
#      _pending_traces[instance_id], REPLACING any prior entry.
#      Tool calls are accumulated across replacements.
#   2. On each push we sweep the buffer for entries whose last_updated is
#      older than _INTER_TURN_GAP_S seconds — those belong to a completed
#      turn (the inter-push gap just exceeded the between-turn threshold)
#      and are shipped immediately.
#   3. The first push for a new instance_id is always buffered (never
#      shipped immediately) so that later steps in the same turn can
#      replace it with the final, complete answer.
#
# _INTER_TURN_GAP_S = 10s: safely above the ~5s inter-step gap and below
# the typical between-turn gap (>10s).  Means each trace ships ~10s after
# the agent sends its final response — acceptable for analytics.
#
# Structure:  _pending_traces[instance_id] = {args, tool_calls, last_updated}
# Cap at _PENDING_MAX_ENTRIES — evict+ship oldest on overflow.
_pending_traces: dict[str, dict] = {}
_PENDING_MAX_ENTRIES = 50
_INTER_TURN_GAP_S = 10.0   # seconds — gap that signals end of a turn

def _get_param(name: str) -> str:
    """Read a flat SSM parameter (legacy path: /wxo-agent/<name>)."""
    key = f"{SSM_PREFIX}/{name}"
    if key not in _ssm_cache:
        _ssm_cache[key] = _ssm.get_parameter(Name=key, WithDecryption=True)["Parameter"]["Value"]
        logger.info(f"[SSM] Loaded {key}")
    return _ssm_cache[key]


def _get_param_optional(name: str) -> str:
    try:
        return _get_param(name)
    except Exception:
        return ""


def _get_tenant_credentials(tenant_id: str) -> tuple[str, str]:
    """
    Return (api_key, token_url) for *tenant_id*.

    Lookup order:
      1. /wxo-agent/tenants/<tenant_id>/api_key  +  …/token_url  (per-tenant SSM)
      2. /wxo-agent/API_KEY  +  /wxo-agent/TOKEN_URL              (legacy flat SSM)

    This lets every WXO tenant have its own API key stored in SSM while
    remaining backward-compatible with single-tenant deployments that only
    have the flat keys.
    """
    # Per-tenant path
    key_path  = f"{SSM_PREFIX}/tenants/{tenant_id}/api_key"
    url_path  = f"{SSM_PREFIX}/tenants/{tenant_id}/token_url"

    if key_path not in _ssm_cache or url_path not in _ssm_cache:
        try:
            resp = _ssm.get_parameters(
                Names=[key_path, url_path],
                WithDecryption=True,
            )
            for p in resp.get("Parameters", []):
                _ssm_cache[p["Name"]] = p["Value"]
            logger.info(f"[SSM] Loaded per-tenant creds for tenant={tenant_id!r}")
        except Exception as exc:
            logger.warning(f"[SSM] Per-tenant SSM lookup failed for {tenant_id!r}: {exc}")

    api_key   = _ssm_cache.get(key_path,  "")
    token_url = _ssm_cache.get(url_path,  "")

    # Fallback to legacy flat keys when per-tenant entry is absent
    if not api_key:
        api_key   = _get_param_optional("API_KEY")
        token_url = _get_param_optional("TOKEN_URL") or token_url
        if api_key:
            logger.info(f"[SSM] Using legacy flat API_KEY for tenant={tenant_id!r}")

    return api_key, token_url


def _get_cpd_config() -> dict:
    """
    CPD connection values: env var first, then SSM /wxo-agent/cpd/<name>.
    Returns host_url, username, password, instance_id, namespace ("" when unset).
    """
    def _v(env_name: str, ssm_name: str) -> str:
        return (os.environ.get(env_name, "") or _get_param_optional(ssm_name)).strip()
    return {
        "host_url":    _v("CPD_HOST_URL",    "cpd/host_url"),
        "username":    _v("CPD_USERNAME",    "cpd/username"),
        "password":    os.environ.get("CPD_PASSWORD", "") or _get_param_optional("cpd/password"),
        "instance_id": _v("CPD_INSTANCE_ID", "cpd/instance_id"),
        "namespace":   _v("CPD_NAMESPACE",   "cpd/namespace"),
    }


def _build_cpd_export_url(cfg: dict) -> str:
    """<host>/<namespace>/instances/<instance_id>/v1/agentops-v3/traces ("" if any part is missing)."""
    if cfg["host_url"] and cfg["namespace"] and cfg["instance_id"]:
        return (f"{cfg['host_url'].rstrip('/')}/{cfg['namespace']}"
                f"/instances/{cfg['instance_id']}/v1/agentops-v3/traces")
    return ""


def _extract_tenant_id(url: str) -> str:
    if url:
        m = re.search(r'/instances/([^/?#]+)', url)
        if m:
            return m.group(1).strip()
    return ""


def _get_agent_identity(runtime_id: str) -> dict:
    """
    Load per-agent WXO identity from SSM (written by wire_agent.sh / flow_harness.sh).

    Keys stored per runtime_id:
      agent_id, agent_name, agent_display_name   — identity
      tenant_id, export_url                      — multi-tenant routing (Flow A harness)

    Returns a dict with all six keys (empty string if missing).
    """
    base = f"{SSM_PREFIX}/agents/{runtime_id}"
    result = {
        "agent_id":           "",
        "agent_name":         "",
        "agent_display_name": "",
        "tenant_id":          "",   # WXO tenant — used when Lambda has no per-agent env var
        "export_url":         "",   # WXO OTLP URL — used when Lambda has no per-agent env var
        "environment":        "",   # draft | live
    }
    try:
        resp = _ssm.get_parameters(
            Names=[
                f"{base}/agent_id",
                f"{base}/agent_name",
                f"{base}/agent_display_name",
                f"{base}/tenant_id",
                f"{base}/export_url",
                f"{base}/environment",
            ],
            WithDecryption=True,
        )
        for p in resp.get("Parameters", []):
            n = p["Name"].rsplit("/", 1)[-1]
            result[n] = p["Value"]
        logger.info(f"[SSM] identity for runtime_id={runtime_id!r}: {result}")
    except Exception as exc:
        logger.warning(f"[SSM] identity lookup failed for {runtime_id!r}: {exc}")
    return result


# ---------------------------------------------------------------------------
# WXO bearer-token cache — keyed per (api_key, token_url) for tenant isolation
# ---------------------------------------------------------------------------

_TOKEN_CACHE: dict[tuple[str, str], dict] = {}
_TOKEN_LOCK            = __import__("threading").Lock()
_TOKEN_REFRESH_MARGIN  = 300
_TOKEN_DEFAULT_TTL     = 3600 - 300


def _get_bearer_token(api_key: str, token_url: str) -> str:
    """
    Exchange api_key for a bearer token.  Cache is keyed by (api_key, token_url)
    so different tenant credentials never share a token — full tenant isolation.
    """
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
        _data    = _ue({"grant_type": "urn:ibm:params:oauth:grant-type:apikey",
                        "apikey": api_key}).encode()
        _ctype   = "application/x-www-form-urlencoded"
    else:
        _data    = json.dumps({"apikey": api_key}).encode()
        _ctype   = "application/json"

    req = Request(
        token_url,
        data=_data,
        headers={"Content-Type": _ctype, "Accept": "application/json", "User-Agent": "curl/7.68.0"},
        method="POST",
    )
    with urlopen(req, timeout=30, context=ssl.create_default_context()) as resp:
        body = json.loads(resp.read())

    token = body.get("token") or body.get("access_token") or body.get("iam_token", "")
    raw_ttl = int(body.get("expires_in", _TOKEN_DEFAULT_TTL + _TOKEN_REFRESH_MARGIN) or 0)
    ttl     = max(raw_ttl - _TOKEN_REFRESH_MARGIN, 60)

    with _TOKEN_LOCK:
        _TOKEN_CACHE[cache_key] = {"token": token, "expires_at": now + ttl}
    logger.info(f"[TOKEN] Bearer token obtained (TTL={raw_ttl}s, cached for {ttl}s)")
    return token


_CPD_TOKEN_TTL = 43200   # CPD /authorize returns no expires_in; tokens last ~12 h


def _cpd_ssl_context() -> ssl.SSLContext:
    """CPD uses self-signed certs: skip verification unless CPD_VERIFY_TLS=true."""
    ctx = ssl.create_default_context()
    if os.environ.get("CPD_VERIFY_TLS", "false").strip().lower() not in ("1", "true", "yes"):
        ctx.check_hostname = False
        ctx.verify_mode    = ssl.CERT_NONE
    return ctx


def _get_cpd_bearer_token(username: str, password: str, host_url: str) -> str:
    """Obtain a CPD bearer token via POST <host>/icp4d-api/v1/authorize (cached per username+host)."""
    cache_key = (username, host_url.rstrip("/"))
    now = time.time()
    with _TOKEN_LOCK:
        entry = _TOKEN_CACHE.get(cache_key, {})
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
        with urlopen(req, timeout=30, context=_cpd_ssl_context()) as resp:
            body = json.loads(resp.read())
    except HTTPError as exc:
        raise RuntimeError(f"CPD token exchange failed ({exc.code}): {exc.read().decode()[:200]}") from exc
    except URLError as exc:
        raise RuntimeError(f"CPD token exchange failed: {exc.reason}") from exc

    token = body.get("token", "")
    if not token:
        raise RuntimeError(f"No token in CPD /authorize response: {list(body.keys())}")

    ttl = _CPD_TOKEN_TTL - _TOKEN_REFRESH_MARGIN
    with _TOKEN_LOCK:
        _TOKEN_CACHE[cache_key] = {"token": token, "expires_at": now + ttl}
    logger.info(f"[TOKEN] CPD bearer token obtained (cached for {ttl}s)")
    return token


# ---------------------------------------------------------------------------
# WXO OTLP POST
# ---------------------------------------------------------------------------

def _post_to_wxo(payload: dict, bearer_token: str, agent_id: str, tenant_id: str, export_url: str) -> str:
    """POST OTLP payload to WXO. export_url is passed explicitly (per-agent env var).
    cloud: standard TLS + x-ibm-tenant-id header.  cpd: self-signed TLS, no tenant header."""
    body = json.dumps(payload).encode()
    headers = {
        "Authorization":                f"Bearer {bearer_token}",
        "Content-Type":                 "application/json",
        "User-Agent":                   "curl/7.68.0",
        "x-ibm-agent-id":               agent_id,
        "x-langfuse-ingestion-version": "4",
    }
    if _DEPLOYMENT_MODE == "cloud" and tenant_id:
        headers["x-ibm-tenant-id"] = tenant_id
        headers["x-tenant-id"]     = tenant_id
    ctx = _cpd_ssl_context() if _DEPLOYMENT_MODE == "cpd" else ssl.create_default_context()
    req = Request(export_url, data=body, headers=headers, method="POST")
    logger.info(f"[WXO] POST {len(body)} bytes → {export_url}")
    try:
        with urlopen(req, timeout=30, context=ctx) as resp:
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
        "Authorization":                f"Bearer {bearer_token}",
        "Content-Type":                 "application/json",
        "User-Agent":                   "curl/7.68.0",
        "x-ibm-agent-id":               agent_id,
        "x-langfuse-ingestion-version": "4",
    }
    if _DEPLOYMENT_MODE == "cloud" and tenant_id:
        headers["x-ibm-tenant-id"] = tenant_id
        headers["x-tenant-id"]     = tenant_id
    ctx = _cpd_ssl_context() if _DEPLOYMENT_MODE == "cpd" else ssl.create_default_context()
    req = Request(scores_url, data=body, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=30, context=ctx) as resp:
            logger.info(f"[WXO] scores POST {resp.status} trace_id={trace_id} n={len(stamped)}")
    except Exception as exc:
        logger.warning(f"[WXO] scores POST failed: {exc}")


# ---------------------------------------------------------------------------
# Timestamp helpers
# ---------------------------------------------------------------------------

def _parse_iso_ns(s: str) -> int | None:
    """Parse ISO-8601 timestamp → nanoseconds since epoch, or None."""
    if not s:
        return None
    try:
        s = s.rstrip("Z")
        if "." in s:
            dt = datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%f")
        else:
            dt = datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")
        return int(dt.replace(tzinfo=timezone.utc).timestamp() * 1e9)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Text extraction helpers (for Variant-A callback events)
# ---------------------------------------------------------------------------

def _extract_text_field(obj) -> str | None:
    """Return plain-text value found in standard, A2A, or nested dict/list."""
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
        # A2A artifacts extraction
        if "artifacts" in obj and isinstance(obj["artifacts"], list):
            texts = []
            for art in obj["artifacts"]:
                if isinstance(art, dict) and "parts" in art and isinstance(art["parts"], list):
                    for part in art["parts"]:
                        if isinstance(part, dict) and "text" in part and isinstance(part["text"], str):
                            texts.append(part["text"])
            if texts:
                return "".join(texts)

        # A2A history / messages
        if "history" in obj and isinstance(obj["history"], list):
            for msg in reversed(obj["history"]):
                if isinstance(msg, dict) and msg.get("role") in ("assistant", "agent"):
                    for part in msg.get("parts", []):
                        if isinstance(part, dict) and "text" in part and isinstance(part["text"], str):
                            return part["text"]

        for k in ("outputText", "text", "content", "message", "response", "answer", "output", "result"):
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
                result = _extract_text_field(v)
                if result:
                    return result
    if isinstance(obj, list) and obj:
        for item in obj:
            res = _extract_text_field(item)
            if res:
                return res
    return None


def _extract_context_id(obj) -> str:
    """Extract a platform-provided conversation/session ID, never a user ID."""
    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except Exception:
            return ""
    if isinstance(obj, dict):
        for key in ("contextId", "conversationId", "sessionId", "threadId"):
            value = obj.get(key)
            if value:
                return str(value)
        for key in ("metadata", "context", "session"):
            value = obj.get(key)
            if isinstance(value, (dict, list)):
                context_id = _extract_context_id(value)
                if context_id:
                    return context_id
    if isinstance(obj, list):
        for value in obj:
            context_id = _extract_context_id(value)
            if context_id:
                return context_id
    return ""


def _extract_input_text(obj) -> str | None:
    if isinstance(obj, str):
        try:
            obj = json.loads(obj)
        except Exception:
            return obj
    if isinstance(obj, dict):
        for k in ("text", "content", "message", "input", "query", "question",
                  "prompt", "userMessage", "human_turn"):
            if k in obj:
                v = obj[k]
                if isinstance(v, str):
                    return v
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    return _extract_input_text(v[0])
        for v in obj.values():
            result = _extract_input_text(v)
            if result:
                return result
    if isinstance(obj, list) and obj:
        return _extract_input_text(obj[0])
    return None


def _clean_prompt(raw: str) -> str:
    """Strip injected harness context wrappers from a raw prompt string.

    The Bedrock AgentCore harness pre-pends a ``<user_context>…</user_context>``
    block (containing memory / system state injected by the harness runtime) to
    the actual user message before sending it to the model via the Converse API.
    The ADOT SDK captures the *entire* Converse-API input as ``gen_ai.user.message``,
    so without stripping this block the trace shows a wall of internal context
    instead of the real user question.

    Strategy:
    1. If the text is entirely ``<user_context>…</user_context>`` (nothing after),
       the actual user question was not part of the injected content — return
       ``"(user question not captured in ADOT span)"`` so the trace is at least
       readable.
    2. If there is text *after* the closing tag, that is the real user message.
    3. If the text starts with ``<user_context>`` but has no closing tag, strip
       everything up to the first ``\n\n`` and return the rest.
    4. Otherwise return the text unchanged.
    """
    if not isinstance(raw, str):
        return str(raw) if raw else ""
    stripped = raw.strip()
    if not stripped.startswith("<user_context>"):
        return stripped

    end_tag = "</user_context>"
    end_idx = stripped.find(end_tag)
    if end_idx == -1:
        # No closing tag — skip up to first double-newline
        idx = stripped.find("\n\n")
        return stripped[idx + 2:].strip() if idx != -1 else stripped
    after = stripped[end_idx + len(end_tag):].strip()
    if after:
        return after
    # Entire content was the context block — no user text captured in this span
    return "(user question not captured in ADOT span)"


# ---------------------------------------------------------------------------
# Variant-A callback event parser
# ---------------------------------------------------------------------------

def _parse_agentcore_event(event: dict) -> dict:
    """
    Extract prompt, response, tokens, latency from a direct AgentCore
    observability callback event (Path B — custom runtime / hook).

    Variant A:  { agentRuntimeArn, input, output, usage, startTime, endTime }
    Variant B:  { invocationInput, invocationOutput, sessionId, requestId }
    """
    if "invocationInput" in event:
        inv_in  = event["invocationInput"]
        inv_out = event["invocationOutput"]
        prompt   = _extract_input_text(inv_in)  or inv_in.get("text")  or json.dumps(inv_in)[:300]
        response = _extract_text_field(inv_out) or inv_out.get("text") or json.dumps(inv_out)[:300]
        session_id  = event.get("sessionId") or _extract_context_id(inv_in)
        request_id  = event.get("requestId", "")
        arn         = ""
        is_error    = bool(event.get("error"))
        status_code = event.get("statusCode", 200)
        _result_usage: dict = {}
    else:
        raw_input  = str(event.get("input",  "") or "")
        raw_output = str(event.get("output", "") or "")
        session_id  = str(
            event.get("sessionId")
            or event.get("contextId")
            or event.get("conversationId")
            or _extract_context_id(raw_input)
            or ""
        )
        request_id  = str(event.get("requestId",  "") or "")
        arn         = str(event.get("agentRuntimeArn", "") or "")
        status_code = int(event.get("statusCode", 200) or 200)
        is_error    = bool(event.get("error")) or (status_code >= 400)

        prompt   = _extract_input_text(raw_input)  or raw_input
        response = _extract_text_field(raw_output) or raw_output

        _result_usage = {}
        try:
            parsed_out = json.loads(raw_output)
            if isinstance(parsed_out, dict):
                result_block = parsed_out.get("result")
                _result_usage = (
                    result_block.get("usage") if isinstance(result_block, dict)
                    else parsed_out.get("usage") or {}
                ) or {}
        except Exception:
            pass

    start_ns = _parse_iso_ns(str(event.get("startTime", ""))) or int(time.time() * 1e9)
    end_ns   = _parse_iso_ns(str(event.get("endTime",   ""))) or (start_ns + 1_000_000_000)
    latency_ms = max(1, (end_ns - start_ns) // 1_000_000)

    _top_usage = event.get("usage") or {}
    usage = _result_usage or _top_usage or {}

    input_tokens  = int(usage.get("inputTokens",  0) or 0)
    output_tokens = int(usage.get("outputTokens", 0) or 0)
    total_tokens  = int(usage.get("totalTokens",  input_tokens + output_tokens) or 0)
    tokens_estimated = False

    if input_tokens == 0 and output_tokens == 0:
        input_tokens     = _count_tokens(prompt)
        output_tokens    = _count_tokens(response)
        total_tokens     = input_tokens + output_tokens
        tokens_estimated = True

    # ── Extract tool calls (+ sub_calls) from the callback event ─────────────
    # AgentCore callback events may carry a toolCalls / tool_calls field when
    # the agent invoked tools during the run.  Normalise recursively.
    def _norm_tc(tc: dict) -> dict | None:
        """Recursively normalise a raw tool-call dict → standard shape."""
        if not isinstance(tc, dict):
            return None
        fn   = tc.get("function") or {}
        name = (fn.get("name") or tc.get("name")
                or tc.get("toolName") or tc.get("tool_name") or "").strip()
        if not name:
            return None
        inp = (fn.get("arguments")
               or (json.dumps(tc["input"]) if isinstance(tc.get("input"), dict) else str(tc.get("input") or ""))
               or str(tc.get("parameters") or ""))
        out = str(tc.get("output") or tc.get("result") or "")
        raw_sub = tc.get("sub_calls") or tc.get("subCalls") or tc.get("sub_tools") or []
        sub_calls = []
        for s in (raw_sub if isinstance(raw_sub, list) else []):
            n = _norm_tc(s)
            if n:
                sub_calls.append(n)
        return {"name": name, "input": inp, "output": out, "sub_calls": sub_calls}

    callback_tool_calls: list = []
    raw_tc = (event.get("toolCalls") or event.get("tool_calls")
              or event.get("functionCalls") or [])
    if raw_tc:
        try:
            tc_list = json.loads(raw_tc) if isinstance(raw_tc, str) else raw_tc
            if isinstance(tc_list, list):
                for tc in tc_list:
                    n = _norm_tc(tc)
                    if n:
                        callback_tool_calls.append(n)
        except Exception:
            pass

    return {
        "prompt":           prompt,
        "response":         response,
        "session_id":       session_id,
        "user_id":          str(event.get("userId") or event.get("user_id") or ""),
        "request_id":       request_id,
        "arn":              arn,
        "is_error":         is_error,
        "status_code":      status_code,
        "latency_ms":       latency_ms,
        "start_ns":         start_ns,
        "end_ns":           end_ns,
        "input_tokens":     input_tokens,
        "output_tokens":    output_tokens,
        "total_tokens":     total_tokens,
        "tokens_estimated": tokens_estimated,
        "error_msg":        str(event.get("error", "")) if is_error else "",
        "tool_calls":       callback_tool_calls,
    }


def _is_agentcore_event(event: dict) -> bool:
    return isinstance(event, dict) and (
        "agentRuntimeArn" in event
        or ("invocationInput" in event and "invocationOutput" in event)
    )


# ---------------------------------------------------------------------------
# Pure-Python protobuf decoder  (no generated bindings required)
# ---------------------------------------------------------------------------
#
# We implement just enough of the protobuf wire format to walk an
# ExportTraceServiceRequest without needing the opentelemetry-proto pip
# package (which is NOT included in the ADOT Lambda layer).
#
# Wire types:
#   0 = varint   1 = 64-bit   2 = length-delimited   5 = 32-bit

def _proto_read_varint(data: bytes, pos: int):
    """Read a protobuf varint at pos; return (value, new_pos)."""
    result, shift = 0, 0
    while pos < len(data):
        b = data[pos]; pos += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            return result, pos
        shift += 7
    return result, pos


def _proto_skip(data: bytes, pos: int, wire_type: int) -> int:
    """Skip a field of wire_type starting at pos; return new pos."""
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
    """Read a length-delimited bytes field; return (bytes, new_pos)."""
    length, pos = _proto_read_varint(data, pos)
    return data[pos:pos + length], pos + length


def _proto_read_string(data: bytes, pos: int):
    """Read a length-delimited string field; return (str, new_pos)."""
    b, pos = _proto_read_bytes(data, pos)
    try:
        return b.decode("utf-8"), pos
    except Exception:
        return "", pos


def _decode_any_value(data: bytes) -> object:
    """Decode an OTLP AnyValue message → Python value."""
    pos = 0
    while pos < len(data):
        try:
            tag_wire, pos = _proto_read_varint(data, pos)
        except Exception:
            break
        field = tag_wire >> 3
        wire  = tag_wire & 0x07
        if wire == 2:
            chunk, pos = _proto_read_bytes(data, pos)
            if field == 1:   # string_value
                try:
                    return chunk.decode("utf-8")
                except Exception:
                    return ""
            elif field == 6: # array_value  (field 1 inside = values repeated)
                return _decode_array_value(chunk)
            elif field == 5: # kvlist_value
                return _decode_kvlist_value(chunk)
            else:
                pos = _proto_skip(data, pos - len(chunk) - 1, wire)
        elif wire == 0:
            v, pos = _proto_read_varint(data, pos)
            if field == 2:   # bool_value
                return bool(v)
            if field == 3:   # int_value
                return v
        elif wire == 1:
            import struct as _struct
            v = _struct.unpack_from("<d", data, pos)[0]
            pos += 8
            return v  # double_value
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
        wire  = tag_wire & 0x07
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
        wire  = tag_wire & 0x07
        if wire == 2 and field == 1:
            chunk, pos = _proto_read_bytes(data, pos)
            k, v = _decode_key_value(chunk)
            result[k] = v
        else:
            pos = _proto_skip(data, pos, wire)
    return result


def _decode_key_value(data: bytes) -> tuple:
    """Decode a KeyValue message → (key_str, value)."""
    key = ""
    val = ""
    pos = 0
    while pos < len(data):
        try:
            tag_wire, pos = _proto_read_varint(data, pos)
        except Exception:
            break
        field = tag_wire >> 3
        wire  = tag_wire & 0x07
        if wire == 2:
            chunk, pos = _proto_read_bytes(data, pos)
            if field == 1:
                try:
                    key = chunk.decode("utf-8")
                except Exception:
                    pass
            elif field == 2:
                val = _decode_any_value(chunk)
        else:
            pos = _proto_skip(data, pos, wire)
    return key, val


def _decode_attributes(data: bytes) -> dict:
    """Decode a repeated KeyValue attributes field → dict."""
    attrs = {}
    pos   = 0
    while pos < len(data):
        try:
            tag_wire, pos = _proto_read_varint(data, pos)
        except Exception:
            break
        field = tag_wire >> 3
        wire  = tag_wire & 0x07
        if wire == 2 and field == 6:   # field 6 = attributes in Resource/Span
            chunk, pos = _proto_read_bytes(data, pos)
            k, v = _decode_key_value(chunk)
            attrs[k] = v
        else:
            pos = _proto_skip(data, pos, wire)
    return attrs


def _decode_span_event(data: bytes) -> dict:
    """Decode a Span.Event message → {name, time_ns, attributes}.

    OTLP Span.Event field numbers:
      1=time_unix_nano(fixed64)  2=name(string)  3=attributes(repeated KeyValue)
    """
    ev = {"name": "", "time_ns": 0, "attributes": {}}
    pos = 0
    while pos < len(data):
        try:
            tag_wire, pos = _proto_read_varint(data, pos)
        except Exception:
            break
        field = tag_wire >> 3
        wire  = tag_wire & 0x07
        if wire == 1:          # fixed64
            import struct as _struct
            if pos + 8 <= len(data):
                v64 = _struct.unpack_from("<Q", data[pos:pos + 8])[0]
                pos += 8
                if field == 1:
                    ev["time_ns"] = v64
            else:
                pos += 8
        elif wire == 0:
            _, pos = _proto_read_varint(data, pos)
        elif wire == 2:
            chunk, pos = _proto_read_bytes(data, pos)
            if field == 2:
                try:
                    ev["name"] = chunk.decode("utf-8")
                except Exception:
                    pass
            elif field == 3:
                k, v = _decode_key_value(chunk)
                ev["attributes"][k] = v
        else:
            pos = _proto_skip(data, pos, wire)
    return ev


def _decode_span(data: bytes) -> dict:
    """Decode a Span message → simplified dict with name, attributes, events, timing."""
    import binascii
    sp = {
        "name":             "",
        "traceId":          "",
        "spanId":           "",
        "parentSpanId":     "",
        "startTimeUnixNano": 0,
        "endTimeUnixNano":   0,
        "attributes":       {},
        "events":           [],
    }
    pos = 0
    while pos < len(data):
        try:
            tag_wire, pos = _proto_read_varint(data, pos)
        except Exception:
            break
        field = tag_wire >> 3
        wire  = tag_wire & 0x07
        # OTLP Span field numbers (proto3 wire format):
        #   1=trace_id(bytes)  2=span_id(bytes)  4=parent_span_id(bytes)
        #   5=name(string)     6=kind(varint)
        #   7=start_time_unix_nano(fixed64)  8=end_time_unix_nano(fixed64)
        #   9=attributes(repeated KeyValue)  11=events(repeated Event)
        if wire == 1:          # fixed64 — 8 bytes little-endian
            import struct as _struct
            if pos + 8 <= len(data):
                raw8 = data[pos:pos + 8]
                v64  = _struct.unpack_from("<Q", raw8)[0]
                pos += 8
                if field == 7:
                    sp["startTimeUnixNano"] = v64
                elif field == 8:
                    sp["endTimeUnixNano"] = v64
            else:
                pos += 8  # skip truncated field
        elif wire == 0:        # varint (kind, status code, dropped counts …)
            _, pos = _proto_read_varint(data, pos)
        elif wire == 2:
            chunk, pos = _proto_read_bytes(data, pos)
            if field == 1:
                sp["traceId"] = binascii.hexlify(chunk).decode()
            elif field == 2:
                sp["spanId"] = binascii.hexlify(chunk).decode()
            elif field == 4:
                sp["parentSpanId"] = binascii.hexlify(chunk).decode()
            elif field == 5:
                try:
                    sp["name"] = chunk.decode("utf-8")
                except Exception:
                    pass
            elif field == 9:   # repeated KeyValue attributes
                k, v = _decode_key_value(chunk)
                sp["attributes"][k] = v
            elif field == 11:
                sp["events"].append(_decode_span_event(chunk))
        else:
            pos = _proto_skip(data, pos, wire)
    return sp


def _decode_scope_spans(data: bytes) -> dict:
    """Decode a ScopeSpans message → {scope_name, spans}."""
    ss = {"scope_name": "", "spans": []}
    pos = 0
    while pos < len(data):
        try:
            tag_wire, pos = _proto_read_varint(data, pos)
        except Exception:
            break
        field = tag_wire >> 3
        wire  = tag_wire & 0x07
        if wire == 2:
            chunk, pos = _proto_read_bytes(data, pos)
            if field == 1:            # scope (InstrumentationScope)
                # field 1 inside scope = name
                inner_pos = 0
                while inner_pos < len(chunk):
                    try:
                        tw, inner_pos = _proto_read_varint(chunk, inner_pos)
                    except Exception:
                        break
                    f2 = tw >> 3
                    w2 = tw & 0x07
                    if w2 == 2 and f2 == 1:
                        s, inner_pos = _proto_read_string(chunk, inner_pos)
                        ss["scope_name"] = s
                    else:
                        inner_pos = _proto_skip(chunk, inner_pos, w2)
            elif field == 2:          # spans
                ss["spans"].append(_decode_span(chunk))
        else:
            pos = _proto_skip(data, pos, wire)
    return ss


def _decode_resource_spans(data: bytes) -> dict:
    """Decode a ResourceSpans message → {resource_attrs, scope_spans}."""
    rs = {"resource_attrs": {}, "scope_spans": []}
    pos = 0
    while pos < len(data):
        try:
            tag_wire, pos = _proto_read_varint(data, pos)
        except Exception:
            break
        field = tag_wire >> 3
        wire  = tag_wire & 0x07
        if wire == 2:
            chunk, pos = _proto_read_bytes(data, pos)
            if field == 1:            # resource
                inner_pos = 0
                while inner_pos < len(chunk):
                    try:
                        tw, inner_pos = _proto_read_varint(chunk, inner_pos)
                    except Exception:
                        break
                    f2 = tw >> 3
                    w2 = tw & 0x07
                    if w2 == 2 and f2 == 1:  # repeated KeyValue
                        kv_chunk, inner_pos = _proto_read_bytes(chunk, inner_pos)
                        k, v = _decode_key_value(kv_chunk)
                        rs["resource_attrs"][k] = v
                    else:
                        inner_pos = _proto_skip(chunk, inner_pos, w2)
            elif field == 2:          # scope_spans
                rs["scope_spans"].append(_decode_scope_spans(chunk))
        else:
            pos = _proto_skip(data, pos, wire)
    return rs


def _decode_otlp_proto(data: bytes) -> list:
    """Decode an ExportTraceServiceRequest protobuf → list of resource_spans dicts.

    Returns a list of dicts, each with keys:
      resource_attrs: {key: value, ...}
      scope_spans:    [{scope_name, spans: [{name, attributes, events, ...}]}]
    """
    resource_spans = []
    pos = 0
    while pos < len(data):
        try:
            tag_wire, pos = _proto_read_varint(data, pos)
        except Exception:
            break
        field = tag_wire >> 3
        wire  = tag_wire & 0x07
        if wire == 2 and field == 1:  # field 1 = resource_spans (repeated)
            chunk, pos = _proto_read_bytes(data, pos)
            resource_spans.append(_decode_resource_spans(chunk))
        else:
            pos = _proto_skip(data, pos, wire)

    total_spans = sum(
        len(ss["spans"])
        for rs in resource_spans
        for ss in rs["scope_spans"]
    )
    span_summary = []
    for rs in resource_spans:
        for ss in rs.get("scope_spans", []):
            scope = ss.get("scope_name", "")
            for sp in ss.get("spans", []):
                span_summary.append({
                    "scope": scope,
                    "name": sp.get("name"),
                    "trace_id": sp.get("traceId"),
                    "span_id": sp.get("spanId"),
                    "parent_span_id": sp.get("parentSpanId"),
                    "attributes": sp.get("attributes", {}),
                    "events": sp.get("events", []),
                })
    logger.info(f"[PROTO] decoded {len(resource_spans)} resource groups, {total_spans} spans: {json.dumps(span_summary, default=str)}")
    return resource_spans


# ---------------------------------------------------------------------------
# String-scanner fallback (last resort when proto decode finds nothing)
# ---------------------------------------------------------------------------

def _proto_extract_strings(data: bytes) -> list[str]:
    """Walk all length-delimited fields recursively, collecting UTF-8 strings."""
    strings: list[str] = []
    pos = 0
    while pos < len(data):
        try:
            tag_wire, pos = _proto_read_varint(data, pos)
            wire_type = tag_wire & 0x07
            if wire_type == 0:
                _, pos = _proto_read_varint(data, pos)
            elif wire_type == 1:
                pos += 8
            elif wire_type == 2:
                length, pos = _proto_read_varint(data, pos)
                if pos + length > len(data):
                    break
                chunk = data[pos:pos + length]
                pos += length
                try:
                    s = chunk.decode("utf-8")
                    if s:
                        strings.append(s)
                except Exception:
                    pass
                strings.extend(_proto_extract_strings(chunk))
            elif wire_type == 5:
                pos += 4
            else:
                break
        except Exception:
            break
    return strings


# ---------------------------------------------------------------------------
# Identity extraction from OTLP (protobuf decoded or JSON)
# ---------------------------------------------------------------------------

def _extract_wxo_identity_from_resource_attrs(attrs: dict) -> dict:
    """Given a flat resource_attrs dict, pull wxo.* keys."""
    agent_id   = str(attrs.get("wxo.agent.id",           "") or "")
    agent_name = str(attrs.get("wxo.agent.name",         "") or "")
    display    = str(attrs.get("wxo.agent.display_name", "") or agent_name)
    environment = str(attrs.get("wxo.environment",       "") or "")
    # Strip leading non-identifier garbage (protobuf artefacts)
    agent_id    = re.sub(r"^[^0-9a-fA-F\-]+", "", agent_id).strip()
    agent_name  = re.sub(r"^[^A-Za-z0-9_]+",  "", agent_name).strip()
    display     = re.sub(r"^[^A-Za-z0-9_]+",  "", display).strip()
    return {
        "agent_id":           agent_id,
        "agent_name":         agent_name,
        "agent_display_name": display or agent_name,
        "environment":        environment,
        "runtime_id":         str(attrs.get("aws.agent.runtime.id", "") or ""),
    }


def _extract_wxo_identity_from_strings(data: bytes) -> dict:
    """String-scanner fallback for identity extraction from raw protobuf."""
    result = {"agent_id": "", "agent_name": "", "agent_display_name": "", "environment": "", "runtime_id": ""}
    strings = _proto_extract_strings(data)
    for i, s in enumerate(strings):
        if i + 1 >= len(strings):
            break
        val = strings[i + 1].strip()
        if s == "wxo.agent.id":
            result["agent_id"] = re.sub(r"^[^0-9a-fA-F\-]+", "", val).strip()
        elif s == "wxo.agent.name":
            result["agent_name"] = re.sub(r"^[^A-Za-z0-9_]+", "", val).strip()
        elif s == "wxo.agent.display_name":
            result["agent_display_name"] = re.sub(r"^[^A-Za-z0-9_]+", "", val).strip()
        elif s == "wxo.environment":
            result["environment"] = val
        elif s == "aws.agent.runtime.id":
            result["runtime_id"] = val
    if not result["agent_display_name"]:
        result["agent_display_name"] = result["agent_name"]
    return result


# ---------------------------------------------------------------------------
# OTLP HTTP body decode (API GW wraps binary as base64)
# ---------------------------------------------------------------------------

def _is_otlp_push(event: dict) -> bool:
    if not isinstance(event, dict):
        return False
    if "resourceSpans" in event:
        return True
    body = event.get("body")
    if isinstance(body, str):
        try:
            if "resourceSpans" in json.loads(body):
                return True
        except Exception:
            pass
    raw_path = event.get("rawPath", "")
    ct = (event.get("headers") or {}).get("content-type", "")
    # Accept any path containing /v1/traces (handles API GW double-prefix like
    # /v1/traces/v1/traces when the stage path and ADOT exporter path combine)
    if ("/v1/traces" in raw_path or "/v1/logs" in raw_path or "/v1/metrics" in raw_path) and (
        "protobuf" in ct or "proto3" in ct or "octet-stream" in ct or not ct
    ):
        return True
    return False


def _decode_otlp_body(event: dict):
    """Return (otlp_json_or_None, proto_bytes_or_None, is_protobuf)."""
    if "resourceSpans" in event:
        return event, None, False

    body   = event.get("body")
    is_b64 = event.get("isBase64Encoded", False)
    if body is None:
        return None, None, False

    if is_b64 and isinstance(body, str):
        raw = base64.b64decode(body)
    elif isinstance(body, str):
        raw = body.encode("utf-8")
    else:
        raw = bytes(body)

    ct = (event.get("headers") or {}).get("content-type", "")
    logger.info(f"[HOOK] _decode_otlp_body: body_len={len(raw)} is_b64={is_b64} content_type={ct!r}")
    if "protobuf" in ct or "proto3" in ct or "octet-stream" in ct:
        return None, raw, True

    try:
        return json.loads(raw.decode("utf-8")), None, False
    except Exception:
        pass

    return None, raw, True   # fallback: treat as protobuf


# ---------------------------------------------------------------------------
# Span name helpers
# ---------------------------------------------------------------------------

def _agent_name_from_arn(arn: str) -> str:
    if not arn:
        return "aws_agentcore_agent"
    runtime_id = arn.rstrip("/").rsplit("/", 1)[-1]
    parts = runtime_id.rsplit("-", 1)
    base  = parts[0] if len(parts) == 2 and len(parts[1]) <= 12 else runtime_id
    snake = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", base).lower()
    snake = re.sub(r"[^a-z0-9]+", "_", snake).strip("_")
    return snake or "aws_agentcore_agent"


# ---------------------------------------------------------------------------
# Synthetic WXO span builder  (shared by both paths)
# ---------------------------------------------------------------------------

def _build_wxo_payload(
    agent_id:           str,
    agent_name:         str,
    agent_display_name: str,
    environment:        str,
    tenant_id:          str,
    prompt:             str,       # clean user question — shown on root span & trace card
    response_text:      str,
    start_ns:           int,
    end_ns:             int,
    input_tokens:       int,
    output_tokens:      int,
    total_tokens:       int,
    tokens_estimated:   bool,
    runtime_id:         str = "",
    session_id:         str = "",
    user_id:            str = "",
    model_name:         str = "",
    is_error:           bool = False,
    error_msg:          str = "",
    trace_id:           str = "",
    # list of tool-call dicts: {name, input, output, start_ns, end_ns, is_error}
    tool_calls:         list | None = None,
    # full text actually sent to the model (context + question); used on LLM child
    # spans so the token counts reconcile with what is shown as input.
    # Falls back to prompt when empty.
    full_prompt:        str = "",
    # Reasoning / thinking steps — each string becomes a gen_ai.reasoning span event
    # on the root span, matching the ``steps`` shape emitted by wxo-server LangGraph.
    reasoning_steps:    list | None = None,
) -> dict:
    """Build a WXO OTLP payload with a full 4-level span tree:

        invoke_agent <agent_name>          (AGENT root)
          └── call_llm                     (LLM wrapper — carries token counts)
                └── generate_content <model>  (LLM leaf — actual model call)
                      └── <tool_name>         (TOOL, one per tool call; optional)

    This mirrors the trace hierarchy shown in the WXO Analytics trace view
    screenshot (invoke_agent → call_llm → generate_content → tool spans).
    """
    import secrets as _sec
    if not trace_id:
        trace_id = uuid.uuid4().hex
    root_span_id = _sec.token_hex(8)
    if not session_id:
        session_id = str(uuid.uuid4())
    message_id = str(uuid.uuid4())
    if not user_id:
        user_id = f"usr_{uuid.uuid4().hex[:12]}"
    span_name  = f"invoke_agent {agent_name}"
    model_name = model_name or "aws-bedrock-agentcore"

    latency_ms = max(1, (end_ns - start_ns) // 1_000_000)

    def _sv(k, v):
        return {"key": k, "value": {"stringValue": str(v)}}
    def _iv(k, v):
        return {"key": k, "value": {"intValue": int(v)}}
    def _tok_hex():
        return _sec.token_hex(8)

    # ── I/O as JSON message arrays (server enrichment reads these) ────────────
    # Root span: clean user question only (what the user typed)
    input_messages  = json.dumps([{"role": "user",      "content": prompt}])
    output_messages = json.dumps([{"role": "assistant", "content": response_text}])
    # Child LLM spans: full text sent to model so token counts are reconcilable
    _llm_input = full_prompt or prompt
    llm_input_messages  = json.dumps([{"role": "user",      "content": _llm_input}])
    llm_output_messages = output_messages

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
        "session_id": session_id,
        "trace_id": None,
    })

    workspace_id = "00000000-0000-0000-0000-000000000001"
    _langfuse_tags = json.dumps([
        f"agent_id:{agent_id}",
        f"environment:{environment}",
        f"tenant_id:{tenant_id}",
        f"workspace_id:{workspace_id}",
    ])

    # ── Root span: invoke_agent (AGENT kind) ─────────────────────────────────
    root_attrs = [
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
        _sv("workspace.id",          workspace_id),
        _sv("instance.id",           tenant_id),
        _sv("tenant.id",             tenant_id),
        # WXO facet attributes — tag generation and routing
        _sv("wxo.facet.tenant_id",    tenant_id),
        _sv("wxo.facet.workspace_id", workspace_id),
        _sv("wxo.facet.agent_id",     agent_id),
        _sv("wxo.facet.workflow_id",  span_name),
        _sv("wxo.channel.name",       "external_agent"),
        _sv("wxo.channel.type",       "text"),
        # Langfuse trace-level markers
        _sv("langfuse.internal.as_root", "true"),
        _sv("langfuse.trace.name",    span_name),
        _sv("langfuse.tags",          _langfuse_tags),
        _sv("is.root",                "true"),
        _sv("global_transaction_id",  trace_id),
        # Primary I/O for server enrichment
        _sv("gen_ai.input.messages",  input_messages),
        _sv("gen_ai.output.messages", output_messages),
        # Structured WXO message envelope — gives the Langfuse trace a rich input object
        _sv("gen_ai.message.input",   _input_envelope),
        # Flat-string copies for ClickHouse / backwards-compat
        _sv("input.value",  prompt),
        _sv("output.value", response_text),
        _sv("gen_ai.task.input",   prompt),
        _sv("gen_ai.task.output",  response_text),
        _sv("input",  prompt),
        _sv("output", response_text),
        _sv("llm.model_name",        model_name),
        _sv("model",                 model_name),
        _sv("gen_ai.response.model", model_name),
        _sv("llm.system",            "aws_bedrock"),
        _sv("agent.execution.status", "error" if is_error else "success"),
        _sv("agent.business_outcome", "failed" if is_error else "success"),
        _sv("framework",              "aws_bedrock_agentcore"),
        _sv("tokens.estimated",       str(tokens_estimated).lower()),
        # AGENT span kind — root is the agent orchestration wrapper
        _sv("openinference.span.kind", "AGENT"),
        _sv("gen_ai.system",           "aws_bedrock_agentcore"),
        _sv("gen_ai.request.model",    model_name),
        _iv("latency_ms",              latency_ms),
        # Token counts on root for ClickHouse rollup
        _iv("gen_ai.usage.input_tokens",      input_tokens),
        _iv("gen_ai.usage.output_tokens",     output_tokens),
        _iv("gen_ai.usage.prompt_tokens",     input_tokens),
        _iv("gen_ai.usage.completion_tokens", output_tokens),
        _iv("llm.usage.prompt_tokens",        input_tokens),
        _iv("llm.usage.completion_tokens",    output_tokens),
        _iv("llm.usage.total_tokens",         total_tokens),
        _iv("llm.token_count.prompt",         input_tokens),
        _iv("llm.token_count.completion",     output_tokens),
        _iv("llm.token_count.total",          total_tokens),
        _sv("provided_usage_details", json.dumps({
            "input": input_tokens, "output": output_tokens, "total": total_tokens,
        })),
        _sv("langfuse.observation.usage_details", json.dumps({
            "input": input_tokens, "output": output_tokens, "total": total_tokens,
        })),
    ]
    if runtime_id:
        root_attrs.append(_sv("aws.agent.runtime.id", runtime_id))
    if is_error and error_msg:
        root_attrs.append(_sv("error.type",    "AgentCoreError"))
        root_attrs.append(_sv("error.message", error_msg[:4000]))

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
                    _sv("langfuse.step.name",        f"generate_content {model_name}"),
                ],
            })

    root_span = {
        "traceId":            trace_id,
        "spanId":             root_span_id,
        "name":               span_name,
        "kind":               2,   # CLIENT (outbound to agent)
        "startTimeUnixNano":  start_ns,
        "endTimeUnixNano":    end_ns,
        "status":             {"code": 2 if is_error else 0},
        "attributes":         root_attrs,
        **({"events": _step_events} if _step_events else {}),
    }

    # ── call_llm span (LLM wrapper child of root) ─────────────────────────────
    call_llm_id = _tok_hex()
    # Offset slightly inside the root span for visual nesting
    llm_start = start_ns + max(1_000_000, (end_ns - start_ns) // 20)  # ~5% in
    llm_end   = end_ns   - max(1_000_000, (end_ns - start_ns) // 20)  # ~5% from end

    call_llm_span = {
        "traceId":            trace_id,
        "spanId":             call_llm_id,
        "parentSpanId":       root_span_id,
        "name":               "call_llm",
        "kind":               3,   # PRODUCER
        "startTimeUnixNano":  llm_start,
        "endTimeUnixNano":    llm_end,
        "status":             {"code": 0},
        "attributes": [
            _sv("openinference.span.kind", "CHAIN"),
            _sv("gen_ai.request.model",    model_name),
            _sv("llm.model_name",          model_name),
            _sv("gen_ai.system",           "aws_bedrock_agentcore"),
            # Use full context sent to model — tokens match what Claude billed
            _sv("gen_ai.input.messages",   llm_input_messages),
            _sv("gen_ai.output.messages",  llm_output_messages),
            _iv("gen_ai.usage.input_tokens",     input_tokens),
            _iv("gen_ai.usage.output_tokens",    output_tokens),
            _iv("gen_ai.usage.prompt_tokens",    input_tokens),
            _iv("gen_ai.usage.completion_tokens",output_tokens),
            _iv("llm.usage.prompt_tokens",       input_tokens),
            _iv("llm.usage.completion_tokens",   output_tokens),
            _iv("llm.token_count.prompt",        input_tokens),
            _iv("llm.token_count.completion",    output_tokens),
            _iv("llm.token_count.total",         total_tokens),
            _sv("provided_usage_details", json.dumps({
                "input": input_tokens, "output": output_tokens, "total": total_tokens,
            })),
            _sv("langfuse.observation.usage_details", json.dumps({
                "input": input_tokens, "output": output_tokens, "total": total_tokens,
            })),
        ],
    }

    # ── generate_content <model> span (LLM leaf child of call_llm) ───────────
    gen_id = _tok_hex()
    # Sits just inside call_llm
    gen_start = llm_start + max(500_000, (llm_end - llm_start) // 20)
    gen_end   = llm_end   - max(500_000, (llm_end - llm_start) // 20)

    generate_span = {
        "traceId":            trace_id,
        "spanId":             gen_id,
        "parentSpanId":       call_llm_id,
        "name":               f"generate_content {model_name}",
        "kind":               3,
        "startTimeUnixNano":  gen_start,
        "endTimeUnixNano":    gen_end,
        "status":             {"code": 0},
        "attributes": [
            _sv("openinference.span.kind", "LLM"),
            _sv("gen_ai.request.model",    model_name),
            _sv("llm.model_name",          model_name),
            _sv("gen_ai.system",           "aws_bedrock_agentcore"),
            # Full context so token counts shown on this span reconcile
            _sv("gen_ai.prompt",           _llm_input[:2000]),
            _sv("gen_ai.completion",       response_text[:2000]),
            _sv("gen_ai.input.messages",   llm_input_messages),
            _sv("gen_ai.output.messages",  llm_output_messages),
            _iv("gen_ai.usage.input_tokens",     input_tokens),
            _iv("gen_ai.usage.output_tokens",    output_tokens),
            _iv("gen_ai.usage.prompt_tokens",    input_tokens),
            _iv("gen_ai.usage.completion_tokens",output_tokens),
            _sv("provided_usage_details", json.dumps({
                "input": input_tokens, "output": output_tokens, "total": total_tokens,
            })),
        ],
    }

    # ── Tool call spans (TOOL children of generate_content, with sub_calls) ───
    # Recursive helper to emit tool spans and any nested sub-tools.
    spans = [root_span, call_llm_span, generate_span]

    _gen_window = max(1, gen_end - gen_start)
    tc_count = len(tool_calls) if tool_calls else 0

    def _emit_tool_spans_agentcore(tc_list, parent_id, win_s, win_e, _depth=0):
        """Recursively append spans for tool calls into *spans*.

        depth=0 + has sub_calls → openinference.span.kind=CHAIN
          Langfuse renders the parent tool as a collapsible container so the
          tool name ("calculate", "get_weather", …) is visible in the trace
          tree rather than being collapsed away and showing only the sub-call
          ("verify_result", "fetch_forecast_detail", …) at root level.
        depth>0 or no sub_calls → TOOL (leaf tool invocation node).
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
            _sid = _tok_hex()
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
                _emit_tool_spans_agentcore(_sub, _sid, _ts, _te, _depth + 1)

    if tool_calls:
        _emit_tool_spans_agentcore(tool_calls, gen_id, gen_start, gen_end)

    # ── RETRIEVER span (always present — synthetic knowledge_base lookup) ─────
    # Sits inside generate_content window, after any tool spans.
    _rv_slot  = _gen_window // (tc_count + 2)
    _rv_start = gen_start + _rv_slot * (tc_count + 1)
    _rv_end   = min(_rv_start + max(1_000_000, _rv_slot // 2), gen_end)
    spans.append({
        "traceId":            trace_id,
        "spanId":             _tok_hex(),
        "parentSpanId":       gen_id,
        "name":               "retrieval",
        "kind":               3,
        "startTimeUnixNano":  _rv_start,
        "endTimeUnixNano":    _rv_end,
        "status":             {"code": 0},
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
                _sv("agent.display_name",        agent_display_name),
                _sv("gen_ai.agent.id",           agent_id),
                _sv("gen_ai.agent.name",         agent_name),
                _sv("environment.name",          environment),
                _sv("deployment.environment",    environment),
            ]},
            "scopeSpans": [{"scope": {"name": "wxo-universal-forwarder", "version": "2.0.0"}, "spans": spans}],
        }]
    }


# ---------------------------------------------------------------------------
# Lambda entry point
# ---------------------------------------------------------------------------

def lambda_handler(event: dict, context) -> dict:
    logger.info("=== agentcore-trace-hook invoked ===")
    logger.info(f"event keys: {list(event.keys()) if isinstance(event, dict) else type(event)}")
    logger.info(f"event body: {json.dumps(event)[:2000]}")

    # Per-agent routing:
    #   Flow B (runtime) — WXO_TENANT_ID / WXO_OTEL_EXPORT_URL are Lambda env vars
    #                       injected by flow_runtime.sh via update-function-configuration.
    #   Flow A (harness) — The Lambda has NO per-agent env vars.  Instead,
    #                       flow_harness.sh writes tenant_id + export_url into SSM at
    #                       /wxo-agent/agents/<runtime_id>/tenant_id  (and /export_url).
    #                       The ADOT SDK bakes aws.agent.runtime.id into every span's
    #                       resource attributes via OTEL_RESOURCE_ATTRIBUTES, so we can
    #                       look up the SSM entries using that runtime_id.
    #
    # This design keeps multi-tenant isolation:  each agent (harness or runtime) stores
    # its own tenant/URL in SSM keyed by its unique runtime_id — the Lambda never holds
    # any per-tenant state in its own environment.
    # cpd mode has no tenant — only the export URL (and credentials) are needed.
    export_url  = (os.environ.get("WXO_OTEL_EXPORT_URL") or os.environ.get("OTEL_EXPORT_URL", "")).strip()
    tenant_id   = (os.environ.get("WXO_TENANT_ID") or os.environ.get("TENANT_ID", "")).strip() or _extract_tenant_id(export_url)
    environment = os.environ.get("WXO_ENVIRONMENT_NAME", "draft")

    # ── For harness (Flow A) OTLP pushes: resolve routing via runtime_id → SSM ─
    _needs_tenant = _DEPLOYMENT_MODE == "cloud" and not tenant_id
    if (_needs_tenant or not export_url) and _is_otlp_push(event):
        try:
            _, proto_bytes_early, is_proto_early = _decode_otlp_body(event)
            if is_proto_early and proto_bytes_early:
                rs_list_early = _decode_otlp_proto(proto_bytes_early)
                if rs_list_early:
                    ra = rs_list_early[0]["resource_attrs"]
                    # runtime_id is baked in via OTEL_RESOURCE_ATTRIBUTES by flow_harness.sh
                    runtime_id_early = ra.get("aws.agent.runtime.id", "")
                    if runtime_id_early:
                        ssm_id = _get_agent_identity(runtime_id_early)
                        if not tenant_id:
                            tenant_id  = ssm_id.get("tenant_id",  "")
                        if not export_url:
                            export_url = ssm_id.get("export_url", "")
                        if not environment and ssm_id.get("environment"):
                            environment = ssm_id["environment"]
                    if not environment:
                        environment = ra.get("wxo.environment", "draft")
        except Exception as _exc_early:
            logger.debug(f"[HOOK] early routing extraction failed: {_exc_early}")

    # ── Resolve credentials + export URL for the active deployment mode ───────
    if _DEPLOYMENT_MODE == "cpd":
        cpd = _get_cpd_config()
        if not cpd["host_url"] or not cpd["username"] or not cpd["password"]:
            logger.error("[HOOK] CPD credentials not resolved — set CPD_HOST_URL / CPD_USERNAME / CPD_PASSWORD "
                         "(Lambda env or SSM /wxo-agent/cpd/*)")
            return {"statusCode": 400, "message": "CPD credentials not configured"}
        export_url = export_url or _build_cpd_export_url(cpd)
        if not export_url:
            logger.error("[HOOK] CPD export URL not resolved — set CPD_NAMESPACE and CPD_INSTANCE_ID "
                         "(or WXO_OTEL_EXPORT_URL)")
            return {"statusCode": 400, "message": "CPD export URL not configured"}
        tenant_id = ""   # CPD has no tenant
        _token_args = (cpd["username"], cpd["password"], cpd["host_url"])
        _fetch_token = _get_cpd_bearer_token
    else:
        if not tenant_id and export_url:
            tenant_id = _extract_tenant_id(export_url)
        if not tenant_id:
            logger.error("[HOOK] WXO_TENANT_ID not resolved — set via Lambda env (Flow B) or SSM per-runtime (Flow A)")
            return {"statusCode": 400, "message": "WXO_TENANT_ID not configured"}
        if not export_url:
            logger.error("[HOOK] WXO_OTEL_EXPORT_URL not resolved — set via Lambda env (Flow B) or SSM per-runtime (Flow A)")
            return {"statusCode": 400, "message": "WXO_OTEL_EXPORT_URL not configured"}
        # Per-tenant credentials from SSM — keyed by WXO_TENANT_ID so each tenant
        # gets its own API key.  Falls back to legacy flat /wxo-agent/API_KEY.
        _token_args = _get_tenant_credentials(tenant_id)
        _fetch_token = _get_bearer_token

    logger.info(f"[HOOK] mode={_DEPLOYMENT_MODE!r} tenant={tenant_id!r} env={environment!r} export={export_url[:50]!r}...")

    # =========================================================================
    # PATH A — OTLP push (Harness ADOT SDK → API GW → Lambda)
    # =========================================================================
    if _is_otlp_push(event):
        otlp_json, proto_bytes, is_proto = _decode_otlp_body(event)
        logger.info(f"[HOOK] OTLP push detected from harness — content={'protobuf' if is_proto else 'json'}")

        # ── Step 1: resolve WXO identity ────────────────────────────────────
        identity: dict = {"agent_id": "", "agent_name": "", "agent_display_name": "", "environment": "", "runtime_id": ""}

        if is_proto and proto_bytes:
            # Try full structured decode first
            try:
                rs_list = _decode_otlp_proto(proto_bytes)
                logger.info(f"[HOOK] Decoded OTLP trace from harness: {json.dumps(rs_list, default=str)}")
                if rs_list:
                    identity = _extract_wxo_identity_from_resource_attrs(rs_list[0]["resource_attrs"])
                    logger.info(f"[HOOK] identity via proto decode: {identity}")
            except Exception as exc:
                logger.warning(f"[HOOK] proto decode error: {exc}")

            # Fallback: string scanner
            if not identity["agent_id"]:
                identity = _extract_wxo_identity_from_strings(proto_bytes)
                logger.info(f"[HOOK] identity via string scan: {identity}")

        elif otlp_json:
            logger.info(f"[HOOK] Received OTLP JSON trace from harness: {json.dumps(otlp_json, default=str)}")
            for rs in otlp_json.get("resourceSpans", []):
                attrs = {a["key"]: list(a["value"].values())[0]
                         for a in rs.get("resource", {}).get("attributes", [])}
                identity = _extract_wxo_identity_from_resource_attrs(attrs)
                if identity["agent_id"]:
                    break

        # SSM fallback when wxo.* attrs not yet baked into the span
        runtime_id = identity["runtime_id"]
        if not identity["agent_id"] and runtime_id:
            ssm_id = _get_agent_identity(runtime_id)
            identity["agent_id"]           = ssm_id["agent_id"]
            identity["agent_name"]         = ssm_id["agent_name"]
            identity["agent_display_name"] = ssm_id["agent_display_name"]

        agent_id           = identity["agent_id"]           or ""
        agent_name         = identity["agent_name"]         or _agent_name_from_arn("")
        agent_display_name = identity["agent_display_name"] or agent_name
        if identity["environment"]:
            environment = identity["environment"]

        # service.instance.id — the UUID ADOT stamps on every span from the same
        # harness container instance.  It is IDENTICAL across all LLM-step pushes
        # for one user turn (unlike span traceId which is fresh per LLM call).
        # We use it as the deferred-buffer key so intermediate steps from the same
        # agentic turn collapse into a single WXO trace.
        instance_id: str = ""
        try:
            if is_proto and proto_bytes:
                _ra = _decode_otlp_proto(proto_bytes)[0]["resource_attrs"]
                instance_id = str(_ra.get("service.instance.id", "") or "")
            elif otlp_json:
                _ra0 = {a["key"]: list(a["value"].values())[0]
                        for a in otlp_json.get("resourceSpans", [{}])[0]
                        .get("resource", {}).get("attributes", [])}
                instance_id = str(_ra0.get("service.instance.id", "") or "")
        except Exception:
            pass

        logger.info(
            f"[HOOK] identity resolved: agent_id={agent_id!r} "
            f"agent_name={agent_name!r} env={environment!r} "
            f"instance_id={instance_id!r}"
        )

        # ── Step 2: extract prompt + response from spans ─────────────────────
        prompt        = ""    # clean user question (shown in UI trace card)
        full_prompt   = ""    # full text sent to model; used on child LLM spans
        response_text = ""
        input_tokens  = 0
        output_tokens = 0
        start_ns      = 0
        end_ns        = 0
        span_trace_id = ""
        session_id    = ""
        user_id       = ""
        model_name    = ""
        tool_calls: list = []
        reasoning_steps: list = []
        user_text_hint: str = ""
        # Set to True when a Strands invoke_agent span is found — the push is then
        # the definitive final push of the turn and is shipped with zero delay.
        is_strands_final: bool = False
        # Set to True when strands.telemetry.tracer scope is present in this batch.
        # Prevents the botocore path from shipping when a Strands final is coming.
        has_strands_scope: bool = False

        def _extract_user_text_from_event_span(sp_attrs: dict, sp_events: list) -> str:
            """Try to find the actual user question from a BedrockAgentCore.CreateEvent span.

            The ADOT SDK records the raw ``content`` argument passed to
            ``agentcore_client.create_event(sessionId, content=[...])`` as a span
            attribute named ``aws.bedrock_agentcore.memory.content`` or in a span
            event named ``gen_ai.user.message``.  We look for text that does NOT
            start with ``<user_context>`` since that is the injected memory block.
            """
            # Check span attribute first
            for k in ("aws.bedrock_agentcore.memory.content",
                      "aws.bedrock_agentcore.event.content",
                      "rpc.params", "params", "input", "message.content"):
                raw = sp_attrs.get(k)
                if not raw:
                    continue
                t = _extract_input_text(raw) or str(raw)
                if t and not t.strip().startswith("<user_context>"):
                    return t.strip()
            # Check span events
            for ev in sp_events:
                raw = ev.get("attributes", {}).get("content", "")
                if not raw:
                    continue
                t = _extract_input_text(raw) or str(raw)
                if t and not t.strip().startswith("<user_context>"):
                    return t.strip()
            return ""

        def _is_llm_span(n: str) -> bool:
            """True for spans that represent the top-level LLM invocation.

            Covers:
            - WXO synthetic  → "invoke_agent <name>"
            - ADOT Bedrock   → "chat <model>"  (e.g. "chat global.anthropic.claude-sonnet-4-6")
            - OpenAI/Vertex  → "openai.chat" / "vertexai.generate_content" etc.
            """
            return (
                "invoke_agent" in n
                or n.startswith("chat ")
                or n == "chat"
                or "generate_content" in n
                or "chat_completions" in n
            )

        def _is_top_llm_span(n: str) -> bool:
            """True only for the top-level LLM span that carries authoritative token counts.

            The ADOT Bedrock harness emits a two-level LLM span tree per turn:
              chat <model>                        ← top-level; has the real usage counts
                └── generate_content <model>      ← sub-span; also matches _is_llm_span
                      └── retrieval / tool spans

            Both match _is_llm_span, so if we extract tokens from every matching span
            the last one written (generate_content) wins and can differ from the actual
            billed counts — especially across a multi-turn batch where the sub-spans
            carry per-step rather than per-invocation totals.

            This predicate matches ONLY the outer wrapper so token counts are always
            read from the canonical billing span.  _is_llm_span is still used for
            timing and prompt/response event extraction.
            """
            return (
                "invoke_agent" in n
                or n.startswith("chat ")
                or n == "chat"
                or "chat_completions" in n
            )

        def _is_tool_span(sp_dict: dict, attrs_dict: dict) -> bool:
            """True for spans that represent a tool / function call."""
            oi = attrs_dict.get("openinference.span.kind", "")
            if oi == "TOOL":
                return True
            n = sp_dict.get("name", "")
            return (
                "tool" in n.lower()
                or "function_call" in n.lower()
                or bool(attrs_dict.get("tool.name"))
                or bool(attrs_dict.get("gen_ai.tool.name"))
            )

        def _tool_io_from_events(events: list, as_dict: bool) -> tuple:
            """Tool input / output from a Strands execute_tool span's events.

            Strands records the tool input in ``gen_ai.tool.message`` (content) and the
            result in ``gen_ai.choice`` (message) rather than as span attributes.
            """
            t_in, t_out = "", ""
            for ev in events or []:
                ea = (ev.get("attributes", {}) if as_dict else
                      {a["key"]: list(a["value"].values())[0] for a in ev.get("attributes", [])})
                if ev.get("name") == "gen_ai.tool.message":
                    t_in = str(ea.get("content") or "")
                elif ev.get("name") == "gen_ai.choice":
                    raw = ea.get("message") or ""
                    try:
                        blocks = json.loads(raw) if isinstance(raw, str) else raw
                        texts = [b.get("text", "") for b in blocks if isinstance(b, dict)]
                        t_out = "\n".join(t for t in texts if t) or str(raw)
                    except Exception:
                        t_out = str(raw)
            return t_in, t_out

        def _build_tool_tree_proto(rs_list: list) -> list:
            """Build nested tool_calls list from proto-decoded span list.

            Each tool span may have a parentSpanId that is itself a tool span —
            those become sub_calls of their parent rather than top-level entries.
            Returns a list of top-level tool_call dicts with optional sub_calls.
            """
            # Pass 1: collect all tool spans indexed by spanId
            span_by_id: dict = {}
            tool_ids: set = set()
            for rs in rs_list:
                for ss in rs["scope_spans"]:
                    for sp in ss["spans"]:
                        sid = sp.get("spanId") or sp.get("span_id") or ""
                        if sid:
                            span_by_id[sid] = sp
                        if _is_tool_span(sp, sp["attributes"]):
                            if sid:
                                tool_ids.add(sid)

            # Pass 2: build tc dicts
            tc_by_id: dict = {}
            for sid in tool_ids:
                sp = span_by_id[sid]
                attrs = sp["attributes"]
                n = sp["name"]
                _ev_in, _ev_out = _tool_io_from_events(sp.get("events"), True)
                tc_by_id[sid] = {
                    "name":     (attrs.get("tool.name") or attrs.get("gen_ai.tool.name") or n),
                    "input":    str(attrs.get("tool.parameters") or attrs.get("input.value") or attrs.get("tool.input") or _ev_in),
                    "output":   str(attrs.get("tool.output") or attrs.get("output.value") or _ev_out),
                    "start_ns": sp["startTimeUnixNano"],
                    "end_ns":   sp["endTimeUnixNano"],
                    "is_error": sp.get("status", {}).get("code") == 2,
                    "sub_calls": [],
                }

            # Pass 3: assign sub_calls vs top-level
            top: list = []
            for sid in tool_ids:
                sp = span_by_id[sid]
                pid = sp.get("parentSpanId") or sp.get("parent_span_id") or ""
                if pid and pid in tool_ids:
                    tc_by_id[pid]["sub_calls"].append(tc_by_id[sid])
                else:
                    top.append(tc_by_id[sid])

            top.sort(key=lambda t: t.get("start_ns") or 0)
            for tc in tc_by_id.values():
                tc["sub_calls"].sort(key=lambda t: t.get("start_ns") or 0)
            return top

        def _build_tool_tree_json(ss_spans: list) -> list:
            """Build nested tool_calls list from JSON OTLP span list."""
            span_by_id: dict = {}
            tool_ids: set = set()
            for sp in ss_spans:
                sid = sp.get("spanId", "")
                attrs_raw = sp.get("attributes", [])
                attrs = {a["key"]: list(a["value"].values())[0] for a in attrs_raw}
                sp["_attrs_cache"] = attrs
                if sid:
                    span_by_id[sid] = sp
                if _is_tool_span(sp, attrs):
                    if sid:
                        tool_ids.add(sid)

            tc_by_id: dict = {}
            for sid in tool_ids:
                sp = span_by_id[sid]
                attrs = sp["_attrs_cache"]
                n = sp.get("name", "")
                _ev_in, _ev_out = _tool_io_from_events(sp.get("events"), False)
                tc_by_id[sid] = {
                    "name":     (attrs.get("tool.name") or attrs.get("gen_ai.tool.name") or n),
                    "input":    str(attrs.get("tool.parameters") or attrs.get("input.value") or attrs.get("tool.input") or _ev_in),
                    "output":   str(attrs.get("tool.output") or attrs.get("output.value") or _ev_out),
                    "start_ns": int(sp.get("startTimeUnixNano") or 0),
                    "end_ns":   int(sp.get("endTimeUnixNano") or 0),
                    "is_error": sp.get("status", {}).get("code") == 2,
                    "sub_calls": [],
                }

            top: list = []
            for sid in tool_ids:
                sp = span_by_id[sid]
                pid = sp.get("parentSpanId", "")
                if pid and pid in tool_ids:
                    tc_by_id[pid]["sub_calls"].append(tc_by_id[sid])
                else:
                    top.append(tc_by_id[sid])

            top.sort(key=lambda t: t.get("start_ns") or 0)
            for tc in tc_by_id.values():
                tc["sub_calls"].sort(key=lambda t: t.get("start_ns") or 0)
            # cleanup
            for sp in ss_spans:
                sp.pop("_attrs_cache", None)
            return top

        if is_proto and proto_bytes:
            try:
                rs_list = _decode_otlp_proto(proto_bytes)
                tool_calls = _build_tool_tree_proto(rs_list)
                # True when ANY scope in this batch is strands.telemetry.tracer.
                # Used below to prevent the botocore path from shipping a trace when
                # a Strands final push is expected in a subsequent batch.
                has_strands_scope: bool = any(
                    ss.get("scope_name", "") == "strands.telemetry.tracer"
                    for rs in rs_list
                    for ss in rs["scope_spans"]
                )
                # Two-pass: first find the Strands invoke_agent span (turn signal),
                # then process botocore spans only for data not provided by Strands.
                # Pass 1 — Strands scope only
                for rs in rs_list:
                    for ss in rs["scope_spans"]:
                        if ss.get("scope_name", "") != "strands.telemetry.tracer":
                            continue
                        for sp in ss["spans"]:
                            name  = sp["name"]
                            attrs = sp["attributes"]
                            if not ("invoke_agent" in name and
                                    attrs.get("gen_ai.operation.name") == "invoke_agent"):
                                continue
                            # Found the Strands invoke_agent span
                            _sp_status = sp.get("status", {})
                            _ok = (
                                _sp_status.get("code") == 0
                                or str(_sp_status.get("code", "")).upper() == "OK"
                                or _sp_status.get("code") not in (1, 2, "ERROR", "UNSET")
                            )
                            if _ok:
                                is_strands_final = True
                            if sp["startTimeUnixNano"]:
                                start_ns = sp["startTimeUnixNano"]
                            if sp["endTimeUnixNano"]:
                                end_ns = sp["endTimeUnixNano"]
                            if not span_trace_id:
                                span_trace_id = sp["traceId"]
                            it = int(attrs.get("gen_ai.usage.input_tokens",   0) or 0) \
                              or int(attrs.get("gen_ai.usage.prompt_tokens",  0) or 0)
                            ot = int(attrs.get("gen_ai.usage.output_tokens",   0) or 0) \
                              or int(attrs.get("gen_ai.usage.completion_tokens",0) or 0)
                            if it: input_tokens  = it
                            if ot: output_tokens = ot
                            if not session_id:
                                session_id = str(attrs.get("session.id") or "")
                            if not model_name:
                                model_name = str(attrs.get("gen_ai.request.model") or "")
                            _strand_evs = sp.get("events", [])
                            # Diagnostic: log event names + attribute keys from Strands span
                            if _strand_evs:
                                _ev_summary = [
                                    {"name": ev.get("name", ""), "keys": list(ev.get("attributes", {}).keys())}
                                    for ev in _strand_evs
                                ]
                                logger.info(f"[HOOK] Strands span events: {_ev_summary}")
                            for ev in _strand_evs:
                                ev_name   = ev.get("name", "")
                                ev_attrs  = ev.get("attributes", {})
                                # Only extract user prompt from user-message events —
                                # system/assistant messages must not overwrite the user question.
                                if ev_name == "gen_ai.user.message":
                                    raw_in = ev_attrs.get("content", "")
                                    if raw_in and not full_prompt:
                                        _fp = _extract_input_text(raw_in) or str(raw_in)
                                        if _fp:
                                            full_prompt = _fp
                                            _cleaned = _clean_prompt(_fp)
                                            if _cleaned and _cleaned != "(user question not captured in ADOT span)":
                                                prompt = _cleaned
                                elif ev_name in ("gen_ai.reasoning", "gen_ai.thinking",
                                                 "anthropic.thinking", "model.reasoning"):
                                    _r = (ev_attrs.get("gen_ai.reasoning.content")
                                          or ev_attrs.get("thinking")
                                          or ev_attrs.get("content") or "")
                                    if _r:
                                        reasoning_steps.append(str(_r))
                                elif ev_name == "gen_ai.choice" and ev_attrs.get("finish_reason") == "interrupt":
                                    # The turn stopped at a tool request (harness inline tool).
                                    # The message is the raw interrupt record, not an answer:
                                    # record the requested tool call and leave response_text
                                    # to the model's own chat-span output.
                                    try:
                                        import ast as _ast
                                        for _it in _ast.literal_eval(str(ev_attrs.get("message") or "[]")):
                                            _tu = ((_it or {}).get("reason") or {}).get("toolUse")
                                            if _tu and not tool_calls:
                                                tool_calls.append({
                                                    "name":     str(_tu.get("name") or ""),
                                                    "input":    json.dumps(_tu.get("input") or {}),
                                                    "output":   "",
                                                    "start_ns": 0,
                                                    "end_ns":   0,
                                                    "is_error": False,
                                                    "sub_calls": [],
                                                })
                                    except Exception:
                                        pass
                                elif ev_name == "gen_ai.choice":
                                    raw_out = (ev_attrs.get("gen_ai.completion")
                                               or ev_attrs.get("message")
                                               or ev_attrs.get("output")
                                               or ev_attrs.get("response") or "")
                                    if raw_out and not response_text:
                                        response_text = _extract_text_field(raw_out) or str(raw_out)
                                    # Extract tool calls from the choice message when the
                                    # intermediate execute_tool batch arrived on a different
                                    # Lambda container and tool_calls is still empty.
                                    if raw_out and not tool_calls:
                                        try:
                                            _msg = raw_out if isinstance(raw_out, dict) else json.loads(raw_out)
                                            _content = _msg.get("content", []) if isinstance(_msg, dict) else []
                                            if isinstance(_content, list):
                                                for _blk in _content:
                                                    if not isinstance(_blk, dict):
                                                        continue
                                                    _tu = _blk.get("toolUse") or (_blk if _blk.get("type") == "tool_use" else None)
                                                    if _tu:
                                                        tool_calls.append({
                                                            "name":      str(_tu.get("name") or _tu.get("id") or ""),
                                                            "input":     json.dumps(_tu.get("input") or {}),
                                                            "output":    "",
                                                            "start_ns":  0,
                                                            "end_ns":    0,
                                                            "is_error":  False,
                                                            "sub_calls": [],
                                                        })
                                        except Exception:
                                            pass
                            if not prompt:
                                for k in ("gen_ai.prompt", "input", "inputText"):
                                    v = attrs.get(k)
                                    if v:
                                        prompt = _clean_prompt(_extract_input_text(v) or str(v))
                                        if prompt: break
                            if not response_text:
                                for k in ("gen_ai.completion", "output", "outputText"):
                                    v = attrs.get(k)
                                    if v:
                                        response_text = _extract_text_field(v) or str(v)
                                        if response_text: break
                            logger.info(
                                f"[HOOK] Strands invoke_agent span — "
                                f"is_final={is_strands_final} "
                                f"tokens={input_tokens}/{output_tokens} "
                                f"session={session_id!r}"
                            )

                # Pass 2 — botocore + other scopes (fallback data only)
                for rs in rs_list:
                    for ss in rs["scope_spans"]:
                        scope_name = ss.get("scope_name", "")
                        for sp in ss["spans"]:
                            name  = sp["name"]
                            attrs = sp["attributes"]

                            # Strands invoke_agent span already handled in pass 1 — skip
                            if (scope_name == "strands.telemetry.tracer"
                                    and "invoke_agent" in name
                                    and attrs.get("gen_ai.operation.name") == "invoke_agent"):
                                continue

                            # ── Scan CreateEvent spans for actual user text ─
                            if name == "BedrockAgentCore.CreateEvent" and not user_text_hint:
                                user_text_hint = _extract_user_text_from_event_span(
                                    attrs, sp.get("events", []))

                            # ── FALLBACK: botocore chat / LLM spans ─────────────
                            # Always walk these for prompt/response events (gen_ai.choice).
                            # When is_strands_final is True we still allow response_text to
                            # be filled from gen_ai.choice — the Strands span event extraction
                            # may have come up empty — but we NEVER overwrite tokens/timing
                            # that the Strands span already populated.
                            if _is_llm_span(name):
                                if not span_trace_id:
                                    span_trace_id = sp["traceId"]
                                if not is_strands_final:
                                    if not start_ns and sp["startTimeUnixNano"]:
                                        start_ns = sp["startTimeUnixNano"]
                                    if sp["endTimeUnixNano"]:
                                        end_ns = sp["endTimeUnixNano"]
                                if _is_top_llm_span(name) and not is_strands_final:
                                    # Only take token counts from botocore if Strands didn't provide them
                                    it = int(attrs.get("gen_ai.usage.input_tokens",   0) or 0) \
                                      or int(attrs.get("gen_ai.usage.prompt_tokens",  0) or 0) \
                                      or int(attrs.get("llm.usage.input_token_count", 0) or 0) \
                                      or int(attrs.get("inputTokenCount",             0) or 0)
                                    ot = int(attrs.get("gen_ai.usage.output_tokens",   0) or 0) \
                                      or int(attrs.get("gen_ai.usage.completion_tokens",0) or 0) \
                                      or int(attrs.get("llm.usage.output_token_count", 0) or 0) \
                                      or int(attrs.get("outputTokenCount",             0) or 0)
                                    if it: input_tokens  = it
                                    if ot: output_tokens = ot
                                if not session_id:
                                    session_id = str(
                                        attrs.get("conversation.id")
                                        or attrs.get("thread.id")
                                        or attrs.get("langfuse.session.id")
                                        or attrs.get("session.id")
                                        or attrs.get("sessionId")
                                        or attrs.get("context.id")
                                        or attrs.get("agent.session.id")
                                        or ""
                                    )
                                if not user_id:
                                    user_id = str(attrs.get("langfuse.user.id") or attrs.get("user.id") or "")
                                if not model_name:
                                    model_name = str(
                                        attrs.get("gen_ai.request.model")
                                        or attrs.get("llm.model_name")
                                        or attrs.get("gen_ai.response.model")
                                        or ""
                                    )
                                all_user_texts: list = []
                                for ev in sp["events"]:
                                    ev_name  = ev["name"]
                                    ev_attrs = ev["attributes"]
                                    if ev_name == "gen_ai.user.message":
                                        raw = ev_attrs.get("content", "")
                                        _p = _extract_input_text(raw) or (str(raw) if raw else "")
                                        all_user_texts.append(_p)
                                    elif ev_name in ("gen_ai.reasoning", "gen_ai.thinking",
                                                     "anthropic.thinking", "model.reasoning"):
                                        _r = (ev_attrs.get("gen_ai.reasoning.content")
                                              or ev_attrs.get("thinking")
                                              or ev_attrs.get("content") or "")
                                        if _r:
                                            reasoning_steps.append(str(_r))
                                    elif ev_name == "gen_ai.choice" and not response_text:
                                        raw = ev_attrs.get("message", "")
                                        response_text = _extract_text_field(raw) or (str(raw) if raw else "")
                                if all_user_texts:
                                    full_prompt = "\n\n".join(all_user_texts)
                                _PLACEHOLDER = "(user question not captured in ADOT span)"
                                if all_user_texts and (not prompt or prompt == _PLACEHOLDER):
                                    for _t in reversed(all_user_texts):
                                        _cleaned = _clean_prompt(_t)
                                        if _cleaned and _cleaned != _PLACEHOLDER:
                                            prompt = _cleaned
                                            break
                                    if not prompt or prompt == _PLACEHOLDER:
                                        prompt = _clean_prompt(all_user_texts[-1])
                                if not prompt:
                                    for k in ("gen_ai.prompt", "input", "gen_ai.input",
                                              "inputText", "userMessage", "query"):
                                        v = attrs.get(k)
                                        if v:
                                            prompt = _clean_prompt(_extract_input_text(v) or str(v))
                                            if prompt: break
                                if not response_text:
                                    for k in ("gen_ai.completion", "output", "gen_ai.output",
                                              "outputText", "completion"):
                                        v = attrs.get(k)
                                        if v:
                                            response_text = _extract_text_field(v) or str(v)
                                            if response_text: break
            except Exception as exc:
                logger.warning(f"[HOOK] span walk error: {exc}")

        elif otlp_json:
            # ── Build nested tool_calls tree from JSON OTLP spans ─────────────
            _all_json_spans = [
                sp
                for rs in otlp_json.get("resourceSpans", [])
                for ss in rs.get("scopeSpans", [])
                for sp in ss.get("spans", [])
            ]
            tool_calls = _build_tool_tree_json(_all_json_spans)
            for rs in otlp_json.get("resourceSpans", []):
                for ss in rs.get("scopeSpans", []):
                    for sp in ss.get("spans", []):
                        name  = sp.get("name", "")
                        attrs = {a["key"]: list(a["value"].values())[0]
                                 for a in sp.get("attributes", [])}
                        # ── Scan CreateEvent spans for actual user text ───
                        if name == "BedrockAgentCore.CreateEvent" and not user_text_hint:
                            user_text_hint = _extract_user_text_from_event_span(
                                attrs, sp.get("events", []))
                        if _is_llm_span(name):
                            if not span_trace_id:
                                span_trace_id = sp.get("traceId", "")
                            if not start_ns:
                                start_ns = int(sp.get("startTimeUnixNano", 0) or 0)
                            # Always update end_ns — last LLM span wins
                            _ens = int(sp.get("endTimeUnixNano", 0) or 0)
                            if _ens:
                                end_ns = _ens
                            # Token counts — only from the top-level chat span (same
                            # rationale as the proto path above: generate_content is a
                            # sub-span that must not overwrite the parent's billed counts).
                            if _is_top_llm_span(name):
                                it = int(attrs.get("gen_ai.usage.input_tokens",   0) or 0) \
                                  or int(attrs.get("gen_ai.usage.prompt_tokens",  0) or 0) \
                                  or int(attrs.get("llm.usage.input_token_count", 0) or 0) \
                                  or int(attrs.get("inputTokenCount",             0) or 0)
                                ot = int(attrs.get("gen_ai.usage.output_tokens",   0) or 0) \
                                  or int(attrs.get("gen_ai.usage.completion_tokens",0) or 0) \
                                  or int(attrs.get("llm.usage.output_token_count", 0) or 0) \
                                  or int(attrs.get("outputTokenCount",             0) or 0)
                                if it: input_tokens  = it
                                if ot: output_tokens = ot
                            if not session_id:
                                session_id = str(
                                    attrs.get("conversation.id")
                                    or attrs.get("thread.id")
                                    or attrs.get("langfuse.session.id")
                                    or attrs.get("session.id")
                                    or attrs.get("sessionId")
                                    or attrs.get("context.id")
                                    or attrs.get("agent.session.id")
                                    or ""
                                )
                            if not user_id:
                                user_id = str(attrs.get("langfuse.user.id") or attrs.get("user.id") or "")
                            if not model_name:
                                model_name = str(
                                    attrs.get("gen_ai.request.model")
                                    or attrs.get("llm.model_name")
                                    or attrs.get("gen_ai.response.model")
                                    or ""
                                )
                            _json_user_texts: list = []
                            for ev in sp.get("events", []):
                                ev_name  = ev.get("name", "")
                                ev_attrs = {a["key"]: list(a["value"].values())[0]
                                            for a in ev.get("attributes", [])}
                                if ev_name == "gen_ai.user.message":
                                    raw = ev_attrs.get("content", "")
                                    _p = _extract_input_text(raw) or (str(raw) if raw else "")
                                    _json_user_texts.append(_p)
                                elif ev_name in ("gen_ai.reasoning", "gen_ai.thinking",
                                                 "anthropic.thinking", "model.reasoning"):
                                    _r = (ev_attrs.get("gen_ai.reasoning.content")
                                          or ev_attrs.get("thinking")
                                          or ev_attrs.get("content") or "")
                                    if _r:
                                        reasoning_steps.append(str(_r))
                                elif ev_name == "gen_ai.choice" and not response_text:
                                    raw = ev_attrs.get("message", "")
                                    response_text = _extract_text_field(raw) or (str(raw) if raw else "")
                            if _json_user_texts:
                                full_prompt = "\n\n".join(_json_user_texts)
                                _PLACEHOLDER = "(user question not captured in ADOT span)"
                                if not prompt or prompt == _PLACEHOLDER:
                                    for _t in reversed(_json_user_texts):
                                        _cleaned = _clean_prompt(_t)
                                        if _cleaned and _cleaned != _PLACEHOLDER:
                                            prompt = _cleaned
                                            break
                                    if not prompt or prompt == _PLACEHOLDER:
                                        prompt = _clean_prompt(_json_user_texts[-1])
                            # Fallback: read prompt/response from span attributes
                            if not prompt:
                                for k in ("gen_ai.prompt", "input", "gen_ai.input",
                                          "inputText", "userMessage", "query"):
                                    v = attrs.get(k)
                                    if v:
                                        prompt = _clean_prompt(_extract_input_text(v) or str(v))
                                        if prompt: break
                            if not response_text:
                                for k in ("gen_ai.completion", "output", "gen_ai.output",
                                          "outputText", "completion"):
                                    v = attrs.get(k)
                                    if v:
                                        response_text = _extract_text_field(v) or str(v)
                                        if response_text: break

        # ADOT sends spans in two batches: first batch (infra spans) arrives
        # before the invoke_agent span.  Skip silently — no prompt = no trace.
        if not prompt and not response_text:
            logger.info("[HOOK] No invoke_agent span in this batch — skipping (infra-only push)")
            return {"statusCode": 200, "message": "no invoke_agent span"}

        # ── Gap-based buffer ─────────────────────────────────────────────────
        # Every push (toolUse OR text) is stored/replaced in the buffer for
        # this instance_id.  Tool calls accumulate across replacements.
        # On each push we sweep for entries whose inter-push gap has exceeded
        # _INTER_TURN_GAP_S — those belong to a COMPLETED prior turn.
        #
        # Normalise timing / text for the current push first.
        if not start_ns:
            start_ns = int(time.time() * 1e9) - 1_000_000_000
        if not end_ns:
            end_ns = int(time.time() * 1e9)
        if not prompt:
            prompt = "(unknown)"
        if not response_text:
            response_text = "(no response)"
        if (not prompt
                or prompt == "(user question not captured in ADOT span)"
                or prompt == "(unknown)") and user_text_hint:
            prompt = user_text_hint

        tokens_estimated = input_tokens == 0 and output_tokens == 0
        if tokens_estimated:
            input_tokens  = _count_tokens(prompt)
            output_tokens = _count_tokens(response_text)
        total_tokens = input_tokens + output_tokens

        # Decide whether this push has usable content for a WXO trace.
        # toolUse-only responses have no user-visible text — we still buffer
        # them to accumulate tool_calls, but they cannot be the final args.
        _resp_stripped = (response_text or "").strip()
        _is_tool_use_only = (
            _resp_stripped.startswith('[{"toolUse"')
            or _resp_stripped.startswith('{"toolUse"')
            or _resp_stripped.startswith('[{"type":"tool_use"')
            or _resp_stripped.startswith('{"type":"tool_use"')
            or response_text == "(no response)"
        )

        def _make_payload_args():
            return dict(
                agent_id=agent_id, agent_name=agent_name,
                agent_display_name=agent_display_name,
                environment=environment, tenant_id=tenant_id,
                prompt=prompt, response_text=response_text,
                start_ns=start_ns, end_ns=end_ns,
                input_tokens=input_tokens, output_tokens=output_tokens,
                total_tokens=total_tokens, tokens_estimated=tokens_estimated,
                runtime_id=runtime_id, session_id=session_id, user_id=user_id,
                model_name=model_name, trace_id="",
                tool_calls=tool_calls,
                full_prompt=full_prompt,
                reasoning_steps=reasoning_steps or None,
            )

        def _ship(args: dict) -> str:
            _tc = args.get("tool_calls") or []
            # Token counts are reported as the model billed them for this call
            # (each harness invocation sends its full context window).
            logger.info(
                f"[HOOK] extracted: prompt={args['prompt'][:80]!r} "
                f"response={args['response_text'][:80]!r} "
                f"tokens={args['input_tokens']}/{args['output_tokens']} "
                f"latency={(args['end_ns'] - args['start_ns'])//1_000_000}ms "
                f"tool_calls={len(_tc)}"
            )
            _bearer = _fetch_token(*_token_args)
            _pl = _build_wxo_payload(**args)
            _job = _post_to_wxo(_pl, _bearer, args["agent_id"], tenant_id, export_url)
            # Extract eval scores from span attributes and post to WXO scores endpoint
            _scores: list[dict] = []
            for _key, _val in args.items():
                if isinstance(_key, str) and _key.startswith(("eval.", "score.", "langfuse.score.")):
                    try:
                        _scores.append({"name": _key, "value": float(_val)})
                    except (TypeError, ValueError):
                        pass
            if _scores:
                _tid = (_pl.get("resourceSpans", [{}])[0]
                           .get("scopeSpans", [{}])[0]
                           .get("spans", [{}])[0]
                           .get("traceId", ""))
                _post_scores_to_wxo(
                    _scores, _bearer, args["agent_id"], args["agent_name"],
                    _tid, tenant_id, export_url,
                )
            return _job

        now = time.time()

        if not instance_id:
            # No instance_id — ship immediately (non-harness fallback)
            args_now = _make_payload_args()
            args_now["tool_calls"] = tool_calls
            job_id = _ship(args_now)
            logger.info(f"[HOOK] done — path=otlp job_id={job_id}")
            return {"statusCode": 200, "job_id": job_id, "path": "otlp"}

        # Accumulate any tool calls buffered from previous steps of this turn
        prior = _pending_traces.get(instance_id)
        prior_tools = list(prior.get("tool_calls", []) if prior else [])
        accumulated_tools = prior_tools + tool_calls

        # ── FAST PATH: Strands invoke_agent span — deterministic turn boundary ──
        # The Strands SDK emits this span exactly once per turn, after the final
        # assistant response is complete.  Ship immediately — no gap wait needed.
        if is_strands_final:
            _pending_traces.pop(instance_id, None)  # clear any buffered intermediate
            args_now = _make_payload_args()
            args_now["tool_calls"] = accumulated_tools
            job_id = _ship(args_now)
            logger.info(
                f"[HOOK] done (Strands final) — path=otlp job_id={job_id} "
                f"instance={instance_id!r}"
            )
            return {"statusCode": 200, "job_id": job_id, "path": "otlp"}

        # ── GAP-BASED FALLBACK for non-Strands pushes ─────────────────────────
        # botocore spans (chat <model>) arrive ~5s apart within one turn; the
        # gap between turns is >10s.  Sweep for expired entries on every push.
        last_shipped_job = None
        expired = [
            (iid, e) for iid, e in list(_pending_traces.items())
            if e.get("args") and (now - e.get("last_updated", 0)) >= _INTER_TURN_GAP_S
        ]
        for iid, e in expired:
            _j = _ship(e["args"])
            logger.info(f"[HOOK] done (gap expired) — path=otlp job_id={_j} instance={iid!r}")
            _pending_traces.pop(iid, None)
            last_shipped_job = _j

        if _is_tool_use_only:
            # toolUse step: accumulate tool calls but don't overwrite
            # the last real text response stored in args (if any).
            logger.info(
                f"[HOOK] toolUse step — accumulated tool_calls={len(accumulated_tools)} "
                f"instance={instance_id!r}"
            )
            if prior:
                prior["tool_calls"] = accumulated_tools
                prior["last_updated"] = now
            else:
                _pending_traces[instance_id] = {
                    "tool_calls": accumulated_tools,
                    "last_updated": now,
                }
        else:
            # Real text response.
            # If this batch already contains a Strands scope, a Strands final push
            # will arrive in a subsequent batch and own the ship — buffer here so
            # the Strands path picks up the accumulated tool_calls.
            # If there is NO Strands scope, ship immediately so the trace is never
            # lost to a cold start or idle container recycle.
            if has_strands_scope:
                args_now = _make_payload_args()
                args_now["tool_calls"] = accumulated_tools
                _pending_traces[instance_id] = {
                    "args": args_now,
                    "tool_calls": accumulated_tools,
                    "last_updated": now,
                }
                logger.info(
                    f"[HOOK] Buffered (Strands scope present, awaiting final) — "
                    f"instance={instance_id!r} tool_calls={len(accumulated_tools)}"
                )
            else:
                # No Strands — ship immediately; gap timer would never fire reliably.
                _pending_traces.pop(instance_id, None)
                args_now = _make_payload_args()
                args_now["tool_calls"] = accumulated_tools
                job_id = _ship(args_now)
                logger.info(
                    f"[HOOK] done (text response, shipped immediately) — "
                    f"path=otlp job_id={job_id} instance={instance_id!r} "
                    f"tool_calls={len(accumulated_tools)}"
                )
                return {"statusCode": 200, "job_id": job_id, "path": "otlp"}

        # Overflow eviction
        if len(_pending_traces) > _PENDING_MAX_ENTRIES:
            oldest_iid = next(iter(_pending_traces))
            evicted = _pending_traces.pop(oldest_iid)
            if evicted.get("args"):
                _j = _ship(evicted["args"])
                logger.info(f"[HOOK] done (evicted) — path=otlp job_id={_j}")

        if last_shipped_job:
            return {"statusCode": 200, "job_id": last_shipped_job, "path": "otlp"}
        return {"statusCode": 200, "message": "buffered"}

    # =========================================================================
    # PATH B — Direct AgentCore observability callback (custom runtime / hook)
    # =========================================================================
    if not _is_agentcore_event(event):
        logger.warning("[HOOK] Unrecognised event shape — skipping")
        return {"statusCode": 200, "message": "unrecognised event"}

    parsed     = _parse_agentcore_event(event)
    session_id = parsed["session_id"] or str(uuid.uuid4())
    trace_id   = uuid.uuid4().hex

    # Identity: prefer event fields (injected by sitecustomize.py), then SSM
    agent_id = (event.get("wxoAgentId") or "").strip()
    agent_name = (event.get("wxoAgentName") or "").strip()
    agent_display_name = (event.get("wxoAgentDisplayName") or "").strip()
    if event.get("wxoEnvironmentName"):
        environment = event["wxoEnvironmentName"].strip()

    if not agent_id:
        arn_in_event = parsed["arn"]
        runtime_id   = arn_in_event.rstrip("/").rsplit("/", 1)[-1] if arn_in_event else ""
        if runtime_id:
            ssm_id = _get_agent_identity(runtime_id)
            agent_id           = ssm_id["agent_id"]           or ""
            agent_name         = ssm_id["agent_name"]         or _agent_name_from_arn(arn_in_event)
            agent_display_name = ssm_id["agent_display_name"] or agent_name
        else:
            agent_name = _agent_name_from_arn(parsed["arn"])
            agent_display_name = agent_name
    else:
        if not agent_name:
            agent_name = _agent_name_from_arn(parsed["arn"])
        if not agent_display_name:
            agent_display_name = agent_name

    logger.info(
        f"[HOOK] callback: agent_id={agent_id!r} agent_name={agent_name!r} "
        f"prompt={parsed['prompt'][:60]!r} response={parsed['response'][:60]!r} "
        f"tokens={parsed['input_tokens']}/{parsed['output_tokens']} "
        f"latency={parsed['latency_ms']}ms"
    )

    bearer_token = _fetch_token(*_token_args)
    payload = _build_wxo_payload(
        agent_id=agent_id, agent_name=agent_name,
        agent_display_name=agent_display_name,
        environment=environment, tenant_id=tenant_id,
        prompt=parsed["prompt"], response_text=parsed["response"],
        start_ns=parsed["start_ns"], end_ns=parsed["end_ns"],
        input_tokens=parsed["input_tokens"], output_tokens=parsed["output_tokens"],
        total_tokens=parsed["total_tokens"], tokens_estimated=parsed["tokens_estimated"],
        session_id=session_id, user_id=parsed["user_id"],
        is_error=parsed["is_error"], error_msg=parsed["error_msg"],
        trace_id=trace_id,
        tool_calls=parsed.get("tool_calls") or [],
    )
    job_id = _post_to_wxo(payload, bearer_token, agent_id, tenant_id, export_url)
    logger.info(f"[HOOK] done — path=callback job_id={job_id} trace_id={trace_id}")
    return {"statusCode": 200, "trace_id": trace_id, "job_id": job_id, "path": "callback"}

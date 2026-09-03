"""wxO-aligned OpenTelemetry ingestion for a Google ADK A2A agent.

The module intentionally uses WXO_API_KEY (not API_KEY) so that the wxO
credential cannot overwrite GOOGLE_API_KEY used by the Gemini SDK.
"""

from __future__ import annotations

import atexit
import base64
import json
import os
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.trace import SpanKind, Status, StatusCode


_ERROR_STATES = {"failed", "failure", "rejected", "canceled", "cancelled"}
_MAX_CAPTURE_BYTES = 64 * 1024


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _jwt_expiry(token: str) -> float | None:
    """Read the unverified JWT exp claim only to schedule credential refresh."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))
        return float(decoded["exp"])
    except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _exchange_token() -> tuple[str, float]:
    from urllib.parse import urlencode
    payload = urlencode({
        "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
        "apikey": _required("WXO_API_KEY"),
    }).encode("utf-8")
    request = Request(
        _required("TOKEN_URL"),
        data=payload,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "external-agent-observability/2.0",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(
            f"wxO token exchange failed with HTTP {exc.code}: {detail}"
        ) from exc
    except URLError as exc:
        raise RuntimeError(f"wxO token exchange failed: {exc.reason}") from exc

    token = body.get("token") or body.get("access_token")
    if not token:
        raise RuntimeError("wxO token response did not contain token/access_token")

    now = time.time()
    expires_at = _jwt_expiry(str(token))
    if expires_at is None:
        expires_in = body.get("expires_in") or body.get("expiresIn") or 3000
        try:
            expires_at = now + float(expires_in)
        except (TypeError, ValueError):
            expires_at = now + 3000
    return str(token), expires_at


class RefreshingOTLPSpanExporter(SpanExporter):
    """Refresh the bearer token and rebuild the OTLP/HTTP exporter as needed."""

    def __init__(self, endpoint: str, tenant_id: str, agent_id: str) -> None:
        self._endpoint = endpoint
        self._tenant_id = tenant_id
        self._agent_id = agent_id
        self._delegate: OTLPSpanExporter | None = None
        self._expires_at = 0.0
        self._lock = threading.Lock()

    def _get_delegate(self) -> OTLPSpanExporter:
        with self._lock:
            if self._delegate is not None and time.time() < self._expires_at - 120:
                return self._delegate

            token, expires_at = _exchange_token()
            new_delegate = OTLPSpanExporter(
                endpoint=self._endpoint,
                headers={
                    "Authorization": f"Bearer {token}",
                    "x-ibm-tenant-id": self._tenant_id,
                    "x-ibm-agent-id": self._agent_id,
                    "x-langfuse-ingestion-version": "4",
                },
            )
            old_delegate = self._delegate
            self._delegate = new_delegate
            self._expires_at = expires_at
            if old_delegate is not None:
                old_delegate.shutdown()
            return new_delegate

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        return self._get_delegate().export(spans)

    def shutdown(self) -> None:
        with self._lock:
            if self._delegate is not None:
                self._delegate.shutdown()
                self._delegate = None

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        delegate = self._delegate
        if delegate is None:
            return True
        force_flush = getattr(delegate, "force_flush", None)
        return bool(force_flush(timeout_millis)) if force_flush else True


@dataclass(frozen=True)
class WxoSettings:
    tenant_id: str
    agent_id: str
    agent_name: str
    agent_display_name: str
    environment_name: str
    workspace_id: str | None
    capture_content: bool


def _settings() -> WxoSettings:
    environment = (os.getenv("ENVIRONMENT_NAME") or os.getenv("WXO_ENVIRONMENT_NAME") or "live").strip().lower()
    if environment not in {"live", "draft"}:
        raise RuntimeError("ENVIRONMENT_NAME must be 'live' or 'draft'")
    return WxoSettings(
        tenant_id=_required("WXO_TENANT_ID"),
        agent_id=_required("WXO_AGENT_ID"),
        agent_name=os.getenv(
            "WXO_AGENT_NAME", "external_order_support_agent"
        ).strip(),
        agent_display_name=os.getenv("WXO_AGENT_DISPLAY_NAME", "Google Agent").strip(),
        environment_name=environment,
        workspace_id=os.getenv("WXO_WORKSPACE_ID", "").strip() or None,
        capture_content=_bool_env("WXO_CAPTURE_CONTENT", True),
    )


_PROVIDER: TracerProvider | None = None
_SETTINGS: WxoSettings | None = None


def configure_wxo_telemetry() -> trace.Tracer:
    """Configure the global provider before importing Google ADK agent modules."""
    global _PROVIDER, _SETTINGS
    if _PROVIDER is not None:
        return trace.get_tracer("wxo-server", "2.0.0")

    settings = _settings()
    resource_attributes: dict[str, str] = {
        "service.name": os.getenv(
            "OTEL_SERVICE_NAME", "external-agent"
        ),
        "service.version": os.getenv("OTEL_SERVICE_VERSION", "2.0.0"),
        "tenant.id": settings.tenant_id,
        # Deliberately NOT setting agent.name/agent.display_name here: sending
        # both agent.id and agent.name (span- or resource-level) makes wxO's
        # ingestion derive langfuse.agent.id/langfuse.agent.name and classify
        # the trace as a known "agent" trace, which unconditionally wraps
        # output into a chat-message array — breaking the Trace View chat
        # bubble (confirmed by comparing captured trace JSON with/without
        # agent.name present). agent.id alone does not trigger this.
        "agent.id": settings.agent_id,
        "environment.name": settings.environment_name,
        # Retained for compatibility with the earlier integration guide.
        "deployment.environment": settings.environment_name,
    }
    if settings.workspace_id:
        resource_attributes["workspace.id"] = settings.workspace_id

    provider = TracerProvider(resource=Resource.create(resource_attributes))
    exporter = RefreshingOTLPSpanExporter(
        endpoint=_required("OTEL_EXPORT_URL"),
        tenant_id=settings.tenant_id,
        agent_id=settings.agent_id,
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _PROVIDER = provider
    _SETTINGS = settings
    atexit.register(provider.shutdown)
    return trace.get_tracer("wxo-server", "2.0.0")


def force_flush(timeout_millis: int = 30_000) -> bool:
    return bool(_PROVIDER and _PROVIDER.force_flush(timeout_millis))


def instrument_agent_invoke(
    agent: Any,
    inputs: dict[str, Any],
    config: dict[str, Any],
    ctx: Any,
) -> dict[str, Any]:
    """Run ``agent.invoke`` inside a restored OTel context and emit child spans.

    This function is intended to be called from a ``run_in_executor`` thread.
    It restores *ctx* (the OTel context captured on the async thread before
    entering the executor) so that every child span created here is properly
    parented to the root ``invoke_agent`` span.

    After the agent returns, it walks the final message list and emits:

    * One ``gen_ai.chat`` span per AI / LLM turn (with tool-call intent noted).
    * One ``tool_call`` span per ``ToolMessage`` (the actual tool execution).
    """
    tracer = trace.get_tracer("wxo-server", "2.0.0")

    token = otel_context.attach(ctx)
    try:
        # --- single child span that covers the full agent graph execution ---
        with tracer.start_as_current_span(
            "agent.graph",
            kind=SpanKind.INTERNAL,
        ) as graph_span:
            try:
                response = agent.invoke(inputs, config)
            except Exception as exc:
                graph_span.record_exception(exc)
                graph_span.set_status(Status(StatusCode.ERROR, str(exc)))
                raise

            # NOTE: deliberately NOT setting gen_ai.input.messages /
            # gen_ai.output.messages here (or on any child span below) — wxO's
            # ingestion derives the trace's chat output from those structured
            # message-array attributes wherever they appear in the trace, and
            # that derived value collides with the root span's plain-string
            # "output" attribute, rendering "[object Object]" in Trace View
            # (confirmed by isolated attribute-bisection testing). All other
            # gen_ai.* attributes (operation.name, system, model, usage.*) are
            # safe and are what populate the Model/token-count summary boxes.
            messages = response.get("messages", [])

        # --- walk messages and emit one child span per step ---
        _emit_message_spans(tracer, ctx, messages)
    finally:
        otel_context.detach(token)

    return response


def _emit_message_spans(
    tracer: trace.Tracer,
    ctx: Any,
    messages: list[Any],
) -> None:
    """Emit ``gen_ai.chat`` and ``tool_call`` child spans from the message list.

    Each span is created **after** the work is already done (we are post-hoc
    instrumenting the completed agent graph).  We assign a synthetic 1 ms
    offset per message index so wxO renders spans in execution order rather
    than sorting arbitrarily among spans with identical timestamps.
    """
    # Base timestamp in nanoseconds; each message step gets +1 ms.
    base_ns = time.time_ns()
    _NS_PER_MS = 1_000_000

    token = otel_context.attach(ctx)
    try:
        for idx, msg in enumerate(messages):
            cls_name = type(msg).__name__
            # Synthetic start/end: base + idx ms so spans sort in message order.
            span_start_ns = base_ns + idx * _NS_PER_MS
            span_end_ns   = span_start_ns + _NS_PER_MS

            # ── LLM / AI turn  (AIMessage or AIMessageChunk) ───────────────
            if cls_name in ("AIMessage", "AIMessageChunk"):
                tool_calls = getattr(msg, "tool_calls", None) or []
                span_name = (
                    "gen_ai.chat → " + ", ".join(
                        tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
                        for tc in tool_calls
                    )
                    if tool_calls
                    else "gen_ai.chat"
                )
                with tracer.start_as_current_span(
                    span_name,
                    kind=SpanKind.CLIENT,
                    start_time=span_start_ns,
                ) as span:
                    span.set_attribute("gen_ai.operation.name", "chat")
                    span.set_attribute("gen_ai.system", "google_gemini")

                    # ── model name ─────────────────────────────────────────
                    resp_meta = getattr(msg, "response_metadata", None) or {}
                    model_name = (
                        resp_meta.get("model_name")
                        or resp_meta.get("model")
                        or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
                    )
                    span.set_attribute("gen_ai.request.model", model_name)
                    span.set_attribute("gen_ai.response.model", model_name)

                    # ── token usage ────────────────────────────────────────
                    usage = getattr(msg, "usage_metadata", None) or {}
                    if not usage:
                        usage = resp_meta.get("usage_metadata") or {}
                    if usage:
                        input_tok = usage.get("input_tokens") or usage.get("prompt_tokens") or 0
                        output_tok = usage.get("output_tokens") or usage.get("completion_tokens") or 0
                        total_tok = usage.get("total_tokens") or (input_tok + output_tok)
                        if input_tok:
                            span.set_attribute("gen_ai.usage.input_tokens", int(input_tok))
                        if output_tok:
                            span.set_attribute("gen_ai.usage.output_tokens", int(output_tok))
                        if total_tok:
                            span.set_attribute("gen_ai.usage.total_tokens", int(total_tok))

                    # NOTE: no gen_ai.input.messages here — see comment in
                    # instrument_agent_invoke above.

                    # ── output / completion text ───────────────────────────
                    content = msg.content
                    if isinstance(content, list):
                        text = "".join(
                            b.get("text", "") if isinstance(b, dict) else str(b)
                            for b in content
                        )
                    else:
                        text = str(content or "")

                    # ── tool call intent (set before output so output can embed it) ──
                    if tool_calls:
                        tc_json = _json([
                            {
                                "name": tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", ""),
                                "args": tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {}),
                            }
                            for tc in tool_calls
                        ])
                        span.set_attribute("gen_ai.tool_calls", tc_json)
                        # Gemini emits content=[] when a tool call is the only output.
                        # Synthesise a readable output so the span is never blank.
                        if not text:
                            text = tc_json

                    if text:
                        span.set_attribute("gen_ai.completion", text[:4000])

            # ── Tool execution result ───────────────────────────────────────
            elif cls_name == "ToolMessage":
                tool_name = getattr(msg, "name", "") or "tool"
                with tracer.start_as_current_span(
                    f"tool_call {tool_name}",
                    kind=SpanKind.INTERNAL,
                    start_time=span_start_ns,
                ) as span:
                    span.set_attribute("gen_ai.operation.name", "tool_call")
                    span.set_attribute("tool.name", tool_name)
                    tool_content = msg.content
                    if isinstance(tool_content, (dict, list)):
                        tool_content_str = _json(tool_content)
                    else:
                        tool_content_str = str(tool_content or "")
                    span.set_attribute("tool.output", tool_content_str[:4000])
                    # NOTE: no gen_ai.input.messages / gen_ai.output.messages
                    # here — see comment in instrument_agent_invoke above.
                    # surface tool-level business failures on the span
                    try:
                        parsed = json.loads(tool_content_str)
                        failure = _find_business_failure(parsed)
                        if failure:
                            code, message = failure
                            span.set_attribute("tool.business_outcome", "failed")
                            span.set_attribute("tool.business_error.code", code)
                            span.set_attribute("tool.business_error.message", message[:1000])
                            span.set_status(Status(StatusCode.ERROR, message[:200]))
                        else:
                            span.set_attribute("tool.business_outcome", "success")
                    except (json.JSONDecodeError, TypeError):
                        pass
    finally:
        otel_context.detach(token)


def _header_map(scope: Mapping[str, Any]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for key, value in scope.get("headers", []):
        headers[key.decode("latin-1").lower()] = value.decode("latin-1")
    return headers


def _decode_json(body: bytes) -> dict[str, Any]:
    if not body:
        return {}
    try:
        parsed = json.loads(body.decode("utf-8"))
        return parsed if isinstance(parsed, dict) else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}


def _message_text(message: Any) -> str:
    if not isinstance(message, dict):
        return ""
    texts: list[str] = []
    for part in message.get("parts", []):
        if isinstance(part, dict) and isinstance(part.get("text"), str):
            texts.append(part["text"])
    return "\n".join(texts)


def _request_context(payload: dict[str, Any], headers: dict[str, str]) -> dict[str, str]:
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    message = params.get("message") if isinstance(params.get("message"), dict) else {}
    metadata = params.get("metadata") if isinstance(params.get("metadata"), dict) else {}
    thread_id = (
        params.get("contextId")
        or message.get("contextId")
        or metadata.get("thread_id")
        or metadata.get("session_id")
        or headers.get("x-wxo-thread-id")
        or ""
    )
    return {
        "message_id": str(message.get("messageId") or uuid.uuid4()),
        "thread_id": str(thread_id),
        "user_id": str(
            headers.get("x-wxo-user-id")
            or metadata.get("user_id")
            or metadata.get("userId")
            or "anonymous"
        ),
        "input": _message_text(message),
    }


def _response_text(payload: dict[str, Any]) -> str:
    result = payload.get("result")
    if not isinstance(result, dict):
        error = payload.get("error")
        return str(error.get("message", "")) if isinstance(error, dict) else ""

    # 1. Artifacts (primary path — server.py puts the answer here)
    for artifact in result.get("artifacts", []) or []:
        text = _message_text(artifact)
        if text:
            return text

    # 2. Status message
    status = result.get("status")
    if isinstance(status, dict):
        text = _message_text(status.get("message"))
        if text:
            return text

    # 3. History (last agent turn)
    for message in reversed(result.get("history", []) or []):
        if isinstance(message, dict) and message.get("role") == "agent":
            text = _message_text(message)
            if text:
                return text

    # 4. Fallback: scan every part in every artifact regardless of type key name
    #    (handles serialization_alias differences where "kind" becomes "type")
    for artifact in result.get("artifacts", []) or []:
        if not isinstance(artifact, dict):
            continue
        for part in artifact.get("parts", []) or []:
            if not isinstance(part, dict):
                continue
            # Accept both "text" key directly and nested under any type indicator
            t = part.get("text") or part.get("content")
            if isinstance(t, str) and t:
                return t

    print(f"wxO _response_text: could not extract output from result keys={list(result.keys())}")
    return ""


def _find_business_failure(value: Any) -> tuple[str, str] | None:
    if isinstance(value, dict):
        if value.get("success") is False:
            return (
                str(value.get("error_code") or "BUSINESS_FAILURE"),
                str(value.get("message") or "Tool reported an unsuccessful outcome"),
            )
        for child in value.values():
            found = _find_business_failure(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_business_failure(child)
            if found:
                return found
    return None


def _technical_failure(
    response: dict[str, Any], status_code: int
) -> tuple[str, str] | None:
    if status_code >= 400:
        return "HTTPError", f"HTTP response status {status_code}"
    rpc_error = response.get("error")
    if isinstance(rpc_error, dict):
        return str(rpc_error.get("code") or "JSONRPCError"), str(
            rpc_error.get("message") or rpc_error
        )
    result = response.get("result")
    if not isinstance(result, dict):
        return None
    status = result.get("status") if isinstance(result.get("status"), dict) else {}
    state = str(status.get("state", "")).lower()
    if state in _ERROR_STATES:
        return "AgentTaskError", f"A2A task ended in state '{state}'"

    status_message = status.get("message") if isinstance(status.get("message"), dict) else {}
    status_metadata = (
        status_message.get("metadata")
        if isinstance(status_message.get("metadata"), dict)
        else {}
    )
    result_metadata = (
        result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
    )
    error_code = (
        result_metadata.get("adk_error_code")
        or status_metadata.get("adk_error_code")
    )
    if error_code:
        return str(error_code), _message_text(status_message) or str(error_code)
    return None


class WxoA2ATraceMiddleware:
    """ASGI middleware that makes one root trace for each A2A message/send turn."""

    def __init__(self, app: Any) -> None:
        self.app = app
        self.tracer = configure_wxo_telemetry()
        if _SETTINGS is None:  # pragma: no cover - defensive
            raise RuntimeError("wxO telemetry was not configured")
        self.settings = _SETTINGS

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        request_messages: list[dict[str, Any]] = []
        request_body = bytearray()
        more_body = True
        while more_body:
            event = await receive()
            request_messages.append(event)
            if event.get("type") == "http.request":
                request_body.extend(event.get("body", b""))
                more_body = bool(event.get("more_body", False))
            else:
                more_body = False

        request_payload = _decode_json(bytes(request_body))
        headers = _header_map(scope)
        context = _request_context(request_payload, headers)
        replay_index = 0

        async def replay_receive() -> dict[str, Any]:
            nonlocal replay_index
            if replay_index < len(request_messages):
                event = request_messages[replay_index]
                replay_index += 1
                return event
            return {"type": "http.request", "body": b"", "more_body": False}

        response_body = bytearray()
        status_code = 500

        async def capture_send(event: dict[str, Any]) -> None:
            nonlocal status_code
            if event.get("type") == "http.response.start":
                status_code = int(event.get("status", 500))
            elif event.get("type") == "http.response.body":
                chunk = event.get("body", b"")
                if len(response_body) < _MAX_CAPTURE_BYTES:
                    response_body.extend(chunk[: _MAX_CAPTURE_BYTES - len(response_body)])
            await send(event)

        span_name = f"invoke_agent {self.settings.agent_name}"
        with self.tracer.start_as_current_span(span_name, kind=SpanKind.SERVER) as span:
            trace_id = f"{span.get_span_context().trace_id:032x}"
            execution_status = "unknown"
            span.set_attribute("agent.id", self.settings.agent_id)
            # Deliberately NOT setting agent.name/agent.display_name (see comment
            # in configure_wxo_telemetry) or gen_ai.operation.name/gen_ai.agent.* here:
            # those classify this root span as an AGENT-type observation in wxO's
            # ingestion, which unconditionally wraps its output into a chat-message
            # array ([{"role":"assistant","content":...}]) even when we send a
            # plain string — breaking the Trace View chat-bubble renderer (Preview
            # UI bug, confirmed by comparing captured trace JSON with/without these
            # attributes). Keeping the root span a plain SPAN preserves scalar
            # input/output while child gen_ai.chat/tool_call spans still carry
            # full GenAI semantics for per-turn analytics.
            span.set_attribute("environment.name", self.settings.environment_name)
            span.set_attribute("message.id", context["message_id"])
            span.set_attribute("langfuse.user.id", context["user_id"])
            span.set_attribute("http.request.method", str(scope.get("method", "")))
            span.set_attribute("url.path", str(scope.get("path", "")))
            if context["thread_id"]:
                span.set_attribute("thread.id", context["thread_id"])
                span.set_attribute("langfuse.session.id", context["thread_id"])
                span.set_attribute("conversation.id", context["thread_id"])
            if self.settings.capture_content:
                # Literal "input" (not gen_ai.input.value) — passes through as a
                # scalar untouched, which is what the Trace View chat bubble needs.
                span.set_attribute("input", context["input"])

            try:
                await self.app(scope, replay_receive, capture_send)
            except Exception as exc:
                execution_status = "error"
                span.record_exception(exc)
                span.set_attribute("agent.execution.status", "error")
                span.set_attribute("error.type", type(exc).__name__)
                span.set_attribute("error.message", str(exc))
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                raise
            finally:
                response_payload = _decode_json(bytes(response_body))
                result = response_payload.get("result")
                response_thread = (
                    result.get("contextId") if isinstance(result, dict) else None
                )
                thread_id = context["thread_id"] or str(response_thread or uuid.uuid4())
                span.set_attribute("thread.id", thread_id)
                span.set_attribute("langfuse.session.id", thread_id)
                span.set_attribute("conversation.id", thread_id)
                span.set_attribute("http.response.status_code", status_code)

                output = _response_text(response_payload)
                if self.settings.capture_content and output:
                    # Literal "output" (not gen_ai.output.value) — see comment above
                    # the "input" attribute for why.
                    span.set_attribute("output", output)

                failure = _technical_failure(response_payload, status_code)
                if failure:
                    error_type, error_message = failure
                    execution_status = "error"
                    span.set_attribute("agent.execution.status", "error")
                    span.set_attribute("error.type", error_type)
                    span.set_attribute("error.message", error_message[:4000])
                    span.set_status(Status(StatusCode.ERROR, error_message[:1000]))
                elif span.status.status_code is not StatusCode.ERROR:
                    execution_status = "success"
                    span.set_attribute("agent.execution.status", "success")
                    business_failure = _find_business_failure(response_payload)
                    if business_failure:
                        code, message = business_failure
                        span.set_attribute("agent.business_outcome", "failed")
                        span.set_attribute("agent.business_error.code", code)
                        span.set_attribute("agent.business_error.message", message[:4000])
                    else:
                        span.set_attribute("agent.business_outcome", "success")

                print(
                    "wxO trace queued "
                    f"trace_id={trace_id} thread_id={thread_id} "
                    f"status={execution_status}"
                )

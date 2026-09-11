"""
A2A v0.3.0 Server — Annualized Rate of Return Agent
Implements the Agent-to-Agent Protocol (JSON-RPC 2.0 over HTTP) with:
  - POST /  → message/send, tasks/get, tasks/cancel
  - GET  /.well-known/agent.json  → AgentCard discovery
  - GET  /health → liveness probe for Code Engine
  - SSE streaming via POST / when configuration.blocking=false
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from a2a_types import (
    A2AErrorCode,
    AgentCapabilities,
    AgentCard,
    AgentProvider,
    AgentSkill,
    Artifact,
    DataPart,
    JSONRPCError,
    JSONRPCRequest,
    JSONRPCResponse,
    Message,
    MessageSendParams,
    Part,
    SecurityScheme,
    Task,
    TaskArtifactUpdateEvent,
    TaskCancelParams,
    TaskQueryParams,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    TextPart,
)
from agent import create_react_agent, format_response
from wxo_otel import WxoA2ATraceMiddleware

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("a2a-server")

# ---------------------------------------------------------------------------
# In-memory task store (replace with Redis/DB for production scale-out)
# ---------------------------------------------------------------------------
_tasks: dict[str, Task] = {}

# LangGraph agent singleton
_agent = None


def get_agent():
    global _agent
    if _agent is None:
        _agent = create_react_agent()
    return _agent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_text(msg: Message) -> str:
    """Concatenate all TextParts from an A2A Message into a plain string."""
    return " ".join(
        part.text for part in msg.parts if isinstance(part, TextPart)
    )


def _build_text_message(text: str, task_id: str, context_id: str) -> Message:
    return Message(
        kind="message",
        role="agent",
        parts=[TextPart(kind="text", text=text)],
        messageId=str(uuid.uuid4()),
        taskId=task_id,
        contextId=context_id,
    )


def _ok(request_id: Any, result: Any) -> JSONRPCResponse:
    return JSONRPCResponse(jsonrpc="2.0", id=request_id, result=result)


def _err(request_id: Any, code: int, message: str, data: Any = None) -> JSONRPCResponse:
    return JSONRPCResponse(
        jsonrpc="2.0",
        id=request_id,
        error=JSONRPCError(code=code, message=message, data=data),
    )


# ---------------------------------------------------------------------------
# Core A2A handler — runs the LangGraph agent for a given user text
# ---------------------------------------------------------------------------

async def _run_agent(user_text: str, thread_id: str) -> str:
    """Invoke the LangGraph agent and return the final text response."""
    from langchain_core.messages import HumanMessage
    from opentelemetry import context as otel_context
    from wxo_otel import instrument_agent_invoke

    agent = get_agent()
    config = {"configurable": {"thread_id": thread_id}}

    # Capture the current OTel context so the root span remains the parent
    # when the synchronous agent.invoke() runs inside a thread-pool executor.
    ctx = otel_context.get_current()
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: instrument_agent_invoke(
            agent,
            {"messages": [HumanMessage(content=user_text)]},
            config,
            ctx,
        ),
    )
    return format_response(response)


# ---------------------------------------------------------------------------
# A2A method implementations
# ---------------------------------------------------------------------------

async def handle_message_send(params: dict[str, Any], request_id: Any) -> JSONRPCResponse:
    """Handles message/send — spec §5.2."""
    try:
        send_params = MessageSendParams(**params)
    except Exception as exc:
        return _err(request_id, A2AErrorCode.INVALID_PARAMS, f"Invalid params: {exc}")

    msg = send_params.message
    task_id = msg.taskId or str(uuid.uuid4())
    context_id = msg.contextId or str(uuid.uuid4())
    user_text = _extract_text(msg)

    if not user_text.strip():
        return _err(
            request_id,
            A2AErrorCode.INVALID_PARAMS,
            "Message contains no text content.",
        )

    # Create task in SUBMITTED state
    task = Task(
        id=task_id,
        contextId=context_id,
        status=TaskStatus(
            state=TaskState.SUBMITTED,
            timestamp=_now_iso(),
        ),
    )
    _tasks[task_id] = task

    try:
        # Update to WORKING
        _tasks[task_id].status = TaskStatus(
            state=TaskState.WORKING,
            timestamp=_now_iso(),
        )

        answer = await _run_agent(user_text, thread_id=context_id)

        # Build result artifact
        artifact = Artifact(
            artifactId=str(uuid.uuid4()),
            name="annualized-return-result",
            parts=[TextPart(kind="text", text=answer)],
            index=0,
            lastChunk=True,
        )

        agent_message = _build_text_message(answer, task_id, context_id)

        # Update task to COMPLETED
        _tasks[task_id].status = TaskStatus(
            state=TaskState.COMPLETED,
            message=agent_message,
            timestamp=_now_iso(),
        )
        _tasks[task_id].artifacts = [artifact]

    except Exception as exc:
        logger.exception("Agent execution failed for task %s", task_id)
        _tasks[task_id].status = TaskStatus(
            state=TaskState.FAILED,
            timestamp=_now_iso(),
        )
        return _err(
            request_id,
            A2AErrorCode.INTERNAL_ERROR,
            f"Agent execution failed: {exc}",
        )

    return _ok(request_id, _tasks[task_id].model_dump(by_alias=True))


async def handle_message_stream(
    params: dict[str, Any], request_id: Any
) -> AsyncIterator[str]:
    """Handles message/stream — streams SSE events for A2A streaming mode."""
    try:
        send_params = MessageSendParams(**params)
    except Exception as exc:
        err_resp = _err(request_id, A2AErrorCode.INVALID_PARAMS, str(exc))
        yield f"data: {err_resp.model_dump_json()}\n\n"
        return

    msg = send_params.message
    task_id = msg.taskId or str(uuid.uuid4())
    context_id = msg.contextId or str(uuid.uuid4())
    user_text = _extract_text(msg)

    task = Task(
        id=task_id,
        contextId=context_id,
        status=TaskStatus(state=TaskState.SUBMITTED, timestamp=_now_iso()),
    )
    _tasks[task_id] = task

    # --- submitted event ---
    submitted_evt = TaskStatusUpdateEvent(
        taskId=task_id,
        contextId=context_id,
        status=TaskStatus(state=TaskState.SUBMITTED, timestamp=_now_iso()),
        final=False,
    )
    yield f"data: {submitted_evt.model_dump_json(by_alias=True)}\n\n"

    # --- working event ---
    _tasks[task_id].status = TaskStatus(state=TaskState.WORKING, timestamp=_now_iso())
    working_evt = TaskStatusUpdateEvent(
        taskId=task_id,
        contextId=context_id,
        status=_tasks[task_id].status,
        final=False,
    )
    yield f"data: {working_evt.model_dump_json(by_alias=True)}\n\n"

    try:
        answer = await _run_agent(user_text, thread_id=context_id)

        artifact = Artifact(
            artifactId=str(uuid.uuid4()),
            name="annualized-return-result",
            parts=[TextPart(kind="text", text=answer)],
            index=0,
            lastChunk=True,
        )
        _tasks[task_id].artifacts = [artifact]

        artifact_evt = TaskArtifactUpdateEvent(
            taskId=task_id,
            contextId=context_id,
            artifact=artifact,
        )
        yield f"data: {artifact_evt.model_dump_json(by_alias=True)}\n\n"

        agent_message = _build_text_message(answer, task_id, context_id)
        _tasks[task_id].status = TaskStatus(
            state=TaskState.COMPLETED,
            message=agent_message,
            timestamp=_now_iso(),
        )
        completed_evt = TaskStatusUpdateEvent(
            taskId=task_id,
            contextId=context_id,
            status=_tasks[task_id].status,
            final=True,
        )
        yield f"data: {completed_evt.model_dump_json(by_alias=True)}\n\n"

    except Exception as exc:
        logger.exception("Streaming agent execution failed for task %s", task_id)
        _tasks[task_id].status = TaskStatus(
            state=TaskState.FAILED, timestamp=_now_iso()
        )
        failed_evt = TaskStatusUpdateEvent(
            taskId=task_id,
            contextId=context_id,
            status=_tasks[task_id].status,
            final=True,
        )
        yield f"data: {failed_evt.model_dump_json(by_alias=True)}\n\n"


async def handle_tasks_get(params: dict[str, Any], request_id: Any) -> JSONRPCResponse:
    """Handles tasks/get — spec §5.4."""
    try:
        query = TaskQueryParams(**params)
    except Exception as exc:
        return _err(request_id, A2AErrorCode.INVALID_PARAMS, str(exc))

    task = _tasks.get(query.id)
    if task is None:
        return _err(request_id, A2AErrorCode.TASK_NOT_FOUND, f"Task {query.id!r} not found.")
    return _ok(request_id, task.model_dump(by_alias=True))


async def handle_tasks_cancel(params: dict[str, Any], request_id: Any) -> JSONRPCResponse:
    """Handles tasks/cancel — spec §5.5."""
    try:
        cancel = TaskCancelParams(**params)
    except Exception as exc:
        return _err(request_id, A2AErrorCode.INVALID_PARAMS, str(exc))

    task = _tasks.get(cancel.id)
    if task is None:
        return _err(request_id, A2AErrorCode.TASK_NOT_FOUND, f"Task {cancel.id!r} not found.")

    terminal = {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELED}
    if task.status.state in terminal:
        return _err(
            request_id,
            A2AErrorCode.TASK_NOT_CANCELABLE,
            f"Task {cancel.id!r} is already in terminal state {task.status.state}.",
        )

    _tasks[cancel.id].status = TaskStatus(
        state=TaskState.CANCELED, timestamp=_now_iso()
    )
    return _ok(request_id, _tasks[cancel.id].model_dump(by_alias=True))


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting A2A server — pre-loading LangGraph agent…")
    get_agent()
    logger.info("Agent ready.")
    yield
    logger.info("Shutting down A2A server.")


app = FastAPI(
    title="Annualized Rate of Return A2A Agent",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# WxoA2ATraceMiddleware wraps every A2A request in a root OTel span and
# ships the trace batch to the wxO ingestion endpoint.  It reads all
# required settings from environment variables (WXO_API_KEY, WXO_TENANT_ID,
# WXO_AGENT_ID, TOKEN_URL, OTEL_EXPORT_URL).  ASGI middleware is added in
# reverse order, so this runs outermost — around CORS and all business logic.
app.add_middleware(WxoA2ATraceMiddleware)


# ---------------------------------------------------------------------------
# AgentCard endpoint  — A2A spec §4 requires GET /.well-known/agent.json
# ---------------------------------------------------------------------------

def _build_agent_card() -> AgentCard:
    base_url = os.getenv("AGENT_BASE_URL", "http://localhost:8080")
    api_key_configured = bool(os.getenv("AGENT_API_KEY"))

    return AgentCard(
        protocolVersion="0.3.0",
        name="annualized-return-agent",
        description=(
            "A LangGraph-based AI agent that calculates the annualized rate of return "
            "for investments. Provide an initial investment amount, current value, and "
            "duration in months to get the annualized and total return percentages."
        ),
        url=base_url,
        provider=AgentProvider(
            organization="IBM watsonx Orchestrate Demo",
            url="https://www.ibm.com/products/watsonx-orchestrate",
        ),
        version="1.0.0",
        documentationUrl=f"{base_url}/docs",
        capabilities=AgentCapabilities(
            streaming=True,
            pushNotifications=False,
            stateTransitionHistory=True,
        ),
        securitySchemes={
            "bearerAuth": SecurityScheme(
                type="bearer",
                description="Bearer token authentication. Set AGENT_API_KEY env var to enable.",
            )
        } if api_key_configured else None,
        security=[{"bearerAuth": []}] if api_key_configured else None,
        defaultInputModes=["text"],
        defaultOutputModes=["text"],
        skills=[
            AgentSkill(
                id="calculate-annualized-return",
                name="Calculate Annualized Rate of Return",
                description=(
                    "Calculates the annualized rate of return given an initial investment, "
                    "current value, and the number of months invested."
                ),
                inputModes=["text"],
                outputModes=["text"],
                tags=["finance", "investment", "returns"],
                examples=[
                    "I invested $10,000 and it's now worth $12,500 after 18 months. What's my annualized return?",
                    "Calculate the annualized return for $5,000 initial, $7,200 current, over 24 months.",
                ],
            )
        ],
    )


@app.get("/.well-known/agent.json", response_model=AgentCard, tags=["Discovery"])
@app.get("/.well-known/agent-card.json", response_model=AgentCard, tags=["Discovery"])
async def agent_card():
    """AgentCard discovery endpoint — served at both filenames for compatibility.
    A2A spec §4 uses agent.json; wxO ADK discover uses agent-card.json.
    """
    return _build_agent_card()


# ---------------------------------------------------------------------------
# Health / liveness probe (Code Engine requires this)
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Operations"])
async def health():
    return {"status": "ok", "protocol": "A2A", "version": "0.3.0"}


# ---------------------------------------------------------------------------
# Main A2A JSON-RPC 2.0 endpoint
# ---------------------------------------------------------------------------

METHOD_HANDLERS = {
    "message/send": handle_message_send,
    "tasks/get": handle_tasks_get,
    "tasks/cancel": handle_tasks_cancel,
}

STREAM_METHODS = {"message/stream"}


def _verify_api_key(request: Request) -> bool:
    """Optional bearer-token gate. Disabled when AGENT_API_KEY is not set."""
    api_key = os.getenv("AGENT_API_KEY")
    if not api_key:
        return True  # auth disabled
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.removeprefix("Bearer ").strip() == api_key
    return False


@app.post("/", tags=["A2A"])
async def jsonrpc_endpoint(request: Request):
    """
    A2A JSON-RPC 2.0 dispatch endpoint.
    Supports: message/send, message/stream, tasks/get, tasks/cancel
    """
    if not _verify_api_key(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        body = await request.json()
    except Exception:
        resp = _err(None, A2AErrorCode.PARSE_ERROR, "Invalid JSON body.")
        return JSONResponse(resp.model_dump(), status_code=400)

    # Handle batch (array) requests — return error per spec
    if isinstance(body, list):
        resp = _err(None, A2AErrorCode.INVALID_REQUEST, "Batch requests are not supported.")
        return JSONResponse(resp.model_dump(), status_code=400)

    try:
        rpc = JSONRPCRequest(**body)
    except Exception as exc:
        resp = _err(body.get("id") if isinstance(body, dict) else None,
                    A2AErrorCode.INVALID_REQUEST, str(exc))
        return JSONResponse(resp.model_dump(), status_code=400)

    logger.info("RPC id=%s method=%s", rpc.id, rpc.method)
    params = rpc.params or {}

    # Streaming method
    if rpc.method in STREAM_METHODS:
        return StreamingResponse(
            handle_message_stream(params, rpc.id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # Non-streaming method
    handler = METHOD_HANDLERS.get(rpc.method)
    if handler is None:
        resp = _err(rpc.id, A2AErrorCode.METHOD_NOT_FOUND, f"Method {rpc.method!r} not found.")
        return JSONResponse(resp.model_dump(), status_code=404)

    result = await handler(params, rpc.id)
    status_code = 200 if result.error is None else 400
    return JSONResponse(result.model_dump(), status_code=status_code)

"""
IT Provisioning Agent - Production-ready for watsonx Orchestrate

Exposes:
- /health
- /.well-known/agent-card.json
- /a2a  (JSON-RPC one-shot; action: provision_account)
- /v1/chat/completions (OpenAI Chat Completions-compatible; streaming JSON chunks)

Behavior:
- Accepts the HR output (Employee object), provisions directory user, groups, hardware.
"""

import asyncio
import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import Body, FastAPI, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr

app = FastAPI(title="IT Provisioning Agent")

# ==================== Models ====================
class Employee(BaseModel):
    employeeId: str
    fullName: str
    email: EmailStr
    jobTitle: str
    department: str
    location: str
    startDate: str
    groups: List[str]
    hardwareProfile: str


class ProvisionResult(BaseModel):
    directoryUserId: str
    provisioningTicketId: str
    hardwareRequestId: str
    status: str


# ==================== Business Logic ====================
async def create_directory_user(emp: Employee) -> str:
    await asyncio.sleep(0.05)
    return "dir-" + uuid.uuid4().hex[:10]


async def assign_groups(user_id: str, groups: List[str]) -> str:
    await asyncio.sleep(0.05)
    return "prov-" + uuid.uuid4().hex[:10]


async def request_hardware(emp: Employee) -> str:
    await asyncio.sleep(0.05)
    return "hw-" + uuid.uuid4().hex[:10]


async def provision_account(emp: Employee) -> ProvisionResult:
    if not emp.groups:
        raise ValueError("groups cannot be empty")
    user_id = await create_directory_user(emp)
    ticket_id = await assign_groups(user_id, emp.groups)
    hardware_id = await request_hardware(emp)
    return ProvisionResult(
        directoryUserId=user_id,
        provisioningTicketId=ticket_id,
        hardwareRequestId=hardware_id,
        status="success",
    )


# ==================== Helpers ====================
def ensure_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {"input": value}
        if isinstance(parsed, dict):
            return parsed
        return {"input": parsed}
    return {"input": value}


def extract_employee(payload: Any) -> Dict[str, Any]:
    payload = ensure_dict(payload)
    required = [
        "employeeId", "fullName", "email", "jobTitle", "department",
        "location", "startDate", "groups", "hardwareProfile",
    ]
    if sum(1 for f in required if f in payload) >= 7:
        return payload

    for _ in range(3):
        if "message" in payload and isinstance(payload["message"], dict):
            payload = ensure_dict(payload["message"])
            continue
        if payload.get("kind") == "message" and isinstance(payload.get("parts"), list):
            for part in payload["parts"]:
                if isinstance(part, dict):
                    for key in ["content", "data", "text", "input"]:
                        if key in part:
                            cand = ensure_dict(part[key])
                            if sum(1 for f in required if f in cand) >= 7:
                                return cand
        break

    missing = [f for f in required if f not in payload]
    raise ValueError(f"Missing required fields: {missing}")


def build_agent_card(base_url: str) -> Dict[str, Any]:
    return {
        "name": "ITProvisioningAgent",
        "version": "1.0.1",
        "protocolVersion": "0.2.1",
        "url": f"{base_url.rstrip('/')}/a2a",
        "description": "Creates directory users, assigns groups, and requests hardware.",
        "actions": [
            {
                "name": "provision_account",
                "title": "Provision directory user, groups, and hardware",
            }
        ],
    }


# ==================== Health / Discovery ====================
@app.get("/health")
def health():
    return {"status": "ok"}


@app.head("/health")
def health_head():
    return Response(status_code=200)


@app.get("/.well-known/agent-card.json")
@app.get("/.well-known/agent.json")
def agent_card(request: Request):
    return build_agent_card(str(request.base_url))


@app.get("/a2a/manifest")
def a2a_manifest():
    return {"protocol": "A2A/0.2.1", "actions": ["provision_account"]}


# ==================== A2A JSON-RPC ====================
def _norm_method(raw: str) -> str:
    m = ((raw or "").strip().lower().replace("::", "/").replace(".", "/").replace(" ", ""))
    return m[:-7] if m.endswith("/stream") else m


@app.post("/a2a")
@app.post("/")
async def a2a_endpoint(body: Dict[str, Any] = Body(...), request: Request = None):
    correlation_id = None
    try:
        correlation_id = (
            (body.get("params") or {}).get("correlationId")
            or body.get("correlationId")
            or (body.get("params") or {}).get("id")
        )
    except AttributeError:
        correlation_id = None

    if "method" not in body:
        return {"jsonrpc": "2.0", "id": body.get("id"),
                "error": {"code": -32600, "message": "Missing 'method'"},
                "result": {"correlationId": correlation_id}}

    jsonrpc_id = body.get("id")
    method = _norm_method(body.get("method"))
    params = ensure_dict(body.get("params") or {})

    if any(t in method for t in ["getcard", "card", "discovery"]):
        return {"jsonrpc": "2.0", "id": jsonrpc_id, "result": build_agent_card(str(request.base_url))}

    if any(t in method for t in ["actions/execute", "action/execute", "a2a/execute", "message/send",
                                 "messages/send", "invoke", "execute", "provision"]):
        payload = (params.get("input") or params.get("payload") or params.get("data") or params)
        try:
            emp = extract_employee(payload)
            res = await provision_account(Employee(**emp))
            return {"jsonrpc": "2.0", "id": jsonrpc_id,
                    "result": {"action": "provision_account", "status": "ok",
                               "output": res.dict(), "correlationId": correlation_id}}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": jsonrpc_id,
                    "error": {"code": -32001, "message": str(e)},
                    "result": {"correlationId": correlation_id}}

    return {"jsonrpc": "2.0", "id": jsonrpc_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
            "result": {"correlationId": correlation_id}}


# ==================== OpenAI Chat Completions (SSE streaming) ====================
@app.post("/v1/chat/completions")
async def chat_completions(payload: Dict[str, Any] = Body(...), request: Request = None):
    model = payload.get("model", "it-agent")
    wants_stream = bool(payload.get("stream")) or ("text/event-stream" in (request.headers.get("accept", "").lower() if request else ""))

    messages = payload.get("messages") or []
    if isinstance(messages, str):
        try:
            messages = json.loads(messages)
        except json.JSONDecodeError:
            messages = []

    user_msgs = [m for m in messages if m.get("role") == "user"]
    content = (user_msgs[-1]["content"] if user_msgs else "") or {}

    def _slice_json(s: str) -> Optional[str]:
        i, j = s.find("{"), s.rfind("}")
        return s[i : j + 1] if (i != -1 and j != -1 and j > i) else None

    if isinstance(content, dict):
        data = content
    elif isinstance(content, str):
        s = content.strip()
        if not (s.startswith("{") and s.endswith("}")):
            maybe = _slice_json(s)
            if maybe:
                s = maybe
        try:
            data = json.loads(s) if s.startswith("{") else {"_free_text": s}
        except json.JSONDecodeError:
            data = {"_free_text": s}
    else:
        s = str(content)
        maybe = _slice_json(s)
        if maybe:
            try:
                data = json.loads(maybe)
            except json.JSONDecodeError:
                data = {"_free_text": s}
        else:
            data = {"_free_text": s}

    async def work() -> str:
        try:
            emp = extract_employee(data)
            res = await provision_account(Employee(**emp))
            return json.dumps(res.dict())
        except Exception as e:
            return f"Error: {str(e)}"

    if wants_stream:
        chunk_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        created = int(time.time())
        chunk_size = 80

        async def gen():
            # 0) Role chunk immediately
            role_chunk = {
                "id": chunk_id, "object": "chat.completion.chunk", "created": created, "model": model,
                "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
            }
            yield f"data: {json.dumps(role_chunk)}\n\n"
            await asyncio.sleep(0)

            # 1) Work after first bytes
            result_text = await work()

            # 2) Content chunks
            for i in range(0, len(result_text), chunk_size):
                part = result_text[i:i+chunk_size]
                content_chunk = {
                    "id": chunk_id, "object": "chat.completion.chunk", "created": created, "model": model,
                    "choices": [{"index": 0, "delta": {"content": part}, "finish_reason": None}],
                }
                yield f"data: {json.dumps(content_chunk)}\n\n"
                await asyncio.sleep(0)

            # 3) Stop
            stop_chunk = {
                "id": chunk_id, "object": "chat.completion.chunk", "created": created, "model": model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            }
            yield f"data: {json.dumps(stop_chunk)}\n\n"
            yield "data: [DONE]\n\n"

        headers = {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
        return StreamingResponse(gen(), headers=headers)

    # Non-streaming fallback
    final_text = await work()
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": final_text}, "finish_reason": "stop"}],
    }


# ==================== Entrypoint ====================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8080"))
    print(f"Starting IT Agent on port {port}")
    uvicorn.run("main_it:app", host="0.0.0.0", port=port, log_level="info")

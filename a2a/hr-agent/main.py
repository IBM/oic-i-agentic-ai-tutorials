"""
HR Agent - Production-ready for watsonx Orchestrate (A2A + OpenAI Chat)

Exposes:
- /health
- /.well-known/agent-card.json
- /a2a  (JSON-RPC one-shot; actions: validate_new_hire, validate_and_provision)
- /v1/chat/completions (OpenAI Chat Completions-compatible; streaming JSON chunks)

Behavior:
- validate_new_hire: validates & normalizes new-hire data and returns NewHireOut.
- validate_and_provision: validates new hire, then calls IT /v1/chat/completions with the HR JSON,
  and returns: {"hr": <NewHireOut>, "it": <ProvisionResult>}.
"""

import asyncio
import json
import os
import re
import time
import uuid
from datetime import date
from typing import Any, Dict, List, Optional

import httpx
from fastapi import Body, FastAPI, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, Field

app = FastAPI(title="HR Agent")

# ==================== Models ====================
class NewHireIn(BaseModel):
    firstName: str = Field(min_length=1)
    lastName: str = Field(min_length=1)
    email: EmailStr
    role: str
    department: str
    location: str
    startDate: str  # ISO yyyy-mm-dd


class NewHireOut(BaseModel):
    employeeId: str
    fullName: str
    email: EmailStr
    jobTitle: str
    department: str
    location: str
    startDate: str
    manager: str
    groups: List[str]
    hardwareProfile: str


# ==================== Business Logic ====================
ROLE_TO_GROUPS = {
    "Data Analyst": ["grp-analytics-read", "grp-bi-tools"],
    "Software Engineer": ["grp-dev", "grp-ci"],
    "Sales Associate": ["grp-crm", "grp-proposal"],
}
DEPT_TO_MANAGER = {
    "Analytics": "laura.nguyen@company.com",
    "Engineering": "andrew.miller@company.com",
    "Sales": "maria.rojas@company.com",
}
LOCATION_TO_HW = {
    "London": "laptop-14in-16gb",
    "Madrid": "laptop-14in-16gb",
    "Dubai": "laptop-15in-32gb",
}


def normalize_role(role: str) -> str:
    return re.sub(r"\s+", " ", role.strip()).title()


def validate_new_hire(payload: NewHireIn) -> NewHireOut:
    try:
        _ = date.fromisoformat(payload.startDate)
    except ValueError as e:
        raise ValueError("startDate must be ISO yyyy-mm-dd format") from e

    role_norm = normalize_role(payload.role)
    groups = ROLE_TO_GROUPS.get(role_norm, ["grp-basic"])
    manager = DEPT_TO_MANAGER.get(payload.department, "hr@company.com")
    hardware = LOCATION_TO_HW.get(payload.location, "laptop-14in-16gb")
    employee_id = "E-" + uuid.uuid4().hex[:8].upper()

    return NewHireOut(
        employeeId=employee_id,
        fullName=f"{payload.firstName.strip()} {payload.lastName.strip()}",
        email=payload.email,
        jobTitle=role_norm,
        department=payload.department,
        location=payload.location,
        startDate=payload.startDate,
        manager=manager,
        groups=groups,
        hardwareProfile=hardware,
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


EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def _pick_from_known(text: str, choices: List[str]) -> Optional[str]:
    for c in choices:
        if re.search(rf"\b{re.escape(c)}\b", text, re.I):
            return c
    return None


def parse_free_text_to_new_hire(text: str) -> Optional[Dict[str, Any]]:
    if not isinstance(text, str) or not text.strip():
        return None
    t = " ".join(text.strip().split())

    email_m = EMAIL_RE.search(t)
    email = email_m.group(0) if email_m else None
    date_m = DATE_RE.search(t)
    start_date = date_m.group(1) if date_m else None
    role = _pick_from_known(t, list(ROLE_TO_GROUPS.keys()))
    department = _pick_from_known(t, list(DEPT_TO_MANAGER.keys()))
    location = _pick_from_known(t, list(LOCATION_TO_HW.keys()))

    name = None
    m = re.search(r":\s*([A-Z][a-zA-Z\-']+)\s+([A-Z][a-zA-Z\-']+)\b", t)
    if not m and email_m:
        prefix = t[: email_m.start()].strip().strip(",")
        tokens = [w for w in re.split(r"[,\s]+", prefix) if w]
        if len(tokens) >= 2 and tokens[-2][0].isalpha() and tokens[-1][0].isalpha():
            name = (tokens[-2], tokens[-1])
    else:
        if m:
            name = (m.group(1), m.group(2))

    if all([email, start_date, role, department, location, name]):
        first, last = name
        return {
            "firstName": first,
            "lastName": last,
            "email": email,
            "role": role,
            "department": department,
            "location": location,
            "startDate": start_date,
        }
    return None


def extract_data_from_payload(payload: Any) -> Dict[str, Any]:
    payload = ensure_dict(payload)
    required = ["firstName", "lastName", "email", "role", "department", "location", "startDate"]
    if sum(1 for f in required if f in payload) >= 6:
        return payload

    for _ in range(5):
        if "message" in payload and isinstance(payload["message"], dict):
            payload = ensure_dict(payload["message"])
            continue
        if payload.get("kind") == "message" and isinstance(payload.get("parts"), list):
            for part in payload["parts"]:
                if isinstance(part, dict):
                    if any(k in part for k in ["firstName", "lastName", "email"]):
                        return part
                    for key in ["text", "content", "data", "input"]:
                        if key in part:
                            val = part[key]
                            if isinstance(val, str):
                                parsed = parse_free_text_to_new_hire(val)
                                if parsed:
                                    return parsed
                                try:
                                    j = json.loads(val)
                                except json.JSONDecodeError:
                                    j = None
                                if isinstance(j, dict) and sum(1 for f in required if f in j) >= 6:
                                    return j
                            elif isinstance(val, dict) and sum(1 for f in required if f in val) >= 6:
                                return val
        break

    missing = [f for f in required if f not in payload]
    raise ValueError(f"Missing required fields: {missing}")


def build_agent_card(base_url: str) -> Dict[str, Any]:
    return {
        "name": "HRAgent",
        "version": "1.1.1",
        "protocolVersion": "0.2.1",
        "url": f"{base_url.rstrip('/')}/a2a",
        "description": "Validates new-hire data. Also supports validate_and_provision to cascade IT provisioning.",
        "actions": [
            {
                "name": "validate_new_hire",
                "title": "Validate new hire",
            },
            {
                "name": "validate_and_provision",
                "title": "Validate new hire and provision account",
            },
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
    return {"protocol": "A2A/0.2.1", "actions": ["validate_new_hire", "validate_and_provision"]}


# ==================== IT downstream (OpenAI Chat) ====================
IT_API_URL = os.getenv(
    "IT_API_URL",
    "https://it-agent.20xtogjmfdje.us-south.codeengine.appdomain.cloud/v1/chat/completions",
)
IT_MODEL = os.getenv("IT_MODEL", "it-agent")


async def call_it_provision(hr_out: NewHireOut) -> Dict[str, Any]:
    payload = {
        "model": IT_MODEL,
        "stream": False,
        "messages": [{"role": "user", "content": json.dumps(hr_out.model_dump())}],
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(IT_API_URL, json=payload, headers={"content-type": "application/json"})
    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise ValueError(f"IT call HTTP error: {e.response.status_code} {e.response.text}") from e

    try:
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
    except Exception as e:
        raise ValueError(f"Unexpected IT response shape: {resp.text}") from e

    i, j = content.find("{"), content.rfind("}")
    if i == -1 or j == -1 or j <= i:
        raise ValueError(f"IT returned no JSON content: {content!r}")
    try:
        return json.loads(content[i : j + 1])
    except json.JSONDecodeError as e:
        raise ValueError(f"IT returned invalid JSON: {content[i : j + 1]!r}") from e


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
        return {"jsonrpc": "2.0", "id": body.get("id"), "error": {"code": -32600, "message": "Missing 'method'"},
                "result": {"correlationId": correlation_id}}

    jsonrpc_id = body.get("id")
    method = _norm_method(body.get("method"))
    params = ensure_dict(body.get("params") or {})

    if any(t in method for t in ["getcard", "card", "discovery"]):
        return {"jsonrpc": "2.0", "id": jsonrpc_id, "result": build_agent_card(str(request.base_url))}

    if any(t in method for t in ["actions/execute", "action/execute", "a2a/execute", "message/send",
                                 "messages/send", "invoke", "execute", "validate"]):
        payload = (params.get("input") or params.get("payload") or params.get("data") or params)
        action = (params.get("action") or "").split(".")[-1]

        try:
            clean = extract_data_from_payload(payload)
            if action == "validate_and_provision":
                hr_out = validate_new_hire(NewHireIn(**clean))
                it_out = await call_it_provision(hr_out)
                result = {"hr": hr_out.model_dump(), "it": it_out}
                act = "validate_and_provision"
            else:
                out = validate_new_hire(NewHireIn(**clean))
                result = out.model_dump()
                act = "validate_new_hire"

            return {"jsonrpc": "2.0", "id": jsonrpc_id,
                    "result": {"action": act, "status": "ok", "output": result, "correlationId": correlation_id}}
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
    """
    Supports streaming and non-streaming. For streaming:
      - First chunk: delta.role only
      - Next chunks: delta.content (pieces of final JSON string)
      - Stop chunk + [DONE]
    """
    model = payload.get("model", "hr-agent")
    wants_stream = bool(payload.get("stream")) or ("text/event-stream" in (request.headers.get("accept", "").lower() if request else ""))

    messages = payload.get("messages") or []
    if isinstance(messages, str):
        try:
            messages = json.loads(messages)
        except json.JSONDecodeError:
            messages = []

    user_msgs = [m for m in messages if m.get("role") == "user"]
    content = (user_msgs[-1]["content"] if user_msgs else "") or {}

    if isinstance(content, dict):
        data = content
    elif isinstance(content, str):
        s = content.strip()
        if s.startswith("{") and s.endswith("}"):
            try:
                data = json.loads(s)
            except json.JSONDecodeError:
                data = {"_free_text": s}
        else:
            data = {"_free_text": s}
    else:
        data = {"_free_text": str(content)}

    async def work() -> str:
        try:
            if "action" in data and "input" in data and isinstance(data["input"], (dict, str)):
                action = (data.get("action") or "").split(".")[-1]
                input_payload = data["input"]
            else:
                try:
                    input_payload = extract_data_from_payload(data)
                    action = "validate_new_hire"
                except ValueError:
                    ft = data.get("_free_text")
                    parsed = parse_free_text_to_new_hire(ft) if ft else None
                    if not parsed:
                        raise
                    action = "validate_new_hire"
                    input_payload = parsed

            clean = extract_data_from_payload(input_payload)
            if action == "validate_and_provision":
                hr_out = validate_new_hire(NewHireIn(**clean))
                it_out = await call_it_provision(hr_out)
                result_obj = {"hr": hr_out.model_dump(), "it": it_out}
            else:
                hr_out = validate_new_hire(NewHireIn(**clean))
                result_obj = hr_out.model_dump()
            return json.dumps(result_obj)
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

            # 1) Do the work AFTER first bytes are sent
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

            # 3) Stop chunk + terminator
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
    print(f"Starting HR Agent on port {port}")
    uvicorn.run("main_hr:app", host="0.0.0.0", port=port, log_level="info")

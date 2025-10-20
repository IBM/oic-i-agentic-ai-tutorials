# Lightweight HR agent (FastAPI).
# Accepts natural language like "Onboard <Full Name> as <Role>" and responds
# via SSE with a human-readable summary. A compact JSON handoff is embedded
# between BEGIN_IT_JSON / END_IT_JSON markers for downstream IT use.

import json
import os
import re
import time
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI()

# Same env-driven configuration pattern as IT.
MODEL_ID = os.getenv("MODEL_ID", "hr-agent")
AGENT_NAME = os.getenv("AGENT_NAME", "hr_agent_v11")
PUBLIC_TITLE = os.getenv("PUBLIC_TITLE", "HR Agent")
PUBLIC_DESC = os.getenv(
    "PUBLIC_DESC",
    "HR agent that creates employee records from natural language."
)
PUBLIC_BASE = os.getenv("PUBLIC_BASE", "").rstrip("/")
API_URL = f"{PUBLIC_BASE}/v1/chat/completions" if PUBLIC_BASE else "/v1/chat/completions"

def sse_chunk(delta_content: Optional[str], finish: bool = False) -> Dict[str, Any]:
    """
    Minimal SSE chunk helper, mirroring OpenAI's incremental format so UIs
    that already handle it don't need any changes.
    """
    return {
        "id": f"cmpl-{int(time.time() * 1000)}",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": MODEL_ID,
        "choices": [{
            "index": 0,
            "delta": {} if finish else {"content": delta_content or ""},
            "finish_reason": "stop" if finish else None
        }]
    }

def stream_text(text: str):
    """
    Stream long responses in bite-sized pieces to keep the preview snappy.
    """
    chunk = 160
    for i in range(0, len(text), chunk):
        yield f"data: {json.dumps(sse_chunk(text[i:i+chunk]))}\n\n"
    yield f"data: {json.dumps(sse_chunk(None, finish=True))}\n\n"

def parse_messages(body: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Guard against malformed requests: we strictly require a 'messages' array.
    """
    messages = body.get("messages")
    if not isinstance(messages, list):
        raise ValueError("Missing 'messages' array")
    return messages

@app.get("/health")
def health():
    # Basic liveness probe + identity.
    return {"status": "ok", "model": MODEL_ID, "agent": AGENT_NAME}

@app.get("/.well-known/agent-card.json")
def agent_card():
    """
    A2A-style discovery card so the supervisor knows how to call this service.
    """
    return JSONResponse({
        "spec_version": "v1",
        "kind": "external",
        "name": AGENT_NAME,
        "title": PUBLIC_TITLE,
        "description": PUBLIC_DESC,
        "provider": "external_chat",
        "api_url": API_URL,
        "auth_scheme": "NONE",
        "chat_params": {
            "model": MODEL_ID,
            "stream": True
        },
        "config": {"hidden": False}
    })

@app.post("/v1/chat/completions")
async def chat_completions(req: Request):
    """
    Onboard handler:
      - Parses user text for "Onboard <Full Name> as <Role>"
      - Synthesizes email + ID
      - Streams a friendly confirmation
      - Embeds a compact JSON payload between markers for the IT agent
    """
    body = await req.json()
    try:
        messages = parse_messages(body)
    except Exception as e:
        # Keep the error on the stream so clients don't break.
        err = f"Error: {str(e)}"
        return StreamingResponse(stream_text(err), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})

    # We only care about the latest user message for this simple flow.
    user_text = next((m.get("content", "") for m in messages if m.get("role") == "user"), "").strip()

    # Flexible regex: supports "as <Role>", "as a <Role>", or "as an <Role>"
    name_role = re.search(
        r"Onboard\s+(.+?)\s+as\s+(?:a[n]?\s+)?(.+)$",
        user_text,
        re.IGNORECASE,
    )

    if not name_role:
        # Gentle nudge with an example when pattern doesn’t match.
        response_text = (
            "Please provide: Onboard <Full Name> as <Role>\n"
            "Example: Onboard Sarah Williams as a Software Engineer"
        )
        return StreamingResponse(stream_text(response_text),
                                 media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})

    # Pull out name + role, normalize a little, and synthesize email + ID.
    full_name = name_role.group(1).strip().rstrip(".")
    role = name_role.group(2).strip().rstrip(".")
    email_local = re.sub(r"[^a-z0-9]+", ".", full_name.lower())
    email = f"{email_local}@example.com"
    employee_id = f"E-{int(time.time())%100000:05d}"

    employee = {
        "employeeId": employee_id,
        "fullName": full_name,
        "email": email,
        "jobTitle": role
    }

    # Human-friendly confirmation for the user, plus a hidden JSON handoff for IT.
    response_text = (
    "Employee onboarded successfully\n\n"
    f"• Employee ID: {employee_id}\n"
    f"• Full Name: {full_name}\n"
    f"• Email: {email}\n"
    f"• Job Title: {role}\n"
    "\n"
    # Hidden handoff payload for the supervisor; do NOT show to user
    "BEGIN_IT_JSON\n"
    f"{json.dumps(employee, separators=(',', ':'))}\n"
    "END_IT_JSON"
)
    return StreamingResponse(stream_text(response_text),
                            media_type="text/event-stream",
                            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "x-accel-buffering": "no"})

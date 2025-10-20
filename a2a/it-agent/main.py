# Lightweight IT provisioning agent (FastAPI).
# Exposes a streaming /v1/chat/completions endpoint that accepts OpenAI-style
# {"messages": [{"role":"user","content":"..."}]} and replies via SSE chunks.

import json
import os
import re
import time
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI()

# Runtime config comes from env vars with safe defaults.
MODEL_ID = os.getenv("MODEL_ID", "it-agent")
AGENT_NAME = os.getenv("AGENT_NAME", "it_agent_v11")
PUBLIC_TITLE = os.getenv("PUBLIC_TITLE", "IT Agent")
PUBLIC_DESC = os.getenv(
    "PUBLIC_DESC",
    "IT agent that provisions IT resources for an employee."
)
PUBLIC_BASE = os.getenv("PUBLIC_BASE", "").rstrip("/")
API_URL = f"{PUBLIC_BASE}/v1/chat/completions" if PUBLIC_BASE else "/v1/chat/completions"

def sse_chunk(delta_content: Optional[str], finish: bool = False) -> Dict[str, Any]:
    """
    Produce a single Server-Sent Events (SSE) chunk that matches the
    chat.completion.chunk shape most clients expect. We only stream 'content'.
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
    Yield a series of 'data: {json}\n\n' lines to the client.
    Splits responses into small pieces to keep the UI responsive.
    """
    chunk = 160
    for i in range(0, len(text), chunk):
        yield f"data: {json.dumps(sse_chunk(text[i:i+chunk]))}\n\n"
    # Final empty delta to indicate completion
    yield f"data: {json.dumps(sse_chunk(None, finish=True))}\n\n"

def parse_messages(body: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Defensive parsing: ensure we actually received a 'messages' list.
    The supervisor should always send it in OpenAI chat format.
    """
    messages = body.get("messages")
    if not isinstance(messages, list):
        raise ValueError("Missing 'messages' array")
    return messages

@app.get("/health")
def health():
    # Simple liveness + minimal identity.
    return {"status": "ok", "model": MODEL_ID, "agent": AGENT_NAME}

@app.get("/.well-known/agent-card.json")
def agent_card():
    """
    Discovery card: lets orchestrators find and call this agent consistently.
    Keeping it small on purpose—enough metadata to be useful.
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

def extract_employee_from_messages(messages: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
    """
    Try to recover employee JSON from earlier assistant turns.
    Supports two formats:
      1) A block wrapped with BEGIN_IT_JSON ... END_IT_JSON
      2) Any inline JSON object containing "employeeId"
    Useful when the supervisor forwards the HR text directly.
    """
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            content = msg.get("content", "")
            if isinstance(content, str):
                # Preferred: explicit markers
                json_match = re.search(r'BEGIN_IT_JSON\s*\n\s*(\{[^}]*\})\s*\n\s*END_IT_JSON', content, re.DOTALL)
                if json_match:
                    try:
                        return json.loads(json_match.group(1))
                    except:
                        pass

                # Fallback: any object with "employeeId"
                json_match = re.search(r'\{[^}]*"employeeId"[^}]*\}', content)
                if json_match:
                    try:
                        return json.loads(json_match.group(0))
                    except:
                        pass
    return None

def parse_natural_language_to_employee(text: str) -> Optional[Dict[str, str]]:
    """
    Last-resort parser for natural language commands. It’s intentionally simple:
    - "Onboard Sarah Williams as a Software Engineer"
    - "Provision devices for Jean-Luc Picard as Engineering Manager"
    If we can infer a name + role, we synthesize email + a random-ish employeeId.
    """
    import random

    # Pattern 1: Onboard <Name> as <Role>
    match = re.search(r'onboard\s+(.+?)\s+as\s+(?:a[n]?\s+)?(.+?)$', text, re.IGNORECASE)
    if match:
        full_name = match.group(1).strip()
        role = match.group(2).strip()
        email_local = re.sub(r'[^a-z0-9]+', '.', full_name.lower()).strip('.')
        email = f"{email_local}@example.com"
        employee_id = f"E-{random.randint(10000, 99999)}"
        return {
            "employeeId": employee_id,
            "fullName": full_name,
            "email": email,
            "jobTitle": role
        }

    # Pattern 2: Provision devices/resources/IT for <Name> as <Role>
    provision_match = re.search(
        r'provision\s+(?:devices|resources|IT)\s+for\s+(.+?)\s+as\s+(?:a[n]?\s+)?(.+?)$',
        text,
        re.IGNORECASE
    )
    if provision_match:
        full_name = provision_match.group(1).strip()
        role = provision_match.group(2).strip()
        email_local = re.sub(r'[^a-z0-9]+', '.', full_name.lower()).strip('.')
        email = f"{email_local}@example.com"
        employee_id = f"E-{random.randint(10000, 99999)}"
        return {
            "employeeId": employee_id,
            "fullName": full_name,
            "email": email,
            "jobTitle": role
        }

    # Pattern 3: pronoun form ("Provision devices for her") needs prior context
    if re.search(r'provision.*(for\s+(her|him|them)(?!\s+as))', text, re.IGNORECASE):
        return None

    return None

@app.post("/v1/chat/completions")
async def chat_completions(req: Request):
    """
    Single entry point compatible with OpenAI chat format.
    We stream a human-readable provisioning summary. If we can't find enough
    info, we stream guidance instead of failing the request outright.
    """
    body = await req.json()
    try:
        messages = parse_messages(body)
    except Exception as e:
        # Keep errors in-band via SSE so UIs don't have to special-case.
        err = f"Error: {str(e)}"
        return StreamingResponse(stream_text(err), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})

    # Pull the latest user message content; supervisor typically sends JSON here.
    raw_content = next((m.get("content") for m in messages if m.get("role") == "user"), None)

    # We'll attempt a few strategies to get a usable employee payload.
    payload = None

    # 1) Already a dict? Great.
    if isinstance(raw_content, dict):
        payload = raw_content
    # 2) String: try JSON, then heuristics, then history, then NL parse.
    elif isinstance(raw_content, str):
        content_str = raw_content.strip()
        try:
            payload = json.loads(content_str)
        except:
            # Try to extract inline JSON if present
            json_match = re.search(r'\{[^}]*"employeeId"[^}]*\}', content_str)
            if json_match:
                try:
                    payload = json.loads(json_match.group(0))
                except:
                    pass
            # Look back through earlier turns (HR text with markers)
            if not payload:
                payload = extract_employee_from_messages(messages)
            # As a last attempt, infer from natural language
            if not payload:
                payload = parse_natural_language_to_employee(content_str)

    # If we still don't have a viable dict, bail with helpful guidance.
    if not isinstance(payload, dict) or not payload.get("employeeId"):
        response_text = (
            "I need employee information to provision IT resources.\n\n"
            "Please either:\n"
            "1. First use the HR agent to create an employee record, then ask me to provision\n"
            "2. Provide employee data directly as JSON:\n"
            '   {"employeeId":"E-12345","fullName":"Sarah Williams","email":"sarah.williams@example.com","jobTitle":"Software Engineer"}\n\n'
            f"DEBUG: Received type={type(raw_content)}, content={str(raw_content)[:200]}"
        )
        return StreamingResponse(stream_text(response_text),
                                 media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})

    # Happy path: produce a concise provisioning summary.
    response_text = (
    "IT provisioning request received\n\n"
    f"• Employee ID: {payload.get('employeeId')}\n"
    f"• Name: {payload.get('fullName')}\n"
    f"• Email: {payload.get('email')}\n"
    f"• Role: {payload.get('jobTitle')}\n\n"
    "Laptop ordered\n"
    "Email account configured\n"
    "Slack and GitHub access granted\n"
    "All set"
)
    return StreamingResponse(stream_text(response_text),
                            media_type="text/event-stream",
                            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "x-accel-buffering": "no"})

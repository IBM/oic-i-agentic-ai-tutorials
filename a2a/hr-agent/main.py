"""
HR Agent - Minimal Streaming Version
Accepts: firstName, lastName, role
Returns: HR data + IT provisioning result
"""

import asyncio
import json
import os
import re
import time
import uuid

import httpx
from fastapi import Body, FastAPI, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

app = FastAPI(title="HR Agent")

# ==================== Models ====================
class NewHireIn(BaseModel):
    firstName: str = Field(min_length=1)
    lastName: str = Field(min_length=1)
    role: str = Field(min_length=1)


class NewHireOut(BaseModel):
    employeeId: str
    fullName: str
    email: str
    jobTitle: str


# ==================== Core Logic ====================
def validate_new_hire(data: NewHireIn) -> NewHireOut:
    """Validate and normalize new hire data"""
    role_norm = re.sub(r"\s+", " ", data.role.strip()).title()
    employee_id = "E-" + uuid.uuid4().hex[:8].upper()
    email = f"{data.firstName.lower()}.{data.lastName.lower()}@company.com"

    return NewHireOut(
        employeeId=employee_id,
        fullName=f"{data.firstName.strip()} {data.lastName.strip()}",
        email=email,
        jobTitle=role_norm,
    )


async def call_it_agent(hr_data: NewHireOut) -> dict:
    """Call IT agent to provision account"""
    it_url = os.getenv(
        "IT_API_URL",
        "https://it-agent.20xtogjmfdje.us-south.codeengine.appdomain.cloud/v1/chat/completions"
    )

    payload = {
        "model": "it-agent",
        "stream": False,
        "messages": [{"role": "user", "content": json.dumps(hr_data.model_dump())}]
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(it_url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]

        # Extract JSON from content
        start = content.find("{")
        end = content.rfind("}") + 1
        return json.loads(content[start:end])


def parse_input(content: str | dict) -> dict:
    """Parse input content to extract firstName, lastName, role"""
    # If already a dict
    if isinstance(content, dict):
        if "action" in content and "input" in content:
            data = content["input"]
        else:
            data = content
    else:
        # Try to parse JSON string
        try:
            data = json.loads(content)
            if "action" in data and "input" in data:
                data = data["input"]
        except:
            # If not valid JSON, try to extract from free text
            data = extract_from_text(content)

    # Extract required fields
    return {
        "firstName": data.get("firstName", ""),
        "lastName": data.get("lastName", ""),
        "role": data.get("role", "")
    }


def extract_from_text(text: str) -> dict:
    """Extract firstName, lastName, and role from free text like 'Onboard Moi Dom as a Architect'"""
    if not text or not isinstance(text, str):
        return {}

    result = {}

    # Remove common prefixes
    cleaned = re.sub(r'^(onboard|add|register|create|hire)\s+', '', text, flags=re.IGNORECASE).strip()

    # Try to find name pattern (two capitalized words before "as")
    name_match = re.search(r'\b([A-Z][a-z]+)\s+([A-Z][a-z]+)\b', cleaned)
    if name_match:
        result["firstName"] = name_match.group(1)
        result["lastName"] = name_match.group(2)

    # Try to find role after "as" (with optional article)
    # Pattern: "as [a/an/the] <role>"
    role_patterns = [
        r'\bas\s+a\s+([A-Z][a-zA-Z\s]+)',      # "as a Architect"
        r'\bas\s+an\s+([A-Z][a-zA-Z\s]+)',     # "as an Engineer"
        r'\bas\s+the\s+([A-Z][a-zA-Z\s]+)',    # "as the Manager"
        r'\bas\s+([A-Z][a-zA-Z\s]+)',          # "as Manager"
    ]

    for pattern in role_patterns:
        role_match = re.search(pattern, cleaned, re.IGNORECASE)
        if role_match:
            result["role"] = role_match.group(1).strip()
            break

    return result


# ==================== Health Check ====================
@app.get("/health")
def health():
    return {"status": "ok"}


@app.head("/health")
def health_head():
    return Response(status_code=200)


# ==================== OpenAI Chat Completions (Streaming) ====================
@app.post("/v1/chat/completions")
async def chat_completions(payload: dict = Body(...)):
    """
    OpenAI-compatible endpoint with streaming support.
    Always calls IT agent after validating HR data.
    """
    model = payload.get("model", "hr-agent")
    wants_stream = bool(payload.get("stream", False))

    # Extract user message
    messages = payload.get("messages", [])
    user_msgs = [m for m in messages if m.get("role") == "user"]
    content = user_msgs[-1]["content"] if user_msgs else ""

    # Parse input
    input_data = parse_input(content)

    async def do_work() -> str:
        """Validate HR data and call IT agent"""
        try:
            # Validate required fields
            if not all([input_data.get("firstName"), input_data.get("lastName"), input_data.get("role")]):
                missing = [k for k in ["firstName", "lastName", "role"] if not input_data.get(k)]
                return json.dumps({"error": f"Missing required fields: {missing}"})

            # Validate new hire
            hr_out = validate_new_hire(NewHireIn(**input_data))

            # Call IT agent
            it_out = await call_it_agent(hr_out)

            # Return combined result
            result = {
                "hr": hr_out.model_dump(),
                "it": it_out
            }
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})

    # Streaming response
    if wants_stream:
        chunk_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        created = int(time.time())

        async def stream():
            # 1) Send role chunk
            yield f"data: {json.dumps({'id': chunk_id, 'object': 'chat.completion.chunk', 'created': created, 'model': model, 'choices': [{'index': 0, 'delta': {'role': 'assistant'}, 'finish_reason': None}]})}\n\n"
            await asyncio.sleep(0)

            # 2) Do the work
            result_text = await do_work()

            # 3) Stream content in chunks
            chunk_size = 80
            for i in range(0, len(result_text), chunk_size):
                chunk = result_text[i:i+chunk_size]
                yield f"data: {json.dumps({'id': chunk_id, 'object': 'chat.completion.chunk', 'created': created, 'model': model, 'choices': [{'index': 0, 'delta': {'content': chunk}, 'finish_reason': None}]})}\n\n"
                await asyncio.sleep(0)

            # 4) Send stop chunk
            yield f"data: {json.dumps({'id': chunk_id, 'object': 'chat.completion.chunk', 'created': created, 'model': model, 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}]})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )

    # Non-streaming response
    final_text = await do_work()
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": final_text},
            "finish_reason": "stop"
        }]
    }


# ==================== Entrypoint ====================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8080"))
    print(f"Starting HR Agent on port {port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, log_level="info")

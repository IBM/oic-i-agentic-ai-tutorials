"""
IT Agent - Minimal Streaming Version
Accepts: HR employee data (employeeId, fullName, email, jobTitle)
Returns: Provisioning result (directoryUserId, status)
"""

import asyncio
import json
import time
import uuid

from fastapi import Body, FastAPI, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI(title="IT Agent")

# ==================== Models ====================
class Employee(BaseModel):
    employeeId: str
    fullName: str
    email: str
    jobTitle: str


class ProvisionResult(BaseModel):
    directoryUserId: str
    status: str


# ==================== Core Logic ====================
async def provision_account(emp: Employee) -> ProvisionResult:
    """Provision directory account for employee"""
    await asyncio.sleep(0.05)  # Simulate work
    user_id = "dir-" + uuid.uuid4().hex[:10]
    return ProvisionResult(directoryUserId=user_id, status="success")


def parse_input(content):
    """Parse input content to extract employee data"""
    # If already a dict
    if isinstance(content, dict):
        return content
    else:
        # Try to parse JSON string
        try:
            return json.loads(content)
        except:
            return {}


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
    Provisions directory account for employee.
    """
    model = payload.get("model", "it-agent")
    wants_stream = bool(payload.get("stream", False))

    # Extract user message
    messages = payload.get("messages", [])
    user_msgs = [m for m in messages if m.get("role") == "user"]
    content = user_msgs[-1]["content"] if user_msgs else ""

    # Parse input
    input_data = parse_input(content)

    async def do_work() -> str:
        """Provision account"""
        try:
            # Validate required fields
            required = ["employeeId", "fullName", "email", "jobTitle"]
            if not all(input_data.get(k) for k in required):
                missing = [k for k in required if not input_data.get(k)]
                return json.dumps({"error": f"Missing required fields: {missing}"})

            # Provision account
            emp = Employee(**input_data)
            result = await provision_account(emp)

            return json.dumps(result.model_dump())
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
    print(f"Starting IT Agent on port {port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, log_level="info")
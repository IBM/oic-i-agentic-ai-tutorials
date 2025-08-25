# === main.py ===
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
import httpx
import json
import asyncio
import time
import os
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # Or ["*"] to allow all
    allow_credentials=True,
    allow_methods=["*"],            # Allow all HTTP methods
    allow_headers=["*"],            # Allow all headers
)

# === CONFIGURATION ===
THREAD_ENDPOINT = os.getenv("THREAD_ENDPOINT")
TOKEN_ENDPOINT = os.getenv("TOKEN_ENDPOINT")
STREAM_API_ENDPOINT = os.getenv("STREAM_API_ENDPOINT")
API_KEY = os.getenv("API_KEY")
RUN_RESULT_URL = THREAD_ENDPOINT + "/"

# === UTILITY FUNCTIONS ===
async def get_token():
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(TOKEN_ENDPOINT, json={"apikey": API_KEY})
        response.raise_for_status()
        return response.json()["token"]

async def get_or_create_thread(query: str, token: str, thread_id: str | None = None):
    if thread_id:
        return thread_id

    headers = {"Authorization": f"Bearer {token}"}
    body = {
        "message": {
            "role": "user",
            "content": query
        },
        "stream": True
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(THREAD_ENDPOINT, headers=headers, json=body)
        response.raise_for_status()
        return response.json()["thread_id"]

# === /get-result: POLLING ENDPOINT ===
@app.get("/get-result")
async def get_result(query: str, agent_id: str):
    try:
        token = await get_token()
        headers = {"Authorization": f"Bearer {token}"}

        async with httpx.AsyncClient(timeout=10.0) as client:
            task_response = await client.post(THREAD_ENDPOINT, headers=headers, json={
                "message": {
                    "role": "user",
                    "content": query
                },
                "agent_id": agent_id
            })

            if task_response.status_code != 200:
                raise HTTPException(
                    status_code=task_response.status_code,
                    detail=f"Error from orchestration API: {task_response.text}"
                )

            run_id = task_response.json().get("run_id")

        result_url = f"{RUN_RESULT_URL}{run_id}"

        timeout = 60
        interval = 2
        start_time = time.time()

        while True:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(result_url, headers=headers)
                response.raise_for_status()
                data = response.json()

            status = data.get("status")
            result = data.get("result")

            if status == "completed":
                return {"message": "✅ Task completed.", "result": result}
            elif status == "failed":
                raise HTTPException(status_code=400, detail="❌ Task failed.")
            elif time.time() - start_time > timeout:
                raise HTTPException(status_code=408, detail="⏱️ Polling timed out.")

            await asyncio.sleep(interval)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"🔴 Server error: {str(e)}")

# === /chat: STREAMING ENDPOINT ===
@app.get("/chat", response_class=StreamingResponse)
async def chat_with_agent(query: str, agent_id: str, thread_id: str = None):
    try:
        token = await get_token()
        thread_id = await get_or_create_thread(query, token, thread_id)

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        body = {
            "message": {
                "role": "user",
                "content": query
            },
            "agent_id": agent_id,
            "thread_id": thread_id
        }

        params = {
            "stream": "true",
            "stream_timeout": "120000",
            "multiple_content": "true"
        }

        async def stream_response():
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", THREAD_ENDPOINT, headers=headers, params=params, json=body) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        raise HTTPException(status_code=response.status_code, detail=error_text.decode())

                    async for chunk in response.aiter_text():
                        chunk = chunk.strip()
                        if not chunk:
                            continue
                        try:
                            event = json.loads(chunk)
                            if event["event"] == "message.delta":
                                contents = event["data"]["delta"].get("content", [])
                                for part in contents:
                                    if part.get("response_type") == "text":
                                        response_json = {
                                            "error_message": False,
                                            "response": part["text"],
                                            "thread_id": thread_id
                                        }
                                        yield f"data: {json.dumps(response_json)}\n\n"
                        except json.JSONDecodeError:
                            continue

        return StreamingResponse(stream_response(), media_type="text/event-stream")

    except httpx.HTTPStatusError as http_err:
        raise HTTPException(status_code=http_err.response.status_code, detail=f"HTTP error: {http_err}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"🔥 Internal server error: {str(e)}")

# === test_apis.py ===
import httpx
import asyncio

BASE_URL = "http://127.0.0.1:8000"
# Temperature agent
async def call_get_result():
    print("\U0001f4e1 Calling /get-result...")
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(f"{BASE_URL}/get-result", params={
                "query": "Run Temperature Check Now",
                "agent_id": "844e3f9a-2a37-4921-8bf5-9e29193fc391"
            })
            print("✅ /get-result Response:")
            print(response.json())
    except Exception as e:
        print(f"❌ Error during /get-result: {e}")
# Risk expert agent
async def call_chat():
    print("\U0001f4ac Calling /chat (stream)...")
    try:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", f"{BASE_URL}/chat", params={
                "query": "How can I create a dashboard with the list of risks in RiskHub?",
                "agent_id": "6f14e7ed-43c3-4051-98a0-a68712729045" 
            }) as response:
                if response.status_code != 200:
                    error = await response.aread()
                    print(f"❌ Error: {response.status_code} - {error.decode()}")
                    return

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        print(line[6:])
    except Exception as e:
        print(f"❌ Error during /chat: {e}")

async def main():
    await call_get_result()
    await call_chat()

if __name__ == "__main__":
    asyncio.run(main())

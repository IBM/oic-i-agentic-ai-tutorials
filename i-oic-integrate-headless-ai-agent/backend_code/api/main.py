"""
FastAPI proxy for a threaded, streaming chat backend.

- Provides a Server-Sent Events (SSE) endpoint: /chat
- Provides a non-streaming convenience endpoint: /chat/v2
"""

import asyncio
import json
import os
import time
from time import monotonic
from typing import Optional

from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import httpx

# --- Load .env locally (ignored in prod if env vars are set) ---
dotenv_path = find_dotenv()
if dotenv_path:
    load_dotenv(dotenv_path)

# --- Required config ---
THREAD_ENDPOINT = os.getenv("THREAD_ENDPOINT")
TOKEN_ENDPOINT = os.getenv("TOKEN_ENDPOINT")
API_KEY = os.getenv("API_KEY")
if not all([THREAD_ENDPOINT, TOKEN_ENDPOINT, API_KEY]):
    raise RuntimeError("Missing env vars: THREAD_ENDPOINT, TOKEN_ENDPOINT, API_KEY")

# Some runtimes allow polling a result at: <THREAD_ENDPOINT>/<run_id>
RUN_RESULT_URL = THREAD_ENDPOINT.rstrip("/") + "/"

# --- App & CORS ---
app = FastAPI(title="Chat Proxy", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    # For development you can allow all origins.
    # In production, replace ["*"] with a list of allowed origins,
    # e.g. ["https://your-frontend.example.com"]
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# --- Shared HTTP client + token cache ---
TOKEN_TTL_SECONDS = int(os.getenv("TOKEN_TTL_SECONDS", str(50 * 60)))  # match provider
app.state.client = None
app.state.token = None
app.state.token_exp = 0.0


@app.on_event("startup")
async def _startup():
    limits = httpx.Limits(max_connections=100, max_keepalive_connections=20)
    # For HTTP/2: pip install "httpx[http2]" and set http2=True
    app.state.client = httpx.AsyncClient(
        timeout=30.0, limits=limits
    )  # http2=True optional


@app.on_event("shutdown")
async def _shutdown():
    if app.state.client:
        await app.state.client.aclose()


async def get_token() -> str:
    """Fetches and caches a short-lived token."""
    now = monotonic()
    if app.state.token and now < app.state.token_exp:
        return app.state.token
    # Choose headers based on endpoint
    if "iam.cloud.ibm.com" in TOKEN_ENDPOINT:
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        data = {
            "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
            "apikey": API_KEY,
        }
        r = await app.state.client.post(TOKEN_ENDPOINT, data=data, headers=headers)
    else:
        headers = {"Accept": "application/json"}
        r = await app.state.client.post(TOKEN_ENDPOINT, json={"apikey": API_KEY}, headers=headers)

    #r = await app.state.client.post(TOKEN_ENDPOINT, json={"apikey": API_KEY}, headers=headers)
    r.raise_for_status()
    data = r.json()
    tok = data.get("token") or data.get("access_token")
    if not tok:
        raise HTTPException(
            status_code=502, detail="Auth server did not return a token."
        )
    app.state.token = tok
    app.state.token_exp = now + TOKEN_TTL_SECONDS
    return tok


async def get_or_create_thread(
    query: str, token: str, thread_id: Optional[str] = None
) -> str:
    """Creates a thread when needed and returns its id."""
    if thread_id:
        return thread_id
    headers = {"Authorization": f"Bearer {token}"}
    body = {"message": {"role": "user", "content": query}}
    r = await app.state.client.post(THREAD_ENDPOINT, headers=headers, json=body)
    r.raise_for_status()
    data = r.json()
    tid = data.get("thread_id")
    if not tid:
        raise HTTPException(
            status_code=502, detail="Upstream did not return thread_id."
        )
    return tid


# ---------------- Endpoints ----------------

@app.get("/chat/v2")
async def chat_non_stream(
    query: str,
    agent_id: str,
    thread_id: Optional[str] = None,
    include_raw: int = 0,  # <-- made plain int
):
    """Non-streaming convenience endpoint. Tries inline result; if needed, polls by run_id."""
    try:
        token = await get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        body = {"message": {"role": "user", "content": query}, "agent_id": agent_id}
        if thread_id:
            body["thread_id"] = thread_id
        params = {"stream": "false", "multiple_content": "true"}

        trig = await app.state.client.post(
            THREAD_ENDPOINT, headers=headers, params=params, json=body
        )
        trig.raise_for_status()
        trig_data = trig.json()

        inline_text = _extract_final_text(trig_data)
        returned_thread = trig_data.get("thread_id") or thread_id
        if inline_text:
            out = {
                "error_message": False,
                "status": "completed",
                "response": inline_text,
                "thread_id": returned_thread,
            }
            if include_raw:
                out["raw"] = trig_data
            return JSONResponse(out)

        run_id = trig_data.get("run_id")
        if not run_id:
            out = {
                "error_message": False,
                "status": trig_data.get("status") or "unknown",
                "response": "",
                "thread_id": returned_thread,
            }
            if include_raw:
                out["raw"] = trig_data
            return JSONResponse(out)

        final_data = await _poll_run_result(run_id, headers)
        final_text = _extract_final_text(final_data) or ""
        returned_thread = final_data.get("thread_id") or returned_thread
        status = final_data.get("status") or "completed"

        out = {
            "error_message": False,
            "status": str(status),
            "response": final_text,
            "thread_id": returned_thread,
        }
        if include_raw:
            out["raw"] = final_data
        return JSONResponse(out)

    except httpx.HTTPStatusError as http_err:
        detail = (
            http_err.response.text if http_err.response is not None else str(http_err)
        )
        raise HTTPException(
            status_code=http_err.response.status_code if http_err.response else 502,
            detail=f"Upstream error: {detail}",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# ---------------- Helpers ----------------


async def _poll_run_result(
    run_id: str, headers: dict, timeout_s: int = 60, interval_s: float = 0.7
):
    """Polls <RUN_RESULT_URL>/<run_id> until completed or failed or timeout."""
    url = f"{RUN_RESULT_URL.rstrip('/')}/{run_id}"
    start = time.time()
    while True:
        r = await app.state.client.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()
        status = (
            data.get("status") or data.get("state") or data.get("run_status") or ""
        ).lower()
        if status in {"completed", "succeeded", "success", "done"}:
            return data
        if status in {"failed", "error", "cancelled"}:
            raise HTTPException(
                status_code=400, detail=f"Run failed: {json.dumps(data)}"
            )
        if time.time() - start > timeout_s:
            raise HTTPException(status_code=408, detail="Polling timed out.")
        await asyncio.sleep(interval_s)


def _extract_final_text(payload: dict) -> str:
    """Looks in common locations for final text."""
    if not isinstance(payload, dict):
        return ""
    try:
        contents = payload["result"]["data"]["message"]["content"]
        if isinstance(contents, list):
            texts = [
                c.get("text")
                for c in contents
                if isinstance(c, dict) and isinstance(c.get("text"), str)
            ]
            if texts:
                dedup = list(dict.fromkeys(texts))
                return "\n".join(dedup).strip()
    except Exception:
        pass
    if isinstance(payload.get("response"), str) and payload["response"].strip():
        return payload["response"].strip()
    content = payload.get("content")
    if isinstance(content, list):
        texts = [
            c.get("text")
            for c in content
            if isinstance(c, dict) and isinstance(c.get("text"), str)
        ]
        if texts:
            dedup = list(dict.fromkeys(texts))
            return "\n".join(dedup).strip()
    return ""

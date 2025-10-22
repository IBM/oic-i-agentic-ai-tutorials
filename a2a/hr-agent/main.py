"""
HR Agent - Watsonx Orchestrate Compatible Server

This creates a simple HTTP server that exposes an HR onboarding agent through
an OpenAI-compatible Chat Completions API. The agent is discoverable by
Watsonx Orchestrate through an A2A agent card.

Key Features:
- OpenAI-compatible /v1/chat/completions endpoint for broad compatibility
- A2A agent card at /.well-known/agent-card.json for discovery
- Server-Sent Events (SSE) streaming for real-time responses
- Support for IBM Code Engine deployment with automatic URL detection
"""

import json
import os
import time
from typing import Optional

from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse, StreamingResponse
from starlette.requests import Request
import uvicorn

from agent_executor import HRAgent


# Server Configuration
# Port defaults to 8080 (required by IBM Code Engine)
PORT = int(os.getenv('PORT', '8080'))

# Detect if we're running in IBM Code Engine by checking for CE environment variables
# Code Engine automatically provides CE_SUBDOMAIN and CE_DOMAIN
CE_SUBDOMAIN = os.getenv('CE_SUBDOMAIN', '')
CE_DOMAIN = os.getenv('CE_DOMAIN', '')

if CE_SUBDOMAIN and CE_DOMAIN:
    # Running in Code Engine - use the provided public URL
    PUBLIC_URL = f'https://{CE_SUBDOMAIN}.{CE_DOMAIN}/'
else:
    # Running locally or in another environment
    PUBLIC_URL = os.getenv('PUBLIC_URL', f'http://localhost:{PORT}/')
    if not PUBLIC_URL.endswith('/'):
        PUBLIC_URL += '/'

# Create a single instance of the HR agent that handles all requests
hr_agent = HRAgent()


async def agent_card(_request: Request) -> JSONResponse:
    """
    Agent Card Endpoint - Enables Discovery by Watsonx Orchestrate

    This endpoint returns metadata about the agent in A2A protocol format.
    Watsonx Orchestrate queries this endpoint to learn what the agent can do,
    what format it expects, and how to communicate with it.

    The agent card includes:
    - Skills: What tasks the agent can perform
    - API URL: Where to send requests
    - Provider: Which protocol version to use (A2A 0.2.1)
    """
    return JSONResponse({
        "spec_version": "v1",
        "kind": "external",
        "name": "hr_agent_a2a",
        "title": "HR Agent",
        "description": "HR agent that creates employee records from natural language",
        "provider": "external_chat/A2A/0.2.1",
        "api_url": f"{PUBLIC_URL}v1/chat/completions",
        "auth_scheme": "NONE",
        "chat_params": {
            "model": "hr-agent",
            "agentProtocol": "A2A",
            "stream": True
        },
        "skills": [{
            "id": "employee_onboarding",
            "name": "Employee Onboarding",
            "description": "Creates employee records from natural language onboarding requests",
            "tags": ["hr", "onboarding", "employee"],
            "examples": [
                "Onboard Sarah Williams as a Software Engineer",
                "Onboard John Smith as Senior Data Analyst",
                "Onboard Maria Garcia as Product Manager"
            ]
        }],
        "config": {"hidden": False}
    })


def sse_chunk(content: Optional[str] = None, finish: bool = False) -> dict:
    """
    Create an OpenAI-compatible Server-Sent Event (SSE) chunk.

    This formats responses to match what OpenAI's API returns, ensuring
    compatibility with tools that expect OpenAI's format.
    """
    return {
        "id": f"cmpl-{int(time.time() * 1000)}",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": "hr-agent",
        "choices": [{
            "index": 0,
            "delta": {} if finish else {"content": content or "", "role": "assistant"},
            "finish_reason": "stop" if finish else None
        }]
    }


async def stream_text(text: str):
    """
    Stream text response in Server-Sent Events (SSE) format.

    Instead of waiting for the entire response to be ready, we stream it
    back to the client in chunks. This provides a better user experience
    for longer responses.

    The first chunk includes the role ("assistant") to indicate who's speaking.
    Subsequent chunks only include the content being streamed.
    """
    chunk_size = 60  # Characters per chunk
    first = True

    # Break the text into chunks and send them one at a time
    for i in range(0, len(text), chunk_size):
        chunk_text = text[i:i+chunk_size]

        if first:
            # First chunk needs to establish that this is the assistant responding
            chunk_data = {
                "id": f"cmpl-{int(time.time() * 1000)}",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": "hr-agent",
                "choices": [{
                    "index": 0,
                    "delta": {"role": "assistant", "content": chunk_text},
                    "finish_reason": None
                }]
            }
            first = False
        else:
            # Subsequent chunks just contain content
            chunk_data = {
                "id": f"cmpl-{int(time.time() * 1000)}",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": "hr-agent",
                "choices": [{
                    "index": 0,
                    "delta": {"content": chunk_text},
                    "finish_reason": None
                }]
            }

        # SSE format requires "data: " prefix and double newline
        yield f"data: {json.dumps(chunk_data)}\n\n"

    # Send the final chunk to indicate completion
    yield f"data: {json.dumps(sse_chunk(finish=True))}\n\n"
    yield "data: [DONE]\n\n"


async def chat_completions(request: Request) -> StreamingResponse:
    """
    OpenAI-Compatible Chat Completions Endpoint

    This endpoint handles incoming chat requests from Watsonx Orchestrate
    and other clients. It supports multiple input formats for flexibility:

    Format 1 - OpenAI standard:
        {"messages": [{"role": "user", "content": "Onboard John Doe..."}]}

    Format 2 - Watsonx supervisor:
        {"text": "Onboard John Doe..."}

    Format 3 - Simple direct:
        {"content": "Onboard John Doe..."}
    """
    try:
        body = await request.json()
        user_text = ""

        # Try to extract the user's message from various possible formats
        # This makes the agent more resilient to different client implementations

        if "text" in body:
            # Watsonx Orchestrate supervisor sometimes uses this format
            user_text = body.get("text", "")

        elif "messages" in body:
            # Standard OpenAI format - find the last user message
            messages = body.get("messages", [])
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    content = msg.get("content", "")

                    # Content might be a string or a list of content blocks
                    if isinstance(content, str):
                        user_text = content
                    elif isinstance(content, list):
                        # Extract text from content blocks
                        for block in content:
                            if isinstance(block, dict):
                                if block.get("type") == "text":
                                    user_text = block.get("text", "")
                                    break
                                elif "text" in block:
                                    user_text = block["text"]
                                    break
                    break

        elif "content" in body:
            # Simple direct format
            user_text = body.get("content", "")

        # Process the request with our HR agent
        result = await hr_agent.onboard_employee(user_text)

        # Stream the response back to the client
        return StreamingResponse(
            stream_text(result),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # Disable nginx buffering
            }
        )

    except Exception as e:
        # If anything goes wrong, stream the error message back
        error_text = f"Error: {str(e)}"
        return StreamingResponse(
            stream_text(error_text),
            media_type="text/event-stream"
        )


async def health(_request: Request) -> JSONResponse:
    """
    Health Check Endpoint

    Used by container orchestration platforms (like Code Engine) to verify
    that the service is running and ready to accept requests.
    """
    return JSONResponse({"status": "ok", "model": "hr-agent", "version": "1.0.0"})


# Define the web application with all our routes
app = Starlette(
    debug=False,
    routes=[
        # A2A agent card for discovery
        Route("/.well-known/agent-card.json", agent_card, methods=["GET"]),

        # Main chat endpoint
        Route("/v1/chat/completions", chat_completions, methods=["POST"]),

        # Health check
        Route("/health", health, methods=["GET"]),
    ]
)


if __name__ == "__main__":
    # Print helpful information when starting up
    print(f"Starting HR Agent on port {PORT}")
    print(f"Agent Card: {PUBLIC_URL}.well-known/agent-card.json")
    print(f"Chat Completions: {PUBLIC_URL}v1/chat/completions")

    # Start the server
    # 0.0.0.0 allows connections from any network interface
    uvicorn.run(app, host="0.0.0.0", port=PORT)

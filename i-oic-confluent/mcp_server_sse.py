"""
MCP Server (SSE Mode): Kafka Agent Bridge

This version runs as an HTTP/SSE server that watsonx Orchestrate can access.

- Consumes Kafka events in a background thread
- Exposes MCP tools via Server-Sent Events (SSE)
- Accessible via HTTP for cloud-based agents
"""

import os
import sys
from queue import Queue
from threading import Thread

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Ensure imports work
sys.path.insert(0, os.path.dirname(__file__))

# Load .env for local development
load_dotenv(override=False)

from consumer import start_consumer  # noqa: E402

# Create MCP server - configure for Code Engine deployment
mcp = FastMCP("kafka-agent-bridge")
# Override default host/port for cloud deployment
mcp.settings.host = "0.0.0.0"
mcp.settings.port = 8080

# Event queue shared between Kafka consumer and MCP tools
event_queue: Queue = Queue()


def _start_kafka_consumer_background() -> None:
    """Start Kafka consumer in daemon thread"""
    t = Thread(
        target=start_consumer,
        args=(event_queue,),
        daemon=True,
    )
    t.start()
    print("[INFO] Kafka consumer started in background thread")


@mcp.tool("get_next_event")
def get_next_event():
    """
    Return the next available Kafka event (one per call).

    Returns:
        {"status": "no_events"} if queue is empty
        {"status": "event", "event": {...}} if event available
    """
    if event_queue.empty():
        return {"status": "no_events"}

    envelope_or_event = event_queue.get()

    # Handle both envelope and raw event formats
    if (
        isinstance(envelope_or_event, dict)
        and "event" in envelope_or_event
        and "kafka" in envelope_or_event
    ):
        return {"status": "event", **envelope_or_event}

    return {"status": "event", "event": envelope_or_event}


@mcp.tool("peek_queue_size")
def peek_queue_size():
    """
    Return how many events are buffered in memory.

    Returns:
        {"size": N} where N is the number of buffered events
    """
    return {"size": event_queue.qsize()}


if __name__ == "__main__":
    # Start Kafka consumer
    _start_kafka_consumer_background()

    # Run MCP server in SSE mode (HTTP accessible)
    # This makes it accessible to cloud-based watsonx Orchestrate
    print(f"[INFO] Starting MCP server in SSE mode on http://{mcp.settings.host}:{mcp.settings.port}")
    mcp.run(transport="sse")

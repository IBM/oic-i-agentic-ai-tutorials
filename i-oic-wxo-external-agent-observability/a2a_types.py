"""
A2A Protocol v0.3.0 — Pydantic models for JSON-RPC 2.0 messages, Tasks, Artifacts, and AgentCard.

Spec reference: https://a2a-protocol.org/latest/specification/
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional, Union
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Agent Card  (served at /.well-known/agent.json)
# ---------------------------------------------------------------------------

class AgentCapabilities(BaseModel):
    streaming: bool = True
    pushNotifications: bool = False
    stateTransitionHistory: bool = False


class AgentSkill(BaseModel):
    id: str
    name: str
    description: str
    inputModes: list[str] = ["text"]
    outputModes: list[str] = ["text"]
    tags: list[str] = []
    examples: list[str] = []


class AgentProvider(BaseModel):
    organization: str
    url: Optional[str] = None


class SecurityScheme(BaseModel):
    type: str  # e.g. "bearer", "apiKey"
    description: Optional[str] = None


class AgentCard(BaseModel):
    """Full A2A AgentCard as per spec §4."""
    protocolVersion: str = "0.3.0"
    name: str
    description: str
    url: str                          # canonical base URL of this A2A server
    provider: Optional[AgentProvider] = None
    version: str = "1.0.0"
    documentationUrl: Optional[str] = None
    capabilities: AgentCapabilities = Field(default_factory=AgentCapabilities)
    securitySchemes: Optional[dict[str, SecurityScheme]] = None
    security: Optional[list[dict[str, list[str]]]] = None
    defaultInputModes: list[str] = ["text"]
    defaultOutputModes: list[str] = ["text"]
    skills: list[AgentSkill] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# JSON-RPC 2.0 envelope
# ---------------------------------------------------------------------------

class JSONRPCRequest(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: Union[str, int, None] = None
    method: str
    params: Optional[dict[str, Any]] = None


class JSONRPCError(BaseModel):
    code: int
    message: str
    data: Optional[Any] = None


class JSONRPCResponse(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: Union[str, int, None] = None
    result: Optional[Any] = None
    error: Optional[JSONRPCError] = None


# ---------------------------------------------------------------------------
# A2A Task lifecycle
# ---------------------------------------------------------------------------

class TaskState(str, Enum):
    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED = "completed"
    CANCELED = "canceled"
    FAILED = "failed"
    UNKNOWN = "unknown"


class TextPart(BaseModel):
    model_config = {"populate_by_name": True}
    kind: Literal["text"] = Field("text", serialization_alias="type")
    text: str
    metadata: Optional[dict[str, Any]] = None


class DataPart(BaseModel):
    model_config = {"populate_by_name": True}
    kind: Literal["data"] = Field("data", serialization_alias="type")
    data: dict[str, Any]
    metadata: Optional[dict[str, Any]] = None


Part = Union[TextPart, DataPart]


class Message(BaseModel):
    """A single message in a conversation turn."""
    kind: Literal["message"] = "message"
    role: Literal["user", "agent"]
    parts: list[Part]
    messageId: str
    taskId: Optional[str] = None
    contextId: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None


class Artifact(BaseModel):
    """An artifact produced by the agent."""
    artifactId: str
    name: Optional[str] = None
    description: Optional[str] = None
    parts: list[Part]
    metadata: Optional[dict[str, Any]] = None
    index: int = 0
    append: Optional[bool] = None
    lastChunk: Optional[bool] = None


class TaskStatus(BaseModel):
    state: TaskState
    message: Optional[Message] = None
    timestamp: Optional[str] = None


class Task(BaseModel):
    """A2A Task object (spec §6.1)."""
    kind: Literal["task"] = "task"
    id: str
    contextId: str
    status: TaskStatus
    artifacts: Optional[list[Artifact]] = None
    history: Optional[list[Message]] = None
    metadata: Optional[dict[str, Any]] = None


# ---------------------------------------------------------------------------
# A2A method-specific param/result types
# ---------------------------------------------------------------------------

class PushNotificationConfig(BaseModel):
    url: str
    token: Optional[str] = None
    authentication: Optional[dict[str, Any]] = None


class MessageSendConfiguration(BaseModel):
    acceptedOutputModes: list[str] = ["text"]
    pushNotificationConfig: Optional[PushNotificationConfig] = None
    historyLength: Optional[int] = None
    blocking: Optional[bool] = True


class MessageSendParams(BaseModel):
    """Params for message/send."""
    message: Message
    configuration: Optional[MessageSendConfiguration] = None
    metadata: Optional[dict[str, Any]] = None


class TaskQueryParams(BaseModel):
    """Params for tasks/get."""
    id: str
    historyLength: Optional[int] = None
    metadata: Optional[dict[str, Any]] = None


class TaskCancelParams(BaseModel):
    """Params for tasks/cancel."""
    id: str
    metadata: Optional[dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Streaming event types (SSE)
# ---------------------------------------------------------------------------

class TaskStatusUpdateEvent(BaseModel):
    kind: Literal["status-update"] = "status-update"
    taskId: str
    contextId: str
    status: TaskStatus
    final: bool = False
    metadata: Optional[dict[str, Any]] = None


class TaskArtifactUpdateEvent(BaseModel):
    kind: Literal["artifact-update"] = "artifact-update"
    taskId: str
    contextId: str
    artifact: Artifact
    metadata: Optional[dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Standard JSON-RPC error codes
# ---------------------------------------------------------------------------

class A2AErrorCode:
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    TASK_NOT_FOUND = -32001
    TASK_NOT_CANCELABLE = -32002
    PUSH_NOTIFICATION_NOT_SUPPORTED = -32003
    UNSUPPORTED_OPERATION = -32004
    CONTENT_TYPE_NOT_SUPPORTED = -32005
    INVALID_AGENT_RESPONSE = -32006

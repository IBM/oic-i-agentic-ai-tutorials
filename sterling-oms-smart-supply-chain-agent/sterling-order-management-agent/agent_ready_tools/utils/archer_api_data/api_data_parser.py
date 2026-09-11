from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from pydantic.type_adapter import TypeAdapter


class ChatThread(BaseModel):
    """
    Represents a chat thread between a user and an AI Agent.

    A ChatThread organizes the messages between a participants.
    """

    title: str
    id: str
    created_on: str
    updated_at: str


class StepType(Enum):
    """Categories for a reasoning step."""

    TOOL_RESPONSE = "tool_response"
    TOOL_CALL = "tool_call"
    "Parameter names and values which tool is called with."
    TOOL_CALLS = "tool_calls"
    "tool_calls this appears to be used in place of tool_calls when a tool call fails."
    PLANNING = "planning"


class Content(BaseModel):
    """
    The content of a chat message.

    The content contains the chat response text.
    """

    response_type: str
    text: Optional[str]


class ToolCalls(BaseModel):
    """Tool calls that correspond to StepType.TOOL_CALLS."""

    args: Dict
    name: Optional[str]


class StepDetail(BaseModel):
    """
    Represents the details of an agent reasoning step.

    A step is generally a tool call and response. It can be a wxo-domains python tool,
    but it also includes the calls & responses of agent transfers, knowledge base calls, etc.

    If StepDetail.type is StepType.TOOL_CALLS, then `name` & `args` data are not found in
    StepDetail (StepDetail.name, StepDetail.args), but in tool_calls. That is List[ToolCalls].

    Example:
    ```json
    "step_details": [
        {
            "type": "tool_calls",
            "tool_calls": [
                {
                    "id": "chatcmpl-tool-970ed3e5b6ee408d987ff14130",
                    "args": {"email": "morgan.stanford_etaj-dev23@oraclepdemos.com"},
                    "name": "oracle_employee_personal_information_agent",
                }
            ],
            "agent_display_name": "oracle_employee_support_manager",
        }
    ]
    ```
    """

    type: StepType
    name: Optional[str] = None
    args: Optional[Dict] = None
    content: Optional[str] = None
    "`content` can either a python tool response or a unstructured text response"

    tool_calls: Optional[List[ToolCalls]] = None
    "Only populated when StepDetail.type is StepType.TOOL_CALLS."


class StepHistory(BaseModel):
    """The Step History contains a list of reasoning steps."""

    step_details: List[StepDetail]


class InterlocutorRole(Enum):
    """The role of the interlocutor in a chat."""

    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(BaseModel):
    """Represents a single message sent within a chat thread and the various reasoning steps to used
    to reach the response (content)."""

    role: Optional[InterlocutorRole]
    step_history: Optional[List[StepHistory]] = None
    content: List[Content]


class WxOApiDataParser:
    """Parse data from the watsonx Orchestrate Server API."""

    @classmethod
    def parse_threads(cls, threads: List[Dict[str, Any]]) -> List[ChatThread]:
        """
        Parse threads from the watsonx Orchestrate Server API.

        Args:
            threads: threads from the API response.

        Returns:
            A list of returned chat threads
        """

        thread_adaptor = TypeAdapter(List[ChatThread])

        return thread_adaptor.validate_python(threads)

    @classmethod
    def parse_messages(cls, thread: List[Dict]) -> List[ChatMessage]:
        """
        Parse messages for a chat thread.

        Args:
            thread: a parsed conversation thread.

        Returns:
            List of dialogue turns from a conversation.
        """

        message_type_adaptor = TypeAdapter(List[ChatMessage])

        return message_type_adaptor.validate_python(thread)

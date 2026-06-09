from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import RunnableConfig

from ibm_watsonx_orchestrate_sdk import Client


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def _latest_user_message(messages: list[BaseMessage]) -> str:
    for message in reversed(messages):
        if getattr(message, "type", "") == "human":
            content = getattr(message, "content", "")
            if isinstance(content, str) and content.strip():
                return content
    return ""


def create_agent(config: RunnableConfig):
    client = Client.from_runnable_config(config)

    def agent_node(state: AgentState):
        user_text = _latest_user_message(state.get("messages", []))
        if not user_text:
            return {"messages": [AIMessage(content="No user message found.")]}

        # Store the message
        client.memory.add_messages(
            messages=[{"role": "user", "content": user_text}],
            memory_type="preference",
            infer=False,
            metadata={"source": "user_preference_processor"}
        )

        # Search for related memories
        search_response = client.memory.search(
            query=user_text,
            limit=3,
            memory_type="preference"
        )

        if search_response.results:
            memory_text = "\n".join(item.content for item in search_response.results)
            response_text = f"Stored! Related memories:\n{memory_text}"
        else:
            response_text = "Stored! This is your first memory."

        return {"messages": [AIMessage(content=response_text)]}

    builder = StateGraph(AgentState)
    builder.add_node("agent", agent_node)
    builder.set_entry_point("agent")
    builder.add_edge("agent", END)
    return builder.compile()

# Made with Bob

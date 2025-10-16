"""
A minimal flow that runs the get_quote tool and uses an Agent Node to send the quote via email.
"""
from pydantic import BaseModel, Field
from ibm_watsonx_orchestrate.flow_builder.flows import (
    flow,
    Flow,
    START,
    END,
    AgentNode
)
from get_quote_min import get_quote_min


class Quote(BaseModel):
    text: str = Field(description="The quote text.")
    author: str = Field(description="The author of the quote.")


class Message(BaseModel):
    message: str = Field(description="Notification message about the quote.")


def build_notify_agent_node(aflow: Flow) -> AgentNode:
    """
    Builds an Agent Node that sends the quote to another agent (e.g., email_notifier_agent).
    """
    notify_agent_node = aflow.agent(
        name="notify_user_via_agent",
        agent="email_test_agent",  # 👈 name of the other agent you’ll create
        title="Send quote via email",
        description="This agent will send the daily quote to the user via email.",
        message="Please send this quote to sgar3484@gmail.com with subject and body being testing wxo agent scheduler.",
        input_schema=Quote,
        output_schema=Message
    )
    return notify_agent_node


@flow(
    name="daily_quote_flow_min",
    output_schema=Message,
    schedulable=True
)
def build_daily_quote_flow(aflow: Flow = None) -> Flow:
    """
    Simple flow that fetches a daily quote and sends it via email using an agent.
    """
    quote_node = aflow.tool(get_quote_min)
    notify_agent_node = build_notify_agent_node(aflow)

    aflow.sequence(START, quote_node, notify_agent_node, END)

    return aflow

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

class NotifyUserInput(BaseModel):
    quote: str = Field(description="The quote text.")
    to_email: str = Field(description="Recipient email address.")



class Message(BaseModel):
    message: str = Field(description="Notification message about the quote.")


def build_notify_agent_node(aflow: Flow) -> AgentNode:
    """
    Builds an Agent Node that sends the quote to another agent.
    """
    notify_agent_node = aflow.agent(
        name="notify_user_via_agent",
        agent="email_test_agent",  # 👈 name of the other agent you’ll create
        title="Send quote via email",
        description="This agent will send the daily quote to the user via email.",
        message="Please send this quote clearly formatted to the recipient email",
        input_schema=NotifyUserInput,
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

# """
# A minimal flow that runs the get_quote_min tool and uses an Agent Node to send the quote via email.
# """
# from pydantic import BaseModel, Field
# from ibm_watsonx_orchestrate.flow_builder.flows import (
#     flow,
#     Flow,
#     START,
#     END,
#     AgentNode
# )
# from get_quote_min import get_quote_min


# # -----------------------------
# # Schema definitions
# # -----------------------------
# class Quote(BaseModel):
#     quote: str = Field(description="The motivational quote text including the author.")


# class Message(BaseModel):
#     message: str = Field(description="Notification message about the email status.")


# # -----------------------------
# # Agent node builder
# # -----------------------------
# def build_notify_agent_node(aflow: Flow) -> AgentNode:
#     """
#     Builds an Agent Node that sends the quote to the user via email.
#     """
#     notify_agent_node = aflow.agent(
#         name="notify_user_via_agent",
#         agent="email_test_agent",
#         title="Send quote via email",
#         description="This agent will send the daily motivational quote to the user via email.",
#         message=(
#             "You will receive the quote text and the recipient email. "
#             "Use the send_email_notification tool to send the quote as an email. "
#             "Always respond with valid JSON: {\"message\": \"<status>\"}."
#         ),
#         input_schema=Quote,
#         output_schema=Message,
#     )
#     return notify_agent_node


# # -----------------------------
# # Flow definition
# # -----------------------------
# @flow(
#     name="daily_quote_flow_min",
#     description="Fetch a random motivational quote and send it via email using the email_test_agent.",
#     output_schema=Message,
#     schedulable=True,
# )
# def build_daily_quote_flow(aflow: Flow = None) -> Flow:
#     """
#     Simple flow that fetches a daily quote and sends it via email using an agent.
#     """
#     quote_node = aflow.tool(get_quote_min, output_schema=Quote)
#     notify_agent_node = build_notify_agent_node(aflow)

#     # ✅ Map quote text to agent input
#     notify_agent_node.map_input("quote", "flow.get_quote_min.quote")
#     notify_agent_node.map_input("to_email", "'sagarn32@in.ibm.com'")

#     # ✅ Map final output (the email status)
#     aflow.map_output("message", "flow.notify_user_via_agent.message")

#     # Define execution order
#     aflow.sequence(START, quote_node, notify_agent_node, END)

#     return aflow

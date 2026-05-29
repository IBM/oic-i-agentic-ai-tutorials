"""
LangGraph React Agent for Annualized Rate of Return Calculations
"""
import logging
from typing import Annotated, TypedDict, Literal
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from tools import calculate_annualized_return
from langchain_core.runnables.config import RunnableConfig
from ibm_watsonx_orchestrate_sdk.langchain import ChatWxO

# Configure logger
logger = logging.getLogger(__name__)


# Define the agent state
class AgentState(MessagesState):
    """State for the agent including message history"""
    pass


# Create the agent
def create_react_agent(config: RunnableConfig):
    """
    Create a LangGraph React agent that can calculate annualized rate of return.
    
    Returns:
        A compiled LangGraph agent
    """
    logger.info("Creating React agent...")
    
    # Access system instructions
    instructions = config.get("configurable", {}).get("instructions", "")
    logger.info(f"System instructions: {instructions}")

    # Use instructions in your agent's system prompt
    system_message = f"You are a helpful assistant. {instructions}"

    # # Get all credentials
    credentials = config.get("configurable", {}).get("credentials", {})

    # using wxo instance model
    wxo_api_key = credentials.get("wxo_langgraph_api_key")
    instance_url = credentials.get("wxo_langgraph_base_url")
    llm = ChatWxO(
            instance_url=instance_url,
            api_key=wxo_api_key,
            model="groq/openai/gpt-oss-120b",
            temperature=0.7,
            streaming=False,
            max_tokens=20000,
        )

    
    # Bind tools to the LLM
    tools = [calculate_annualized_return]
    logger.info(f"Binding {len(tools)} tools to LLM")
    llm_with_tools = llm.bind_tools(tools)
    
    # Define the agent node
    def agent_node(state: AgentState):
        """
        The agent node that processes messages and decides whether to use tools.
        """
        logger.info("Agent node invoked")
        messages = state["messages"]
        logger.debug(f"Processing {len(messages)} messages")
        response = llm_with_tools.invoke(messages)
        logger.info(f"Agent response generated: {type(response).__name__}")
        return {"messages": [response]}
    
    # Define the routing function
    def should_continue(state: AgentState) -> Literal["tools", "end"]:
        """
        Determine whether to continue to tools or end the conversation.
        """
        messages = state["messages"]
        last_message = messages[-1]
        
        # If there are tool calls, continue to tools
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            logger.info(f"Tool calls detected: {len(last_message.tool_calls)} tool(s)")
            return "tools"
        # Otherwise, end
        logger.info("No tool calls detected, ending conversation")
        return "end"
    
    # Create the tool node
    tool_node = ToolNode(tools)
    logger.info("Tool node created")
    
    # Build the graph
    workflow = StateGraph(AgentState)
    logger.info("Building workflow graph...")
    
    # Add nodes
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)
    logger.info("Nodes added to workflow")
    
    # Add edges
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": END
        }
    )
    workflow.add_edge("tools", "agent")
    logger.info("Edges added to workflow")
    
    # # Add memory
    # memory = MemorySaver()
    
    # # Compile the graph
    # app = workflow.compile(checkpointer=memory)
    
    # return app
    logger.info("React agent created successfully")
    return workflow


def format_response(response):
    """
    Format the agent's response for display.
    
    Args:
        response: The response from the agent
        
    Returns:
        Formatted string response
    """
    logger.info("Formatting response")
    messages = response["messages"]
    last_message = messages[-1]
    
    if isinstance(last_message, AIMessage):
        logger.debug(f"Returning AI message content: {last_message.content[:100]}...")
        return last_message.content
    logger.debug(f"Returning message as string: {str(last_message)[:100]}...")
    return str(last_message)

# Made with Bob

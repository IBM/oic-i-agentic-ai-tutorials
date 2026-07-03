"""
LangGraph React Agent for Annualized Rate of Return Calculations
"""
from langchain_core.runnables.base import Runnable


from langchain_core.language_models.base import LanguageModelInput


from langchain_core.messages.base import BaseMessage


from langchain_core.tools.base import BaseTool


from typing import Annotated, TypedDict, Literal
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from tools import calculate_annualized_return


# Define the agent state
class AgentState(MessagesState):
    """State for the agent including message history"""
    pass


# Create the agent
def create_react_agent():
    """
    Create a LangGraph React agent that can calculate annualized rate of return.
    
    Returns:
        A compiled LangGraph agent
    """
    # Initialize the LLM
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    
    # Bind tools to the LLM
    tools: list[BaseTool] = [calculate_annualized_return]
    llm_with_tools: Runnable[LanguageModelInput, BaseMessage] = llm.bind_tools(tools)
    
    # Define the agent node
    def agent_node(state: AgentState):
        """
        The agent node that processes messages and decides whether to use tools.
        """
        messages = state["messages"]
        response = llm_with_tools.invoke(messages)
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
            return "tools"
        # Otherwise, end
        return "end"
    
    # Create the tool node
    tool_node = ToolNode(tools)
    
    # Build the graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)
    
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
    
    # Add memory
    memory = MemorySaver()
    
    # Compile the graph
    app = workflow.compile(checkpointer=memory)
    
    return app


def format_response(response):
    """
    Format the agent's response for display.
    
    Args:
        response: The response from the agent
        
    Returns:
        Formatted string response
    """
    messages = response["messages"]
    last_message = messages[-1]
    
    if isinstance(last_message, AIMessage):
        return last_message.content
    return str(last_message)


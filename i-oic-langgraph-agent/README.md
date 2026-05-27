# Run Your Custom LangGraph Agents Within watsonx Orchestrate Runtime Environment  

As an Enterprise AI Architect, one of your core goals is to industrialize agentic AI without creating a fragmented runtime landscape. Many organizations already have custom LangGraph agents developed by innovation teams, line-of-business developers, or partner ecosystems. The challenge is not whether these agents exist—it is how to operationalize them within a governed, scalable, enterprise-grade runtime.

watsonx Orchestrate addresses this need by allowing you to import custom LangGraph agents and run them inside the WXO agent runtime. This gives you a strong value proposition: you can preserve prior investments in custom agent logic while consolidating execution, security, model access, governance, and operations within a single enterprise platform. Instead of maintaining separate hosting stacks for bespoke LangGraph agents, you can bring them into WXO and manage them as part of your broader AI architecture.

This capability is especially valuable when designing enterprise agent ecosystems because it helps you:
- Reuse existing LangGraph assets rather than rebuilding them from scratch
- Standardize runtime operations across native and imported agents
- Centralize credentials, model access, and environment management
- Improve governance, scalability, and operational consistency
- Reduce the complexity and cost of supporting multiple agent runtimes

This tutorial shows how to take a custom LangGraph agent, adapt it for compatibility, and run it within the watsonx Orchestrate runtime environment.

First, we will create and run a simple LangGraph agent in standalone mode. Then we will make the required code adjustments to import that LangGraph agent into WXO so it can execute within the WXO agent runtime.

## Architecture

Understanding the architecture is key to successfully deploying LangGraph agents within watsonx Orchestrate. The diagram below illustrates how a custom LangGraph agent integrates with the WXO platform:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      watsonx Orchestrate Platform                           │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                      WXO Agent Runtime                                │ │
│  │                                                                       │ │
│  │  ┌─────────────────────────────────────────────────────────┐         │ │
│  │  │           Your Custom LangGraph Agent                   │         │ │
│  │  │                                                         │         │ │
│  │  │  ┌──────────────┐      ┌──────────────┐               │         │ │
│  │  │  │ Agent Logic  │      │    Tools     │               │         │ │
│  │  │  │  (agent.py)  │◄────►│  (tools.py)  │               │         │ │
│  │  │  └──────────────┘      └──────────────┘               │         │ │
│  │  │         │                                              │         │ │
│  │  │         │ Uses ChatWxO                                 │         │ │
│  │  │         ▼                                              │         │ │
│  │  └─────────┼──────────────────────────────────────────────┘         │ │
│  │            │                                                        │ │
│  │            │                                                        │ │
│  │  ┌─────────▼────────────────────────────────────────────┐           │ │
│  │  │            WXO Internal Model Gateway                │           │ │
│  │  │                                                      │           │ │
│  │  │  ┌──────────┐  ┌──────────┐  ┌──────────┐          │           │ │
│  │  │  │  Groq    │  │ watsonx  │  │  Ollama  │   ...    │           │ │
│  │  │  │  Models  │  │  Models  │  │  Models  │          │           │ │
│  │  │  └──────────┘  └──────────┘  └──────────┘          │           │ │
│  │  └──────────────────────────────────────────────────────┘           │ │
│  │            ▲                                                        │ │
│  │            │ Credentials from Connection                           │ │
│  │            │                                                        │ │
│  │  ┌─────────┴────────────────────────────────────────────┐           │ │
│  │  │             WXO Connection Manager                   │           │ │
│  │  │                                                      │           │ │
│  │  │  Connection: wxo_langgraph                           │           │ │
│  │  │  - base_url (WXO instance URL)                       │           │ │
│  │  │  - api_key (WXO API key)                             │           │ │
│  │  └──────────────────────────────────────────────────────┘           │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Can also call
                                    │ 
                                    ▼
                    ┌───────────────────────────────┐
                    │   External LLM Providers      │
                    │                               │
                    │  ┌──────────┐  ┌──────────┐  │
                    │  │ OpenAI   │  │ Anthropic│  │
                    │  │  Models  │  │  Models  │  │
                    │  └──────────┘  └──────────┘  │
                    └───────────────────────────────┘
```

### Key Architecture Components

1. **WXO Agent Runtime**: The managed runtime environment where your LangGraph agent executes. It handles:
   - Agent lifecycle management
   - Conversation state management
   - Security and authentication
   - Scaling and resource allocation

2. **Your Custom LangGraph Agent**: Your agent code (agent.py and tools.py) runs within the WXO runtime:
   - Receives configuration and credentials via `RunnableConfig`
   - Uses `ChatWxO` to access WXO's internal model infrastructure
   - Can also use `ChatOpenAI` or other LangChain integrations to call external models
   - Implements your custom business logic and tools

3. **WXO Internal Model Gateway**: Provides unified access to models hosted within WXO:
   - Groq models (Llama, Mixtral, etc.)
   - IBM watsonx.ai models
   - Ollama models
   - Other internally hosted providers
   - Handles authentication, rate limiting, and failover

4. **External LLM Providers**: Your agent can also directly call external hosted models:
   - OpenAI models (GPT-4, GPT-3.5, etc.) via `ChatOpenAI`
   - Anthropic models (Claude) via `ChatAnthropic`
   - Requires separate API keys managed through connections
   - Useful for models not available in WXO's internal gateway

5. **WXO Connection Manager**: Securely manages credentials:
   - Stores API keys and connection details
   - Injects credentials into agent runtime
   - Supports multiple environments (draft/live)

### Benefits of This Architecture

- **Unified Runtime**: No need to manage separate agent infrastructure
- **Model Flexibility**: Easy switching between different LLM providers
- **Secure Credentials**: Centralized, secure credential management
- **Enterprise Ready**: Built-in scaling, monitoring, and governance
- **Cost Optimization**: Shared infrastructure reduces operational costs

## Prerequisites

- An active watsonx Orchestrate instance (local developer edition or IBM Cloud hosted instance)
- A running local environment of the watsonx Agent Development Kit (ADK) to configure connections and agents using the CLI. If you do not have an active ADK instance, review the [getting started with ADK tutorial](https://www.ibm.com/docs/en/watsonx/watson-orchestrate/current?topic=started-getting-adk). This tutorial has been tested and validated with ADK version 2.2.0.
- Python version between 3.11.x to 3.13.x installed on your local machine
- An OpenAI API key (for the standalone version)

## Part 1: Creating and Running a Standalone LangGraph Agent

In this section, we'll create a simple LangGraph agent that calculates the annualized rate of return for investments.

### Step 1: Set Up Your Project Directory

Create a new directory for your project and navigate to it:

```bash
mkdir langraph-wxo-demo
cd langraph-wxo-demo
```

### Step 2: Create Environment Configuration

Create a `.env` file to store your API keys:

```bash
# .env
OPENAI_API_KEY=your-openai-api-key-here
```

**Important:** Replace `your-openai-api-key-here` with your actual OpenAI API key. You can get one from [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys).

### Step 3: Create the Tools Module

Create a `tools.py` file that defines the calculation tool:

```python
"""
Tools for calculating annualized rate of return
"""
from langchain_core.tools import tool


@tool
def calculate_annualized_return(
    initial_investment: float,
    current_value: float,
    months_invested: int
) -> dict:
    """
    Calculate the annualized rate of return for an investment.
    
    Args:
        initial_investment: The initial investment amount in dollars
        current_value: The current value of the investment in dollars
        months_invested: The number of months the money has been invested
        
    Returns:
        A dictionary containing the calculation results including:
        - annualized_return: The annualized rate of return as a percentage
        - total_return: The total return as a percentage
        - profit_loss: The profit or loss amount in dollars
    """
    if initial_investment <= 0:
        return {
            "error": "Initial investment must be greater than 0",
            "annualized_return": None,
            "total_return": None,
            "profit_loss": None
        }
    
    if months_invested <= 0:
        return {
            "error": "Months invested must be greater than 0",
            "annualized_return": None,
            "total_return": None,
            "profit_loss": None
        }
    
    # Calculate total return
    total_return = ((current_value - initial_investment) / initial_investment) * 100
    
    # Calculate profit/loss
    profit_loss = current_value - initial_investment
    
    # Calculate annualized return
    # Formula: ((Current Value / Initial Investment) ^ (12 / months)) - 1
    years = months_invested / 12
    annualized_return = (((current_value / initial_investment) ** (1 / years)) - 1) * 100
    
    return {
        "annualized_return": round(annualized_return, 2),
        "total_return": round(total_return, 2),
        "profit_loss": round(profit_loss, 2),
        "initial_investment": initial_investment,
        "current_value": current_value,
        "months_invested": months_invested,
        "years_invested": round(years, 2)
    }
```

### Step 4: Create the Agent Module

Create an `agent.py` file that defines the LangGraph agent:

```python
"""
LangGraph React Agent for Annualized Rate of Return Calculations
"""
from typing import Literal
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage
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
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    # Bind tools to the LLM
    tools = [calculate_annualized_return]
    llm_with_tools = llm.bind_tools(tools)
    
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
```

### Step 5: Create the Main Script

Create a `main.py` file to run the agent interactively:

```python
"""
Main script to run the Annualized Rate of Return Agent
"""
import os
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from agent import create_react_agent, format_response


def main():
    """
    Main function to run the agent interactively.
    """
    # Load environment variables
    load_dotenv()
    
    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not found in environment variables.")
        print("Please create a .env file with your OpenAI API key:")
        print("OPENAI_API_KEY=your-api-key-here")
        return
    
    # Create the agent
    print("Initializing Annualized Rate of Return Agent...")
    agent = create_react_agent()
    print("Agent ready!\n")
    
    # Configuration for thread
    config = {"configurable": {"thread_id": "1"}}
    
    print("=" * 70)
    print("Annualized Rate of Return Calculator Agent")
    print("=" * 70)
    print("\nThis agent can help you calculate the annualized rate of return")
    print("for your investments. Just provide:")
    print("  - Initial investment amount")
    print("  - Current value")
    print("  - Number of months invested")
    print("\nType 'quit' or 'exit' to end the conversation.\n")
    print("=" * 70)
    
    # Interactive loop
    while True:
        try:
            # Get user input
            user_input = input("\nYou: ").strip()
            
            # Check for exit commands
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\nThank you for using the Annualized Rate of Return Agent!")
                break
            
            if not user_input:
                continue
            
            # Create message
            message = HumanMessage(content=user_input)
            
            # Invoke the agent
            print("\nAgent: ", end="", flush=True)
            response = agent.invoke(
                {"messages": [message]},
                config=config
            )
            
            # Format and print response
            formatted_response = format_response(response)
            print(formatted_response)
            
        except KeyboardInterrupt:
            print("\n\nInterrupted by user. Exiting...")
            break
        except Exception as e:
            print(f"\nError: {str(e)}")
            print("Please try again or type 'quit' to exit.")


if __name__ == "__main__":
    main()
```

### Step 6: Set Up Python Virtual Environment and Install Dependencies

Create a `requirements.txt` file:

```
langgraph
langchain
langchain-openai
python-dotenv
ibm-watsonx-orchestrate
```

**Note:** We're including `ibm-watsonx-orchestrate` in the requirements file because we'll use the same virtual environment to run WXO ADK commands later in Part 2.

Create and activate a Python virtual environment:

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On macOS/Linux:
source .venv/bin/activate

# On Windows:
.venv\Scripts\activate
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

You should see output indicating that all packages are being installed, including the watsonx Orchestrate ADK.

### Step 7: Test the Standalone Agent

Run the agent:

```bash
python main.py
```

Try asking questions like:
- "I invested $10,000 and now it's worth $12,500. I've been invested for 18 months. What's my annualized rate of return?"
- "Calculate the annualized return for an initial investment of $5000, current value of $6200, over 24 months."

The agent should use the `calculate_annualized_return` tool to perform the calculations and provide detailed responses.

## Part 2: Adapting the Agent for watsonx Orchestrate

Now that we have a working standalone agent, let's adapt it to run within the watsonx Orchestrate runtime environment.

### Step 1: Create the WXO Agent Directory

Create a new directory for the WXO-compatible agent:

```bash
mkdir my_langraph_agent
```

### Step 2: Copy and Modify the Tools

Copy the `tools.py` file to the new directory:

```bash
cp tools.py my_langraph_agent/
```

The tools file doesn't need any modifications for WXO.

### Step 3: Modify the Agent for WXO

Create a modified `agent.py` in the `my_langraph_agent` directory with the following key changes:

```python
"""
LangGraph React Agent for Annualized Rate of Return Calculations
Adapted for watsonx Orchestrate runtime
"""
import logging
from typing import Literal
from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode
from langchain_core.runnables.config import RunnableConfig
from ibm_watsonx_orchestrate_sdk.langchain import ChatWxO
from tools import calculate_annualized_return

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
    
    Args:
        config: RunnableConfig containing credentials and instructions from WXO
    
    Returns:
        A compiled LangGraph workflow
    """
    logger.info("Creating React agent...")
    
    # Access system instructions from WXO
    instructions = config.get("configurable", {}).get("instructions", "")
    logger.info(f"System instructions: {instructions}")
    
    # Get credentials from WXO connection
    credentials = config.get("configurable", {}).get("credentials", {})
    
    # Extract WXO connection credentials
    wxo_api_key = credentials.get("wxo_langgraph_api_key")
    instance_url = credentials.get("wxo_langgraph_base_url")
    
    # Initialize ChatWxO LLM
    llm = ChatWxO(
        instance_url=instance_url,
        api_key=wxo_api_key,
        model="groq/openai/gpt-oss-120b",  # Use WXO model
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
    
    logger.info("React agent created successfully")
    return workflow
```

**Key Changes from Standalone Version:**

1. **Function Signature**: The `create_react_agent` function now accepts a `config: RunnableConfig` parameter
2. **Credentials Access**: Credentials are retrieved from the config object provided by WXO
3. **LLM Initialization**: Uses `ChatWxO` instead of `ChatOpenAI` to leverage WXO's model infrastructure
4. **Logging**: Added comprehensive logging for debugging in the WXO environment
5. **Memory Removal**: Removed `MemorySaver` as WXO manages conversation state
6. **Return Value**: Returns the workflow graph instead of a compiled app

### Step 4: Create Requirements File

Create a `requirements.txt` in the `my_langraph_agent` directory:

```
langgraph>=0.2.0
langchain>=0.3.0
langchain-openai>=0.2.0
python-dotenv>=1.0.0
ibm-watsonx-orchestrate-sdk
```

**Note:** Do NOT include `ibm-watsonx-orchestrate` in your requirements.txt as it's provided by the WXO runtime.

### Step 5: Create Agent Configuration

Create an `agent.yaml` file in the `my_langraph_agent` directory:

```yaml
spec_version: v1
kind: agent
name: my_langraph_agent
title: My LangGraph Agent
framework: langgraph
description: This agent can return annualized rate of return when provided with initial investment ammount, current value and number of months the ammount has been invested.
deployment:
  code_bundle:
    entrypoint: agent:create_react_agent
checkpointer:
  type: memory
```

This YAML file tells WXO:
- The agent's name and description
- The entrypoint function to call (module:function format)

### Step 6: Create WXO Setup Script

Create a `import_to_wxo.sh` script in the root directory:

```bash
#!/bin/bash

# Script to create and configure WatsonX Orchestrate connection for LangGraph agent
# This script will prompt for required credentials

echo "=========================================="
echo "WatsonX Orchestrate Connection Setup"
echo "=========================================="
echo ""

# Prompt for WatsonX Orchestrate URL
read -p "Enter your WatsonX Orchestrate instance URL: " WXO_LANGGRAPH_URL
if [ -z "$WXO_LANGGRAPH_URL" ]; then
    echo "Error: WatsonX Orchestrate URL is required"
    exit 1
fi

# Prompt for WatsonX Orchestrate API Key
read -sp "Enter your WatsonX Orchestrate API Key: " WXO_LANGGRAPH_API_KEY
echo ""
if [ -z "$WXO_LANGGRAPH_API_KEY" ]; then
    echo "Error: WatsonX Orchestrate API Key is required"
    exit 1
fi

echo ""
echo "Creating connection with provided credentials..."
echo ""

# Create connection
orchestrate connections add --app-id wxo_langgraph 

# Configure connection for draft environment
orchestrate connections configure \
    --app-id wxo_langgraph \
    --env draft \
    --type team \
    --kind key_value 

# Configure connection for live environment
orchestrate connections configure \
    --app-id wxo_langgraph \
    --env live \
    --type team \
    --kind key_value 

# Set credentials for draft environment
orchestrate connections set-credentials \
    --app-id wxo_langgraph \
    --env draft \
    -e base_url="$WXO_LANGGRAPH_URL" \
    -e api_key="$WXO_LANGGRAPH_API_KEY"

# Set credentials for live environment
orchestrate connections set-credentials \
    --app-id wxo_langgraph \
    --env live \
    -e base_url="$WXO_LANGGRAPH_URL" \
    -e api_key="$WXO_LANGGRAPH_API_KEY"

echo ""
echo "Importing agent..."
echo ""

# Import the agent
orchestrate agents import --experimental-package-root my_langraph_agent --experimental-config-file my_langraph_agent/agent.yaml

echo ""
echo "Connecting agent to connection..."
echo ""

# Connect agent to connection
orchestrate agents experimental-connect -n my_langraph_agent -c wxo_langgraph

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo "Agent 'my_langraph_agent' has been created and connected to the 'wxo_langgraph' connection."
echo ""
```

Make the script executable:

```bash
chmod +x import_to_wxo.sh.sh
```

### Step 7: Import the Agent into WXO

Run the setup script:

```bash
./import_to_wxo.sh.sh
```

The script will:
1. Prompt you for your WXO instance URL and API key
2. Create a connection named `wxo_langgraph`
3. Configure the connection for both draft and live environments
4. Set the credentials
5. Import your agent into WXO
6. Connect the agent to the connection

### Step 8: Test the Agent in WXO

Once imported, you can test your agent in the watsonx Orchestrate UI:

1. Navigate to your WXO instance
2. Go to the Agents section
3. Find "my_langraph_agent"
4. Start a conversation and ask questions like:
   - "I invested $10,000 and now it's worth $12,500. I've been invested for 18 months. What's my annualized rate of return?"

The agent will now run within the WXO runtime environment, using WXO's model infrastructure and connection management.

![LangGraph agent running in watsonx Orchestrate](img/langgraph-agent.png)

## Summary

In this tutorial, you learned how to:

1. **Create a standalone LangGraph agent** with:
   - Custom tools (`tools.py`)
   - Agent logic (`agent.py`)
   - Interactive interface (`main.py`)
   - Environment configuration (`.env`)

2. **Adapt the agent for WXO** by:
   - Modifying the agent function to accept `RunnableConfig`
   - Switching from `ChatOpenAI` to `ChatWxO`
   - Accessing credentials from WXO connections
   - Adding proper logging
   - Creating agent configuration (`agent.yaml`)
   - Setting up WXO connections

3. **Deploy to WXO** using:
   - The ADK CLI
   - Connection management
   - Agent import process


## Acknowledgments

This tutorial is produced as part of an IBM Open Innovation Community initiative.

The authors deeply appreciate the support of Jerome Joubert (jerome.joubert@fr.ibm.com) for the guidance on making langraph agent works in wxo enviornment.

For more information, visit the [watsonx Orchestrate documentation](https://www.ibm.com/docs/en/watsonx/watson-orchestrate).

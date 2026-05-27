# Run Your Custom LangGraph Agents Within watsonx Orchestrate Runtime Environment  

As an Enterprise AI Architect, one of our core goals is to industrialize agentic AI without creating a fragmented runtime landscape. Many organizations already have custom LangGraph agents developed by innovation teams, line-of-business developers, or partner ecosystems. The challenge is not whether these agents exist—it is how to operationalize them within a governed, scalable, enterprise-grade runtime.

watsonx Orchestrate addresses this need by allowing us to import custom LangGraph agents and run them inside the WXO agent runtime. This provides a strong value proposition: We can preserve prior investments in custom agent logic while consolidating execution, security, model access, governance, and operations within a single enterprise platform. Instead of maintaining separate hosting stacks for bespoke LangGraph agents, we can bring them into WXO and manage them as part of our broader AI architecture.

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

## Getting Started  

### Prerequisites

- An active watsonx Orchestrate instance (local developer edition or IBM Cloud hosted instance)
- A running local environment of the watsonx Agent Development Kit (ADK) to configure connections and agents using the CLI. If you do not have an active ADK instance, review the [getting started with ADK tutorial](https://www.ibm.com/docs/en/watsonx/watson-orchestrate/current?topic=started-getting-adk). This tutorial has been tested and validated with ADK version 2.2.0.
- Python version between 3.11.x to 3.13.x installed on your local machine
- An OpenAI API key (for the standalone version)

### Clone the Repository

To follow this tutorial, clone the repository and navigate to the tutorial folder:

```bash
git clone https://github.com/IBM/oic-i-agentic-ai-tutorials.git
cd oic-i-agentic-ai-tutorials/i-oic-langgraph-agent
```

**Repository:** [IBM/oic-i-agentic-ai-tutorials](https://github.com/IBM/oic-i-agentic-ai-tutorials)

All the files referenced in this tutorial are available in the `i-oic-langgraph-agent` folder. You can either:
- Use the provided files as reference while building your own implementation
- Copy and modify them directly for your use case
- Study the complete working examples to understand the patterns

## File Structure Guide

The file structure below shows how your project folder should look as you implement this tutorial. All these files are already available in the cloned repository for your reference:

### Project File Tree

```
langraph-wxo-demo/
├── .env                          # Environment variables (create this)
├── agent.py                      # Standalone agent implementation
├── main.py                       # Interactive CLI for standalone agent
├── tools.py                      # Investment calculation tool
├── requirements.txt              # Python dependencies
├── import_to_wxo.sh             # WXO deployment automation script
└── my_langraph_agent/           # WXO-compatible agent directory
    ├── agent.py                 # WXO-adapted agent implementation
    ├── tools.py                 # Same tool (WXO compatible)
    ├── requirements.txt         # WXO deployment dependencies
    └── agent.yaml               # WXO agent configuration
```

### Standalone Agent Files (Root Directory)

| File | Purpose | Key Features |
|------|---------|--------------|
| **[tools.py](tools.py)** | Defines the investment calculation tool | - Uses LangChain's `@tool` decorator<br>- Implements `calculate_annualized_return` function<br>- Validates inputs and calculates annualized returns, total returns, and profit/loss<br>- Returns structured dictionary with financial metrics |
| **[agent.py](agent.py)** | Creates standalone LangGraph ReAct agent | - Uses OpenAI's `ChatOpenAI` with GPT-4o-mini model<br>- Implements StateGraph with agent and tool nodes<br>- Includes MemorySaver for conversation persistence<br>- Defines routing logic between agent and tools<br>- Returns compiled LangGraph application |
| **[main.py](main.py)** | Interactive CLI interface for the agent | - Loads environment variables from `.env` file<br>- Provides interactive conversation loop<br>- Handles user input and agent responses<br>- Includes example mode for quick testing<br>- Manages thread configuration for conversation state |
| **[requirements.txt](requirements.txt)** | Python dependencies | - Lists all required packages for both standalone and WXO versions<br>- Includes langgraph, langchain, langchain-openai, python-dotenv, and ibm-watsonx-orchestrate |

### WXO-Compatible Agent Files (`my_langraph_agent/` directory)

| File | Purpose | Key Differences from Standalone |
|------|---------|--------------------------------|
| **[my_langraph_agent/tools.py](my_langraph_agent/tools.py)** | Same calculation tool | - Identical to root `tools.py`<br>- No modifications needed for WXO compatibility |
| **[my_langraph_agent/agent.py](my_langraph_agent/agent.py)** | WXO-compatible agent implementation | - Accepts `RunnableConfig` parameter to receive WXO credentials<br>- Uses `ChatWxO` instead of `ChatOpenAI` to access WXO's model gateway<br>- Retrieves credentials from `config.get("configurable", {}).get("credentials", {})`<br>- Adds comprehensive logging for debugging in WXO environment<br>- Returns workflow graph (not compiled app) - WXO handles compilation<br>- No MemorySaver - WXO manages conversation state |
| **[my_langraph_agent/agent.yaml](my_langraph_agent/agent.yaml)** | Agent configuration for WXO | - Defines agent metadata (name, title, description)<br>- Specifies framework type as `langgraph`<br>- Sets entrypoint to `agent:create_react_agent`<br>- Configures memory checkpointer type |
| **[my_langraph_agent/requirements.txt](my_langraph_agent/requirements.txt)** | WXO deployment dependencies | - Similar to root requirements.txt<br>- Excludes `ibm-watsonx-orchestrate` (provided by WXO runtime)<br>- Includes version constraints for compatibility |

### Deployment Script

| File | Purpose | What It Does |
|------|---------|--------------|
| **[import_to_wxo.sh](import_to_wxo.sh)** | Automated WXO deployment script | - Prompts for WXO instance URL and API key<br>- Creates `wxo_langgraph` connection<br>- Configures connection for draft and live environments<br>- Sets credentials securely<br>- Imports agent into WXO<br>- Connects agent to the connection |



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

Create a `tools.py` file that defines the calculation tool.

**📄 File Reference:** See [tools.py](tools.py) for the complete implementation.

**What this file does:**
- Uses LangChain's `@tool` decorator to create a tool that the agent can call
- Implements the `calculate_annualized_return` function that takes three parameters:
  - `initial_investment`: The starting investment amount in dollars
  - `current_value`: The current value of the investment in dollars
  - `months_invested`: The number of months the money has been invested
- Validates inputs to ensure positive values for investment and time period
- Calculates three key financial metrics:
  - **Annualized Return**: The yearly rate of return using the formula `((Current Value / Initial Investment) ^ (1 / years)) - 1`
  - **Total Return**: The overall percentage gain or loss
  - **Profit/Loss**: The absolute dollar amount gained or lost
- Returns a structured dictionary with all calculated metrics, making it easy for the LLM to interpret and present results

### Step 4: Create the Agent Module

Create an `agent.py` file that defines the LangGraph agent.

**📄 File Reference:** See [agent.py](agent.py) for the complete implementation.

**What this file does:**

**1. Defines the Agent State:**
- Creates `AgentState` class extending `MessagesState` to maintain conversation history
- This state is passed between nodes in the graph

**2. Implements the `create_react_agent()` function:**
- **Initializes the LLM**: Uses OpenAI's `ChatOpenAI` with the `gpt-4o-mini` model at temperature 0 for consistent responses
- **Binds Tools**: Attaches the `calculate_annualized_return` tool to the LLM using `llm.bind_tools()`
- **Creates Agent Node**: Defines `agent_node()` function that:
  - Takes the current state with message history
  - Invokes the LLM with tools to generate a response
  - Returns updated state with the LLM's response
- **Implements Routing Logic**: Defines `should_continue()` function that:
  - Checks if the last message contains tool calls
  - Routes to "tools" node if tool calls are present
  - Routes to "end" if no tool calls (conversation complete)
- **Builds the State Graph**:
  - Creates a `StateGraph` with two nodes: "agent" and "tools"
  - Connects START → agent
  - Adds conditional edge from agent → tools or end
  - Connects tools → agent (for iterative tool use)
- **Adds Memory**: Uses `MemorySaver` to persist conversation state across turns
- **Compiles and Returns**: Returns the compiled LangGraph application ready for execution

**3. Provides Response Formatting:**
- `format_response()` function extracts and formats the agent's final response for display
- Handles different message types (AIMessage, etc.)

This creates a ReAct (Reasoning + Acting) agent that can reason about when to use tools and iterate until the task is complete.

### Step 5: Create the Main Script

Create a `main.py` file to run the agent interactively.

**📄 File Reference:** See [main.py](main.py) for the complete implementation.

**What this file does:**

**1. Environment Setup:**
- Loads environment variables from `.env` file using `python-dotenv`
- Validates that `OPENAI_API_KEY` is present before proceeding
- Provides helpful error messages if configuration is missing

**2. Agent Initialization:**
- Creates the LangGraph agent by calling `create_react_agent()`
- Sets up thread configuration for conversation state management
- Uses thread_id "1" to maintain conversation context across multiple turns

**3. Interactive CLI Interface:**
- Displays a welcome banner with instructions
- Implements a continuous loop that:
  - Prompts user for input
  - Handles exit commands ('quit', 'exit', 'q')
  - Creates `HumanMessage` objects from user input
  - Invokes the agent with the message and configuration
  - Formats and displays the agent's response
- Includes error handling for:
  - Keyboard interrupts (Ctrl+C)
  - Runtime exceptions with helpful error messages

**4. Example Mode (Bonus):**
- Includes a `run_example()` function for quick testing
- Can be run with `python main.py --example` to see a sample calculation
- Demonstrates the agent's capabilities without manual interaction

This provides a complete, user-friendly interface for testing the standalone agent locally before deploying to WXO.

### Step 6: Set Up Python Virtual Environment and Install Dependencies

**📄 File Reference:** See [requirements.txt](requirements.txt) for the complete dependency list.

**What this file contains:**
- `langgraph` - The LangGraph framework for building stateful, multi-actor applications
- `langchain` - Core LangChain library for building LLM applications
- `langchain-openai` - OpenAI integration for LangChain (used in standalone version)
- `python-dotenv` - For loading environment variables from `.env` file
- `ibm-watsonx-orchestrate>=2.10.0` - WXO ADK for deploying agents (used in Part 2)

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

Create a modified `agent.py` in the `my_langraph_agent` directory.

**📄 File Reference:** See [my_langraph_agent/agent.py](my_langraph_agent/agent.py) for the complete WXO-compatible implementation.

**What this file does differently from the standalone version:**

**Key Changes for WXO Compatibility:**

1. **Function Signature Change:**
   - Now accepts `config: RunnableConfig` parameter
   - This config object is provided by WXO runtime and contains credentials and instructions

2. **Credentials Management:**
   - Retrieves credentials from `config.get("configurable", {}).get("credentials", {})`
   - Extracts `wxo_langgraph_api_key` and `wxo_langgraph_base_url` from the connection
   - No need for environment variables or `.env` files

3. **LLM Initialization - ChatWxO:**
   - Uses `ChatWxO` from `ibm_watsonx_orchestrate_sdk.langchain` instead of `ChatOpenAI`
   - Connects to WXO's internal model gateway
   - Accesses models like `groq/openai/gpt-oss-120b` hosted within WXO
   - Benefits from WXO's model management, rate limiting, and failover

4. **System Instructions:**
   - Can access custom instructions from `config.get("configurable", {}).get("instructions", "")`
   - Allows dynamic behavior based on WXO agent configuration

5. **Comprehensive Logging:**
   - Added `logging` throughout for debugging in WXO environment
   - Logs agent initialization, tool binding, node invocations, and routing decisions
   - Helps troubleshoot issues in production

6. **Memory Management:**
   - Removed `MemorySaver` - WXO runtime manages conversation state
   - No need to handle checkpointing manually

7. **Return Value:**
   - Returns the `workflow` graph (not compiled app)
   - WXO runtime handles compilation and execution

**Why These Changes Matter:**
- **Security**: Credentials managed centrally by WXO, not in code or env files
- **Scalability**: WXO handles agent lifecycle, scaling, and resource management
- **Governance**: Centralized model access, monitoring, and compliance
- **Flexibility**: Easy to switch models or update configurations without code changes

### Step 4: Create Requirements File

**📄 File Reference:** See [my_langraph_agent/requirements.txt](my_langraph_agent/requirements.txt) for the WXO deployment dependencies.

**What this file contains:**
- `langgraph>=0.2.0` - LangGraph framework with version constraint
- `langchain>=0.3.0` - Core LangChain library
- `langchain-openai>=0.2.0` - OpenAI integration (for potential external model calls)
- `python-dotenv>=1.0.0` - Environment variable management
- `ibm-watsonx-orchestrate-sdk` - SDK for ChatWxO and WXO integrations

**Important Note:** Do NOT include `ibm-watsonx-orchestrate` (the ADK CLI tool) in this requirements.txt as it's provided by the WXO runtime. Only include `ibm-watsonx-orchestrate-sdk` which provides the Python SDK for agent development.

### Step 5: Create Agent Configuration

**📄 File Reference:** See [my_langraph_agent/agent.yaml](my_langraph_agent/agent.yaml) for the complete agent configuration.

**What this YAML file defines:**

- **`spec_version: v1`** - Configuration schema version
- **`kind: agent`** - Declares this as an agent resource
- **`name: my_langraph_agent`** - Unique identifier for the agent
- **`title: My LangGraph Agent`** - Display name in WXO UI
- **`framework: langgraph`** - Specifies the agent framework type
- **`description`** - Explains what the agent does (shown in WXO UI)
- **`deployment.code_bundle.entrypoint`** - Points to `agent:create_react_agent`
  - Format: `module:function`
  - WXO will import the `agent` module and call `create_react_agent(config)`
- **`checkpointer.type: memory`** - Configures conversation state persistence

This configuration tells WXO how to load, initialize, and run your custom LangGraph agent within its runtime environment.

### Step 6: Create WXO Setup Script

**📄 File Reference:** See [import_to_wxo.sh](import_to_wxo.sh) for the complete deployment automation script.

**What this script automates:**

**1. User Input Collection:**
- Prompts for WXO instance URL
- Securely prompts for WXO API key
- Validates that both values are provided

**2. Connection Creation (`orchestrate connections add`):**
- Creates a new connection with app-id `wxo_langgraph`
- This connection will store credentials for accessing WXO's model gateway

**3. Connection Configuration:**
- Configures the connection for both `draft` and `live` environments
- Sets connection type as `team` (shared across team members)
- Sets kind as `key_value` (simple key-value credential storage)

**4. Credential Storage:**
- Stores `base_url` and `api_key` for both draft and live environments
- These credentials are securely managed by WXO
- Agent retrieves them at runtime via `RunnableConfig`

**5. Agent Import:**
- Imports the agent using `orchestrate agents import`
- Specifies `--experimental-package-root my_langraph_agent` (agent code directory)
- Specifies `--experimental-config-file my_langraph_agent/agent.yaml` (configuration)

**6. Agent-Connection Linking:**
- Connects the agent to the connection using `orchestrate agents experimental-connect`
- Links agent name `my_langraph_agent` to connection `wxo_langgraph`
- This allows the agent to access the stored credentials

Make the script executable:

```bash
chmod +x import_to_wxo.sh
```

### Step 7: Import the Agent into WXO

Run the setup script:

```bash
./import_to_wxo.sh
```

**What happens when you run this script:**

1. **Interactive Prompts**: You'll be asked to enter:
   - Your WXO instance URL (e.g., `https://your-instance.watsonx.orchestrate.ibm.com`)
   - Your WXO API key (input will be hidden for security)

2. **Connection Creation**: Creates a connection named `wxo_langgraph` that stores your WXO credentials

3. **Environment Configuration**: Sets up the connection for both:
   - **Draft environment**: For development and testing
   - **Live environment**: For production deployment

4. **Credential Storage**: Securely stores your credentials in WXO's connection manager

5. **Agent Import**: Uploads your agent code and configuration to WXO

6. **Connection Linking**: Associates your agent with the connection so it can access credentials at runtime

After successful execution, your agent will be ready to use in the WXO platform!

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

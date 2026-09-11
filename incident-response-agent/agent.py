"""
agent.py  –  Incident Response Agent using langchain deepagents
================================================================
Use case: An incident response assistant that can:
  1. Parse error logs and diagnose issues       (log-parser skill)
  2. Generate Slack posts and action checklists (incident-brief-summarizer skill)

Run:
  pip install -r requirements.txt
  export ANTHROPIC_API_KEY="your-key" (or configure WatsonX/OpenRouter)
  python agent.py
"""

import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import MemorySaver
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_ibm import ChatWatsonx

# Load environment variables from .env file
load_dotenv()


# ─────────────────────────────────────────────────────────────
# 1. MODEL SETUP  – Choose between Anthropic Claude, IBM WatsonX, or OpenRouter
# ─────────────────────────────────────────────────────────────
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "anthropic")  # "anthropic", "watsonx", or "openrouter"

print(f"\n{'='*70}")
print(f"🤖 INCIDENT RESPONSE AGENT - INITIALIZING")
print(f"{'='*70}")

if MODEL_PROVIDER == "watsonx":
    # IBM WatsonX Model Setup
    model_id = os.getenv("WATSON_MODEL_ID", "meta-llama/llama-3-3-70b-instruct")
    print(f"📡 Model Provider: IBM WatsonX")
    print(f"🧠 Model ID: {model_id}")
    
    model = ChatWatsonx(
        model_id=model_id,
        url=os.getenv("WATSON_ML_URL", "https://us-south.ml.cloud.ibm.com"),
        apikey=os.getenv("WATSON_API_KEY"),
        project_id=os.getenv("WATSON_PROJECT_ID"),
        params={
            "decoding_method": os.getenv("WATSON_DECODING_METHOD", "greedy"),
            "temperature": float(os.getenv("WATSON_TEMPERATURE", "0.5")),
            "min_new_tokens": int(os.getenv("WATSON_MIN_NEW_TOKENS", "5")),
            "max_new_tokens": int(os.getenv("WATSON_MAX_NEW_TOKENS", "800")),
            "stop_sequences": ["Human:", "Observation"],
        },
    )
elif MODEL_PROVIDER == "openrouter":
    # OpenRouter Model Setup
    # Supports various models through OpenRouter API
    # Popular options: "openai/gpt-4", "anthropic/claude-3-opus", "meta-llama/llama-3-70b-instruct"
    from langchain_openai import ChatOpenAI
    
    model_id = os.getenv("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet")
    print(f"📡 Model Provider: OpenRouter")
    print(f"🧠 Model ID: {model_id}")
    
    model = ChatOpenAI(
        model=model_id,
        openai_api_key=os.getenv("OPENROUTER_API_KEY"),
        openai_api_base=os.getenv("OPENROUTER_API_BASE", "https://openrouter.ai/api/v1"),
        temperature=float(os.getenv("OPENROUTER_TEMPERATURE", "0.7")),
        max_tokens=int(os.getenv("OPENROUTER_MAX_TOKENS", "4096")),
        model_kwargs={
            "extra_headers": {
                "HTTP-Referer": os.getenv("OPENROUTER_REFERER", "https://github.com/your-repo"),
                "X-Title": os.getenv("OPENROUTER_APP_NAME", "Incident Response Agent"),
            }
        }
    )
else:
    # Anthropic Claude Model Setup (default)
    # Options: "anthropic:claude-haiku-4-5-20251001" (fast + cheap)
    #          "anthropic:claude-sonnet-4-5-20250929" (smarter)
    model_id = os.getenv("ANTHROPIC_MODEL", "anthropic:claude-haiku-4-5-20251001")
    print(f"📡 Model Provider: Anthropic Claude")
    print(f"🧠 Model ID: {model_id}")
    
    model = init_chat_model(model_id)

print(f"{'='*70}\n")


# ─────────────────────────────────────────────────────────────
# 2. SKILLS SETUP
#    Skills live in ./skills/<skill-name>/SKILL.md
#    The agent reads the frontmatter of each SKILL.md at startup,
#    then reads the full file only when a matching task comes in.
# ─────────────────────────────────────────────────────────────
SKILLS_DIR = str(Path(__file__).parent / "skills")


# ─────────────────────────────────────────────────────────────
# 3. BACKEND SETUP
#    FilesystemBackend lets the agent read/write real files on disk.
#    root_dir is the agent's working directory.
# ─────────────────────────────────────────────────────────────
WORKSPACE = str(Path(__file__).parent / "workspace")
os.makedirs(WORKSPACE, exist_ok=True)

backend = lambda runtime: FilesystemBackend(root_dir=WORKSPACE, virtual_mode=True)


# ─────────────────────────────────────────────────────────────
# 4. MCP SERVER SETUP (from environment)
# ─────────────────────────────────────────────────────────────
MCP_SERVER_NAME = os.getenv("MCP_SERVER_NAME", "debug-assistant-mcp")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "")
MCP_SERVER_TRANSPORT = os.getenv("MCP_SERVER_TRANSPORT", "streamable-http")

async def get_mcp_tools():
    """Fetch tools from the configured MCP server using langchain_mcp_adapters."""
    mcp_tools = []
    
    # Skip MCP setup if URL is not configured
    if not MCP_SERVER_URL:
        return mcp_tools
    
    print(f"\n🔌 Connecting to MCP: {MCP_SERVER_NAME}")
    
    try:
        # Create MCP client using langchain_mcp_adapters
        mcp_client = MultiServerMCPClient(
            {
                MCP_SERVER_NAME: {
                    "url": MCP_SERVER_URL,
                    "transport": MCP_SERVER_TRANSPORT,
                }
            }
        )
        
        # Get tools from MCP server
        async_mcp_tools = await mcp_client.get_tools()
        
        print(f"✅ Loaded {len(async_mcp_tools)} MCP tools")
        
        # Wrap async tools to make them sync-compatible for deepagents
        from langchain_core.tools import StructuredTool
        from functools import wraps
        import inspect
        
        for async_tool in async_mcp_tools:
            tool_name = getattr(async_tool, 'name', 'unknown')
            tool_desc = getattr(async_tool, 'description', '')
            
            # Create a sync wrapper for the async tool
            def make_sync_wrapper(atool):
                async def async_wrapper(**kwargs):
                    """Async wrapper that calls the MCP tool."""
                    try:
                        result = await atool.ainvoke(kwargs)
                        return result
                    except Exception as e:
                        error_msg = f"MCP tool error: {str(e)}"
                        print(f"❌ {error_msg}")
                        return error_msg
                
                # Create a sync version that runs the async function
                def sync_wrapper(**kwargs):
                    """Sync wrapper that runs async tool in event loop."""
                    try:
                        # Try to get existing event loop
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # If loop is running, create a new task
                            import concurrent.futures
                            with concurrent.futures.ThreadPoolExecutor() as executor:
                                future = executor.submit(asyncio.run, async_wrapper(**kwargs))
                                return future.result()
                        else:
                            # If no loop is running, use asyncio.run
                            return loop.run_until_complete(async_wrapper(**kwargs))
                    except RuntimeError:
                        # No event loop, create one
                        return asyncio.run(async_wrapper(**kwargs))
                
                return sync_wrapper, async_wrapper
            
            sync_func, async_func = make_sync_wrapper(async_tool)
            
            # Create a new StructuredTool with both sync and async support
            wrapped_tool = StructuredTool(
                name=tool_name,
                description=tool_desc,
                func=sync_func,
                coroutine=async_func,
                args_schema=getattr(async_tool, 'args_schema', None)
            )
            
            mcp_tools.append(wrapped_tool)
                
    except Exception as e:
        print(f"⚠️  MCP connection failed: {e}")
    
    return mcp_tools


# ─────────────────────────────────────────────────────────────
# 5. MEMORY (optional but useful for multi-turn conversations)
# ─────────────────────────────────────────────────────────────
checkpointer = MemorySaver()


# ─────────────────────────────────────────────────────────────
# 6. CREATE THE DEEP AGENT WITH MCP TOOLS
# ─────────────────────────────────────────────────────────────
# Get MCP tools synchronously
mcp_tools = asyncio.run(get_mcp_tools())

print(f"📚 Loading skills from: {SKILLS_DIR}")
# List available skills
skill_folders = [d for d in Path(SKILLS_DIR).iterdir() if d.is_dir() and (d / "SKILL.md").exists()]
print(f"✅ Found {len(skill_folders)} skill(s):")
for skill_folder in skill_folders:
    print(f"   • {skill_folder.name}")
print()

agent = create_deep_agent(
    model=model,
    backend=backend,
    skills=[SKILLS_DIR],          # where to find skill folders
    tools=mcp_tools,              # Add MCP tools from configured server
    checkpointer=checkpointer,    # enables conversation memory
    system_prompt=(
        "You are an incident response assistant. You help on-call engineers:\n"
        "IMPORTANT: You MUST use the available skills for every incident analysis:\n"
        "- ALWAYS use log-parser skill to analyze error logs\n"
        "- ALWAYS use incident-brief-summarizer skill to create incident reports\n"
        "- Do NOT skip skills or provide direct responses without using them\n\n"
        "Your goal: Get the engineer from 'something broke' to 'here's what to do' in 90 seconds.\n"
        "Always be concise, calm, and actionable"
    ),
)


# ─────────────────────────────────────────────────────────────
# 7. HELPER – run one query and print streamed output
# ─────────────────────────────────────────────────────────────
def ask(question: str, thread_id: str = "default"):
    """Send a message to the agent and stream the response."""
    print(f"\n{'='*60}")
    print(f"You: {question}")
    print("="*60)

    config = {"configurable": {"thread_id": thread_id}}
    inputs = {"messages": [{"role": "user", "content": question}]}

    # stream_mode="updates" prints each step as it happens
    for chunk in agent.stream(inputs, config=config, stream_mode="updates"):
        for node, updates in chunk.items():
            if updates and "messages" in updates:
                # Handle Overwrite object - get the actual messages
                messages = updates["messages"]
                if hasattr(messages, "value"):
                    messages = messages.value
                
                # Ensure messages is iterable
                if not isinstance(messages, list):
                    messages = [messages]
                
                for msg in messages:
                    # Check if this is a tool call (skill execution)
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        for tool_call in msg.tool_calls:
                            tool_name = tool_call.get("name", "unknown")
                            print(f"\n🎯 SKILL CALLED: {tool_name}")
                            if "args" in tool_call:
                                print(f"   Arguments: {tool_call['args']}")
                    
                    # Check if this is a tool response (skill result)
                    if hasattr(msg, "__class__") and "Tool" in msg.__class__.__name__:
                        print(f"\n✅ SKILL COMPLETED: {getattr(msg, 'name', 'unknown')}")
                        if hasattr(msg, "content"):
                            content_preview = str(msg.content)[:200]
                            print(f"   Result preview: {content_preview}...")
                    
                    # Only print AI messages (not human messages)
                    if hasattr(msg, "__class__") and "AI" in msg.__class__.__name__:
                        if hasattr(msg, "content") and isinstance(msg.content, str):
                            if msg.content.strip():
                                print(f"\n🤖 Agent Response:\n{msg.content}")


# ─────────────────────────────────────────────────────────────
# 8. DEMO QUERIES  – shows skills and MCP tools in action
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"\n{'='*70}")
    print(f"🚨 INCIDENT RESPONSE AGENT - INTERACTIVE MODE")
    print(f"{'='*70}\n")
    
    # Get log file path from user
    log_file_path = input("📁 Enter the path to the log file: ").strip()
    
    # Validate and read log file
    try:
        # Handle relative and absolute paths
        if not os.path.isabs(log_file_path):
            log_file_path = Path(__file__).parent / log_file_path
        else:
            log_file_path = Path(log_file_path)
        
        if not log_file_path.exists():
            print(f"❌ Error: Log file not found at {log_file_path}")
            exit(1)
        
        with open(log_file_path, 'r') as f:
            log_content = f.read()
        
        print(f"✅ Successfully loaded log file: {log_file_path}")
        print(f"📊 Log file size: {len(log_content)} characters\n")
        
    except Exception as e:
        print(f"❌ Error reading log file: {e}")
        exit(1)
    
    # Get user query
    print("💬 Enter your query about the logs:")
    print("   (e.g., 'What caused this error?', 'Analyze what broke and give me a Slack post + action checklist')")
    user_query = input("Query: ").strip()
    
    if not user_query:
        print("❌ Error: Query cannot be empty")
        exit(1)
    
    # Combine log content with user query
    combined_message = (
        f"{user_query}\n\n"
        f"Here are the logs from {log_file_path.name}:\n\n"
        f"```\n{log_content}\n```"
    )
    
    # Send to agent
    ask(combined_message, thread_id="incident-response-session")
    
    print(f"\n{'='*70}")
    print(f"✅ ANALYSIS COMPLETE")
    print(f"{'='*70}\n")


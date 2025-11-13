# RAG-LangFlow-and-watsonx-Orchestrate
Building a RAG Pipeline with LangFlow and watsonx Orchestrate

## What You'll Build

A custom RAG (Retrieval-Augmented Generation) agent that:
- Uses **LangFlow** to visually design a document retrieval pipeline
- Connects to **watsonx Orchestrate** via MCP protocol
- Answers questions based on your private documents

## Prerequisites

Before starting, complete these tutorials:
1. ✅ [Getting Started with watsonx Orchestrate ADK](https://developer.ibm.com/tutorials/getting-started-with-watsonx-orchestrate/)
2. ✅ [Connecting to MCP tools with watsonx Orchestrate](https://developer.ibm.com/tutorials/connect-mcp-tools-watsonx-orchestrate-adk/)

You should have:
- watsonx Orchestrate ADK installed (`orchestrate --version`)
- Docker Desktop running
- Python 3.11+
- Node.js 18+
- API key for watsonx.ai or OpenAI

## Why This Approach?

watsonx Orchestrate has a built-in Knowledge feature for standard RAG use cases. This tutorial shows you how to build **custom RAG pipelines** when you need:
- Visual pipeline design with LangFlow
- Custom retrieval strategies (hybrid search, reranking)
- Integration with your own vector database
- Cross-platform reusability (not just Orchestrate)

For standard use cases, see the [ibm_knowledge example](https://github.com/IBM/ibm-watsonx-orchestrate-adk/tree/main/examples/agent_builder/ibm_knowledge).


## Quick Start

### Automated Setup (Recommended)

Run the setup script to automate environment setup:

```bash
git clone <repo-url>
./setup.sh
```

Then edit `.env` with your API credentials and you're ready to go!

### Manual Setup

1. **Clone the repository:**
   ```bash
   git clone <repo-url>
   ```

2. **Create virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure API credentials:**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and add **either** watsonx.ai **or** OpenAI credentials:
   
   **Option A: watsonx.ai (recommended)**
   ```bash
   WATSONX_API_KEY=your_api_key_here
   WATSONX_PROJECT_ID=your_project_id_here
   ```
   
   **Option B: OpenAI**
   ```bash
   OPENAI_API_KEY=sk-proj-your_key_here
   ```
   
   ⚠️ **Get credentials:**
   - watsonx.ai: [IBM Cloud Console](https://cloud.ibm.com) → watsonx.ai → API Keys
   - OpenAI: [platform.openai.com/api-keys](https://platform.openai.com/api-keys)

5. **Start infrastructure:**
   ```bash
   docker-compose up -d
   ```

6. **Follow the tutorial:**
   See [docs/tutorial.md](docs/tutorial.md) for the complete guide.

**Having issues?** See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)

## Learning Path

This tutorial is part of the watsonx Orchestrate learning path:

1. **Beginner**: [Getting Started with ADK](https://developer.ibm.com/tutorials/getting-started-with-watsonx-orchestrate/)
2. **Beginner**: [MCP Tools Connection](https://developer.ibm.com/tutorials/connect-mcp-tools-watsonx-orchestrate-adk/)
3. **Intermediate**: **This Tutorial** ← You are here
4. **Advanced**: [Agent Observability with LangFuse](https://developer.ibm.com/tutorials/agentsops-telemetry-langfuse-watsonx-orchestrate/)

## Support

- IBM Developer Community: [developer.ibm.com](https://developer.ibm.com)
- watsonx Orchestrate Docs: [developer.watson-orchestrate.ibm.com](https://developer.watson-orchestrate.ibm.com)


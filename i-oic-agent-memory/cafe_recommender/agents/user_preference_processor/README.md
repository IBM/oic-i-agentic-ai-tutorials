# User Preference Processor Agent

A custom LangGraph agent specialized in storing and retrieving user preferences (e.g., location settings) with memory storage capabilities.

## Overview

The User Preference Processor is a custom LangGraph agent that handles preference storage operations. It acts as a collaborator to the Main Orchestrator Agent, maintaining context across conversations through watsonx Orchestrate's memory service.

## Configuration

- **Name**: `user_preference_processor`
- **Type**: Custom LangGraph agent
- **Framework**: LangGraph
- **Entrypoint**: `user_preference_processor:create_agent`
- **Checkpointer**: Memory (in-memory state persistence)

## Capabilities

- **Memory Storage**: Stores user preferences (like location) for context and history.
- **Context-Aware Retrieval**: Searches for related previous preference settings.
- **Cross-Session Persistence**: Memory persists across different user conversations.

## Deployment

### Prerequisites

```bash
# Install dependencies (includes memory SDK)
cd cafe_recommender/agents/user_preference_processor
pip install -r requirements.txt
```

**Required dependencies:**
- `langgraph>=0.2.0` - LangGraph framework
- `langchain-core>=0.3.0` - Core LangChain components
- `ibm-watsonx-orchestrate-sdk>=0.7.0` - Memory storage SDK

### Deploy to watsonx Orchestrate

```bash
# Import the agent
orchestrate agents import \
  --experimental-package-root agents/user_preference_processor

# The agent will be automatically available in Orchestrate
```

## Local Testing

Test the agent locally before deployment:

```bash
cd cafe_recommender/agents/user_preference_processor
python user_preference_processor.py
```

## Memory Features

### How Memory Works

The agent stores user preference settings in memory with:
- **Memory Type**: `preference`
- **Content**: User's preferences or location settings
- **Metadata**: Source (`user_preference_processor`)

### Memory Storage

```python
# Automatically stores preference
client.memory.add_messages(
    messages=[{"role": "user", "content": user_text}],
    memory_type="preference",
    infer=False,
    metadata={"source": "user_preference_processor"}
)
```

### Context Retrieval

```python
# Searches for related previous preferences
search_response = client.memory.search(
    query=user_text,
    limit=3,
    memory_type="preference"
)
```

## State Persistence

### Current: Memory
```yaml
checkpointer:
  type: memory
```
- In-memory storage
- Resets on restart
- Good for development

### PostgreSQL (Production)
```yaml
checkpointer:
  type: postgres
  connection_string_key: db_connection_string
```
- Persistent across restarts

## Troubleshooting

### Import fails
- Ensure all dependencies are in `requirements.txt`
- Verify entrypoint path: `user_preference_processor:create_agent`

### Agent not found by orchestrator
- Deploy `user_preference_processor` before `cafe_recommendation_agent`
- Verify agent name matches in orchestrator's collaborators list

## Resources

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [watsonx Orchestrate Custom Agents](https://developer.watson-orchestrate.ibm.com/agents/import_agent)
- [watsonx Orchestrate Memory SDK](https://ibm.github.io/watsonx-orchestrate-python-sdk/)
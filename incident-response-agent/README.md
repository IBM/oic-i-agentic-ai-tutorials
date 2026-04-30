# Incident Response Agent

An AI-powered incident response assistant built with LangChain's `deepagents` library. Helps on-call engineers diagnose production issues and generate actionable incident briefs in 90 seconds.

## 🎯 Use Case

**The Story:** A developer pushes a bad deploy. The API error rate spikes. On-call engineer gets paged. They paste the logs + alert into the agent → get a diagnosis + Slack post in 90 seconds.

## 🏗️ Project Structure

```
incident-response-agent/
├── agent.py                                    # Main entry point
├── requirements.txt                            # Python dependencies
├── .env.example                                # Environment configuration template
├── workspace/                                  # Agent's read/write workspace (auto-created)
└── skills/
    ├── log-parser/                             # Skill 1: Diagnose issues from logs
    │   ├── SKILL.md                            # Skill instructions
    │   └── references/
    │       └── common-errors.md                # Error patterns lookup table
    └── incident-brief-summarizer/              # Skill 2: Generate incident briefs
        ├── SKILL.md                            # Skill instructions
        └── references/
            ├── slack-post.md                   # Slack post template + examples
            └── checklist.md                    # Action checklist template + examples
```

## 🚀 How It Works

### Skills Overview

| Skill | Trigger | What it does |
|-------|---------|--------------|
| **log-parser** | "something broke", "we have an incident", "here are the logs" | Reads error logs, identifies the issue, checks deploy history, outputs diagnosis |
| **incident-brief-summarizer** | "write the Slack post", "I need an incident update" | Takes diagnosis and generates copy-paste ready Slack post + action checklist |

### Workflow

1. **Engineer pastes log file with query** → Agent triggers `log-parser` skill
2. **log-parser analyzes** → Finds error, checks deploy timing, assesses confidence
3. **Outputs diagnosis** → What broke, when, likely cause, top 3 actions
4. **Agent triggers** → `incident-brief-summarizer` skill
5. **Generates briefs** → Slack post (for team) + Action checklist (for engineer)
6. **Engineer copies** → Paste to Slack, follow checklist, resolve incident

### Progressive Disclosure

The agent uses **progressive disclosure** for efficiency:
1. At startup → reads only the frontmatter `description` of every SKILL.md
2. When a user prompt matches a skill → reads the full SKILL.md
3. Follows the instructions (which reference references and lookup tables)

## 📦 Setup & Run

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and add your API keys and configuration
# Required: ANTHROPIC_API_KEY, WATSON_API_KEY, or OPENROUTER_API_KEY (depending on MODEL_PROVIDER)
# Optional: MCP_SERVER_URL for MCP server integration
```

### 3. Run the Agent

```bash
python agent.py
```

The agent will prompt you for:
1. **Log file path**: Enter the path to your log file (e.g., `sample_logs.txt` or `/path/to/logs.txt`)
2. **Your query**: Enter your question about the logs (e.g., "What caused this error?" or "Create incident report")

The agent will read the log file, attach its content to your query, and analyze it using the available skills.

**Example:**
```
📁 Enter the path to the log file: sample_logs.txt
✅ Successfully loaded log file: sample_logs.txt
📊 Log file size: 1234 characters

💬 Enter your query about the logs:
Query: Diagnose the issue and create an incident report
```

## ⚙️ Configuration

The agent supports three model providers and optional MCP server integration:

### Model Providers

**Option 1: Anthropic Claude (Default)**
```bash
MODEL_PROVIDER=anthropic
ANTHROPIC_API_KEY=your-anthropic-api-key
ANTHROPIC_MODEL=anthropic:claude-haiku-4-5-20251001
```

**Option 2: IBM WatsonX**
```bash
MODEL_PROVIDER=watsonx
WATSON_API_KEY=your-watson-api-key
WATSON_ML_URL=https://us-south.ml.cloud.ibm.com
WATSON_PROJECT_ID=your-project-id
WATSON_MODEL_ID=meta-llama/llama-3-3-70b-instruct
```

**Option 3: OpenRouter**
```bash
MODEL_PROVIDER=openrouter
OPENROUTER_API_KEY=your-openrouter-api-key
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
OPENROUTER_API_BASE=https://openrouter.ai/api/v1
OPENROUTER_TEMPERATURE=0.7
OPENROUTER_MAX_TOKENS=4096
```

OpenRouter provides access to multiple AI models through a single API:
- Get your API key from: https://openrouter.ai/keys
- Browse available models: https://openrouter.ai/models
- Popular options: `anthropic/claude-3.5-sonnet`, `openai/gpt-4-turbo`, `meta-llama/llama-3-70b-instruct`

### MCP Server Integration (Optional)

To enable MCP (Model Context Protocol) tools for additional debugging capabilities:
```bash
MCP_SERVER_NAME=debug-assistant-mcp
MCP_SERVER_URL=https://your-mcp-server.example.com/mcp
MCP_SERVER_TRANSPORT=streamable-http
```

Leave `MCP_SERVER_URL` empty to disable MCP tools. You can integrate any MCP-compatible server for extended functionality such as ticket creation, log analysis, or other debugging tools.

See [`.env.example`](.env.example) for all available configuration options.

## 📝 Example Usage

### Scenario: Payment Service Error

**Input:**
```
We have an incident! Here are the logs:

[2024-01-15 03:04:12] ERROR payment-service: NullPointerException at DiscountCalculator.java:47
[2024-01-15 03:04:13] ERROR payment-service: Failed to process checkout request
[2024-01-15 03:04:14] ERROR payment-service: NullPointerException at DiscountCalculator.java:47

Deploy history:
[2024-01-15 03:01:00] payment-service v2.5.0 deployed
```

**Output:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📢 SLACK POST  (copy → #incidents)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔴 Payment service is returning 500 errors — checkouts are failing

**Started:** 2024-01-15 03:04 UTC
**Impact:** ~30% of checkout requests failing (est. 200 users affected)
**Status:** Identified — rolling back deploy

**What we know:**
- First error at 03:04, 3 minutes after payment-service deploy
- NullPointerException in new discount calculation code
- Error rate: 30% of requests (intermittent, not all users)

**Next steps:**
- Rolling back payment-service to v2.4.1 (ETA: 5 min)
- Monitoring error rate after rollback

**Owned by:** [your-name]
**Next update:** 03:20 UTC (15 min)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ ACTION CHECKLIST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Immediate Actions
- [ ] Rollback payment-service to v2.4.1
      Why: Error started 3 min after deploy, high confidence it's the cause

- [ ] Monitor error rate for 5 minutes after rollback
      Why: Confirm rollback fixed the issue before closing incident

- [ ] Check if any payments are stuck in "pending" state
      Why: Failed requests may have left incomplete transactions

## If That Doesn't Work
- [ ] Check database connection pool status
      Why: 500 errors can also be caused by exhausted DB connections

- [ ] Page payment-service owner (@jane-doe)
      Why: If rollback didn't help, need domain expert to investigate

## After Resolution
- [ ] Post update to Slack in 15 minutes
- [ ] Open a post-mortem ticket once resolved
```

## 🛠️ Skills Deep Dive

### log-parser Skill

**Purpose:** Diagnose production issues from error logs

**Process:**
1. **Find the Error** → Scan for ERROR, FATAL, Exception, 5xx status codes
2. **Check the Deploy** → Correlate error timestamps with deploy history
3. **Output Diagnosis** → Structured format with confidence level

**References:**
- [`common-errors.md`](skills/log-parser/references/common-errors.md) - Lookup table for HTTP errors, runtime errors, and deploy patterns

### incident-brief-summarizer Skill

**Purpose:** Generate copy-paste ready incident communications

**Process:**
1. **Read Diagnosis** → Extract key facts from log-parser output
2. **Write Slack Post** → Using template, create team update
3. **Write Checklist** → Generate prioritized action items
4. **Output Both** → Clearly separated, ready to use

**References:**
- [`slack-post.md`](skills/incident-brief-summarizer/references/slack-post.md) - Slack post format with severity emojis
- [`checklist.md`](skills/incident-brief-summarizer/references/checklist.md) - Action checklist patterns for common scenarios

## 🎯 Design Principles

1. **Speed** → 90 seconds from logs to action plan
2. **Clarity** → Plain English, no jargon, calm tone
3. **Actionable** → Every output is copy-paste ready
4. **Honest** → Clear confidence levels (High/Medium/Low)
5. **Practical** → Designed for 3 AM incidents

## 🔧 Customization

### Adding New Error Patterns

Edit [`skills/log-parser/references/common-errors.md`](skills/log-parser/references/common-errors.md) to add:
- New HTTP error codes
- Application-specific errors
- Custom deploy patterns

### Modifying References

Edit references in [`skills/incident-brief-summarizer/references/`](skills/incident-brief-summarizer/references/):
- Adjust Slack post format for your team's style
- Add company-specific checklist items
- Customize severity levels

### Adding New Skills

Create a new folder in `skills/` with a `SKILL.md` file:

```markdown
---
name: my-skill
description: When to use this skill (triggers)
---

# my-skill

## Instructions
Step-by-step instructions the agent follows
```

## 📚 Additional Resources

- [LangChain DeepAgents Documentation](https://python.langchain.com/docs/deepagents)
- [MCP Protocol Specification](https://modelcontextprotocol.io/)
- [Anthropic Claude API](https://docs.anthropic.com/)

---

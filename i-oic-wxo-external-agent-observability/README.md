# Annualized Rate of Return — External Agent for watsonx Orchestrate

A LangGraph ReAct agent, deployed **outside** watsonx Orchestrate (wxO) on **IBM Cloud Code Engine**, exposed over the **Agent-to-Agent (A2A) protocol v0.3.0**, registered in wxO as an external collaborator, and instrumented with standard **OpenTelemetry** so every conversation, LLM call, and tool call shows up in the wxO Analytics dashboard next to natively built agents.

`agent.py` and `tools.py` are ordinary LangGraph code with no wxO or OpenTelemetry imports. All registration and telemetry plumbing lives in `server.py` and `wxo_otel.py`. See [`article-wxo-agentic-control-plane-v2.md`](article-wxo-agentic-control-plane-v2.md) for the full write-up of why and how this works.

This README walks through **deploying the agent to IBM Cloud Code Engine** and then **verifying it end to end through the wxO control plane** — both by tailing Code Engine logs and by reading the trace tree in the wxO UI.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  IBM Cloud Code Engine  (us-south)                                      │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  FastAPI A2A Server  (server.py)                                  │  │
│  │    GET  /.well-known/agent.json        AgentCard (A2A spec)       │  │
│  │    GET  /.well-known/agent-card.json   AgentCard (wxO ADK path)   │  │
│  │    GET  /health                        liveness probe             │  │
│  │    POST /  JSON-RPC 2.0   message/send · message/stream ·         │  │
│  │            tasks/get · tasks/cancel                               │  │
│  │  ┌─────────────────────────────────────────────────────────────┐  │  │
│  │  │  LangGraph ReAct agent  (agent.py)  ·  Gemini 2.5 Flash     │  │  │
│  │  │  Tool: calculate_annualized_return  (tools.py)              │  │  │
│  │  └─────────────────────────────────────────────────────────────┘  │  │
│  │  ┌─────────────────────────────────────────────────────────────┐  │  │
│  │  │  OTel telemetry  (wxo_otel.py)                              │  │  │
│  │  │  ASGI middleware → IAM token exchange → OTLP/HTTP exporter  │  │  │
│  │  └─────────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
          ▲  A2A v0.3.0 / JSON-RPC 2.0          │  OTLP/HTTP traces
          │  (wxO calls the agent)              ▼  (agent pushes to wxO)
┌─────────────────────────────────────────────────────────────────────────┐
│  watsonx Orchestrate — Agentic Control Plane                            │
│  Registered external agent · Collaborator for native agents             │
│  Analyze → Overview · Agent dashboard · Conversations · Trace view      │
└─────────────────────────────────────────────────────────────────────────┘
```

## Repository layout

| File | Role |
|---|---|
| `agent.py` | LangGraph ReAct agent (Gemini 2.5 Flash) — untouched by telemetry |
| `tools.py` | `calculate_annualized_return` tool — untouched by telemetry |
| `a2a_types.py` | A2A v0.3.0 Pydantic models (AgentCard, Task, Message, JSON-RPC envelopes) |
| `server.py` | FastAPI A2A server: JSON-RPC dispatch, AgentCard endpoint, health probe, bearer-token gate |
| `wxo_otel.py` | wxO telemetry: ASGI trace middleware, IAM token exchange, `TracerProvider`, span emission |
| `main.py` | Original interactive CLI for the agent (no A2A, no telemetry) |
| `Dockerfile` | Multi-stage `python:3.12-slim` image, non-root user |
| `deploy.sh` | End-to-end IBM Cloud Code Engine deployment script |
| `agent.yaml` | wxO registration spec (YAML import) |
| `.well-known/agent.json` | Static fallback AgentCard (also served dynamically by `server.py`) |
| `.env.example` | Environment variable reference |

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.12+ | local development / testing only |
| Docker (or OrbStack) with a running daemon | image build |
| `ibmcloud` CLI | `curl -fsSL https://clis.cloud.ibm.com/install/osx \| sh` |
| Code Engine plugin | `ibmcloud plugin install code-engine` |
| Container Registry plugin | `ibmcloud plugin install container-registry` |
| An IBM Cloud account with permission to create resource groups, ICR namespaces, and Code Engine projects | https://cloud.ibm.com |
| A watsonx Orchestrate instance (SaaS on IBM Cloud) | with the `orchestrate` ADK CLI configured against it |
| A Google Gemini API key | https://aistudio.google.com/app/apikey |

---

## Part 1 — Run it locally first

Confirm the agent and the A2A server work before touching the cloud.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env — set at minimum:
#   GOOGLE_API_KEY=<your-gemini-key>
#   AGENT_BASE_URL=http://localhost:8080
#   AGENT_API_KEY=<any secret string you choose>

set -a && source .env && set +a
uvicorn server:app --host 0.0.0.0 --port 8080 --reload
```

In another terminal:

```bash
curl http://localhost:8080/health

curl http://localhost:8080/.well-known/agent.json | python3 -m json.tool

curl -s -X POST http://localhost:8080/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${AGENT_API_KEY}" \
  -d '{
    "jsonrpc": "2.0",
    "id": "local-001",
    "method": "message/send",
    "params": {
      "message": {
        "kind": "message",
        "role": "user",
        "messageId": "msg-001",
        "parts": [{"kind": "text", "text": "I invested $10,000 and it is now $13,500 after 18 months. What is my annualized return?"}]
      }
    }
  }' | python3 -m json.tool
```

Do not set `WXO_AGENT_ID` / `WXO_TENANT_ID` / `WXO_API_KEY` / `OTEL_EXPORT_URL` locally unless you want to send test traffic straight into wxO — the middleware requires all four of these to be non-empty to even start (see [Note on bootstrapping telemetry](#note-on-bootstrapping-telemetry) below), so leave telemetry disabled for local runs by simply not sourcing that section of `.env`, or run without telemetry env vars set at all if `server.py` in your checkout makes them optional for local dev.

---

## Part 2 — Deploy to IBM Cloud Code Engine

### Step 1 — Generate the API keys you'll need

```bash
ibmcloud login --sso

# Platform key — used to log in, push to ICR, and pull the image into Code Engine
ibmcloud iam api-key-create wxo-a2a-deploy-key \
  -d "A2A agent deployment key" \
  --file wxo-a2a-deploy-key.json

# Dedicated key — used only for wxO trace ingestion (kept separate on purpose)
ibmcloud iam api-key-create wxo-telemetry-key \
  -d "wxO telemetry trace ingestion" \
  --file wxo-telemetry-key.json

# Bearer token that will protect your A2A endpoint — you choose this value
openssl rand -hex 32
```

Keep both `*.json` key files and the generated token out of git — see [Handling secrets](#handling-secrets).

### Step 2 — A note on bootstrapping telemetry

`WxoA2ATraceMiddleware` reads `WXO_TENANT_ID`, `WXO_AGENT_ID`, and `OTEL_EXPORT_URL` **when the app starts**, not lazily on first request — if any of them is empty the process fails at startup and the Code Engine revision never becomes Ready. `deploy.sh` enforces the same requirement before it will even build the image.

This creates a chicken-and-egg problem: you need the app's public URL to register it in wxO and get `WXO_AGENT_ID`, but you need `WXO_AGENT_ID` to deploy the app. The way out is to **deploy twice**:

1. **First deploy** — with placeholder (non-empty, but not-yet-real) values for the four telemetry variables, just to satisfy the startup check and get the app running and its URL assigned.
2. **Register** the running agent with wxO (Part 3) to obtain the real `WXO_AGENT_ID` and `WXO_TENANT_ID`.
3. **Update** the same Code Engine app with the real telemetry values (Part 4) — this is a config-only `ibmcloud ce app update`, no rebuild needed.

### Step 3 — Export the variables for the first deploy

```bash
export IBMCLOUD_API_KEY="<apikey from wxo-a2a-deploy-key.json>"
export GOOGLE_API_KEY="<your-gemini-api-key>"
export AGENT_API_KEY="<the hex token from openssl rand -hex 32>"

# Placeholders only — just need to be non-empty for the first deploy.
# Real values go in during Part 4, after registration.
export ENVIRONMENT_NAME="draft"          # must be exactly "draft" or "live"
export WXO_API_KEY="pending"
export WXO_TENANT_ID="pending"
export WXO_AGENT_ID="pending"
export OTEL_EXPORT_URL="https://pending.example.com/v1/orchestrate/inject/traces"
```

> Tip: put these in `.env` and run `set -a && source .env && set +a` — `deploy.sh` also auto-sources a `.env` file in the same directory if present.

### Step 4 — Run the deployment script

```bash
chmod +x deploy.sh
./deploy.sh
```

`deploy.sh` will, in order:

1. Log in to IBM Cloud with `IBMCLOUD_API_KEY`.
2. Create the resource group (default `itrhsp`, override with `RESOURCE_GROUP`) if it doesn't exist, and target it.
3. Log in to IBM Container Registry (`us.icr.io`) and create the ICR namespace (default `itrhsp-a2a-agents`, override with `CR_NAMESPACE`) if it doesn't exist.
4. Build a `linux/amd64` Docker image (tagged with a timestamp) and push it to ICR.
5. Create or select the Code Engine project (default `wxo-a2a-agents`, override with `CE_PROJECT_NAME`).
6. Create the `icr-secret` registry pull secret if it doesn't exist.
7. Create (or update, on subsequent runs) the Code Engine application `annualized-return-agent` (override with `CE_APP_NAME`), with `--min-scale 1 --max-scale 5 --cpu 1 --memory 4G`.
8. Poll for up to 5 minutes until the revision is Ready, then print the public URL.

**Expected output:**

```
✅  Deployment complete!
    App URL       : https://annualized-return-agent.<hash>.us-south.codeengine.appdomain.cloud
    Agent card    : https://annualized-return-agent.<hash>.us-south.codeengine.appdomain.cloud/.well-known/agent.json
    Health check  : https://annualized-return-agent.<hash>.us-south.codeengine.appdomain.cloud/health
    A2A endpoint  : https://annualized-return-agent.<hash>.us-south.codeengine.appdomain.cloud/
```

If the app never reaches Ready, check `ibmcloud ce app logs --name annualized-return-agent` and `ibmcloud ce app events --name annualized-return-agent` — a missing/empty telemetry variable (Step 3) is the most common cause of a crash loop at this stage.

### Step 5 — Smoke-test the deployed agent

```bash
APP_URL="https://annualized-return-agent.<hash>.us-south.codeengine.appdomain.cloud"

curl "${APP_URL}/health"

curl "${APP_URL}/.well-known/agent.json" | python3 -m json.tool

curl -s -X POST "${APP_URL}/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${AGENT_API_KEY}" \
  -d '{
    "jsonrpc": "2.0",
    "id": "smoke-001",
    "method": "message/send",
    "params": {
      "message": {
        "kind": "message",
        "role": "user",
        "messageId": "msg-smoke-001",
        "parts": [{"kind": "text", "text": "I invested $10,000 and it is now $13,500 after 18 months. What is my annualized return?"}]
      }
    }
  }' | python3 -m json.tool
```

A successful response returns a completed `Task` with the agent's answer in its `artifacts`. At this point telemetry is still pointed at placeholder values — no trace will reach wxO, and that's expected.

---

## Part 3 — Register the agent with watsonx Orchestrate

### Option A — Auto-discovery (fastest)

```bash
orchestrate agents discover -u "${APP_URL}"
```

The ADK CLI fetches `/.well-known/agent-card.json` (both that path and `/.well-known/agent.json` are served by `server.py`) and registers the agent automatically.

### Option B — YAML import (declarative / GitOps-friendly)

1. Edit [`agent.yaml`](agent.yaml):
   - `api_url` → your `APP_URL` from Step 4 above
   - `auth_config.token` → your `AGENT_API_KEY` value
2. Import it:

```bash
orchestrate agents import -f agent.yaml
```

### After registration

Either method prints an **Agent ID** (a UUID). Copy it — it is the identity the control plane uses to route to this agent, expose it as a collaborator, and attribute telemetry, and you need it in the next part.

---

## Part 4 — Wire up real telemetry and redeploy

### Step 1 — Collect the real identifiers

| Variable | Where to find it |
|---|---|
| `WXO_AGENT_ID` | Printed by `orchestrate agents discover` / `import` in Part 3 |
| `WXO_TENANT_ID` | wxO UI → Profile → About → CRN, formatted `<account-id>_<instance-id>` |
| `OTEL_EXPORT_URL` | `https://api.<region>.watson-orchestrate.cloud.ibm.com/instances/<instance-id>/v1/orchestrate/inject/traces` |
| `WXO_API_KEY` | The apikey value inside `wxo-telemetry-key.json` from Part 2 Step 1 |

### Step 2 — Update the running Code Engine app

This is a configuration-only change — no image rebuild:

```bash
ibmcloud ce app update --name annualized-return-agent \
  --env WXO_AGENT_ID="${WXO_AGENT_ID}" \
  --env WXO_TENANT_ID="${WXO_TENANT_ID}" \
  --env ENVIRONMENT_NAME="draft" \
  --env WXO_API_KEY="${WXO_API_KEY}" \
  --env OTEL_EXPORT_URL="${OTEL_EXPORT_URL}"
```

`TOKEN_URL` (`https://iam.cloud.ibm.com/identity/token`) is already set by `deploy.sh` on every deploy — it does not need to be repeated here unless you are targeting a non-SaaS wxO instance.

Wait for the new revision to become Ready:

```bash
ibmcloud ce app get --name annualized-return-agent
```

---

## Part 5 — Test and view logs through the wxO control plane

There are two complementary ways to confirm telemetry is flowing: the Code Engine application log, and the wxO Analytics UI itself.

### 1. Send a test conversation

Either call the A2A endpoint directly (same `curl` as Part 2 Step 5), or open the wxO chat UI, start (or continue) a conversation with an orchestrator agent that has this agent registered as a collaborator, and ask:

> *"I invested $10,000 and it is now $13,500 after 18 months. What is my annualized return?"*

### 2. Confirm the trace was queued, from Code Engine logs

```bash
ibmcloud ce app logs --name annualized-return-agent --follow
```

Within a few seconds of the request completing, look for a line like:

```
wxO trace queued trace_id=<32-hex> thread_id=<uuid> status=success
```

This line is printed by `WxoA2ATraceMiddleware` in `wxo_otel.py` right after the root span closes and the batch is handed to the exporter. If it never appears, telemetry isn't flowing — jump to [Troubleshooting](#troubleshooting) below before checking the UI.

Other useful log commands:

```bash
ibmcloud ce app logs --name annualized-return-agent --tail 100
ibmcloud ce app logs --name annualized-return-agent --previous   # last crashed container
```

### 3. Confirm the trace in the wxO control plane UI

In the wxO UI, go to **Analyze** and look at three altitudes:

1. **Overview** — the tenant-wide analytics dashboard. The external agent's conversation volume appears here alongside native wxO agents.
2. **Annualized Return Agent → Agent dashboard** — per-agent token consumption, tool-usage counts, latency, and feedback for this agent specifically.
3. **Annualized Return Agent → Conversations** — pick the conversation you just created. Opening it shows the full trace tree:

```
invoke_agent annualized_return_agent            ← root span (SERVER), one per A2A request
  ├─ agent.graph                                ← the whole LangGraph invoke() call
  ├─ gen_ai.chat → calculate_annualized_return   ← LLM turn that decided to call the tool
  ├─ tool_call calculate_annualized_return        ← the tool call, with its JSON output
  └─ gen_ai.chat                                  ← LLM turn that wrote the final answer
```

The root span carries the user's `input`, the agent's `output`, `thread.id` / `langfuse.session.id` (so multi-turn conversations group correctly), `agent.execution.status` (technical success/error), and `agent.business_outcome` (business-level success/failure even on HTTP 200). The `gen_ai.chat` spans carry the model name and `gen_ai.usage.*` token counts that populate the token-consumption panels. See Figures 1–5 in [`article-wxo-agentic-control-plane-v2.md`](article-wxo-agentic-control-plane-v2.md) and the screenshots in [`img/`](img/) for what each of these screens looks like.

If a conversation never appears in **Conversations**, but the `wxO trace queued ... status=success` log line did print, wait — ingestion is asynchronous and can lag a few seconds — then re-check `WXO_TENANT_ID`/`WXO_AGENT_ID` are exactly what was printed at registration.

---

## Environment variables reference

### A2A server

| Variable | Required | Description |
|---|---|---|
| `GOOGLE_API_KEY` | yes | Google Gemini API key |
| `AGENT_BASE_URL` | yes | Public URL of this server (embedded in the AgentCard) |
| `AGENT_API_KEY` | recommended | Bearer token protecting `POST /`; leave unset to disable auth (dev only) |
| `GEMINI_MODEL` | no | Defaults to `gemini-2.5-flash` |

### Deployment (`deploy.sh`)

| Variable | Required | Description |
|---|---|---|
| `IBMCLOUD_API_KEY` | yes | IBM Cloud platform API key (login, ICR push) |
| `IBMCLOUD_REGION` | no | Default `us-south` |
| `RESOURCE_GROUP` | no | Default `itrhsp` |
| `CE_PROJECT_NAME` | no | Default `wxo-a2a-agents` |
| `CE_APP_NAME` | no | Default `annualized-return-agent` |
| `CR_NAMESPACE` | no | Default `itrhsp-a2a-agents` — must be globally unique in `us.icr.io` |

### Telemetry (`wxo_otel.py`)

| Variable | Required | Description |
|---|---|---|
| `WXO_AGENT_ID` | yes — app fails to start without it | Registered agent UUID from wxO |
| `WXO_TENANT_ID` | yes — app fails to start without it | `<account-id>_<instance-id>` |
| `OTEL_EXPORT_URL` | yes — app fails to start without it | wxO OTLP trace ingestion endpoint |
| `WXO_API_KEY` | yes, checked on first export | IBM Cloud API key exchanged for a bearer token via IAM; kept separate from `GOOGLE_API_KEY` so the two never collide |
| `TOKEN_URL` | yes | `https://iam.cloud.ibm.com/identity/token` for IBM Cloud SaaS — hardcoded by `deploy.sh` |
| `ENVIRONMENT_NAME` | no | `draft` or `live` only — anything else raises at startup; default `live` |
| `WXO_AGENT_NAME` | no | Used in the root span name `invoke_agent <name>`; default `external_order_support_agent` |
| `WXO_AGENT_DISPLAY_NAME` | no | Display label only, never sent as a span attribute (see Troubleshooting) |
| `WXO_WORKSPACE_ID` | no | Sent as `workspace.id` resource attribute if present |
| `WXO_CAPTURE_CONTENT` | no | Set `false` to omit request/response text (`input`/`output`) from traces — keeps timing, tokens, and outcomes while dropping payloads (useful for PII-sensitive workloads) |
| `OTEL_SERVICE_NAME` / `OTEL_SERVICE_VERSION` | no | OTel resource attributes; defaults `external-agent` / `2.0.0` |

---

## Handling secrets

`wxo-a2a-deploy-key.json`, `wxo-telemetry-key.json`, and `.env` contain live IBM Cloud API keys and must never be committed. 

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Code Engine revision never reaches Ready; crash loop right after deploy | `WXO_TENANT_ID`, `WXO_AGENT_ID`, or `OTEL_EXPORT_URL` empty | These are read at process startup, not lazily — set non-empty placeholders for the first deploy (Part 2 Step 3) |
| `ENVIRONMENT_NAME must be 'live' or 'draft'` in logs, app won't start | `ENVIRONMENT_NAME` set to something other than exactly `live` or `draft` | Fix the value and redeploy/update |
| `401 Unauthorized` on `POST /` | Wrong or missing `AGENT_API_KEY` | Send `Authorization: Bearer <AGENT_API_KEY>` |
| `404` from `orchestrate agents discover` | ADK fetches `agent-card.json`, not `agent.json` | Both paths are served by `server.py` — confirm the latest image is deployed |
| `wxO token exchange failed with HTTP 403` | Wrong `TOKEN_URL` (MCSP endpoint blocked from Code Engine IPs) | Use `https://iam.cloud.ibm.com/identity/token` for IBM Cloud SaaS |
| `wxO token exchange failed with HTTP 400` | `WXO_API_KEY` invalid or from the wrong account | Regenerate with `ibmcloud iam api-key-create` against the account that owns the wxO instance |
| No `wxO trace queued` line at all | Telemetry never configured / app crashed before the middleware ran | Check `ibmcloud ce app logs --previous` for the startup error |
| `wxO trace queued ... status=success` in logs, but nothing in the wxO UI | `WXO_TENANT_ID` / `WXO_AGENT_ID` don't match the registered agent, or ingestion is still catching up | Re-check both values against what `orchestrate agents discover`/`import` printed; wait a few seconds and refresh |
| Trace output renders as `[object Object]` in Trace View | `agent.name` (alongside `agent.id`), or `gen_ai.input.messages` / `gen_ai.output.messages` were set on a span | Don't set these — wxO's ingestion wraps `output` into a chat-message array when either is present, colliding with the plain-string `output` attribute. Neither is set anywhere in `wxo_otel.py` by design; if you extend it, keep it that way |
| `PORT is a reserved environment variable` on deploy | Code Engine injects `PORT` itself | Never pass `--env PORT=...` |
| `ModuleNotFoundError: wxo_otel` inside the container | `wxo_otel.py` missing from the image | Confirm `COPY wxo_otel.py ./wxo_otel.py` is in the `Dockerfile` and rebuild |

---

## Cleaning up

```bash
ibmcloud ce app delete --name annualized-return-agent -f
ibmcloud cr image-list --restrict itrhsp-a2a-agents   # then ibmcloud cr image-rm <image> for old tags
orchestrate agents remove -n annualized_return_agent   # or via the wxO UI
```

---

## Further reading

- [`article-wxo-agentic-control-plane-v2.md`](article-wxo-agentic-control-plane-v2.md) — the full architectural write-up: why a control plane matters, how each piece of `wxo_otel.py` works (thread-boundary context propagation, the refreshing OTLP exporter, technical-vs-business failure), and what the pattern delivers.

#!/usr/bin/env bash
# =============================================================================
# deploy.sh — Deploy the A2A Agent to IBM Cloud Code Engine
#
# Prerequisites:
#   1. ibmcloud CLI installed + logged in  (ibmcloud login --sso)
#   2. Code Engine plugin installed        (ibmcloud plugin install code-engine)
#   3. Container Registry plugin installed (ibmcloud plugin install container-registry)
#   4. Docker installed and daemon running
#   5. All required environment variables set (see .env.example)
#
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh
# =============================================================================
set -euo pipefail

# Load .env from the same directory as this script (if it exists)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "${SCRIPT_DIR}/.env" ]]; then
    # shellcheck source=.env
    set -a
    # shellcheck disable=SC1091
    source "${SCRIPT_DIR}/.env"
    set +a
fi

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURATION — edit these values before running
# ──────────────────────────────────────────────────────────────────────────────

IBMCLOUD_REGION="${IBMCLOUD_REGION:-us-south}"
RESOURCE_GROUP="${RESOURCE_GROUP:-itrhsp}"
CE_PROJECT_NAME="${CE_PROJECT_NAME:-wxo-a2a-agents}"
CE_APP_NAME="${CE_APP_NAME:-annualized-return-agent}"
CR_NAMESPACE="${CR_NAMESPACE:-itrhsp-a2a-agents}"                  # ICR namespace — must be globally unique in us.icr.io
IMAGE_TAG="${IMAGE_TAG:-$(date +%Y%m%d%H%M%S)}"
IMAGE_NAME="us.icr.io/${CR_NAMESPACE}/${CE_APP_NAME}:${IMAGE_TAG}"

# Agent runtime secrets (loaded from environment — do NOT hard-code)
: "${GOOGLE_API_KEY:?GOOGLE_API_KEY must be set}"
: "${AGENT_API_KEY:?AGENT_API_KEY must be set}"

GEMINI_MODEL="${GEMINI_MODEL:-gemini-2.5-flash}"

# ──────────────────────────────────────────────────────────────────────────────
# 1. Authenticate to IBM Cloud
# ──────────────────────────────────────────────────────────────────────────────

echo "🔐 Logging in to IBM Cloud (no resource group yet — needed to create it first)..."
ibmcloud login --apikey "${IBMCLOUD_API_KEY:?IBMCLOUD_API_KEY must be set}" \
               -r "${IBMCLOUD_REGION}"

# Ensure the resource group exists before targeting it
echo "📁 Ensuring resource group '${RESOURCE_GROUP}' exists..."
if ! ibmcloud resource group "${RESOURCE_GROUP}" &>/dev/null; then
    echo "   Resource group not found — creating '${RESOURCE_GROUP}'..."
    ibmcloud resource group-create "${RESOURCE_GROUP}"
    echo "   ✅ Resource group '${RESOURCE_GROUP}' created."
else
    echo "   ✅ Resource group '${RESOURCE_GROUP}' already exists."
fi

# Now target the resource group
ibmcloud target -g "${RESOURCE_GROUP}"

echo "🔐 Logging in to IBM Container Registry..."
ibmcloud cr login --client docker
ibmcloud cr region-set "${IBMCLOUD_REGION}"

# ──────────────────────────────────────────────────────────────────────────────
# 2. Create ICR namespace if it doesn't exist
# ──────────────────────────────────────────────────────────────────────────────

echo "📦 Ensuring ICR namespace '${CR_NAMESPACE}' exists..."
if ibmcloud cr namespace-list --output json 2>/dev/null | python3 -c "import sys,json; namespaces=[n.get('name','') for n in json.load(sys.stdin)]; exit(0 if '${CR_NAMESPACE}' in namespaces else 1)" 2>/dev/null; then
    echo "   ✅ Namespace '${CR_NAMESPACE}' already exists — skipping."
else
    echo "   Creating namespace '${CR_NAMESPACE}'..."
    ibmcloud cr namespace-add "${CR_NAMESPACE}"
fi

# ──────────────────────────────────────────────────────────────────────────────
# 3. Build & push container image
# ──────────────────────────────────────────────────────────────────────────────

echo "🐳 Building Docker image: ${IMAGE_NAME}"
docker build --platform linux/amd64 -t "${IMAGE_NAME}" .

echo "📤 Pushing image to IBM Container Registry..."
docker push "${IMAGE_NAME}"

# ──────────────────────────────────────────────────────────────────────────────
# 4. Select / create Code Engine project
# ──────────────────────────────────────────────────────────────────────────────

echo "🚀 Configuring Code Engine project '${CE_PROJECT_NAME}'..."
if ! ibmcloud ce project select --name "${CE_PROJECT_NAME}" 2>/dev/null; then
    echo "   Project not found — creating it..."
    ibmcloud ce project create --name "${CE_PROJECT_NAME}"
    ibmcloud ce project select --name "${CE_PROJECT_NAME}"
fi

# ──────────────────────────────────────────────────────────────────────────────
# 5. Create an IAM-based registry secret for Code Engine to pull images
# ──────────────────────────────────────────────────────────────────────────────

echo "🔑 Ensuring registry access secret 'icr-secret' exists..."
if ibmcloud ce registry get --name icr-secret &>/dev/null; then
    echo "   ✅ Registry secret 'icr-secret' already exists — skipping."
else
    echo "   Creating registry secret..."
    ibmcloud ce registry create \
        --name icr-secret \
        --server us.icr.io \
        --username iamapikey \
        --password "${IBMCLOUD_API_KEY}"
fi

# ──────────────────────────────────────────────────────────────────────────────
# 6. Deploy or update the Code Engine application
# ──────────────────────────────────────────────────────────────────────────────

DEPLOY_ARGS=(
    --name           "${CE_APP_NAME}"
    --image          "${IMAGE_NAME}"
    --registry-secret icr-secret
    --port           8080
    --min-scale      1
    --max-scale      5
    --cpu            1
    --memory         4G
    --env            GOOGLE_API_KEY="${GOOGLE_API_KEY}"
    --env            AGENT_API_KEY="${AGENT_API_KEY}"
    --env            GEMINI_MODEL="${GEMINI_MODEL}"
    --env            HOST=0.0.0.0
    --env            ENVIRONMENT_NAME="${ENVIRONMENT_NAME:-draft}"
    --env            TOKEN_URL="${TOKEN_URL:-https://iam.cloud.ibm.com/identity/token}"
)

# wxO telemetry env vars (read by wxo_otel.py / WxoA2ATraceMiddleware)
# WXO_API_KEY, WXO_TENANT_ID, WXO_AGENT_ID and OTEL_EXPORT_URL are required
# at runtime — the app will crash on first request if they are absent.
: "${WXO_API_KEY:?WXO_API_KEY must be set}"
: "${WXO_TENANT_ID:?WXO_TENANT_ID must be set}"
: "${WXO_AGENT_ID:?WXO_AGENT_ID must be set}"
: "${OTEL_EXPORT_URL:?OTEL_EXPORT_URL must be set}"

DEPLOY_ARGS+=(
    --env "WXO_API_KEY=${WXO_API_KEY}"
    --env "WXO_TENANT_ID=${WXO_TENANT_ID}"
    --env "WXO_AGENT_ID=${WXO_AGENT_ID}"
    --env "OTEL_EXPORT_URL=${OTEL_EXPORT_URL}"
)

# Optional wxO telemetry overrides
[ -n "${WXO_AGENT_NAME:-}"        ] && DEPLOY_ARGS+=(--env "WXO_AGENT_NAME=${WXO_AGENT_NAME}")
[ -n "${WXO_AGENT_DISPLAY_NAME:-}" ] && DEPLOY_ARGS+=(--env "WXO_AGENT_DISPLAY_NAME=${WXO_AGENT_DISPLAY_NAME}")
[ -n "${WXO_WORKSPACE_ID:-}"      ] && DEPLOY_ARGS+=(--env "WXO_WORKSPACE_ID=${WXO_WORKSPACE_ID}")
[ -n "${WXO_CAPTURE_CONTENT:-}"   ] && DEPLOY_ARGS+=(--env "WXO_CAPTURE_CONTENT=${WXO_CAPTURE_CONTENT}")
[ -n "${OTEL_SERVICE_NAME:-}"     ] && DEPLOY_ARGS+=(--env "OTEL_SERVICE_NAME=${OTEL_SERVICE_NAME}")
[ -n "${OTEL_SERVICE_VERSION:-}"  ] && DEPLOY_ARGS+=(--env "OTEL_SERVICE_VERSION=${OTEL_SERVICE_VERSION}")

if ibmcloud ce app get --name "${CE_APP_NAME}" &>/dev/null; then
    echo "🔄 Updating existing Code Engine application '${CE_APP_NAME}'..."
    ibmcloud ce app update "${DEPLOY_ARGS[@]}" --no-wait
else
    echo "🆕 Creating Code Engine application '${CE_APP_NAME}'..."
    ibmcloud ce app create "${DEPLOY_ARGS[@]}" --no-wait
fi

# ──────────────────────────────────────────────────────────────────────────────
# 7. Poll until ready, then display deployment URL
# ──────────────────────────────────────────────────────────────────────────────

echo ""
echo "⏳ Waiting for application to become ready (timeout: 5 min)..."

READY=false
for i in $(seq 1 30); do
    STATUS=$(ibmcloud ce app get --name "${CE_APP_NAME}" --output json 2>/dev/null \
             | python3 -c "
import sys, json
d = json.load(sys.stdin)
conds = d.get('status', {}).get('conditions', [])
for c in conds:
    if c.get('type') == 'Ready':
        print(c.get('status', 'Unknown'))
        break
else:
    print('Unknown')
" 2>/dev/null || echo "Unknown")

    if [[ "${STATUS}" == "True" ]]; then
        READY=true
        break
    fi
    echo "   [${i}/30] status=${STATUS} — retrying in 10 s..."
    sleep 10
done

if [[ "${READY}" != "true" ]]; then
    echo "⚠️  Application did not reach Ready state within 5 minutes."
    echo "   Check logs: ibmcloud ce app logs --name ${CE_APP_NAME}"
    echo "   Check events: ibmcloud ce app events --name ${CE_APP_NAME}"
    exit 1
fi

ibmcloud ce app get --name "${CE_APP_NAME}" --output json | \
    python3 -c "
import sys, json
d = json.load(sys.stdin)
url = d.get('status', {}).get('url') or d.get('endpoint', '')
if url:
    print(f'\n✅  Deployment complete!')
    print(f'    App URL       : {url}')
    print(f'    Agent card    : {url}/.well-known/agent.json')
    print(f'    Health check  : {url}/health')
    print(f'    A2A endpoint  : {url}/')
    print(f'\n📝  Next steps:')
    print(f'    1. Update agent.yaml api_url to: {url}')
    print(f'    2. Set AGENT_BASE_URL={url} in your environment')
    print(f'    3. Register with wxO:  orchestrate agents import -f agent.yaml')
    print(f'    4. Or auto-discover:  orchestrate agents discover -u {url}')
else:
    print('Could not determine app URL. Run: ibmcloud ce app get --name ${CE_APP_NAME}')
"

echo ""
echo "🎉 Done. Your A2A agent is running on IBM Cloud Code Engine."

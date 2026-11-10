#!/usr/bin/env bash
# =============================================================================
# lib/flow_selfhosted.sh  —  Self-hosted container wiring (sitecustomize hook)
#
# Zero user-code changes.  Zero CMD/ENTRYPOINT changes.
# Injects sitecustomize.py into the container image via a one-line Dockerfile
# layer.  Python imports sitecustomize automatically at startup — before any
# user code — so it patches the HTTP handler without touching server.py.
#
# What the patch does:
#   Patches all major Python HTTP / RPC frameworks at startup:
#     http.server, Starlette/FastAPI, Flask, Django, generic WSGI,
#     Tornado, aiohttp, and gRPC (unary + all streaming types).
#   Captures prompt (request body) + response (response body) on every POST
#   and POSTs a WXO-compatible synthetic OTLP span directly to WXO.
#
# Config injected into the container via Cloud Run / GKE env vars:
#   WXO_AGENT_ID          WXO agent UUID
#   WXO_AGENT_NAME        snake_case name shown in WXO
#   WXO_TENANT_ID         WXO tenant ID
#   WXO_API_KEY           WXO API key
#   WXO_TOKEN_URL         IAM token endpoint
#   WXO_OTEL_EXPORT_URL   WXO OTLP/HTTP ingestion URL
#   WXO_ENVIRONMENT_NAME  draft | live
#
# Span path:
#   sitecustomize.py (in container) → POST directly to WXO_OTEL_EXPORT_URL
#
# Targets supported (set CONTAINER_TARGET in config.env):
#   cloudrun  → gcloud run deploy with --update-env-vars
#   artifact  → just build + push the patched image (you deploy manually / via GKE)
#
# Sourced by wire_agent.sh.  Not executed directly.
# =============================================================================

# -----------------------------------------------------------------------------
# _ensure_gcloud — verify gcloud is on PATH; attempt auto-install if missing.
# Exits with a human-friendly message if gcloud cannot be made available.
# -----------------------------------------------------------------------------
_ensure_gcloud() {
    if command -v gcloud &>/dev/null; then
        return 0
    fi

    echo ""
    echo "  ⚠ gcloud (Google Cloud SDK) is not installed or not on your PATH."
    echo ""
    echo "  Attempting automatic installation via the official Google installer..."
    echo "  (This runs: curl https://sdk.cloud.google.com | bash)"
    echo ""

    # Attempt non-interactive install into ~/google-cloud-sdk
    if curl -fsSL https://sdk.cloud.google.com | bash -s -- \
            --disable-prompts --install-dir="${HOME}" >/tmp/gcloud_install.log 2>&1; then

        # Source the path helper the installer drops into the home dir
        for _init in \
            "${HOME}/google-cloud-sdk/path.bash.inc" \
            "${HOME}/google-cloud-sdk/path.zsh.inc"; do
            [ -f "${_init}" ] && source "${_init}" && break
        done

        if command -v gcloud &>/dev/null; then
            echo "  ✓ gcloud installed successfully: $(command -v gcloud)"
            echo ""
            return 0
        fi
    fi

    # Auto-install failed — give the user clear next steps and bail out
    echo ""
    echo "  ✗ Automatic installation failed (see /tmp/gcloud_install.log for details)."
    echo ""
    echo "  Please install the Google Cloud SDK manually, then re-run this script:"
    echo ""
    echo "    macOS (Homebrew):"
    echo "      brew install --cask google-cloud-sdk"
    echo "      # then open a new terminal and run:  gcloud init"
    echo ""
    echo "    Linux / macOS (official installer):"
    echo "      curl https://sdk.cloud.google.com | bash"
    echo "      exec -l \$SHELL"
    echo "      gcloud init"
    echo ""
    echo "    Full docs: https://cloud.google.com/sdk/docs/install"
    echo ""
    exit 1
}

run_flow_selfhosted() {
    # AGENT_PATCH_DIR is set by the caller (vertex/wire_agent.sh) to the shared
    # container_hook/ directory at the repo root.  Fall back to the old relative
    # path so the script still works when sourced directly from the vertex/ dir.
    local AGENT_PATCH_DIR
    AGENT_PATCH_DIR="${AGENT_PATCH_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/container_hook}"

    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║  --selfhosted  (Self-hosted container / sitecustomize hook)  ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""

    # ── [1/4] Validate config ────────────────────────────────────────────────
    echo "[1/4] Validating configuration..."

    local _missing=0
    for _var in SOURCE_IMAGE GCP_PROJECT_ID GCP_REGION GCP_ARTIFACT_REGISTRY; do
        if [ -z "${!_var:-}" ]; then
            echo "  ✗ ${_var} is not set in config.env"
            _missing=1
        fi
    done
    [ "${_missing}" -eq 1 ] && { echo ""; echo "Edit config.env and re-run."; exit 1; }

    # Derive agent name and display name
    local AGENT_NAME DISPLAY
    AGENT_NAME="${WXO_AGENT_NAME:-$(echo "${SOURCE_IMAGE}" | python3 -c "
import sys, re
u = sys.stdin.read().strip().split('/')[-1].rsplit(':',1)[0]
snake = re.sub(r'[^a-z0-9]+', '_', u.lower()).strip('_')
print(snake or 'vertex_agent')")}"
    DISPLAY="${WXO_DISPLAY_NAME:-${AGENT_NAME}}"

    # Always patch from the source image — never re-patch an already-patched image
    local PATCHED_TAG="${SOURCE_IMAGE##*/}"          # strip registry prefix
    PATCHED_TAG="${PATCHED_TAG%:*}:wxo-patched"     # swap tag to wxo-patched
    local PATCHED_IMAGE="${GCP_ARTIFACT_REGISTRY}/${PATCHED_TAG}"

    echo "  ✓ Config valid"
    echo "    Source image   : ${SOURCE_IMAGE}"
    echo "    Patched image  : ${PATCHED_IMAGE}"
    echo "    Agent name     : ${AGENT_NAME}"
    echo "    Display        : ${DISPLAY}"
    echo "    Target         : ${CONTAINER_TARGET:-cloudrun}"

    # ── [2/4] Authenticate with Artifact Registry ────────────────────────────
    echo ""
    echo "[2/4] Authenticating with Artifact Registry..."
    _ensure_gcloud

    # Activate the service-account key so both docker pull (source repo) and
    # docker push (target repo) share the same authenticated identity.
    local _SA_KEY="${GCP_SERVICE_ACCOUNT_JSON:-${GOOGLE_APPLICATION_CREDENTIALS:-}}"
    if [ -n "${_SA_KEY}" ]; then
        if [ -f "${_SA_KEY}" ]; then
            gcloud auth activate-service-account \
                --key-file="${_SA_KEY}" --quiet 2>/dev/null \
                && echo "  ✓ gcloud: activated SA from key file"
        else
            python3 -c "
import base64, sys
raw = sys.argv[1].strip()
if raw.startswith('{'):
    print(raw)
else:
    print(base64.b64decode(raw).decode('utf-8'))
" "${_SA_KEY}" 2>/dev/null | gcloud auth activate-service-account --key-file=- --quiet 2>/dev/null \
                && echo "  ✓ gcloud: activated SA from decoded credentials (in-memory)"
        fi
    fi

    # Determine all registry hosts that need Docker credential helpers:
    #   - the push target (GCP_ARTIFACT_REGISTRY)
    #   - the source image registry (may differ, e.g. cloud-run-source-deploy)
    local _REGISTRY_HOST _SOURCE_REGISTRY_HOST
    _REGISTRY_HOST=$(echo "${GCP_ARTIFACT_REGISTRY}" | cut -d'/' -f1)
    _SOURCE_REGISTRY_HOST=$(echo "${SOURCE_IMAGE}" | cut -d'/' -f1)

    for _host in "${_REGISTRY_HOST}" "${_SOURCE_REGISTRY_HOST}"; do
        gcloud auth configure-docker "${_host}" --quiet 2>/dev/null || \
            gcloud auth print-access-token | docker login -u oauth2accesstoken \
                --password-stdin "https://${_host}" > /dev/null 2>&1
    done

    echo "  ✓ Registry auth: ${_REGISTRY_HOST}"

    # ── [3/4] Build + push patched image ─────────────────────────────────────
    echo ""
    echo "[3/4] Building hook-patched image..."
    echo "  What changes   : + sitecustomize.py (Python auto-imports at startup)"
    echo "  What stays     : original CMD, ENTRYPOINT, server.py — UNCHANGED"
    echo ""

    docker pull --platform linux/amd64 "${SOURCE_IMAGE}" --quiet > /dev/null

    docker build \
        --platform linux/amd64 \
        --build-arg SOURCE_IMAGE="${SOURCE_IMAGE}" \
        -t "${PATCHED_IMAGE}" \
        -f "${AGENT_PATCH_DIR}/Dockerfile" \
        "${SCRIPT_DIR}" \
        --quiet

    echo "  ✓ Image built: ${PATCHED_IMAGE}"
    docker push "${PATCHED_IMAGE}" --quiet
    echo "  ✓ Image pushed to Artifact Registry"

    # ── [4/4] Inject WXO env vars into the running service ───────────────────
    echo ""
    echo "[4/4] Injecting WXO env vars..."

    # All WXO_* vars come from the current environment, which is either:
    #   • single-agent mode: loaded from config.env by wire_agent.sh
    #   • multi-agent mode:  overridden per-entry by the WXO_AGENT_MAP loop
    #     (WXO_API_KEY comes from the map entry's wxo_api_key field when set,
    #      otherwise falls back to API_KEY)
    # cloud: API key + token URL + tenant.  cpd: CPD_* login (no key / tenant).
    local _ENV_VARS
    if [ "${WXO_DEPLOYMENT_MODE:-cloud}" != "cpd" ]; then
        if [ -z "${WXO_TENANT_ID:-}" ] && [ -n "${WXO_OTEL_EXPORT_URL:-}" ]; then
            if [[ "${WXO_OTEL_EXPORT_URL}" =~ /instances/([^/]+) ]]; then
                WXO_TENANT_ID="${BASH_REMATCH[1]}"
                WXO_TENANT_ID="${WXO_TENANT_ID%%\?*}"
                WXO_TENANT_ID="${WXO_TENANT_ID%%\#*}"
            fi
        fi
    fi
    if [ "${WXO_DEPLOYMENT_MODE:-cloud}" = "cpd" ]; then
        _ENV_VARS="WXO_DEPLOYMENT_MODE=cpd,\
WXO_AGENT_ID=${WXO_AGENT_ID},\
WXO_AGENT_NAME=${AGENT_NAME},\
WXO_OTEL_EXPORT_URL=${WXO_OTEL_EXPORT_URL},\
WXO_ENVIRONMENT_NAME=${ENVIRONMENT_NAME},\
CPD_HOST_URL=${CPD_HOST_URL},\
CPD_USERNAME=${CPD_USERNAME},\
CPD_PASSWORD=${CPD_PASSWORD},\
CPD_INSTANCE_ID=${CPD_INSTANCE_ID},\
CPD_NAMESPACE=${CPD_NAMESPACE},\
CPD_VERIFY_TLS=${CPD_VERIFY_TLS:-false}"
    else
        local _API_KEY_VAL="${WXO_API_KEY:-${API_KEY}}"
        local _TOKEN_URL_VAL="${WXO_TOKEN_URL:-${TOKEN_URL}}"
        _ENV_VARS="WXO_AGENT_ID=${WXO_AGENT_ID},\
WXO_AGENT_NAME=${AGENT_NAME},\
WXO_TENANT_ID=${WXO_TENANT_ID},\
WXO_API_KEY=${_API_KEY_VAL},\
WXO_TOKEN_URL=${_TOKEN_URL_VAL},\
WXO_OTEL_EXPORT_URL=${WXO_OTEL_EXPORT_URL},\
WXO_ENVIRONMENT_NAME=${ENVIRONMENT_NAME}"
    fi

    echo "  WXO_DEPLOYMENT_MODE  = ${WXO_DEPLOYMENT_MODE:-cloud}"
    echo "  WXO_AGENT_ID         = ${WXO_AGENT_ID}"
    echo "  WXO_AGENT_NAME       = ${AGENT_NAME}"
    if [ "${WXO_DEPLOYMENT_MODE:-cloud}" != "cpd" ]; then
        echo "  WXO_TENANT_ID        = ${WXO_TENANT_ID}"
    fi
    echo "  WXO_ENVIRONMENT_NAME = ${ENVIRONMENT_NAME}"
    echo "  WXO_OTEL_EXPORT_URL  = ${WXO_OTEL_EXPORT_URL:0:50}..."

    if [ "${CONTAINER_TARGET:-cloudrun}" = "cloudrun" ]; then
        if [ -z "${CLOUD_RUN_SERVICE:-}" ]; then
            echo ""
            echo "  ✗ CLOUD_RUN_SERVICE is not set in config.env"
            echo "    Set it to the name of your Cloud Run service, or set"
            echo "    CONTAINER_TARGET=artifact to only build and push the image."
            exit 1
        fi

        gcloud run deploy "${CLOUD_RUN_SERVICE}" \
            --image "${PATCHED_IMAGE}" \
            --region "${GCP_REGION}" \
            --project "${GCP_PROJECT_ID}" \
            --update-env-vars "${_ENV_VARS}" \
            --quiet

        echo "  ✓ Cloud Run service updated — waiting for READY..."
        wait_ready "Cloud Run" 30 10 "True" \
            gcloud run services describe "${CLOUD_RUN_SERVICE}" \
                --region "${GCP_REGION}" --project "${GCP_PROJECT_ID}" \
                --format "value(status.conditions[0].status)"

        local SERVICE_URL
        SERVICE_URL=$(gcloud run services describe "${CLOUD_RUN_SERVICE}" \
            --region "${GCP_REGION}" --project "${GCP_PROJECT_ID}" \
            --format "value(status.url)" 2>/dev/null || echo "")

        echo ""
        echo "══════════════════════════════════════════════════════════════════"
        echo "  Done"
        echo "  Service URL  : ${SERVICE_URL}"
        echo "  Patched image: ${PATCHED_IMAGE}"
        echo ""
        echo "  Span path: sitecustomize.py → WXO directly"
        echo "  Agent appears in WXO under: ${DISPLAY} / env=${ENVIRONMENT_NAME}"
        echo ""
        echo "  Monitor logs:"
        echo "    gcloud run services logs tail ${CLOUD_RUN_SERVICE} --region ${GCP_REGION}"
        echo "══════════════════════════════════════════════════════════════════"

    else
        # artifact-only: just build + push — user deploys to GKE / Knative / etc.
        echo ""
        echo "══════════════════════════════════════════════════════════════════"
        echo "  Done  (artifact-only mode)"
        echo "  Patched image: ${PATCHED_IMAGE}"
        echo ""
        echo "  Deploy this image to your cluster and set these env vars:"
        echo ""
        echo "    WXO_AGENT_ID         = ${WXO_AGENT_ID}"
        echo "    WXO_AGENT_NAME       = ${AGENT_NAME}"
        if [ "${WXO_DEPLOYMENT_MODE:-cloud}" = "cpd" ]; then
            echo "    WXO_DEPLOYMENT_MODE  = cpd"
            echo "    CPD_HOST_URL         = ${CPD_HOST_URL}"
            echo "    CPD_USERNAME         = <your-cpd-username>"
            echo "    CPD_PASSWORD         = <your-cpd-password>"
            echo "    CPD_INSTANCE_ID      = ${CPD_INSTANCE_ID}"
            echo "    CPD_NAMESPACE        = ${CPD_NAMESPACE}"
        else
            echo "    WXO_TENANT_ID        = ${WXO_TENANT_ID}"
            echo "    WXO_API_KEY          = <your-api-key>"
            echo "    WXO_TOKEN_URL        = ${TOKEN_URL}"
        fi
        echo "    WXO_OTEL_EXPORT_URL  = ${WXO_OTEL_EXPORT_URL:0:60}..."
        echo "    WXO_ENVIRONMENT_NAME = ${ENVIRONMENT_NAME}"
        echo ""
        echo "  Span path: sitecustomize.py → WXO directly"
        echo "══════════════════════════════════════════════════════════════════"
    fi
}

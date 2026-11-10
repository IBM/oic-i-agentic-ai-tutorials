#!/usr/bin/env bash
# =============================================================================
# lib/flow_runtime.sh  —  Flow B: Custom-image runtime wiring (sitecustomize hook)
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
# Config injected into the runtime via update-agent-runtime env vars:
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
# Sourced by wire_agent.sh.  Not executed directly.
# =============================================================================

run_flow_runtime() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║  Flow B — Custom-image runtime  (sitecustomize hook)         ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""

    # ── [1/3] Fetch runtime metadata ─────────────────────────────────────────
    echo "[1/3] Fetching runtime from AgentCore..."

    local RUNTIME_JSON
    RUNTIME_JSON=$(aws bedrock-agentcore-control get-agent-runtime \
        --agent-runtime-id "${AGENT_REF}" --region "${AWS_REGION}" --output json 2>&1) || {
        echo ""
        echo "  ✗ Runtime '${AGENT_REF}' not found in region ${AWS_REGION}."
        echo ""
        echo "  List your runtimes:"
        echo "    aws bedrock-agentcore-control list-agent-runtimes --region ${AWS_REGION} --output table"
        exit 1
    }

    local CURRENT_URI ORIGINAL_URI ROLE_ARN_RUNTIME NETWORK_MODE ECR_REPO AGENT_NAME DISPLAY

    CURRENT_URI=$(echo "${RUNTIME_JSON}" | python3 -c "
import sys, json
print(json.load(sys.stdin)['agentRuntimeArtifact']['containerConfiguration']['containerUri'])")

    # Always patch from :latest — never re-patch a :wxo-patched image
    ORIGINAL_URI=$(echo "${CURRENT_URI}" | python3 -c "
import sys
u = sys.stdin.read().strip()
print(u.replace(':wxo-patched', ':latest') if u.endswith(':wxo-patched') else u)")

    ROLE_ARN_RUNTIME=$(echo "${RUNTIME_JSON}" | python3 -c \
        "import sys, json; print(json.load(sys.stdin)['roleArn'])")
    NETWORK_MODE=$(echo "${RUNTIME_JSON}" | python3 -c \
        "import sys, json; print(json.load(sys.stdin)['networkConfiguration']['networkMode'])")
    SERVER_PROTOCOL=$(echo "${RUNTIME_JSON}" | python3 -c \
        "import sys, json; d=json.load(sys.stdin); print(d.get('protocolConfiguration',{}).get('serverProtocol','HTTP'))")
    ECR_REPO=$(echo "${ORIGINAL_URI}" | python3 -c "
import sys
u = sys.stdin.read().strip()
print(u.split('/', 1)[-1].rsplit(':', 1)[0])")

    AGENT_NAME=$(snake_name "${AGENT_REF}")
    DISPLAY="${WXO_DISPLAY_NAME:-${AGENT_NAME}}"
    local PATCHED_URI="${REGISTRY}/${ECR_REPO}:wxo-patched"

    echo "  ✓ Runtime found"
    echo "    Original image : ${ORIGINAL_URI}"
    echo "    Patched image  : ${PATCHED_URI}"
    echo "    Agent name     : ${AGENT_NAME}"
    echo "    Display        : ${DISPLAY}"

    # ── [2/3] Write agent identity to SSM ────────────────────────────────────
    # Flow B posts directly from sitecustomize.py → WXO — no Lambda or API GW.
    echo ""
    echo "[2/3] Writing agent identity to SSM..."
    write_ssm_identity "${AGENT_REF}" "${AGENT_NAME}" "${DISPLAY}"

    # ── [3/3] Build + push patched image ─────────────────────────────────────
    echo ""
    echo "[3/3] Building hook-patched image..."
    echo "  What changes   : + sitecustomize.py (Python auto-imports at startup)"
    echo "  What stays     : original CMD, ENTRYPOINT, server.py — UNCHANGED"
    echo ""

    aws ecr get-login-password --region "${AWS_REGION}" \
        | docker login --username AWS --password-stdin "${REGISTRY}" > /dev/null 2>&1

    docker pull "${ORIGINAL_URI}" --quiet > /dev/null

    docker build \
        --build-arg SOURCE_IMAGE="${ORIGINAL_URI}" \
        -t "${PATCHED_URI}" \
        -f "${AGENT_PATCH_DIR}/Dockerfile" \
        "${SCRIPT_DIR}" \
        --quiet

    echo "  ✓ Image built: ${PATCHED_URI}"
    docker push "${PATCHED_URI}" --quiet
    echo "  ✓ Image pushed to ECR"

    # ── Update AgentCore runtime with patched image + WXO env vars ───────────
    echo ""
    echo "Updating runtime with patched image + WXO env vars..."

    # WXO vars come from the current env — either config.env (single-agent)
    # or overridden per-entry by the WXO_AGENT_MAP loop (multi-agent).
    # cloud: WXO_API_KEY prefers the per-agent map entry; falls back to API_KEY.
    # cpd:   CPD_* login values are injected instead (no API key / tenant).
    local _RT_ENV
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
        _RT_ENV="$(python3 -c "
import json, os
e = os.environ
print(json.dumps({
    'WXO_DEPLOYMENT_MODE':  'cpd',
    'WXO_AGENT_ID':         e['WXO_AGENT_ID'],
    'WXO_AGENT_NAME':       '${AGENT_NAME}',
    'WXO_OTEL_EXPORT_URL':  e.get('WXO_OTEL_EXPORT_URL', ''),
    'WXO_ENVIRONMENT_NAME': e['ENVIRONMENT_NAME'],
    'CPD_HOST_URL':         e['CPD_HOST_URL'],
    'CPD_USERNAME':         e['CPD_USERNAME'],
    'CPD_PASSWORD':         e['CPD_PASSWORD'],
    'CPD_INSTANCE_ID':      e['CPD_INSTANCE_ID'],
    'CPD_NAMESPACE':        e['CPD_NAMESPACE'],
    'CPD_VERIFY_TLS':       e.get('CPD_VERIFY_TLS', 'false'),
}))")"
    else
        local _API_KEY_VAL="${WXO_API_KEY:-${API_KEY}}"
        local _TOKEN_URL_VAL="${WXO_TOKEN_URL:-${TOKEN_URL}}"
        _RT_ENV="{
            \"WXO_AGENT_ID\":          \"${WXO_AGENT_ID}\",
            \"WXO_AGENT_NAME\":        \"${AGENT_NAME}\",
            \"WXO_TENANT_ID\":         \"${WXO_TENANT_ID}\",
            \"WXO_API_KEY\":           \"${_API_KEY_VAL}\",
            \"WXO_TOKEN_URL\":         \"${_TOKEN_URL_VAL}\",
            \"WXO_OTEL_EXPORT_URL\":   \"${WXO_OTEL_EXPORT_URL}\",
            \"WXO_ENVIRONMENT_NAME\":  \"${ENVIRONMENT_NAME}\"
        }"
    fi

    echo "  WXO_DEPLOYMENT_MODE  = ${WXO_DEPLOYMENT_MODE:-cloud}"
    echo "  WXO_AGENT_ID         = ${WXO_AGENT_ID}"
    echo "  WXO_AGENT_NAME       = ${AGENT_NAME}"
    if [ "${WXO_DEPLOYMENT_MODE:-cloud}" != "cpd" ]; then
        echo "  WXO_TENANT_ID        = ${WXO_TENANT_ID}"
    fi
    echo "  WXO_ENVIRONMENT_NAME = ${ENVIRONMENT_NAME}"
    echo "  WXO_OTEL_EXPORT_URL  = ${WXO_OTEL_EXPORT_URL:0:50}..."

    aws bedrock-agentcore-control update-agent-runtime \
        --agent-runtime-id "${AGENT_REF}" \
        --agent-runtime-artifact "{\"containerConfiguration\":{\"containerUri\":\"${PATCHED_URI}\"}}" \
        --role-arn "${ROLE_ARN_RUNTIME}" \
        --network-configuration "{\"networkMode\":\"${NETWORK_MODE}\"}" \
        --protocol-configuration "{\"serverProtocol\":\"${SERVER_PROTOCOL}\"}" \
        --environment-variables "${_RT_ENV}" \
        --region "${AWS_REGION}" --output text --query "agentRuntimeId" > /dev/null

    echo "  ✓ Runtime updated — waiting for READY..."
    wait_ready "Runtime" 30 10 "READY" \
        aws bedrock-agentcore-control get-agent-runtime \
            --agent-runtime-id "${AGENT_REF}" --region "${AWS_REGION}" \
            --query "status" --output text

    # ── Summary ───────────────────────────────────────────────────────────────
    echo ""
    echo "══════════════════════════════════════════════════════════════════"
    echo "  Done"
    echo "  Runtime ARN  : arn:aws:bedrock-agentcore:${AWS_REGION}:${AWS_ACCOUNT_ID}:runtime/${AGENT_REF}"
    echo "  Patched image: ${PATCHED_URI}"
    echo ""
    echo "  Span path: sitecustomize.py → WXO directly (no Lambda hop)"
    echo "  Agent appears in WXO under: ${DISPLAY} / env=${ENVIRONMENT_NAME}"
    echo ""
    echo "  Monitor container logs via CloudWatch:"
    echo "    aws logs tail /aws/bedrock-agentcore/runtime/${AGENT_REF} --follow --region ${AWS_REGION}"
    echo "══════════════════════════════════════════════════════════════════"
}

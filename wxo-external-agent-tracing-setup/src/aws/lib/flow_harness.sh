#!/usr/bin/env bash
# =============================================================================
# lib/flow_harness.sh  —  Flow A: Harness agent wiring
#
# Zero Docker, zero image change.
# Harness managed images ship aws-opentelemetry-distro pre-installed.
# We only inject OTEL_* env vars via update-harness.
#
# How spans flow:
#   ADOT SDK (pre-installed in managed image)
#     → reads OTEL_EXPORTER_OTLP_ENDPOINT at startup
#     → pushes OTLP/HTTP protobuf to API GW after every invocation
#     → API GW → Lambda → WXO Agent Analytics
#
# Sourced by wire_agent.sh.  Not executed directly.
# =============================================================================

run_flow_harness() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║  Flow A — Harness  (env vars only · no Docker · no image)   ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""

    # ── [1/3] Fetch harness metadata ─────────────────────────────────────────
    echo "[1/3] Fetching harness from AgentCore..."

    local HARNESS_JSON
    HARNESS_JSON=$(aws bedrock-agentcore-control get-harness \
        --harness-id "${AGENT_REF}" --region "${AWS_REGION}" --output json 2>&1) || {
        echo ""
        echo "  ✗ Harness '${AGENT_REF}' not found in region ${AWS_REGION}."
        echo ""
        echo "  List your harnesses:"
        echo "    aws bedrock-agentcore-control list-harnesses --region ${AWS_REGION} --output table"
        exit 1
    }

    local HARNESS_NAME RUNTIME_ID AGENT_NAME DISPLAY
    HARNESS_NAME=$(echo "${HARNESS_JSON}" | python3 -c \
        "import sys,json; print(json.load(sys.stdin)['harness']['harnessName'])")
    RUNTIME_ID=$(echo "${HARNESS_JSON}" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(d['harness']['environment']['agentCoreRuntimeEnvironment']['agentRuntimeId'])")
    AGENT_NAME=$(snake_name "${HARNESS_NAME}")
    DISPLAY="${WXO_DISPLAY_NAME:-${HARNESS_NAME}}"

    echo "  ✓ ${HARNESS_NAME}"
    echo "    Runtime ID : ${RUNTIME_ID}"
    echo "    Agent name : ${AGENT_NAME}"
    echo "    Display    : ${DISPLAY}"

    # ── [2/3] Shared infra + SSM ──────────────────────────────────────────────
    echo ""
    ensure_infra

    echo ""
    echo "[2/3] Writing agent identity to SSM..."
    write_ssm_identity "${RUNTIME_ID}" "${AGENT_NAME}" "${DISPLAY}"

    # ── [3/3] Inject OTEL_* + WXO_* env vars into the harness ───────────────
    echo ""
    echo "[3/3] Injecting env vars into harness (no image change)..."

    # Bake WXO identity into OTEL_RESOURCE_ATTRIBUTES so the Lambda reads it
    # straight from the protobuf span.  The ADOT SDK copies every key=value
    # pair here into every span it emits.
    local RESOURCE_ATTRS="aws.agent.runtime.id=${RUNTIME_ID},wxo.agent.id=${WXO_AGENT_ID},wxo.agent.name=${AGENT_NAME},wxo.environment=${ENVIRONMENT_NAME}"

    if [ "${WXO_DEPLOYMENT_MODE:-cloud}" != "cpd" ]; then
        if [ -z "${WXO_TENANT_ID:-}" ] && [ -n "${WXO_OTEL_EXPORT_URL:-}" ]; then
            if [[ "${WXO_OTEL_EXPORT_URL}" =~ /instances/([^/]+) ]]; then
                WXO_TENANT_ID="${BASH_REMATCH[1]}"
                WXO_TENANT_ID="${WXO_TENANT_ID%%\?*}"
                WXO_TENANT_ID="${WXO_TENANT_ID%%\#*}"
            fi
        fi
    fi

    # Inject WXO_TENANT_ID and WXO_OTEL_EXPORT_URL directly as harness env
    # vars so the Lambda reads them from os.environ without any SSM call.
    # Values come from config/aws.env (WXO_TENANT_ID, WXO_OTEL_EXPORT_URL) —
    # NOT from shared.env — enabling each harness to target a different tenant.
    local MERGED_ENV
    MERGED_ENV=$(echo "${HARNESS_JSON}" | python3 -c "
import sys, json
d   = json.load(sys.stdin)
env = dict(d['harness'].get('environmentVariables', {}))
env['OTEL_EXPORTER_OTLP_ENDPOINT'] = '${OTLP_ENDPOINT}'
env['OTEL_EXPORTER_OTLP_PROTOCOL'] = 'http/protobuf'
env['OTEL_TRACES_EXPORTER']        = 'otlp'
env['OTEL_LOGS_EXPORTER']          = 'none'
env['OTEL_SERVICE_NAME']           = '${AGENT_NAME}'
env['OTEL_RESOURCE_ATTRIBUTES']    = '${RESOURCE_ATTRS}'
if '${WXO_DEPLOYMENT_MODE:-cloud}' != 'cpd':
    env['WXO_TENANT_ID']           = '${WXO_TENANT_ID}'
env['WXO_OTEL_EXPORT_URL']         = '${WXO_OTEL_EXPORT_URL}'
env['WXO_AGENT_ID']                = '${WXO_AGENT_ID}'
env['WXO_AGENT_NAME']              = '${AGENT_NAME}'
env['WXO_ENVIRONMENT_NAME']        = '${ENVIRONMENT_NAME}'
print(json.dumps(env))")

    aws bedrock-agentcore-control update-harness \
        --harness-id "${AGENT_REF}" \
        --environment-variables "${MERGED_ENV}" \
        --region "${AWS_REGION}" \
        --output text --query "harness.harnessId" > /dev/null

    echo "  ✓ Env vars set:"
    echo "    OTEL_EXPORTER_OTLP_ENDPOINT = ${OTLP_ENDPOINT}"
    echo "    OTEL_EXPORTER_OTLP_PROTOCOL = http/protobuf"
    echo "    OTEL_TRACES_EXPORTER        = otlp"
    echo "    OTEL_LOGS_EXPORTER          = none"
    echo "    OTEL_SERVICE_NAME           = ${AGENT_NAME}"
    echo "    OTEL_RESOURCE_ATTRIBUTES    = ${RESOURCE_ATTRS}"
    if [ "${WXO_DEPLOYMENT_MODE:-cloud}" != "cpd" ]; then
        echo "    WXO_TENANT_ID               = ${WXO_TENANT_ID}"
    fi
    echo "    WXO_OTEL_EXPORT_URL         = ${WXO_OTEL_EXPORT_URL:0:50}..."
    echo "    WXO_AGENT_ID                = ${WXO_AGENT_ID}"
    echo "    WXO_AGENT_NAME              = ${AGENT_NAME}"
    echo "    WXO_ENVIRONMENT_NAME        = ${ENVIRONMENT_NAME}"
    echo ""
    echo "  Waiting for READY..."
    wait_ready "Harness" 30 10 "READY" \
        aws bedrock-agentcore-control get-harness \
            --harness-id "${AGENT_REF}" --region "${AWS_REGION}" \
            --query "harness.status" --output text

    # ── Summary ───────────────────────────────────────────────────────────────
    echo ""
    echo "══════════════════════════════════════════════════════════════════"
    echo "  Done"
    echo "  Harness ARN  : arn:aws:bedrock-agentcore:${AWS_REGION}:${AWS_ACCOUNT_ID}:harness/${AGENT_REF}"
    echo "  Lambda       : arn:aws:lambda:${AWS_REGION}:${AWS_ACCOUNT_ID}:function:${HOOK_FUNCTION}"
    echo "  OTLP endpoint: ${OTLP_ENDPOINT}"
    echo ""
    echo "  Monitor Lambda logs:"
    echo "    aws logs tail /aws/lambda/${HOOK_FUNCTION} --follow --region ${AWS_REGION}"
    echo "══════════════════════════════════════════════════════════════════"
}

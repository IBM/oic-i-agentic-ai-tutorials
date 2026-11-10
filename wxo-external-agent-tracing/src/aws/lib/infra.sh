#!/usr/bin/env bash
# =============================================================================
# lib/infra.sh  —  Shared infrastructure helpers
#
# Sourced by wire_agent.sh and the flow scripts.
# Never executed directly.
# =============================================================================

# ── Derive a snake_case service name from an agent ID / harness name ─────────
# Strips the trailing random suffix (up to 12 chars) then lowercases + slugifies.
snake_name() {
    echo "$1" | python3 -c "
import sys, re
raw   = sys.stdin.read().strip()
parts = raw.rsplit('-', 1)
base  = parts[0] if len(parts) == 2 and len(parts[1]) <= 12 else raw
snake = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', '_', base).lower()
snake = re.sub(r'[^a-z0-9]+', '_', snake).strip('_')
print(snake or 'aws_agentcore_agent')"
}

# ── Put an SSM parameter via python3/boto3 (overwrites if exists) ────────────
# Args: <name> <value> <type: String|SecureString>
ssm_put() {
    python3 -c "
import boto3, os, sys
ssm = boto3.client('ssm', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
ssm.put_parameter(Name=sys.argv[1], Value=sys.argv[2], Type=sys.argv[3], Overwrite=True)
" "$1" "$2" "$3"
}

# ── Store per-agent WXO identity in SSM (keyed by runtime_id) ────────────────
# Args: <runtime_id> <agent_name> <display_name>
#
# Stores six SSM entries under /wxo-agent/agents/<runtime_id>/:
#   agent_id           — WXO agent UUID
#   agent_name         — snake_case name
#   agent_display_name — human-readable label
#   tenant_id          — WXO tenant (multi-tenant routing for Flow A harness)
#   export_url         — WXO OTLP endpoint (multi-tenant routing for Flow A harness)
#   environment        — draft | live
#
# The Lambda reads tenant_id + export_url from here when it cannot find them
# in its own environment (Flow A / harness path) — this is the canonical
# multi-tenant design: each harness agent owns its own SSM entries.
write_ssm_identity() {
    local runtime_id="$1" agent_name="$2" display_name="$3"

    ssm_put "${SSM_PREFIX}/agents/${runtime_id}/agent_id"           "${WXO_AGENT_ID}" "SecureString"
    ssm_put "${SSM_PREFIX}/agents/${runtime_id}/agent_name"         "${agent_name}"   "String"
    ssm_put "${SSM_PREFIX}/agents/${runtime_id}/agent_display_name" "${display_name}" "String"

    # ── Multi-tenant routing — stored per runtime_id so the Lambda can serve
    #    any number of harness agents pointing to different WXO tenants without
    #    any per-agent env var on the Lambda itself.
    #    CPD mode has no tenant header, so tenant_id is skipped; the Lambda builds
    #    the export URL from /wxo-agent/cpd/* when export_url is not stored.
    if [ "${WXO_DEPLOYMENT_MODE:-cloud}" != "cpd" ]; then
        if [ -z "${WXO_TENANT_ID:-}" ] && [ -n "${WXO_OTEL_EXPORT_URL:-}" ]; then
            if [[ "${WXO_OTEL_EXPORT_URL}" =~ /instances/([^/]+) ]]; then
                WXO_TENANT_ID="${BASH_REMATCH[1]}"
                WXO_TENANT_ID="${WXO_TENANT_ID%%\?*}"
                WXO_TENANT_ID="${WXO_TENANT_ID%%\#*}"
            fi
        fi
        ssm_put "${SSM_PREFIX}/agents/${runtime_id}/tenant_id" "${WXO_TENANT_ID}" "SecureString"
    fi

    if [ -n "${WXO_OTEL_EXPORT_URL:-}" ]; then
        ssm_put "${SSM_PREFIX}/agents/${runtime_id}/export_url" "${WXO_OTEL_EXPORT_URL}" "String"
    fi

    ssm_put "${SSM_PREFIX}/agents/${runtime_id}/environment" "${ENVIRONMENT_NAME:-draft}" "String"

    echo "  ✓ SSM  ${SSM_PREFIX}/agents/${runtime_id}/"
    echo "         agent_id           = ${WXO_AGENT_ID}"
    echo "         agent_name         = ${agent_name}"
    echo "         agent_display_name = ${display_name}"
    if [ "${WXO_DEPLOYMENT_MODE:-cloud}" != "cpd" ]; then
        echo "         tenant_id          = ${WXO_TENANT_ID}"
    fi
    echo "         export_url         = ${WXO_OTEL_EXPORT_URL:0:50}..."
    echo "         environment        = ${ENVIRONMENT_NAME:-draft}"
}

# ── Ensure the shared Lambda + API Gateway exist ──────────────────────────────
# Sets globals: OTLP_ENDPOINT  HOOK_ARN  APIGW_ID
# No ADOT layer needed — agentcore_trace_hook.py uses stdlib + boto3 only.

ensure_infra() {
    echo "[infra] Syncing tenant credentials to SSM..."
    bash "${SCRIPT_DIR}/aws/ssm_params.sh" 2>&1 | sed 's/^/  /'
    echo ""
    echo "[infra] Checking shared OTLP collector (Lambda + API GW)..."

    local _APIGW_ID _ENDPOINT

    # Try to read the cached API GW ID from SSM
    _APIGW_ID=$(aws ssm get-parameter --name "${APIGW_SSM_KEY}" \
        --region "${AWS_REGION}" --query "Parameter.Value" \
        --output text 2>/dev/null || echo "")

    if [ -n "${_APIGW_ID}" ]; then
        _ENDPOINT=$(aws apigatewayv2 get-api --api-id "${_APIGW_ID}" \
            --region "${AWS_REGION}" --query "ApiEndpoint" \
            --output text 2>/dev/null || echo "")
        [ -z "${_ENDPOINT}" ] && _APIGW_ID=""   # API GW was deleted — recreate
    fi

    if [ -z "${_APIGW_ID}" ]; then
        echo "  Not found — creating Lambda + API GW (one-time setup)..."
        _create_infra
        _APIGW_ID="${APIGW_ID}"
    else
        APIGW_ID="${_APIGW_ID}"
        echo "  ✓ Reusing existing API GW: ${_APIGW_ID}"
        # Always redeploy Lambda code so:
        #   1. Latest agentcore_trace_hook.py is live
        #   2. Warm containers are recycled → SSM cache is cleared
        #      (important after WXO_AGENT_ID changes in config.env)
        echo "  Redeploying Lambda code (clears warm-container SSM cache)..."
        _deploy_lambda_code
    fi

    HOOK_ARN="arn:aws:lambda:${AWS_REGION}:${AWS_ACCOUNT_ID}:function:${HOOK_FUNCTION}"
    OTLP_ENDPOINT=$(aws apigatewayv2 get-api --api-id "${APIGW_ID}" \
        --region "${AWS_REGION}" --query "ApiEndpoint" --output text)

    # Ensure bedrock-agentcore can invoke the Lambda (idempotent)
    aws lambda remove-permission --function-name "${HOOK_FUNCTION}" \
        --statement-id "AllowAgentCoreInvoke" --region "${AWS_REGION}" 2>/dev/null || true
    aws lambda add-permission --function-name "${HOOK_FUNCTION}" \
        --statement-id "AllowAgentCoreInvoke" --action "lambda:InvokeFunction" \
        --principal "bedrock-agentcore.amazonaws.com" \
        --region "${AWS_REGION}" --output text --query "Statement" > /dev/null

    echo "  ✓ OTLP endpoint: ${OTLP_ENDPOINT}"
}

# ── Package and push Lambda code (used by both create and update paths) ───────
_deploy_lambda_code() {
    local _PKG _LAMBDA_ENV
    _PKG="$(mktemp -d)"
    cp "${SCRIPT_DIR}/aws/agentcore_trace_hook.py" "${_PKG}/"
    cd "${_PKG}" && zip -qr lambda.zip agentcore_trace_hook.py && cd - > /dev/null

    # WXO_DEPLOYMENT_MODE tells the Lambda how to authenticate (cloud: API key,
    # cpd: username/password from SSM /wxo-agent/cpd/*). One Lambda = one mode.
    _LAMBDA_ENV="{\"Variables\":{\"SSM_PREFIX\":\"${SSM_PREFIX}\",\"WXO_ENVIRONMENT_NAME\":\"${ENVIRONMENT_NAME:-draft}\",\"WXO_DEPLOYMENT_MODE\":\"${WXO_DEPLOYMENT_MODE:-cloud}\"}}"

    local _FUNC_EXISTS
    _FUNC_EXISTS=$(aws lambda get-function --function-name "${HOOK_FUNCTION}" \
        --region "${AWS_REGION}" --query "Configuration.FunctionName" \
        --output text 2>/dev/null || echo "")

    if [ -z "${_FUNC_EXISTS}" ]; then
        local _ROLE_ARN
        _ROLE_ARN=$(aws iam get-role --role-name "${ROLE_NAME}" --query "Role.Arn" --output text)
        aws lambda create-function --function-name "${HOOK_FUNCTION}" \
            --runtime python3.12 --role "${_ROLE_ARN}" \
            --handler agentcore_trace_hook.lambda_handler \
            --zip-file "fileb://${_PKG}/lambda.zip" --timeout 60 --memory-size 256 \
            --region "${AWS_REGION}" --environment "${_LAMBDA_ENV}" \
            --output text --query "FunctionArn" > /dev/null
        echo "  ✓ Lambda created"
    else
        aws lambda update-function-code --function-name "${HOOK_FUNCTION}" \
            --zip-file "fileb://${_PKG}/lambda.zip" --region "${AWS_REGION}" \
            --output text --query "FunctionArn" > /dev/null
        aws lambda wait function-updated \
            --function-name "${HOOK_FUNCTION}" --region "${AWS_REGION}"
        aws lambda update-function-configuration --function-name "${HOOK_FUNCTION}" \
            --environment "${_LAMBDA_ENV}" \
            --region "${AWS_REGION}" \
            --output text --query "FunctionArn" > /dev/null
        aws lambda wait function-updated \
            --function-name "${HOOK_FUNCTION}" --region "${AWS_REGION}"
        echo "  ✓ Lambda code + config updated"
    fi
    rm -rf "${_PKG}"
}

# ── Internal: create Lambda + API GW from scratch ────────────────────────────
_create_infra() {
    # IAM role
    local _ROLE_ARN
    _ROLE_ARN=$(aws iam get-role --role-name "${ROLE_NAME}" \
        --query "Role.Arn" --output text 2>/dev/null || echo "")

    if [ -z "${_ROLE_ARN}" ]; then
        aws iam create-role --role-name "${ROLE_NAME}" \
            --assume-role-policy-document \
            '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
            --output text --query "Role.Arn" > /dev/null
        aws iam attach-role-policy --role-name "${ROLE_NAME}" \
            --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
        aws iam put-role-policy --role-name "${ROLE_NAME}" \
            --policy-name wxo-agent-tracer-policy \
            --policy-document "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":[\"ssm:GetParameter\",\"ssm:GetParameters\",\"ssm:GetParametersByPath\"],\"Resource\":\"arn:aws:ssm:${AWS_REGION}:${AWS_ACCOUNT_ID}:parameter${SSM_PREFIX}/*\"}]}"
        echo "  ✓ IAM role created — waiting 10 s for propagation..."
        sleep 10
    fi

    # Lambda (create or update via shared helper)
    _deploy_lambda_code
    echo "  ✓ Lambda ready"

    # API Gateway
    APIGW_ID=$(aws apigatewayv2 create-api --name "wxo-otlp-collector" \
        --protocol-type HTTP --region "${AWS_REGION}" \
        --output text --query "ApiId")
    local _INTEG_ID
    _INTEG_ID=$(aws apigatewayv2 create-integration --api-id "${APIGW_ID}" \
        --integration-type AWS_PROXY \
        --integration-uri "arn:aws:lambda:${AWS_REGION}:${AWS_ACCOUNT_ID}:function:${HOOK_FUNCTION}" \
        --payload-format-version "2.0" --region "${AWS_REGION}" \
        --output text --query "IntegrationId")
    aws apigatewayv2 create-route --api-id "${APIGW_ID}" --route-key "\$default" \
        --target "integrations/${_INTEG_ID}" --region "${AWS_REGION}" \
        --output text --query "RouteId" > /dev/null
    aws apigatewayv2 create-stage --api-id "${APIGW_ID}" --stage-name "\$default" \
        --auto-deploy --region "${AWS_REGION}" --output text --query "StageName" > /dev/null
    aws lambda add-permission --function-name "${HOOK_FUNCTION}" \
        --statement-id "AllowAPIGWOTLPInvoke" --action "lambda:InvokeFunction" \
        --principal "apigateway.amazonaws.com" \
        --source-arn "arn:aws:execute-api:${AWS_REGION}:${AWS_ACCOUNT_ID}:${APIGW_ID}/*" \
        --region "${AWS_REGION}" --output text --query "Statement" > /dev/null 2>&1 || true

    # Cache API GW ID in SSM so future runs reuse it
    ssm_put "${APIGW_SSM_KEY}" "${APIGW_ID}" "String"

    echo "  ✓ API Gateway created (ID: ${APIGW_ID})"
}

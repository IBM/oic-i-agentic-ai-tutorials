#!/usr/bin/env bash
# =============================================================================
# lib/common.sh  —  Shared shell helpers used by all platform flows
#
# Sourced by aws/lib/flow_harness.sh, aws/lib/flow_runtime.sh, and
# vertex/lib/flow_selfhosted.sh.  Never executed directly.
# =============================================================================

# ── wait_ready ────────────────────────────────────────────────────────────────
# Poll a shell command until it returns a given expected value, or times out.
#
# Usage:
#   wait_ready <label> <max_attempts> <sleep_sec> <expected_value> <cmd...>
#
# Arguments:
#   label          Human-readable name for log output (e.g. "Harness", "Runtime")
#   max_attempts   Maximum number of poll iterations (e.g. 30)
#   sleep_sec      Seconds to sleep between polls (e.g. 10)
#   expected_value The stdout value that signals success (e.g. "READY" or "True")
#   cmd...         Command + args to run; its stdout is compared to expected_value
#
# Returns 0 on success, 1 on timeout.
#
# Example:
#   wait_ready "AgentCore Harness" 30 10 "READY" \
#       aws bedrock-agentcore-control get-harness \
#           --harness-id "${AGENT_REF}" --region "${AWS_REGION}" \
#           --query "harness.status" --output text
# =============================================================================
wait_ready() {
    local label="$1" max="$2" delay="$3" expected="$4"
    shift 4   # remaining args are the command to run

    local status i
    for i in $(seq 1 "${max}"); do
        status=$("$@" 2>/dev/null || echo "UNKNOWN")
        if [ "${status}" = "${expected}" ]; then
            echo "  ✓ ${label} ${expected}"
            return 0
        fi
        printf "  ... %s (%d/%d)\n" "${status}" "${i}" "${max}"
        sleep "${delay}"
    done

    echo "  ✗ Timed out waiting for ${label} to reach '${expected}' (${max} attempts × ${delay}s)"
    return 1
}

# =============================================================================
# Deployment mode — WXO_DEPLOYMENT_MODE = cloud (default) | cpd
#
#   cloud  IBM Cloud SaaS
#            required: API_KEY, TOKEN_URL, WXO_TENANT_ID, WXO_OTEL_EXPORT_URL
#   cpd    Cloud Pak for Data (on-prem)
#            required: CPD_HOST_URL, CPD_USERNAME, CPD_PASSWORD,
#                      CPD_INSTANCE_ID, CPD_NAMESPACE
#            WXO_OTEL_EXPORT_URL is built from them unless set explicitly:
#              <CPD_HOST_URL>/<CPD_NAMESPACE>/instances/<CPD_INSTANCE_ID>/v1/agentops-v3/traces
# =============================================================================

# wxo_is_unset <value>  — true when empty or still a "<placeholder>"
wxo_is_unset() {
    [ -z "${1:-}" ] || [[ "${1}" == *"<"* ]]
}

# wxo_resolve_mode
# Normalises WXO_DEPLOYMENT_MODE and (cpd) derives WXO_OTEL_EXPORT_URL.
# Exports the result so every child script/process inherits it.
wxo_resolve_mode() {
    local _mode
    _mode="$(printf '%s' "${WXO_DEPLOYMENT_MODE:-cloud}" | tr '[:upper:]' '[:lower:]')"
    case "${_mode}" in
        cloud|cpd) ;;
        *)
            echo "  ✗ WXO_DEPLOYMENT_MODE must be 'cloud' or 'cpd' (got: '${WXO_DEPLOYMENT_MODE}')"
            return 1
            ;;
    esac
    export WXO_DEPLOYMENT_MODE="${_mode}"

    if [ "${_mode}" = "cpd" ] && wxo_is_unset "${WXO_OTEL_EXPORT_URL:-}"; then
        if ! wxo_is_unset "${CPD_HOST_URL:-}" && ! wxo_is_unset "${CPD_NAMESPACE:-}" \
           && ! wxo_is_unset "${CPD_INSTANCE_ID:-}"; then
            export WXO_OTEL_EXPORT_URL="${CPD_HOST_URL%/}/${CPD_NAMESPACE}/instances/${CPD_INSTANCE_ID}/v1/agentops-v3/traces"
        else
            export WXO_OTEL_EXPORT_URL=""
        fi
    fi

    # Derive WXO_TENANT_ID from WXO_OTEL_EXPORT_URL if not explicitly set
    if [ "${_mode}" != "cpd" ]; then
        if wxo_is_unset "${WXO_TENANT_ID:-}" && ! wxo_is_unset "${WXO_OTEL_EXPORT_URL:-}"; then
            if [[ "${WXO_OTEL_EXPORT_URL}" =~ /instances/([^/]+) ]]; then
                local _tid="${BASH_REMATCH[1]}"
                _tid="${_tid%%\?*}"
                _tid="${_tid%%\#*}"
                export WXO_TENANT_ID="${_tid}"
            fi
        fi
    fi
}

# wxo_validate_mode <config-description>
# Prints every missing setting for the active mode; returns 1 if any are missing.
wxo_validate_mode() {
    local _cfg_desc="${1:-config}" _var _missing=0 _required
    if [ "${WXO_DEPLOYMENT_MODE:-cloud}" = "cpd" ]; then
        _required="CPD_HOST_URL CPD_USERNAME CPD_PASSWORD CPD_INSTANCE_ID CPD_NAMESPACE ENVIRONMENT_NAME"
    else
        _required="API_KEY TOKEN_URL WXO_OTEL_EXPORT_URL ENVIRONMENT_NAME"
    fi
    for _var in ${_required}; do
        if wxo_is_unset "${!_var:-}"; then
            echo "  ✗ ${_var} is not set in ${_cfg_desc}  (WXO_DEPLOYMENT_MODE=${WXO_DEPLOYMENT_MODE:-cloud})"
            _missing=1
        fi
    done
    return "${_missing}"
}

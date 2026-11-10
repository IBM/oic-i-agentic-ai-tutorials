#!/usr/bin/env bash
# =============================================================================
# aws/wire_agent.sh  —  Wire any AgentCore agent to WXO Agent Analytics tracing
#
# All configuration is read from config/shared.env + config/aws.env.
# Called by the top-level wire_agent.sh --aws.
#
# Usage (direct):
#   ./aws/wire_agent.sh [--harness|--runtime] [--dry-run]
#
# Agent input — WXO_AGENT_MAP (required, set in config/aws.env):
#   One or many agents expressed as a JSON object.  Each key is an AGENT_REF
#   (harness ID or runtime ID); the value carries the WXO identity fields.
#
#   Example (one agent):
#     WXO_AGENT_MAP='{"harness_hmhcq-FGWZ2OHwpG": {
#       "wxo_agent_id":        "<uuid>",
#       "wxo_tenant_id":       "<tenant>",
#       "wxo_otel_export_url": "<url>"
#     }}'
#
#   Example (many agents — each may target a different WXO tenant):
#     WXO_AGENT_MAP='{
#       "harness_hmhcq-FGWZ2OHwpG": {"wxo_agent_id":"...", "wxo_tenant_id":"...", "wxo_otel_export_url":"..."},
#       "WxoFlaskAgent-pUrlXvGkTh":  {"wxo_agent_id":"...", "wxo_tenant_id":"...", "wxo_otel_export_url":"..."}
#     }'
#
#   Optional per-entry fields:
#     wxo_agent_name    snake_case name in WXO  (auto-derived if absent)
#     wxo_display_name  human-readable label    (defaults to wxo_agent_name)
#     environment       draft | live            (defaults to ENVIRONMENT_NAME)
#
# Two flows (set AGENT_TYPE in config/aws.env, or override with --harness / --runtime):
#   harness → Flow A: env vars only, no Docker, no image change
#             AWS managed images already ship ADOT; we inject OTEL_* vars.
#   runtime → Flow B: sitecustomize.py image patch
#             No user code touched.
#
# Pre-requisites:
#   - config/shared.env + config/aws.env filled in (WXO_AGENT_MAP required)
#   - ssm_params.sh run once  (stores WXO credentials in SSM)
#   - Docker running  (only needed for AGENT_TYPE=runtime)
# =============================================================================

set -euo pipefail

# Resolve to the repo root (parent of this aws/ dir)
export SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Load config if not already exported
if [ -z "${WXO_DEPLOYMENT_MODE:-}" ]; then
    if [ -f "${SCRIPT_DIR}/../config.env" ]; then
        eval "$(python3 "${SCRIPT_DIR}/lib/parse_env_section.py" "${SCRIPT_DIR}/../config.env" "aws" "sh")"
    elif [ -f "${SCRIPT_DIR}/../config/config.env" ]; then
        eval "$(python3 "${SCRIPT_DIR}/lib/parse_env_section.py" "${SCRIPT_DIR}/../config/config.env" "aws" "sh")"
    elif [ -f "${SCRIPT_DIR}/../config/aws.env" ]; then
        set -a
        [ -f "${SCRIPT_DIR}/../config/shared.env" ] && source "${SCRIPT_DIR}/../config/shared.env"
        source "${SCRIPT_DIR}/../config/aws.env"
        set +a
    fi
fi
source "${SCRIPT_DIR}/lib/common.sh"
wxo_resolve_mode || exit 1
source "${SCRIPT_DIR}/aws/lib/infra.sh"
source "${SCRIPT_DIR}/aws/lib/flow_harness.sh"
source "${SCRIPT_DIR}/aws/lib/flow_runtime.sh"

# ── Shared constants (consumed by lib/ functions) ─────────────────────────────
SSM_PREFIX="/wxo-agent"
APIGW_SSM_KEY="${SSM_PREFIX}/APIGW_ID"
HOOK_FUNCTION="wxo-agentcore-trace-hook"
ROLE_NAME="wxo-agent-tracer-role"
REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
AGENT_PATCH_DIR="${SCRIPT_DIR}/aws/agent-patch"

# ── Flags ─────────────────────────────────────────────────────────────────────
DRY_RUN=0
for arg in "$@"; do
    case "${arg}" in
        --harness) AGENT_TYPE="harness" ;;
        --runtime) AGENT_TYPE="runtime" ;;
        --dry-run) DRY_RUN=1 ;;
        --help|-h)
            sed -n '2,/^set -/p' "$0" | grep '^#' | sed 's/^# \{0,2\}//'
            exit 0
            ;;
        *) echo "Unknown option: ${arg}"; echo "Run $0 --help for usage."; exit 1 ;;
    esac
done

if [[ "${AGENT_TYPE}" != "harness" && "${AGENT_TYPE}" != "runtime" ]]; then
    echo "  ✗ AGENT_TYPE must be 'harness' or 'runtime' (got: '${AGENT_TYPE}')"
    exit 1
fi

# ── Banner ────────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║         WXO AgentCore → Agent Analytics  Tracing Setup          ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
echo "  WXO mode    : ${WXO_DEPLOYMENT_MODE}"
echo "  AWS account : ${AWS_ACCOUNT_ID}"
echo "  Region      : ${AWS_REGION}"
echo "  Agent type  : ${AGENT_TYPE}"
echo ""

if [ "${DRY_RUN}" -eq 1 ]; then
    echo "  --dry-run: no changes made."
    exit 0
fi

# ── Require WXO_AGENT_MAP ─────────────────────────────────────────────────────
_agent_map="${WXO_AGENT_MAP:-}"
if [ -z "${_agent_map}" ]; then
    echo "  ✗ WXO_AGENT_MAP is not set in config/aws.env"
    echo ""
    echo "  Set WXO_AGENT_MAP to a JSON object with one or more agents:"
    echo '    WXO_AGENT_MAP='"'"'{"<AGENT_REF>": {"wxo_agent_id":"<uuid>", "wxo_tenant_id":"<tid>", "wxo_otel_export_url":"<url>"}}'"'"
    echo ""
    echo "  See config/aws.env.example for the full schema."
    exit 1
fi

echo "  WXO_AGENT_MAP — wiring $(echo "${_agent_map}" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "?") agent(s)."
echo ""

# Parse the map and iterate; Python handles per-agent env overrides
python3 - <<'PYEOF'
import json, os, re, sys, subprocess

def extract_tenant_id(url):
    if url:
        m = re.search(r'/instances/([^/?#]+)', url)
        if m:
            return m.group(1).strip()
    return ""

raw = os.environ.get("WXO_AGENT_MAP", "")
try:
    agent_map = json.loads(raw)
except Exception as exc:
    print(f"  ✗ WXO_AGENT_MAP is not valid JSON: {exc}", file=sys.stderr)
    sys.exit(1)

agent_type    = os.environ.get("AGENT_TYPE", "harness")
env_name_dflt = os.environ.get("ENVIRONMENT_NAME", "draft")
# SCRIPT_DIR is exported by aws/wire_agent.sh before this heredoc runs
script_dir    = os.environ.get("SCRIPT_DIR", ".")
aws_dir       = os.path.join(script_dir, "aws")

# Global defaults from the platform config file — every entry falls back to these
# when it does not supply its own tenant / URL / key / token-url.
_dflt_url      = os.environ.get("WXO_OTEL_EXPORT_URL",  "")
_dflt_tenant   = extract_tenant_id(_dflt_url) or os.environ.get("WXO_TENANT_ID", "")
_dflt_env      = os.environ.get("ENVIRONMENT_NAME",     "draft")
_dflt_api_key  = os.environ.get("API_KEY",              "")
_dflt_tok_url  = os.environ.get("TOKEN_URL",            "")

for agent_ref, cfg in agent_map.items():
    # Only wxo_agent_id is required per entry — everything else falls back to globals
    if not cfg.get("wxo_agent_id"):
        print(f"  ✗ WXO_AGENT_MAP entry '{agent_ref}' missing required field: wxo_agent_id", file=sys.stderr)
        sys.exit(1)

    export_url = cfg.get("wxo_otel_export_url") or _dflt_url
    env = os.environ.copy()
    env["AGENT_REF"]           = agent_ref
    env["WXO_AGENT_ID"]        = cfg["wxo_agent_id"]
    if os.environ.get("WXO_DEPLOYMENT_MODE", "cloud") == "cpd":
        # CPD: no tenant header; export URL derived from CPD_* (or per-agent override)
        env["WXO_TENANT_ID"]   = ""
    else:
        env["WXO_TENANT_ID"]   = cfg.get("wxo_tenant_id") or extract_tenant_id(export_url) or _dflt_tenant
    env["WXO_OTEL_EXPORT_URL"] = export_url
    env["WXO_AGENT_NAME"]      = cfg.get("wxo_agent_name",  "")
    env["WXO_DISPLAY_NAME"]    = cfg.get("wxo_display_name", "")
    env["ENVIRONMENT_NAME"]    = cfg.get("environment", _dflt_env)
    if cfg.get("wxo_api_key"):
        env["API_KEY"] = cfg["wxo_api_key"]
    if cfg.get("wxo_token_url"):
        env["TOKEN_URL"] = cfg["wxo_token_url"]

    _who = ("cpd instance=" + os.environ.get("CPD_INSTANCE_ID", "")) if os.environ.get("WXO_DEPLOYMENT_MODE") == "cpd" else ("tenant=" + env["WXO_TENANT_ID"])
    print(f"\n  ─── Wiring agent_ref={agent_ref!r}  {_who!r} ───")

    lib_name = "flow_harness.sh" if agent_type == "harness" else "flow_runtime.sh"
    lib = os.path.join(aws_dir, "lib", lib_name)
    flow_fn = "run_flow_harness" if agent_type == "harness" else "run_flow_runtime"

    script = f"""
set -euo pipefail
SCRIPT_DIR="{script_dir}"
source "$SCRIPT_DIR/lib/common.sh"
source "$SCRIPT_DIR/aws/lib/infra.sh"
source "{lib}"
SSM_PREFIX="/wxo-agent"
APIGW_SSM_KEY="/wxo-agent/APIGW_ID"
HOOK_FUNCTION="wxo-agentcore-trace-hook"
ROLE_NAME="wxo-agent-tracer-role"
REGISTRY="${{AWS_ACCOUNT_ID}}.dkr.ecr.${{AWS_REGION}}.amazonaws.com"
AGENT_PATCH_DIR="$SCRIPT_DIR/aws/agent-patch"
{flow_fn}
"""
    result = subprocess.run(["bash", "-c", script], env=env)
    if result.returncode != 0:
        print(f"  ✗ Failed to wire {agent_ref!r}", file=sys.stderr)
        sys.exit(result.returncode)
PYEOF

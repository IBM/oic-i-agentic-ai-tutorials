#!/usr/bin/env bash
# =============================================================================
# vertex/wire_agent.sh  —  Wire a Vertex AI agent to WXO Agent Analytics
#
# All configuration is read from config/shared.env + config/vertex.env.
# Called by the top-level wire_agent.sh --vertex.
#
# Usage (direct):
#   ./vertex/wire_agent.sh --reasoning-engine   [--dry-run]
#   ./vertex/wire_agent.sh --selfhosted         [--dry-run]
#
# Agent input — WXO_AGENT_MAP (required, set in config/vertex.env):
#   One or many agents expressed as a JSON object.
#
#   Example (one agent — reasoning-engine):
#     WXO_AGENT_MAP='{"my-engine": {
#       "wxo_agent_id":       "<uuid>",
#       "wxo_tenant_id":      "<tenant>",
#       "wxo_otel_export_url":"<url>",
#       "reasoning_engine_id":"<id>"
#     }}'
#
#   Example (one agent — selfhosted):
#     WXO_AGENT_MAP='{"my-service": {
#       "wxo_agent_id":       "<uuid>",
#       "wxo_tenant_id":      "<tenant>",
#       "wxo_otel_export_url":"<url>",
#       "source_image":       "gcr.io/my-project/my-agent:latest",
#       "cloud_run_service":  "my-service"
#     }}'
#
#   Optional per-entry fields:
#     wxo_agent_name    snake_case name in WXO  (auto-derived if absent)
#     wxo_display_name  human-readable label    (defaults to wxo_agent_name)
#     wxo_api_key       per-tenant API key      (overrides shared API_KEY)
#     wxo_token_url     per-tenant IAM URL      (overrides shared TOKEN_URL)
#     environment       draft | live            (defaults to ENVIRONMENT_NAME)
#
# --reasoning-engine:
#   Patches an existing Vertex AI ReasoningEngine with WXO tracing by
#   re-uploading the agent bytecode via deploy.py.
#
# --selfhosted:
#   Injects sitecustomize.py into your container image and deploys to
#   Cloud Run (CONTAINER_TARGET=cloudrun) or pushes for GKE/Knative.
#
# Pre-requisites (both):
#   - config/shared.env + config/vertex.env filled in (WXO_AGENT_MAP required)
#   - gcloud CLI authenticated
# Pre-requisites (--selfhosted only):
#   - Docker running
# =============================================================================

set -euo pipefail

# Resolve to the repo root (parent of this vertex/ dir)
export SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Load config if not already exported
if [ -z "${WXO_DEPLOYMENT_MODE:-}" ]; then
    if [ -f "${SCRIPT_DIR}/../config.env" ]; then
        eval "$(python3 "${SCRIPT_DIR}/lib/parse_env_section.py" "${SCRIPT_DIR}/../config.env" "vertex" "sh")"
    elif [ -f "${SCRIPT_DIR}/../config/config.env" ]; then
        eval "$(python3 "${SCRIPT_DIR}/lib/parse_env_section.py" "${SCRIPT_DIR}/../config/config.env" "vertex" "sh")"
    elif [ -f "${SCRIPT_DIR}/../config/vertex.env" ]; then
        set -a
        [ -f "${SCRIPT_DIR}/../config/shared.env" ] && source "${SCRIPT_DIR}/../config/shared.env"
        source "${SCRIPT_DIR}/../config/vertex.env"
        set +a
    fi
fi
source "${SCRIPT_DIR}/lib/common.sh"
wxo_resolve_mode || exit 1

# ── Flags ─────────────────────────────────────────────────────────────────────
DRY_RUN=0
FLOW="selfhosted"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --reasoning-engine) FLOW="reasoning-engine" ;;
        --selfhosted)       FLOW="selfhosted" ;;
        --dry-run)          DRY_RUN=1 ;;
        --help|-h)
            sed -n '2,/^set -/p' "$0" | grep '^#' | sed 's/^# \{0,2\}//'
            exit 0
            ;;
        *) echo "Unknown option: $1"; echo "Run $0 --help for usage."; exit 1 ;;
    esac
    shift
done

# ── Banner ────────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║     WXO Vertex AI → Agent Analytics  Tracing Setup              ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
echo "  WXO mode    : ${WXO_DEPLOYMENT_MODE}"
echo "  GCP project : ${GCP_PROJECT_ID}"
echo "  Region      : ${GCP_REGION}"
echo "  Flow        : ${FLOW}  $([ "${FLOW}" = "reasoning-engine" ] && echo "(Vertex AI Reasoning Engine)" || echo "(Self-hosted container)")"
echo ""

if [ "${DRY_RUN}" -eq 1 ]; then
    echo "  --dry-run: no changes made."
    exit 0
fi

export FLOW
export AGENT_PATCH_DIR="${SCRIPT_DIR}/container_hook"

# ── Require WXO_AGENT_MAP ─────────────────────────────────────────────────────
_agent_map="${WXO_AGENT_MAP:-}"
if [ -z "${_agent_map}" ]; then
    echo "  ✗ WXO_AGENT_MAP is not set in config/vertex.env"
    echo ""
    echo "  Set WXO_AGENT_MAP to a JSON object with one or more agents:"
    echo '    WXO_AGENT_MAP='"'"'{"<key>": {"wxo_agent_id":"<uuid>", "wxo_tenant_id":"<tid>", "wxo_otel_export_url":"<url>", "source_image":"<img>"}}'"'"
    echo ""
    echo "  See config/vertex.env.example for the full schema."
    exit 1
fi

echo "  WXO_AGENT_MAP — wiring $(echo "${_agent_map}" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "?") agent(s)."
echo ""

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

flow          = os.environ.get("FLOW", "selfhosted")
env_name_dflt = os.environ.get("ENVIRONMENT_NAME", "draft")
# SCRIPT_DIR is exported by vertex/wire_agent.sh before this heredoc runs
script_dir    = os.environ.get("SCRIPT_DIR", ".")
agent_patch   = os.path.join(script_dir, "container_hook")

# Global defaults — every entry falls back to these when it omits tenant/url/key.
_dflt_url     = os.environ.get("WXO_OTEL_EXPORT_URL",  "")
_dflt_tenant  = extract_tenant_id(_dflt_url) or os.environ.get("WXO_TENANT_ID", "")
_dflt_env     = os.environ.get("ENVIRONMENT_NAME",     "draft")
_dflt_api_key = os.environ.get("API_KEY",              "")
_dflt_tok_url = os.environ.get("TOKEN_URL",            "")

for agent_key, cfg in agent_map.items():
    # Only wxo_agent_id is always required; flow-specific fields validated below
    if not cfg.get("wxo_agent_id"):
        print(f"  ✗ WXO_AGENT_MAP entry '{agent_key}' missing required field: wxo_agent_id", file=sys.stderr)
        sys.exit(1)
    # Skip entries that belong to a different flow — a mixed map (both
    # reasoning-engine and selfhosted entries) is valid; just run the
    # right subset.
    if flow == "selfhosted" and not cfg.get("source_image"):
        print(f"  · Skipping '{agent_key}' — no source_image (not a selfhosted entry)")
        continue
    if flow == "reasoning-engine" and not cfg.get("reasoning_engine_id"):
        print(f"  · Skipping '{agent_key}' — no reasoning_engine_id (not a reasoning-engine entry)")
        continue

    export_url = cfg.get("wxo_otel_export_url") or _dflt_url
    env = os.environ.copy()
    env["WXO_AGENT_ID"]        = cfg["wxo_agent_id"]
    # CPD has no tenant; cloud falls back to the global tenant
    env["WXO_TENANT_ID"]       = "" if os.environ.get("WXO_DEPLOYMENT_MODE") == "cpd" else (cfg.get("wxo_tenant_id") or extract_tenant_id(export_url) or _dflt_tenant)
    env["WXO_OTEL_EXPORT_URL"] = export_url
    env["WXO_AGENT_NAME"]      = cfg.get("wxo_agent_name",  "")
    env["WXO_DISPLAY_NAME"]    = cfg.get("wxo_display_name", "")
    env["ENVIRONMENT_NAME"]    = cfg.get("environment", _dflt_env)
    env["AGENT_PATCH_DIR"]     = agent_patch
    if cfg.get("wxo_api_key"):
        env["API_KEY"] = cfg["wxo_api_key"]
    if cfg.get("wxo_token_url"):
        env["TOKEN_URL"] = cfg["wxo_token_url"]
    if flow == "selfhosted":
        env["SOURCE_IMAGE"]      = cfg["source_image"]
        env["CLOUD_RUN_SERVICE"] = cfg.get("cloud_run_service", agent_key)
    elif flow == "reasoning-engine":
        env["REASONING_ENGINE_ID"] = cfg["reasoning_engine_id"]

    _who = ("cpd instance=" + os.environ.get("CPD_INSTANCE_ID", "")) if os.environ.get("WXO_DEPLOYMENT_MODE") == "cpd" else ("tenant=" + env["WXO_TENANT_ID"])
    print(f"\n  ─── Wiring {flow} key={agent_key!r}  {_who!r} ───")

    if flow == "reasoning-engine":
        result = subprocess.run(
            ["python3", os.path.join(script_dir, "vertex/reasoning_engine/deploy.py")],
            env=env,
        )
    else:
        script = f"""
set -euo pipefail
SCRIPT_DIR="{script_dir}"
source "$SCRIPT_DIR/lib/common.sh"
source "$SCRIPT_DIR/vertex/lib/flow_selfhosted.sh"
run_flow_selfhosted
"""
        result = subprocess.run(["bash", "-c", script], env=env)

    if result.returncode != 0:
        print(f"  ✗ Failed to wire {agent_key!r}", file=sys.stderr)
        sys.exit(result.returncode)
PYEOF

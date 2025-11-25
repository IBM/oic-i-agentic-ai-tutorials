#!/usr/bin/env bash
set -euo pipefail

ENV_NAME="oictutorial"

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

# activate env
orchestrate env activate "$ENV_NAME"

# -----------------------------
# Remove Agents
# -----------------------------
orchestrate agents remove -n oic_cost_inflation_analysis_agent -k native || true
orchestrate agents remove -n oic_cost_insight_agent -k native || true

# -----------------------------
# Remove Python Tools
# -----------------------------
# (these were imported from tools directory in your script)
orchestrate tools remove -n oic_granite_summary_tool || true
orchestrate tools remove -n cost_analysis_tool || true


# -----------------------------
# Remove Knowledge Bases
# -----------------------------
#orchestrate knowledge-bases remove -n streaming_cost_docs || true

# -----------------------------
# Remove Models
# -----------------------------
# Groq
orchestrate models remove -n virtual-model/groq/openai/gpt-oss-120b || true

# Anthropic
orchestrate models remove -n virtual-model/anthropic/claude-sonnet-4-5-20250929 || true

# -----------------------------
# Remove Connections
# -----------------------------
orchestrate connections remove -a "oic_llm_creds" || true
orchestrate connections remove -a "groq_credentials" || true
orchestrate connections remove -a "anthropic_credentials" || true

# -----------------------------
# Re-run import script
# -----------------------------
#bash "${SCRIPT_DIR}/import-all.sh"

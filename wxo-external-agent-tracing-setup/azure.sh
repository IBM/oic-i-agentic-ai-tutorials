#!/usr/bin/env bash
# azure.sh — Azure AI Foundry tracing: deploy the Function App that polls Log Analytics.
# Entrypoint for the [azure] section of config/azure.env (shared setup lives in wire_agent.sh).
#
#   ./azure.sh                  # deploy Function App
#   ./azure.sh --publish-only   # redeploy function code only
#   ./azure.sh --dry-run
set -euo pipefail
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/wire_agent.sh" --platform azure "$@"

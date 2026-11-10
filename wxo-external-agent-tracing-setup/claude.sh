#!/usr/bin/env bash
# claude.sh — Claude tracing: deploy the OTLP forwarder and connect Claude to it.
# Entrypoint for the [claude] section of config/claude.env (shared setup lives in wire_agent.sh).
#
#   ./claude.sh                          # deploy forwarder, then set Claude's OTel endpoint
#   ./claude.sh --target aws|azure|docker
#   ./claude.sh --sync                   # push config only, no redeploy
#   ./claude.sh --local                  # run the OTLP receiver locally (port 4318)
#   ./claude.sh --dry-run
set -euo pipefail
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/wire_agent.sh" --platform claude "$@"

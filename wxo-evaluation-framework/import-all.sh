#!/usr/bin/env bash
set -x

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

orchestrate tools import -k python -f ${SCRIPT_DIR}/agent_tools/banking_tools.py

orchestrate agents import -f ${SCRIPT_DIR}/agent_tools/banking_agent.json

orchestrate agents deploy --name banking_agent
#!/usr/bin/env bash
set -e
# Import all WXO python tools, flows and agents (assumes orchestrate CLI logged in)
orchestrate tools import -k python -f ./wxo_tools/predict_failure.py
orchestrate tools import -k python -f ./wxo_tools/maintenance_cost_tool.py
orchestrate tools import -k python -f ./wxo_tools/book_slot_tool.py
orchestrate tools import -k python -f ./wxo_tools/order_parts_tool.py
orchestrate tools import -k python -f ./wxo_tools/send_notification_tool.py
orchestrate tools import -k flows -f ./wxo_flows/predictive_maintenance_flow.py
orchestrate agents import -f ./wxo_agents/maintenance_agent.yaml
orchestrate agents import -f ./wxo_agents/maintenance_scheduler_agent.yaml
echo "Import complete. Check Orchestrate UI."

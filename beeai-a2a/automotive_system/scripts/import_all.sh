#!/usr/bin/env bash
set -e

echo "===== Importing WXO Tools ====="
orchestrate tools import -k python -f ../wxo_tools/predict_failure.py
orchestrate tools import -k python -f ../wxo_tools/maintenance_cost_tool.py
orchestrate tools import -k python -f ../wxo_tools/book_slot_tool.py
orchestrate tools import -k python -f ../wxo_tools/order_parts_tool.py
orchestrate tools import -k python -f ../wxo_tools/send_notification_tool.py

echo "===== Importing Predictive Maintenance Flow ====="
orchestrate tools import -k flow -f ../wxo_flows/predictive_maintenance_flow.py

echo "===== Importing Agents ====="
orchestrate agents import -f ../wxo_agents/maintenance_agent.yaml
orchestrate agents import -f ../wxo_agents/maintenance_scheduler_agent.yaml

echo "===== Configuring Langfuse Observability ====="

orchestrate settings observability langfuse configure --config-file=../agents_observability/langfuse_config.yml


echo "===== Import Complete. Check Watsonx Orchestrate UI ====="

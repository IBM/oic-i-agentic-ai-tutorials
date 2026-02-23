#!/usr/bin/env bash
set -e

echo "====================================="
echo "WXO Import Script - Predictive Maintenance"
echo "====================================="

# Step 1: Import WXO Tools
echo ""
echo "Step 1/5: Importing WXO Tools..."
orchestrate tools import -k python -f ../wxo_tools/predict_failure.py
orchestrate tools import -k python -f ../wxo_tools/maintenance_cost_tool.py
orchestrate tools import -k python -f ../wxo_tools/book_slot_tool.py
orchestrate tools import -k python -f ../wxo_tools/order_parts_tool.py
orchestrate tools import -k python -f ../wxo_tools/send_notification_tool.py
echo "✓ Tools imported successfully"

# Step 2: Importing BeeAI Integration 
echo ""
echo "Step 2/5: Importing BeeAI Integration Tool..."
orchestrate tools import -k python -f ../wxo_tools/call_beeai_analysis.py
echo "✓ BeeAI tool imported"

# Step 3: Import Flows
echo ""
echo "Step 3/5: Importing Predictive Maintenance Flow..."
orchestrate tools import -k flow -f ../wxo_flows/predictive_maintenance_flow.py
echo "✓ Flow imported successfully"

# Step 4: Import Agents
echo ""
echo "Step 4/5: Importing Agents..."
orchestrate agents import -f ../wxo_agents/maintenance_agent.yaml
orchestrate agents import -f ../wxo_agents/maintenance_scheduler_agent.yaml
echo "✓ Agents imported successfully"

# Step 5: Configure Langfuse Observability
echo ""
echo "Step 5/5: Configuring Langfuse Observability..."
orchestrate settings observability langfuse configure --config-file=../agents_observability/langfuse_config.yml
echo "✓ Observability configured successfully"

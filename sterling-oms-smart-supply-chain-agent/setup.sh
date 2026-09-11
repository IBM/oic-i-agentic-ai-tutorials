#!/bin/bash
set -e
# This script sets up the agent environment and installs necessary dependencies.

#tool import 
orchestrate tools import -k python -f "tools/weather_retriever_tool/weather_tool.py" -r "tools/weather_retriever_tool/requirements.txt"

#agents import 
orchestrate agents import -f agents/weather_agent.yaml
orchestrate agents import -f agents/news_agent.yaml
orchestrate agents import -f agents/disruption_detector_agent.yaml

cd wxo-domains

bash import --manager collaborator_agents/supply_chain/sterling_order_management_agent.yaml

orchestrate agents import -f agents/supply_chain_agent.yaml

# List everything
orchestrate agents list
#!/bin/bash
set -e  # Exit immediately if a command fails

echo "🚀 Starting Watson Orchestrate import process..."

# -------------------------
# 1️⃣ Import Tools
# -------------------------
echo "📦 Importing tools..."

# Tool that fetches a motivational quote
orchestrate tools import -k python -f ./tools/get_quote_min.py

# Tool that sends email using MailerSend API
orchestrate tools import -k python -f ./tools/send_email_tool.py

echo "✅ Tools imported successfully!"


# -------------------------
# 2️⃣ Import Flows
# -------------------------
echo "🌀 Importing flows..."

# Flow that retrieves a quote
orchestrate flows import -f ./tools/daily_quote_flow_min.py


echo "✅ Flows imported successfully!"


# -------------------------
# 3️⃣ Import Agents
# -------------------------
echo "🤖 Importing agents..."

# Agent responsible for sending emails via SMTP
orchestrate agents import -f ./agents/email_test_agent.yaml

# Agent responsible for scheduling email or quote flows
orchestrate agents import -f ./agents/schedule_daily_quote_agent.yaml

echo "✅ Agents imported successfully!"


echo "🎉 All components imported successfully!"

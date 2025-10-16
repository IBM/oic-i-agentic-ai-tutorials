#!/bin/bash
set -e  # Exit immediately if a command fails

echo "🚀 Starting Watson Orchestrate import process..."

# -------------------------
# 1️⃣ Import Tools
# -------------------------
echo "📦 Importing tools..."

# Tool that fetches a motivational quote
orchestrate tools import -k python -f get_quote_min.py

# Tool that sends email using MailerSend API
orchestrate tools import -k python -f send_email_mailersend.py

echo "✅ Tools imported successfully!"


# -------------------------
# 2️⃣ Import Flows
# -------------------------
echo "🌀 Importing flows..."

# Flow that retrieves a quote
orchestrate flows import -f daily_quote_flow_min.py

# Flow that sends an email (uses email_notifier_agent internally)
orchestrate flows import -f send_email_flow.py

echo "✅ Flows imported successfully!"


# -------------------------
# 3️⃣ Import Agents
# -------------------------
echo "🤖 Importing agents..."

# Agent responsible for sending emails via MailerSend
orchestrate agents import -f email_notifier_agent.yaml

# Agent responsible for scheduling email or quote flows
orchestrate agents import -f schedule_daily_quote_agent_min.yaml

echo "✅ Agents imported successfully!"


echo "🎉 All components imported successfully!"

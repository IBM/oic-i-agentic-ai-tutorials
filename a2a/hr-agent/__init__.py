"""
HR Agent Package

This package contains a complete HR onboarding agent that works with
Watsonx Orchestrate and other orchestration platforms.

Main Components:
- agent_executor.py: Core business logic for processing onboarding requests
- main.py: HTTP server providing OpenAI-compatible API endpoints
- Dockerfile: Container packaging for cloud deployment
- hr_agent.yaml: Configuration for Watsonx Orchestrate integration

The agent accepts natural language requests like "Onboard John Doe as Engineer"
and generates structured employee records with auto-generated IDs and email addresses.
"""

__version__ = "1.0.0"

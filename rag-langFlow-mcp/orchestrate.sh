#!/bin/bash
# Helper script to run orchestrate commands with proper environment

set -e

# Activate virtual environment
source .venv/bin/activate

# Load environment variables
source .env

# Run orchestrate command with all arguments passed to this script
orchestrate "$@"

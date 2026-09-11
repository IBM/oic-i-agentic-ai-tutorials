#! /usr/bin/env bash

set -e
set -x

# Let the DB start
python app/backend_pre_start.py

# Run migrations only if database is configured
if [ -n "$POSTGRES_SERVER" ] && [ -n "$POSTGRES_USER" ]; then
    echo "Database configured, running migrations..."
    alembic upgrade head
    # Create initial data in DB
    python app/initial_data.py
else
    echo "Database not configured, skipping migrations and initial data"
fi

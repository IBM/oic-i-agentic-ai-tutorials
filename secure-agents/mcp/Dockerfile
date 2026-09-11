
# syntax=docker/dockerfile:1
# Multi-process build with nginx proxy and Python MCP server (OpenShift compatible)

FROM python:3.12-slim

WORKDIR /app

# Install nginx, supervisor, curl and build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    nginx \
    supervisor \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first for better cache
COPY pyproject.toml README.md ./

# Install dependencies directly from pyproject.toml
RUN pip install --no-cache-dir .

# Copy the rest of the application
COPY . .

# Copy nginx configuration (OpenShift compatible - no default user directive)
COPY nginx.conf /etc/nginx/sites-available/default
RUN rm -f /etc/nginx/sites-enabled/default && \
    ln -s /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default

# Copy supervisor configuration
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# OpenShift compatibility: Create directories and set permissions for arbitrary UID
# OpenShift runs containers with random UID but GID 0 (root group)
RUN mkdir -p /var/log/nginx /var/log/supervisor /var/run/supervisor /var/cache/nginx \
             /var/lib/nginx /tmp/.local/share/fastmcp && \
    touch /var/log/nginx/mcp_access.log /var/log/nginx/mcp_error.log && \
    # Make everything writable by root group (GID 0)
    chgrp -R 0 /app /var/log/nginx /var/log/supervisor /var/run /var/cache/nginx /var/lib/nginx /tmp/.local && \
    chmod -R g=u /app /var/log/nginx /var/log/supervisor /var/run /var/cache/nginx /var/lib/nginx /tmp/.local && \
    # Nginx needs to write PID file
    chmod g+w /var/run && \
    # Make nginx config writable for potential runtime modifications
    chmod -R g=u /etc/nginx

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    SERVER_HOST=0.0.0.0 \
    SERVER_PORT=8001 \
    PYTHONPATH="/app/src" \
    HOME=/tmp

# Switch to non-root user for OpenShift compatibility
# Use UID 1001 which is commonly used in OpenShift
# OpenShift will override this with its own arbitrary UID from the allowed range
USER 1001

# Expose ports (8080 for nginx, 8001 for MCP, 8002 for health)
EXPOSE 8080 8001 8002

# Run supervisor to manage both nginx and Python server
# OpenShift will run this as arbitrary UID with GID 0
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
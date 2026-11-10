# =============================================================================
# Dockerfile — WXO OTLP Trace Forwarder Container
# =============================================================================
FROM python:3.11-slim

WORKDIR /app

# Ensure non-buffered stdout/stderr output
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=4318

# Copy application code only. Config/secrets are injected at runtime via --env-file.
COPY forwarder/ /app/forwarder/

# Expose standard OTLP port
EXPOSE 4318

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:4318/health', timeout=2)" || exit 1

# Start the forwarder receiver daemon
ENTRYPOINT ["python3", "-m", "forwarder.wire_agent", "--receiver"]

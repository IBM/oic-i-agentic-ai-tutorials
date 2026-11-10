# Flow B Dockerfile — WXO hook via sitecustomize.py
# ===================================================
# What this does
# --------------
# Copies sitecustomize.py into the Python site-packages directory.
# Python automatically imports sitecustomize at startup — BEFORE any user
# code — so it patches the HTTP handler without touching server.py or
# agent.py.
#
# What does NOT change
# --------------------
#   - server.py / agent.py / any user code
#   - CMD / ENTRYPOINT — the container starts exactly as before
#   - Port, health check, or any runtime configuration
#
# All config comes from env vars injected by wire_agent.sh via
# Cloud Run update (WXO_AGENT_ID, WXO_TENANT_ID, WXO_OTEL_EXPORT_URL, …).
#
# Build context: repo root (invoked with -f container_hook/Dockerfile .)
# sitecustomize.py is read from shared/ — the single canonical source.

ARG SOURCE_IMAGE
FROM ${SOURCE_IMAGE}

USER root

# Find the site-packages dir and drop sitecustomize.py there.
# Works for any Python 3.x regardless of minor version.
COPY shared/sitecustomize.py /tmp/wxo_sitecustomize.py
RUN SITE=$(python3 -c "import site; print(site.getsitepackages()[0])") && \
    cp /tmp/wxo_sitecustomize.py "${SITE}/sitecustomize.py" && \
    echo "WXO hook installed at ${SITE}/sitecustomize.py"

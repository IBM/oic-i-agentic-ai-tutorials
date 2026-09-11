# ── Build stage ────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Runtime stage ──────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Non-root user for Code Engine security best practice
RUN groupadd -r appgroup && useradd -r -g appgroup -d /app -s /sbin/nologin appuser

WORKDIR /app

# Copy installed packages from build stage
COPY --from=builder /install /usr/local

# Copy application source
COPY a2a_types.py   ./a2a_types.py
COPY server.py      ./server.py
COPY agent.py       ./agent.py
COPY tools.py       ./tools.py
COPY wxo_otel.py    ./wxo_otel.py

# Copy the static .well-known directory (also served dynamically at runtime)
COPY .well-known/   ./.well-known/

# Ownership
RUN chown -R appuser:appgroup /app

USER appuser

# IBM Code Engine listens on PORT env var (default 8080)
ENV PORT=8080
ENV HOST=0.0.0.0
ENV GEMINI_MODEL=gemini-2.5-flash
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8080

# Uvicorn with a single worker per replica (Code Engine scales via replicas).
# For production consider gunicorn + uvicorn workers if needed.
CMD ["sh", "-c", "uvicorn server:app --host $HOST --port $PORT --workers 1 --log-level info"]

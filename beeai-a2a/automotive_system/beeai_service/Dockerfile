FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project configuration first
COPY pyproject.toml ./

# Create the beeai_service package structure
COPY __init__.py ./beeai_service/__init__.py
COPY __main__.py ./beeai_service/__main__.py
COPY config/ ./beeai_service/config/
COPY core/ ./beeai_service/core/
COPY servers/ ./beeai_service/servers/

# Install the package in editable mode
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# Create non-root user for security
RUN useradd -m -u 1000 beeai && \
    chown -R beeai:beeai /app

USER beeai

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run the application
CMD ["python", "-m", "beeai_service"]
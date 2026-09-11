FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for confluent-kafka
RUN apt-get update && apt-get install -y \
    librdkafka-dev \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY mcp_server_sse.py .
COPY consumer.py .

# Expose port 8080 (Code Engine default)
EXPOSE 8080

# Run MCP server in SSE mode
CMD ["python3", "mcp_server_sse.py"]

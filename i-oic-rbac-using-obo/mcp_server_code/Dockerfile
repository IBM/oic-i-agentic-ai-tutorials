# Use Python 3.11 slim image
FROM python:3.11-slim

# Ensure logs are flushed immediately (important for Code Engine)
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY server.py .

# Code Engine provides PORT via env var, EXPOSE is optional
EXPOSE 8000

# Run the MCP server
CMD ["python", "server.py"]

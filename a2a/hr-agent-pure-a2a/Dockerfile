FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app ./app
COPY pyproject.toml .

# Expose port
EXPOSE 8080

# Start the agent
CMD ["python", "-m", "app", "--host", "0.0.0.0", "--port", "8080"]

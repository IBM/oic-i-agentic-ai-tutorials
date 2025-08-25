# Use slim Python base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY ./api ./api

# Optionally include .env (for local testing only – not for cloud deployments)
# Comment this out if using Code Engine env vars
 COPY .env .env

# Set startup command
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

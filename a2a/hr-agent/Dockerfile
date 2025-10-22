# HR Agent Docker Container
#
# This Dockerfile packages the HR agent as a container that can run anywhere:
# locally with Docker, in IBM Code Engine, or any other container platform.

# Start with Python 3.11 slim image (smaller than the full Python image)
FROM python:3.11-slim

# Python configuration for better container behavior:
# - PYTHONDONTWRITEBYTECODE: Prevents Python from creating .pyc files
# - PYTHONUNBUFFERED: Ensures logs appear immediately (important for debugging)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set working directory where our application will live
WORKDIR /app

# Install Python dependencies first
# We do this before copying code to take advantage of Docker's layer caching.
# If requirements.txt doesn't change, Docker reuses this layer on rebuilds.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
# These files contain the actual agent logic
COPY __init__.py .
COPY main.py .
COPY agent_executor.py .

# Expose port 8080
# IBM Code Engine expects services to listen on port 8080
# For local testing, you can map this to any host port (e.g., -p 8000:8080)
EXPOSE 8080

# Start the HR agent when the container runs
# This launches the HTTP server that handles incoming requests
CMD ["python", "main.py"]

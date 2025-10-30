FROM python:3.11-slim


# optional: install system libs for torch wheels as needed
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*


WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download model during build to avoid runtime downloads
COPY download_model.py .
ENV MODEL_NAME=ibm-granite/granite-4.0-h-1b
RUN python3 download_model.py

COPY server.py .
ENV AUTH_TOKEN="change-me"


EXPOSE 8080
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]
FROM registry.redhat.io/ubi9/python-311-minimal:latest

# Create non-root user
RUN useradd -m -u 1001 appuser

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application (nltk removed — no RUN nltk.download() step needed)
COPY --chown=appuser:appuser app.py .

USER 1001

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "127.0.0.1", "--port", "8000"]
